//! Private one-slot native save ownership. No browser grant or timeout release.
use std::sync::mpsc::{self, Receiver, Sender, TryRecvError};
use std::thread::{self, JoinHandle};
use std::time::Duration;
use crate::NativeReportSave;
use crate::resource_wire::SaveKind;

pub(crate) type ResultValue = Result<NativeReportSave, String>;
pub(crate) type Work = Box<dyn FnOnce(&mut bool) -> ResultValue + Send + 'static>;
const FAULT: &str = "Native Save As ownership is unconfirmed";

pub(crate) struct SaveTicket {
    grant: Receiver<Result<(), String>>,
    work: Sender<Work>,
    result: Receiver<ResultValue>,
}

impl SaveTicket {
    // Bound only the pre-start wait. Drop closes the sole submission sender;
    // the supervisor, not the timeout, decides whether work ever started.
    pub(crate) fn wait_grant(self) -> Result<Self, String> {
        self.grant.recv_timeout(Duration::from_secs(8))
            .map_err(|_| "Native Save As admission unavailable".to_owned())??;
        Ok(self)
    }

    pub(crate) fn submit(self, work: Work) -> Result<Receiver<ResultValue>, String> {
        self.work.send(work).map_err(|_| FAULT.to_owned())?;
        Ok(self.result)
    }
}

pub(crate) struct SaveOwner {
    pub(crate) kind: SaveKind,
    grant: Option<Sender<Result<(), String>>>,
    work: Receiver<Work>,
    result: Option<Sender<ResultValue>>,
    task: Option<JoinHandle<(ResultValue, bool)>>,
    settled: Option<ResultValue>,
    uncertain: bool,
}

impl SaveOwner {
    pub(crate) fn pair(kind: SaveKind) -> (Self, SaveTicket) {
        let (grant, grant_rx) = mpsc::channel();
        let (work_tx, work) = mpsc::channel();
        let (result, result_rx) = mpsc::channel();
        (Self { kind, grant: Some(grant), work, result: Some(result),
            task: None, settled: None, uncertain: false },
         SaveTicket { grant: grant_rx, work: work_tx, result: result_rx })
    }

    pub(crate) fn granted(&mut self) -> Result<(), &'static str> {
        let tx = self.grant.take().ok_or(FAULT)?;
        // Lost receiver means pre-start cancellation, not release evidence.
        let _ = tx.send(Ok(()));
        Ok(())
    }

    pub(crate) fn denied(mut self, reason: &str) {
        if let Some(tx) = self.grant.take() { let _ = tx.send(Err(reason.to_owned())); }
    }

    // Called only after the correlated grant reply. Join the exact writer,
    // never use a caller's dropped IPC or a deadline as writer completion.
    pub(crate) fn poll(&mut self, stopping: bool) -> Result<bool, &'static str> {
        if self.uncertain { return Err(FAULT); }
        if self.settled.is_some() { return Ok(true); }
        if let Some(task) = self.task.as_ref() {
            if !task.is_finished() { return Ok(false); }
            let (result, settled) = match self.task.take().ok_or(FAULT)?.join() {
                Ok(value) => value,
                Err(_) => { self.uncertain = true; return Err(FAULT); },
            };
            if !settled { self.uncertain = true; return Err(FAULT); }
            self.settled = Some(result);
            return Ok(true);
        }
        match self.work.try_recv() {
            Ok(work) if !stopping => {
                let task = thread::Builder::new().name("pilotodin-owned-native-save".into())
                    .spawn(move || {
                        let mut entered_publication = false;
                        let result = work(&mut entered_publication);
                        let settled = result.is_ok() || !entered_publication;
                        (result, settled)
                    });
                let task = match task {
                    Ok(task) => task,
                    Err(_) => { self.uncertain = true; return Err(FAULT); },
                };
                self.task = Some(task);
                Ok(false)
            },
            Ok(work) => {
                // Shutdown won before writer creation: drop all captured
                // bytes and pins before reporting never-started settlement.
                drop(work);
                self.settled = Some(Err("Desktop is shutting down".into()));
                Ok(true)
            },
            Err(TryRecvError::Disconnected) => {
                self.settled = Some(Err("Native Save As cancelled before start".into()));
                Ok(true)
            },
            Err(TryRecvError::Empty) => Ok(false),
        }
    }

    pub(crate) fn released(mut self) -> Result<(), &'static str> {
        let value = self.settled.take().ok_or(FAULT)?;
        let tx = self.result.take().ok_or(FAULT)?;
        let _ = tx.send(value);
        Ok(())
    }

    pub(crate) fn fault(&mut self) {
        if let Some(tx) = self.grant.take() { let _ = tx.send(Err(FAULT.into())); }
        if let Some(tx) = self.result.take() { let _ = tx.send(Err(FAULT.into())); }
        // Drain only after the caller submits or disappears, and join an
        // actual running writer when it returns. Never issue a release.
        let _ = self.poll(true);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn abandoned_ticket_requires_observed_disconnect() {
        let (mut owner, ticket) = SaveOwner::pair(SaveKind::Report);
        owner.granted().unwrap();
        assert!(!owner.poll(false).unwrap());
        drop(ticket);
        assert!(owner.poll(false).unwrap());
        owner.released().unwrap();
    }
    #[test]
    fn uncertain_publication_does_not_settle() {
        let (mut owner, ticket) = SaveOwner::pair(SaveKind::Export);
        owner.granted().unwrap();
        let result = ticket.wait_grant().unwrap().submit(Box::new(|entered| {
            *entered = true;
            Err("fixture publisher failed".into())
        })).unwrap();
        assert!(!owner.poll(false).unwrap());
        let deadline = std::time::Instant::now()+Duration::from_secs(5);
        loop {
            match owner.poll(false) {
                Err(_) => break,
                Ok(false) => { assert!(std::time::Instant::now()<deadline); thread::yield_now(); },
                Ok(true) => panic!("uncertain publication released"),
            }
        }
        assert!(matches!(result.try_recv(),Err(TryRecvError::Empty)));
        owner.fault();
        assert!(result.recv().unwrap().is_err());
    }
    #[test]
    fn result_waits_for_actual_join_and_release() {
        let (mut owner, ticket) = SaveOwner::pair(SaveKind::Export);
        owner.granted().unwrap();
        let (resume, wait) = mpsc::channel();
        let result = ticket.wait_grant().unwrap().submit(Box::new(move |_| {
            wait.recv_timeout(Duration::from_secs(5)).unwrap();
            Ok(NativeReportSave {status:"cancelled",filename:None})
        })).unwrap();
        assert!(!owner.poll(false).unwrap());
        assert!(!owner.poll(true).unwrap());
        assert!(matches!(result.try_recv(),Err(TryRecvError::Empty)));
        resume.send(()).unwrap();
        let deadline = std::time::Instant::now()+Duration::from_secs(5);
        while !owner.poll(true).unwrap() {
            assert!(std::time::Instant::now()<deadline);
            thread::yield_now();
        }
        assert!(matches!(result.try_recv(),Err(TryRecvError::Empty)));
        owner.released().unwrap();
        assert_eq!(result.recv().unwrap().unwrap().status,"cancelled");
    }
}
