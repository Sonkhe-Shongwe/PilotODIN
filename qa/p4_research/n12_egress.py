"""Validate program-scoped Windows egress containment on a disposable runner."""
import argparse
from collections import Counter
from contextlib import ExitStack, contextmanager
from ipaddress import ip_address
import json
import ntpath
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from uuid import uuid4

from qa.p4_native.n12_trace import EvidenceValidationError, local_disposable_path, require
from qa.p4_research import n12_app_build as build


CONSENT = "I_APPROVE_ONE_N12_EGRESS_PREFLIGHT"
PEER = ("github.com", 443)
# Keep IPv4, IPv6 and IPv4-mapped loopback outside the block. Unspecified
# addresses are local socket sentinels and do not describe external peers.
REMOTE_RANGES = (
    "0.0.0.1-126.255.255.255", "128.0.0.0-255.255.255.255",
    "::2-::ffff:7eff:ffff", "::ffff:8000:0-ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff",
)
FIREWALL_COMMAND = r"""
$ErrorActionPreference = 'Stop'
$request = [Console]::In.ReadToEnd() | ConvertFrom-Json
if ($request.operation -ceq 'remove') {
    $rule = Get-NetFirewallRule -PolicyStore PersistentStore | Where-Object Name -CEQ $request.name
    if ($rule) { $rule | Remove-NetFirewallRule }
    foreach ($store in @('PersistentStore', 'ActiveStore')) {
        if (Get-NetFirewallRule -PolicyStore $store | Where-Object Name -CEQ $request.name) {
            throw 'N12 outbound rule cleanup could not be verified.'
        }
    }
    return
}
if ($request.operation -cne 'add') { throw 'Unknown N12 firewall operation.' }
$null = New-NetFirewallRule -PolicyStore PersistentStore -Name $request.name -DisplayName $request.name `
    -Program $request.program -Direction Outbound -Action Block -Profile Any -Protocol Any `
    -RemoteAddress $request.remote_addresses
$rule = Get-NetFirewallRule -PolicyStore ActiveStore -Name $request.name
$application = Get-NetFirewallApplicationFilter -AssociatedNetFirewallRule $rule
$addresses = Get-NetFirewallAddressFilter -AssociatedNetFirewallRule $rule
$protocol = Get-NetFirewallPortFilter -AssociatedNetFirewallRule $rule
@{
    enabled = [string]$rule.Enabled
    direction = [string]$rule.Direction
    action = [string]$rule.Action
    profile = [string]$rule.Profile
    program = [string]$application.Program
    protocol = [string]$protocol.Protocol
    remote_addresses = @($addresses.RemoteAddress)
} | ConvertTo-Json -Compress
"""


def intervals(ranges):
    return {tuple(ip_address(endpoint) for endpoint in item.split("-")) for item in ranges}


def firewall(operation, name, **fields):
    system = Path(os.environ["SystemRoot"]) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    result = subprocess.run([str(system), "-NoProfile", "-NonInteractive", "-Command", FIREWALL_COMMAND],
                            input=json.dumps({"operation": operation, "name": name, **fields}),
                            capture_output=True, text=True, timeout=60)
    require(result.returncode == 0, f"Windows Firewall {operation} failed.")
    return json.loads(result.stdout) if operation == "add" else None


def verify_rule(rule, program):
    require(rule["enabled"] == "True" and rule["direction"] == "Outbound" and rule["action"] == "Block"
            and rule["profile"] == "Any" and rule["protocol"] == "Any"
            and ntpath.normcase(rule["program"]) == ntpath.normcase(str(program))
            and intervals(rule["remote_addresses"]) == intervals(REMOTE_RANGES),
            "The active rule does not match the requested egress boundary.")


@contextmanager
def outbound_block(program):
    require(program.is_absolute() and program.suffix.casefold() == ".exe", "An exact executable path is required.")
    name = f"PilotODIN-N12-Egress-{uuid4().hex}"
    try:
        verify_rule(firewall("add", name, program=str(program), remote_addresses=REMOTE_RANGES), program)
        yield
    finally:
        firewall("remove", name)


def journey_programs(app, backend, webview_runtime_directory):
    require(webview_runtime_directory.is_absolute(), "An absolute WebView2 runtime directory is required.")
    runtime = (webview_runtime_directory / "msedgewebview2.exe").resolve(strict=True)
    require(runtime.name.casefold() == "msedgewebview2.exe" and runtime.parent ==
            webview_runtime_directory.resolve(strict=True), "The WebView2 executable must belong to the selected runtime.")
    programs = {"app": app.resolve(strict=True), "backend": backend.resolve(strict=True), "webview": runtime}
    require(all(path.is_file() and path.suffix.casefold() == ".exe" for path in programs.values()) and
            len({ntpath.normcase(str(path)) for path in programs.values()}) == len(programs),
            "The journey requires three distinct executable paths.")
    return programs


@contextmanager
def journey_blocks(programs):
    with ExitStack() as stack:
        for program in programs.values():
            stack.enter_context(outbound_block(program))
        yield


def journey_images_match(programs, observed):
    expected = {role: ntpath.normcase(str(path)) for role, path in programs.items()}
    expected["webview-network"] = expected["webview"]
    verified = Counter()
    for guid, role in observed.roles.items():
        if role in expected:
            if observed.processes[guid].image != expected[role]:
                return False
            verified[role] += 1
    # The existing audit also requires both WebView roles in each launch.
    return verified["app"] == 2 and all(verified[role] for role in expected)


def non_loopback_peer():
    results = socket.getaddrinfo(*PEER, family=socket.AF_INET, type=socket.SOCK_STREAM)
    peer = results[0][4]
    require(ip_address(peer[0]).is_global, "The control peer did not resolve to a public IPv4 address.")
    return peer


def connect(peer):
    with socket.create_connection(peer, timeout=5):
        pass


def probe(program, peer):
    # The listener and caller are the same executable under test. Prove
    # reachability before installing the rule and after removing it.
    connect(peer)
    with outbound_block(program), socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        connect(listener.getsockname())
        try:
            connect(peer)
        except OSError as error:
            require(getattr(error, "winerror", None) == 10013,
                    "The external control did not produce a verified access denial.")
        else:
            raise EvidenceValidationError("The external control connection succeeded under the rule.")
    connect(peer)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    try:
        env = os.environ
        run = env.get("GITHUB_RUN_ID", "")
        require(re.fullmatch(r"[0-9]+", run) and env.get("GITHUB_RUN_ATTEMPT") == "1"
                and env.get("GITHUB_EVENT_NAME") == "push" and env.get("GITHUB_REF_NAME") == build.BRANCH
                and re.fullmatch(r"[0-9a-f]{40}", args.source) and env.get("PILOTODIN_N12_EGRESS_SOURCE") == args.source
                and env.get("PILOTODIN_N12_EGRESS_CONSENT") == CONSENT,
                "N12 egress preflight requires fresh source-pinned approval on hosted Windows.")
        local_disposable_path(Path(env["RUNNER_TEMP"]) / f"pilotodin-n12-egress-{run}", runner_temp_only=True)
        require(build.git("rev-parse", "HEAD") == args.source
                and not build.git("status", "--porcelain", "--untracked-files=no"),
                "The checkout differs from the approved source.")
        probe(Path(sys.executable).resolve(strict=True), non_loopback_peer())
    except (EvidenceValidationError, OSError, KeyError, ValueError, subprocess.SubprocessError) as error:
        reason = str(error) if isinstance(error, EvidenceValidationError) else type(error).__name__
        print(f"N12 egress preflight BLOCKED: {reason}", file=sys.stderr)
        return 2
    print(json.dumps({"source_sha": args.source, "scope": "windows-firewall-python-tcp-fixture", "status": "PASS"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
