//! Staged POD1 wire codec. No shell dependency or live registration.
//! Only the trusted host supervisor may construct this client or supply exit
//! evidence. Transport must fault it on timeout, EOF, short/failed write or
//! ambiguous delivery. A protocol reply is NOT an owned process-exit witness.

const MAX_FRAME: usize = 4096;
const MAX_SEQUENCE: u32 = 2_147_483_647;
const FAULT: &str = "Owned resource control protocol fault";

fn hex(value: &str, n: usize) -> bool {
    value.len() == n && value.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub(crate) enum ExitEvidence { NeverStarted, Exited }

#[derive(Clone, Copy, PartialEq, Eq)]
enum Pending { Grant, Drain, Release, Stop }

#[derive(Debug, PartialEq, Eq)]
pub(crate) enum Reply { Granted, Denied(&'static str), Draining, Released, AdmissionStopped }

pub(crate) struct Wire {
    generation: String,
    capability: String,
    sequence: u32,
    pending: Option<Pending>,
    grant: Option<String>,
    buffer: Vec<u8>,
    stopping: bool,
    faulted: bool,
}

impl Wire {
    pub(crate) fn new(generation: String, capability: String) -> Result<Self, &'static str> {
        if !hex(&generation, 32) || !hex(&capability, 64) { return Err(FAULT); }
        Ok(Self { generation, capability, sequence: 0, pending: None, grant: None,
            buffer: Vec::new(), stopping: false, faulted: false })
    }

    pub(crate) fn fault(&mut self) {
        // Retain pending and grant identity: neither unknown work nor known
        // resident work is released by a transport error.
        self.faulted = true;
        self.stopping = true;
    }

    pub(crate) fn faulted(&self) -> bool { self.faulted }
    pub(crate) fn has_grant(&self) -> bool { self.grant.is_some() }

    fn reject<T>(&mut self) -> Result<T, &'static str> {
        self.fault();
        Err(FAULT)
    }

    fn request(&mut self, command: Pending, body: &str) -> Result<Vec<u8>, &'static str> {
        if self.faulted || self.pending.is_some() || self.sequence == MAX_SEQUENCE {
            return self.reject();
        }
        self.sequence += 1;
        self.pending = Some(command);
        Ok(format!("POD1 {} {} {} {}\n", self.generation, self.capability,
            self.sequence, body).into_bytes())
    }

    pub(crate) fn grant(&mut self) -> Result<Vec<u8>, &'static str> {
        if self.stopping || self.grant.is_some() { return Err(FAULT); }
        self.request(Pending::Grant, "GRANT_REQUEST LOCAL_INFERENCE")
    }

    pub(crate) fn drain(&mut self) -> Result<Vec<u8>, &'static str> {
        let id = self.grant.clone().ok_or(FAULT)?;
        self.request(Pending::Drain, &format!("DRAIN {id}"))
    }

    pub(crate) fn release(&mut self, evidence: ExitEvidence) -> Result<Vec<u8>, &'static str> {
        let id = self.grant.clone().ok_or(FAULT)?;
        let proof = match evidence { ExitEvidence::NeverStarted => "NEVER_STARTED",
            ExitEvidence::Exited => "EXITED" };
        self.request(Pending::Release, &format!("RELEASE {id} {proof}"))
    }

    pub(crate) fn stop(&mut self) -> Result<Vec<u8>, &'static str> {
        self.stopping = true;
        self.request(Pending::Stop, "STOP")
    }

    pub(crate) fn receive(&mut self, chunk: &[u8]) -> Result<Option<Reply>, &'static str> {
        if self.faulted || self.pending.is_none() || chunk.is_empty() ||
            chunk.len() > MAX_FRAME || chunk.len() > MAX_FRAME - self.buffer.len() {
            return self.reject();
        }
        if chunk.iter().enumerate().any(|(i, &b)| {
            if b == b'\n' { i + 1 != chunk.len() } else { !(32..=126).contains(&b) }
        }) { return self.reject(); }
        self.buffer.extend_from_slice(chunk);
        if self.buffer.last() != Some(&b'\n') {
            if self.buffer.len() == MAX_FRAME { return self.reject(); }
            return Ok(None);
        }
        let frame = std::mem::take(&mut self.buffer);
        let line = match std::str::from_utf8(&frame[..frame.len()-1]) {
            Ok(s) => s, Err(_) => return self.reject(),
        };
        let parts: Vec<&str> = line.split(' ').collect();
        let sequence = self.sequence.to_string();
        if parts.len() < 4 || parts[0] != "POD1" ||
            parts[1] != self.generation.as_str() || parts[2] != sequence.as_str() {
            return self.reject();
        }
        let reply = match (self.pending, &parts[3..]) {
            (Some(Pending::Grant), ["GRANT_REPLY", "GRANTED", id]) if hex(id,32) => {
                if self.grant.is_some() { return self.reject(); }
                self.grant = Some((*id).to_owned());
                Reply::Granted
            },
            (Some(Pending::Grant), ["GRANT_REPLY", "DENIED", code]) => {
                let denial = match *code {
                    "resource_busy" => "resource_busy",
                    "ownership_unknown" => "ownership_unknown",
                    "shutting_down" => "shutting_down",
                    "memory_unavailable" => "memory_unavailable",
                    "policy_unavailable" => "policy_unavailable",
                    "observation_stale" => "observation_stale",
                    "low_memory_headroom" => "low_memory_headroom",
                    _ => return self.reject(),
                };
                if denial == "shutting_down" { self.stopping = true; }
                Reply::Denied(denial)
            },
            (Some(Pending::Drain), ["DRAINING", id])
                if self.grant.as_deref() == Some(*id) => Reply::Draining,
            (Some(Pending::Release), ["RELEASED", id])
                if self.grant.as_deref() == Some(*id) => {
                    self.grant = None;
                    Reply::Released
                },
            (Some(Pending::Stop), ["ADMISSION_STOPPED"]) => Reply::AdmissionStopped,
            _ => return self.reject(),
        };
        self.pending = None;
        Ok(Some(reply))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    const GEN: &str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    const KEY: &str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    const GRANT: &str = "cccccccccccccccccccccccccccccccc";
    fn wire() -> Wire { Wire::new(GEN.into(), KEY.into()).unwrap() }
    fn reply(seq: u32, body: &str) -> Vec<u8> {
        format!("POD1 {GEN} {seq} {body}\n").into_bytes()
    }

    #[test]
    fn matching_grant_drain_release() {
        let mut w = wire();
        assert_eq!(w.grant().unwrap(), format!("POD1 {GEN} {KEY} 1 GRANT_REQUEST LOCAL_INFERENCE\n").into_bytes());
        let msg = reply(1, &format!("GRANT_REPLY GRANTED {GRANT}"));
        for b in &msg[..msg.len()-1] { assert_eq!(w.receive(&[*b]).unwrap(), None); }
        assert_eq!(w.receive(b"\n").unwrap(), Some(Reply::Granted));
        assert!(w.has_grant());
        w.drain().unwrap();
        assert_eq!(w.receive(&reply(2,&format!("DRAINING {GRANT}"))).unwrap(),Some(Reply::Draining));
        w.release(ExitEvidence::Exited).unwrap();
        assert!(w.has_grant());
        assert_eq!(w.receive(&reply(3,&format!("RELEASED {GRANT}"))).unwrap(),Some(Reply::Released));
        assert!(!w.has_grant());
    }

    #[test]
    fn single_outstanding_and_lost_reply_fault() {
        let mut w=wire();
        w.grant().unwrap();
        assert!(w.stop().is_err());
        assert!(w.faulted());
        assert!(w.receive(&reply(1,&format!("GRANT_REPLY GRANTED {GRANT}"))).is_err());
        let mut w=wire();
        w.grant().unwrap();
        w.fault();
        assert!(w.grant().is_err());
    }

    #[test]
    fn wrong_sequence_and_pipelining_rejected() {
        for bad in [reply(2,"GRANT_REPLY DENIED resource_busy"),
            [reply(1,"GRANT_REPLY DENIED resource_busy"), b"P".to_vec()].concat(),
            reply(1,"GRANT_REPLY DENIED invalid"),
            vec![b'x';MAX_FRAME]] {
            let mut w=wire();
            w.grant().unwrap();
            assert!(w.receive(&bad).is_err());
            assert!(w.faulted());
        }
    }

    #[test]
    fn stop_is_not_exit_and_wrong_release_retains_grant() {
        let mut w=wire();
        w.grant().unwrap();
        w.receive(&reply(1,&format!("GRANT_REPLY GRANTED {GRANT}"))).unwrap();
        w.stop().unwrap();
        assert_eq!(w.receive(&reply(2,"ADMISSION_STOPPED")).unwrap(),Some(Reply::AdmissionStopped));
        assert!(w.has_grant());
        w.release(ExitEvidence::NeverStarted).unwrap();
        assert!(w.receive(&reply(3,&format!("RELEASED {GEN}"))).is_err());
        assert!(w.has_grant() && w.faulted());
    }

    #[test]
    fn busy_denial_permits_new_explicit_intent() {
        let mut w=wire();
        w.grant().unwrap();
        assert_eq!(w.receive(&reply(1,"GRANT_REPLY DENIED resource_busy")).unwrap(),
            Some(Reply::Denied("resource_busy")));
        assert!(!w.has_grant());
        assert!(w.grant().is_ok());
    }
}
