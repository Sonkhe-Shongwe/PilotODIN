"""G2.24: the ordinary source branch must never rearm legacy N12 native jobs.

Static source guard, not a YAML execution engine or an approval authority.
A separately reviewed one-use activation must be isolated from ordinary CI.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1] / ".github" / "workflows"
ARCHIVED = {
    "p4-n12-app-journey.yml", "p4-n12-app-lifetime.yml",
    "p4-n12-backend-bytecode.yml", "p4-n12-background-thread.yml",
    "p4-n12-collector-inventory.yml", "p4-n12-egress-preflight.yml",
    "p4-n12-generated-sysmon-bookends.yml", "p4-n12-isolated-stack.yml",
    "p4-n12-kernel-symbols.yml", "p4-n12-lifetime-control.yml",
    "p4-n12-live-calibration.yml", "p4-n12-native-rundown.yml",
    "p4-n12-no-cdp-fileio.yml", "p4-n12-origin-stack.yml",
    "p4-n12-original-stack.yml", "p4-n12-procmon-environment-control.yml",
    "p4-n12-procmon-timing-control.yml", "p4-n12-protected-restore.yml",
    "p4-n12-recorder-dwell.yml", "p4-n12-socket-lifetime-control.yml",
    "p4-n12-staggered-writes.yml", "p4-n12-tmp-debugger-fixture.yml",
    "p4-n12-webview-storage.yml",
    "p4-r025-g213-generated-pss.yml", "p4-r025-g214-generated-pss-runtime.yml",
    "p4-r025-g215-generated-duplicate-type.yml",
}


def disarmed_job_count(source):
    """Require the reviewed block layout and a literal false per job."""
    sections = re.split(r"(?m)^jobs:\s*$", source)
    if len(sections) != 2:
        raise ValueError("unrecognized jobs layout")
    jobs = re.split(r"(?m)^  [a-zA-Z0-9_-]+:\s*$", sections[1])
    if len(jobs) < 2 or jobs[0].strip():
        raise ValueError("unrecognized job layout")
    for job in jobs[1:]:
        conditions = re.findall(r"(?m)^    if:[^\n]*$", job)
        if len(conditions) != 1 or not re.fullmatch(
            r"    if: \$\{\{ false \}\}(?:\s*#[^\n]*)?\s*", conditions[0]
        ):
            raise ValueError("native job not literally disarmed")
    return len(jobs) - 1


class NativeWorkflowGuards(unittest.TestCase):
    def test_all_archived_n12_jobs_are_literal_false(self):
        for name in sorted(ARCHIVED):
            with self.subTest(workflow=name):
                self.assertGreater(disarmed_job_count((ROOT / name).read_text(encoding="utf-8")), 0)

    def test_new_n12_workflow_requires_explicit_review(self):
        self.assertEqual({p.name for p in ROOT.glob("p4-n12-*.yml")},
                         {name for name in ARCHIVED if name.startswith("p4-n12-")})

    def test_missing_conditional_duplicate_and_folded_guard_fail(self):
        for body in (
            "    runs-on: windows-latest",
            "    if: ${{ github.run_attempt == '1' }}",
            "    if: >-\n      false",
            "    if: ${{ false }}\n    if: ${{ true }}",
        ):
            with self.subTest(body=body):
                with self.assertRaises(ValueError):
                    disarmed_job_count("jobs:\n  native:\n" + body + "\n")

    def test_one_unguarded_job_cannot_hide_behind_a_disarmed_job(self):
        with self.assertRaises(ValueError):
            disarmed_job_count("jobs:\n  old:\n    if: ${{ false }}\n  extra:\n    runs-on: windows-latest\n")

    def test_guard_is_source_only_and_watches_n12_workflows(self):
        ci = (ROOT / "p4-r02-5-fileio-source-contract.yml").read_text(encoding="utf-8")
        self.assertIn(".github/workflows/p4-n12-*.yml", ci)
        self.assertIn("runs-on: ubuntu-24.04", ci)
        self.assertIn("python -B -m unittest discover -s tests -p 'test_p4_n12_g2_24_native_workflow_guards.py'", ci)


if __name__ == "__main__":
    unittest.main()
