"""Authenticated in-memory, default-off QA worker-to-reducer handle transport.

Raw original WebView process handles stay out of log output, filesystem
artifacts and native acceptance. This module does not start a native run.
"""
from dataclasses import asdict
import json
from multiprocessing.connection import Listener, Client
import os
import re
import secrets
from threading import Thread
from uuid import uuid4

from qa.p4_native import n12_trace as trace
from qa.p4_research.n12_no_cdp_child_handles import (
    CHILD_HANDLE_CONSENT, MAX_HANDLES, PrivateChildHandleEvidence,
)


PIPE_ENV = "PILOTODIN_N12_PRIVATE_CHILD_PIPE"
KEY_ENV = "PILOTODIN_N12_PRIVATE_CHILD_PIPE_KEY"
MAX_BYTES = 65536
FIELDS = frozenset({"source_sha", "executable_sha256", "root_birth_ticks",
                    "sampling_started_ticks", "sampling_finished_ticks",
                    "witnesses", "collector_receipt"})
WITNESS_FIELDS = frozenset({"pid", "birth", "exit", "image_dos",
                            "image_native", "parent_pid"})
RECEIPT_FIELDS = frozenset({"scope", "status", "sample_count",
                            "retained_original_handle_count", "faults",
                            "native_N12_acceptance"})


def requested(env):
    value = env.get("PILOTODIN_N12_CHILD_HANDLE_CONSENT", "")
    trace.require(value in ("", CHILD_HANDLE_CONSENT),
                  "no-cdp-child-handle-consent-invalid")
    return value == CHILD_HANDLE_CONSENT


def hosted_scope(env, source, expected_hash):
    trace.require(os.name == "nt" and env.get("GITHUB_ACTIONS") == "true"
                  and env.get("RUNNER_ENVIRONMENT") == "github-hosted"
                  and env.get("RUNNER_OS") == "Windows"
                  and env.get("GITHUB_EVENT_NAME") == "push"
                  and env.get("GITHUB_RUN_ATTEMPT") == "1"
                  and env.get("PILOTODIN_N12_APPROVED_SOURCE") == source
                  and env.get("PILOTODIN_N12_NO_CDP_STORAGE_CONSENT")
                  == "I_APPROVE_ONE_N12_NO_CDP_STORAGE"
                  and requested(env)
                  and re.fullmatch(r"[0-9a-f]{40}", source)
                  and re.fullmatch(r"[0-9a-f]{64}", expected_hash),
                  "no-cdp-child-pipe-hosted-approval-unverified")


def encode(evidence):
    trace.require(type(evidence) is PrivateChildHandleEvidence,
                  "no-cdp-child-pipe-evidence-type-unverified")
    record = asdict(evidence)
    raw = json.dumps(record, separators=(",", ":"), ensure_ascii=True,
                     allow_nan=False).encode("ascii")
    trace.require(len(raw) <= MAX_BYTES, "no-cdp-child-pipe-payload-too-large")
    return raw


def decode(raw, *, source, expected_hash):
    try:
        trace.require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES,
                      "no-cdp-child-pipe-message-invalid")
        record = json.loads(raw.decode("ascii"))
        trace.require(type(record) is dict and set(record) == FIELDS
                      and record["source_sha"] == source
                      and record["executable_sha256"] == expected_hash,
                      "no-cdp-child-pipe-provenance-invalid")
        for name in ("root_birth_ticks", "sampling_started_ticks", "sampling_finished_ticks"):
            trace.require(type(record[name]) is int and record[name] > 0,
                          "no-cdp-child-pipe-clock-invalid")
        rows = record["witnesses"]
        trace.require(type(rows) is list and len(rows) <= MAX_HANDLES,
                      "no-cdp-child-pipe-witness-count-invalid")
        seen = set()
        for w in rows:
            trace.require(type(w) is dict and set(w) == WITNESS_FIELDS
                          and all(type(w[k]) is int and w[k] > 0
                                  for k in ("pid", "birth", "exit", "parent_pid"))
                          and w["birth"] <= w["exit"]
                          and all(type(w[k]) is str and 0 < len(w[k]) <= 1024
                                  for k in ("image_dos", "image_native"))
                          and w["image_native"].casefold().startswith("\\device\\"),
                          "no-cdp-child-pipe-original-handle-invalid")
            trace.windows_path(w["image_dos"])
            identity = w["pid"], w["birth"]
            trace.require(identity not in seen, "no-cdp-child-pipe-duplicate-handle")
            seen.add(identity)
        receipt = record["collector_receipt"]
        trace.require(type(receipt) is dict and set(receipt) == RECEIPT_FIELDS
                      and type(receipt["sample_count"]) is int
                      and 0 <= receipt["sample_count"] <= 1_000_000
                      and type(receipt["retained_original_handle_count"]) is int
                      and receipt["retained_original_handle_count"] == len(rows)
                      and type(receipt["faults"]) is dict
                      and all(type(k) is str and len(k) <= 64
                              and type(v) is int and 0 <= v <= 1_000_000
                              for k, v in receipt["faults"].items())
                      and receipt["scope"] == "isolated-qa-webview-original-handle-sampler"
                      and receipt["status"] in {"BLOCKED", "SAMPLING_FINISHED_UNVERIFIED"}
                      and receipt["native_N12_acceptance"] == "NOT_EVALUATED",
                      "no-cdp-child-pipe-collector-invalid")
        return PrivateChildHandleEvidence(
            source_sha=source, executable_sha256=expected_hash,
            root_birth_ticks=record["root_birth_ticks"],
            sampling_started_ticks=record["sampling_started_ticks"],
            sampling_finished_ticks=record["sampling_finished_ticks"],
            witnesses=tuple(rows), collector_receipt=receipt)
    except (UnicodeError, ValueError, KeyError, TypeError, OverflowError,
            trace.EvidenceValidationError):
        # Never echo untrusted private values to caller's logs.
        raise trace.EvidenceValidationError("no-cdp-private-child-pipe-rejected") from None


class PrivateChildPipe:
    """One authenticated frame. Production uses AF_PIPE; tests use AF_UNIX."""

    def __init__(self, *, address, family, key, source, expected_hash):
        trace.require(family in {"AF_PIPE", "AF_UNIX"}
                      and type(key) is bytes and len(key) == 32,
                      "no-cdp-child-pipe-configuration-invalid")
        self.address, self.family = address, family
        self.key, self.source, self.expected_hash = key, source, expected_hash
        self._listener = None
        self._thread = None
        self._received = None
        self._error = False

    def __enter__(self):
        self._listener = Listener(address=self.address, family=self.family,
                                  authkey=self.key)
        self._thread = Thread(target=self._read_one, daemon=True,
                              name="n12-private-child-witness-receiver")
        self._thread.start()
        return self

    def worker_environment(self, env):
        return {**env, PIPE_ENV: self.address, KEY_ENV: self.key.hex()}

    def _read_one(self):
        try:
            with self._listener.accept() as connection:
                raw = connection.recv_bytes(MAX_BYTES)
            self._received = decode(raw, source=self.source, expected_hash=self.expected_hash)
        except Exception:
            self._error = True

    def take(self):
        self._thread.join(timeout=8)
        trace.require(not self._thread.is_alive() and not self._error
                      and self._received is not None,
                      "no-cdp-private-child-pipe-unverified")
        result, self._received = self._received, None
        return result

    def __exit__(self, *_):
        if self._thread is not None and self._thread.is_alive():
            try:
                with Client(self.address, family=self.family, authkey=self.key) as connection:
                    connection.send_bytes(b"")
            except (OSError, EOFError, ConnectionError):
                pass
            self._thread.join(timeout=4)
        if self._listener is not None:
            self._listener.close()


def hosted_channel(env, source, expected_hash):
    hosted_scope(env, source, expected_hash)
    return PrivateChildPipe(address=r"\\.\pipe\pilotodin-n12-child-" + uuid4().hex,
                            family="AF_PIPE", key=secrets.token_bytes(32),
                            source=source, expected_hash=expected_hash)


def send_from_worker(env, evidence):
    hosted_scope(env, evidence.source_sha, evidence.executable_sha256)
    address, secret = env.get(PIPE_ENV, ""), env.get(KEY_ENV, "")
    trace.require(re.fullmatch(r"\\\\\.\\pipe\\pilotodin-n12-child-[0-9a-f]{32}", address)
                  and re.fullmatch(r"[0-9a-f]{64}", secret),
                  "no-cdp-private-child-pipe-worker-scope-unverified")
    with Client(address, family="AF_PIPE", authkey=bytes.fromhex(secret)) as connection:
        connection.send_bytes(encode(evidence))
