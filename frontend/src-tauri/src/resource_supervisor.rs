//! Windows owned host driver for the POD1 demand/session protocol.
//! Not registered in the application until the runner/frontend switch is
//! coherent. The composition root must retain this object and drive tick
//! independently of IPC/HTTP, even when callers cancel. No raw handles,
//! model paths, tokens or grant identifiers are exposed to the WebView.
use std::sync::{Arc, atomic::{AtomicBool, Ordering}};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};
use crate::resource_shell::{InferenceGroup, ShellDriver};
use crate::resource_transport::Command;
use crate::resource_wire::{ExitEvidence, Reply};

const FAULT: &str = "Owned desktop resource supervisor is blocked";
const POLL_INTERVAL: Duration = Duration::from_millis(100);
const READY_LIMIT: Duration = Duration::from_secs(30);
const START_LIMIT: Duration = Duration::from_secs(120);
const ENGINE_EXIT_LIMIT: Duration = Duration::from_secs(12);

// R retains the exact model and storage pins through group exit and the
// correlated release acknowledgement. NeverStarted must be returned only
// by a factory that did not enter Command::spawn; errors after entering
// spawn, including panic, must be Uncertain.
pub(crate) enum StartupOutcome<R> {
    Started(InferenceGroup, R),
    NeverStarted,
    Uncertain,
}

pub(crate) type Factory<R> = Arc<dyn Fn(Arc<AtomicBool>) -> StartupOutcome<R> + Send + Sync>;

struct Startup<R> {
    cancelled: Arc<AtomicBool>,
    task: JoinHandle<StartupOutcome<R>>,
    deadline: Instant,
}

fn join_finished<R>(slot: &mut Option<Startup<R>>, now: Instant)
    -> Result<Option<(StartupOutcome<R>, bool)>, &'static str> {
    let Some(startup) = slot.as_ref() else { return Ok(None); };
    if !startup.task.is_finished() {
        if now >= startup.deadline { return Err(FAULT); }
        return Ok(None);
    }
    let startup = slot.take().ok_or(FAULT)?;
    let deadline = startup.deadline;
    let outcome = startup.task.join().map_err(|_| FAULT)?;
    Ok(Some((outcome, Instant::now() >= deadline)))
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Phase {
    Boot, Idle, Claim, Starting, Running, Drain, Exit, Release,
    EngineExit, Closed, Fault,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Pending { Ready, Poll, Grant, WorkerReady, Drain, Release, Stop }

enum Worker<R> {
    None,
    NeverStarted,
    Owned(InferenceGroup, R),
}

pub(crate) struct Supervisor<R: Send + 'static> {
    shell: ShellDriver,
    factory: Factory<R>,
    startup: Option<Startup<R>>,
    worker: Worker<R>,
    phase: Phase,
    pending: Option<Pending>,
    next_poll: Instant,
    ready_deadline: Instant,
    stopping: bool,
    stop_ack: bool,
    exit_deadline: Option<Instant>,
    graceful_observation: bool,
    fault_engine_cleanup: bool,
    fault_worker_cleanup: bool,
}

impl<R: Send + 'static> Supervisor<R> {
    pub(crate) fn new(shell: ShellDriver, factory: Factory<R>) -> Self {
        let now = Instant::now();
        Self { shell, factory, startup: None, worker: Worker::None,
            phase: Phase::Boot, pending: None, next_poll: now,
            ready_deadline: now + READY_LIMIT, stopping: false, stop_ack: false,
            exit_deadline: None, graceful_observation: false,
            fault_engine_cleanup: false, fault_worker_cleanup: false }
    }

    // This is private host state, not a public grant or model-ready claim.
    pub(crate) fn ready(&self) -> bool {
        !self.stopping && matches!(self.phase, Phase::Idle | Phase::Claim |
            Phase::Starting | Phase::Running | Phase::Drain | Phase::Exit | Phase::Release)
    }

    pub(crate) fn closed(&self) -> bool { self.phase == Phase::Closed }

    pub(crate) fn request_stop(&mut self) {
        self.stopping = true;
        if let Some(startup) = &self.startup {
            startup.cancelled.store(true, Ordering::Release);
        }
    }

    fn fail(&mut self) {
        self.request_stop();
        self.phase = Phase::Fault;
        // Do not clear pending/grant/startup/worker on fault. The actual
        // owner continues best-effort cleanup without issuing RELEASE.
    }

    fn send(&mut self, pending: Pending, command: Command, now: Instant)
        -> Result<(), &'static str> {
        if self.pending.is_some() { return Err(FAULT); }
        self.shell.begin(command, now)?;
        self.pending = Some(pending);
        Ok(())
    }

    fn begin_start(&mut self, now: Instant) -> Result<(), &'static str> {
        if self.startup.is_some() || !matches!(&self.worker, Worker::None) ||
            !self.shell.has_grant() { return Err(FAULT); }
        if self.stopping {
            self.worker = Worker::NeverStarted;
            self.phase = Phase::Drain;
            return Ok(());
        }
        let cancelled = Arc::new(AtomicBool::new(false));
        let cancel = cancelled.clone();
        let factory = self.factory.clone();
        let task = thread::Builder::new().name("pilotodin-owned-inference-startup".into())
            .spawn(move || factory(cancel)).map_err(|_| FAULT)?;
        self.startup = Some(Startup { cancelled, task, deadline: now + START_LIMIT });
        Ok(())
    }

    // Only a completed real JoinHandle may transfer a spawned group or
    // a proved pre-spawn refusal into this exact grant owner.
    fn reap_start(&mut self, now: Instant) -> Result<(), &'static str> {
        let Some((outcome, late)) = join_finished(&mut self.startup, now)? else {
            return Ok(());
        };
        if !matches!(&self.worker, Worker::None) { return Err(FAULT); }
        match outcome {
            StartupOutcome::Started(group, pins) => {
                // Keep ownership even if the startup completed too late.
                self.worker = Worker::Owned(group, pins);
            },
            StartupOutcome::NeverStarted => self.worker = Worker::NeverStarted,
            StartupOutcome::Uncertain => return Err(FAULT),
        }
        if late { return Err(FAULT); }
        Ok(())
    }

    fn reply(&mut self, reply: Reply, now: Instant) -> Result<(), &'static str> {
        let pending = self.pending.take().ok_or(FAULT)?;
        match (pending, reply) {
            (Pending::Ready, Reply::Ready) if self.phase == Phase::Boot => {
                if now >= self.ready_deadline { return Err(FAULT); }
                self.phase = Phase::Idle;
            },
            (Pending::Ready, Reply::NotReady) if self.phase == Phase::Boot => {
                if now >= self.ready_deadline { return Err(FAULT); }
            },
            (Pending::Poll, Reply::DemandNone) if self.phase == Phase::Idle => {},
            (Pending::Poll, Reply::DemandPending) if self.phase == Phase::Idle => {
                if !self.stopping { self.phase = Phase::Claim; }
            },
            (Pending::Grant, Reply::Granted) if self.phase == Phase::Claim => {
                if !self.shell.has_grant() { return Err(FAULT); }
                self.phase = Phase::Starting;
            },
            (Pending::Grant, Reply::Denied(reason)) if self.phase == Phase::Claim => {
                self.phase = match reason {
                    "not_ready" => Phase::Boot,
                    "shutting_down" | "ownership_unknown" => return Err(FAULT),
                    _ => Phase::Idle,
                };
                if self.phase == Phase::Boot { self.ready_deadline = now + READY_LIMIT; }
            },
            (Pending::WorkerReady, Reply::WorkerReady) if self.phase == Phase::Starting => {
                self.phase = Phase::Running;
            },
            (Pending::Poll, Reply::DemandWaiting) if self.phase == Phase::Running => {},
            (Pending::Poll, Reply::DemandFinished) if self.phase == Phase::Running => {
                self.phase = Phase::Drain;
            },
            (Pending::Drain, Reply::Draining) if self.phase == Phase::Drain => {
                if self.startup.is_some() { return Err(FAULT); }
                match &mut self.worker {
                    Worker::Owned(group, _) => {
                        group.begin_owned_cleanup()?;
                        self.phase = Phase::Exit;
                    },
                    Worker::NeverStarted => self.phase = Phase::Release,
                    Worker::None => return Err(FAULT),
                }
            },
            (Pending::Release, Reply::Released) if self.phase == Phase::Release => {
                if self.shell.has_grant() || self.startup.is_some() { return Err(FAULT); }
                self.worker = Worker::None;
                if self.stop_ack { self.begin_engine_exit(now); }
                else { self.phase = Phase::Idle; }
            },
            (Pending::Stop, Reply::AdmissionStopped) if self.stopping && !self.stop_ack => {
                self.stop_ack = true;
                if !self.shell.has_grant() {
                    if self.startup.is_some() || !matches!(&self.worker, Worker::None) {
                        return Err(FAULT);
                    }
                    self.begin_engine_exit(now);
                }
            },
            _ => return Err(FAULT),
        }
        self.next_poll = now + POLL_INTERVAL;
        Ok(())
    }

    fn begin_engine_exit(&mut self, now: Instant) {
        self.phase = Phase::EngineExit;
        self.exit_deadline = Some(now + ENGINE_EXIT_LIMIT);
    }

    fn drive(&mut self, now: Instant) -> Result<(), &'static str> {
        self.shell.poll(now)?;
        if let Some(reply) = self.shell.take_reply() { self.reply(reply, now)?; }
        self.reap_start(now)?;

        if let Worker::Owned(group, _) = &mut self.worker {
            if matches!(self.phase, Phase::Starting | Phase::Running) {
                group.poll_events();
                if !group.admission_open() { return Err(FAULT); }
            }
        }
        if self.pending.is_some() { return Ok(()); }
        if self.stopping && !self.stop_ack &&
            !matches!(self.phase, Phase::EngineExit | Phase::Closed) {
            return self.send(Pending::Stop, Command::Stop, now);
        }
        match self.phase {
            Phase::Boot => {
                if now >= self.ready_deadline { return Err(FAULT); }
                if now >= self.next_poll { self.send(Pending::Ready, Command::Ready, now)?; }
            },
            Phase::Idle => {
                if now >= self.next_poll { self.send(Pending::Poll, Command::PollDemand, now)?; }
            },
            Phase::Claim => self.send(Pending::Grant, Command::GrantDemand, now)?,
            Phase::Starting => {
                if self.startup.is_some() { return Ok(()); }
                match &self.worker {
                    Worker::None => self.begin_start(now)?,
                    Worker::NeverStarted => self.phase = Phase::Drain,
                    Worker::Owned(_, _) if self.stopping => self.phase = Phase::Drain,
                    Worker::Owned(_, _) => self.send(Pending::WorkerReady, Command::WorkerReady, now)?,
                }
            },
            Phase::Running => {
                // STOP does not prove synchronous generation has returned.
                // Continue polling until the exact backend demand is finished.
                if now >= self.next_poll { self.send(Pending::Poll, Command::PollDemand, now)?; }
            },
            Phase::Drain => self.send(Pending::Drain, Command::Drain, now)?,
            Phase::Exit => {
                let Worker::Owned(group, _) = &mut self.worker else { return Err(FAULT); };
                if self.startup.is_some() { return Err(FAULT); }
                if group.poll_owned_cleanup(true)? { self.phase = Phase::Release; }
            },
            Phase::Release => {
                let evidence = match &self.worker {
                    Worker::NeverStarted => ExitEvidence::NeverStarted,
                    Worker::Owned(_, _) => ExitEvidence::Exited,
                    Worker::None => return Err(FAULT),
                };
                self.send(Pending::Release, Command::Release(evidence), now)?;
            },
            Phase::EngineExit => {
                if !self.graceful_observation {
                    if now >= self.exit_deadline.ok_or(FAULT)? { return Err(FAULT); }
                    if self.shell.graceful_exit_observable() {
                        self.shell.begin_graceful_exit_observation()?;
                        self.graceful_observation = true;
                    }
                }
                if self.graceful_observation && self.shell.poll_graceful_exit()? {
                    self.phase = Phase::Closed;
                }
            },
            Phase::Closed | Phase::Fault => {},
        }
        Ok(())
    }

    // On fault, retain the exact owner indefinitely if evidence is absent.
    // Best-effort termination is not permission to release or to restart.
    fn cleanup_fault(&mut self, now: Instant) {
        let _ = self.reap_start(now);
        if !self.fault_engine_cleanup {
            self.fault_engine_cleanup = true;
            let _ = self.shell.begin_owned_cleanup();
        }
        let _ = self.shell.poll_owned_cleanup(true);
        if let Worker::Owned(group, _) = &mut self.worker {
            if !self.fault_worker_cleanup {
                self.fault_worker_cleanup = true;
                let _ = group.begin_owned_cleanup();
            }
            let _ = group.poll_owned_cleanup(self.startup.is_none());
        }
    }

    /// Call on an independently scheduled timer, not on webview requests.
    /// Retain this supervisor on Err and keep ticking for fault cleanup.
    pub(crate) fn tick(&mut self) -> Result<(), &'static str> {
        let now = Instant::now();
        if self.phase == Phase::Closed { return Ok(()); }
        if self.phase != Phase::Fault && self.drive(now).is_err() { self.fail(); }
        if self.phase == Phase::Fault {
            self.cleanup_fault(now);
            return Err(FAULT);
        }
        Ok(())
    }
}


#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::mpsc;

    fn fixture_start(deadline: Instant) -> (Option<Startup<()>>, mpsc::Sender<()>) {
        let (release, wait) = mpsc::channel();
        let cancelled = Arc::new(AtomicBool::new(false));
        let task = thread::spawn(move || {
            wait.recv_timeout(Duration::from_secs(5)).unwrap();
            StartupOutcome::NeverStarted
        });
        (Some(Startup { cancelled, task, deadline }), release)
    }

    fn wait_finished(slot: &Option<Startup<()>>) {
        let deadline = Instant::now() + Duration::from_secs(5);
        while !slot.as_ref().unwrap().task.is_finished() {
            assert!(Instant::now() < deadline);
            thread::yield_now();
        }
    }

    #[test]
    fn pending_startup_is_not_joined_or_released_on_cancel() {
        let now = Instant::now();
        let (mut slot, release) = fixture_start(now + Duration::from_secs(30));
        slot.as_ref().unwrap().cancelled.store(true, Ordering::Release);
        assert!(join_finished(&mut slot, now).unwrap().is_none());
        assert!(slot.is_some());
        release.send(()).unwrap();
        wait_finished(&slot);
        assert!(matches!(join_finished(&mut slot,Instant::now()).unwrap(),
            Some((StartupOutcome::NeverStarted,false))));
        assert!(slot.is_none());
    }

    #[test]
    fn timeout_keeps_exact_startup_and_late_result_is_marked() {
        let now = Instant::now();
        let (mut slot, release) = fixture_start(now);
        assert!(join_finished(&mut slot,now).is_err());
        assert!(slot.is_some());
        release.send(()).unwrap();
        wait_finished(&slot);
        assert!(matches!(join_finished(&mut slot,Instant::now()).unwrap(),
            Some((StartupOutcome::NeverStarted,true))));
        assert!(slot.is_none());
    }

    #[test]
    fn panicked_startup_is_not_never_started_proof() {
        let task = thread::spawn(|| -> StartupOutcome<()> { panic!("fixture"); });
        let mut slot = Some(Startup { cancelled: Arc::new(AtomicBool::new(false)),
            task, deadline: Instant::now() + Duration::from_secs(30) });
        wait_finished(&slot);
        assert!(join_finished(&mut slot,Instant::now()).is_err());
        assert!(slot.is_none());
    }
}
