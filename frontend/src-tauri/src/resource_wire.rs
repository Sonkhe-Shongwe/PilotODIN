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
pub(crate) enum SaveKind { Report, Export }

#[derive(Clone, Copy, PartialEq, Eq)]
enum Pending { Ready, PollDemand, Grant, WorkerReady, Drain, Release, SaveGrant, SaveRelease, Stop }

#[derive(Debug, PartialEq, Eq)]
pub(crate) enum Reply { Ready, NotReady, DemandNone, DemandPending, DemandWaiting, DemandFinished, Granted, Denied(&'static str), WorkerReady, Draining, Released, AdmissionStopped }

pub(crate) struct Wire {
    generation: String,
    capability: String,
    sequence: u32,
    pending: Option<Pending>,
    grant: Option<String>,
    demand: Option<String>,
    native_save: bool,
    buffer: Vec<u8>,
    stopping: bool,
    ready: bool,
    faulted: bool,
}

impl Wire {
    pub(crate) fn new(generation: String, capability: String) -> Result<Self, &'static str> {
        if !hex(&generation, 32) || !hex(&capability, 64) { return Err(FAULT); }
        Ok(Self { generation, capability, sequence: 0, pending: None, grant: None, demand: None, native_save: false,
            buffer: Vec::new(), stopping: false, ready: false, faulted: false })
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

    pub(crate) fn ready(&mut self) -> Result<Vec<u8>, &'static str> {
        if self.stopping || self.grant.is_some() { return Err(FAULT); }
        self.request(Pending::Ready, "READY")
    }

    #[cfg(test)]
    pub(crate) fn fixture_ready(generation: String, capability: String) -> Self {
        let mut wire = Self::new(generation, capability).unwrap();
        wire.ready = true;
        wire
    }

    pub(crate) fn poll_demand(&mut self) -> Result<Vec<u8>, &'static str> {
        if !self.ready || self.native_save { return Err(FAULT); }
        self.request(Pending::PollDemand, "POLL_DEMAND")
    }

    pub(crate) fn grant_demand(&mut self) -> Result<Vec<u8>, &'static str> {
        if !self.ready || self.stopping || self.grant.is_some() { return Err(FAULT); }
        let demand = self.demand.clone().ok_or(FAULT)?;
        self.request(Pending::Grant, &format!("GRANT_REQUEST LOCAL_INFERENCE {demand}"))
    }

    pub(crate) fn worker_ready(&mut self) -> Result<Vec<u8>, &'static str> {
        if self.stopping || self.native_save || self.demand.is_none() { return Err(FAULT); }
        let grant = self.grant.clone().ok_or(FAULT)?;
        self.request(Pending::WorkerReady, &format!("WORKER_READY {grant}"))
    }

    pub(crate) fn grant(&mut self) -> Result<Vec<u8>, &'static str> {
        if !self.ready || self.stopping || self.grant.is_some() { return Err(FAULT); }
        self.request(Pending::Grant, "GRANT_REQUEST LOCAL_INFERENCE")
    }

    pub(crate) fn drain(&mut self) -> Result<Vec<u8>, &'static str> {
        if self.native_save { return Err(FAULT); }
        let id = self.grant.clone().ok_or(FAULT)?;
        self.request(Pending::Drain, &format!("DRAIN {id}"))
    }

    pub(crate) fn release(&mut self, evidence: ExitEvidence) -> Result<Vec<u8>, &'static str> {
        if self.native_save { return Err(FAULT); }
        let id = self.grant.clone().ok_or(FAULT)?;
        let proof = match evidence { ExitEvidence::NeverStarted => "NEVER_STARTED",
            ExitEvidence::Exited => "EXITED" };
        self.request(Pending::Release, &format!("RELEASE {id} {proof}"))
    }

    pub(crate) fn save_grant(&mut self, kind: SaveKind) -> Result<Vec<u8>, &'static str> {
        if !self.ready || self.stopping || self.grant.is_some() { return Err(FAULT); }
        self.request(Pending::SaveGrant, match kind {
            SaveKind::Report => "SAVE_GRANT REPORT", SaveKind::Export => "SAVE_GRANT EXPORT",
        })
    }

    pub(crate) fn save_release(&mut self) -> Result<Vec<u8>, &'static str> {
        if !self.native_save { return Err(FAULT); }
        let id = self.grant.clone().ok_or(FAULT)?;
        self.request(Pending::SaveRelease, &format!("SAVE_RELEASE {id} SETTLED"))
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
            (Some(Pending::Ready), ["READY"]) => { self.ready = true; Reply::Ready },
            (Some(Pending::Ready), ["NOT_READY"]) => { self.ready = false; Reply::NotReady },
            (Some(Pending::PollDemand), ["DEMAND_NONE"]) if self.grant.is_none() => {
                self.demand = None; Reply::DemandNone
            },
            (Some(Pending::PollDemand), ["DEMAND_PENDING", id])
                if self.grant.is_none() && hex(id,32) => {
                    self.demand = Some((*id).to_owned()); Reply::DemandPending
                },
            (Some(Pending::PollDemand), ["DEMAND_WAITING", id])
                if self.grant.is_some() && self.demand.as_deref() == Some(*id) => Reply::DemandWaiting,
            (Some(Pending::PollDemand), ["DEMAND_FINISHED", id])
                if self.grant.is_some() && self.demand.as_deref() == Some(*id) => Reply::DemandFinished,
            (Some(Pending::WorkerReady), ["WORKER_READY", id])
                if self.grant.as_deref() == Some(*id) => Reply::WorkerReady,
            (Some(Pending::Grant), ["GRANT_REPLY", "GRANTED", id]) if hex(id,32) => {
                if self.grant.is_some() { return self.reject(); }
                self.grant = Some((*id).to_owned());
                Reply::Granted
            },
            (Some(Pending::SaveGrant), ["SAVE_GRANTED", id]) if hex(id,32) => {
                if self.grant.is_some() { return self.reject(); }
                self.grant = Some((*id).to_owned());
                self.native_save = true;
                Reply::Granted
            },
            (Some(Pending::Grant), ["GRANT_REPLY", "DENIED", code]) |
            (Some(Pending::SaveGrant), ["SAVE_DENIED", code]) => {
                let denial = match *code {
                    "not_ready" => { self.ready = false; "not_ready" },
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
                self.demand = None;
                Reply::Denied(denial)
            },
            (Some(Pending::Drain), ["DRAINING", id])
                if self.grant.as_deref() == Some(*id) => Reply::Draining,
            (Some(Pending::Release), ["RELEASED", id])
                if self.grant.as_deref() == Some(*id) => {
                    self.grant = None;
                    self.demand = None;
                    Reply::Released
                },
            (Some(Pending::SaveRelease), ["SAVE_RELEASED", id])
                if self.native_save && self.grant.as_deref() == Some(*id) => {
                    self.grant = None;
                    self.native_save = false;
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
    fn wire() -> Wire { Wire::fixture_ready(GEN.into(), KEY.into()) }
    fn reply(seq: u32, body: &str) -> Vec<u8> {
        format!("POD1 {GEN} {seq} {body}\n").into_bytes()
    }

    #[test]
    fn exact_demand_poll_grant_worker_ready_and_finish() {
        let mut w=wire();
        assert!(w.grant_demand().is_err());
        w.poll_demand().unwrap();
        assert_eq!(w.receive(&reply(1,&format!("DEMAND_PENDING {GRANT}"))).unwrap(),Some(Reply::DemandPending));
        assert_eq!(w.grant_demand().unwrap(),format!("POD1 {GEN} {KEY} 2 GRANT_REQUEST LOCAL_INFERENCE {GRANT}\n").into_bytes());
        w.receive(&reply(2,&format!("GRANT_REPLY GRANTED {GRANT}"))).unwrap();
        w.worker_ready().unwrap();
        assert_eq!(w.receive(&reply(3,&format!("WORKER_READY {GRANT}"))).unwrap(),Some(Reply::WorkerReady));
        w.poll_demand().unwrap();
        assert_eq!(w.receive(&reply(4,&format!("DEMAND_FINISHED {GRANT}"))).unwrap(),Some(Reply::DemandFinished));
    }

    #[test]
    fn native_save_grant_is_typed_and_release_is_correlated() {
        let mut w=wire();
        assert_eq!(w.save_grant(SaveKind::Report).unwrap(),
            format!("POD1 {GEN} {KEY} 1 SAVE_GRANT REPORT\n").into_bytes());
        assert_eq!(w.receive(&reply(1,&format!("SAVE_GRANTED {GRANT}"))).unwrap(),Some(Reply::Granted));
        assert!(w.poll_demand().is_err());
        assert!(w.release(ExitEvidence::Exited).is_err());
        assert_eq!(w.save_release().unwrap(),
            format!("POD1 {GEN} {KEY} 2 SAVE_RELEASE {GRANT} SETTLED\n").into_bytes());
        assert!(w.has_grant());
        assert_eq!(w.receive(&reply(2,&format!("SAVE_RELEASED {GRANT}"))).unwrap(),Some(Reply::Released));
        assert!(!w.has_grant());
    }

    #[test]
    fn native_save_wrong_ack_retains_grant() {
        let mut w=wire();
        w.save_grant(SaveKind::Export).unwrap();
        w.receive(&reply(1,&format!("SAVE_GRANTED {GRANT}"))).unwrap();
        w.save_release().unwrap();
        assert!(w.receive(&reply(2,&format!("RELEASED {GRANT}"))).is_err());
        assert!(w.faulted() && w.has_grant());
    }

    #[test]
    fn readiness_precedes_any_grant() {
        let mut w=Wire::new(GEN.into(),KEY.into()).unwrap();
        assert!(w.grant().is_err());
        assert_eq!(w.ready().unwrap(),format!("POD1 {GEN} {KEY} 1 READY\n").into_bytes());
        assert_eq!(w.receive(&reply(1,"NOT_READY")).unwrap(),Some(Reply::NotReady));
        assert!(w.grant().is_err());
        w.ready().unwrap();
        assert_eq!(w.receive(&reply(2,"READY")).unwrap(),Some(Reply::Ready));
        assert!(w.grant().is_ok());
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
