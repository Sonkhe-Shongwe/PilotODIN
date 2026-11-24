"""Source checks for actual bundled worker temp containment in production Rust.

These static contracts and synthetic fixtures never imply an N12 native PASS.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUST = ROOT / "frontend" / "src-tauri" / "src" / "lib.rs"
CONFIG = ROOT / "frontend" / "src-tauri" / "tauri.conf.json"
BOUNDARY = RUST.with_name("storage_boundary.rs")


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
        self.assertIn('"baseline" => Some("baseline")', helper)
        self.assertIn('"candidate" => Some("candidate")', helper)
        self.assertIn("storage_boundary::prepare_directory(&app_root)?", helper)
        self.assertIn('storage_boundary::prepare_directory(&root.join("data"))?', helper)
        self.assertIn("storage_boundary::prepare_directory(&home.join(profile))", helper)
        self.assertNotIn("create_dir_all", helper)

    def test_rejects_junction_escape_and_nonliteral_worker_directory_names(self):
        src = RUST.read_text(encoding="utf-8")
        helper = slice_between(src, "fn worker_temp_directory(", "#[tauri::command]\nfn launch_backend")
        self.assertIn("storage_boundary::prepare_worker_temp(home, name)", helper)
        policy = BOUNDARY.read_text(encoding="utf-8")
        self.assertIn('matches!(name, "backend-temp" | "inference-temp")', policy)
        prepare = slice_between(policy, "pub fn prepare_directory(", "pub fn prepare_worker_temp(")
        self.assertLess(prepare.index("validate_existing_directory(parent)?"),
                        prepare.index("fs::create_dir(path)"))
        self.assertLess(prepare.index("fs::symlink_metadata(path)"),
                        prepare.index("fs::create_dir(path)"))
        self.assertIn("validate_existing_directory(path)?", prepare)
        self.assertIn("resolved.parent() != Some(after.as_path())", prepare)
        self.assertIn("metadata.file_attributes() & 0x400", policy)
        self.assertNotIn("create_dir_all", policy)

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
        self.assertIs(main.get("create"), False)
        setup = slice_between(src, ".setup(|app| {", ".invoke_handler(")
        self.assertIn('app.config().identifier == "com.pilotodin.studio"', setup)
        self.assertLess(setup.index("prepare_production_profile(&root)"), setup.index("app.manage(lease)"))
        self.assertLess(setup.index("app.manage(lease)"), setup.index(".data_directory(profile)"))
        self.assertLess(setup.index(".data_directory(profile)"), setup.index(".build()?"))
        profile = RUST.with_name("desktop_profile.rs").read_text(encoding="utf-8")
        self.assertIn("reject_registry_overrides()?", profile)
        self.assertIn(".share_mode(0)", profile)
        self.assertIn("info.links != 1", profile)
        self.assertNotIn("set_var(", profile)
        self.assertNotIn("appDirectoriesOverride", config["app"])


if __name__ == "__main__":
    unittest.main()
