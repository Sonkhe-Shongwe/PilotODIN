import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from qa.p4_native import n12_trace
from qa.p4_native import r06_prospective_fingerprint as r06


class ProspectiveFingerprintTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name).resolve()
        self.root = self.folder / r06.ORIGINAL_APP_ID
        self.root.mkdir()
        self.file = self.root / "private-project.csv"
        self.file.write_bytes(b"synthetic")
        self.before = self.folder / "before.json"
        self.after = self.folder / "after.json"

    def capture(self):
        # Use the real tree walker on Linux, substituting only the required
        # Windows path identity. On Windows the CLI test exercises it directly.
        with patch.object(n12_trace, "windows_path", return_value=r"C:\fixture\original"):
            return r06.capture(self.root)

    def set_bookends(self, before, after):
        start = datetime(2026, 11, 14, tzinfo=r06.UTC)
        for path, record, seconds in [(self.before, before, 0), (self.after, after, 10)]:
            record["started_utc"] = (start + timedelta(seconds=seconds)).isoformat()
            record["ended_utc"] = (start + timedelta(seconds=seconds + 1)).isoformat()
            path.write_text(json.dumps(record), encoding="utf-8-sig")

    def test_matching_endpoints_and_redacted_result(self):
        first = self.capture()
        self.assertNotIn(self.file.name, json.dumps(first))
        self.set_bookends(first, self.capture())
        output = io.StringIO()
        with patch.object(sys, "argv", ["r06", "compare", str(self.before), str(self.after)]):
            with redirect_stdout(output):
                self.assertEqual(r06.main(), 0)
        self.assertEqual(json.loads(output.getvalue()), {
            "endpoint_status": "MATCH", "continuous_trace": "NOT_EVALUATED",
        })

    def test_content_and_empty_directory_changes_are_differences(self):
        initial = self.capture()
        self.file.write_bytes(b"different")
        self.set_bookends(initial.copy(), self.capture())
        self.assertFalse(r06.compare(self.before, self.after))
        before_directory = self.capture()
        (self.root / "new-empty-directory").mkdir()
        self.set_bookends(before_directory, self.capture())
        self.assertFalse(r06.compare(self.before, self.after))

    def test_unstable_rescan_is_blocked(self):
        first = n12_trace.fingerprint

        def mutate_after_first_read(path):
            result = first(path)
            self.file.write_bytes(b"changed during capture")
            return result

        with patch.object(n12_trace, "windows_path", return_value=r"C:\fixture\original"):
            with patch.object(r06, "fingerprint", side_effect=mutate_after_first_read):
                with self.assertRaisesRegex(r06.EvidenceValidationError, "changed during"):
                    r06.capture(self.root)

    def test_wrong_root_reversed_epoch_and_historical_schema_are_blocked(self):
        first = self.capture()
        self.set_bookends(first.copy(), dict(first, root_id="0" * 64))
        with self.assertRaisesRegex(r06.EvidenceValidationError, "roots differ"):
            r06.compare(self.before, self.after)
        self.set_bookends(first.copy(), first.copy())
        with self.assertRaisesRegex(r06.EvidenceValidationError, "overlap or are reversed"):
            r06.compare(self.after, self.before)
        self.before.write_text('{"schema_version": 1}', encoding="utf-8")
        with self.assertRaisesRegex(r06.EvidenceValidationError, "prospective R06"):
            r06.compare(self.before, self.after)

    def test_missing_inputs_do_not_leak_private_paths(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["r06", "compare", str(self.before), str(self.after)]):
            with redirect_stderr(output):
                self.assertEqual(r06.main(), 2)
        self.assertNotIn(str(self.before), output.getvalue())

    @unittest.skipIf(os.name == "nt", "symlink creation needs Windows privileges")
    def test_tree_walker_rejects_a_link_and_a_linked_ancestor(self):
        outside = self.folder / "outside"
        outside.mkdir()
        link = self.root / "linked-directory"
        link.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(r06.EvidenceValidationError, "snapshot contains a reparse point"):
            self.capture()
        (outside / "nested").mkdir()
        with self.assertRaisesRegex(r06.EvidenceValidationError, "original-data root traverses"):
            r06.capture(link / "nested")

    @unittest.skipUnless(os.name == "nt", "Windows capture entry point")
    def test_windows_cli_resolves_the_generated_original_tree(self):
        self.assertEqual(os.environ.get("RUNNER_ENVIRONMENT"), "github-hosted")
        self.assertEqual(os.environ.get("GITHUB_ACTIONS"), "true")
        run = subprocess.run(
            [sys.executable, "-B", "-m", r06.__name__, "capture"],
            env=dict(os.environ, LOCALAPPDATA=str(self.folder)), capture_output=True,
            text=True, check=True, timeout=10,
        )
        record = json.loads(run.stdout)
        self.assertEqual(record["digest"], n12_trace.fingerprint(self.root)["digest"])
        self.assertNotIn(self.file.name, run.stdout)
        self.assertNotIn(str(self.root), run.stdout)


if __name__ == "__main__":
    unittest.main()
