"""Generated fixtures only. No model, process, network, or native execution."""
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
from desktop import verify_inference_assets as assets
from qa.p4_research import dla_stage1_contract as d
from tools.build_input_preflight import Blocked


def archive(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, payload in entries:
            z.writestr(name, payload)
    return stream.getvalue()


def inspect(raw):
    return d._inspect_snapshot(raw, len(raw), hashlib.sha256(raw).hexdigest())


class Stage1(unittest.TestCase):
    def test_archive_observations(self):
        raw = archive([("llama-server.exe", b"fixture"), ("ggml.dll", b"dll")])
        self.assertEqual(inspect(raw), {
            "llama-server.exe": {"bytes": 7, "sha256": hashlib.sha256(b"fixture").hexdigest()},
            "ggml.dll": {"bytes": 3, "sha256": hashlib.sha256(b"dll").hexdigest()}})
        with self.assertRaises(Blocked):
            d.inspect_pinned_runtime_snapshot(raw)

    def test_archive_refusals(self):
        for entries in ([("../escape.dll", b"x")],
                        [("a.dll", b"x"), ("A.dll", b"y")],
                        [("CON.dll", b"x")]):
            with self.subTest(entries=entries), self.assertRaises(Blocked):
                inspect(archive(entries))
        raw = archive([("a.dll", b"x")])
        with self.assertRaises(Blocked):
            d._inspect_snapshot(raw, len(raw), "0" * 64)

    def test_original_exact_inventory_route(self):
        from tools import c5_archive_preflight as z
        raw = archive([("a.dll", b"one"), ("b.dll", b"two")])
        rows = {
            "a.dll": {"bytes": 3, "sha256": hashlib.sha256(b"one").hexdigest()},
            "b.dll": {"bytes": 3, "sha256": hashlib.sha256(b"two").hexdigest()}}
        expected = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                    "members": rows}
        with tempfile.TemporaryDirectory(prefix="dla-generated-") as directory:
            path = Path(directory) / "generated.zip"
            path.write_bytes(raw)
            self.assertEqual(z.verified_candidate_snapshot(path, expected), raw)
            wrong = {**expected, "members": {"a.dll": rows["a.dll"]}}
            with self.assertRaises(Blocked):
                z.verify_candidate_archive(path, wrong)
            wrong = {**expected, "members": {**rows, "b.dll": {
                "bytes": 3, "sha256": "0" * 64}}}
            with self.assertRaises(Blocked):
                z.verify_candidate_archive(path, wrong)
            self.assertEqual(path.read_bytes(), raw)

    def test_granite_and_production_remain_disarmed(self):
        row = {"bytes": 1, "sha256": "a" * 64}
        expected = {"model": {"bytes": 1, "sha256": d.GRANITE_SHA}, "server": row,
                    "dlls": {"ggml.dll": row}, "notices": {n: row for n in d.NOTICE_NAMES}}
        with self.assertRaisesRegex(Blocked, "DLA_GRANITE_POINTER_UNCONFIRMED"):
            d.granite_preflight(expected)
        with self.assertRaisesRegex(Blocked, "C5_INFERENCE_PROVENANCE_BLOCKED"):
            assets.verify(Path("never-read"))

    def test_five_cases_exact_and_bad_results(self):
        cases = d.five_cases()
        self.assertEqual(tuple(x[0] for x in cases), d.CASE_NAMES)
        self.assertEqual(cases[-1][-1], "Synthetic context for the batch-size check.\n" * 100)
        responses = {name: {"finish_reason": "stop", "content": json.dumps(expected)}
                     for name, _, _, expected, _ in cases}
        self.assertTrue(all(d.score_five(responses).values()))
        responses["unknown_cause"]["content"] = '{"missing_rows":7,"cause":"invented"}'
        responses["no_training_claim"]["content"] = '{"training_started":0,"validation_score":null}'
        responses["long_context_overview"]["finish_reason"] = "length"
        scores = d.score_five(responses)
        self.assertEqual(sum(scores.values()), 2)
        del responses["dataset_overview"]
        with self.assertRaises(Blocked):
            d.score_five(responses)

    def test_strict_planner(self):
        plans = {
            "filtered_median": {"operation": "median", "measure": "premium",
                                "filter_column": "outcome", "filter_value": "Yes"},
            "grouped_missingness": {"operation": "grouped_missingness",
                                    "measure": "premium", "group_by": "outcome"},
            "labelled_rate": {"operation": "rate", "measure": "outcome",
                              "value": "Yes", "denominator": "labelled"},
            "all_row_rate": {"operation": "rate", "measure": "outcome",
                             "value": "Yes", "denominator": "all_rows"},
        }
        responses = {k: {"finish_reason": "stop", "content": json.dumps(v)}
                     for k, v in plans.items()}
        self.assertTrue(all(d.score_plans(responses).values()))
        plans["filtered_median"]["operation"] = "execute_sql"
        plans["labelled_rate"]["denominator"] = "all_rows"
        for k in ("filtered_median", "labelled_rate"):
            responses[k]["content"] = json.dumps(plans[k])
        self.assertEqual(sum(d.score_plans(responses).values()), 2)

    def test_admission_and_settlement(self):
        self.assertTrue(d.admission(d.FLOOR, d.GRANITE_ALIAS, True))
        self.assertFalse(d.admission(d.FLOOR - 1, d.GRANITE_ALIAS, True))
        self.assertFalse(d.admission(d.FLOOR, "foreign", True))
        self.assertFalse(d.admission(d.FLOOR, d.GRANITE_ALIAS, 1))
        witness = dict(generation="fixture", startup_joined=True, leader_terminated=True,
                       receiver_closed=True, child_dropped=True, event_fault=False,
                       active_processes=0, group_observed_ns=10,
                       listener_identity_verified=True, listener_absent=True,
                       listener_observed_ns=11)
        self.assertTrue(d.settled(witness, "fixture", 12))
        for key, value in (("generation", "foreign"), ("startup_joined", False),
                           ("leader_terminated", False), ("receiver_closed", False),
                           ("child_dropped", False), ("event_fault", True),
                           ("active_processes", 1), ("active_processes", False),
                           ("listener_identity_verified", False), ("listener_absent", False),
                           ("listener_observed_ns", 12), ("listener_observed_ns", 9)):
            with self.subTest(key=key, value=value):
                self.assertFalse(d.settled({**witness, key: value}, "fixture", 12))
        receipt = d.redacted_synthetic_result(dict.fromkeys(d.CASE_NAMES, True),
                       dict.fromkeys(d.PLAN_NAMES, True), witness, "fixture", 12)
        self.assertFalse(receipt["candidate_qualified"])
        self.assertFalse(receipt["execution_authorised"])


if __name__ == "__main__":
    unittest.main()
