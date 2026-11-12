"""P4-57 synthetic-only local validator regression checks. No GitHub/network/ML."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "qa" / "p4_shadow" / "validate_shadow_log.py"
spec = importlib.util.spec_from_file_location("p4_shadow_validator", TOOL)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def pre_record():
    return {
        "change_id": "synthetic-001", "recorded_at_utc": "2026-11-12T08:00:00Z",
        "branch": "feature/live-dev-workspace-20261023", "base_sha": "a" * 40,
        "patch_sha256": "b" * 64, "changed_paths": ["frontend/src/App.tsx"],
        "extra_preflight_recommended": True, "proposed_check": "targeted frontend typecheck",
        "rationale": "Synthetic frontend edit has type safety exposure",
    }


def post_record():
    return {
        "change_id": "synthetic-001", "push_at_utc": "2026-11-12T09:00:00Z",
        "workflow_run_id": 123456789, "workflow": "P1 Isolated Frontend Verification",
        "run_started_at_utc": "2026-11-12T09:01:00Z", "run_conclusion": "failure",
        "failure_attribution": "unattributed", "attribution_evidence_url": None,
        "human_debug_minutes": None, "actual_preflight_minutes": None,
    }


class ShadowLogTests(unittest.TestCase):
    def test_valid_unattributed_failure_preserves_missing_measured_time(self):
        before, after = pre_record(), post_record()
        original = (deepcopy(before), deepcopy(after))
        self.assertEqual(validator.validate([before], [after]), {
            "pre_changes": 1, "post_runs": 1, "completed_runs": 1,
            "failed_runs": 1, "censored_or_unresolved": 0,
        })
        self.assertEqual((before, after), original)

    def test_predecision_rejects_outcome_leakage(self):
        before = pre_record()
        before["run_conclusion"] = "failure"
        with self.assertRaisesRegex(validator.ValidationError, "unexpected"):
            validator.validate([before], [])

    def test_post_before_predecision_is_rejected(self):
        before, after = pre_record(), post_record()
        after["push_at_utc"] = before["recorded_at_utc"]
        with self.assertRaisesRegex(validator.ValidationError, "precede push"):
            validator.validate([before], [after])

    def test_duplicate_decision_and_run_id_fail_closed(self):
        before, after = pre_record(), post_record()
        with self.assertRaises(validator.ValidationError):
            validator.validate([before, deepcopy(before)], [])
        with self.assertRaises(validator.ValidationError):
            validator.validate([before], [after, deepcopy(after)])

    def test_missing_predecision_is_not_retroactively_admitted(self):
        with self.assertRaisesRegex(validator.ValidationError, "missing pre-push"):
            validator.validate([], [post_record()])

    def test_cancellation_cannot_be_labeled_actionable_defect(self):
        before, after = pre_record(), post_record()
        after["run_conclusion"] = "cancelled"
        after["failure_attribution"] = "new_actionable"
        with self.assertRaisesRegex(validator.ValidationError, "non-failure"):
            validator.validate([before], [after])
        after["failure_attribution"] = "not_applicable"
        result = validator.validate([before], [after])
        self.assertEqual(result["censored_or_unresolved"], 1)
        self.assertEqual(result["failed_runs"], 0)

    def test_attributed_failure_needs_repository_evidence(self):
        before, after = pre_record(), post_record()
        after["failure_attribution"] = "new_actionable"
        with self.assertRaises(validator.ValidationError):
            validator.validate([before], [after])
        after["attribution_evidence_url"] = "https://github.com/Other/Repo/issues/1"
        with self.assertRaisesRegex(validator.ValidationError, "this repository"):
            validator.validate([before], [after])
        after["attribution_evidence_url"] = "https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/123456789"
        self.assertEqual(validator.validate([before], [after])["failed_runs"], 1)

    def test_queued_not_falsely_completed_and_unmeasured_is_not_zero(self):
        before, after = pre_record(), post_record()
        after.update(run_conclusion="queued", failure_attribution="not_applicable",
                     run_started_at_utc=None)
        self.assertEqual(validator.validate([before], [after])["completed_runs"], 0)
        after["human_debug_minutes"] = "0"
        with self.assertRaisesRegex(validator.ValidationError, "measured minutes"):
            validator.validate([before], [after])
        after["human_debug_minutes"] = 0
        self.assertEqual(validator.validate([before], [after])["censored_or_unresolved"], 1)

    def test_invalid_timestamp_and_unsafe_path_blocked(self):
        before = pre_record()
        before["recorded_at_utc"] = "2026-11-12T08:00:00"
        with self.assertRaisesRegex(validator.ValidationError, "explicit UTC"):
            validator.validate([before], [])
        before = pre_record()
        before["changed_paths"] = ["../outside.txt"]
        with self.assertRaisesRegex(validator.ValidationError, "repository-relative"):
            validator.validate([before], [])

    def test_malformed_json_field_types_are_rejected_as_validation_errors(self):
        before, after = pre_record(), post_record()
        after["change_id"] = ["synthetic-001"]
        with self.assertRaises(validator.ValidationError):
            validator.validate([before], [after])
        after = post_record()
        after["run_conclusion"] = {"unexpected": True}
        with self.assertRaises(validator.ValidationError):
            validator.validate([before], [after])

    def test_completed_run_requires_real_start_timestamp(self):
        before, after = pre_record(), post_record()
        after["run_started_at_utc"] = None
        with self.assertRaisesRegex(validator.ValidationError, "requires run start"):
            validator.validate([before], [after])

    def test_cli_is_read_only_and_reports_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            pre = Path(directory) / "pre.jsonl"
            post = Path(directory) / "post.jsonl"
            pre.write_text(json.dumps(pre_record()) + "\n", encoding="utf-8")
            post.write_text(json.dumps(post_record()) + "\n", encoding="utf-8")
            originals = pre.read_bytes(), post.read_bytes()
            result = subprocess.run([sys.executable, str(TOOL), str(pre), str(post)],
                                    text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("not externally attested", result.stdout)
            self.assertEqual((pre.read_bytes(), post.read_bytes()), originals)


if __name__ == "__main__":
    unittest.main()
