//! Production desktop profile admission. This coordinates cooperating
//! desktops and rejects existing redirects/override configuration; it does
//! not establish independent browser FileIO coverage or an OS sandbox.
use crate::storage_boundary::{prepare_directory, validate_existing_directory};
use std::ffi::OsStr;
use std::fs::{self, File, OpenOptions};
use std::path::{Path, PathBuf};

const LOCK_NAME: &str = ".pilotodin-desktop.lock";
const UNSAFE: &str = "Desktop profile storage is unavailable or unsafe";
const BUSY: &str = "PilotODIN desktop workspace is already in use or unavailable";
const OVERRIDE: &str = "Unsupported WebView2 startup override; review configuration before opening PilotODIN";

pub struct DesktopProfileLease {
    _file: File,
}

fn reject_environment<'a>(keys: impl IntoIterator<Item = &'a OsStr>) -> Result<(), String> {
    for key in keys {
        if key.to_string_lossy().to_ascii_uppercase().starts_with("WEBVIEW2_") {
            return Err(OVERRIDE.into());
        }
    }
    Ok(())
}

#[cfg(windows)]
mod windows {
    use super::*;
    use std::ffi::c_void;
    use std::os::windows::fs::{MetadataExt, OpenOptionsExt};
    use std::os::windows::io::AsRawHandle;

    #[repr(C)]
    struct FileTime { low: u32, high: u32 }
    #[repr(C)]
    struct FileInformation {
        attributes: u32, created: FileTime, accessed: FileTime, written: FileTime,
        volume_serial: u32, size_high: u32, size_low: u32, links: u32,
        index_high: u32, index_low: u32,
    }

    #[link(name = "kernel32")]
    extern "system" {
        fn GetFileInformationByHandle(file: *mut c_void, info: *mut FileInformation) -> i32;
        fn GetFileType(file: *mut c_void) -> u32;
    }
    #[link(name = "advapi32")]
    extern "system" {
        fn RegOpenKeyExW(key: *mut c_void, subkey: *const u16, options: u32,
                         access: u32, result: *mut *mut c_void) -> i32;
        fn RegCloseKey(key: *mut c_void) -> i32;
    }

    pub fn check_named_file(info: &fs::Metadata) -> Result<(), String> {
        if !info.is_file() || info.file_type().is_symlink()
            || info.file_attributes() & 0x400 != 0 || info.len() != 0 {
            return Err(UNSAFE.into());
        }
        Ok(())
    }

    pub fn open_lease(path: &Path) -> Result<File, String> {
        // No sharing or delete sharing, no truncate, open the final reparse
        // object itself. The original owned handle is the lease.
        let file = OpenOptions::new().read(true).write(true).create(true)
            .truncate(false).share_mode(0).custom_flags(0x00200000)
            .open(path).map_err(|_| BUSY.to_string())?;
        let handle = file.as_raw_handle();
        let mut information = std::mem::MaybeUninit::<FileInformation>::uninit();
        // The handle belongs to this File and remains open throughout.
        let info = unsafe {
            if GetFileType(handle) != 1
                || GetFileInformationByHandle(handle, information.as_mut_ptr()) == 0 {
                return Err(UNSAFE.into());
            }
            information.assume_init()
        };
        if info.attributes & (0x400 | 0x10) != 0 || info.links != 1
            || info.size_high != 0 || info.size_low != 0
            || (info.index_high == 0 && info.index_low == 0) {
            return Err(UNSAFE.into());
        }
        Ok(file)
    }

    pub fn reject_registry_overrides() -> Result<(), String> {
        // Read-only, both roots and registry views. Conservative: a key
        // containing an override class is not accepted even if intended for
        // another application. Never edit enterprise policy or read its data.
        let classes = ["UserDataFolder", "BrowserExecutableFolder",
            "AdditionalBrowserArguments", "ReleaseChannelPreference",
            "ChannelSearchKind", "ReleaseChannels"];
        for root in [0x80000001u32, 0x80000002u32] {
            let key = (root as i32 as isize) as *mut c_void;
            for view in [0x100u32, 0x200u32] {
                for class in classes {
                    let name: Vec<u16> = format!(
                        r"SOFTWARE\Policies\Microsoft\Edge\WebView2\{}", class
                    ).encode_utf16().chain(std::iter::once(0)).collect();
                    let mut opened = std::ptr::null_mut();
                    // KEY_QUERY_VALUE | KEY_WOW64_64KEY or KEY_WOW64_32KEY.
                    let result = unsafe { RegOpenKeyExW(key, name.as_ptr(), 0,
                        0x0001 | view, &mut opened) };
                    match result {
                        2 | 3 => {}, // documented file/path not found
                        0 => {
                            let _ = unsafe { RegCloseKey(opened) };
                            return Err(OVERRIDE.into());
                        }
                        _ => return Err(OVERRIDE.into()), // inaccessible/unknown
                    }
                }
            }
        }
        Ok(())
    }
}

#[cfg(not(windows))]
mod windows {
    use super::*;
    #[cfg(unix)]
    use std::os::unix::fs::MetadataExt;

    pub fn check_named_file(info: &fs::Metadata) -> Result<(), String> {
        if !info.is_file() || info.file_type().is_symlink() || info.len() != 0 {
            return Err(UNSAFE.into());
        }
        #[cfg(unix)]
        if info.nlink() != 1 { return Err(UNSAFE.into()); }
        Ok(())
    }

    pub fn open_lease(path: &Path) -> Result<File, String> {
        let file = OpenOptions::new().read(true).write(true).create(true)
            .truncate(false).open(path).map_err(|_| BUSY.to_string())?;
        file.try_lock().map_err(|_| BUSY.to_string())?;
        let opened = file.metadata().map_err(|_| UNSAFE.to_string())?;
        let named = fs::symlink_metadata(path).map_err(|_| UNSAFE.to_string())?;
        check_named_file(&opened)?;
        check_named_file(&named)?;
        #[cfg(unix)]
        if opened.dev() != named.dev() || opened.ino() != named.ino() {
            return Err(UNSAFE.into());
        }
        Ok(file)
    }

    pub fn reject_registry_overrides() -> Result<(), String> { Ok(()) }
}

fn acquire(root: &Path) -> Result<DesktopProfileLease, String> {
    validate_existing_directory(root)?;
    let marker = root.join(LOCK_NAME);
    match fs::symlink_metadata(&marker) {
        Ok(info) => windows::check_named_file(&info)?,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {},
        Err(_) => return Err(UNSAFE.into()),
    }
    let file = windows::open_lease(&marker)?;
    validate_existing_directory(root)?;
    Ok(DesktopProfileLease { _file: file })
}

/// Use exactly the existing Tauri app-local profile root. No relocation,
/// reset, browser flags, process-wide env edits or policy modifications.
pub fn prepare_production_profile(root: &Path) -> Result<(PathBuf, DesktopProfileLease), String> {
    let keys: Vec<_> = std::env::vars_os().map(|(key, _)| key).collect();
    reject_environment(keys.iter().map(|key| key.as_os_str()))?;
    windows::reject_registry_overrides()?;
    let root = prepare_directory(root)?;
    let lease = acquire(&root)?;
    Ok((root, lease))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};
    static SERIAL: AtomicUsize = AtomicUsize::new(0);
    struct Fixture(PathBuf);
    impl Fixture {
        fn new() -> Self {
            let base = std::env::temp_dir();
            #[cfg(not(windows))]
            let base = base.canonicalize().unwrap();
            let root = base.join(format!("pilotodin-profile-lease-{}-{}",
                std::process::id(), SERIAL.fetch_add(1, Ordering::Relaxed)));
            fs::create_dir(&root).unwrap();
            Self(root)
        }
    }
    impl Drop for Fixture {
        fn drop(&mut self) { let _ = fs::remove_dir_all(&self.0); }
    }

    #[test]
    fn competing_lease_refused_then_reusable_without_marker_removal() {
        let root = Fixture::new();
        let first = acquire(&root.0).unwrap();
        assert!(acquire(&root.0).is_err());
        drop(first);
        let second = acquire(&root.0).unwrap();
        drop(second);
        assert_eq!(fs::metadata(root.0.join(LOCK_NAME)).unwrap().len(), 0);
    }
    #[test]
    fn distinct_roots_do_not_contend() {
        let one = Fixture::new();
        let two = Fixture::new();
        let _a = acquire(&one.0).unwrap();
        let _b = acquire(&two.0).unwrap();
    }
    #[test]
    fn preserves_unknown_nonempty_marker() {
        let root = Fixture::new();
        let marker = root.0.join(LOCK_NAME);
        fs::write(&marker, b"preserve").unwrap();
        assert!(acquire(&root.0).is_err());
        assert_eq!(fs::read(marker).unwrap(), b"preserve");
    }
    #[test]
    fn rejects_hardlinked_marker_without_mutation() {
        let root = Fixture::new();
        let target = root.0.join("unrelated");
        File::create(&target).unwrap();
        fs::hard_link(&target, root.0.join(LOCK_NAME)).unwrap();
        assert!(acquire(&root.0).is_err());
        assert_eq!(fs::metadata(target).unwrap().len(), 0);
    }
    #[cfg(unix)]
    #[test]
    fn rejects_redirected_marker_and_root() {
        use std::os::unix::fs::symlink;
        let root = Fixture::new();
        let target = root.0.join("unrelated");
        File::create(&target).unwrap();
        symlink(&target, root.0.join(LOCK_NAME)).unwrap();
        assert!(acquire(&root.0).is_err());
        let alias = root.0.join("alias");
        symlink(&root.0, &alias).unwrap();
        assert!(acquire(&alias).is_err());
        assert_eq!(fs::metadata(target).unwrap().len(), 0);
    }
    #[test]
    fn environment_override_is_rejected_case_insensitively() {
        assert!(reject_environment([OsStr::new("TEMP"), OsStr::new("PATH")]).is_ok());
        for key in ["WEBVIEW2_USER_DATA_FOLDER", "webview2_additional_browser_arguments",
                    "WebView2_Browser_Executable_Folder", "WEBVIEW2_UNKNOWN"] {
            assert!(reject_environment([OsStr::new(key)]).is_err());
        }
    }
}
