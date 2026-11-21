"""Source checks for actual bundled worker temp containment in production Rust.

These static contracts and synthetic fixtures never imply an N12 native PASS.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUST = ROOT / "frontend" / "src-tauri" / "src" / "lib.rs"
CONFIG = ROOT / "frontend" / "src-tauri" / "tauri.conf.json"


def slice_between(content, before, after):
    assert content.count(before) == 1, before
    return content.split(before, 1)[1].split(after, 1)[0]


class BundledWorkerProductFilesystemContract(unittest.TestCase):
    def test_both_worker_families_use_the_same_canonical_app_local_data_root(self):
        src = RUST.read_text(encoding="utf-8")
        helper = slice_between(src, "fn worker_data_home(", "fn worker_temp_directory(")
        self.assertIn("app.path().app_local_data_dir()", helper)
        self.assertIn('.join("data")', helper)
        self.assertIn('com.pilotodin.p4r03benchmark', helper)
        self.assertIn('"baseline" | "candidate"', helper)
        self.assertIn("std::fs::create_dir_all(&home)", helper)

    def test_rejects_junction_escape_and_nonliteral_worker_directory_names(self):
        src = RUST.read_text(encoding="utf-8")
        helper = slice_between(src, "fn worker_temp_directory(", "#[tauri::command]\nfn launch_backend")
        self.assertIn('matches!(name, "backend-temp" | "inference-temp")', helper)
        self.assertIn("home.canonicalize()", helper)
        self.assertIn("candidate.canonicalize()", helper)
        self.assertIn("resolved.parent() != Some(root.as_path())", helper)
        self.assertIn("Worker temporary storage escapes app data", helper)

    def test_backend_uses_own_temp_and_retains_project_data_home_and_cwd(self):
        src = RUST.read_text(encoding="utf-8")
        launch = slice_between(src, "fn launch_backend(", "fn verify_bundled_model(")
        self.assertIn("worker_data_home(&app)?", launch)
        self.assertIn('worker_temp_directory(&data_dir, "backend-temp")?', launch)
        for key in ("TEMP", "TMP", "TMPDIR"):
            self.assertIn(f'.env("{key}", worker_temp.as_os_str())', launch)
        self.assertIn('.env("PILOTODIN_HOME", data_dir.to_string_lossy().to_string())', launch)
        self.assertIn(".current_dir(&data_dir)", launch)

    def test_inference_retains_runtime_dll_cwd_and_its_own_temp_directory(self):
        src = RUST.read_text(encoding="utf-8")
        launch = slice_between(src, "fn launch_bundled_ai(", "const MAX_REPORT_EXPORT_BYTES")
        self.assertIn('worker_temp_directory(&worker_data_home(&app)?, "inference-temp")?', launch)
        for key in ("TEMP", "TMP", "TMPDIR"):
            self.assertIn(f'.env("{key}", worker_temp.as_os_str())', launch)
        self.assertIn('.env("PATH", runtime_path)', launch)
        self.assertIn(".current_dir(&runtime_dlls)", launch)

    def test_no_application_wide_environment_or_production_webview_override(self):
        import json
        src = RUST.read_text(encoding="utf-8")
        helper = slice_between(src, "fn worker_temp_directory(", "#[tauri::command]\nfn launch_backend")
        self.assertNotIn("set_var(", helper)
        self.assertNotIn("remove_var(", helper)
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        main = config["app"]["windows"][0]
        self.assertNotIn("dataDirectory", main)
        self.assertNotIn("appDirectoriesOverride", config["app"])


if __name__ == "__main__":
    unittest.main()
