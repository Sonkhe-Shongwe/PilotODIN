//! PilotODIN desktop lifecycle supervisor.
//! Python and bundled inference are separate loopback-only, per-session workers.
//! AI has no arbitrary process- or filesystem-execution capability.
use std::fs::File;
use std::io::Read;
use std::path::Path;
use std::net::TcpListener;
use std::sync::Mutex;
use sha2::{Digest, Sha256};
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, Manager, RunEvent, State};
use tauri_plugin_shell::{process::{CommandChild, CommandEvent}, ShellExt};
use tauri_plugin_dialog::DialogExt;

#[derive(Clone, Serialize)]
struct BackendConnection {
    port: u16,
    token: String,
}

struct ActiveBackend {
    connection: BackendConnection,
    child: CommandChild,
}

struct InferenceSettings {
    port: u16,
    token: String,
}

struct ActiveInference {
    child: CommandChild,
    token: String,
}

#[derive(Default)]
struct DesktopState {
    backend: Mutex<Option<ActiveBackend>>,
    inference: Mutex<Option<ActiveInference>>,
    inference_settings: Mutex<Option<InferenceSettings>>,
}

// A native CloseRequested event is not a browser beforeunload navigation.
// Always block OS close until the live Studio explicitly approves this ticket.
// Tickets hold no project identifiers or form values.
#[derive(Default)]
struct NativeCloseState {
    pending: Mutex<Option<String>>,
}

#[derive(Clone, Serialize)]
struct NativeCloseRequest {
    token: String,
}

fn consume_native_close_ticket(pending: &mut Option<String>, provided: &str) -> bool {
    if pending.as_deref() != Some(provided) { return false; }
    *pending = None;
    true
}

#[tauri::command]
fn resolve_native_close_request(
    window: tauri::WebviewWindow,
    state: State<'_, NativeCloseState>,
    token: String,
    approve: bool,
) -> Result<(), String> {
    if window.label() != "main" { return Err("Unexpected desktop window".into()); }
    let mut pending = state.pending.lock()
        .map_err(|_| "Native close state unavailable".to_string())?;
    if !consume_native_close_ticket(&mut pending, &token) {
        return Err("Native close request expired or was not issued".into());
    }
    drop(pending);
    if approve {
        // close() would re-enter CloseRequested and loop. destroy() is only
        // reachable with a one-use ticket issued by an actual OS close event.
        window.destroy().map_err(|e| format!("Could not close window: {e}"))?;
    }
    Ok(())
}

// QA-only deterministic exit for the isolated P3 Quality W5 native test.
// It cannot close the installed app or the accepted W1-W4 harness: debug
// build, exact native QA application identifier and both launch flags are
// all mandatory. Only an explicit click in the synthetic QA window invokes
// it, after the frontend verifies the reviewed v1 state.
fn eligible_p3_w5_qa_exit(
    debug: bool, identifier: &str, qa_flag: Option<&str>, smoke_flag: Option<&str>,
) -> bool {
    debug && identifier == "com.pilotodin.p3qualityw5qa"
        && qa_flag == Some("1") && smoke_flag == Some("1")
}

#[tauri::command]
fn finish_p3_w5_synthetic_qa(window: tauri::WebviewWindow) -> Result<(), String> {
    if window.label() != "main" { return Err("Unexpected desktop window".into()); }
    let qa_flag = std::env::var("VITE_P3_NATIVE_QUALITY_W5_QA").ok();
    let smoke_flag = std::env::var("VITE_PILOTODIN_NATIVE_SMOKE").ok();
    if !eligible_p3_w5_qa_exit(
        cfg!(debug_assertions), &window.app_handle().config().identifier,
        qa_flag.as_deref(), smoke_flag.as_deref(),
    ) {
        return Err("Synthetic P3 W5 exit is unavailable outside the dedicated dev QA app".into());
    }
    // QA-only explicit finish bypasses a potentially stuck CloseRequested
    // ticket; production app unsaved-draft veto remains unchanged.
    window.destroy().map_err(|e| format!("Synthetic native QA window could not close: {e}"))
}

// This is intentionally a Rust-side dialog. The Tauri dialog plugin may
// replace browser window.confirm with an asynchronous IPC function, so the
// native close handshake must never assume a synchronous browser boolean.
#[tauri::command]
async fn confirm_native_close(
    window: tauri::WebviewWindow,
    state: State<'_, NativeCloseState>,
    token: String,
) -> Result<bool, String> {
    if window.label() != "main" { return Err("Unexpected desktop window".into()); }
    {
        let guard = state.pending.lock()
            .map_err(|_| "Native close state unavailable".to_string())?;
        if guard.as_deref() != Some(token.as_str()) {
            return Err("Native close request expired or was not issued".into());
        }
    }
    // A blocking system dialog must NOT run on the WebView/UI thread.
    // Only an explicit click on Close allows the existing ticket resolver
    // to destroy the window. Cancellation leaves the form and window intact.
    let prompt = window.dialog()
        .message("You have unsaved changes in the workspace. Closing this window will discard those changes.")
        .title("PilotODIN - Unsaved changes")
        .kind(tauri_plugin_dialog::MessageDialogKind::Warning)
        .buttons(tauri_plugin_dialog::MessageDialogButtons::OkCancelCustom(
            "Close PilotODIN".into(), "Stay".into(),
        ))
        .parent(&window);
    tauri::async_runtime::spawn_blocking(move || prompt.blocking_show())
        .await.map_err(|_| "Native confirmation could not finish".to_string())
}

// WebView2 must not use a synchronous browser confirm to discard edited inputs.
// The native dialog has explicit Stay and Switch buttons and is owned by main.
#[tauri::command]
async fn confirm_native_project_switch(
    window: tauri::WebviewWindow,
) -> Result<bool, String> {
    if window.label() != "main" { return Err("Unexpected desktop window".into()); }
    let prompt = window.dialog()
        .message("You have unsaved changes in this workspace. Switching projects may discard those edits. Continue?")
        .title("PilotODIN - Unsaved changes")
        .kind(tauri_plugin_dialog::MessageDialogKind::Warning)
        .buttons(tauri_plugin_dialog::MessageDialogButtons::OkCancelCustom(
            "Switch project".into(), "Stay".into(),
        ))
        .parent(&window);
    tauri::async_runtime::spawn_blocking(move || prompt.blocking_show())
        .await.map_err(|_| "Native project-switch confirmation could not finish".to_string())
}

// Route changes from an edited Deliver workspace must not rely on the
// synchronous browser confirm implementation in Windows WebView2.
// This command only asks for consent. JS must recheck the live project, route
// and dirty marker before performing any state transition.
#[tauri::command]
async fn confirm_native_deliver_exit(
    window: tauri::WebviewWindow,
) -> Result<bool, String> {
    if window.label() != "main" { return Err("Unexpected desktop window".into()); }
    let prompt = window.dialog()
        .message("Your Deliver report has unsaved changes. Switching workspaces will discard those edits.")
        .title("PilotODIN - Unsaved Deliver report")
        .kind(tauri_plugin_dialog::MessageDialogKind::Warning)
        .buttons(tauri_plugin_dialog::MessageDialogButtons::OkCancelCustom(
            "Leave Deliver".into(), "Keep editing".into(),
        ))
        .parent(&window);
    tauri::async_runtime::spawn_blocking(move || prompt.blocking_show())
        .await.map_err(|_| "Native Deliver confirmation could not finish".to_string())
}

#[derive(Deserialize)]
struct ModelManifest {
    model_file: String,
    model_sha256: String,
}

fn free_loopback_port() -> Result<u16, String> {
    let socket = TcpListener::bind("127.0.0.1:0")
        .map_err(|e| format!("Could not allocate local port: {e}"))?;
    let port = socket.local_addr().map_err(|e| e.to_string())?.port();
    drop(socket);
    Ok(port)
}

fn new_token() -> String {
    format!("{}{}", uuid::Uuid::new_v4().simple(), uuid::Uuid::new_v4().simple())
}

#[tauri::command]
fn launch_backend(app: AppHandle, state: State<'_, DesktopState>) -> Result<BackendConnection, String> {
    let mut guard = state.backend.lock().map_err(|_| "Engine state unavailable".to_string())?;
    if let Some(existing) = guard.as_ref() {
        return Ok(existing.connection.clone());
    }
    let port = free_loopback_port()?;
    let inference_port = free_loopback_port()?;
    if port == inference_port {return Err("Port reservation collision".into());}
    let token = new_token();
    let inference_token = new_token();
    let data_dir = app.path().app_local_data_dir().map_err(|e| e.to_string())?.join("data");
    std::fs::create_dir_all(&data_dir)
        .map_err(|e| format!("Could not prepare user storage: {e}"))?;

    // Supplying a dedicated port and key does not start or load a model.
    // Only a deliberate local AI request invokes launch_bundled_ai.
    let command = app.shell().sidecar("pilotodin-engine")
        .map_err(|e| format!("Bundled analytical engine missing: {e}"))?
        .env("PILOTODIN_HOME", data_dir.to_string_lossy().to_string())
        .env("PILOTODIN_DESKTOP_PORT", port.to_string())
        .env("PILOTODIN_DESKTOP_SESSION", token.as_str())
        .env("PILOTODIN_BUNDLED_LLM_PORT", inference_port.to_string())
        .env("PILOTODIN_BUNDLED_LLM_TOKEN", inference_token.as_str())
        .env("PILOTODIN_DESKTOP_ALLOW_DEV", if cfg!(debug_assertions) { "1" } else { "0" })
        .set_process_group(true);
    let (mut events, child) = command.spawn()
        .map_err(|e| format!("Could not start analytical engine: {e}"))?;
    let connection = BackendConnection { port, token: token.clone() };
    *guard = Some(ActiveBackend { connection: connection.clone(), child });
    *state.inference_settings.lock().map_err(|_| "AI state unavailable".to_string())? =
        Some(InferenceSettings { port: inference_port, token: inference_token });
    drop(guard);

    let owner = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = events.recv().await {
            match event {
                CommandEvent::Terminated(_) => {
                    let state = owner.state::<DesktopState>();
                    if let Ok(mut active) = state.backend.lock() {
                        if active.as_ref().map(|b| b.connection.token == token).unwrap_or(false) {
                            *active = None;
                            if let Ok(mut ai) = state.inference.lock() {
                                if let Some(worker) = ai.take() {let _ = worker.child.kill();}
                            }
                            if let Ok(mut settings) = state.inference_settings.lock() {*settings = None;}
                        }
                    }
                    break;
                }
                CommandEvent::Error(message) => eprintln!("Analytical engine error: {message}"),
                _ => {}
            }
        }
    });
    Ok(connection)
}

fn verify_bundled_model(app: &AppHandle) -> Result<std::path::PathBuf, String> {
    let resources = app.path().resource_dir().map_err(|e| e.to_string())?;
    let manifest_file = resources.join("models").join("model-manifest.json");
    let manifest: ModelManifest = serde_json::from_slice(
        &std::fs::read(&manifest_file).map_err(|_| "Bundled AI manifest missing".to_string())?
    ).map_err(|_| "Invalid bundled AI manifest".to_string())?;
    // Reject path traversal and alternate model paths from a modified manifest.
    if manifest.model_file != "qwen3-1.7b-q4_k_m.gguf" || manifest.model_sha256.len() != 64 ||
       !manifest.model_sha256.bytes().all(|c| c.is_ascii_hexdigit()) {
        return Err("Invalid bundled model identity".into());
    }
    let model = resources.join("models").join(&manifest.model_file);
    let mut reader = File::open(&model).map_err(|_| "Bundled offline model missing".to_string())?;
    let mut hash = Sha256::new();
    let mut chunk = [0u8; 1024 * 1024];
    loop {
        let count = reader.read(&mut chunk).map_err(|_| "Could not verify local AI model".to_string())?;
        if count == 0 {break;}
        hash.update(&chunk[..count]);
    }
    let computed = format!("{:x}", hash.finalize());
    if !computed.eq_ignore_ascii_case(&manifest.model_sha256) {
        return Err("Bundled local model failed integrity verification".into());
    }
    Ok(model)
}

#[tauri::command]
fn launch_bundled_ai(app: AppHandle, state: State<'_, DesktopState>) -> Result<(), String> {
    // Only one local inference worker is permitted on constrained hardware.
    let mut active = state.inference.lock().map_err(|_| "AI state unavailable".to_string())?;
    if active.is_some() {return Ok(());}
    // Copy the settings before doing model integrity checks or spawning the worker.
    // A borrowed settings reference cannot be dropped to release the mutex.
    let (token, port) = {
        let guard = state.inference_settings.lock()
            .map_err(|_| "AI configuration unavailable".to_string())?;
        let settings = guard.as_ref().ok_or("Start analytics before AI")?;
        (settings.token.clone(), settings.port)
    };
    let model = verify_bundled_model(&app)?;
    let resources = app.path().resource_dir().map_err(|e| e.to_string())?;
    let runtime_dlls = resources.join("llama-runtime");
    let old_path = std::env::var_os("PATH").unwrap_or_default();
    let mut paths = vec![runtime_dlls.clone()];
    paths.extend(std::env::split_paths(&old_path));
    let runtime_path = std::env::join_paths(paths).map_err(|_| "Invalid inference runtime path".to_string())?;
    let command = app.shell().sidecar("pilotodin-inference")
        .map_err(|_| "Bundled inference executable missing".to_string())?
        .args(["--model", model.to_str().ok_or("Invalid model path")?,
               "--alias", "pilotodin-qwen3-1.7b", "--host", "127.0.0.1",
               "--port", &port.to_string(), "--ctx-size", "2048",
               "--threads", "2", "--parallel", "1", "--gpu-layers", "0",
               "--no-webui", "--no-agent"])
        .env("LLAMA_API_KEY", token.as_str())
        .env("PATH", runtime_path)
        // ggml_backend_load_all scans the executable directory and current
        // working directory, not PATH, for version-specific CPU backends.
        // Keep the runtime DLL directory as the process working directory.
        .current_dir(&runtime_dlls)
        .set_process_group(true);
    let (mut events, child) = command.spawn().map_err(|e| format!("Could not launch local model: {e}"))?;
    *active = Some(ActiveInference { child, token: token.clone() });
    drop(active);
    let owner = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = events.recv().await {
            match event {
                CommandEvent::Terminated(_) => {
                    if let Ok(mut active) = owner.state::<DesktopState>().inference.lock() {
                        if active.as_ref().map(|w| w.token == token).unwrap_or(false) {*active = None;}
                    }
                    break;
                }
                CommandEvent::Error(message) => eprintln!("Local AI worker error: {message}"),
                _ => {}
            }
        }
    });
    Ok(())
}


const MAX_REPORT_EXPORT_BYTES: usize = 12 * 1024 * 1024;

#[derive(Serialize)]
struct NativeReportSave {
    status: &'static str,
    filename: Option<String>,
}

fn check_report_payload(format: &str, filename: &str, bytes: &[u8]) -> Result<(), String> {
    // This command is deliberately NOT a general-purpose filesystem writer.
    // It handles only previously fetched, bounded HTML/PDF report payloads.
    let extension = match format {
        "html" => ".html",
        "pdf" => ".pdf",
        _ => return Err("Choose a PDF or HTML report format".into()),
    };
    if filename.is_empty() || filename.len() > 180 ||
       filename.chars().any(|c| c.is_control() || matches!(c, '/' | '\\' | ':' | '*' | '?' | '"' | '<' | '>' | '|')) ||
       !filename.to_ascii_lowercase().ends_with(extension) {
        return Err("Invalid report filename or extension".into());
    }
    if bytes.is_empty() || bytes.len() > MAX_REPORT_EXPORT_BYTES {
        return Err("The report export is empty or exceeds the safe desktop size limit".into());
    }
    let valid_signature = if format == "pdf" {
        bytes.starts_with(b"%PDF-")
    } else {
        bytes.get(..15).map(|x| x.eq_ignore_ascii_case(b"<!doctype html>"))
            .unwrap_or(false)
    };
    if !valid_signature {
        return Err("Report file content does not match its declared format".into());
    }
    Ok(())
}

#[tauri::command]
async fn save_report_as(app: AppHandle, format: String, filename: String, bytes: Vec<u8>)
    -> Result<NativeReportSave, String> {
    check_report_payload(&format, &filename, &bytes)?;
    // Blocking native dialogs must not run on the application's UI thread.
    // Spawn one blocking worker, then report the exact outcome to Deliver.
    tauri::async_runtime::spawn_blocking(move || -> Result<NativeReportSave, String> {
        let dialog = app.dialog().file()
            .set_title("Save PilotODIN report")
            .set_file_name(filename);
        let chosen = if format == "pdf" {
            dialog.add_filter("PDF document", &["pdf"]).blocking_save_file()
        } else {
            dialog.add_filter("HTML document", &["html"]).blocking_save_file()
        };
        let path = match chosen {
            Some(path) => path.into_path()
                .map_err(|_| "The selected Save As location is not a local file".to_string())?,
            None => return Ok(NativeReportSave { status: "cancelled", filename: None }),
        };
        // Even if a user manually edits the extension in the dialog, never
        // write PDF bytes to an .html file, or vice versa.
        if !path.extension().and_then(|ext| ext.to_str())
            .map(|ext| ext.eq_ignore_ascii_case(&format)).unwrap_or(false) {
            return Err("Save As extension differs from the report format".into());
        }
        // Only the OS dialog may choose the destination. Never accept a path
        // from JavaScript. Standard Save As handles overwrite confirmation.
        std::fs::write(&path, &bytes)
            .map_err(|e| format!("Could not save report to the selected location: {e}"))?;
        // Confirm the entire saved content, not only its length. A partial
        // write or a concurrent destination change must never be reported as
        // successfully saved to the user.
        let stored_size = std::fs::metadata(&path)
            .map_err(|e| format!("Could not verify the saved report: {e}"))?.len();
        if stored_size != bytes.len() as u64 {
            return Err("Saved report size verification failed".into());
        }
        let saved_hash = {
            let mut file = File::open(&path)
                .map_err(|e| format!("Could not read the saved report for verification: {e}"))?;
            let mut hasher = Sha256::new();
            let mut buffer = [0u8; 65_536];
            loop {
                let read = file.read(&mut buffer)
                    .map_err(|e| format!("Could not verify saved report contents: {e}"))?;
                if read == 0 { break; }
                hasher.update(&buffer[..read]);
            }
            hasher.finalize()
        };
        let expected_hash = Sha256::digest(&bytes);
        if saved_hash[..] != expected_hash[..] {
            return Err("The saved report failed content verification".into());
        }
        let saved_filename = Path::new(&path).file_name()
            .and_then(|name| name.to_str()).map(str::to_owned);
        Ok(NativeReportSave { status: "saved", filename: saved_filename })
    }).await.map_err(|_| "The native Save As task could not finish".to_string())?
}

#[cfg(test)]
mod report_save_tests {
    use super::{check_report_payload, MAX_REPORT_EXPORT_BYTES};

    #[test]
    fn native_report_writer_accepts_only_matching_report_types() {
        assert!(check_report_payload("pdf", "pilotodin_report.pdf", b"%PDF-1.7\n%%EOF").is_ok());
        assert!(check_report_payload("html", "pilotodin_report.html", b"<!doctype html><html></html>").is_ok());
        assert!(check_report_payload("pdf", "pilotodin_report.html", b"%PDF-1.7").is_err());
        assert!(check_report_payload("html", "pilotodin_report.html", b"%PDF-1.7").is_err());
        assert!(check_report_payload("txt", "report.txt", b"hello").is_err());
        assert!(check_report_payload("pdf", "..\\elsewhere.pdf", b"%PDF-1.7").is_err());
        assert!(check_report_payload("pdf", "report.pdf", b"").is_err());
        assert!(check_report_payload("pdf", "report.html", b"%PDF-1.7").is_err());
        assert!(check_report_payload("pdf", "bad:name.pdf", b"%PDF-1.7").is_err());
        assert!(check_report_payload("html", "bad<name>.html", b"<!doctype html>").is_err());
        assert!(check_report_payload("pdf", "report.pdf", &vec![0u8; MAX_REPORT_EXPORT_BYTES + 1]).is_err());
    }
}


#[cfg(test)]
mod native_close_ticket_tests {
    use super::{consume_native_close_ticket, eligible_p3_w5_qa_exit};

    #[test]
    fn synthetic_w5_finish_is_not_a_general_native_close_bypass() {
        assert!(eligible_p3_w5_qa_exit(
            true, "com.pilotodin.p3qualityw5qa", Some("1"), Some("1")
        ));
        assert!(!eligible_p3_w5_qa_exit(
            false, "com.pilotodin.p3qualityw5qa", Some("1"), Some("1")
        ));
        assert!(!eligible_p3_w5_qa_exit(
            true, "com.pilotodin.studio", Some("1"), Some("1")
        ));
        assert!(!eligible_p3_w5_qa_exit(
            true, "com.pilotodin.p3semanticqa", Some("1"), Some("1")
        ));
        assert!(!eligible_p3_w5_qa_exit(
            true, "com.pilotodin.p3qualityw5qa", None, Some("1")
        ));
        assert!(!eligible_p3_w5_qa_exit(
            true, "com.pilotodin.p3qualityw5qa", Some("1"), None
        ));
    }

    #[test]
    fn only_current_ticket_can_authorize_one_native_close_resolution() {
        let mut pending = Some("current".to_string());
        assert!(!consume_native_close_ticket(&mut pending, "stale"));
        assert_eq!(pending.as_deref(), Some("current"));
        assert!(consume_native_close_ticket(&mut pending, "current"));
        assert!(pending.is_none());
        assert!(!consume_native_close_ticket(&mut pending, "current"));
        assert!(!consume_native_close_ticket(&mut pending, ""));
    }
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(DesktopState::default())
        .manage(NativeCloseState::default())
        .invoke_handler(tauri::generate_handler![
            launch_backend, launch_bundled_ai, save_report_as,
            resolve_native_close_request, confirm_native_close, confirm_native_project_switch,
            finish_p3_w5_synthetic_qa, confirm_native_deliver_exit
        ])
        .on_window_event(|window, event| {
            if window.label() != "main" { return; }
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                // Synchronous veto first. If the frontend has not registered
                // or cannot reply, native close stays blocked, never silent.
                api.prevent_close();
                let state = window.state::<NativeCloseState>();
                let token = {
                    let Ok(mut guard) = state.pending.lock() else {
                        eprintln!("Native close blocked: state unavailable");
                        return;
                    };
                    if guard.is_some() { return; } // Prevent duplicate prompts.
                    let token = uuid::Uuid::new_v4().simple().to_string();
                    *guard = Some(token.clone());
                    token
                };
                if let Err(error) = window.emit(
                    "pilotodin:native-close-requested",
                    NativeCloseRequest { token: token.clone() }
                ) {
                    if let Ok(mut guard) = state.pending.lock() {
                        if guard.as_deref() == Some(token.as_str()) { *guard = None; }
                    }
                    eprintln!("Native close blocked: could not dispatch request: {error}");
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("Could not initialise PilotODIN desktop")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                let state = app.state::<DesktopState>();
                if let Ok(mut ai) = state.inference.lock() {
                    if let Some(worker) = ai.take() {let _ = worker.child.kill();}
                }
                if let Ok(mut backend) = state.backend.lock() {
                    if let Some(worker) = backend.take() {let _ = worker.child.kill();}
                };
            }
        });
}
