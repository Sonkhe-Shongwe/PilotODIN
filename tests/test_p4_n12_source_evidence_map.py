"""Source-only checks for the Stage 1 reference-first traceability worksheet.

Tests enforce source/function/predicate/test identity and provenance of
documented partial native evidence. Nothing launches the desktop app.
"""
import ast
import copy
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "docs/P4_N12_STAGE1_SOURCE_EVIDENCE_MAP_2026-11-21.json"
STATES = frozenset({"REAL_PARTIAL", "SYNTHETIC_ONLY", "DISPUTED"})


def source_at_symbol(path, symbol):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    hits = [
        ast.get_source_segment(source, node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == symbol
    ]
    if len(hits) != 1:
        raise ValueError("source-evidence-symbol-missing-or-ambiguous")
    return hits[0]


def validate_map(data, root=ROOT):
    if (type(data) is not dict
            or data.get("schema") != "pilotodin-p4-n12-source-evidence-map-v1"
            or data.get("source_only") is not True
            or data.get("native_approval_granted") is not False
            or data.get("stage1_native_verdict") != "BLOCKED"
            or data.get("full_golden_stage1_reference") is not False
            or data.get("original_webview_child_handles_observed") != 0
            or data.get("observed_webview_role_counts") != {
                "webview": 6, "webview_network": 1,
            }
            or data.get("historical_sysmon_etw_exit_offset_ticks") != {
                "launcher": 32932, "app": 77625,
            }
            or data.get("last_tested_code_sha")
            != "0511aca1e192ff4aa0950ac1255dcbd1b887b8f2"
            or data.get("last_source_ci_run") != 44903523887
            or data.get("last_approved_native_stage1_run") != 44893498723):
        raise ValueError("source-evidence-provenance-or-native-state-invalid")
    rows = data.get("items")
    if (type(rows) is not list or len(rows) != 11
            or [r.get("id") for r in rows if type(r) is dict]
            != [f"S{i:02d}" for i in range(1, 12)]):
        raise ValueError("source-evidence-invariants-incomplete")
    for row in rows:
        if (type(row) is not dict
                or set(row) != {
                    "id", "claim", "status", "source", "symbol", "predicate",
                    "test", "real", "positive", "negative", "gap",
                }
                or row["status"] not in STATES
                or any(type(row[k]) is not str or not row[k].strip()
                       for k in row)):
            raise ValueError("source-evidence-row-invalid")
        source_path = root / row["source"]
        if source_path.suffix != ".py" or not source_path.is_file():
            raise ValueError("source-evidence-source-file-missing")
        fn = source_at_symbol(source_path, row["symbol"])
        if row["predicate"] not in fn:
            raise ValueError("source-evidence-predicate-not-in-function")
        parts = row["test"].split("::")
        if len(parts) != 2 or not parts[0].startswith("tests/"):
            raise ValueError("source-evidence-test-reference-invalid")
        test_path = root / parts[0]
        if not test_path.is_file():
            raise ValueError("source-evidence-test-file-missing")
        if not any(
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == parts[1]
            for n in ast.walk(ast.parse(test_path.read_text(encoding="utf-8")))
        ):
            raise ValueError("source-evidence-test-symbol-not-found")
    return True


class GoldenSourceEvidenceMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(MAP_PATH.read_text(encoding="utf-8"))

    def test_each_of_11_golden_invariants_links_existing_source_and_test(self):
        self.assertTrue(validate_map(self.data))
        self.assertEqual({x["id"] for x in self.data["items"]},
                         {f"S{i:02d}" for i in range(1, 12)})

    def test_no_fixture_could_be_misrepresented_as_complete_native_green(self):
        d = self.data
        self.assertFalse(d["full_golden_stage1_reference"])
        self.assertFalse(d["native_approval_granted"])
        self.assertEqual(d["stage1_native_verdict"], "BLOCKED")
        self.assertEqual(d["original_webview_child_handles_observed"], 0)
        self.assertEqual(d["historical_sysmon_etw_exit_offset_ticks"]["launcher"], 32932)
        self.assertEqual(d["historical_sysmon_etw_exit_offset_ticks"]["app"], 77625)
        self.assertEqual(d["observed_webview_role_counts"]["webview"], 6)
        self.assertEqual(d["observed_webview_role_counts"]["webview_network"], 1)
        self.assertEqual(
            [x["id"] for x in d["items"] if x["status"] == "DISPUTED"],
            ["S10"],
        )

    def test_clock_equality_is_explicitly_disputed_not_relaxed(self):
        row = next(x for x in self.data["items"] if x["id"] == "S10")
        self.assertEqual(row["predicate"], "etw-exit-exactly-matches-sysmon")
        code = source_at_symbol(ROOT / row["source"], row["symbol"])
        self.assertIn('stop.exit == trace.utc_ticks(process.end)', code)

    def test_child_birth_before_sampler_is_visible_as_a_contract_question(self):
        from qa.p4_research import n12_no_cdp_child_handles as child
        code = source_at_symbol(Path(child.__file__), "private_child_handle_diagnostic")
        self.assertIn('evidence.sampling_started_ticks <= witness["birth"]', code)
        # This is intentionally a source assumption, not a Windows guarantee:
        # never pretend a child born just after app launch was unobserved.
        self.assertFalse(self.data["full_golden_stage1_reference"])

    def test_tampered_mapping_fails_without_changing_any_acceptance(self):
        cases = [
            ("source", "qa/p4_research/fabricated.py"),
            ("symbol", "imaginary_success_predicate"),
            ("predicate", "accept-everything"),
            ("test", "tests/test_p4_n12_app_lifetime.py::test_not_real"),
            ("status", "NATIVE_PASS"),
        ]
        for key, value in cases:
            with self.subTest(case=key):
                record = copy.deepcopy(self.data)
                record["items"][0][key] = value
                with self.assertRaises(ValueError):
                    validate_map(record)
        record = copy.deepcopy(self.data)
        record["full_golden_stage1_reference"] = True
        with self.assertRaises(ValueError):
            validate_map(record)

    def test_real_child_observer_remains_default_off(self):
        workflow = (ROOT / ".github/workflows/p4-n12-app-lifetime.yml").read_text(encoding="utf-8")
        self.assertIn("if: $" + "{{ false }}", workflow)
        self.assertNotIn("PILOTODIN_N12_CHILD_HANDLE_CONSENT", workflow)


if __name__ == "__main__":
    unittest.main()
