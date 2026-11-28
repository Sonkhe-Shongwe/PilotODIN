"""Source-only Windows entry-point safety checks; no provisioning/launch."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GeneratedSysmonSourceGuards(unittest.TestCase):
    def test_future_native_job_is_disarmed_and_marker_not_present(self):
        workflow = (ROOT / ".github/workflows/p4-n12-generated-sysmon-bookends.yml").read_text(encoding="utf-8")
        self.assertIn("if: ${{ false }}", workflow)
        self.assertNotIn("workflow_dispatch:", workflow)
        self.assertNotIn("actions/upload-artifact", workflow)
        self.assertNotIn("cargo build", workflow)
        self.assertNotIn("n12_app_build", workflow)
        self.assertNotIn("-NoCdpFileIO", workflow)
        self.assertNotIn("--fileio", workflow)
        self.assertNotIn("I_APPROVE_ONE_N12_NO_CDP_FILEIO", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("$changed.Count -ne 2", workflow)
        self.assertIn("$added.Count -ne 1", workflow)
        self.assertIn("git checkout --detach $source", workflow)
        self.assertIn("-WithEtw -GeneratedBookendsOnly", workflow)
        self.assertIn("N12_GENERATED_BOOKENDS_OWNER_APPROVAL_G2_8_FRESH_ONE_USE.txt", workflow)
        self.assertNotIn("qa/p4_research/N12_GENERATED_BOOKENDS_OWNER_APPROVAL_G2_6_FRESH_ONE_USE.txt", workflow)
        self.assertNotIn("qa/p4_research/N12_GENERATED_BOOKENDS_OWNER_APPROVAL_G2_5_FRESH_ONE_USE.txt", workflow)
        self.assertNotIn("qa/p4_research/N12_GENERATED_BOOKENDS_OWNER_APPROVAL.txt", workflow)
        self.assertFalse((ROOT / "qa/p4_research/N12_GENERATED_BOOKENDS_OWNER_APPROVAL_G2_8_FRESH_ONE_USE.txt").exists())
        # G2.6 approval was used exactly once, and must remain consumed.
        self.assertEqual((ROOT / "qa/p4_research/N12_GENERATED_BOOKENDS_OWNER_APPROVAL_G2_6_FRESH_ONE_USE.txt").read_text(encoding="utf-8").splitlines(), [
            "reviewed_source=598bb9fe80f7caca8cd20eec1ab898b9be027fc6",
            "scope=n12-generated-sysmon-bookends-one-use",
        ])
        # Second approved G2.5 activation is now consumed and immutable.
        self.assertEqual((ROOT / "qa/p4_research/N12_GENERATED_BOOKENDS_OWNER_APPROVAL_G2_5_FRESH_ONE_USE.txt").read_text(encoding="utf-8").splitlines(), [
            "reviewed_source=aea47e35e257b0f227059a39127c2daa458e3c85",
            "scope=n12-generated-sysmon-bookends-one-use",
        ])
        # Exactly one authorised run has consumed this marker. The marker
        # must remain a source-pinned historical record, NOT be deleted or
        # treated as permission to re-arm the disabled workflow.
        consumed = ROOT / "qa/p4_research/N12_GENERATED_BOOKENDS_OWNER_APPROVAL.txt"
        self.assertEqual(consumed.read_text(encoding="utf-8").splitlines(), [
            "reviewed_source=0862c8dbfe7cd0305bd6fe18a850ca2fc96788b6",
            "scope=n12-generated-sysmon-bookends-one-use",
        ])
        self.assertIn("if: ${{ false }}", workflow)
        self.assertIn("never rerun", workflow.casefold())
        self.assertIn("$changed.Count -ne 2", workflow)
        self.assertIn("$added.Count -ne 1", workflow)


    def test_powershell_source_does_not_inherit_ordinary_collector_permission(self):
        source = (ROOT / "qa/p4_native/Invoke_P4_N12_Live_Calibration.ps1").read_text(encoding="utf-8")
        self.assertIn("[switch]$GeneratedBookendsOnly", source)
        self.assertIn("if ($GeneratedBookendsOnly -and (", source)
        self.assertIn("I_APPROVE_ONE_N12_GENERATED_SYSMON_BOOKENDS", source)
        self.assertIn("PILOTODIN_N12_GENERATED_BOOKENDS_SOURCE", source)
        self.assertIn("(git rev-parse HEAD)", source)
        self.assertIn("-not $GeneratedBookendsOnly", source)
        self.assertIn("python -B -m qa.p4_research.n12_generated_sysmon_bookends", source)
        self.assertLess(source.index("if ($GeneratedBookendsOnly -and ("), source.index("Get-MicrosoftCollector"))
        self.assertLess(source.index("python -B -m qa.p4_research.n12_generated_sysmon_bookends"),
                        source.index("    if ($AppLifetime) {"))
        self.assertIn("if ($NoCdpFileIO -and (", source)
        self.assertIn('if: ${{ false }}',
                      (ROOT / '.github/workflows/p4-n12-no-cdp-fileio.yml').read_text(encoding='utf-8'))

    def test_same_strict_sysmon_verifier_keeps_outside_birth_blocking(self):
        source = (ROOT / "qa/p4_research/n12_app_journey.py").read_text(encoding="utf-8")
        self.assertIn('"parent-birth-before-window"', source)
        candidate = (ROOT / 'qa/p4_research/n12_generated_sysmon_bookends.py').read_text(encoding='utf-8')
        self.assertIn('verify=journey.verify_fixture_sysmon', candidate)
        self.assertIn('trace.sysmon_events(', source)
        self.assertIn('"child-loopback-tcp-or-udp-missing"', source)

    def test_generated_sysmon_reader_only_has_hosted_one_use_source_guard(self):
        helper = (ROOT / "qa/p4_research/Invoke_N12_Journey_Evidence.ps1").read_text(encoding="utf-8")
        gate = helper.split("$generatedBookendRead = ", 1)[1].split("$backgroundThreadRead =", 1)[0]
        for part in ("$Operation -ceq 'sysmon-tail'", "GITHUB_EVENT_NAME -ceq 'push'",
                     "GITHUB_RUN_ATTEMPT -ceq '1'", "GITHUB_RUN_ID -cmatch '^[0-9]+$'",
                     "PILOTODIN_N12_GENERATED_BOOKENDS_CONSENT -ceq 'I_APPROVE_ONE_N12_GENERATED_SYSMON_BOOKENDS'",
                     "(git rev-parse HEAD) -ceq $env:PILOTODIN_N12_GENERATED_BOOKENDS_SOURCE"):
            with self.subTest(part=part):
                self.assertIn(part, gate)
        self.assertNotIn("'etw-export'", gate)
        self.assertNotIn("'fileio-rundown'", gate)
        self.assertIn("-not $timingExport -and -not $generatedBookendRead -and", helper)

    def test_sysmon_tail_delegates_to_the_guarded_powershell_reader(self):
        from unittest.mock import patch
        from qa.p4_research import n12_app_journey as journey
        with patch.object(journey, "powershell", return_value=b"1234\n") as child:
            self.assertEqual(journey.sysmon_tail(), 1234)
        child.assert_called_once()
        self.assertEqual(child.call_args.args[0].name, "Invoke_N12_Journey_Evidence.ps1")
        self.assertEqual(child.call_args.args[1], "sysmon-tail")


if __name__ == '__main__':
    unittest.main()
