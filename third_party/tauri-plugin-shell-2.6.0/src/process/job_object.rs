// Copyright 2019-2023 Tauri Programme within The Commons Conservancy
// SPDX-License-Identifier: Apache-2.0
// SPDX-License-Identifier: MIT

// Modified by PilotODIN (2026-11-24): retained own-job accounting query and
// best-effort termination on a failed resume. Upstream licence retained.

//! Job object backing `process_group` on Windows, adapted from
//! [process-wrap](https://github.com/watchexec/process-wrap) (Apache-2.0 OR MIT).

use std::{io, mem, os::windows::io::AsRawHandle, process::Child, ptr};

use windows_sys::Win32::{
    Foundation::{CloseHandle, HANDLE, INVALID_HANDLE_VALUE},
    System::{
        Diagnostics::ToolHelp::{
            CreateToolhelp32Snapshot, TH32CS_SNAPTHREAD, THREADENTRY32, Thread32First, Thread32Next,
        },
        JobObjects::{
            AssignProcessToJobObject, CreateJobObjectW, TerminateJobObject,
            QueryInformationJobObject, JobObjectBasicAccountingInformation,
            JOBOBJECT_BASIC_ACCOUNTING_INFORMATION,
        },
        Threading::{OpenThread, ResumeThread, THREAD_SUSPEND_RESUME},
    },
};

/// Owned job object handle. Closing it leaves the processes in the job running.
#[derive(Debug)]
pub(crate) struct JobObject(
    HANDLE,
    #[cfg(feature = "dla-qa-listener")] std::os::windows::io::OwnedHandle,
);

// SAFETY: the handle is only ever passed to thread-safe Win32 calls.
unsafe impl Send for JobObject {}
unsafe impl Sync for JobObject {}

impl JobObject {
    /// Creates a job object, assigns the `CREATE_SUSPENDED` `child` to it and resumes the child.
    pub(crate) fn assign(child: &Child) -> io::Result<Self> {
        // Duplicate the original suspended process handle, not a PID lookup.
        // On ordinary builds this optional QA feature is disabled.
        #[cfg(feature = "dla-qa-listener")]
        let original = {
            use std::os::windows::io::AsHandle;
            child.as_handle().try_clone_to_owned()?
        };
        let job = unsafe { CreateJobObjectW(ptr::null(), ptr::null()) };
        if job.is_null() {
            return Err(io::Error::last_os_error());
        }
        let job = Self(job, #[cfg(feature = "dla-qa-listener")] original);
        if unsafe { AssignProcessToJobObject(job.0, child.as_raw_handle()) } == 0 {
            return Err(io::Error::last_os_error());
        }
        if let Err(error) = resume_threads(child.id()) {
            // Some threads could already have resumed. Do not merely close
            // the job and leave descendants behind; the caller still treats
            // this spawn as uncertain, even if termination succeeds.
            let _ = job.terminate();
            return Err(error);
        }
        Ok(job)
    }

    /// Query only this already-owned unnamed job; no PID or handle lookup.
    /// A failed or incomplete accounting query is never interpreted as zero.
    pub(crate) fn active_processes(&self) -> io::Result<u32> {
        let mut info: JOBOBJECT_BASIC_ACCOUNTING_INFORMATION = unsafe { mem::zeroed() };
        let size = mem::size_of::<JOBOBJECT_BASIC_ACCOUNTING_INFORMATION>() as u32;
        let mut returned = 0u32;
        if unsafe {
            QueryInformationJobObject(
                self.0,
                JobObjectBasicAccountingInformation,
                (&mut info as *mut JOBOBJECT_BASIC_ACCOUNTING_INFORMATION).cast(),
                size,
                &mut returned,
            )
        } == 0 {
            return Err(io::Error::last_os_error());
        }
        if returned != size {
            return Err(io::Error::new(io::ErrorKind::InvalidData,
                "Incomplete owned job accounting information"));
        }
        Ok(info.ActiveProcesses)
    }

    #[cfg(feature = "dla-qa-listener")]
    pub(crate) fn qa_identity(&self) -> io::Result<(u32, u64)> {
        use windows_sys::Win32::{Foundation::FILETIME,
            System::Threading::{GetProcessId, GetProcessTimes}};
        let handle = self.1.as_raw_handle();
        let pid = unsafe { GetProcessId(handle) };
        let mut created: FILETIME = unsafe { mem::zeroed() };
        let mut exited = created;
        let mut kernel = created;
        let mut user = created;
        if pid == 0 || unsafe {
            GetProcessTimes(handle, &mut created, &mut exited, &mut kernel, &mut user)
        } == 0 {
            return Err(io::Error::last_os_error());
        }
        let created = (u64::from(created.dwHighDateTime) << 32) |
            u64::from(created.dwLowDateTime);
        if created == 0 { return Err(qa_listener::fault()); }
        Ok((pid, created))
    }

    #[cfg(feature = "dla-qa-listener")]
    pub(crate) fn qa_listener_owned(&self, pid: u32, created: u64, port: u16)
        -> io::Result<bool>
    {
        use windows_sys::Win32::{Foundation::WAIT_TIMEOUT,
            System::{JobObjects::IsProcessInJob, Threading::WaitForSingleObject}};
        let handle = self.1.as_raw_handle();
        let live = || -> io::Result<bool> {
            let mut member = 0;
            if unsafe { IsProcessInJob(handle, self.0, &mut member) } == 0 {
                return Err(io::Error::last_os_error());
            }
            Ok(self.qa_identity()? == (pid, created) && member != 0 &&
                unsafe { WaitForSingleObject(handle, 0) } == WAIT_TIMEOUT)
        };
        if port < 1024 || !live()? { return Ok(false); }
        let matches = qa_listener::observe(pid, port, false)?;
        Ok(matches && live()?)
    }

    #[cfg(feature = "dla-qa-listener")]
    pub(crate) fn qa_listener_absent(&self, pid: u32, created: u64, port: u16)
        -> io::Result<bool>
    {
        use windows_sys::Win32::{Foundation::WAIT_OBJECT_0,
            System::Threading::WaitForSingleObject};
        if port < 1024 || self.qa_identity()? != (pid, created) ||
            unsafe { WaitForSingleObject(self.1.as_raw_handle(), 0) } != WAIT_OBJECT_0 ||
            self.active_processes()? != 0 {
            return Ok(false);
        }
        let absent = qa_listener::observe(pid, port, true)?;
        Ok(absent && self.active_processes()? == 0 &&
            self.qa_identity()? == (pid, created) &&
            unsafe { WaitForSingleObject(self.1.as_raw_handle(), 0) } == WAIT_OBJECT_0)
    }

    pub(crate) fn terminate(&self) -> io::Result<()> {
        if unsafe { TerminateJobObject(self.0, 1) } == 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }
}

// Private, opt-in QA implementation using the documented IP Helper API.
// No network requests, raw endpoint output, arbitrary process opening,
// termination or public handle export. Source only, not native proof.
#[cfg(feature = "dla-qa-listener")]
mod qa_listener {
    use std::{ffi::c_void, io};
    const AF_INET: u32 = 2;
    const AF_INET6: u32 = 23;
    const TCP_TABLE_OWNER_PID_LISTENER: u32 = 3;
    const ERROR_INSUFFICIENT_BUFFER: u32 = 122;
    const MAX_TABLE_BYTES: u32 = 1024 * 1024;
    const LISTEN: u32 = 2;

    #[link(name = "iphlpapi")]
    unsafe extern "system" {
        fn GetExtendedTcpTable(table: *mut c_void, size: *mut u32,
            order: i32, family: u32, class: u32, reserved: u32) -> u32;
    }

    pub(super) fn fault() -> io::Error {
        io::Error::new(io::ErrorKind::InvalidData, "Unconfirmed QA listener identity")
    }

    // MIB_TCPTABLE_OWNER_PID and MIB_TCP6TABLE_OWNER_PID consist of a
    // DWORD count and DWORD-aligned rows (6 and 14 DWORDs respectively).
    // Bound allocation, reject incomplete/changing/unsupported results.
    fn table(family: u32, width: usize) -> io::Result<Vec<u32>> {
        let mut size = 0u32;
        let code = unsafe { GetExtendedTcpTable(std::ptr::null_mut(), &mut size,
            0, family, TCP_TABLE_OWNER_PID_LISTENER, 0) };
        if code != ERROR_INSUFFICIENT_BUFFER || !(4..=MAX_TABLE_BYTES).contains(&size) {
            return Err(fault());
        }
        let mut words = vec![0u32; (size as usize).div_ceil(4)];
        let capacity = words.len() * 4;
        let code = unsafe { GetExtendedTcpTable(words.as_mut_ptr().cast(), &mut size,
            0, family, TCP_TABLE_OWNER_PID_LISTENER, 0) };
        if code != 0 || size as usize > capacity || size < 4 { return Err(fault()); }
        let count = words[0] as usize;
        let used = count.checked_mul(width).and_then(|n| n.checked_add(1))
            .ok_or_else(fault)?;
        if used > words.len() || used * 4 > size as usize { return Err(fault()); }
        words.truncate(used);
        Ok(words)
    }

    fn classify(v4: &[u32], v6: &[u32], pid: u32, port: u16, absent: bool)
        -> io::Result<bool>
    {
        if v4.is_empty() || v6.is_empty() ||
            (v4.len()-1) % 6 != 0 || (v6.len()-1) % 14 != 0 ||
            v4[0] as usize != (v4.len()-1)/6 ||
            v6[0] as usize != (v6.len()-1)/14 { return Err(fault()); }
        let mut matches = 0;
        for row in v4[1..].chunks_exact(6) {
            if row[0] != LISTEN { return Err(fault()); }
            let row_port = u16::from_be(row[2] as u16);
            if row[5] == pid || row_port == port {
                if absent || row[5] != pid || row_port != port ||
                    row[1].to_ne_bytes() != [127, 0, 0, 1] {
                    return Ok(false);
                }
                matches += 1;
            }
        }
        for row in v6[1..].chunks_exact(14) {
            if row[12] != LISTEN { return Err(fault()); }
            if row[13] == pid || u16::from_be(row[5] as u16) == port {
                return Ok(false);
            }
        }
        Ok(if absent { matches == 0 } else { matches == 1 })
    }

    pub(super) fn observe(pid: u32, port: u16, absent: bool) -> io::Result<bool> {
        let v4 = table(AF_INET, 6)?;
        let v6 = table(AF_INET6, 14)?;
        classify(&v4, &v6, pid, port, absent)
    }

    #[cfg(test)]
    mod tests {
        use super::*;
        #[test]
        fn strict_loopback_and_absence() {
            let port = 43210u16;
            let row = [1, LISTEN, u32::from_ne_bytes([127,0,0,1]),
                u32::from(port.to_be()), 0, 0, 42];
            assert!(classify(&row, &[0], 42, port, false).unwrap());
            assert!(!classify(&row, &[0], 42, port, true).unwrap());
            assert!(classify(&[0], &[0], 42, port, true).unwrap());
            let mut foreign = row;
            foreign[6] = 43;
            assert!(!classify(&foreign, &[0], 42, port, false).unwrap());
            let mut wildcard = row;
            wildcard[2] = 0;
            assert!(!classify(&wildcard, &[0], 42, port, false).unwrap());
            let mut v6 = [0u32; 15];
            v6[0] = 1; v6[6] = u32::from(port.to_be());
            v6[13] = LISTEN; v6[14] = 43;
            assert!(!classify(&row, &v6, 42, port, false).unwrap());
            assert!(classify(&[1], &[0], 42, port, true).is_err());
        }
    }
}

impl Drop for JobObject {
    fn drop(&mut self) {
        unsafe { CloseHandle(self.0) };
    }
}

/// `std` closes the main thread handle right after `CreateProcess`, so a suspended
/// child can only be resumed by looking its threads up again.
fn resume_threads(pid: u32) -> io::Result<()> {
    let snapshot = unsafe { CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0) };
    if snapshot == INVALID_HANDLE_VALUE {
        return Err(io::Error::last_os_error());
    }
    let result = resume_snapshot_threads(snapshot, pid);
    unsafe { CloseHandle(snapshot) };
    result
}

fn resume_snapshot_threads(snapshot: HANDLE, pid: u32) -> io::Result<()> {
    let mut entry: THREADENTRY32 = unsafe { mem::zeroed() };
    entry.dwSize = mem::size_of::<THREADENTRY32>() as u32;
    let mut found = unsafe { Thread32First(snapshot, &mut entry) } != 0;
    while found {
        if entry.th32OwnerProcessID == pid {
            let thread = unsafe { OpenThread(THREAD_SUSPEND_RESUME, 0, entry.th32ThreadID) };
            if thread.is_null() {
                return Err(io::Error::last_os_error());
            }
            if unsafe { ResumeThread(thread) } == u32::MAX {
                let err = io::Error::last_os_error();
                unsafe { CloseHandle(thread) };
                return Err(err);
            }
            unsafe { CloseHandle(thread) };
        }
        found = unsafe { Thread32Next(snapshot, &mut entry) } != 0;
    }
    Ok(())
}
