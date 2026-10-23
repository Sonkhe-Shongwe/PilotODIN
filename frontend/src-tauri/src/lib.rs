//! PilotODIN desktop lifecycle supervisor.
//! Python and bundled inference are separate loopback-only, per-session workers.
//! AI has no arbitrary process- or filesystem-execution capability.
use std::fs::File;
use std::io::Read;
use std::net::TcpListener;
use std::sync::Mutex;
use sha2::{Digest, Sha256};
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager, RunEvent, State};
use tauri_plugin_shell::{process::{CommandChild, CommandEvent}, ShellExt};

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

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(DesktopState::default())
        .invoke_handler(tauri::generate_handler![launch_backend, launch_bundled_ai])
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
