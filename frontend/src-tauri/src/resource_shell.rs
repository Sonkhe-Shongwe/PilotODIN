//! Dormant shell 2.6.0 adapter. Not registered in lib.rs.
//! The composition root must retain this object through fault/shutdown,
//! tick independently of event delivery, and drain the event receiver even
//! after protocol failure. Dropping a JoinHandle is not worker exit.
use std::thread::{self, JoinHandle};
use std::time::Instant;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use crate::resource_transport::{Command, Transport};
use crate::resource_wire::Reply;

const FAULT: &str = "Owned shell transport unavailable";

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
}

impl ShellChannel {
    pub(crate) fn new(transport: Transport, child: CommandChild) -> Self {
        Self { transport, writer: Writer::new(child),
            leader_terminated: false, receiver_closed: false }
    }

    pub(crate) fn begin(&mut self, command: Command, now: Instant) -> Result<(), &'static str> {
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
                self.transport.lost();
                Err(FAULT)
            },
            _ => {
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

    pub(crate) fn take_for_cleanup(&mut self) -> Option<CommandChild> {
        self.reply = None;
        self.channel.take_for_cleanup()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::mpsc;
    use std::time::Duration;

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
