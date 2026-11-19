"""Check the N12 firewall policy and preflight decisions without changing host rules."""
from ipaddress import ip_address
from pathlib import Path
import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
