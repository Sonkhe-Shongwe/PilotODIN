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




# Redacted real-observation partial reference and synthetic counterexamples.
# This is appended to source-evidence mapping tests so routine P4 CI executes it.
PARTIAL_REFERENCE = (
    ROOT / "qa/p4_research/fixtures/n12_stage1_partial_reference_44893498723.json"
)


def inspect_partial_reference(data):
    """Validate the pinned historical derived reference, NEVER grant Stage 1 PASS."""
    if (type(data) is not dict
            or set(data) != {
                "schema", "evidence_type", "approved_native_run",
                "reviewed_source_sha", "one_use_activation_sha",
                "native_stage1_verdict", "full_golden_stage1_reference",
                "native_N12_acceptance", "file_event_coverage",
                "network_isolation", "observations", "children",
                "etw_counters", "protected_endpoint_comparison",
                "strict_exit_clock_equality", "interpretation",
            }
            or data.get("schema") != "pilotodin-p4-n12-stage1-partial-reference-v1"
            or data.get("evidence_type")
            != "REDACTED_DERIVATION_OF_APPROVED_NATIVE_OBSERVATION"
            or data.get("approved_native_run") != 44893498723
            or data.get("reviewed_source_sha")
            != "41eaa3b240d621491ed0aec3a7a8ae227d92a626"
            or data.get("one_use_activation_sha")
            != "d55a956fd4f691f91549fb574507325fad506505"
            or data.get("native_stage1_verdict") != "BLOCKED"
            or data.get("full_golden_stage1_reference") is not False
            or any(data.get(k) != "NOT_EVALUATED"
                   for k in ("native_N12_acceptance", "file_event_coverage",
                             "network_isolation"))
            or data.get("strict_exit_clock_equality") != "DISPUTED"
            or data.get("protected_endpoint_comparison") != "MATCH"
            or not isinstance(data.get("interpretation"), str)):
        raise ValueError("partial-reference-provenance-or-verdict-invalid")
    expected = {
        "launcher": (6393, 32932),
        "app": (8582, 77625),
    }
    if type(data.get("observations")) is not dict or set(data["observations"]) != set(expected):
        raise ValueError("partial-reference-original-process-incomplete")
    for name, (birth_delta, exit_delta) in expected.items():
        value = data["observations"][name]
        if (type(value) is not dict
                or set(value) != {
                    "original_handle_retained",
                    "handle_etw_birth_difference_ticks",
                    "handle_etw_exit_difference_ticks",
                    "etw_birth_minus_sysmon_birth_ticks",
                    "etw_exit_minus_sysmon_event5_ticks",
                    "sysmon_exit",
                }
                or value.get("original_handle_retained") is not True
                or value.get("handle_etw_birth_difference_ticks") != 0
                or value.get("handle_etw_exit_difference_ticks") != 0
                or value.get("etw_birth_minus_sysmon_birth_ticks") != birth_delta
                or value.get("etw_exit_minus_sysmon_event5_ticks") != exit_delta
                or value.get("sysmon_exit") != "UNDISPUTED"):
            raise ValueError("partial-reference-handle-or-clock-tampered")
    children = data.get("children")
    if (type(children) is not dict
            or set(children) != {
                "observed_role_counts", "original_handle_coverage",
                "exact_original_child_handle_data",
            }
            or children.get("observed_role_counts") != {
                "webview": 6, "webview-network": 1,
            }
            or children.get("original_handle_coverage") != [
                {"role": "webview", "observed": 6, "retained_original_handles": 0,
                 "evidence": "MISSING"},
                {"role": "webview-network", "observed": 1,
                 "retained_original_handles": 0, "evidence": "MISSING"},
            ]
            or children.get("exact_original_child_handle_data") != "NOT_COLLECTED"):
        raise ValueError("partial-reference-child-originals-fabricated")
    if data.get("etw_counters") != {
        "events_lost": 0, "log_buffers_lost": 0,
        "realtime_buffers_lost": 0, "buffers_written": 5,
    }:
        raise ValueError("partial-reference-etw-source-record-altered")
    return {"scope": "HISTORICAL_PARTIAL_REFERENCE_ONLY",
            "status": "PARTIAL_CORROBORATION_WITH_MISSING_CHILD_HANDLES",
            "native_N12_acceptance": "NOT_EVALUATED"}


class Stage1PartialReferenceBackwardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads(PARTIAL_REFERENCE.read_text(encoding="utf-8"))

    def test_real_app_launcher_properties_are_partial_not_a_native_green(self):
        result = inspect_partial_reference(self.reference)
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertEqual(self.reference["native_stage1_verdict"], "BLOCKED")
        self.assertEqual(
            sum(r["observed"] for r in
                self.reference["children"]["original_handle_coverage"]), 7)
        self.assertEqual(
            sum(r["retained_original_handles"] for r in
                self.reference["children"]["original_handle_coverage"]), 0)
        self.assertEqual(
            self.reference["observations"]["app"]["etw_exit_minus_sysmon_event5_ticks"],
            77625)
        self.assertEqual(
            self.reference["observations"]["launcher"]["etw_exit_minus_sysmon_event5_ticks"],
            32932)

    def test_no_forged_full_reference_or_clock_reinterpretation(self):
        mutations = [
            lambda d: d.__setitem__("full_golden_stage1_reference", True),
            lambda d: d.__setitem__("native_stage1_verdict", "PASS"),
            lambda d: d.__setitem__("native_N12_acceptance", "PASS"),
            lambda d: d["children"]["original_handle_coverage"][0].__setitem__(
                "retained_original_handles", 6),
            lambda d: d["observations"]["app"].__setitem__(
                "handle_etw_exit_difference_ticks", 1),
            lambda d: d["observations"]["launcher"].__setitem__(
                "etw_exit_minus_sysmon_event5_ticks", 0),
            lambda d: d["etw_counters"].__setitem__("events_lost", 1),
            lambda d: d.__setitem__("unknown_success", True),
        ]
        for change in mutations:
            with self.subTest(change=mutations.index(change)):
                candidate = copy.deepcopy(self.reference)
                change(candidate)
                with self.assertRaises(ValueError):
                    inspect_partial_reference(candidate)

    def test_early_born_retained_child_is_rejected_before_independent_join(self):
        # The sampled child has a retained original handle, verified full image,
        # valid parent, and birth BEFORE sampling started. It is still alive at
        # that first sample and has a later observed original-handle exit.
        # Strict native gate is NOT changed by documenting this contradiction.
        from qa.p4_research.n12_no_cdp_child_handles import (
            PrivateChildHandleEvidence, private_child_handle_diagnostic,
        )
        from tests.test_p4_n12_no_cdp_child_handles import ChildObserverTests
        from tests.test_p4_n12_exit_corroboration import ORIGIN, stamp

        case = ChildObserverTests()
        case.setUp()
        case.observer.sample_once(case.rows)
        witnesses = tuple(case.finish())
        self.assertEqual(len(witnesses), 2)
        self.assertLess(witnesses[0]["birth"], ORIGIN + 250_000)
        self.assertGreater(witnesses[0]["exit"], ORIGIN + 250_000)
        processes, roles, lifetimes = case.process_fixture()
        manifest = {
            "source_sha": "a" * 40,
            "executable_sha256": "b" * 64,
            "markers": {
                "launch": stamp(50_000).isoformat(),
                "ready": stamp(400_000).isoformat(),
                "close": stamp(700_000).isoformat(),
                "profile-exit": stamp(850_000).isoformat(),
            },
        }
        common = dict(
            manifest=manifest, processes=processes, roles=roles,
            app_guid="app", app_witness={"birth": ORIGIN + 100_000},
            lifetimes=lifetimes, source_issues=set(),
            capture_start=ORIGIN, capture_end=ORIGIN + 1_000_000,
        )

        def diagnose(sampling_start):
            evidence = PrivateChildHandleEvidence(
                source_sha="a" * 40,
                executable_sha256="b" * 64,
                root_birth_ticks=ORIGIN + 100_000,
                sampling_started_ticks=ORIGIN + sampling_start,
                sampling_finished_ticks=ORIGIN + 900_000,
                witnesses=witnesses,
                collector_receipt=case.observer.redacted_receipt(),
            )
            return private_child_handle_diagnostic(evidence=evidence, **common)

        late_sampling = diagnose(250_000)
        self.assertEqual(late_sampling["status"], "BLOCKED")
        self.assertIn("private-evidence-child-outside-sampling-or-profile",
                      late_sampling["failed_checks"])

        # Same independently matched child handles, clock, GUIDs, ancestry and
        # images with earlier observer start: the private shadow is reviewable.
        # This demonstrates the *extra* diagnostic inequality, NOT native PASS.
        early_sampling = diagnose(200_000)
        self.assertEqual(early_sampling["status"], "REVIEWABLE_ONLY")
        self.assertEqual(early_sampling["native_N12_acceptance"], "NOT_EVALUATED")

    def test_role_mix_requirement_is_an_unverified_spec_assumption(self):
        # Illustrates present predicate, does not certify all-webview role trees.
        from tests.test_p4_n12_no_cdp_child_handles import ChildObserverTests
        case = ChildObserverTests()
        case.setUp()
        case.observer.sample_once(case.rows)
        witnesses = case.finish()
        self.assertEqual(case.review(witnesses)["status"], "REVIEWABLE_ONLY")
        processes, roles, lifetimes = case.process_fixture()
        roles["child2"] = "webview"
        changed = case.review(witnesses, processes=processes,
                              roles=roles, lifetimes=lifetimes)
        self.assertEqual(changed["status"], "BLOCKED")
        self.assertIn("browser-role-coverage-missing", changed["failed_checks"])
        self.assertEqual(changed["native_N12_acceptance"], "NOT_EVALUATED")


if __name__ == "__main__":
    unittest.main()
