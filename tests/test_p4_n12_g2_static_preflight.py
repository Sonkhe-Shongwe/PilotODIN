"""Source-only G2 preflight, never a native capture or permission."""
from pathlib import Path
import re
import unittest
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def event3_rule_status(source):
    """Static analysis of generated XML, NOT an actual Sysmon observation."""
    m = re.search(r"\$definition\s*=\s*@'\s*([\s\S]*?)\s*'@", source)
    if m is None:
        return "DEFINITION_MISSING"
    try:
        root = ET.fromstring(m.group(1))
    except ET.ParseError:
        return "XML_INVALID"
    rules = root.findall("./EventFiltering/NetworkConnect")
    if len(rules) != 1 or rules[0].attrib != {"onmatch": "exclude"}:
        return "EVENT3_FILTER_NOT_UNFILTERED"
    tail = source[m.end():]
    use = re.search(r"\$definition\s*\|\s*Set-Content\s+-LiteralPath\s+\$config", tail)
    if use is None:
        return "CONFIG_OUTPUT_MISSING"
    executable = [l.strip() for l in tail[:use.start()].splitlines()
                  if l.strip() and not l.lstrip().startswith("#")]
    if executable:
        return "CONFIG_INTERVENING_MUTATION"
    return "SOURCE_REVIEWABLE_ONLY"


def native_disarmed(source):
    return bool(re.search(r"(?m)^jobs:\s*\n\s+no-cdp-fileio:\s*\n\s+if:\s*\$\{\{\s*false\s*\}\}", source))


class G2SourceOnlySafetyPreflight(unittest.TestCase):
    def setUp(self):
        self.ps = read("qa/p4_native/Invoke_P4_N12_Live_Calibration.ps1")
        self.workflow = read(".github/workflows/p4-n12-no-cdp-fileio.yml")

    def test_generated_event3_xml_source_is_unfiltered(self):
        self.assertEqual(event3_rule_status(self.ps), "SOURCE_REVIEWABLE_ONLY")

    def test_old_empty_include_regression_fails_closed(self):
        bad = self.ps.replace('<NetworkConnect onmatch="exclude" />',
                              '<NetworkConnect onmatch="include" />', 1)
        self.assertNotEqual(event3_rule_status(bad), "SOURCE_REVIEWABLE_ONLY")

    def test_intervening_xml_replacement_fails_closed(self):
        anchor = "$definition | Set-Content -LiteralPath $config"
        self.assertIn(anchor, self.ps)
        bad = self.ps.replace(anchor,
                              '$definition = $definition.Replace("exclude", "include")\n' + anchor, 1)
        self.assertEqual(event3_rule_status(bad), "CONFIG_INTERVENING_MUTATION")

    def test_missing_event3_rule_fails_closed(self):
        bad = self.ps.replace('<NetworkConnect onmatch="exclude" />', "", 1)
        self.assertNotEqual(event3_rule_status(bad), "SOURCE_REVIEWABLE_ONLY")

    def test_capture_wrapper_requires_source_pinned_one_use_consent(self):
        required = ("if ($NoCdpFileIO -and (",
                    "-not $NoCdp -or -not $AppLifetime -or -not $WithEtw",
                    "PILOTODIN_N12_NO_CDP_FILEIO_CONSENT",
                    "PILOTODIN_N12_CHILD_HANDLE_CONSENT",
                    "PILOTODIN_N12_APPROVED_SOURCE",
                    "if ($NoCdpFileIO) { $lifetimeArgs += '--fileio' }")
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, self.ps)
        self.assertLess(self.ps.index("n12_app_build verify --source"),
                        self.ps.index("Start-CollectorCommand $sysmon"))

    def test_native_workflow_is_still_disabled_and_first_run_pinned(self):
        self.assertTrue(native_disarmed(self.workflow))
        for token in ("RUNNER_OS -cne 'Windows'",
                      "RUNNER_ENVIRONMENT -cne 'github-hosted'",
                      "GITHUB_RUN_ATTEMPT -cne '1'",
                      "$changed.Count -ne 2", "$added.Count -ne 1",
                      "git checkout --detach $source",
                      "-NoCdp -NoCdpFileIO"):
            with self.subTest(token=token):
                self.assertIn(token, self.workflow)
        self.assertNotIn("workflow_dispatch:", self.workflow)

    def test_unauthorised_activation_is_detectable(self):
        changed = self.workflow.replace("if: $" + "{{ false }}",
                                        "if: $" + "{{ true }}", 1)
        self.assertFalse(native_disarmed(changed))

    def test_original_one_use_marker_is_consumed(self):
        marker = read("qa/p4_research/N12_NO_CDP_FILEIO_OWNER_APPROVAL.txt")
        self.assertEqual(marker.splitlines(), [
            "reviewed_source=c6062b5c8c1e1d75e6dab1f91d515d21bcfdd089",
            "scope=n12-one-build-one-no-cdp-fileio-baseline",
        ])
        # The first marker remains a historical consumed record. A second
        # one-use native approval was consumed by run #45041259808, and the
        # workflow was safely disarmed immediately after activation.
        fresh = "qa/p4_research/N12_NO_CDP_FILEIO_OWNER_APPROVAL_20261122_FRESH_ONE_USE.txt"
        self.assertEqual(read(fresh).splitlines(), [
            "reviewed_source=166dfa39efa6a1629c35cc4c2c6c3fc740078c3c",
            "scope=n12-one-build-one-no-cdp-fileio-baseline",
        ])
        self.assertIn(fresh, self.workflow)
        self.assertTrue(native_disarmed(self.workflow))

    def test_privacy_limits_and_nonacceptance_remain_explicit(self):
        self.assertNotIn("upload-artifact", self.workflow)
        self.assertIn("No private path, PID, GUID or raw capture exported.", self.workflow)
        self.assertIn("no complete redacted diagnostic receipt (BLOCKED)", self.workflow)
        builder = read("qa/p4_research/n12_app_build.py")
        lifetime = read("qa/p4_research/n12_app_lifetime.py")
        reducer = read("qa/p4_research/n12_no_cdp_fileio_review.py")
        self.assertIn('bundle.get("active") is False', builder)
        self.assertIn("child_pipe.hosted_scope", lifetime)
        self.assertIn("journey.run_initial_calibration(", lifetime)
        self.assertIn('"native_N12_acceptance": "NOT_EVALUATED"', reducer)
        self.assertIn('"file_mutation_acceptance": "NOT_EVALUATED"', reducer)
        self.assertIn('"full_product_tree_mutation_containment": "NOT_DEMONSTRATED"', reducer)


if __name__ == "__main__":
    unittest.main()
