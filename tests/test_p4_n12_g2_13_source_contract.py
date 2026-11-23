"""G2.13 source-only contract for a DISARMED generated Windows PSS probe."""
import ctypes
from pathlib import Path
import re
import unittest

from qa.p4_research import n12_pss_win32_backend as native

ROOT = Path(__file__).resolve().parents[1]
CPP = ROOT / "qa/p4_native/g213_generated_pss_probe.cpp"
WF = ROOT / ".github/workflows/p4-r025-g213-generated-pss.yml"
MARKER = ROOT / "qa/p4_research/N12_G213_GENERATED_PSS_OWNER_APPROVAL_FRESH_ONE_USE.txt"


class G213SourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cpp = CPP.read_text(encoding="utf-8")
        cls.wf = WF.read_text(encoding="utf-8")

    def test_no_owner_approval_marker_and_workflow_remains_disarmed(self):
        self.assertFalse(MARKER.exists())
        self.assertRegex(self.wf, r"(?m)^\s+if: \$\{\{ false \}\}")
        self.assertNotIn("workflow_dispatch", self.wf)
        self.assertIn("PILOTODIN_G213_GENERATED_CONSENT", self.wf)

    def test_approval_is_fresh_direct_child_and_exact_source(self):
        for s in ("$env:GITHUB_RUN_ATTEMPT -cne '1'",
                  "git rev-list --parents -n 1 HEAD",
                  "git diff --name-only $source HEAD",
                  "git checkout --detach $source",
                  "$changed.Count -ne 2", "$added.Count -ne 1",
                  "scope=g213-one-generated-process-one-pss-feasibility"):
            with self.subTest(s=s):
                self.assertIn(s, self.wf)

    def test_only_one_generated_self_process_no_webview_or_installer(self):
        self.assertIn("GetCurrentProcess()", self.cpp)
        self.assertNotIn("OpenProcess(", self.cpp)
        for forbidden in ("msedgewebview2", "pilotodin-engine", "PILOTODIN_HOME",
                          "PssDuplicateSnapshot", "DuplicateHandle(", "system(",
                          "ShellExecute", "WinHttp", "InternetOpen", "URLDownloadToFile"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.cpp)
        self.assertNotIn("cargo ", self.wf)
        self.assertNotIn("tauri", self.wf.lower().split("- name: compile windows sdk")[1].split("- name: execute generated")[0])

    def test_generated_only_runner_root_and_delete_on_close(self):
        for s in ("RUNNER_TEMP", "GetTempFileNameW", "FILE_FLAG_DELETE_ON_CLOSE",
                  "FILE_ATTRIBUTE_REPARSE_POINT", "GENERIC_WRITE | DELETE",
                  "DeleteFileW(fixture_name)",
                  "GetFileAttributesW(fixture_name)", "CloseHandle(file)"):
            self.assertIn(s, self.cpp)

    def test_sdk_abi_match_x64_ctypes_contract(self):
        self.assertEqual(ctypes.sizeof(native._HandleEntry), 136)
        expected = {"Handle": 0, "Flags": 8, "ObjectType": 12,
                    "CaptureTime": 16, "CreationTime": 48,
                    "TypeNameLength": 56, "TypeName": 64,
                    "ObjectNameLength": 72, "ObjectName": 80,
                    "TypeSpecificInformation": 88}
        mapped = {"Handle": "handle", "Flags": "flags",
                  "ObjectType": "object_type", "CaptureTime": "capture_time",
                  "CreationTime": "creation_time", "TypeNameLength": "type_name_bytes",
                  "TypeName": "type_name", "ObjectNameLength": "object_name_bytes",
                  "ObjectName": "object_name", "TypeSpecificInformation": "type_info"}
        for field, offset in expected.items():
            with self.subTest(field=field):
                self.assertIn(f"offsetof(PSS_HANDLE_ENTRY, {field}) == {offset}", self.cpp)
                self.assertEqual(getattr(native._HandleEntry, mapped[field]).offset, offset)
        self.assertIn("sizeof(PSS_HANDLE_ENTRY) == 136", self.cpp)

    def test_minimal_flags_no_object_names_or_system_scans(self):
        self.assertIn("PSS_CAPTURE_HANDLES | PSS_CAPTURE_HANDLE_BASIC_INFORMATION", self.cpp)
        self.assertIn("PSS_WALK_HANDLES", self.cpp)
        self.assertIn("PSS_HANDLE_HAVE_TYPE", self.cpp)
        self.assertIn("PSS_HANDLE_HAVE_NAME", self.cpp)
        self.assertIn("PssFreeSnapshot(GetCurrentProcess(), snapshot)", self.cpp)
        for forbidden in ("PSS_CAPTURE_HANDLE_NAME_INFORMATION",
                          "PSS_CAPTURE_VA_CLONE", "PSS_CAPTURE_THREADS",
                          "NtQuerySystemInformation", "PssCaptureSnapshot(process"):
            self.assertNotIn(forbidden, self.cpp)

    def test_full_walk_or_fail_closed_after_256(self):
        self.assertIn("kMaximumRows = 256", self.cpp)
        self.assertIn("i <= kMaximumRows", self.cpp)
        self.assertIn("i == kMaximumRows", self.cpp)
        self.assertIn("G213_HANDLE_WALK_INCOMPLETE", self.cpp)
        self.assertIn("!completed_walk", self.cpp)

    def test_only_generated_file_type_classification_public(self):
        self.assertIn('G213_GENERATED_FILE_TYPE_PRESENT', self.cpp)
        self.assertIn('G213_GENERATED_FILE_TYPE_UNAVAILABLE', self.cpp)
        self.assertIn('G213_GENERATED_HANDLE_NOT_OBSERVED', self.cpp)
        self.assertIn('g2_13=%s', self.cpp)
        self.assertNotIn('%ls', self.cpp)
        self.assertNotIn('%p', self.cpp)
        self.assertNotIn('std::wprintf', self.cpp)

    def test_no_native_execution_in_source_contract_suite(self):
        source = Path(native.__file__).read_text(encoding="utf-8")
        self.assertIn("def prepare_native_backend", source)
        self.assertIn('CONSENT = "I_APPROVE_ONE_N12_PSS_FILE_HANDLE_FEASIBILITY"', source)
        self.assertNotIn("n12_app_lifetime", self.wf)
        self.assertNotIn("Invoke_P4_N12_Live_Calibration", self.wf)


if __name__ == "__main__":
    unittest.main()
