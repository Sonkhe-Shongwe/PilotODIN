"""Disarmed, archive-only DLA independent observation. No extraction or use.

The publisher archive is an independently pinned input, not a staging
receipt. This program cannot qualify a model, licence or runtime.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import signal
import ssl
import sys
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request
import unittest
import zipfile

from qa.p4_research.dla_stage1_contract import (
    ARCHIVE_BYTES, ARCHIVE_SHA, inspect_pinned_runtime_snapshot,
)
from tools.build_input_preflight import Blocked, require

ARMED = False
URL = "https://github.com/ggml-org/llama.cpp/releases/download/b10344/llama-b10344-bin-win-cpu-x64.zip"
BRANCH = "refs/heads/feature/dla-stage1-archive-20261128"
REDIRECT_HOST = "release-assets.githubusercontent.com"
REDIRECT_PATH = re.compile(
    r"/github-production-release-asset/612354784/[0-9a-fA-F-]{36}", re.ASCII)
SHA = re.compile(r"[0-9a-f]{40}", re.ASCII)
NOTICE = re.compile(
    r"(?:licen[cs]e|copying|notice|third[-_ ]party|copyright)(?:[._-][A-Za-z0-9_.-]+)?",
    re.IGNORECASE | re.ASCII)
MAX_NOTICE = 65536
MAX_NOTICES = 131072
MAX_RECEIPT = 524288


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def request(url):
    return Request(url, headers={"Accept-Encoding": "identity",
                                 "User-Agent": "PilotODIN-DLA-archive-review/1"},
                   method="GET")


def redirect_destination(locations):
    require(len(locations) == 1 and 0 < len(locations[0]) <= 8192,
            "DLA_REDIRECT_COUNT")
    loc = locations[0]
    require(loc.isascii() and all(33 <= ord(c) <= 126 for c in loc)
            and "\\" not in loc, "DLA_REDIRECT_CHARACTERS")
    u = urlsplit(loc)
    require(u.scheme == "https" and u.netloc == REDIRECT_HOST
            and REDIRECT_PATH.fullmatch(u.path) is not None
            and bool(u.query) and not u.fragment, "DLA_REDIRECT_DESTINATION")
    return loc


def exact_body(response):
    require(response.status == 200, "DLA_HTTP_STATUS")
    require(response.headers.get_all("Content-Length", []) == [str(ARCHIVE_BYTES)],
            "DLA_HTTP_LENGTH")
    require(response.headers.get_all("Content-Encoding", []) in ([], ["identity"])
            and not response.headers.get_all("Transfer-Encoding", []),
            "DLA_HTTP_FRAMING")
    raw = response.read(ARCHIVE_BYTES)
    require(len(raw) == ARCHIVE_BYTES and
            hashlib.sha256(raw).hexdigest() == ARCHIVE_SHA, "DLA_ARCHIVE_IDENTITY")
    return raw


def fetch_once(opener):
    # Maximum two GETs: exact publisher URL and one constrained 302.
    # No body read on redirect; no credentials, proxies, retry or fallback.
    try:
        response = opener.open(request(URL), timeout=15)
    except HTTPError as error:
        try:
            require(error.code == 302, "DLA_REDIRECT_STATUS")
            destination = redirect_destination(error.headers.get_all("Location", []))
        finally:
            error.close()
        with opener.open(request(destination), timeout=15) as response:
            require(response.geturl() == destination, "DLA_REDIRECT_UNEXPECTED")
            return exact_body(response), 2
    else:
        with response:
            require(response.geturl() == URL, "DLA_ORIGIN_UNEXPECTED")
            return exact_body(response), 1


def receipt(raw, gets):
    members = inspect_pinned_runtime_snapshot(raw)
    notices = {}
    total = 0
    # Reuse the strict parser's verified snapshot. zipfile is used only to
    # read bounded public notice bytes from that same snapshot, never extract.
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(len(archive.infolist()) == len(members) and
                set(archive.namelist()) == set(members), "DLA_NOTICE_LAYOUT")
        for name, row in sorted(members.items()):
            if not NOTICE.fullmatch(name.rsplit("/", 1)[-1]):
                continue
            total += row["bytes"]
            require(row["bytes"] <= MAX_NOTICE and total <= MAX_NOTICES,
                    "DLA_NOTICE_LIMIT")
            with archive.open(name) as stream:
                body = stream.read(row["bytes"] + 1)
            require(len(body) == row["bytes"] and
                    hashlib.sha256(body).hexdigest() == row["sha256"],
                    "DLA_NOTICE_IDENTITY")
            notices[name] = base64.b64encode(body).decode("ascii")
    # Missing notices or an unfamiliar component do not establish rights.
    return {"scope": "INDEPENDENT_ARCHIVE_OBSERVATION_ONLY",
            "publisher": URL, "archive_bytes": ARCHIVE_BYTES, "archive_sha256": ARCHIVE_SHA,
            "gets": gets, "members": members, "notice_base64": notices,
            "rights_reviewed": False, "runtime_qualified": False,
            "production_ready": False}


def run():
    require(ARMED, "DLA_FRESH_APPROVAL_REQUIRED")
    require(os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("GITHUB_EVENT_NAME") == "push"
            and os.environ.get("GITHUB_REF") == BRANCH
            and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
            and os.environ.get("RUNNER_OS") == "Linux"
            and os.environ.get("RUNNER_ARCH") == "X64"
            and os.environ.get("ImageVersion") == "20261122.23.1"
            and os.environ.get("ImageOS") == "ubuntu24"
            and os.getuid() != 0, "DLA_HOST_SCOPE")
    before = os.environ.get("DLA_EXPECTED_BEFORE", "")
    source = os.environ.get("GITHUB_SHA", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    require(SHA.fullmatch(before) and SHA.fullmatch(source)
            and re.fullmatch(r"[0-9]{1,20}", run_id), "DLA_EVENT_ID")
    with open(os.environ["GITHUB_EVENT_PATH"], "rb") as stream:
        event_bytes = stream.read(1048577)
    require(len(event_bytes) <= 1048576, "DLA_EVENT_LIMIT")
    event = json.loads(event_bytes)
    require(event.get("before") == before and event.get("after") == source
            and event.get("ref") == BRANCH, "DLA_EVENT_BINDING")
    require(signal.getitimer(signal.ITIMER_REAL) == (0., 0.), "DLA_TIMER_BUSY")
    def expired(*_):
        raise Blocked("DLA_INSPECTION_DEADLINE")
    prior = signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, 90)
        context = ssl.create_default_context()
        opener = build_opener(ProxyHandler({}), NoRedirect(), HTTPSHandler(context=context))
        raw, gets = fetch_once(opener)
        report = receipt(raw, gets)
        del raw
        report.update(run_id=run_id, source_sha=source,
                      host_image=os.environ["ImageVersion"], python=sys.version.split()[0])
        # Emit bounded deterministic, safely escaped records, not raw notice
        # text or signed URLs. Reconstruct and hash canonical JSON on review.
        wire = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        require(len(wire) <= MAX_RECEIPT, "DLA_RECEIPT_LIMIT")
        digest = hashlib.sha256(wire).hexdigest()
        encoded = base64.b64encode(wire).decode("ascii")
        for i in range(0, len(encoded), 4096):
            print("DLA_ARCHIVE_RECEIPT", i // 4096, encoded[i:i+4096], flush=True)
        print("DLA_ARCHIVE_RECEIPT_END", len(wire), digest, flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, prior)


class TransportContracts(unittest.TestCase):
    def test_exact_redirect(self):
        good = "https://" + REDIRECT_HOST + "/github-production-release-asset/612354784/" + "a"*36 + "?signed=opaque"
        self.assertEqual(redirect_destination([good]), good)
        for bad in (good.replace("https:", "http:"), good.replace(REDIRECT_HOST, "evil.example"),
                    good.replace("612354784", "1"), good + "#fragment",
                    good.replace(REDIRECT_HOST, REDIRECT_HOST + ":443"),
                    good.replace(REDIRECT_HOST, "user@" + REDIRECT_HOST), good + "\n"):
            with self.subTest(bad=bad), self.assertRaises(Blocked):
                redirect_destination([bad])
        for bad in ([], [good, good]):
            with self.assertRaises(Blocked):
                redirect_destination(bad)

    def test_exact_length_and_encoding(self):
        from email.message import Message
        from unittest.mock import Mock
        for headers in ({"Content-Length": "1"}, {"Content-Length": str(ARCHIVE_BYTES), "Content-Encoding": "gzip"},
                        {"Content-Length": str(ARCHIVE_BYTES), "Transfer-Encoding": "chunked"}):
            resp = Mock(status=200, headers=Message())
            for k, v in headers.items():
                resp.headers[k] = v
            with self.assertRaises(Blocked):
                exact_body(resp)
            resp.read.assert_not_called()
        resp = Mock(status=200, headers=Message())
        resp.headers["Content-Length"] = str(ARCHIVE_BYTES)
        resp.read.return_value = b"short"
        with self.assertRaises(Blocked):
            exact_body(resp)
        resp.read.assert_called_once_with(ARCHIVE_BYTES)

    def test_no_automatic_redirect(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, URL))
        req = request(URL)
        self.assertIsNone(req.get_header("Authorization"))
        self.assertEqual(req.get_method(), "GET")


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(TransportContracts)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        raise SystemExit(0 if result.wasSuccessful() and result.testsRun == 3 else 1)
    if sys.argv[1:] != ["--inspect-once"]:
        raise SystemExit(2)
    try:
        run()
    except Exception:
        # Never expose signed URLs, exceptions, credentials or payloads.
        print("DLA_ARCHIVE_INSPECTION_REFUSED", flush=True)
        raise SystemExit(2)
