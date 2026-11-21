"""Synthetic-only controls for a default-off hosted QA WebView child observer."""
from contextlib import contextmanager
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from qa.p4_native import n12_exit_corroboration as etw
from qa.p4_native import n12_trace as trace
from qa.p4_research.n12_no_cdp_child_handles import (
    ScopedQaChildHandleObserver, review_scoped_children, _hosted_scope,
)
from tests.test_p4_n12_exit_corroboration import event, stamp, ORIGIN


APP = r"c:\qa\isolated\pilotodin-desktop.exe"
WEB = r"c:\qa\webview\msedgewebview2.exe"
NATIVE_WEB = r"\Device\HarddiskVolume3\qa\webview\msedgewebview2.exe"
DEVICES = {r"\device\harddiskvolume3": "c:"}


class FakeHandles:
    def __init__(self):
        self.opened = []
        self.closed = []
        self.timing = {
            600: {"pid": 600, "birth": ORIGIN + 100_000, "exit": None},
            601: {"pid": 601, "birth": ORIGIN + 210_000, "exit": None},
            602: {"pid": 602, "birth": ORIGIN + 300_000, "exit": None},
        }
        self.image = {
            600: {"image_dos": APP, "image_native": r"\Device\HarddiskVolume3\qa\isolated\pilotodin-desktop.exe"},
            601: {"image_dos": WEB, "image_native": NATIVE_WEB},
            602: {"image_dos": WEB, "image_native": NATIVE_WEB},
        }

    @contextmanager
    def open_handle(self, pid):
        self.opened.append(pid)
        try:
            yield SimpleNamespace(pid=pid)
        finally:
            self.closed.append(pid)

    def times(self, handle, allow_running=False):
        record = self.timing[handle.pid]
        if not allow_running and record["exit"] is None:
            raise trace.EvidenceValidationError("fixture handle still running")
        return dict(record)

    def images(self, handle):
        return dict(self.image[handle.pid])


class ChildObserverTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeHandles()
        self.root = SimpleNamespace(pid=600)
        self.observer = ScopedQaChildHandleObserver(
            root_process=self.root, expected_app_image=APP,
            open_handle=self.backend.open_handle, process_times=self.backend.times,
            process_images=self.backend.images)
        self.rows = [
            (600, 50, "pilotodin-desktop.exe"),
            (601, 600, "msedgewebview2.exe"),
            (602, 601, "msedgewebview2.exe"),
            (888, 44, "other-process.exe"),
        ]

    def finish(self):
        self.backend.timing[601]["exit"] = ORIGIN + 640_000
        self.backend.timing[602]["exit"] = ORIGIN + 680_000
        return self.observer.finish()

    def test_scoped_capture_and_original_handles_only(self):
        self.observer.sample_once(self.rows)
        self.observer.sample_once(self.rows)
        witnesses = self.finish()
        self.assertEqual(set(self.backend.opened), {601, 602})
        self.assertEqual(set(self.backend.closed), {601, 602})
        self.assertEqual(len(witnesses), 2)
        self.assertEqual(self.observer.redacted_receipt()["status"], "SAMPLING_FINISHED_UNVERIFIED")
        self.assertEqual(self.observer.redacted_receipt()["retained_original_handle_count"], 2)
        for private in (APP, WEB, "601", '"pid"', "private"):
            self.assertNotIn(private, json.dumps(self.observer.redacted_receipt()))

    def test_missing_child_sample_remains_detectable_at_sysmon_join(self):
        self.observer.sample_once([self.rows[0], self.rows[1]])
        witnesses = self.finish()
        self.assertEqual(len(witnesses), 1)
        self.assertEqual(self.observer.redacted_receipt()["status"], "SAMPLING_FINISHED_UNVERIFIED")

    def test_aborted_observer_releases_handles_without_partial_witness(self):
        self.observer.sample_once(self.rows)
        self.assertEqual(set(self.backend.opened), {601, 602})
        self.assertEqual(self.backend.closed, [])
        self.observer.abort()
        self.observer.abort()  # idempotent exception unwind
        self.assertEqual(set(self.backend.closed), {601, 602})
        self.assertEqual(self.observer.redacted_receipt()["status"], "BLOCKED")
        self.assertEqual(self.observer.redacted_receipt()["retained_original_handle_count"], 0)
        self.assertIn("observer-interrupted", self.observer.redacted_receipt()["faults"])
        with self.assertRaisesRegex(trace.EvidenceValidationError, "already-finished"):
            self.observer.finish()

    def test_child_created_and_exited_between_samples_is_never_credited(self):
        # Child 602 exists in the independent Sysmon/ETW fixture but never
        # appeared in either snapshot. A clean sampler count is NOT coverage.
        self.observer.sample_once([self.rows[0], self.rows[1]])
        self.observer.sample_once([self.rows[0], self.rows[1]])
        witnesses = self.finish()
        self.assertEqual(len(witnesses), 1)
        self.assertEqual(self.observer.redacted_receipt()["status"], "SAMPLING_FINISHED_UNVERIFIED")
        self.assertEqual(self.review(witnesses)["status"], "BLOCKED")
        self.assertIn("original-child-handle-missing-or-ambiguous",
                      self.review(witnesses)["failed_checks"])

    def test_pid_reuse_and_parent_spoof_faults_are_permanent(self):
        self.observer.sample_once(self.rows)
        self.backend.timing[601]["birth"] += 50_000
        self.observer.sample_once(self.rows)
        witnesses = self.finish()
        self.assertEqual(len(witnesses), 1)  # the old original handle's birth must not change
        self.assertIn("snapshot-duplicate-or-reused-pid", self.observer.redacted_receipt()["faults"])
        self.assertEqual(self.observer.redacted_receipt()["status"], "BLOCKED")

    def test_duplicate_pid_in_one_snapshot_cannot_be_deduplicated_into_evidence(self):
        rows = self.rows + [(601, 600, "msedgewebview2.exe")]
        self.observer.sample_once(rows)
        self.finish()
        self.assertEqual(set(self.backend.opened), {602})
        self.assertIn("snapshot-duplicate-or-reused-pid", self.observer.redacted_receipt()["faults"])
        self.assertEqual(self.observer.redacted_receipt()["status"], "BLOCKED")

    def test_unarmed_live_snapshot_call_is_refused_before_win32_initialization(self):
        with self.assertRaisesRegex(trace.EvidenceValidationError, "live-sampling-not-authorized"):
            self.observer.sample_once()
        self.assertEqual(self.backend.opened, [])

    def test_no_unrelated_or_unrecognized_process_is_queried(self):
        self.rows.append((800, 602, "powershell.exe"))
        self.observer.sample_once(self.rows)
        self.finish()
        self.assertEqual(set(self.backend.opened), {601, 602})
        self.assertIn("unexpected-descendant", self.observer.redacted_receipt()["faults"])

    def test_failed_open_and_capacity_gaps_cannot_be_credited(self):
        self.observer.max_handles = 1
        self.observer.sample_once(self.rows)
        self.finish()
        self.assertIn("handle-limit-reached", self.observer.redacted_receipt()["faults"])
        self.assertEqual(self.observer.redacted_receipt()["retained_original_handle_count"], 1)

    def test_no_sample_or_incomplete_original_exit_blocks(self):
        self.observer.finish()
        self.assertEqual(self.observer.redacted_receipt()["status"], "BLOCKED")
        other = ScopedQaChildHandleObserver(root_process=self.root, expected_app_image=APP,
            open_handle=self.backend.open_handle, process_times=self.backend.times,
            process_images=self.backend.images)
        other.sample_once(self.rows)
        other.finish()
        self.assertEqual(other.redacted_receipt()["status"], "BLOCKED")
        self.assertIn("handle-exit-unavailable", other.redacted_receipt()["faults"])

    def test_live_start_rejected_on_unapproved_non_hosted_environment(self):
        with patch("qa.p4_research.n12_no_cdp_child_handles.os.name", "posix"):
            with self.assertRaisesRegex(trace.EvidenceValidationError, "hosted-consent-or-source"):
                self.observer.start_live(profile="c:/private/profile", env={})
        self.assertEqual(self.backend.opened, [])

    def process_fixture(self):
        app = trace.Process("app", "launch", 600, APP, "a"*64, stamp(100_000), "", stamp(800_000))
        first = trace.Process("child1", "app", 601, WEB, None, stamp(210_000), "", stamp(640_000))
        second = trace.Process("child2", "child1", 602, WEB, None, stamp(300_000),
                               "--utility-sub-type=network.mojom.NetworkService", stamp(680_000))
        processes = {p.guid: p for p in (app, first, second)}
        roles = {"app": "app", "child1": "webview", "child2": "webview-network"}
        events = [
            event(1, 600, 600, 100_000, 100_100, APP, parent=50, parent_sequence=50),
            event(2, 600, 600, 100_000, 800_100, "pilotodin-desk", exit=800_000),
            event(1, 601, 601, 210_000, 210_100, WEB, parent=600, parent_sequence=600),
            event(2, 601, 601, 210_000, 640_100, "msedgewebview2", exit=640_000),
            event(1, 602, 602, 300_000, 300_100, WEB, parent=601, parent_sequence=601),
            event(2, 602, 602, 300_000, 680_100, "msedgewebview2", exit=680_000),
        ]
        lifetimes = etw.EtwLifetimes(events, DEVICES, (ORIGIN, ORIGIN + 900_000),
                                    no_cdp_sysmon_corroboration=True)
        return processes, roles, lifetimes

    def review(self, witnesses, **modifiers):
        processes, roles, lifetimes = self.process_fixture()
        sources = {"processes": processes, "roles": roles, "app_guid": "app",
                   "witnesses": witnesses, "lifetimes": lifetimes,
                   "collector_receipt": self.observer.redacted_receipt(),
                   "source_issues": set()}
        sources.update(modifiers)
        return review_scoped_children(**sources)

    def test_full_fake_child_tree_is_only_reviewable_not_accepted(self):
        self.observer.sample_once(self.rows)
        witnesses = self.finish()
        report = self.review(witnesses)
        self.assertEqual(report["status"], "REVIEWABLE_ONLY")
        self.assertEqual(report["verified_handle_counts"], {"webview": 1, "webview-network": 1})
        self.assertEqual(report["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertNotIn("pid", json.dumps(report).lower())
        self.assertNotIn(WEB, json.dumps(report))

    def test_missing_one_witness_fails_join(self):
        self.observer.sample_once([self.rows[0], self.rows[1]])
        witnesses = self.finish()
        result = self.review(witnesses)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failed_checks"]["original-child-handle-missing-or-ambiguous"], 1)

    def test_wrong_parent_full_image_and_handle_time_fail_join(self):
        self.observer.sample_once(self.rows)
        witnesses = self.finish()
        for mutation in (
            lambda w: w.__setitem__("parent_pid", 999),
            lambda w: w.__setitem__("image_native", r"\Device\HarddiskVolume3\qa\wrong\msedgewebview2.exe"),
            lambda w: w.__setitem__("exit", w["exit"] + 10),
        ):
            modified = [dict(row) for row in witnesses]
            mutation(modified[1])
            result = self.review(modified)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertTrue(result["failed_checks"])

    def test_ambiguous_duplicate_witness_and_unrelated_extra_are_refused(self):
        self.observer.sample_once(self.rows)
        witnesses = list(self.finish())
        duplicate = self.review(witnesses + [dict(witnesses[1])])
        self.assertEqual(duplicate["status"], "BLOCKED")
        other = self.review(witnesses + [{"pid": 901, "birth": ORIGIN + 300_000,
                "exit": ORIGIN + 680_000, "parent_pid": 900,
                "image_dos": WEB, "image_native": NATIVE_WEB}])
        self.assertEqual(other["status"], "BLOCKED")
        self.assertIn("unmatched-or-duplicate-retained-handle", other["failed_checks"])

    def test_missing_sysmon_exit_wrong_sequence_and_capture_loss_fail(self):
        self.observer.sample_once(self.rows)
        witnesses = self.finish()
        processes, roles, lifetimes = self.process_fixture()
        processes["child2"].end = None
        self.assertEqual(self.review(witnesses, processes=processes)["status"], "BLOCKED")
        wrong_sequence = deepcopy(lifetimes)
        wrong_sequence.stops[602][0] = etw.Lifecycle(**{
            **vars(wrong_sequence.stops[602][0]), "sequence": 999})
        self.assertEqual(self.review(witnesses, lifetimes=wrong_sequence)["status"], "BLOCKED")
        self.assertEqual(self.review(witnesses, source_issues={"etw-event-or-buffer-loss"})["status"], "BLOCKED")
        self.assertEqual(self.review(witnesses, source_issues={"process-root-missing-or-ambiguous"})["status"], "BLOCKED")

    def test_unbound_descendant_or_wrong_role_fails_review(self):
        self.observer.sample_once(self.rows)
        witnesses = self.finish()
        processes, roles, lifetimes = self.process_fixture()
        roles.pop("child2")
        result = self.review(witnesses, processes=processes, roles=roles)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("unexpected-app-descendant", result["failed_checks"])
