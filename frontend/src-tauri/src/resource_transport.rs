//! Staged deadline/acknowledgement state for an owned shell transport.
//! No shell calls, process spawning, threads or module registration here.
//! A single supervisor drives this state; its writer owns the actual child
//! and must report completion even after timeout. Timeout is not job exit.
use std::time::{Duration, Instant};
use crate::resource_wire::{Wire, Reply, ExitEvidence};

const CAP: usize = 4096;
const DEADLINE: Duration = Duration::from_secs(5);
const FAULT: &str = "Owned resource transport unavailable";

#[derive(Clone, Copy)]
pub(crate) enum Command { Grant, Drain, Release(ExitEvidence), Stop }

pub(crate) struct Transport {
    wire: Wire,
    deadline: Option<Instant>,
    written: bool,
    early: Vec<u8>,
}

impl Transport {
    pub(crate) fn new(wire: Wire) -> Self {
        Self { wire, deadline: None, written: false, early: Vec::new() }
    }
    pub(crate) fn faulted(&self) -> bool { self.wire.faulted() }
    pub(crate) fn has_grant(&self) -> bool { self.wire.has_grant() }
    pub(crate) fn pending(&self) -> bool { self.deadline.is_some() }

    pub(crate) fn lost(&mut self) {
        self.wire.fault();
        // Preserve pending deadline and identity; no reset after uncertainty.
        self.early.clear();
    }
    fn fail<T>(&mut self) -> Result<T, &'static str> {
        self.lost();
        Err(FAULT)
    }

    pub(crate) fn poll(&mut self, now: Instant) -> Result<(), &'static str> {
        if self.wire.faulted() { return Err(FAULT); }
        if self.deadline.is_some_and(|d| now >= d) { return self.fail(); }
        Ok(())
    }

    /// The returned bytes go to the sole owned writer. Do not wait for the
    /// write on the event loop or hold this state lock while writing.
    pub(crate) fn begin(&mut self, command: Command, now: Instant) -> Result<Vec<u8>, &'static str> {
        self.poll(now)?;
        if self.pending() { return Err(FAULT); }
        let deadline = now.checked_add(DEADLINE).ok_or(FAULT)?;
        let bytes = match command {
            Command::Grant => self.wire.grant(),
            Command::Drain => self.wire.drain(),
            Command::Release(proof) => self.wire.release(proof),
            Command::Stop => self.wire.stop(),
        }?;
        self.deadline = Some(deadline);
        self.written = false;
        self.early.clear();
        Ok(bytes)
    }

    /// Actual writer completion, not task scheduling or timeout.
    pub(crate) fn write_finished(&mut self, success: bool, now: Instant)
        -> Result<Option<Reply>, &'static str> {
        self.poll(now)?;
        if !self.pending() || self.written || !success { return self.fail(); }
        self.written = true;
        if self.early.is_empty() { return Ok(None); }
        let bytes = std::mem::take(&mut self.early);
        self.accept(&bytes)
    }

    /// Only exact owned stdout bytes, never stderr or transformed lines.
    pub(crate) fn stdout(&mut self, chunk: &[u8], now: Instant)
        -> Result<Option<Reply>, &'static str> {
        self.poll(now)?;
        if !self.pending() || chunk.is_empty() || chunk.len() > CAP {
            return self.fail();
        }
        if self.written { return self.accept(chunk); }
        // A fast engine reply may arrive before the writer completion event.
        // Keep it bounded without consuming the grant/release in Wire yet.
        if self.early.last() == Some(&b'\n') || chunk.len() > CAP - self.early.len() ||
            chunk.iter().enumerate().any(|(i, &b)| {
                if b == b'\n' { i + 1 != chunk.len() } else { !(32..=126).contains(&b) }
            }) {
            return self.fail();
        }
        self.early.extend_from_slice(chunk);
        if self.early.len() == CAP && self.early.last() != Some(&b'\n') {
            return self.fail();
        }
        Ok(None)
    }

    fn accept(&mut self, bytes: &[u8]) -> Result<Option<Reply>, &'static str> {
        match self.wire.receive(bytes) {
            Ok(Some(reply)) => {
                self.deadline = None;
                self.written = false;
                Ok(Some(reply))
            }
            Ok(None) => Ok(None),
            Err(_) => self.fail(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    const GEN: &str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    const KEY: &str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    const ID: &str = "cccccccccccccccccccccccccccccccc";
    fn transport() -> Transport {
        Transport::new(Wire::new(GEN.into(), KEY.into()).unwrap())
    }
    fn reply(seq: u32, body: &str) -> Vec<u8> {
        format!("POD1 {GEN} {seq} {body}\n").into_bytes()
    }
    fn grant(t: &mut Transport, now: Instant) {
        t.begin(Command::Grant, now).unwrap();
        assert_eq!(t.write_finished(true,now).unwrap(),None);
        assert_eq!(t.stdout(&reply(1,&format!("GRANT_REPLY GRANTED {ID}")),now).unwrap(),Some(Reply::Granted));
    }

    #[test]
    fn early_reply_is_not_consumed_before_write_completion() {
        let now=Instant::now();
        let mut t=transport();
        t.begin(Command::Grant,now).unwrap();
        let r=reply(1,&format!("GRANT_REPLY GRANTED {ID}"));
        assert_eq!(t.stdout(&r[..8],now).unwrap(),None);
        assert_eq!(t.stdout(&r[8..],now).unwrap(),None);
        assert!(!t.has_grant() && t.pending());
        assert_eq!(t.write_finished(true,now).unwrap(),Some(Reply::Granted));
        assert!(t.has_grant() && !t.pending());
    }

    #[test]
    fn timeout_while_write_pending_rejects_late_completion() {
        let now=Instant::now();
        let mut t=transport();
        t.begin(Command::Grant,now).unwrap();
        assert!(t.poll(now+DEADLINE).is_err());
        assert!(t.faulted() && t.pending());
        assert!(t.write_finished(true,now+DEADLINE).is_err());
        assert!(t.begin(Command::Grant,now+DEADLINE).is_err());
    }

    #[test]
    fn deadline_not_extended_by_write_or_partial_reply() {
        let now=Instant::now();
        let mut t=transport();
        t.begin(Command::Grant,now).unwrap();
        t.write_finished(true,now+Duration::from_secs(4)).unwrap();
        assert_eq!(t.stdout(b"POD1 ",now+Duration::from_secs(4)).unwrap(),None);
        assert!(t.poll(now+DEADLINE).is_err());
    }

    #[test]
    fn failed_release_write_retains_grant_even_with_early_reply() {
        let now=Instant::now();
        let mut t=transport();
        grant(&mut t,now);
        t.begin(Command::Release(ExitEvidence::Exited),now).unwrap();
        assert_eq!(t.stdout(&reply(2,&format!("RELEASED {ID}")),now).unwrap(),None);
        assert!(t.has_grant());
        assert!(t.write_finished(false,now).is_err());
        assert!(t.has_grant() && t.faulted());
    }

    #[test]
    fn early_duplicate_and_unsolicited_stdout_fail_closed() {
        let now=Instant::now();
        let mut t=transport();
        t.begin(Command::Grant,now).unwrap();
        let r=reply(1,"GRANT_REPLY DENIED resource_busy");
        t.stdout(&r,now).unwrap();
        assert!(t.stdout(b"P",now).is_err());
        let mut t=transport();
        assert!(t.stdout(&r,now).is_err());
    }

    #[test]
    fn second_intent_does_not_replace_pending_write() {
        let now=Instant::now();
        let mut t=transport();
        t.begin(Command::Grant,now).unwrap();
        assert!(t.begin(Command::Stop,now).is_err());
        assert!(!t.faulted());
        t.write_finished(true,now).unwrap();
        assert_eq!(t.stdout(&reply(1,"GRANT_REPLY DENIED resource_busy"),now).unwrap(),
            Some(Reply::Denied("resource_busy")));
        assert!(t.begin(Command::Stop,now).is_ok());
    }

    #[test]
    fn lost_transport_does_not_release_grant() {
        let now=Instant::now();
        let mut t=transport();
        grant(&mut t,now);
        t.lost();
        assert!(t.has_grant() && t.faulted());
        assert!(t.begin(Command::Drain,now).is_err());
    }
}
