"""Generated ETW path and Chromium NetLog diagnostics. No Windows capture needed."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import socket
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from qa.p4_research import n12_journey_diagnostics as diagnostics
from qa.p4_research.n12_backend_wakeup import loop_wakeup_sockets
from qa.p4_native.n12_trace import utc_ticks


OFFSET = 1_800_000_000_000
TYPES = {name: i for i, name in enumerate((
    "TCP_CONNECT", "TCP_CONNECT_ATTEMPT", "UDP_CONNECT", "UDP_LOCAL_ADDRESS",
    "URL_REQUEST_START_JOB", "SOCKET_POOL_BOUND_TO_SOCKET", "HTTP_STREAM_JOB_BOUND_TO_REQUEST",
    "DNS_TRANSACTION_ATTEMPT", "DNS_TRANSACTION", "DNS_TRANSACTION_QUERY",
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
    def test_wakeup_reader_reports_the_two_connected_socket_ends(self):
        self.assertEqual(loop_wakeup_sockets(SimpleNamespace()), [])
        with socket.socket() as listener, socket.socket() as first:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            first.settimeout(2)
            first.connect(listener.getsockname())
            second, _ = listener.accept()
            with second:
                rows = loop_wakeup_sockets(SimpleNamespace(_ssock=first, _csock=second))
                self.assertEqual(rows[0]["local_port"], rows[1]["remote_port"])
                self.assertEqual(rows[0]["remote_port"], rows[1]["local_port"])

    def test_backend_snapshot_requires_same_process_and_both_socket_directions(self):
        obs = {**observation(remote="127.0.0.1", port=62000),
               "role": "backend", "kind": "unexpected-loopback"}
        stamp = datetime.fromisoformat(obs["utc"])
        process = SimpleNamespace(pid=702, guid=obs["process_guid"], start=stamp - timedelta(seconds=1),
                                  end=stamp + timedelta(seconds=5))
        journey = SimpleNamespace(bindings=[({"role": "backend"}, process)])
        outgoing = {"local_address": "::ffff:127.0.0.1", "local_port": obs["source_port"],
                    "remote_address": "127.0.0.1", "remote_port": obs["port"]}
        reverse = {"local_address": outgoing["remote_address"], "local_port": outgoing["remote_port"],
                   "remote_address": outgoing["local_address"], "remote_port": outgoing["local_port"]}
        snapshot = {"pid": process.pid, "birth_ticks": utc_ticks(process.start),
                    "observed_ticks": utc_ticks(stamp + timedelta(seconds=1)), "sockets": [outgoing, reverse]}
        match = diagnostics.backend_self_connections
        self.assertEqual(match([obs], journey, snapshot), {1})
        summary = diagnostics.network_summary([obs], {}, {}, backend_pairs={1})
        self.assertEqual(summary["observations"], [{
            "observation": 1, "socket_status": "matched-same-process-pair",
            "request_category": "backend-internal-loopback",
        }])
        for hidden in ("private-guid", "51200", "62000", "127.0.0.1", "702"):
            self.assertNotIn(hidden, json.dumps(summary))
        for incomplete in (
            None,
            {**snapshot, "pid": 703},
            {**snapshot, "birth_ticks": utc_ticks(stamp)},
            {**snapshot, "observed_ticks": utc_ticks(stamp - timedelta(milliseconds=1))},
            {**snapshot, "observed_ticks": utc_ticks(process.end + timedelta(milliseconds=1))},
            {**snapshot, "sockets": [outgoing]},
            {**snapshot, "sockets": [outgoing, reverse, reverse]},
            {**snapshot, "sockets": [outgoing, reverse, {**outgoing, "local_address": "127.0.0.2"}]},
        ):
            self.assertEqual(match([obs], journey, incomplete), set())
        self.assertEqual(match([obs, obs], journey, snapshot), set())
        self.assertEqual(match([{**obs, "process_guid": "reused-pid"}], journey, snapshot), set())
        wakeup = diagnostics.backend_wakeup_connections
        witness = {key: snapshot[key] for key in ("pid", "observed_ticks", "sockets")}
        self.assertEqual(wakeup([obs], journey, snapshot, witness), {1})
        for invalid in (
            {**witness, "pid": process.pid + 1},
            {**witness, "observed_ticks": snapshot["observed_ticks"] + 1},
            {**witness, "observed_ticks": utc_ticks(stamp - timedelta(milliseconds=1))},
            {**witness, "sockets": [{**outgoing, "local_address": "127.0.0.2"}, reverse]},
        ):
            self.assertEqual(wakeup([obs], journey, snapshot, invalid), set())
        result = diagnostics.network_summary([obs], {}, {}, backend_pairs={1}, backend_wakeup_pairs={1})
        self.assertEqual(result["observations"][0]["request_category"], "backend-event-loop-wakeup")
        self.assertNotIn("62000", json.dumps(result))
        process.end = None
        self.assertEqual(match([obs], journey, snapshot), set())

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

    def test_writer_breakdown_distinguishes_tools_and_redacts_unknown_images(self):
        paths = diagnostics.OutsidePaths([("runner-temp", r"C:\private\temp")])
        for image in ("node.exe", "esbuild.exe", "powershell.exe", "pwsh.exe", "private-helper.exe", None):
            paths.record("driver", "write", (r"c:\private\temp\owner-file",), image)

        writers = {row["writer"]: row["count"] for row in paths.writer_summary()}
        self.assertEqual(writers, {"node": 1, "esbuild": 1, "powershell": 2,
                                   "other-executable": 1, "unavailable": 1})
        self.assertEqual(sum(writers.values()), paths.summary()[0]["count"])
        self.assertNotIn("private", json.dumps(paths.writer_summary()))

    def test_webview_storage_reports_fixed_families_and_preserves_ordinary_counts(self):
        local = r"c:\private\owner\appdata\local"
        paths = diagnostics.OutsidePaths([
            ("user-temp", local + r"\temp"),
            ("runner-temp", r"d:\private\runner"),
            ("user-local", local),
        ])
        cache = local + r"\d3dscache\private-file.bin"
        custom = local + r"\d3dscache-other\private-file.tmp"
        def record_webview(operation, path):
            paths.record("webview", operation, (path,), "msedgewebview2.exe")

        for _ in range(4):
            record_webview("create", local + r"\temp\generated.tmp")
            record_webview("create", cache)
            record_webview("overwrite", cache)
            record_webview("write", custom)
        paths.record("backend", "create", (local + r"\temp\backend.tmp",), "python.exe")
        result = paths.webview_storage_summary()
        self.assertEqual(result["ambient_temp_creates"], 4)
        rows = result["user_local_targets"]
        self.assertEqual([(r["operation"], r["destination_family"], r["file_type"],
                           r["distinct_targets"], r["target_events"]) for r in rows], [
            ("create", "direct3d-cache", "other-extension", 1, 4),
            ("overwrite", "direct3d-cache", "other-extension", 1, 4),
            ("write", "other-user-local", "temporary", 1, 4),
        ])
        self.assertTrue(all(r["writer"] == "webview2" for r in rows))
        self.assertEqual(sum(r["count"] for r in paths.summary() if r["path_categories"] == ["user-local"]), 12)
        self.assertNotIn("private", json.dumps(result))
        self.assertEqual(diagnostics.OutsidePaths([]).webview_storage_summary(),
                         {"ambient_temp_creates": 0, "user_local_targets": []})
        paths.record("webview-network", "create", (r"d:\private\runner\new.tmp",), "msedgewebview2.exe")
        self.assertEqual(paths.webview_storage_summary()["ambient_temp_creates"], 5)

    def test_backend_target_summary_identifies_repeated_targets_without_name_disclosure(self):
        paths = diagnostics.OutsidePaths([
            ("backend-stdout-log", r"C:\owner\capture\backend.log"),
            ("capture-workspace", r"C:\owner\capture"),
        ])
        log = r"c:\owner\capture\backend.log"
        first = r"d:\private\first.custom"
        second = r"d:\private\second.custom"
        for path in (log, log, first, first, second):
            paths.record("backend", "write", (path,), "python.exe")
        paths.record("driver", "write", (log,), "node.exe")

        rows = paths.backend_target_summary()
        self.assertEqual(rows, [
            {"operation": "write", "path_category": "backend-stdout-log", "file_type": "log",
             "distinct_targets": 1, "target_events": 2, "most_events_for_one_target": 2},
            {"operation": "write", "path_category": "other-path", "file_type": "other-extension",
             "distinct_targets": 2, "target_events": 3, "most_events_for_one_target": 2},
        ])
        for private_value in ("owner", "private", ".custom", "backend.log"):
            self.assertNotIn(private_value, json.dumps(rows))

    def test_exact_launch_socket_and_explicit_request_chain_without_sensitive_values(self):
        events = [
            event("URL_REQUEST_START_JOB", 115, REQUEST, {
                "url": "https://private.test/token?owner=private",
                "initiator": "http://127.0.0.1:5173",
            }, "PHASE_BEGIN"),
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
            {"observation": 1, "socket_status": "matched-socket", "request_category": "https-request",
             "request_host_category": "other-host", "initiator_category": "qa-frontend-origin"},
        ]})
        for hidden in ("private", "192.0.2", "51200", "token"):
            self.assertNotIn(hidden, json.dumps(report))
        self.assertEqual(log.match_evidence(observation(local=51201))[0], "no-socket-match")
        self.assertEqual(log.match_evidence(observation(stamp=4100))[0], "no-socket-match")
        self.assertEqual(log.match_evidence(observation(remote="192.0.2.10"))[0], "no-socket-match")
        self.assertEqual(log.match_evidence(observation(port=80))[0], "no-socket-match")
        blocked = diagnostics.network_summary([obs, {**obs, "role": "backend"}], {},
            {"first": "first.json"}, reader=lambda path: ("parsed", log))
        self.assertEqual([x["socket_status"] for x in blocked["observations"]],
                         ["launch-unverified", "outside-webview"])

    def test_failed_connect_and_conflicting_candidates_stay_unattributed(self):
        log = diagnostics.NetLog(payload(tcp(net_error=-2)))
        self.assertEqual(log.match_evidence(observation()), ("no-socket-match", "unattributed", {}))
        log = diagnostics.NetLog(payload(tcp(source_address="10.0.0.9:51200")))
        self.assertEqual(log.match_evidence(observation()), ("no-socket-match", "unattributed", {}))
        log = diagnostics.NetLog(payload(tcp() + tcp(source=(1, 11))))
        self.assertEqual(log.match_evidence(observation()), ("ambiguous-socket", "unattributed", {}))
        retry = [
            event("TCP_CONNECT_ATTEMPT", 121, SOCKET, {"address": "192.0.2.9:443"}, "PHASE_BEGIN"),
            event("TCP_CONNECT_ATTEMPT", 124, SOCKET, {
                "local_address": "10.0.0.9:51200", "remote_address": "192.0.2.9:443",
            }, "PHASE_END"),
        ]
        log = diagnostics.NetLog(payload(tcp() + retry))
        self.assertEqual(log.match_evidence(observation()), ("matched-socket", "unattributed", {}))

    def test_udp_dns_requires_local_address_and_link(self):
        events = [
            event("UDP_CONNECT", 120, SOCKET, {"address": "192.0.2.9:53"}, "PHASE_BEGIN"),
            event("UDP_LOCAL_ADDRESS", 121, SOCKET, {"address": "10.0.0.9:51200"}),
            event("UDP_CONNECT", 122, SOCKET, phase="PHASE_END"),
        ]
        obs = observation(protocol="udp", port=53)
        self.assertEqual(diagnostics.NetLog(payload(events)).match_evidence(obs),
                         ("matched-socket", "unattributed", {}))
        dns = link("DNS_TRANSACTION_ATTEMPT", 123, JOB, SOCKET)
        self.assertEqual(diagnostics.NetLog(payload(events + [dns])).match_evidence(obs),
                         ("matched-socket", "dns-transaction", {"dns_host_category": "unavailable"}))
        self.assertEqual(diagnostics.NetLog(payload(events[::2] + [dns])).match_evidence(obs),
                         ("no-socket-match", "unattributed", {}))
        name = event("DNS_TRANSACTION", 100, JOB, {"hostname": "wpad"}, "PHASE_BEGIN")
        query = event("DNS_TRANSACTION_QUERY", 101, JOB, {"qname": "wpad.private.test."}, "PHASE_BEGIN")
        later = event("DNS_TRANSACTION_QUERY", 124, JOB, {"qname": "later.private.test"}, "PHASE_BEGIN")
        stale = event("DNS_TRANSACTION_QUERY", -15000, JOB, {"qname": "old.private.test"}, "PHASE_BEGIN")
        unrelated = event("DNS_TRANSACTION_QUERY", 101, REQUEST, {"qname": "ipc.localhost"}, "PHASE_BEGIN")
        named = events + [dns, name, query, later, stale, unrelated]
        self.assertEqual(diagnostics.NetLog(payload(named)).match_evidence(obs),
                         ("matched-socket", "dns-transaction", {"dns_host_category": "wpad-host"}))
        other = event("DNS_TRANSACTION_QUERY", 103, JOB, {"qname": "other.private.test"}, "PHASE_BEGIN")
        self.assertEqual(diagnostics.NetLog(payload(named + [other])).match_evidence(obs),
                         ("matched-socket", "dns-transaction", {"dns_host_category": "ambiguous-host"}))
        reverse = link("DNS_TRANSACTION_ATTEMPT", 123, SOCKET, JOB)
        self.assertEqual(diagnostics.NetLog(payload(events + [reverse, query])).match_evidence(obs),
                         ("matched-socket", "unattributed", {}))

    def test_origin_categories_require_exact_documented_hosts_and_qa_origins(self):
        cases = {
            "http://ipc.localhost/command": "tauri-ipc-host",
            "https://TAURI.LOCALHOST./page": "tauri-app-host",
            "http://127.0.0.1:8000/api/projects": "qa-api-origin",
            "http://127.0.0.2:8000/api/projects": "loopback-host",
            "https://edge.microsoft.com/private": "documented-edge-service-host",
            "https://edge.microsoft.com.private.test/": "other-host",
            "http://fonts.gstatic.com/private": "google-fonts-host",
            "http://ipc.localhost@private.test/": "unavailable",
            "http://127.0.0.1:99999/": "unavailable",
            "null": "unavailable",
        }
        for value, category in cases.items():
            with self.subTest(value=value):
                self.assertEqual(diagnostics.origin_category(value), category)

    def test_request_redirect_or_shared_socket_does_not_invent_purpose(self):
        events = tcp() + [link("SOCKET_POOL_BOUND_TO_SOCKET", 126, JOB, SOCKET),
                          link("HTTP_STREAM_JOB_BOUND_TO_REQUEST", 127, JOB, REQUEST)]
        for stamp in (115, 116):
            events.append(event("URL_REQUEST_START_JOB", stamp, REQUEST, {"url": f"https://private.test/{stamp}"},
                                "PHASE_BEGIN"))
        self.assertEqual(diagnostics.NetLog(payload(events)).match_evidence(observation()),
                         ("matched-socket", "ambiguous-request", {}))

    def test_ipc_command_requires_the_qa_origin_and_an_exact_linked_request(self):
        events = tcp(local_address="127.0.0.1:51200", remote_address="127.0.0.1:80") + [
            link("SOCKET_POOL_BOUND_TO_SOCKET", 126, JOB, SOCKET),
            link("HTTP_STREAM_JOB_BOUND_TO_REQUEST", 127, JOB, REQUEST),
        ]
        obs = observation(remote="127.0.0.1", port=80)
        origin = "http://127.0.0.1:5173"
        url = "http://ipc.localhost/plugin%3Aevent%7Clisten"

        def request(url=url, method="POST", initiator=origin, stamp=115):
            return event("URL_REQUEST_START_JOB", stamp, REQUEST,
                         {"url": url, "method": method, "initiator": initiator}, "PHASE_BEGIN")

        def match(*requests):
            return diagnostics.NetLog(payload(events + list(requests))).match_evidence(obs)

        self.assertEqual(match(request())[2], {
            "request_host_category": "tauri-ipc-host", "initiator_category": "qa-frontend-origin",
            "ipc_command": "plugin:event|listen", "ipc_method": "POST",
        })
        self.assertEqual(match(request(method="OPTIONS"))[2]["ipc_method"], "OPTIONS")
        self.assertEqual(match(request(), request(method="OPTIONS"))[:2],
                         ("matched-socket", "ambiguous-request"))
        self.assertEqual(match(request(), request(stamp=116))[:2],
                         ("matched-socket", "ambiguous-request"))
        for invalid in (
            request(method="GET"), request(method=None),
            request(initiator=origin + "/unexpected"),
            request(url="http://ipc.localhost/confirm_native_project_switch?owner-private"),
            request(url="http://ipc.localhost/owner-private"),
        ):
            with self.subTest(invalid=invalid):
                status, purpose, details = match(invalid)
                self.assertEqual((status, purpose), ("matched-socket", "http-request"))
                self.assertNotIn("ipc_command", details)
                self.assertNotIn("owner-private", json.dumps(details))
        self.assertEqual(match(request(url="http://ipc.localhost/confirm_native_project_switch"))[2]["ipc_command"],
                         "confirm_native_project_switch")

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
