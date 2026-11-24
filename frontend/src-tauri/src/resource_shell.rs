//! Dormant shell 2.6.0 adapter. Not registered in lib.rs.
//! The composition root must retain this object through fault/shutdown,
//! tick independently of event delivery, and drain the event receiver even
//! after protocol failure. Dropping a JoinHandle is not worker exit.
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
#[cfg(windows)]
use tauri_plugin_shell::process::OwnedJob;
use crate::resource_transport::{Command, Transport};
use crate::resource_wire::Reply;

const FAULT: &str = "Owned shell transport unavailable";

// No browser input can construct these witnesses. The host must derive
// startup_joined from the independently joined exact startup generation.
// A leader event is necessary but not sufficient for whole-job exit.
#[derive(Clone, Copy)]
struct ExitWitnesses {
    startup_joined: bool,
    leader_terminated: bool,
    receiver_closed: bool,
    child_dropped: bool,
    event_fault: bool,
}

const JOB_EXIT_LIMIT: Duration = Duration::from_secs(4);
const JOB_FAULT: &str = "Owned process group exit is unconfirmed";

#[derive(Default)]
struct ExitFence {
    deadline: Option<Instant>,
    faulted: bool,
    confirmed: bool,
}

impl ExitFence {
    fn begin(&mut self, now: Instant) -> Result<(), &'static str> {
        if self.deadline.is_some() || self.faulted || self.confirmed {
            return Err(JOB_FAULT);
        }
        self.deadline = Some(now.checked_add(JOB_EXIT_LIMIT).ok_or(JOB_FAULT)?);
        Ok(())
    }

    fn fail<T>(&mut self) -> Result<T, &'static str> {
        self.faulted = true;
        Err(JOB_FAULT)
    }

    // No deadline renewal, and no query until all actual ownership
    // witnesses have settled. A late positive result is not a pass.
    fn poll<F>(&mut self, now: Instant, witness: ExitWitnesses, query: F)
        -> Result<bool, &'static str>
    where F: FnOnce() -> Result<(u32, Instant), &'static str> {
        if self.faulted || witness.event_fault { return self.fail(); }
        let deadline = self.deadline.ok_or(JOB_FAULT)?;
        if self.confirmed { return Ok(true); }
        if now >= deadline { return self.fail(); }
        if !(witness.startup_joined && witness.leader_terminated &&
             witness.receiver_closed && witness.child_dropped) {
            return Ok(false);
        }
        match query() {
            Ok((active, observed)) if observed >= now && observed < deadline => {
                if active == 0 { self.confirmed = true; }
                Ok(self.confirmed)
            },
            _ => self.fail(),
        }
    }
}

// The exact job handle is retained independently of the moved child and
// survives a blocked pipe writer, consumed child, or failed accounting query.
// This is a Windows-only Rust owner, not a Tauri IPC capability.
#[cfg(windows)]
struct OwnedJobDrain {
    job: Option<OwnedJob>,
    fence: ExitFence,
}

#[cfg(windows)]
impl OwnedJobDrain {
    fn new(child: &CommandChild) -> Self {
        let job = child.owned_job();
        let fence = ExitFence { faulted: job.is_none(), ..ExitFence::default() };
        Self { job, fence }
    }

    fn admission_open(&self) -> bool {
        self.job.is_some() && self.fence.deadline.is_none() && !self.fence.faulted
    }

    fn begin(&mut self) -> Result<(), &'static str> {
        // Close admission BEFORE requesting termination. Retain the original
        // accounting handle even if termination fails or blocks a writer.
        self.fence.begin(Instant::now())?;
        match self.job.as_ref().map(|job| job.terminate()) {
            Some(Ok(())) => Ok(()),
            _ => self.fence.fail(),
        }
    }

    fn poll(&mut self, witness: ExitWitnesses) -> Result<bool, &'static str> {
        let job = self.job.as_ref();
        self.fence.poll(Instant::now(), witness, || {
            let count = job.ok_or(JOB_FAULT)?.active_processes().map_err(|_| JOB_FAULT)?;
            Ok((count, Instant::now()))
        })
    }
}

struct Writer<C> {
    child: Option<C>,
    job: Option<JoinHandle<(C, bool)>>,
    lost: bool,
}

impl<C: Send + 'static> Writer<C> {
    fn new(child: C) -> Self {
        Self { child: Some(child), job: None, lost: false }
    }

    fn start<F>(&mut self, bytes: Vec<u8>, write: F) -> Result<(), &'static str>
    where F: FnOnce(&mut C, &[u8]) -> bool + Send + 'static {
        if self.lost || self.job.is_some() { return Err(FAULT); }
        let mut child = self.child.take().ok_or(FAULT)?;
        match thread::Builder::new().name("pilotodin-owned-pipe-writer".into())
            .spawn(move || {
                let success = write(&mut child, &bytes);
                (child, success)
            }) {
            Ok(job) => { self.job = Some(job); Ok(()) },
            Err(_) => {
                // Spawn error consumes the moved closure. Do not recreate
                // the child or infer that kill-on-drop proved termination.
                self.lost = true;
                Err(FAULT)
            }
        }
    }

    fn reap(&mut self) -> Result<Option<bool>, &'static str> {
        if self.lost { return Err(FAULT); }
        if !self.job.as_ref().is_some_and(|job| job.is_finished()) {
            return Ok(None);
        }
        let job = self.job.take().ok_or(FAULT)?;
        match job.join() {
            Ok((child, success)) => {
                self.child = Some(child);
                Ok(Some(success))
            },
            Err(_) => {
                self.lost = true;
                Err(FAULT)
            }
        }
    }

    fn pending(&self) -> bool { self.job.is_some() }

    fn take_for_cleanup(&mut self) -> Option<C> {
        if self.pending() || self.lost { return None; }
        self.lost = true;
        self.child.take()
    }
}

pub(crate) struct ShellChannel {
    transport: Transport,
    writer: Writer<CommandChild>,
    leader_terminated: bool,
    receiver_closed: bool,
    event_fault: bool,
    #[cfg(windows)]
    cleanup: OwnedJobDrain,
    #[cfg(windows)]
    child_dropped: bool,
}

impl ShellChannel {
    pub(crate) fn new(mut transport: Transport, child: CommandChild) -> Self {
        // Capture the actual assigned job before transferring the child into
        // Writer. A missing job faults admission, not ownership: keep the child.
        #[cfg(windows)]
        let cleanup = OwnedJobDrain::new(&child);
        #[cfg(windows)]
        if !cleanup.admission_open() { transport.lost(); }
        Self { transport, writer: Writer::new(child),
            leader_terminated: false, receiver_closed: false, event_fault: false,
            #[cfg(windows)]
            cleanup,
            #[cfg(windows)]
            child_dropped: false }
    }

    pub(crate) fn begin(&mut self, command: Command, now: Instant) -> Result<(), &'static str> {
        #[cfg(windows)]
        if !self.cleanup.admission_open() { return Err(FAULT); }
        if self.writer.pending() || self.leader_terminated || self.receiver_closed {
            return Err(FAULT);
        }
        let bytes = self.transport.begin(command, now)?;
        if self.writer.start(bytes, |child, bytes| child.write(bytes).is_ok()).is_err() {
            self.transport.lost();
            return Err(FAULT);
        }
        Ok(())
    }

    /// Must be driven by an independent monotonic timer, not by the writer.
    /// Even after timeout, keep polling the job for cleanup ownership.
    pub(crate) fn tick(&mut self, now: Instant) -> Result<Option<Reply>, &'static str> {
        let deadline = self.transport.poll(now);
        let joined = self.writer.reap();
        match joined {
            Err(_) => {
                self.transport.lost();
                Err(FAULT)
            },
            Ok(result) => {
                deadline?;
                match result {
                    Some(success) => self.transport.write_finished(success, now),
                    None => Ok(None),
                }
            }
        }
    }

    /// Pass events from only this exact engine's raw receiver. Stderr is
    /// consumed but never forwarded as text; error payloads are not logged.
    /// Terminated is a leader/event witness only, not process-group proof.
    pub(crate) fn event(&mut self, event: CommandEvent, now: Instant)
        -> Result<Option<Reply>, &'static str> {
        if self.leader_terminated {
            // The pinned shell emits Terminated only after the pipe readers
            // join; an event after that witness is contradictory.
            self.event_fault = true;
            self.transport.lost();
            return Err(FAULT);
        }
        match event {
            CommandEvent::Stdout(bytes) => {
                if self.transport.faulted() { return Err(FAULT); }
                self.transport.stdout(&bytes, now)
            },
            CommandEvent::Stderr(_) => Ok(None),
            CommandEvent::Terminated(_) => {
                self.leader_terminated = true;
                self.transport.lost();
                Err(FAULT)
            },
            CommandEvent::Error(_) => {
                self.event_fault = true;
                self.transport.lost();
                Err(FAULT)
            },
            _ => {
                self.event_fault = true;
                self.transport.lost();
                Err(FAULT)
            }
        }
    }

    pub(crate) fn receiver_closed(&mut self) {
        self.receiver_closed = true;
        self.transport.lost();
    }

    pub(crate) fn writer_pending(&self) -> bool { self.writer.pending() }
    pub(crate) fn leader_terminated(&self) -> bool { self.leader_terminated }
    pub(crate) fn faulted(&self) -> bool { self.transport.faulted() }
    pub(crate) fn has_grant(&self) -> bool { self.transport.has_grant() }

    #[cfg(windows)]
    fn begin_owned_cleanup(&mut self) -> Result<(), &'static str> {
        self.transport.lost();
        self.cleanup.begin()
    }

    #[cfg(windows)]
    fn poll_owned_cleanup(&mut self, startup_joined: bool) -> Result<bool, &'static str> {
        // ShellDriver::poll has reaped the actual writer and drained the
        // receiver. A panic/lost child is not a successful join.
        if startup_joined && self.leader_terminated && self.receiver_closed &&
            !self.writer.pending() && !self.child_dropped {
            if let Some(child) = self.writer.take_for_cleanup() {
                drop(child);
                self.child_dropped = true;
            }
        }
        self.cleanup.poll(ExitWitnesses {
            startup_joined,
            leader_terminated: self.leader_terminated,
            receiver_closed: self.receiver_closed,
            child_dropped: self.child_dropped,
            event_fault: self.event_fault,
        })
    }

    /// Returns the actual child only once the writer has joined.
    /// Cleanup ownership does NOT establish process exit or release a grant.
    pub(crate) fn take_for_cleanup(&mut self) -> Option<CommandChild> {
        self.transport.lost();
        self.writer.take_for_cleanup()
    }
}

/// Retains the exact receiver even after a failed handshake. The desktop
/// owner must drive poll independently (including when no events arrive).
/// No task may abandon or replace this driver on cancellation.
pub(crate) struct ShellDriver {
    channel: ShellChannel,
    receiver: tauri::async_runtime::Receiver<CommandEvent>,
    reply: Option<Reply>,
    closed: bool,
}

impl ShellDriver {
    pub(crate) fn new(channel: ShellChannel,
                      receiver: tauri::async_runtime::Receiver<CommandEvent>) -> Self {
        Self { channel, receiver, reply: None, closed: false }
    }

    pub(crate) fn begin(&mut self, command: Command, now: Instant) -> Result<(), &'static str> {
        if self.reply.is_some() || self.closed { return Err(FAULT); }
        self.channel.begin(command, now)
    }

    fn record(&mut self, result: Result<Option<Reply>, &'static str>) {
        match result {
            Ok(Some(reply)) if self.reply.is_none() && !self.channel.faulted() => {
                self.reply = Some(reply);
            },
            Ok(None) => {},
            _ => {
                self.channel.transport.lost();
                self.reply = None;
            }
        }
    }

    /// Bound work even under a stderr flood; never skip the writer/deadline
    /// tick and never stop consuming the exact receiver merely on a fault.
    pub(crate) fn poll(&mut self, now: Instant) -> Result<(), &'static str> {
        let result = self.channel.tick(now);
        self.record(result);
        for _ in 0..32 {
            match self.receiver.try_recv() {
                Ok(event) => {
                    let result = self.channel.event(event, Instant::now());
                    self.record(result);
                },
                Err(_) => {
                    if self.receiver.is_closed() && self.receiver.is_empty() {
                        self.closed = true;
                        self.channel.receiver_closed();
                        self.reply = None;
                    }
                    break;
                }
            }
        }
        if self.channel.faulted() {
            self.reply = None;
            return Err(FAULT);
        }
        Ok(())
    }

    pub(crate) fn take_reply(&mut self) -> Option<Reply> {
        if self.channel.faulted() { return None; }
        self.reply.take()
    }

    pub(crate) fn writer_pending(&self) -> bool { self.channel.writer_pending() }
    pub(crate) fn receiver_closed(&self) -> bool { self.closed }
    pub(crate) fn leader_terminated(&self) -> bool { self.channel.leader_terminated() }
    pub(crate) fn has_grant(&self) -> bool { self.channel.has_grant() }

    #[cfg(windows)]
    pub(crate) fn begin_owned_cleanup(&mut self) -> Result<(), &'static str> {
        self.reply = None;
        self.channel.begin_owned_cleanup()
    }

    /// Continue draining the retained receiver and reaping the actual writer
    /// even after protocol fault. The returned boolean certifies only this
    /// owned engine job, never an inference grant or another generation.
    #[cfg(windows)]
    pub(crate) fn poll_owned_cleanup(&mut self, startup_joined: bool)
        -> Result<bool, &'static str> {
        let _ = self.poll(Instant::now());
        self.channel.poll_owned_cleanup(startup_joined)
    }

    pub(crate) fn take_for_cleanup(&mut self) -> Option<CommandChild> {
        self.reply = None;
        self.channel.take_for_cleanup()
    }
}

// Staged companion for the inference sidecar, which has no POD1 stdin
// protocol. The actual supervisor must retain this owner in the exact
// grant/startup generation, poll independently of HTTP/IPC, and never
// clear it on timeout, error, or a leader-only event.
#[cfg(windows)]
pub(crate) struct InferenceGroup {
    child: Option<CommandChild>,
    receiver: tauri::async_runtime::Receiver<CommandEvent>,
    cleanup: OwnedJobDrain,
    leader_terminated: bool,
    receiver_closed: bool,
    child_dropped: bool,
    event_fault: bool,
}

#[cfg(windows)]
impl InferenceGroup {
    pub(crate) fn new(child: CommandChild,
                      receiver: tauri::async_runtime::Receiver<CommandEvent>) -> Self {
        let cleanup = OwnedJobDrain::new(&child);
        Self { child: Some(child), receiver, cleanup, leader_terminated: false,
            receiver_closed: false, child_dropped: false, event_fault: false }
    }

    /// Spawn acknowledgement only; this is not model/HTTP readiness.
    pub(crate) fn admission_open(&self) -> bool {
        self.cleanup.admission_open() && !self.leader_terminated &&
            !self.receiver_closed && !self.event_fault && self.child.is_some()
    }

    pub(crate) fn poll_events(&mut self) {
        // Bound each tick, consume all available event categories without
        // exposing worker log bytes or returning before the receiver settles.
        for _ in 0..32 {
            match self.receiver.try_recv() {
                Ok(event) => {
                    if self.leader_terminated { self.event_fault = true; }
                    match event {
                        CommandEvent::Terminated(_) => self.leader_terminated = true,
                        CommandEvent::Stdout(_) | CommandEvent::Stderr(_) => {},
                        _ => self.event_fault = true,
                    }
                },
                Err(_) => {
                    if self.receiver.is_closed() && self.receiver.is_empty() {
                        self.receiver_closed = true;
                    }
                    break;
                },
            }
        }
    }

    pub(crate) fn begin_owned_cleanup(&mut self) -> Result<(), &'static str> {
        self.cleanup.begin()
    }

    pub(crate) fn poll_owned_cleanup(&mut self, startup_joined: bool)
        -> Result<bool, &'static str> {
        self.poll_events();
        if startup_joined && self.leader_terminated && self.receiver_closed &&
            !self.child_dropped {
            if let Some(child) = self.child.take() {
                drop(child);
                self.child_dropped = true;
            }
        }
        self.cleanup.poll(ExitWitnesses {
            startup_joined,
            leader_terminated: self.leader_terminated,
            receiver_closed: self.receiver_closed,
            child_dropped: self.child_dropped,
            event_fault: self.event_fault,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::mpsc;
    use std::time::Duration;

    fn witnesses() -> ExitWitnesses {
        ExitWitnesses { startup_joined: true, leader_terminated: true,
            receiver_closed: true, child_dropped: true, event_fault: false }
    }

    #[test]
    fn job_query_waits_for_every_actual_witness() {
        let now = Instant::now();
        let mut fence = ExitFence::default();
        fence.begin(now).unwrap();
        for index in 0..4 {
            let mut witness = witnesses();
            match index {
                0 => witness.startup_joined = false,
                1 => witness.leader_terminated = false,
                2 => witness.receiver_closed = false,
                _ => witness.child_dropped = false,
            }
            assert!(!fence.poll(now, witness, || panic!("premature job query")).unwrap());
        }
        assert!(!fence.poll(now, witnesses(), || Ok((2,now))).unwrap());
        assert!(fence.poll(now, witnesses(), || Ok((0,now))).unwrap());
        assert!(fence.begin(now).is_err());
    }

    #[test]
    fn accounting_error_is_terminal_and_does_not_release() {
        let now = Instant::now();
        let mut fence = ExitFence::default();
        fence.begin(now).unwrap();
        assert!(fence.poll(now,witnesses(),|| Err(JOB_FAULT)).is_err());
        assert!(fence.poll(now,witnesses(),|| panic!("faulted fence queried")).is_err());
        assert!(!fence.confirmed);
    }

    #[test]
    fn deadline_and_late_zero_are_not_exit_proof() {
        let now = Instant::now();
        let mut fence = ExitFence::default();
        fence.begin(now).unwrap();
        let deadline = now + JOB_EXIT_LIMIT;
        assert!(fence.poll(deadline,witnesses(),|| panic!("expired query")).is_err());
        assert!(!fence.confirmed);
        let mut late = ExitFence::default();
        late.begin(now).unwrap();
        assert!(late.poll(now,witnesses(),|| Ok((0,deadline))).is_err());
        assert!(!late.confirmed);
    }

    #[test]
    fn missing_begin_and_contradictory_events_never_prove_exit() {
        let now = Instant::now();
        let mut fence = ExitFence::default();
        assert!(fence.poll(now,witnesses(),|| panic!("unstarted query")).is_err());
        fence.begin(now).unwrap();
        let mut witness = witnesses();
        witness.event_fault = true;
        assert!(fence.poll(now,witness,|| panic!("invalid event query")).is_err());
        assert!(!fence.confirmed);
    }

    fn wait_finished<C: Send + 'static>(writer: &mut Writer<C>)
        -> Result<Option<bool>, &'static str> {
        let deadline = Instant::now() + Duration::from_secs(5);
        while writer.pending() {
            match writer.reap()? {
                Some(value) => return Ok(Some(value)),
                None if Instant::now() < deadline => thread::yield_now(),
                None => return Err("fixture writer did not exit"),
            }
        }
        Ok(None)
    }

    #[test]
    fn exact_child_retained_until_writer_join() {
        let mut writer = Writer::new(17usize);
        let (entered, observed) = mpsc::channel();
        let (release, resume) = mpsc::channel();
        writer.start(vec![1,2], move |child, bytes| {
            assert_eq!(*child,17);
            assert_eq!(bytes,&[1,2]);
            entered.send(()).unwrap();
            resume.recv_timeout(Duration::from_secs(5)).unwrap();
            *child = 19;
            true
        }).unwrap();
        observed.recv_timeout(Duration::from_secs(5)).unwrap();
        assert!(writer.pending());
        assert_eq!(writer.reap().unwrap(),None);
        assert!(writer.take_for_cleanup().is_none());
        assert!(writer.start(vec![3],|_,_|true).is_err());
        release.send(()).unwrap();
        assert_eq!(wait_finished(&mut writer).unwrap(),Some(true));
        assert_eq!(writer.take_for_cleanup(),Some(19));
        assert!(writer.take_for_cleanup().is_none());
    }

    #[test]
    fn failed_write_returns_child_for_cleanup_only() {
        let mut writer=Writer::new(23usize);
        writer.start(vec![1],|_,_|false).unwrap();
        assert_eq!(wait_finished(&mut writer).unwrap(),Some(false));
        assert_eq!(writer.take_for_cleanup(),Some(23));
    }

    #[test]
    fn panic_does_not_reconstruct_child_or_allow_retry() {
        let mut writer=Writer::new(29usize);
        writer.start(vec![1],|_,_|panic!("fixture")).unwrap();
        assert!(wait_finished(&mut writer).is_err());
        assert!(writer.take_for_cleanup().is_none());
        assert!(writer.start(vec![2],|_,_|true).is_err());
    }
}
