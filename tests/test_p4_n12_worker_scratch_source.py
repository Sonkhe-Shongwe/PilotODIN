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
        self.assertIn("pins.prepare(&app_root)?", helper)
        self.assertIn('pins.prepare(&root.join("data"))?', helper)
        self.assertIn("pins.prepare(&home.join(profile))", helper)
        self.assertNotIn("create_dir_all", helper)

    def test_rejects_junction_escape_and_nonliteral_worker_directory_names(self):
        src = RUST.read_text(encoding="utf-8")
        helper = slice_between(src, "fn worker_temp_directory(", "// Verify the actual production environment")
        self.assertIn("pins.prepare_worker_temp(home, name)", helper)
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
        self.assertIn("worker_data_home(&app, &mut storage_pins)?", launch)
        self.assertIn('worker_temp_directory(&data_dir, "backend-temp", &mut storage_pins)?', launch)
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

    def test_retained_directory_handles_precede_creation_and_spawn(self):
        src = RUST.read_text(encoding="utf-8")
        policy = BOUNDARY.read_text(encoding="utf-8")
        prepare = slice_between(policy, "pub fn prepare(&mut self", "pub fn prepare_worker_temp(&mut self")
        self.assertLess(prepare.index("self.admit_existing(parent)?"), prepare.index("prepare_directory(path)?"))
        self.assertLess(prepare.index("prepare_directory(path)?"), prepare.index("self.admit_existing(&prepared)?"))
        self.assertIn(".share_mode(0x3)", policy)
        self.assertIn("GetFileInformationByHandleEx", policy)
        for start, end in (("fn launch_backend(", "fn verify_bundled_model("),
                           ("fn launch_bundled_ai(", "const MAX_REPORT_EXPORT_BYTES")):
            launch = slice_between(src, start, end)
            self.assertLess(launch.index("storage_pins.verify()?"), launch.index("command.spawn()"))
            self.assertIn("_storage_pins: storage_pins", launch)
        profile = RUST.with_name("desktop_profile.rs").read_text(encoding="utf-8")
        self.assertIn("pins: DirectoryPins", profile)
        self.assertIn("pins.prepare(root)?", profile)
        self.assertIn("verify_root(&root)?", src)

    def test_no_application_wide_environment_or_production_webview_override(self):
        import json
        src = RUST.read_text(encoding="utf-8")
        helper = slice_between(src, "fn worker_temp_directory(", "// Verify the actual production environment")
        self.assertNotIn("set_var(", helper)
        self.assertNotIn("remove_var(", helper)
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        main = config["app"]["windows"][0]
        self.assertNotIn("dataDirectory", main)
        self.assertNotIn("appDirectoriesOverride", config["app"])
        self.assertNotIn("create", main)  # QA may inherit the base window list.
        run = src.split("pub fn run() {", 1)[1]
        self.assertLess(run.index("context.config_mut()"), run.index("config.app.windows[0].create = false"))
        self.assertLess(run.index("config.app.windows[0].create = false"), run.index("tauri::Builder::default()"))
        self.assertIn("config.app.app_directories_override.is_some()", run)
        self.assertIn(".build(context)", run)
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

    def test_effective_profile_is_checked_before_launch_and_close_drains_owned_workers(self):
        src = RUST.read_text(encoding="utf-8")
        launch = slice_between(src, "async fn launch_backend(", "fn verify_bundled_model(")
        self.assertLess(launch.index("verify_effective_desktop_profile(&window).await?"),
                        launch.index("command.spawn()"))
        self.assertIn("ICoreWebView2Environment7", src)
        self.assertIn("environment.UserDataFolder(&mut value)", src)
        self.assertIn("verify_effective_directory(&root", src)
        close = slice_between(src, "async fn resolve_native_close_request(", "// This command acknowledges QA")
        self.assertLess(close.index("consume_native_close_ticket"), close.index("stop_owned_workers"))
        self.assertLess(close.index("stop_owned_workers"), close.index("window.destroy()"))
        shutdown = slice_between(src, "fn stop_owned_workers(", "#[tauri::command]\nasync fn launch_backend")
        self.assertLess(shutdown.index("stopping.store(true"), shutdown.index("child.write("))
        self.assertLess(shutdown.index("child.write("), shutdown.index("terminate_owned_child(worker.child.take())"))
        self.assertIn("wait_for_worker(&worker.exit", shutdown)
        self.assertIn("exit is not confirmed", shutdown)


if __name__ == "__main__":
    unittest.main()
