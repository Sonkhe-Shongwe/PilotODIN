//! Windows application composition of the private POD1 resource driver.
//! The compile-time selection remains false until all C1/C2 integration
//! and compatibility requirements are satisfied. No runtime/env/UI opt-in.
use super::*;
use std::thread::{self, JoinHandle};
use crate::resource_shell::{InferenceGroup, ShellChannel, ShellDriver};
use crate::resource_supervisor::{Factory, StartupOutcome, Supervisor};
use crate::resource_transport::Transport;
use crate::resource_wire::{Wire, SaveKind};
use crate::resource_save::{SaveTicket, Work};
use tauri_plugin_shell::process::Command;

const OWNED_RESOURCE_ENABLED: bool = false;
const TICK: Duration = Duration::from_millis(25);
const CLOSE_WAIT: Duration = Duration::from_secs(12);
const BOOT: u8 = 0;
const READY: u8 = 1;
const CLOSED: u8 = 2;
const BLOCKED: u8 = 3;

pub(super) fn selected(app: &AppHandle) -> bool {
    OWNED_RESOURCE_ENABLED && app.config().identifier == "com.pilotodin.studio"
}

// Retain pins and the verified model until exact worker group exit and
// correlated resource release; do not put them in the startup thread alone.
struct Pins {
    _storage_pins: storage_boundary::DirectoryPins,
    _model: VerifiedModel,
}

pub(super) struct OwnedSession {
    supervisor: Mutex<Supervisor<Pins>>,
    stop: AtomicBool,
    status: AtomicU8,
    timer: Mutex<Option<JoinHandle<()>>>,
}

impl OwnedSession {
    pub(super) fn new(app: AppHandle, wire: Wire,
                      events: tauri::async_runtime::Receiver<CommandEvent>,
                      child: CommandChild, backend_token: String,
                      port: u16, token: String) -> Self {
        // The closure captures this session's immutable identity/settings,
        // not browser data or the mutable legacy settings slot.
        let factory: Factory<Pins> = Arc::new(move |cancelled| {
            start_inference(&app, &backend_token, port, &token, cancelled)
        });
        let channel = ShellChannel::new(Transport::new(wire), child);
        Self { supervisor: Mutex::new(Supervisor::new(ShellDriver::new(channel, events), factory)),
            stop: AtomicBool::new(false), status: AtomicU8::new(BOOT),
            timer: Mutex::new(None) }
    }

    pub(super) fn start_timer(self: &Arc<Self>, app: AppHandle) -> Result<(), String> {
        let mut timer = self.timer.lock().map_err(|_| "Owned timer state unavailable")?;
        if timer.is_some() || self.status.load(Ordering::Acquire) != BOOT {
            return Err("Owned timer already installed or unavailable".into());
        }
        let owner = self.clone();
        let task = thread::Builder::new().name("pilotodin-resource-supervisor".into())
            .spawn(move || {
                let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| loop {
                    let state = app.state::<DesktopState>();
                    let Ok(mut supervisor) = owner.supervisor.lock() else {
                        owner.status.store(BLOCKED, Ordering::Release);
                        state.stopping.store(true, Ordering::Release);
                        break;
                    };
                    if owner.stop.load(Ordering::Acquire) || state.stopping.load(Ordering::Acquire) {
                        supervisor.request_stop();
                    }
                    if supervisor.tick().is_err() {
                        // Retain and keep ticking the exact faulted owner.
                        owner.status.store(BLOCKED, Ordering::Release);
                        state.stopping.store(true, Ordering::Release);
                    } else if supervisor.closed() {
                        owner.status.store(CLOSED, Ordering::Release);
                        break;
                    } else if supervisor.ready() {
                        owner.status.store(READY, Ordering::Release);
                    }
                    drop(supervisor);
                    thread::sleep(TICK);
                }));
                if result.is_err() {
                    // A panicked owner is not an exit witness. Retain its
                    // supervisor and prevent engine/session replacement.
                    owner.status.store(BLOCKED, Ordering::Release);
                    app.state::<DesktopState>().stopping.store(true, Ordering::Release);
                }
            });
        match task {
            Ok(task) => { *timer = Some(task); Ok(()) },
            Err(_) => {
                self.status.store(BLOCKED, Ordering::Release);
                self.request_stop();
                Err("Owned supervisor timer start unconfirmed".into())
            },
        }
    }

    pub(super) fn check_available(&self) -> Result<(), String> {
        match self.status.load(Ordering::Acquire) {
            BOOT | READY if !self.stop.load(Ordering::Acquire) => Ok(()),
            _ => Err("Owned analytical session unavailable".into()),
        }
    }

    pub(super) fn request_stop(&self) { self.stop.store(true, Ordering::Release); }

    pub(super) fn stop_and_join(&self) -> Result<(), String> {
        self.request_stop();
        let deadline = Instant::now() + CLOSE_WAIT;
        loop {
            if self.status.load(Ordering::Acquire) == BLOCKED {
                return Err("Owned worker exit unconfirmed; shutdown blocked".into());
            }
            {
                let mut timer = self.timer.lock().map_err(|_| "Owned timer state unavailable")?;
                if timer.as_ref().is_some_and(|task| task.is_finished()) {
                    let task = timer.take().ok_or("Owned timer unavailable")?;
                    if task.join().is_err() || self.status.load(Ordering::Acquire) != CLOSED {
                        self.status.store(BLOCKED, Ordering::Release);
                        return Err("Owned supervisor join unconfirmed".into());
                    }
                    return Ok(());
                }
                if timer.is_none() {
                    return if self.status.load(Ordering::Acquire) == CLOSED { Ok(()) }
                    else { Err("Owned timer never joined".into()) };
                }
            }
            if Instant::now() >= deadline {
                return Err("Owned worker shutdown still pending; retry close".into());
            }
            thread::sleep(TICK);
        }
    }
}

// Acquire the exact installed native owner, without holding a desktop lock
// across the broker handshake. No caller may select a grant by ID.
pub(super) async fn reserve_save(app: &AppHandle, kind: SaveKind)
    -> Result<Option<SaveTicket>, String> {
    if !selected(app) { return Ok(None); }
    let ticket = {
        let state = app.state::<DesktopState>();
        ensure_desktop_admission(app, &state)?;
        let backend = state.backend.lock().map_err(|_| "Engine state unavailable")?;
        let owner = backend.as_ref().and_then(|worker| worker.owned.as_ref())
            .ok_or("Owned analytical session unavailable")?;
        owner.check_available()?;
        let mut supervisor = owner.supervisor.try_lock()
            .map_err(|_| "Native Save As resource_busy")?;
        supervisor.reserve_save(kind).map_err(str::to_owned)?
    };
    let ticket = tauri::async_runtime::spawn_blocking(move || ticket.wait_grant())
        .await.map_err(|_| "Native Save As admission unavailable".to_owned())??;
    Ok(Some(ticket))
}

pub(super) async fn run_save(ticket: SaveTicket, work: Work)
    -> Result<NativeReportSave, String> {
    let result = ticket.submit(work)?;
    // This waiter is not the writer. A dropped IPC future cannot detach
    // the actual writer from the supervisor or authorize lane release.
    tauri::async_runtime::spawn_blocking(move || {
        result.recv().map_err(|_| "Native Save As ownership unavailable".to_owned())?
    }).await.map_err(|_| "Native Save As result unavailable".to_owned())?
}

// Same existing model integrity, location, scratch and process-group
// contracts as the legacy launcher. Keep all fallible preparation separate
// from the spawn boundary: only preparation errors prove NeverStarted.
fn prepare_inference(app: &AppHandle, attempt: &InferenceStartup,
                     port: u16, token: &str) -> Result<(Command, Pins), String> {
    let state = app.state::<DesktopState>();
    let model = verify_bundled_model(app, attempt, &state.stopping)?;
    let mut storage_pins = storage_boundary::DirectoryPins::default();
    let data_dir = worker_data_home(app, &mut storage_pins)?;
    let worker_temp = worker_temp_directory(&data_dir, "inference-temp", &mut storage_pins)?;
    let resources = app.path().resource_dir().map_err(|_| "Bundled resources unavailable")?;
    let runtime_dlls = resources.join("llama-runtime");
    let old_path = std::env::var_os("PATH").unwrap_or_default();
    let mut paths = vec![runtime_dlls.clone()];
    paths.extend(std::env::split_paths(&old_path));
    let runtime_path = std::env::join_paths(paths).map_err(|_| "Invalid inference runtime path")?;
    let command = app.shell().sidecar("pilotodin-inference")
        .map_err(|_| "Bundled inference executable missing")?
        .args(["--model", model.path.to_str().ok_or("Invalid model path")?,
               "--alias", "pilotodin-qwen3-1.7b", "--host", "127.0.0.1",
               "--port", &port.to_string(), "--ctx-size", "2048",
               "--threads", "2", "--parallel", "1", "--gpu-layers", "0",
               "--sleep-idle-seconds", INFERENCE_IDLE_SLEEP_SECONDS,
               "--no-webui", "--no-agent"])
        .env("LLAMA_API_KEY", token)
        .env("PATH", runtime_path)
        .env("TEMP", worker_temp.as_os_str())
        .env("TMP", worker_temp.as_os_str())
        .env("TMPDIR", worker_temp.as_os_str())
        .current_dir(&runtime_dlls)
        .set_process_group(true)
        .kill_on_drop(true);
    Ok((command, Pins { _storage_pins: storage_pins, _model: model }))
}

fn start_inference(app: &AppHandle, backend_token: &str, port: u16, token: &str,
                   cancelled: Arc<AtomicBool>) -> StartupOutcome<Pins> {
    let state = app.state::<DesktopState>();
    let mut attempt = InferenceStartup::new(backend_token.to_owned());
    attempt.cancelled = cancelled;
    let (command, pins) = match prepare_inference(app, &attempt, port, token) {
        Ok(value) => value,
        Err(_) => return StartupOutcome::NeverStarted,
    };
    let Ok(_launch) = state.launch_gate.lock() else { return StartupOutcome::NeverStarted; };
    if ensure_desktop_admission(app, &state).is_err() || attempt.check(&state.stopping).is_err() {
        return StartupOutcome::NeverStarted;
    }
    {
        let Ok(backend) = state.backend.lock() else { return StartupOutcome::NeverStarted; };
        if !backend.as_ref().is_some_and(|worker|
            worker.connection.token == attempt.backend_token && worker.owned.is_some() &&
            worker.child.is_none() && !worker.stop_requested) {
            return StartupOutcome::NeverStarted;
        }
    }
    if pins._storage_pins.verify().is_err() || pins._model.verify().is_err() ||
        attempt.check(&state.stopping).is_err() {
        return StartupOutcome::NeverStarted;
    }
    match command.spawn() {
        Ok((events, child)) => StartupOutcome::Started(InferenceGroup::new(child, events), pins),
        Err(_) => {
            state.stopping.store(true, Ordering::Release);
            StartupOutcome::Uncertain
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn incomplete_composition_has_no_activation_switch() {
        assert!(!OWNED_RESOURCE_ENABLED);
    }
}
