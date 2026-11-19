"""Check the N12 firewall policy and preflight decisions without changing host rules."""
from ipaddress import ip_address
import os
from pathlib import Path, PureWindowsPath
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from qa.p4_research import n12_app_journey as journey
from qa.p4_research import n12_egress as egress


class EgressPreflightTests(unittest.TestCase):
    def setUp(self):
        self.program = Path.cwd() / "python.exe"
        self.external = ("192.0.2.10", 443)
        self.rule = {"enabled": "True", "direction": "Outbound", "action": "Block", "profile": "Any",
                     "protocol": "Any", "program": str(self.program), "remote_addresses": egress.REMOTE_RANGES}

    def test_rule_excludes_loopback_and_includes_non_loopback_boundaries(self):
        scope = egress.intervals(egress.REMOTE_RANGES)
        for value, blocked in {
            "0.0.0.0": False, "0.0.0.1": True, "126.255.255.255": True,
            "127.0.0.0": False, "127.255.255.255": False, "128.0.0.0": True,
            "255.255.255.255": True, "::": False, "::1": False, "::2": True,
            "::ffff:126.255.255.255": True, "::ffff:127.0.0.0": False,
            "::ffff:127.255.255.255": False, "::ffff:128.0.0.0": True,
            "2001:db8::1": True, "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff": True,
        }.items():
            address = ip_address(value)
            with self.subTest(address=value):
                self.assertEqual(any(low.version == address.version and low <= address <= high
                                     for low, high in scope), blocked)

    def test_preflight_proves_reachability_and_loopback_before_crediting_denial(self):
        denied = PermissionError("generated outbound denial")
        denied.winerror = 10013
        with patch.object(egress, "firewall", side_effect=[self.rule, None]) as firewall, \
                patch.object(egress, "connect", side_effect=[None, None, denied, None]) as connect:
            egress.probe(self.program, self.external)
        destinations = [call.args[0] for call in connect.call_args_list]
        self.assertEqual(destinations[0], self.external)
        self.assertEqual(destinations[1][0], "127.0.0.1")
        self.assertEqual(destinations[2:], [self.external, self.external])
        add, remove = firewall.call_args_list
        self.assertEqual(add.args, ("add", remove.args[1]))
        self.assertEqual(remove.args[0], "remove")
        self.assertEqual(add.kwargs["program"], str(self.program))

    def test_success_or_timeout_under_the_rule_cannot_pass(self):
        for result in (None, TimeoutError("generated timeout")):
            with self.subTest(result=result), patch.object(egress, "firewall", side_effect=[self.rule, None]) as rule, \
                    patch.object(egress, "connect", side_effect=[None, None, result]):
                with self.assertRaises(egress.EvidenceValidationError):
                    egress.probe(self.program, self.external)
                self.assertEqual(rule.call_args.args[0], "remove")

    def test_unreachable_baseline_leaves_firewall_untouched(self):
        with patch.object(egress, "firewall") as firewall, patch.object(egress, "connect", side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                egress.probe(self.program, self.external)
        firewall.assert_not_called()

    def test_partial_setup_or_wrong_active_scope_removes_only_its_own_rule(self):
        for invalid_rule in (egress.EvidenceValidationError("setup failed"), {**self.rule, "program": "other.exe"}):
            with self.subTest(rule=invalid_rule), \
                    patch.object(egress, "firewall", side_effect=[invalid_rule, None]) as firewall:
                with self.assertRaises(egress.EvidenceValidationError):
                    with egress.outbound_block(self.program):
                        self.fail("A failed or mismatched rule reached the probe")
                add, remove = firewall.call_args_list
                self.assertEqual(remove.args, ("remove", add.args[1]))

    def test_journey_resolves_three_distinct_executables_including_exact_runtime(self):
        with TemporaryDirectory() as scratch:
            root = Path(scratch)
            app, backend, runtime = (root / name for name in ("pilotodin.exe", "python.exe", "msedgewebview2.exe"))
            for path in (app, backend):
                path.touch()
            with self.assertRaises(FileNotFoundError):
                egress.journey_programs(app, backend, root)
            runtime.touch()
            self.assertEqual(egress.journey_programs(app, backend, root),
                             {"app": app.resolve(), "backend": backend.resolve(), "webview": runtime.resolve()})
            with self.assertRaises(egress.EvidenceValidationError):
                egress.journey_programs(app, app, root)
            with self.assertRaises(egress.EvidenceValidationError):
                egress.journey_programs(app, backend, Path("relative-runtime"))

    def test_journey_cleans_up_every_rule_after_capture_or_partial_setup_failure(self):
        programs = {role: self.program.with_name(name) for role, name in (
            ("app", "pilotodin.exe"), ("backend", "python.exe"), ("webview", "msedgewebview2.exe"),
        )}
        for fail_at in (None, "backend", "capture"):
            verified_rules = []

            def firewall(action, name, **fields):
                if action == "remove":
                    verified_rules.remove(name)
                    return None
                verified_rules.append(name)
                if fail_at == "backend" and fields["program"] == str(programs["backend"]):
                    raise egress.EvidenceValidationError("generated setup failure")
                return {**self.rule, "program": fields["program"]}

            def capture():
                with egress.journey_blocks(programs):
                    self.assertNotEqual(fail_at, "backend")
                    self.assertEqual(len(verified_rules), 3)
                    if fail_at == "capture":
                        raise egress.EvidenceValidationError("generated capture failure")

            with self.subTest(fail_at=fail_at), patch.object(egress, "firewall", side_effect=firewall) as rule:
                if fail_at is None:
                    capture()
                else:
                    with self.assertRaises(egress.EvidenceValidationError):
                        capture()
                installed = 2 if fail_at == "backend" else 3
                adds, removes = rule.call_args_list[:installed], rule.call_args_list[installed:]
                self.assertEqual([c.kwargs["program"] for c in adds], list(map(str, programs.values()))[:installed])
                self.assertEqual([c.args for c in removes], [("remove", c.args[1]) for c in reversed(adds)])
                self.assertFalse(verified_rules)

    def test_journey_blocks_evidence_for_an_omitted_or_different_runtime_image(self):
        programs = {"app": PureWindowsPath(r"C:\Stage\pilotodin.exe"),
                    "backend": PureWindowsPath(r"C:\Python\python.exe"),
                    "webview": PureWindowsPath(r"C:\Runtime\1\msedgewebview2.exe")}
        roles = {"first": "app", "relaunch": "app", "backend": "backend", "browser": "webview",
                 "network": "webview-network"}
        processes = {guid: SimpleNamespace(image=str(programs[role.removesuffix("-network")]).lower())
                     for guid, role in roles.items()}
        observed = SimpleNamespace(roles=roles, processes=processes)
        self.assertTrue(egress.journey_images_match(programs, observed))
        observed.processes["network"].image = r"c:\runtime\2\msedgewebview2.exe"
        self.assertFalse(egress.journey_images_match(programs, observed))
        del observed.roles["network"]
        self.assertFalse(egress.journey_images_match(programs, observed))

    def test_journey_entry_requires_consent_and_verified_cleanup(self):
        executable = "b" * 64
        source = "a" * 40
        args = ["n12_app_journey", "--source", source, "--expected-exe-sha256", executable,
                "--webview-runtime-directory", str(self.program.parent)]
        report = {"network": "PASS_SCOPED", "filesystem": "PASS_SCOPED",
                  "webview_credit_comparison": {"status": "completed"}}
        staged = self.program.parent / "staged"
        for consent, cleanup, expected in (("", None, 2), (journey.CAPTURE_CONSENT, None, 0),
                                            (journey.CAPTURE_CONSENT, RuntimeError, 2)):
            with self.subTest(consent=bool(consent), cleanup=cleanup), \
                    patch.object(sys, "argv", args), \
                    patch.dict(os.environ, {"PILOTODIN_N12_APP_JOURNEY_CONSENT": consent}, clear=True), \
                    patch.object(journey.build, "stage_root", return_value=staged), \
                    patch.object(journey.build, "verify"), patch.object(journey, "listening", return_value=False), \
                    patch.object(journey.shutil, "which", return_value="node.exe"), \
                    patch.object(journey, "sysmon_tail", return_value=1), \
                    patch.object(journey.trace, "local_disposable_path", return_value=staged), \
                    patch.object(egress, "journey_programs", return_value={"app": self.program}) as resolve, \
                    patch.object(egress, "firewall", side_effect=[self.rule, cleanup() if cleanup else None]), \
                    patch.object(journey, "capture", return_value=report) as capture, \
                    patch("builtins.print") as output:
                self.assertEqual(journey.main(), expected)
                if not consent:
                    resolve.assert_not_called()
                    capture.assert_not_called()
                else:
                    capture.assert_called_once_with(staged, staged, source, executable, "node.exe", {"app": self.program})
                self.assertEqual(any('"network": "PASS_SCOPED"' in str(c.args[0])
                                     for c in output.call_args_list), expected == 0)


if __name__ == "__main__":
    unittest.main()
