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
        self.assertFalse((ROOT / "qa/p4_research/N12_GENERATED_BOOKENDS_OWNER_APPROVAL.txt").exists())

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
                        source.index("if ($AppLifetime) {"))
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


if __name__ == '__main__':
    unittest.main()
