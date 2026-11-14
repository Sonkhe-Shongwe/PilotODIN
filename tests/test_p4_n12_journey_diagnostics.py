"""Generated ETW path and Chromium NetLog diagnostics. No Windows capture needed."""
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from qa.p4_research import n12_journey_diagnostics as diagnostics


OFFSET = 1_800_000_000_000
TYPES = {name: i for i, name in enumerate((
    "TCP_CONNECT", "TCP_CONNECT_ATTEMPT", "UDP_CONNECT", "UDP_LOCAL_ADDRESS",
    "URL_REQUEST_START_JOB", "SOCKET_POOL_BOUND_TO_SOCKET", "HTTP_STREAM_JOB_BOUND_TO_REQUEST",
    "DNS_TRANSACTION_ATTEMPT",
), 1)}
PHASES = {"PHASE_NONE": 0, "PHASE_BEGIN": 1, "PHASE_END": 2}
SOCKET, JOB, REQUEST = (1, 10), (2, 20), (3, 30)


def event(kind, stamp, source, params=None, phase="PHASE_NONE"):
    return {"type": TYPES[kind], "time": str(stamp), "phase": PHASES[phase],
            "source": {"type": source[0], "id": source[1]}, "params": params or {}}


def payload(events):
    return {"constants": {"logEventTypes": TYPES, "logEventPhase": PHASES,
                          "timeTickOffset": str(OFFSET)}, "events": events}


def observation(stamp=123, protocol="tcp", local=51200, remote="192.0.2.9", port=443):
    return {"role": "webview-network", "process_guid": "private-guid", "address": remote,
            "port": port, "source_port": local, "protocol": protocol,
            "utc": datetime.fromtimestamp((OFFSET + stamp) / 1000, timezone.utc).isoformat()}


def tcp(source=SOCKET, end=125, **params):
    return [
        event("TCP_CONNECT", 120, source, {"address_list": ["192.0.2.9:443", "192.0.2.10:443"]}, "PHASE_BEGIN"),
        event("TCP_CONNECT", end, source, params or {
            "local_address": "[::ffff:10.0.0.9]:51200", "remote_address": "192.0.2.9:443",
        }, "PHASE_END"),
    ]


def link(kind, stamp, source, peer):
    return event(kind, stamp, source, {"source_dependency": {"type": peer[0], "id": peer[1]}})


class JourneyDiagnosticsTests(unittest.TestCase):
    def test_outside_paths_are_fixed_categories_and_count_operations_once(self):
        paths = diagnostics.OutsidePaths([
            ("webview-profile", r"C:\private\owner\webview"), ("runner-temp", r"C:\private\owner"),
        ])
        paths.record("driver", "rename", (r"c:\private\owner\webview\hidden-name",
                                          r"c:\private\owner\another-name",
                                          r"c:\private\owner\third-name"))
        paths.record("backend", "write", (r"c:\private\ownerish\secret.txt",))
        rows = paths.summary()
        self.assertEqual(rows, [
            {"role": "backend", "operation": "write", "path_categories": ["other-path"], "count": 1},
            {"role": "driver", "operation": "rename", "path_categories": ["runner-temp", "webview-profile"],
             "count": 1},
        ])
        self.assertNotIn("private", json.dumps(rows))

    def test_exact_launch_socket_and_explicit_request_chain_without_sensitive_values(self):
        events = [
            event("URL_REQUEST_START_JOB", 115, REQUEST, {"url": "https://private.test/token"}, "PHASE_BEGIN"),
            *tcp(),
            link("SOCKET_POOL_BOUND_TO_SOCKET", 126, JOB, SOCKET),
            link("HTTP_STREAM_JOB_BOUND_TO_REQUEST", 127, JOB, REQUEST),
        ]
        log = diagnostics.NetLog(payload(events))
        obs = observation(remote="::ffff:192.0.2.9")
        report = diagnostics.network_summary([obs], {"private-guid": "first"},
            {"first": "first.json", "relaunch": "relaunch.json"},
            reader=lambda path: ("parsed", log) if path == "first.json" else ("missing", None))
        self.assertEqual(report, {"logs": {"first": "parsed", "relaunch": "missing"}, "observations": [
            {"observation": 1, "socket_status": "matched-socket", "request_category": "https-request"},
        ]})
        for hidden in ("private", "192.0.2", "51200", "token"):
            self.assertNotIn(hidden, json.dumps(report))
        self.assertEqual(log.match(observation(local=51201))[0], "no-socket-match")
        self.assertEqual(log.match(observation(stamp=4100))[0], "no-socket-match")
        self.assertEqual(log.match(observation(remote="192.0.2.10"))[0], "no-socket-match")
        self.assertEqual(log.match(observation(port=80))[0], "no-socket-match")
        blocked = diagnostics.network_summary([obs, {**obs, "role": "backend"}], {},
            {"first": "first.json"}, reader=lambda path: ("parsed", log))
        self.assertEqual([x["socket_status"] for x in blocked["observations"]],
                         ["launch-unverified", "outside-webview"])

    def test_failed_connect_and_conflicting_candidates_stay_unattributed(self):
        log = diagnostics.NetLog(payload(tcp(net_error=-2)))
        self.assertEqual(log.match(observation()), ("no-socket-match", "unattributed"))
        log = diagnostics.NetLog(payload(tcp(source_address="10.0.0.9:51200")))
        self.assertEqual(log.match(observation()), ("no-socket-match", "unattributed"))
        log = diagnostics.NetLog(payload(tcp() + tcp(source=(1, 11))))
        self.assertEqual(log.match(observation()), ("ambiguous-socket", "unattributed"))
        retry = [
            event("TCP_CONNECT_ATTEMPT", 121, SOCKET, {"address": "192.0.2.9:443"}, "PHASE_BEGIN"),
            event("TCP_CONNECT_ATTEMPT", 124, SOCKET, {
                "local_address": "10.0.0.9:51200", "remote_address": "192.0.2.9:443",
            }, "PHASE_END"),
        ]
        log = diagnostics.NetLog(payload(tcp() + retry))
        self.assertEqual(log.match(observation()), ("matched-socket", "unattributed"))

    def test_udp_dns_requires_local_address_and_link(self):
        events = [
            event("UDP_CONNECT", 120, SOCKET, {"address": "192.0.2.9:53"}, "PHASE_BEGIN"),
            event("UDP_LOCAL_ADDRESS", 121, SOCKET, {"address": "10.0.0.9:51200"}),
            event("UDP_CONNECT", 122, SOCKET, phase="PHASE_END"),
        ]
        obs = observation(protocol="udp", port=53)
        self.assertEqual(diagnostics.NetLog(payload(events)).match(obs), ("matched-socket", "unattributed"))
        dns = link("DNS_TRANSACTION_ATTEMPT", 123, JOB, SOCKET)
        self.assertEqual(diagnostics.NetLog(payload(events + [dns])).match(obs),
                         ("matched-socket", "dns-transaction"))
        self.assertEqual(diagnostics.NetLog(payload(events[::2] + [dns])).match(obs),
                         ("no-socket-match", "unattributed"))

    def test_request_redirect_or_shared_socket_does_not_invent_purpose(self):
        events = tcp() + [link("SOCKET_POOL_BOUND_TO_SOCKET", 126, JOB, SOCKET),
                          link("HTTP_STREAM_JOB_BOUND_TO_REQUEST", 127, JOB, REQUEST)]
        for stamp in (115, 116):
            events.append(event("URL_REQUEST_START_JOB", stamp, REQUEST, {"url": f"https://private.test/{stamp}"},
                                "PHASE_BEGIN"))
        self.assertEqual(diagnostics.NetLog(payload(events)).match(observation()),
                         ("matched-socket", "ambiguous-request"))

    def test_missing_truncated_or_oversized_private_log(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(
                diagnostics, "local_disposable_path", side_effect=lambda path, **kw: path):
            log = Path(folder) / "generated-netlog.json"
            self.assertEqual(diagnostics.read_netlog(log), ("missing", None))
            log.write_text('{"private":', encoding="utf-8")
            self.assertEqual(diagnostics.read_netlog(log), ("unusable", None))
            log.write_text(json.dumps(payload(tcp())), encoding="utf-8")
            self.assertEqual(diagnostics.read_netlog(log)[0], "parsed")
            with patch.object(diagnostics, "NETLOG_LIMIT", 10):
                self.assertEqual(diagnostics.read_netlog(log), ("size-limit", None))


if __name__ == "__main__":
    unittest.main()
