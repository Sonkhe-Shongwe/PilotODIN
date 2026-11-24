"""G2.15 static C++ source and DISARMED native workflow boundary."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CPP = ROOT / "qa/p4_native/g215_generated_duplicate_type.cpp"
WF = ROOT / ".github/workflows/p4-r025-g215-generated-duplicate-type.yml"
MARKER = ROOT / "qa/p4_research/N12_G215_GENERATED_DUPLICATE_OWNER_APPROVAL_FRESH_ONE_USE.txt"


class G215NativeScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cpp = CPP.read_text(encoding="utf-8")
        cls.wf = WF.read_text(encoding="utf-8")

    def test_one_use_marker_consumed_and_native_workflow_stays_disabled(self):
        # Successful generated-only Windows run 45300245828 consumed this
        # precise approval; the marker is retained as auditable evidence.
        self.assertTrue(MARKER.is_file())
        self.assertEqual(
            MARKER.read_text(encoding="utf-8"),
            "reviewed_source=f3962d21ab739f0d217457213e8809c82034a4e8\n"
            "scope=g215-one-generated-self-process-duplicate-type\n",
        )
        self.assertIn("1975e71be4e0335966f7b421a426d0b1877d1b60", self.wf)
        self.assertNotIn("    if: ${{ true }}", self.wf)
        self.assertIn("    if: ${{ false }}", self.wf)
        self.assertNotIn("workflow_dispatch", self.wf)
        self.assertIn("scope=g215-one-generated-self-process-duplicate-type", self.wf)
        self.assertIn("git diff --name-only $source HEAD", self.wf)
        self.assertIn("$changed.Count -ne 2", self.wf)
        self.assertIn("$added.Count -ne 1", self.wf)
        self.assertIn("git checkout --detach $source", self.wf)
        self.assertIn("$env:GITHUB_RUN_ATTEMPT -cne '1'", self.wf)

    def test_only_generated_self_process_and_no_name_apis(self):
        self.assertIn("GetCurrentProcess()", self.cpp)
        self.assertIn("DuplicateHandle(", self.cpp)
        self.assertIn("GetFileType(", self.cpp)
        self.assertIn("SetLastError(NO_ERROR)", self.cpp)
        self.assertIn("FILE_TYPE_UNKNOWN", self.cpp)
        self.assertIn("DUPLICATE_SAME_ACCESS", self.cpp)
        for forbidden in (
            "OpenProcess(", "PssCaptureSnapshot(", "NtQuerySystemInformation",
            "GetFinalPathNameByHandle", "GetFileInformationByHandleEx",
            "QueryFullProcessImageName", "GetFileName", "msedgewebview2",
            "system(", "WinHttp", "InternetOpen", "CreateProcess(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.cpp)
        self.assertIn("RUNNER_TEMP", self.cpp)
        self.assertIn("FILE_FLAG_DELETE_ON_CLOSE", self.cpp)
        self.assertIn("CloseHandle(duplicated)", self.cpp)
        self.assertIn("CloseHandle(original)", self.cpp)
        self.assertIn("G215_CLEANUP_BLOCKED", self.cpp)

    def test_public_output_fixed_label_and_no_native_app(self):
        self.assertIn('g2_15=%s', self.cpp)
        self.assertNotIn("%ls", self.cpp)
        self.assertNotIn("%p", self.cpp)
        self.assertIn("No raw handle", self.wf)
        self.assertNotIn("cargo ", self.wf)
        self.assertNotIn("npm ", self.wf)
        self.assertNotIn("n12_app_lifetime", self.wf)
        self.assertNotIn("Invoke_P4_N12_Live_Calibration", self.wf)


if __name__ == "__main__":
    unittest.main()
