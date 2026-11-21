"""Source-only QA private child-handle transport regression tests."""
from dataclasses import replace
import json
from multiprocessing.connection import Client
import os
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_private_child_pipe as bridge
from qa.p4_research.n12_no_cdp_child_handles import (
    CHILD_HANDLE_CONSENT, PrivateChildHandleEvidence,
)


SOURCE = "a" * 40
HASH = "b" * 64
WEB = r"c:\qa\webview\msedgewebview2.exe"
NATIVE = r"\Device\HarddiskVolume3\qa\webview\msedgewebview2.exe"


def fixture():
    return PrivateChildHandleEvidence(
        source_sha=SOURCE, executable_sha256=HASH,
        root_birth_ticks=900000, sampling_started_ticks=950000,
        sampling_finished_ticks=2000000,
        witnesses=({"pid": 602, "birth": 1010000, "exit": 1600000,
                    "image_dos": WEB, "image_native": NATIVE, "parent_pid": 601},),
        collector_receipt={
            "scope": "isolated-qa-webview-original-handle-sampler",
            "status": "SAMPLING_FINISHED_UNVERIFIED",
            "sample_count": 3, "retained_original_handle_count": 1,
            "faults": {}, "native_N12_acceptance": "NOT_EVALUATED",
        })


class PrivateChildPipeTests(unittest.TestCase):
    def test_private_wire_round_trip_exact(self):
        evidence = fixture()
        wire = bridge.encode(evidence)
        self.assertIn(b'"pid":602', wire)
        self.assertEqual(bridge.decode(wire, source=SOURCE, expected_hash=HASH), evidence)
        self.assertLess(len(wire), bridge.MAX_BYTES)

    def test_provenance_identity_schema_and_length_are_fail_closed(self):
        evidence = fixture()
        wire = bridge.encode(evidence)
        for source, digest in (("c" * 40, HASH), (SOURCE, "d" * 64)):
            with self.subTest(source=source), self.assertRaises(trace.EvidenceValidationError):
                bridge.decode(wire, source=source, expected_hash=digest)
        record = json.loads(wire)
        variants = (
            {**record, "unexpected_owner_private": "secret"},
            {**record, "root_birth_ticks": False},
            {**record, "witnesses": [dict(record["witnesses"][0], pid="602")]},
            {**record, "witnesses": record["witnesses"] * 97},
            {**record, "witnesses": record["witnesses"] * 2},
            {**record, "witnesses": [dict(record["witnesses"][0], image_dos="private")]},
            {**record, "witnesses": [dict(record["witnesses"][0], parent_pid=-2)]},
            {**record, "collector_receipt": {**record["collector_receipt"], "sample_count": "1"}},
            {**record, "collector_receipt": {**record["collector_receipt"],
                                             "retained_original_handle_count": 2}},
        )
        for variant in variants:
            with self.subTest(variant=str(variant)[:50]):
                with self.assertRaisesRegex(trace.EvidenceValidationError,
                                            "no-cdp-private-child-pipe-rejected") as context:
                    bridge.decode(json.dumps(variant).encode("ascii"), source=SOURCE,
                                  expected_hash=HASH)
                self.assertNotIn("secret", str(context.exception))
        for data in (b"", b"\xff", b"not json", b"z" * (bridge.MAX_BYTES + 1)):
            with self.assertRaises(trace.EvidenceValidationError):
                bridge.decode(data, source=SOURCE, expected_hash=HASH)

    def test_default_off_and_unapproved_host_block_before_windows_pipe(self):
        self.assertFalse(bridge.requested({}))
        self.assertTrue(bridge.requested({
            "PILOTODIN_N12_CHILD_HANDLE_CONSENT": CHILD_HANDLE_CONSENT}))
        with self.assertRaises(trace.EvidenceValidationError):
            bridge.requested({"PILOTODIN_N12_CHILD_HANDLE_CONSENT": "invalid"})
        with patch.object(bridge.os, "name", "posix"), patch.object(bridge, "Listener") as listener:
            with self.assertRaises(trace.EvidenceValidationError):
                bridge.hosted_channel({}, SOURCE, HASH)
            listener.assert_not_called()
        with patch.object(bridge.os, "name", "posix"), patch.object(bridge, "Client") as client:
            with self.assertRaises(trace.EvidenceValidationError):
                bridge.send_from_worker({}, fixture())
            client.assert_not_called()

    @unittest.skipUnless(hasattr(socket, "AF_UNIX"), "Unix sockets unavailable")
    def test_authenticated_one_shot_memory_only_send(self):
        with TemporaryDirectory(prefix="p4-private-pipe-") as temp:
            address = str(Path(temp) / "fixture.sock")
            transport = bridge.PrivateChildPipe(
                address=address, family="AF_UNIX", key=b"k" * 32,
                source=SOURCE, expected_hash=HASH)
            with transport:
                worker = Thread(target=self._send, args=(address, bridge.encode(fixture()), b"k" * 32))
                worker.start()
                value = transport.take()
                worker.join(timeout=2)
                self.assertFalse(worker.is_alive())
                self.assertEqual(value, fixture())
                self.assertEqual(transport.worker_environment({})[bridge.PIPE_ENV], address)
                self.assertEqual(set(Path(temp).iterdir()), {Path(address)})
            self.assertIsNone(transport._received)
            self.assertNotIn("pid", json.dumps({"status": "REVIEWABLE_ONLY"}))

    @staticmethod
    def _send(address, data, key):
        with Client(address, family="AF_UNIX", authkey=key) as connection:
            connection.send_bytes(data)

    @unittest.skipUnless(hasattr(socket, "AF_UNIX"), "Unix sockets unavailable")
    def test_rejected_private_message_never_returns_payload(self):
        with TemporaryDirectory(prefix="p4-private-reject-") as temp:
            address = str(Path(temp) / "fixture.sock")
            with bridge.PrivateChildPipe(
                address=address, family="AF_UNIX", key=b"x" * 32,
                source=SOURCE, expected_hash=HASH) as transport:
                worker = Thread(target=self._send, args=(address, b'{"private":"bad"}', b"x" * 32))
                worker.start()
                with self.assertRaisesRegex(trace.EvidenceValidationError,
                                            "no-cdp-private-child-pipe-unverified"):
                    transport.take()
                worker.join(timeout=2)

    def test_no_unapproved_observer_can_be_created_by_default(self):
        # Source-only checks prove no native workflow sets child consent.
        from qa.p4_research import n12_app_build as build
        workflow = (build.REPO / ".github/workflows/p4-n12-app-lifetime.yml").read_text("utf-8")
        self.assertIn("if: $" + "{{ false }}", workflow)
        self.assertNotIn("PILOTODIN_N12_CHILD_HANDLE_CONSENT", workflow)
        self.assertNotIn("PILOTODIN_N12_PRIVATE_CHILD_PIPE_KEY", workflow)
