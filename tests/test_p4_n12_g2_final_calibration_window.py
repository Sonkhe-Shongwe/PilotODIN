"""Synthetic-only final Sysmon calibration window tests, no native capture."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
from unittest.mock import patch

from qa.p4_research import n12_app_lifetime as lifetime


class G2FinalSysmonWindowTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 11, 22, 16, 4, 4, 757471, tzinfo=timezone.utc)
        self.end = self.start + timedelta(seconds=4)
        self.root = Path("synthetic-disposable-root")
        self.directory = self.root / "fixture-final"
        self.manifest = {"sysmon_first_record": 15}
        self.record = {"role": "calibration", "synthetic": True}
        self.events = []

    def test_window_starts_before_lead_in_and_stays_strict(self):
        events = self.events
        times = [self.start, self.end]

        def now():
            events.append("now")
            return times.pop(0)

        def sleep(seconds):
            events.append(("sleep", seconds))

        def calibrate(directory, manifest, *, child_hold_seconds):
            events.append(("calibrate", directory, child_hold_seconds))
            self.assertIs(manifest, self.manifest)
            return self.record

        def check(root, first, start, end, record, *, phase):
            events.append(("verify", start, end, phase))
            self.assertEqual((root, first, start, end, record, phase), (
                self.root, 15, self.start, self.end, self.record, "final"))
            return 37

        with (
            patch.object(lifetime.journey, "now", side_effect=now),
            patch.object(lifetime.time, "sleep", side_effect=sleep),
            patch.object(lifetime.journey, "calibrate", side_effect=calibrate),
            patch.object(lifetime.journey, "verify_fixture_sysmon", side_effect=check),
        ):
            actual = lifetime.verify_final_calibration(
                self.root, self.directory, self.manifest)

        self.assertEqual(actual, 37)
        self.assertEqual(events[0], "now")
        self.assertEqual(events[1], ("sleep", lifetime.journey.INITIAL_FIXTURE_LEAD_IN_SECONDS))
        self.assertGreaterEqual(events[1][1], 0.01)
        self.assertEqual(events[2], (
            "calibrate", self.directory, lifetime.journey.TRACED_FIXTURE_CHILD_HOLD_SECONDS))
        self.assertEqual(events[3], "now")
        self.assertEqual(events[4], ("verify", self.start, self.end, "final"))

    def test_reported_submillisecond_birth_rounding_is_prevented_not_waived(self):
        # Native diagnostic: creation +5279 ticks, Sysmon event -4710 ticks
        # from the original start, 9989 ticks difference (sub-millisecond).
        # Synthetic demonstration only; actual Sysmon timing is not proven.
        birth = self.start + timedelta(microseconds=527.9)
        recorded = birth.replace(microsecond=birth.microsecond // 1000 * 1000)
        self.assertLess(recorded, self.start)
        delayed_birth = birth + timedelta(seconds=lifetime.journey.INITIAL_FIXTURE_LEAD_IN_SECONDS)
        delayed_record = delayed_birth.replace(
            microsecond=delayed_birth.microsecond // 1000 * 1000)
        self.assertGreater(delayed_record, self.start)

    def test_strict_final_sysmon_rejection_propagates_without_retry(self):
        err = lifetime.trace.EvidenceValidationError("final parent-birth-before-window")
        with (
            patch.object(lifetime.journey, "now", side_effect=[self.start, self.end]),
            patch.object(lifetime.time, "sleep") as sleeping,
            patch.object(lifetime.journey, "calibrate", return_value=self.record) as fixture,
            patch.object(lifetime.journey, "verify_fixture_sysmon", side_effect=err) as verifier,
        ):
            with self.assertRaises(lifetime.trace.EvidenceValidationError):
                lifetime.verify_final_calibration(self.root, self.directory, self.manifest)
        sleeping.assert_called_once_with(lifetime.journey.INITIAL_FIXTURE_LEAD_IN_SECONDS)
        fixture.assert_called_once()
        verifier.assert_called_once()

    def test_failed_generated_fixture_cannot_reach_sysmon_review(self):
        error = lifetime.trace.EvidenceValidationError("calibration fixture blocked")
        with (
            patch.object(lifetime.journey, "now", return_value=self.start),
            patch.object(lifetime.time, "sleep"),
            patch.object(lifetime.journey, "calibrate", side_effect=error) as fixture,
            patch.object(lifetime.journey, "verify_fixture_sysmon") as verifier,
        ):
            with self.assertRaises(lifetime.trace.EvidenceValidationError):
                lifetime.verify_final_calibration(self.root, self.directory, self.manifest)
        fixture.assert_called_once()
        verifier.assert_not_called()


if __name__ == "__main__":
    unittest.main()
