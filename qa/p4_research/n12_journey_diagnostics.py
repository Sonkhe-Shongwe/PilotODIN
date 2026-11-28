"""Redacted diagnostics for the approved disposable N12 Windows app journey."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from ipaddress import IPv6Address, ip_address
import json
import ntpath
from urllib.parse import quote, urlsplit

from qa.p4_native.n12_trace import inside, local_disposable_path, utc_ticks, utc_time, windows_path


CONNECT_EVENTS = {"TCP_CONNECT", "TCP_CONNECT_ATTEMPT", "UDP_CONNECT"}
DNS_ATTEMPT_EVENTS = {"DNS_TRANSACTION_ATTEMPT", "DNS_TRANSACTION_TCP_ATTEMPT"}
DNS_NAME_FIELDS = {"DNS_TRANSACTION": "hostname", "DNS_TRANSACTION_QUERY": "qname"}
LINK_EVENTS = {
    "SOCKET_POOL_BOUND_TO_SOCKET", "SOCKET_POOL_BOUND_TO_CONNECT_JOB", "CONNECT_JOB_SET_SOCKET",
    "HTTP_STREAM_JOB_BOUND_TO_REQUEST", "HTTP_STREAM_REQUEST_BOUND_TO_JOB",
    "TRANSPORT_CONNECT_JOB_CONNECT_ATTEMPT", "TCP_CONNECT_JOB_CONNECTOR_CONNECT_START",
} | DNS_ATTEMPT_EVENTS
CLOCK_TOLERANCE_MS = 1000
REQUEST_LOOKBACK_MS = 10_000
NETLOG_LIMIT = 64 * 1024 * 1024
# Tauri uses encodeURIComponent(command) in the Windows IPC URL. Publish
# only known commands exercised by the N12 journey from the Vite QA origin.
IPC_URL_COMMANDS = {f"http://ipc.localhost/{quote(command, safe='')}": command for command in (
    "plugin:event|listen", "plugin:event|unlisten", "plugin:window|close",
    "confirm_native_project_switch", "confirm_native_close", "resolve_native_close_request",
)}
WRITER_CATEGORIES = {
    "node.exe": "node",
    "esbuild.exe": "esbuild",
    "powershell.exe": "powershell",
    "pwsh.exe": "powershell",
    "python.exe": "python",
    "pythonw.exe": "python",
    "msedgewebview2.exe": "webview2",
}
FILE_TYPES = {
    ".db": "database", ".sqlite": "database", ".sqlite3": "database",
    ".csv": "data", ".parquet": "data", ".json": "metadata",
    ".log": "log", ".pyc": "python-bytecode", ".tmp": "temporary",
}
WEBVIEW_ROLES = {"webview", "webview-network"}
WEBVIEW_LOCAL_FOLDERS = (
    ("direct3d-cache", "D3DSCache"),
    ("edge-webview", r"Microsoft\EdgeWebView"),
    ("edge-update", r"Microsoft\EdgeUpdate"),
    ("edge", r"Microsoft\Edge"),
    ("windows-internet-cache", r"Microsoft\Windows\INetCache"),
    ("windows-web-cache", r"Microsoft\Windows\WebCache"),
    ("crash-dumps", "CrashDumps"),
)


class OutsidePaths:
    def __init__(self, roots):
        # The caller supplies fixed categories ordered from narrow to broad.
        self.roots = [(label, windows_path(str(path))) for label, path in roots]
        self.counts = Counter()
        self.writers = Counter()
        self.backend_targets = defaultdict(Counter)
        self.webview_targets = defaultdict(Counter)
        local = next((root for label, root in self.roots if label == "user-local"), None)
        self.webview_local_families = [
            (label, windows_path(ntpath.join(local, directory)))
            for label, directory in WEBVIEW_LOCAL_FOLDERS
        ] if local is not None else []

    def record(self, role, operation, paths, image=None):
        targets = {path: next((label for label, root in self.roots if inside(path, root)), "other-path")
                   for path in paths}
        labels = tuple(sorted(set(targets.values())))
        self.counts[role, operation, labels] += 1
        category = WRITER_CATEGORIES.get(image, "other-executable" if image else "unavailable")
        self.writers[role, operation, labels, category] += 1
        if role == "backend":
            for path, label in targets.items():
                extension = ntpath.splitext(path)[1]
                file_type = FILE_TYPES.get(extension, "other-extension" if extension else "no-extension")
                self.backend_targets[operation, label, file_type][path] += 1
        elif role in WEBVIEW_ROLES:
            for path, label in targets.items():
                if label != "user-local":
                    continue
                family = next((group for group, prefix in self.webview_local_families if inside(path, prefix)),
                              "other-user-local")
                extension = ntpath.splitext(path)[1]
                file_type = FILE_TYPES.get(extension, "other-extension" if extension else "no-extension")
                self.webview_targets[role, operation, category, family, file_type][path] += 1

    def summary(self):
        return [{"role": role, "operation": op, "path_categories": list(labels), "count": count}
                for (role, op, labels), count in sorted(self.counts.items())]

    def writer_summary(self):
        return [{"role": role, "operation": op, "path_categories": list(labels),
                 "writer": writer, "count": count}
                for (role, op, labels, writer), count in sorted(self.writers.items())]

    def backend_target_summary(self):
        return [{"operation": operation, "path_category": label, "file_type": file_type,
                 "distinct_targets": len(targets), "target_events": sum(targets.values()),
                 "most_events_for_one_target": max(targets.values())}
                for (operation, label, file_type), targets in sorted(self.backend_targets.items())]

    def webview_storage_summary(self):
        ambient_temp_creates = sum(
            count for (role, operation, labels), count in self.counts.items()
            if role in WEBVIEW_ROLES and operation == "create" and
            ("user-temp" in labels or "runner-temp" in labels)
        )
        return {"ambient_temp_creates": ambient_temp_creates, "user_local_targets": [
            {"role": role, "operation": operation, "writer": writer, "destination_family": family,
             "file_type": file_type, "distinct_targets": len(targets), "target_events": sum(targets.values())}
            for (role, operation, writer, family, file_type), targets in sorted(self.webview_targets.items())
        ]}


def address(value):
    parsed = ip_address(value)
    if isinstance(parsed, IPv6Address) and parsed.ipv4_mapped:
        return parsed.ipv4_mapped
    return parsed


def endpoint(value):
    if not isinstance(value, str):
        raise ValueError("missing address")
    host, separator, port = value.rpartition(":")
    if not separator or not port.isascii() or not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ValueError("invalid endpoint")
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    elif ":" in host:
        raise ValueError("IPv6 endpoint must be bracketed")
    return address(host), int(port)


@dataclass(frozen=True)
class SocketMatch:
    source: tuple[int, int]
    protocol: str
    local_port: int
    remote: tuple
    start: int
    end: int


def host_category(host):
    if not isinstance(host, str) or not host.strip():
        return "unavailable"
    host = host.casefold().removesuffix(".")
    if host == "ipc.localhost":
        return "tauri-ipc-host"
    if host == "tauri.localhost":
        return "tauri-app-host"
    if host in {"fonts.googleapis.com", "fonts.gstatic.com"}:
        return "google-fonts-host"
    if host in {"edge.microsoft.com", "config.edge.skype.com", "msedge.api.cdp.microsoft.com"}:
        return "documented-edge-service-host"
    if host == "wpad" or host.startswith("wpad."):
        return "wpad-host"
    if host == "localhost":
        return "loopback-host"
    try:
        if address(host).is_loopback:
            return "loopback-host"
    except ValueError:
        pass
    return "other-host"


def origin_category(url):
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return "unavailable"
        if parsed.username is not None or parsed.password is not None:
            return "unavailable"
        port = parsed.port
        if parsed.scheme == "http" and parsed.hostname == "127.0.0.1":
            if port == 5173:
                return "qa-frontend-origin"
            if port == 8000:
                return "qa-api-origin"
        return host_category(parsed.hostname)
    except ValueError:
        return "unavailable"


def source_key(source):
    key = source["type"], source["id"]
    if any(type(part) is not int or part <= 0 for part in key):
        raise ValueError("invalid NetLog source")
    return key


def event_codes(constants, field):
    pairs = constants[field]
    if not isinstance(pairs, dict) or any(type(code) is not int for code in pairs.values()):
        raise ValueError("invalid NetLog codes")
    reverse = {code: name for name, code in pairs.items()}
    if len(reverse) != len(pairs):
        raise ValueError("ambiguous NetLog codes")
    return reverse


def socket_match(kind, source, start, end, before, after, udp_locals):
    if end < start or "get_address_net_error" in after or any(
        after.get(field, 0) != 0 for field in ("net_error", "os_error")
    ):
        return None
    try:
        if kind == "UDP_CONNECT":
            remote = endpoint(before.get("address"))
            # Separate getsockname evidence is usable only for the same source
            # and time, with an unambiguous local endpoint.
            locals_found = {local for stamp, local in udp_locals[source]
                            if start <= stamp <= end + CLOCK_TOLERANCE_MS}
            if len(locals_found) != 1:
                return None
            _, port = locals_found.pop()
        else:
            local = after.get("local_address", after.get("source_address"))
            _, port = endpoint(local)
            if "remote_address" in after:
                remote = endpoint(after["remote_address"])
            elif kind == "TCP_CONNECT_ATTEMPT":
                remote = endpoint(before.get("address"))
            else:
                candidates = {endpoint(item) for item in before.get("address_list", [])}
                if len(candidates) != 1:
                    return None
                remote = candidates.pop()
    except (TypeError, ValueError):
        return None
    return SocketMatch(source, "udp" if kind == "UDP_CONNECT" else "tcp", port, remote, start, end)


class NetLog:
    def __init__(self, raw):
        constants = raw["constants"]
        kinds = event_codes(constants, "logEventTypes")
        phases = event_codes(constants, "logEventPhase")
        offset = int(constants["timeTickOffset"])
        if not {"PHASE_BEGIN", "PHASE_END"} <= set(phases.values()) or not CONNECT_EVENTS & set(kinds.values()):
            raise ValueError("missing NetLog event types")
        recorded = CONNECT_EVENTS | LINK_EVENTS | DNS_NAME_FIELDS.keys() | {
            "URL_REQUEST_START_JOB", "UDP_LOCAL_ADDRESS",
        }
        self.links = defaultdict(list)
        self.requests = defaultdict(list)
        self.dns_names = defaultdict(list)
        self.dns_attempts = defaultdict(list)
        self.sockets = defaultdict(list)
        pending, udp_locals, completed = {}, defaultdict(list), []
        if not isinstance(raw["events"], list) or not raw["events"]:
            raise ValueError("missing NetLog events")
        for event in raw["events"]:
            kind = kinds.get(event["type"])
            if kind not in recorded:
                continue
            source = source_key(event["source"])
            phase = phases.get(event["phase"])
            stamp = int(event["time"]) + offset
            params = event.get("params", {})
            if not isinstance(params, dict):
                raise ValueError("invalid NetLog parameters")
            key = source, kind
            if kind in CONNECT_EVENTS:
                if phase == "PHASE_BEGIN":
                    pending[key] = (stamp, params) if key not in pending else None
                elif phase == "PHASE_END":
                    begin = pending.pop(key, None)
                    if begin is not None:
                        began, first = begin
                        completed.append((kind, source, began, stamp, first, params))
            elif kind == "UDP_LOCAL_ADDRESS":
                try:
                    udp_locals[source].append((stamp, endpoint(params.get("address"))))
                except ValueError:
                    continue
            elif kind == "URL_REQUEST_START_JOB" and phase == "PHASE_BEGIN" and isinstance(params.get("url"), str):
                initiator, method = params.get("initiator"), params.get("method")
                self.requests[source].append((stamp, params["url"],
                    initiator if isinstance(initiator, str) else "", method if isinstance(method, str) else ""))
            elif kind in DNS_NAME_FIELDS and phase == "PHASE_BEGIN":
                field = DNS_NAME_FIELDS[kind]
                self.dns_names[source].append((stamp, field, params.get(field)))
            elif kind in LINK_EVENTS and "source_dependency" in params:
                linked = source_key(params["source_dependency"])
                self.links[source].append((linked, stamp))
                self.links[linked].append((source, stamp))
                if kind in DNS_ATTEMPT_EVENTS:
                    self.dns_attempts[linked].append((source, stamp))
        for event in completed:
            match = socket_match(*event, udp_locals)
            if match is not None:
                self.sockets[match.protocol, match.local_port, match.remote].append(match)

    def request_evidence(self, socket):
        lower = socket.start - REQUEST_LOOKBACK_MS
        upper = socket.end + CLOCK_TOLERANCE_MS
        dns_attempts = {(source, stamp) for source, stamp in self.dns_attempts[socket.source]
                        if lower <= stamp <= upper}
        seen, pending, requests = set(), [socket.source], []
        while pending and len(seen) < 64:
            source = pending.pop()
            if source in seen:
                continue
            seen.add(source)
            requests.extend((url, initiator, method) for stamp, url, initiator, method in self.requests[source]
                            if lower <= stamp <= upper)
            pending.extend(linked for linked, stamp in self.links[source] if lower <= stamp <= upper)
        if pending or len(requests) > 1 or len(dns_attempts) > 1 or (requests and dns_attempts):
            return "ambiguous-request", {}
        if dns_attempts:
            dns_source, attempted_at = next(iter(dns_attempts))
            # Query names take precedence over the original hostname, which can
            # differ after suffix expansion. Several names in scope are ambiguous.
            names = [(field, value) for stamp, field, value in self.dns_names[dns_source]
                     if lower <= stamp <= attempted_at]
            preferred = "qname" if any(field == "qname" for field, _ in names) else "hostname"
            selected = {value.casefold().removesuffix(".") for field, value in names
                        if field == preferred and isinstance(value, str) and value.strip()}
            category = "ambiguous-host" if len(selected) > 1 else host_category(next(iter(selected), None))
            return "dns-transaction", {"dns_host_category": category}
        if not requests:
            return "unattributed", {}
        (url, initiator, method), = requests
        try:
            scheme = urlsplit(url).scheme
            destination = origin_category(url)
            if destination != "unavailable":
                details = {"request_host_category": destination, "initiator_category": origin_category(initiator)}
                command = IPC_URL_COMMANDS.get(url)
                remote_ip, remote_port = socket.remote
                if (command is not None and method in {"POST", "OPTIONS"}
                        and initiator == "http://127.0.0.1:5173"
                        and socket.protocol == "tcp" and remote_ip.is_loopback and remote_port == 80):
                    details.update(ipc_command=command, ipc_method=method)
                return f"{scheme}-request", details
        except ValueError:
            pass
        return "unattributed", {}

    def match_evidence(self, observation):
        time = datetime.fromisoformat(observation["utc"])
        if time.utcoffset() is None or time.utcoffset().total_seconds() != 0:
            raise ValueError("expected a UTC observation")
        stamp = round(time.timestamp() * 1000)
        remote = address(observation["address"]), observation["port"]
        # A socket's TCP_CONNECT and TCP_CONNECT_ATTEMPT may describe the
        # same successful connect. Group only overlapping records for that source.
        key = observation["protocol"], observation["source_port"], remote
        matches = sorted((match for match in self.sockets.get(key, ())
                          if match.start - CLOCK_TOLERANCE_MS <= stamp <= match.end + CLOCK_TOLERANCE_MS),
                         key=lambda match: (match.source, match.start, match.end))
        group = []
        for match in matches:
            if group and (group[0].source != match.source or match.start > min(item.end for item in group)):
                return "ambiguous-socket", "unattributed", {}
            group.append(match)
        if not group:
            return "no-socket-match", "unattributed", {}
        interval = min(group, key=lambda match: match.end - match.start)
        category, details = self.request_evidence(interval)
        return "matched-socket", category, details


def read_netlog(path):
    try:
        approved = local_disposable_path(path, runner_temp_only=True)
        with approved.open("rb") as stream:
            payload = stream.read(NETLOG_LIMIT + 1)
        if len(payload) > NETLOG_LIMIT:
            return "size-limit", None
        return "parsed", NetLog(json.loads(payload))
    except FileNotFoundError:
        return "missing", None
    except (OSError, KeyError, TypeError, ValueError, OverflowError):
        return "unusable", None


def backend_self_connections(observations, journey, snapshot):
    """Correlate both ends of a live TCP pair to the declared backend lifetime."""
    if snapshot is None:
        return set()
    bindings = [process for root, process in journey.bindings if root["role"] == "backend"]
    if len(bindings) != 1:
        return set()
    process, = bindings
    if (process.pid != snapshot["pid"] or process.end is None
            or abs(utc_ticks(process.start) - snapshot["birth_ticks"]) > 100_000
            or not utc_ticks(process.start) <= snapshot["observed_ticks"] <= utc_ticks(process.end)):
        return set()
    rows = [(address(row["local_address"]), row["local_port"],
             address(row["remote_address"]), row["remote_port"]) for row in snapshot["sockets"]]
    counts = Counter(rows)
    matches = {}
    for ordinal, entry in enumerate(observations, 1):
        if (entry["role"] != "backend" or entry["protocol"] != "tcp"
                or entry["kind"] != "unexpected-loopback" or entry["process_guid"] != process.guid
                or not utc_ticks(process.start) <= utc_ticks(utc_time(entry["utc"])) <= snapshot["observed_ticks"]):
            continue
        remote = address(entry["address"])
        candidates = [row for row in counts if row[0].is_loopback and remote.is_loopback
                      and row[1:] == (entry["source_port"], remote, entry["port"])]
        if len(candidates) != 1:
            continue
        row, = candidates
        reverse = row[2:] + row[:2]
        if row != reverse and counts[row] == counts[reverse] == 1:
            matches[ordinal] = frozenset((row, reverse))
    uses = Counter(matches.values())
    return {ordinal for ordinal, pair in matches.items() if uses[pair] == 1}


def backend_wakeup_connections(observations, journey, snapshot, witness):
    if snapshot is None or witness is None:
        return set()
    try:
        observed = witness["observed_ticks"]
        if (type(witness["pid"]) is not int or witness["pid"] != snapshot["pid"]
                or type(observed) is not int or observed > snapshot["observed_ticks"]):
            return set()
        sockets = witness["sockets"]
        if not isinstance(sockets, list) or len(sockets) != 2:
            return set()
        def endpoint(row):
            return (address(row["local_address"]), row["local_port"],
                    address(row["remote_address"]), row["remote_port"])

        live_rows = Counter(endpoint(row) for row in snapshot["sockets"])
        if any(live_rows[endpoint(row)] != 1 for row in sockets):
            return set()
        return backend_self_connections(observations, journey, {
            **snapshot, "observed_ticks": observed, "sockets": sockets,
        })
    except (KeyError, TypeError, ValueError):
        return set()


def network_summary(observations, launches, paths, reader=read_netlog, *, backend_pairs=(), backend_wakeup_pairs=()):
    logs = {label: reader(path) for label, path in paths.items()}
    result = []
    for ordinal, observation in enumerate(observations, 1):
        launch = launches.get(observation["process_guid"]) if observation["role"] == "webview-network" else None
        state, purpose, details = "outside-webview", "unattributed", {}
        if observation["role"] == "webview-network":
            state, log = logs.get(launch, ("launch-unverified", None))
            if log is not None:
                try:
                    state, purpose, details = log.match_evidence(observation)
                except (OSError, KeyError, TypeError, ValueError, OverflowError):
                    state = "observation-unusable"
        if ordinal in backend_pairs:
            state, purpose = "matched-same-process-pair", "backend-internal-loopback"
            if ordinal in backend_wakeup_pairs:
                purpose = "backend-event-loop-wakeup"
        # The ordinal refers to the existing redacted list in the audit report.
        result.append({"observation": ordinal, "socket_status": state, "request_category": purpose, **details})
    return {"logs": {label: status for label, (status, _) in logs.items()}, "observations": result}
