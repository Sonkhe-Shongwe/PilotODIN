//! PilotODIN desktop lifecycle supervisor.
//! Python and bundled inference are separate loopback-only, per-session workers.
//! AI has no arbitrary process- or filesystem-execution capability.
use std::borrow::Cow;
use std::fs::File;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::net::TcpListener;
use std::sync::{Arc, Mutex};
use std::sync::atomic::{AtomicBool, AtomicU8, Ordering};
use std::time::{Duration, Instant};
use sha2::{Digest, Sha256};
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, Manager, RunEvent, State};
use tauri::ipc::{InvokeBody, Request};
use tauri_plugin_shell::{process::{CommandChild, CommandEvent}, ShellExt};
use tauri_plugin_dialog::DialogExt;

mod report_file;
mod storage_boundary;
mod desktop_profile;
mod dataset_file;
mod dataset_attestation;
#[cfg(windows)]
mod resource_wire;
#[cfg(windows)]
mod resource_transport;
#[cfg(windows)]
mod resource_shell;
#[cfg(windows)]
mod resource_supervisor;
#[cfg(windows)]
mod resource_desktop;

#[derive(Clone, Serialize)]
struct BackendConnection {
    port: u16,
    token: String,
    // Routing metadata only; never a resource lease or control capability.
    backend_driven_inference: bool,
}

struct ActiveBackend {
    connection: BackendConnection,
    // Separate from the serialized WebView API connection.
    dataset_export_key: String,
    child: Option<CommandChild>,
    exit: Arc<AtomicU8>,
    stop_requested: bool,
    _storage_pins: storage_boundary::DirectoryPins,
    #[cfg(windows)]
    owned: Option<Arc<resource_desktop::OwnedSession>>,
}

struct InferenceSettings {
    port: u16,
    token: String,
}

struct ActiveInference {
    child: Option<CommandChild>,
    exit: Arc<AtomicU8>,
    _storage_pins: storage_boundary::DirectoryPins,
    _model: VerifiedModel,
}

// A generation is retained until the actual blocking startup task has joined.
// The caller's dropped IPC future is not cancellation or completion evidence.
struct InferenceStartup {
    backend_token: String,
    cancelled: Arc<AtomicBool>,
    joined: AtomicBool,
    uncertain: AtomicBool,
}

impl InferenceStartup {
    fn new(backend_token: String) -> Self {
        Self { backend_token, cancelled: Arc::new(AtomicBool::new(false)),
            joined: AtomicBool::new(false), uncertain: AtomicBool::new(false) }
    }

    fn check(&self, stopping: &AtomicBool) -> Result<(), String> {
        if self.cancelled.load(Ordering::Acquire) || stopping.load(Ordering::Acquire) {
            Err("Local inference startup cancelled".into())
        } else { Ok(()) }
    }
}

const INFERENCE_IDLE_SLEEP_SECONDS: &str = "30";

#[derive(Default)]
struct DesktopState {
    profile_verified: AtomicBool,
    dataset_save_busy: AtomicBool,
    stopping: AtomicBool,
    #[cfg(windows)]
    owned_engine_uncertain: AtomicBool,
    launch_gate: Mutex<()>,
    backend: Mutex<Option<ActiveBackend>>,
    inference: Mutex<Option<ActiveInference>>,
    inference_startup: Mutex<Option<Arc<InferenceStartup>>>,
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
async fn resolve_native_close_request(
    window: tauri::WebviewWindow,
    state: State<'_, NativeCloseState>,
    token: String,
    approve: bool,
) -> Result<(), String> {
    if window.label() != "main" { return Err("Unexpected desktop window".into()); }
    {
        let mut pending = state.pending.lock()
            .map_err(|_| "Native close state unavailable".to_string())?;
        if !consume_native_close_ticket(&mut pending, &token) {
            return Err("Native close request expired or was not issued".into());
        }
    }
    if approve {
        let app = window.app_handle().clone();
        tauri::async_runtime::spawn_blocking(move || stop_owned_workers(&app))
            .await.map_err(|_| "Desktop shutdown task did not finish".to_string())??;
        // close() would re-enter CloseRequested and loop. destroy() is only
        // reachable with a one-use ticket issued by an actual OS close event.
        window.destroy().map_err(|e| format!("Could not close window: {e}"))?;
    }
    Ok(())
}

// This command acknowledges QA listener registration *only* after disposing
// the extra hidden lifecycle peer created by the isolated QA build. The peer
// has no project content; the real main CloseRequested ticket is untouched.
// This command cannot approve/close the main window or expose owner data.
fn eligible_n12_no_cdp_listener_ack(debug: bool, page_url: &str, consent: Option<&str>) -> bool {
    debug && consent == Some("I_APPROVE_ONE_N12_NO_CDP_STORAGE")
        && page_url.split('#').next() == Some("http://127.0.0.1:5173/")
}

#[tauri::command]
fn acknowledge_n12_no_cdp_close_listener_ready(window: tauri::WebviewWindow) -> Result<(), String> {
    if window.label() != "main" { return Err("Unexpected desktop window".into()); }
    let page_url = window.url()
        .map_err(|_| "N12 no-CDP readiness URL unavailable".to_string())?;
    let consent = std::env::var("PILOTODIN_N12_NO_CDP_STORAGE_CONSENT").ok();
    if !eligible_n12_no_cdp_listener_ack(cfg!(debug_assertions), page_url.as_str(), consent.as_deref()) {
        return Err("N12 no-CDP readiness not authorized".into());
    }
    // In the exact isolated QA overlay there is one extra hidden "n12peer"
    // window. The CDP driver used to close it before the main OS-close test.
    // No-CDP mode has no browser driver, so close only this empty synthetic
    // peer through its ordinary Tauri close request. The host's on_window_event
    // veto applies to "main" only; never destroy or close that window here.
    let peer = window.app_handle().get_webview_window("n12peer")
        .ok_or_else(|| "N12 QA synthetic peer missing".to_string())?;
    peer.close().map_err(|_| "N12 QA synthetic peer close refused".to_string())?;
    // Fixed literal: no paths, tokens, PIDs, browser flags or project content.
    // The later OS window close and full process exit are separately checked.
    eprintln!("N12 QA native close listener registered");
    Ok(())
}

// QA-only deterministic exit for the *specific* native W5 dev page.
// The original environment/identifier checks could disagree with Tauri dev
// configuration merging. The loaded WebView URL is a stronger, independently
// observable QA-scope boundary: a debug build serving only this exact page
// on the one-use loopback test port. This command is inaccessible to normal
// 5173 development and production tauri:// or https:// application windows.
fn eligible_p3_w5_qa_exit(debug: bool, page_url: &str) -> bool {
    if !debug { return false; }
    let without_fragment = page_url.split('#').next().unwrap_or_default();
    without_fragment == "http://127.0.0.1:5178/p3_native_quality_w5_qa.html"
}

#[tauri::command]
fn finish_p3_w5_synthetic_qa(window: tauri::WebviewWindow) -> Result<(), String> {
    if window.label() != "main" { return Err("Unexpected desktop window".into()); }
    let page_url = window.url()
        .map_err(|_| "W5 QA finish refused: cannot determine WebView page origin".to_string())?;
    if !eligible_p3_w5_qa_exit(cfg!(debug_assertions), page_url.as_str()) {
        let reason = if !cfg!(debug_assertions) {
            "W5 QA finish refused: this is not a debug build"
        } else {
            "W5 QA finish refused: not the exact isolated W5 local page"
        };
        // Never emit raw URL, environment, source path, tokens or data here.
        eprintln!("[PilotODIN W5 QA] {reason}");
        return Err(reason.into());
    }
    // A synchronous destroy can discard the WebView before Tauri's invoke
    // response reaches JS. A rejected invoke with no Error/string then looks
    // like a QA failure despite the reviewed version being valid. Acknowledge
    // the command first; close only this already scope-checked QA window from
    // the UI thread, after a short bounded interval. Production CloseRequested
    // and unsaved-work veto remain entirely unchanged.
    let app = window.app_handle().clone();
    let qa_window = window.clone();
    std::thread::spawn(move || {
        std::thread::sleep(std::time::Duration::from_millis(350));
        if app.run_on_main_thread(move || {
            if qa_window.destroy().is_err() {
                eprintln!("[PilotODIN W5 QA] delayed native window destroy failed");
            }
        }).is_err() {
            eprintln!("[PilotODIN W5 QA] delayed native window dispatch failed");
        }
    });
    Ok(())
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

// Keep both worker families in the same identifier-scoped app-local data
// home. Admit each component before creating descendants; preserve the
// existing layout and the R03 baseline/candidate isolation contract.
fn worker_data_home(app: &AppHandle, pins: &mut storage_boundary::DirectoryPins) -> Result<PathBuf, String> {
    let app_root = app.path().app_local_data_dir()
        .map_err(|_| "App-local storage unavailable".to_string())?;
    let profile = if app.config().identifier == "com.pilotodin.p4r03benchmark" {
        match std::env::var("PILOTODIN_R03_BENCHMARK").unwrap_or_default().as_str() {
            "baseline" => Some("baseline"),
            "candidate" => Some("candidate"),
            _ => return Err("Select a valid R03 QA benchmark profile".into()),
        }
    } else {
        None
    };
    let root = pins.prepare(&app_root)?;
    let home = pins.prepare(&root.join("data"))?;
    match profile {
        Some(profile) => pins.prepare(&home.join(profile)),
        None => Ok(home),
    }
}

// Prepare only named owned scratch, before either child is spawned. No
// application-wide environment changes and no canonical verbatim path
// handed to the Python workspace admission contract.
fn worker_temp_directory(home: &Path, name: &str, pins: &mut storage_boundary::DirectoryPins) -> Result<PathBuf, String> {
    pins.prepare_worker_temp(home, name)
}

// Verify the actual production environment rather than repeating the requested
// Tauri path. The COM query runs on the WebView UI thread; waiting does not.
async fn verify_effective_desktop_profile(window: &tauri::WebviewWindow) -> Result<(), String> {
    if window.label() != "main" { return Err("Unexpected desktop window".into()); }
    let app = window.app_handle();
    if app.config().identifier != "com.pilotodin.studio" { return Ok(()); }
    let state = app.state::<DesktopState>();
    state.profile_verified.store(false, Ordering::Release);
    let root = app.path().app_local_data_dir()
        .map_err(|_| "Desktop profile path unavailable".to_string())?;
    app.state::<desktop_profile::DesktopProfileLease>().verify_root(&root)?;
    #[cfg(windows)]
    {
        use webview2_com::Microsoft::Web::WebView2::Win32::ICoreWebView2Environment7;
        use windows_core::{Interface, PWSTR};
        let (tx, rx) = std::sync::mpsc::sync_channel(1);
        window.with_webview(move |webview| {
            let observed = (|| -> Result<(), String> {
                let environment = webview.environment().cast::<ICoreWebView2Environment7>()
                    .map_err(|_| "Effective WebView2 profile interface unavailable".to_string())?;
                let mut value = PWSTR::null();
                let outcome = unsafe { environment.UserDataFolder(&mut value) };
                // The COM allocator's returned buffer must be freed on every path.
                let folder = if value.is_null() { None } else {
                    Some(webview2_com::take_pwstr(value))
                };
                outcome.map_err(|_| "Effective WebView2 profile unavailable".to_string())?;
                let folder = folder.ok_or("Effective WebView2 profile unavailable")?;
                desktop_profile::verify_effective_directory(&root, Path::new(&folder))
            })();
            let _ = tx.send(observed);
        }).map_err(|_| "WebView2 profile observation could not be scheduled".to_string())?;
        tauri::async_runtime::spawn_blocking(move || {
            rx.recv_timeout(Duration::from_secs(5))
                .map_err(|_| "Effective WebView2 profile verification timed out".to_string())?
        }).await.map_err(|_| "Profile verification task did not finish".to_string())??;
        state.profile_verified.store(true, Ordering::Release);
        Ok(())
    }
    #[cfg(not(windows))]
    {
        let _ = root;
        Err("Production desktop profile verification requires Windows".into())
    }
}

fn ensure_desktop_admission(app: &AppHandle, state: &DesktopState) -> Result<(), String> {
    if state.stopping.load(Ordering::Acquire) {
        return Err("Desktop is shutting down; no new work can start".into());
    }
    if app.config().identifier == "com.pilotodin.studio"
        && !state.profile_verified.load(Ordering::Acquire) {
        return Err("Desktop browser profile has not been verified".into());
    }
    Ok(())
}

// Windows uses the already-owned job and non-waiting kill-on-drop.
// Preserve the previous explicit child/group cleanup on other platforms;
// the bounded normal shutdown contract is for our Windows desktop.
fn terminate_owned_child(child: Option<CommandChild>) {
    if let Some(child) = child {
        #[cfg(windows)]
        drop(child);
        #[cfg(not(windows))]
        if let Err(error) = child.kill() {
            eprintln!("Owned worker cleanup failed: {error}");
        }
    }
}

// 0 = no termination witness, 1 = normal zero exit, 2 = other exit.
// Missing child handles are not exit evidence.
fn wait_for_worker(exit: &AtomicU8, timeout: Duration) -> u8 {
    let deadline = Instant::now() + timeout;
    loop {
        let status = exit.load(Ordering::Acquire);
        if status != 0 || Instant::now() >= deadline { return status; }
        std::thread::sleep(Duration::from_millis(25));
    }
}

fn stop_owned_workers(app: &AppHandle) -> Result<(), String> {
    let state = app.state::<DesktopState>();
    state.stopping.store(true, Ordering::Release);
    // Do not certify graceful exit while a consented dataset save is active.
    // Setting stopping first blocks its final admission if still in the dialog.
    // A publication already admitted must finish before retrying close.
    if state.dataset_save_busy.load(Ordering::Acquire) {
        return Err("Dataset Save As is still active; finish or cancel it, then retry close".into());
    }
    #[cfg(windows)]
    if resource_desktop::selected(app) {
        // Preserve the legacy bounded gate path when the new mode is off.
        // Serialize against backend installation, then release all locks
        // before waiting for the exact timer join.
        let deadline = Instant::now() + Duration::from_secs(5);
        let owned = {
            let _launch = loop {
                match state.launch_gate.try_lock() {
                    Ok(guard) => break guard,
                    Err(std::sync::TryLockError::WouldBlock) if Instant::now() < deadline =>
                        std::thread::sleep(Duration::from_millis(25)),
                    _ => return Err("Owned worker launch is not finished; retry close".into()),
                }
            };
            if state.owned_engine_uncertain.load(Ordering::Acquire) {
                return Err("Owned engine launch outcome unconfirmed; shutdown blocked".into());
            }
            let backend = state.backend.lock().map_err(|_| "Engine state unavailable")?;
            match backend.as_ref() {
                Some(worker) => Some(worker.owned.clone().ok_or("Owned session identity unavailable")?),
                None => None,
            }
        };
        return match owned {
            Some(owner) => owner.stop_and_join(),
            None => Ok(()), // launch gate held above: no spawn entered or retained
        };
    }
    let deadline = Instant::now() + Duration::from_secs(5);
    let _launch = loop {
        match state.launch_gate.try_lock() {
            Ok(guard) => {
                // Stop was published before this gate. No new startup can be
                // installed after we release it for the actual join wait.
                let pending = state.inference_startup.lock()
                    .map_err(|_| "AI startup state unavailable")?.clone();
                if let Some(attempt) = pending {
                    attempt.cancelled.store(true, Ordering::Release);
                    drop(guard);
                    while !attempt.joined.load(Ordering::Acquire) && Instant::now() < deadline {
                        std::thread::sleep(Duration::from_millis(25));
                    }
                    if !attempt.joined.load(Ordering::Acquire)
                        || attempt.uncertain.load(Ordering::Acquire) {
                        return Err("Local inference startup exit is not confirmed; retry close".into());
                    }
                    // The supervisor clears the matching slot after joining.
                    // Do not wait for it with the launch gate held.
                    if Instant::now() >= deadline {
                        return Err("Local inference startup settlement is pending; retry close".into());
                    }
                    std::thread::sleep(Duration::from_millis(10));
                    continue;
                }
                break guard;
            },
            Err(std::sync::TryLockError::WouldBlock) if Instant::now() < deadline =>
                std::thread::sleep(Duration::from_millis(25)),
            _ => return Err("Worker launch is not finished; retry close".into()),
        }
    };
    let mut interrupted = false;
    {
        let mut active = state.backend.lock().map_err(|_| "Engine state unavailable")?;
        if let Some(worker) = active.as_mut() {
            if worker.exit.load(Ordering::Acquire) == 0 && !worker.stop_requested {
                worker.stop_requested = true;
                if let Some(child) = worker.child.as_mut() {
                    if child.write(b"PILOTODIN_STOP\n").is_err() {
                        eprintln!("Analytical engine shutdown request failed");
                    }
                }
            }
            let mut status = wait_for_worker(&worker.exit, Duration::from_secs(12));
            if status == 0 {
                // Windows owned job group kill-on-drop is non-waiting.
                // Keep the termination witness even after the handle is dropped.
                terminate_owned_child(worker.child.take());
                interrupted = true;
                status = wait_for_worker(&worker.exit, Duration::from_secs(4));
            }
            if status == 0 {
                return Err("Analytical engine exit is not confirmed; retry close".into());
            }
            if status != 1 { interrupted = true; }
        }
        *active = None;
    }
    {
        let mut active = state.inference.lock().map_err(|_| "AI state unavailable")?;
        if let Some(worker) = active.as_mut() {
            // There is no reviewed inference shutdown endpoint. Terminate
            // only the owned group once analytical work has drained.
            terminate_owned_child(worker.child.take());
            if wait_for_worker(&worker.exit, Duration::from_secs(4)) == 0 {
                return Err("Local inference exit is not confirmed; retry close".into());
            }
        }
        *active = None;
    }
    *state.inference_settings.lock().map_err(|_| "AI state unavailable")? = None;
    if interrupted {
        return Err("Analytical engine was interrupted during shutdown. Retry close to finish exiting.".into());
    }
    Ok(())
}

#[tauri::command]
async fn launch_backend(window: tauri::WebviewWindow, app: AppHandle, state: State<'_, DesktopState>) -> Result<BackendConnection, String> {
    verify_effective_desktop_profile(&window).await?;
    let _launch = state.launch_gate.lock().map_err(|_| "Worker launch unavailable")?;
    ensure_desktop_admission(&app, &state)?;
    let mut guard = state.backend.lock().map_err(|_| "Engine state unavailable".to_string())?;
    if let Some(existing) = guard.as_ref() {
        #[cfg(windows)]
        if let Some(owner) = &existing.owned {
            owner.check_available()?;
        }
        return Ok(existing.connection.clone());
    }
    let port = free_loopback_port()?;
    let inference_port = free_loopback_port()?;
    if port == inference_port {return Err("Port reservation collision".into());}
    let token = new_token();
    let inference_token = new_token();
    let dataset_export_key = new_token();
    let mut storage_pins = storage_boundary::DirectoryPins::default();
    let data_dir = worker_data_home(&app, &mut storage_pins)?;
    let worker_temp = worker_temp_directory(&data_dir, "backend-temp", &mut storage_pins)?;

    // Supplying a dedicated port and key does not start or load a model.
    // Only a deliberate local AI request invokes launch_bundled_ai.
    let command = app.shell().sidecar("pilotodin-engine")
        .map_err(|e| format!("Bundled analytical engine missing: {e}"))?
        .env("PILOTODIN_HOME", data_dir.to_string_lossy().to_string())
        .env("TEMP", worker_temp.as_os_str())
        .env("TMP", worker_temp.as_os_str())
        .env("TMPDIR", worker_temp.as_os_str())
        .env("PILOTODIN_DESKTOP_PORT", port.to_string())
        .env("PILOTODIN_DESKTOP_SESSION", token.as_str())
        .env("PILOTODIN_DATASET_EXPORT_KEY", dataset_export_key.as_str())
        .env("PILOTODIN_DESKTOP_WATCH_STDIN", "1")
        .env("PILOTODIN_CONTROL_MODE", "legacy")
        .env("PILOTODIN_BUNDLED_LLM_PORT", inference_port.to_string())
        .env("PILOTODIN_BUNDLED_LLM_TOKEN", inference_token.as_str())
        .env("PILOTODIN_DESKTOP_ALLOW_DEV", if cfg!(debug_assertions) { "1" } else { "0" })
        // The sidecar owns only user storage. Do not inherit the desktop's
        // installation or source-checkout working directory: relative cache
        // writes must land under the created application data directory.
        .current_dir(&data_dir)
        .set_process_group(true)
        .kill_on_drop(cfg!(windows));
    storage_pins.verify()?;
    #[cfg(windows)]
    if resource_desktop::selected(&app) {
        // Source registration is deliberately inactive until the coherent
        // runner/frontend and resource/consent compatibility switch.
        let generation = uuid::Uuid::new_v4().simple().to_string();
        let capability = new_token();
        let wire = resource_wire::Wire::new(generation.clone(), capability.clone())
            .map_err(str::to_owned)?;
        let (events, child) = match command
            .env("PILOTODIN_CONTROL_MODE", "pod1")
            .env("PILOTODIN_CONTROL_GENERATION", generation.as_str())
            .env("PILOTODIN_CONTROL_CAPABILITY", capability.as_str())
            .set_raw_out(true).spawn() {
                Ok(value) => value,
                Err(_) => {
                    // Spawn may have created an unobserved process group.
                    state.owned_engine_uncertain.store(true, Ordering::Release);
                    state.stopping.store(true, Ordering::Release);
                    return Err("Owned engine launch outcome unconfirmed".into());
                },
            };
        let connection = BackendConnection { port, token: token.clone(), backend_driven_inference: true };
        let exit = Arc::new(AtomicU8::new(0));
        let owner = Arc::new(resource_desktop::OwnedSession::new(
            app.clone(), wire, events, child, token.clone(), inference_port, inference_token));
        // Install ownership before scheduling the independent timer. A
        // failed timer creation does not clear the installed owner.
        *guard = Some(ActiveBackend { connection: connection.clone(), dataset_export_key,
            child: None, exit, stop_requested: false, _storage_pins: storage_pins,
            owned: Some(owner.clone()) });
        drop(guard);
        if let Err(error) = owner.start_timer(app.clone()) {
            state.stopping.store(true, Ordering::Release);
            return Err(error);
        }
        return Ok(connection);
    }
    let (mut events, child) = command.spawn()
        .map_err(|e| format!("Could not start analytical engine: {e}"))?;
    let connection = BackendConnection { port, token: token.clone(), backend_driven_inference: false };
    let exit = Arc::new(AtomicU8::new(0));
    *guard = Some(ActiveBackend { connection: connection.clone(), dataset_export_key, child: Some(child),
        exit: exit.clone(), stop_requested: false, _storage_pins: storage_pins,
        #[cfg(windows)]
        owned: None });
    *state.inference_settings.lock().map_err(|_| "AI state unavailable".to_string())? =
        Some(InferenceSettings { port: inference_port, token: inference_token });
    drop(guard);

    let owner = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = events.recv().await {
            match event {
                CommandEvent::Terminated(payload) => {
                    exit.store(if payload.code == Some(0) { 1 } else { 2 }, Ordering::Release);
                    let state = owner.state::<DesktopState>();
                    if let Ok(mut active) = state.backend.lock() {
                        if !state.stopping.load(Ordering::Acquire)
                            && active.as_ref().map(|b| b.connection.token == token).unwrap_or(false) {
                            // An unexpected engine exit invalidates the
                            // whole session, not just a cached connection.
                            state.stopping.store(true, Ordering::Release);
                            if let Ok(pending) = state.inference_startup.lock() {
                                if let Some(attempt) = pending.as_ref() {
                                    attempt.cancelled.store(true, Ordering::Release);
                                }
                            }
                            // Retain backend and inference ownership for
                            // explicit shutdown; do not start a replacement.
                            if let Ok(mut ai) = state.inference.lock() {
                                if let Some(worker) = ai.as_mut() { terminate_owned_child(worker.child.take()); }
                            }
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

struct VerifiedModel {
    path: PathBuf,
    file: File,
    size: u64,
    modified: std::time::SystemTime,
    pins: storage_boundary::DirectoryPins,
}

impl VerifiedModel {
    fn verify(&self) -> Result<(), String> {
        self.pins.verify()?;
        let held = self.file.metadata().map_err(|_| "Bundled model identity unavailable")?;
        let named = std::fs::symlink_metadata(&self.path)
            .map_err(|_| "Bundled model identity unavailable")?;
        if !held.is_file() || !named.is_file() || named.file_type().is_symlink()
            || held.len() != self.size || named.len() != self.size
            || held.modified().ok() != Some(self.modified)
            || named.modified().ok() != Some(self.modified) {
            return Err("Bundled model changed during verification".into());
        }
        #[cfg(windows)]
        {
            use std::os::windows::fs::MetadataExt;
            if held.file_attributes() & 0x400 != 0 || named.file_attributes() & 0x400 != 0 {
                return Err("Bundled model redirected".into());
            }
        }
        Ok(())
    }
}

fn verify_bundled_model(app: &AppHandle, attempt: &InferenceStartup,
                        stopping: &AtomicBool) -> Result<VerifiedModel, String> {
    attempt.check(stopping)?;
    let resources = app.path().resource_dir().map_err(|_| "Bundled resources unavailable")?;
    let directory = resources.join("models");
    let mut pins = storage_boundary::DirectoryPins::default();
    pins.admit_existing(&directory)?;
    let manifest_file = directory.join("model-manifest.json");
    let mut manifest_bytes = Vec::new();
    File::open(&manifest_file).map_err(|_| "Bundled AI manifest missing")?
        .take(65_537).read_to_end(&mut manifest_bytes)
        .map_err(|_| "Bundled AI manifest unreadable")?;
    if manifest_bytes.len() > 65_536 { return Err("Bundled AI manifest too large".into()); }
    let manifest: ModelManifest = serde_json::from_slice(&manifest_bytes)
        .map_err(|_| "Invalid bundled AI manifest")?;
    if manifest.model_file != "qwen3-1.7b-q4_k_m.gguf" || manifest.model_sha256.len() != 64 ||
       !manifest.model_sha256.bytes().all(|c| c.is_ascii_hexdigit()) {
        return Err("Invalid bundled model identity".into());
    }
    let model = directory.join(&manifest.model_file);
    let mut options = std::fs::OpenOptions::new();
    options.read(true);
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        // Hold read-only sharing through worker cleanup; refuse normal write
        // or deletion/rename while the exact verified file is resident.
        options.share_mode(1).custom_flags(0x00200000);
    }
    let mut reader = options.open(&model).map_err(|_| "Bundled offline model missing")?;
    let metadata = reader.metadata().map_err(|_| "Bundled model identity unavailable")?;
    let size = metadata.len();
    let modified = metadata.modified().map_err(|_| "Bundled model timestamp unavailable")?;
    if !metadata.is_file() || size == 0 { return Err("Invalid bundled model file".into()); }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        if metadata.file_attributes() & 0x400 != 0 { return Err("Bundled model redirected".into()); }
    }
    let mut hash = Sha256::new();
    let mut chunk = vec![0u8; 1024 * 1024];
    let mut observed = 0u64;
    loop {
        attempt.check(stopping)?;
        let count = reader.read(&mut chunk).map_err(|_| "Could not verify local AI model")?;
        if count == 0 { break; }
        observed = observed.checked_add(count as u64).ok_or("Bundled model size invalid")?;
        if observed > size { return Err("Bundled model grew during verification".into()); }
        hash.update(&chunk[..count]);
    }
    let computed = format!("{:x}", hash.finalize());
    if observed != size || !computed.eq_ignore_ascii_case(&manifest.model_sha256) {
        return Err("Bundled local model failed integrity verification".into());
    }
    let verified = VerifiedModel { path: model, file: reader, size, modified, pins };
    verified.verify()?;
    attempt.check(stopping)?;
    Ok(verified)
}

#[tauri::command]
async fn launch_bundled_ai(window: tauri::WebviewWindow, app: AppHandle,
                           state: State<'_, DesktopState>) -> Result<(), String> {
    if window.label() != "main" { return Err("Unexpected desktop window".into()); }
    #[cfg(windows)]
    if resource_desktop::selected(&app) {
        return Err("Local inference is admitted only by the analytical engine".into());
    }
    let attempt = {
        let _launch = state.launch_gate.lock().map_err(|_| "Worker launch unavailable")?;
        ensure_desktop_admission(&app, &state)?;
        let backend_token = {
            let backend = state.backend.lock().map_err(|_| "Engine state unavailable")?;
            let current = backend.as_ref().ok_or("Start analytics before AI")?;
            if current.exit.load(Ordering::Acquire) != 0 {
                return Err("Analytical engine exit detected".into());
            }
            current.connection.token.clone()
        };
        let mut startup = state.inference_startup.lock().map_err(|_| "AI startup state unavailable")?;
        if startup.is_some() { return Err("Local inference startup in progress".into()); }
        let active = state.inference.lock().map_err(|_| "AI state unavailable")?;
        if let Some(worker) = active.as_ref() {
            return if worker.exit.load(Ordering::Acquire) == 0 && worker.child.is_some() { Ok(()) }
                else { Err("Previous inference worker exit requires session cleanup".into()) };
        }
        let attempt = Arc::new(InferenceStartup::new(backend_token));
        *startup = Some(attempt.clone());
        attempt
    };
    // An independent supervisor owns the join. Dropping this IPC invocation
    // only drops the one-result receiver, never the blocking startup.
    let (tx, mut rx) = tauri::async_runtime::channel(1);
    let owner = app.clone();
    tauri::async_runtime::spawn(async move {
        let work_app = owner.clone();
        let work_attempt = attempt.clone();
        let result = match tauri::async_runtime::spawn_blocking(move ||
            start_owned_inference(work_app, work_attempt)).await {
            Ok(result) => result,
            Err(_) => {
                attempt.uncertain.store(true, Ordering::Release);
                Err("Local inference startup outcome unconfirmed".into())
            }
        };
        attempt.joined.store(true, Ordering::Release);
        {
            let state = owner.state::<DesktopState>();
            if !attempt.uncertain.load(Ordering::Acquire) {
                if let Ok(mut slot) = state.inference_startup.lock() {
                    if slot.as_ref().is_some_and(|current| Arc::ptr_eq(current,&attempt)) {
                        *slot = None;
                    }
                }
            } else {
                state.stopping.store(true, Ordering::Release);
            }
        }
        let _ = tx.send(result).await;
    });
    rx.recv().await.ok_or_else(|| "Local inference startup supervisor unavailable".to_string())?
}

fn start_owned_inference(app: AppHandle, attempt: Arc<InferenceStartup>) -> Result<(), String> {
    let state = app.state::<DesktopState>();
    attempt.check(&state.stopping)?;
    // Copy immutable launch settings. No state lock across hash or filesystem
    // preparation, no launch gate held during model integrity verification.
    let (token, port) = {
        let guard = state.inference_settings.lock().map_err(|_| "AI configuration unavailable")?;
        let settings = guard.as_ref().ok_or("Start analytics before AI")?;
        (settings.token.clone(), settings.port)
    };
    let model = verify_bundled_model(&app, &attempt, &state.stopping)?;
    let mut storage_pins = storage_boundary::DirectoryPins::default();
    let data_dir = worker_data_home(&app, &mut storage_pins)?;
    let worker_temp = worker_temp_directory(&data_dir, "inference-temp", &mut storage_pins)?;
    let resources = app.path().resource_dir().map_err(|e| e.to_string())?;
    let runtime_dlls = resources.join("llama-runtime");
    let old_path = std::env::var_os("PATH").unwrap_or_default();
    let mut paths = vec![runtime_dlls.clone()];
    paths.extend(std::env::split_paths(&old_path));
    let runtime_path = std::env::join_paths(paths).map_err(|_| "Invalid inference runtime path".to_string())?;
    let command = app.shell().sidecar("pilotodin-inference")
        .map_err(|_| "Bundled inference executable missing".to_string())?
        .args(["--model", model.path.to_str().ok_or("Invalid model path")?,
               "--alias", "pilotodin-qwen3-1.7b", "--host", "127.0.0.1",
               "--port", &port.to_string(), "--ctx-size", "2048",
               "--threads", "2", "--parallel", "1", "--gpu-layers", "0",
               "--sleep-idle-seconds", INFERENCE_IDLE_SLEEP_SECONDS,
               "--no-webui", "--no-agent"])
        .env("LLAMA_API_KEY", token.as_str())
        .env("PATH", runtime_path)
        .env("TEMP", worker_temp.as_os_str())
        .env("TMP", worker_temp.as_os_str())
        .env("TMPDIR", worker_temp.as_os_str())
        // ggml_backend_load_all scans the executable directory and current
        // working directory, not PATH, for version-specific CPU backends.
        // Keep the runtime DLL directory as the process working directory.
        .current_dir(&runtime_dlls)
        .set_process_group(true)
        .kill_on_drop(cfg!(windows));
    storage_pins.verify()?;
    model.verify()?;
    // Final admission is serialized with shutdown and engine replacement.
    // No hashing, long wait or async await occurs under this gate.
    let _launch = state.launch_gate.lock().map_err(|_| "Worker launch unavailable")?;
    ensure_desktop_admission(&app, &state)?;
    attempt.check(&state.stopping)?;
    {
        let backend = state.backend.lock().map_err(|_| "Engine state unavailable")?;
        let current = backend.as_ref().ok_or("Start analytics before AI")?;
        if current.connection.token != attempt.backend_token
            || current.exit.load(Ordering::Acquire) != 0 {
            return Err("Analytical engine changed during AI startup".into());
        }
    }
    {
        let current = state.inference_settings.lock().map_err(|_| "AI configuration unavailable")?;
        if !current.as_ref().is_some_and(|s| s.port == port && s.token == token) {
            return Err("Local inference configuration changed".into());
        }
    }
    {
        let current = state.inference_startup.lock().map_err(|_| "AI startup state unavailable")?;
        if !current.as_ref().is_some_and(|s| Arc::ptr_eq(s, &attempt)) {
            return Err("Local inference startup generation changed".into());
        }
    }
    let mut active = state.inference.lock().map_err(|_| "AI state unavailable")?;
    if active.is_some() { return Err("Previous inference worker remains owned".into()); }
    attempt.check(&state.stopping)?;
    let (mut events, child) = match command.spawn() {
        Ok(value) => value,
        Err(_) => {
            // The locked shell can fail after creating a child. A failed
            // return is not conclusive evidence that no group exists.
            attempt.uncertain.store(true, Ordering::Release);
            state.stopping.store(true, Ordering::Release);
            return Err("Local inference launch outcome unconfirmed".into());
        }
    };
    let exit = Arc::new(AtomicU8::new(0));
    *active = Some(ActiveInference { child: Some(child), exit: exit.clone(),
        _storage_pins: storage_pins, _model: model });
    drop(active);
    // The owned event task retains the leader witness. Never discard the
    // exact child/group just because its leader terminated.
    tauri::async_runtime::spawn(async move {
        while let Some(event) = events.recv().await {
            match event {
                CommandEvent::Terminated(payload) => {
                    exit.store(if payload.code == Some(0) { 1 } else { 2 }, Ordering::Release);
                    break;
                }
                CommandEvent::Error(_) => eprintln!("Local AI worker event unavailable"),
                _ => {}
            }
        }
    });
    Ok(())
}


const MAX_REPORT_EXPORT_BYTES: usize = 12 * 1024 * 1024;
const MAX_REPORT_FILENAME_BYTES: usize = 180;

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
    if filename.is_empty() || filename.len() > MAX_REPORT_FILENAME_BYTES ||
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

fn report_save_headers(headers: &tauri::http::HeaderMap) -> Result<(&str, Cow<'_, str>), String> {
    let format = headers.get("x-pilotodin-report-format")
        .and_then(|value| value.to_str().ok())
        .ok_or("Missing or invalid report format header")?;
    let encoded_name = headers.get("x-pilotodin-report-filename")
        .and_then(|value| value.to_str().ok())
        .filter(|value| value.len() <= 3 * MAX_REPORT_FILENAME_BYTES)
        .ok_or("Missing or invalid report filename header")?;
    let filename = percent_encoding::percent_decode_str(encoded_name).decode_utf8()
        .map_err(|_| "Invalid report filename encoding")?;
    Ok((format, filename))
}

fn report_save_bytes(body: &InvokeBody) -> Result<Cow<'_, [u8]>, String> {
    match body {
        InvokeBody::Raw(bytes) => Ok(Cow::Borrowed(bytes)),
        // Tauri's postMessage fallback serializes a binary argument as an array.
        InvokeBody::Json(serde_json::Value::Array(values)) => {
            if values.is_empty() || values.len() > MAX_REPORT_EXPORT_BYTES {
                return Err("The report export is empty or exceeds the safe desktop size limit".into());
            }
            let bytes: Result<Vec<u8>, _> = values.iter().map(|value| {
                value.as_u64().and_then(|byte| u8::try_from(byte).ok())
                    .ok_or("Report payload must contain only bytes")
            }).collect();
            Ok(Cow::Owned(bytes?))
        }
        InvokeBody::Json(_) => Err("Report payload must contain bytes".into()),
    }
}

// Dataset Save As is separate from report publication and never accepts
// a destination path from IPC. The guard covers consent and publication.
struct DatasetSaveLease(AppHandle);
impl Drop for DatasetSaveLease {
    fn drop(&mut self) {
        self.0.state::<DesktopState>().dataset_save_busy.store(false, Ordering::Release);
    }
}

fn current_dataset_export_key(app: &AppHandle) -> Result<String,String> {
    let state=app.state::<DesktopState>();
    ensure_desktop_admission(app,&state)?;
    let backend=state.backend.lock().map_err(|_| "Engine state unavailable")?;
    let active=backend.as_ref().filter(|b| !b.stop_requested && b.exit.load(Ordering::Acquire)==0)
        .ok_or("Active analytical engine required for dataset Save As")?;
    #[cfg(windows)]
    if active.owned.is_some() {
        // Native binary-save admission is not yet wired to the shared lane.
        return Err("Owned resource admission for dataset Save As is unavailable".into());
    }
    active._storage_pins.verify()?;
    Ok(active.dataset_export_key.clone())
}

fn dataset_destination_roots(app:&AppHandle)->Result<(Vec<PathBuf>,Vec<PathBuf>),String>{
    let paths=app.path();
    let home=paths.home_dir().map_err(|_| "Home directory unavailable")?;
    storage_boundary::validate_existing_directory(&home)?;
    let mut allowed=Vec::new();
    // Reject relocated known folders rather than granting new permissions.
    // Missing or redirected standard local home children are not admitted.
    for (root,name) in [(paths.document_dir(),"Documents"),(paths.download_dir(),"Downloads"),
                        (paths.desktop_dir(),"Desktop")] {
        if let Ok(root)=root {
            let standard=home.join(name);
            if storage_boundary::validate_existing_directory(&root).is_ok()
                && storage_boundary::validate_existing_directory(&standard).is_ok()
                && root.canonicalize().ok().zip(standard.canonicalize().ok())
                    .is_some_and(|(a,b)|a==b) {
                allowed.push(root);
            }
        }
    }
    if allowed.is_empty() {return Err("No standard local Documents, Downloads or Desktop directory is available".into());}
    let mut protected=Vec::new();
    // Explicitly protect the running executable directory as well as resources.
    // The resource resolver is not a substitute for the executable location.
    let executable=std::env::current_exe().map_err(|_|"Executable location unavailable")?;
    let executable_parent=executable.parent().ok_or("Executable directory unavailable")?.to_path_buf();
    storage_boundary::validate_existing_directory(&executable_parent)?;
    protected.push(executable_parent);
    // Protect app-data bases, config overrides, cache/logs and packaged
    // resources. An absent protected root protects its existing parent;
    // admission never creates a directory.
    for root in [paths.local_data_dir(),paths.data_dir(),paths.config_dir(),
                 paths.app_local_data_dir(),paths.app_data_dir(),paths.app_config_dir(),
                 paths.app_cache_dir(),paths.app_log_dir(),paths.resource_dir()] {
        let mut root=root.map_err(|_| "Protected desktop root unavailable")?;
        loop {
            match std::fs::symlink_metadata(&root) {
                Ok(_)=>break,
                Err(e) if e.kind()==std::io::ErrorKind::NotFound=>{
                    root=root.parent().ok_or("Protected desktop root unavailable")?.to_path_buf();
                }
                Err(_)=>return Err("Protected desktop root unavailable".into()),
            }
        }
        storage_boundary::validate_existing_directory(&root)?;
        if !protected.contains(&root){protected.push(root);}
    }
    Ok((allowed,protected))
}

#[tauri::command]
async fn save_dataset_as(window:tauri::WebviewWindow, request:Request<'_>)
    ->Result<NativeReportSave,String> {
    if window.label()!="main" {return Err("Unexpected desktop window".into());}
    let app=window.app_handle().clone();
    let key=current_dataset_export_key(&app)?;
    let metadata=dataset_attestation::Metadata::from_headers(request.headers())?;
    // No large JSON fallback. Only exact bounded raw binary IPC.
    let bytes=match request.body(){
        InvokeBody::Raw(bytes) if bytes.len()==metadata.size && bytes.len()<=dataset_file::MAX_BYTES=>bytes,
        _=>return Err("Dataset Save As requires exact bounded binary payload".into()),
    };
    if app.state::<DesktopState>().dataset_save_busy
        .compare_exchange(false,true,Ordering::AcqRel,Ordering::Acquire).is_err(){
        return Err("Another dataset Save As is already active".into());
    }
    let lease=DatasetSaveLease(app.clone());
    let bytes=bytes.to_vec();
    tauri::async_runtime::spawn_blocking(move||->Result<NativeReportSave,String>{
        let _lease=lease;
        metadata.verify(&key)?;
        let payload=dataset_file::validate(metadata.format,&metadata.filename,metadata.version,
            metadata.size,&metadata.sha256,&bytes)?;
        if current_dataset_export_key(&app)?!=key {return Err("Analytical engine changed; export again".into());}
        let (allowed,protected)=dataset_destination_roots(&app)?;
        // Pin each root independently, including roots on other volumes.
        // Retain these pins across consent rather than trusting path strings.
        let mut root_pins=Vec::new();
        for root in allowed.iter().chain(&protected) {
            let mut pin=storage_boundary::DirectoryPins::default();
            pin.admit_existing(root)?;
            root_pins.push(pin);
        }
        let extension=metadata.format.extension();
        let chosen=window.dialog().file().set_parent(&window)
            .set_title("Save PilotODIN cleaned dataset (new file only)")
            .set_directory(allowed[0].clone()).set_file_name(&metadata.filename)
            .add_filter(if extension=="csv"{"CSV dataset"}else{"Excel workbook"},&[extension])
            .blocking_save_file();
        let path=match chosen {
            None=>return Ok(NativeReportSave{status:"cancelled",filename:None}),
            Some(path)=>path.into_path().map_err(|_|"Choose a local dataset destination")?,
        };
        for pin in &root_pins {pin.verify()?;}
        let (allowed_now,protected_now)=dataset_destination_roots(&app)?;
        if allowed_now!=allowed || protected_now!=protected {
            return Err("Dataset destination roots changed; export again".into());
        }
        // Serialize final admission with owned worker launch/normal shutdown.
        // Never hold the gate across the interactive dialog. An emergency
        // process exit is still not a verified graceful drain.
        let state=app.state::<DesktopState>();
        let _publication=state.launch_gate.lock().map_err(|_|"Desktop publication unavailable")?;
        if current_dataset_export_key(&app)?!=key {return Err("Analytical engine changed; export again".into());}
        dataset_file::publish_new(&path,&payload,uuid::Uuid::new_v4().as_u128(),
            &allowed_now,&protected_now)?;
        Ok(NativeReportSave{status:"saved",filename:path.file_name().and_then(|n|n.to_str()).map(str::to_owned)})
    }).await.map_err(|_|"Native dataset Save As could not finish".to_string())?
}

#[tauri::command]
async fn save_report_as(app: AppHandle, request: Request<'_>)
    -> Result<NativeReportSave, String> {
    ensure_desktop_admission(&app, &app.state::<DesktopState>())?;
    #[cfg(windows)]
    if resource_desktop::selected(&app) {
        // No independent native writer may bypass the shared workload lane.
        return Err("Owned resource admission for report Save As is unavailable".into());
    }
    let (format, filename, bytes) = {
        let (format, filename) = report_save_headers(request.headers())?;
        let bytes = report_save_bytes(request.body())?;
        check_report_payload(format, &filename, &bytes)?;
        (format.to_owned(), filename.into_owned(), bytes.into_owned())
    };
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
        // Only the OS dialog may choose the destination. Never accept a path
        // from JavaScript. Standard Save As handles overwrite confirmation.
        ensure_desktop_admission(&app, &app.state::<DesktopState>())?;
        write_verified_report(&path, &format, &bytes)
    }).await.map_err(|_| "The native Save As task could not finish".to_string())?
}

fn write_verified_report(path: &Path, format: &str, bytes: &[u8])
    -> Result<NativeReportSave, String> {
    if !path.extension().and_then(|ext| ext.to_str())
        .map(|ext| ext.eq_ignore_ascii_case(format)).unwrap_or(false) {
        return Err("Save As extension differs from the report format".into());
    }
    report_file::publish_report(path, bytes, uuid::Uuid::new_v4().as_u128())
        .map_err(|e| format!("Could not save report to the selected location: {e}"))?;
    let filename = path.file_name().and_then(|name| name.to_str()).map(str::to_owned);
    Ok(NativeReportSave { status: "saved", filename })
}

#[cfg(test)]
mod report_save_tests {
    use super::{check_report_payload, report_save_bytes, report_save_headers, write_verified_report, MAX_REPORT_EXPORT_BYTES};
    use std::borrow::Cow;
    use tauri::{http::HeaderMap, ipc::InvokeBody};

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

    #[test]
    fn raw_and_fallback_report_payloads_preserve_bytes() {
        let exact = b"%PDF-1.7\n\x00\x81\xff";
        let raw = InvokeBody::Raw(exact.to_vec());
        let payload = report_save_bytes(&raw).unwrap();
        assert!(matches!(payload, Cow::Borrowed(_)));
        assert_eq!(&*payload, exact);
        let fallback = InvokeBody::Json(serde_json::json!(exact.to_vec()));
        assert_eq!(&*report_save_bytes(&fallback).unwrap(), exact);
        for invalid in [
            serde_json::json!([]), serde_json::json!([-1]),
            serde_json::json!([256]), serde_json::json!([1.5]),
            serde_json::json!(["8"]), serde_json::json!({"bytes":[8]}),
        ] {
            assert!(report_save_bytes(&InvokeBody::Json(invalid)).is_err());
        }
    }

    #[test]
    fn encoded_filenames_still_pass_native_validation() {
        let mut headers = HeaderMap::new();
        assert!(report_save_headers(&headers).is_err());
        headers.insert("x-pilotodin-report-format", "pdf".parse().unwrap());
        headers.insert("x-pilotodin-report-filename", "R%C3%A9sum%C3%A9%201.pdf".parse().unwrap());
        let (format, filename) = report_save_headers(&headers).unwrap();
        assert_eq!(filename, "Résumé 1.pdf");
        assert!(check_report_payload(format, &filename, b"%PDF-").is_ok());
        headers.insert("x-pilotodin-report-filename", "folder%2Freport.pdf".parse().unwrap());
        let (format, filename) = report_save_headers(&headers).unwrap();
        assert!(check_report_payload(format, &filename, b"%PDF-").is_err());
        headers.insert("x-pilotodin-report-filename", "%ff.pdf".parse().unwrap());
        assert!(report_save_headers(&headers).is_err());
    }

    #[test]
    fn native_writer_preserves_raw_pdf_and_fallback_html_on_disk() {
        let root = std::env::temp_dir().join(format!("pilotodin-report-test-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();
        let result = (|| -> Result<(), String> {
            let pdf = include_bytes!("../../public/p2-native-fixtures/report.pdf");
            let html = include_bytes!("../../public/p2-native-fixtures/report.html");
            for (format, original, body) in [
                ("pdf", pdf.as_slice(), InvokeBody::Raw(pdf.to_vec())),
                ("html", html.as_slice(), InvokeBody::Json(serde_json::json!(html.to_vec()))),
            ] {
                let filename = format!("synthetic.{format}");
                let target = root.join(&filename);
                let bytes = report_save_bytes(&body)?;
                check_report_payload(format, &filename, &bytes)?;
                let saved = write_verified_report(&target, format, &bytes)?;
                assert_eq!(saved.status, "saved");
                assert_eq!(saved.filename.as_deref(), Some(filename.as_str()));
                assert_eq!(std::fs::read(target).unwrap(), original);
                let wrong_extension = root.join("unwritten.txt");
                assert!(write_verified_report(&wrong_extension, format, &bytes).is_err());
                assert!(!wrong_extension.exists());
            }
            Ok(())
        })();
        std::fs::remove_dir_all(&root).unwrap();
        result.unwrap();
    }
}


#[cfg(test)]
mod worker_temp_directory_tests {
    use super::worker_temp_directory;
    use std::fs;
    use std::path::PathBuf;

    #[test]
    fn worker_temp_stays_under_existing_app_data_and_refuses_unreviewed_name() {
        let root = std::env::temp_dir().join(format!(
            "pilotodin-worker-temp-unit-{}", uuid::Uuid::new_v4()
        ));
        fs::create_dir(&root).unwrap();
        let run = (|| -> Result<(), String> {
            let mut pins = super::storage_boundary::DirectoryPins::default();
            let backend = worker_temp_directory(&root, "backend-temp", &mut pins)?;
            let inference = worker_temp_directory(&root, "inference-temp", &mut pins)?;
            let home = root.clone();
            if backend.parent() != Some(home.as_path()) ||
                inference.parent() != Some(home.as_path()) ||
                backend == inference || !backend.is_dir() || !inference.is_dir() {
                return Err("Worker scratch directory was not isolated".into());
            }
            if worker_temp_directory(&root, "..", &mut pins).is_ok() {
                return Err("Unreviewed worker directory was accepted".into());
            }
            Ok(())
        })();
        fs::remove_dir_all(&root).unwrap();
        run.unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn worker_temp_rejects_symlink_outside_app_data() {
        use std::os::unix::fs::symlink;
        let outer = std::env::temp_dir().join(format!(
            "pilotodin-worker-temp-outer-{}", uuid::Uuid::new_v4()
        ));
        let home = outer.join("home");
        let outside = outer.join("outside");
        fs::create_dir(&outer).unwrap();
        fs::create_dir(&home).unwrap();
        fs::create_dir(&outside).unwrap();
        symlink(&outside, home.join("backend-temp")).unwrap();
        {
            let mut pins = super::storage_boundary::DirectoryPins::default();
            assert!(worker_temp_directory(&home, "backend-temp", &mut pins).is_err());
        }
        fs::remove_dir_all(&outer).unwrap();
    }
}

#[cfg(test)]
mod native_close_ticket_tests {
    use super::{consume_native_close_ticket, eligible_p3_w5_qa_exit, eligible_n12_no_cdp_listener_ack};

    #[test]
    fn no_cdp_ack_needs_debug_exact_local_root_and_separate_consent() {
        let page = "http://127.0.0.1:5173/";
        let consent = Some("I_APPROVE_ONE_N12_NO_CDP_STORAGE");
        assert!(eligible_n12_no_cdp_listener_ack(true, page, consent));
        assert!(eligible_n12_no_cdp_listener_ack(
            true, "http://127.0.0.1:5173/#/quality", consent,
        ));
        for (debug, url, approval) in [
            (false, page, consent),
            (true, page, None),
            (true, page, Some("I_APPROVE_ONE_N12_WEBVIEW_STORAGE")),
            (true, "http://localhost:5173/", consent),
            (true, "http://127.0.0.1:5173/?other=1", consent),
            (true, "http://127.0.0.1:5173/p4_n12_lifecycle_peer.html", consent),
            (true, "http://127.0.0.1:5178/", consent),
            (true, "tauri://localhost/", consent),
            (true, "https://example.com/", consent),
        ] {
            assert!(!eligible_n12_no_cdp_listener_ack(debug, url, approval));
        }
    }

    #[test]
    fn synthetic_w5_finish_is_not_a_general_native_close_bypass() {
        let w5 = "http://127.0.0.1:5178/p3_native_quality_w5_qa.html";
        assert!(eligible_p3_w5_qa_exit(true, w5));
        assert!(eligible_p3_w5_qa_exit(
            true, "http://127.0.0.1:5178/p3_native_quality_w5_qa.html#/studio/quality"
        ));
        assert!(!eligible_p3_w5_qa_exit(false, w5));
        assert!(!eligible_p3_w5_qa_exit(
            true, "http://127.0.0.1:5173/"
        ));
        assert!(!eligible_p3_w5_qa_exit(
            true, "http://localhost:5178/p3_native_quality_w5_qa.html"
        ));
        assert!(!eligible_p3_w5_qa_exit(
            true, "http://127.0.0.1:5178/p3_native_semantic_qa.html"
        ));
        assert!(!eligible_p3_w5_qa_exit(
            true, "http://127.0.0.1:5178/p3_native_quality_w5_qa.html?unsafe=1"
        ));
        assert!(!eligible_p3_w5_qa_exit(
            true, "tauri://localhost/p3_native_quality_w5_qa.html"
        ));
        assert!(!eligible_p3_w5_qa_exit(
            true, "https://example.com/p3_native_quality_w5_qa.html"
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
    // Defer only the production window in the in-memory configuration.
    // Several QA identities inherit the base window list. Changing the base
    // JSON create flag would inadvertently disable their existing windows.
    let mut context = tauri::generate_context!();
    if context.config().identifier == "com.pilotodin.studio" {
        let config = context.config_mut();
        if config.app.app_directories_override.is_some()
            || config.app.windows.len() != 1
            || config.app.windows[0].label != "main"
            || config.app.windows[0].data_directory.is_some()
            || config.app.windows[0].additional_browser_args.is_some() {
            panic!("Unexpected production desktop startup configuration");
        }
        config.app.windows[0].create = false;
    }
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(DesktopState::default())
        .manage(NativeCloseState::default())
        .setup(|app| {
            // Only the production main window was deferred above.
            // Isolated QA configurations retain their existing startup paths.
            if app.config().identifier == "com.pilotodin.studio" {
                let config = app.config().app.windows.iter()
                    .find(|window| window.label == "main")
                    .ok_or_else(|| std::io::Error::other("Missing production main window configuration"))?
                    .clone();
                if config.create || app.get_webview_window("main").is_some() {
                    return Err(std::io::Error::other("Production window must be deferred").into());
                }
                let root = app.path().app_local_data_dir()?;
                let (profile, lease) = desktop_profile::prepare_production_profile(&root)
                    .map_err(std::io::Error::other)?;
                // Retain the lease in application state, not a temporary setup variable.
                if !app.manage(lease) {
                    return Err(std::io::Error::other("Desktop profile ownership already registered").into());
                }
                tauri::WebviewWindowBuilder::from_config(app.handle(), &config)?
                    .data_directory(profile)
                    .build()?;
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            launch_backend, launch_bundled_ai, save_report_as, save_dataset_as,
            resolve_native_close_request, confirm_native_close, confirm_native_project_switch,
            acknowledge_n12_no_cdp_close_listener_ready,
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
        .build(context)
        .expect("Could not initialise PilotODIN desktop")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                let state = app.state::<DesktopState>();
                state.stopping.store(true, Ordering::Release);
                // Emergency/non-ticket exit is not a verified graceful drain.
                if let Ok(pending) = state.inference_startup.lock() {
                    if let Some(attempt) = pending.as_ref() {
                        attempt.cancelled.store(true, Ordering::Release);
                    }
                }
                if let Ok(mut ai) = state.inference.lock() {
                    if let Some(mut worker) = ai.take() {
                        eprintln!("Emergency inference cleanup");
                        terminate_owned_child(worker.child.take());
                    }
                }
                if let Ok(mut backend) = state.backend.lock() {
                    if let Some(mut worker) = backend.take() {
                        #[cfg(windows)]
                        if let Some(owner) = &worker.owned { owner.request_stop(); }
                        eprintln!("Emergency analytical cleanup");
                        terminate_owned_child(worker.child.take());
                    }
                };
            }
        });
}
