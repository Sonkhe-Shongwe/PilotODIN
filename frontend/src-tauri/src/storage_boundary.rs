//! Shared pre-spawn directory policy for app-owned worker storage.
//! Existing components are inspected without following reparse points.
//! Retained original directory handles supplement path checks, not an OS sandbox.
use std::fs::{self, File};
use std::path::{Component, Path, PathBuf};

const INVALID: &str = "Worker storage directory unavailable or unsafe";
const REDIRECTED: &str = "Worker storage directory is redirected or invalid";

fn redirected(metadata: &fs::Metadata) -> bool {
    if metadata.file_type().is_symlink() {
        return true;
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        // FILE_ATTRIBUTE_REPARSE_POINT: includes junctions and mount points.
        if metadata.file_attributes() & 0x400 != 0 {
            return true;
        }
    }
    false
}

fn check_directory(path: &Path) -> Result<(), String> {
    let metadata = fs::symlink_metadata(path).map_err(|_| INVALID.to_string())?;
    if redirected(&metadata) || !metadata.is_dir() {
        return Err(REDIRECTED.into());
    }
    Ok(())
}

fn check_path_shape(path: &Path) -> Result<(), String> {
    if !path.is_absolute() {
        return Err(INVALID.into());
    }
    for part in path.components() {
        match part {
            Component::ParentDir | Component::CurDir => return Err(INVALID.into()),
            Component::Prefix(prefix) => {
                // Only ordinary local drive syntax. UNC/device/verbatim
                // paths must not be silently passed to the Python entrypoint.
                if !matches!(prefix.kind(), std::path::Prefix::Disk(_)) {
                    return Err(INVALID.into());
                }
            }
            Component::Normal(name) => {
                #[cfg(windows)]
                {
                    let name = name.to_str().ok_or_else(|| INVALID.to_string())?;
                    let stem = name.split('.').next().unwrap_or("")
                        .trim_end_matches(' ').to_ascii_uppercase();
                    let reserved = matches!(stem.as_str(), "CON" | "PRN" | "AUX" | "NUL"
                        | "CONIN$" | "CONOUT$")
                        || (stem.len() == 4
                            && (stem.starts_with("COM") || stem.starts_with("LPT"))
                            && stem.as_bytes()[3].is_ascii_digit());
                    if reserved || name.contains(':') || name.ends_with(' ')
                        || name.ends_with('.') {
                        return Err(INVALID.into());
                    }
                }
                #[cfg(not(windows))]
                let _ = name;
            }
            Component::RootDir => {}
        }
    }
    Ok(())
}

/// Inspect all existing components from the volume root down. Do not create
/// directories or follow pre-existing links to determine whether they are safe.
pub fn validate_existing_directory(path: &Path) -> Result<(), String> {
    check_path_shape(path)?;
    let mut current = PathBuf::new();
    for part in path.components() {
        current.push(part.as_os_str());
        if !matches!(part, Component::Prefix(_)) {
            check_directory(&current)?;
        }
    }
    Ok(())
}

#[cfg(windows)]
mod handles {
    use super::*;
    use std::ffi::c_void;
    use std::fs::OpenOptions;
    use std::os::windows::fs::OpenOptionsExt;
    use std::os::windows::io::AsRawHandle;

    #[repr(C)]
    struct AttributeTag { attributes: u32, tag: u32 }
    #[repr(C)]
    struct FileId { volume: u64, identifier: [u8; 16] }

    #[link(name = "kernel32")]
    extern "system" {
        fn GetFileInformationByHandleEx(file: *mut c_void, class: i32,
            buffer: *mut c_void, size: u32) -> i32;
    }

    pub type Identity = (u64, [u8; 16]);

    pub fn open(path: &Path) -> Result<File, String> {
        // FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES; no delete sharing.
        // OPEN_EXISTING, BACKUP_SEMANTICS | OPEN_REPARSE_POINT.
        OpenOptions::new().read(true).access_mode(0x81).share_mode(0x3)
            .custom_flags(0x02200000).open(path).map_err(|_| INVALID.into())
    }

    pub fn identity(file: &File) -> Result<Identity, String> {
        let mut attr = AttributeTag { attributes: 0, tag: 0 };
        let mut id = FileId { volume: 0, identifier: [0; 16] };
        let handle = file.as_raw_handle();
        let ok = unsafe {
            GetFileInformationByHandleEx(handle, 9, (&mut attr as *mut AttributeTag).cast(),
                std::mem::size_of::<AttributeTag>() as u32) != 0
            && GetFileInformationByHandleEx(handle, 18, (&mut id as *mut FileId).cast(),
                std::mem::size_of::<FileId>() as u32) != 0
        };
        if !ok || attr.attributes & 0x10 == 0 || attr.attributes & 0x400 != 0
            || id.identifier.iter().all(|byte| *byte == 0) {
            return Err(INVALID.into());
        }
        Ok((id.volume, id.identifier))
    }
}

#[cfg(unix)]
mod handles {
    use super::*;
    use std::os::unix::fs::MetadataExt;
    pub type Identity = (u64, u64);
    // Named entry checked before/after open; POSIX does not block rename.
    pub fn open(path: &Path) -> Result<File, String> {
        File::open(path).map_err(|_| INVALID.into())
    }
    pub fn identity(file: &File) -> Result<Identity, String> {
        let info = file.metadata().map_err(|_| INVALID.to_string())?;
        if !info.is_dir() || info.ino() == 0 { return Err(INVALID.into()); }
        Ok((info.dev(), info.ino()))
    }
}

struct DirectoryPin {
    path: PathBuf,
    file: File,
    identity: handles::Identity,
}
impl DirectoryPin {
    fn open(path: &Path) -> Result<Self, String> {
        check_directory(path)?;
        let file = handles::open(path)?;
        let identity = handles::identity(&file)?;
        let pin = Self { path: path.to_path_buf(), file, identity };
        pin.verify()?;
        Ok(pin)
    }
    fn verify(&self) -> Result<(), String> {
        check_directory(&self.path)?;
        let named = handles::open(&self.path)?;
        if handles::identity(&self.file)? != self.identity
            || handles::identity(&named)? != self.identity {
            return Err("Owned directory identity changed".into());
        }
        check_directory(&self.path)
    }
}

/// Retain the actual directories used by one profile or worker. Windows
/// prevents ordinary deletion/rename while held; POSIX detects observed
/// identity changes. RAII closes handles including on admission failure.
#[derive(Default)]
pub struct DirectoryPins {
    entries: Vec<DirectoryPin>,
}
impl DirectoryPins {
    pub fn verify(&self) -> Result<(), String> {
        for pin in &self.entries { pin.verify()?; }
        Ok(())
    }
    pub fn admit_existing(&mut self, path: &Path) -> Result<(), String> {
        check_path_shape(path)?;
        let mut current = PathBuf::new();
        for part in path.components() {
            current.push(part.as_os_str());
            if matches!(part, Component::Prefix(_)) { continue; }
            if let Some(pin) = self.entries.iter().find(|pin| pin.path == current) {
                pin.verify()?;
                continue;
            }
            let pin = DirectoryPin::open(&current)?;
            if self.entries.first().is_some_and(|first| first.identity.0 != pin.identity.0) {
                return Err("Owned directory volume changed".into());
            }
            self.entries.push(pin);
        }
        self.verify()
    }
    pub fn prepare(&mut self, path: &Path) -> Result<PathBuf, String> {
        check_path_shape(path)?;
        let parent = path.parent().ok_or_else(|| INVALID.to_string())?;
        self.admit_existing(parent)?;
        let prepared = prepare_directory(path)?;
        self.admit_existing(&prepared)?;
        Ok(prepared)
    }
    pub fn prepare_worker_temp(&mut self, home: &Path, name: &str) -> Result<PathBuf, String> {
        if !matches!(name, "backend-temp" | "inference-temp") {
            return Err("Unexpected worker temporary directory".into());
        }
        self.prepare(&home.join(name))
    }
    pub fn verify_path(&self, path: &Path) -> Result<(), String> {
        if !self.entries.iter().any(|pin| pin.path == path) {
            return Err("Directory was not admitted".into());
        }
        self.verify()
    }
}

/// Admit an existing directory or create ONLY its missing final component
/// after verifying all ancestors. Return the original spelling; Windows
/// canonicalize uses a verbatim prefix unsuitable for some child interfaces.
/// A second check narrows, but cannot eliminate, concurrent replacement races.
pub fn prepare_directory(path: &Path) -> Result<PathBuf, String> {
    check_path_shape(path)?;
    let parent = path.parent().ok_or_else(|| INVALID.to_string())?;
    validate_existing_directory(parent)?;
    let before = parent.canonicalize().map_err(|_| INVALID.to_string())?;
    match fs::symlink_metadata(path) {
        Ok(info) => {
            if redirected(&info) || !info.is_dir() {
                return Err(REDIRECTED.into());
            }
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            match fs::create_dir(path) {
                Ok(()) => {}
                Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => {}
                Err(_) => return Err(INVALID.into()),
            }
        }
        Err(_) => return Err(INVALID.into()),
    }
    validate_existing_directory(path)?;
    let after = parent.canonicalize().map_err(|_| INVALID.to_string())?;
    let resolved = path.canonicalize().map_err(|_| INVALID.to_string())?;
    if before != after || resolved.parent() != Some(after.as_path()) {
        return Err("Worker storage directory escapes verified parent".into());
    }
    Ok(path.to_path_buf())
}

pub fn prepare_worker_temp(home: &Path, name: &str) -> Result<PathBuf, String> {
    if !matches!(name, "backend-temp" | "inference-temp") {
        return Err("Unexpected worker temporary directory".into());
    }
    validate_existing_directory(home)?;
    prepare_directory(&home.join(name))
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
            let root = base.join(format!("pilotodin-storage-policy-{}-{}",
                std::process::id(), SERIAL.fetch_add(1, Ordering::Relaxed)));
            fs::create_dir(&root).unwrap();
            Self(root)
        }
    }
    impl Drop for Fixture {
        fn drop(&mut self) { let _ = fs::remove_dir_all(&self.0); }
    }

    #[test]
    fn retained_chain_preserves_identity_and_releases_handles() {
        let fixture = Fixture::new();
        let parent = fixture.0.join("app");
        let mut pins = DirectoryPins::default();
        pins.prepare(&parent).unwrap();
        let scratch = pins.prepare_worker_temp(&parent, "backend-temp").unwrap();
        pins.verify_path(&scratch).unwrap();
        assert!(pins.verify_path(&parent.join("unadmitted")).is_err());
        let moved = fixture.0.join("moved");
        #[cfg(windows)]
        {
            assert!(fs::rename(&parent, &moved).is_err());
            pins.verify().unwrap();
        }
        #[cfg(unix)]
        {
            fs::rename(&parent, &moved).unwrap();
            fs::create_dir(&parent).unwrap();
            assert!(pins.verify().is_err());
            fs::remove_dir(&parent).unwrap();
            fs::rename(&moved, &parent).unwrap();
            pins.verify().unwrap();
        }
        drop(pins);
        fs::rename(&parent, &moved).unwrap();
        assert!(moved.join("backend-temp").is_dir());
    }

    #[test]
    fn retained_chain_rejects_missing_parent_without_creation() {
        let fixture = Fixture::new();
        let mut pins = DirectoryPins::default();
        let absent = fixture.0.join("missing");
        assert!(pins.prepare(&absent.join("data")).is_err());
        assert!(!absent.exists());
    }

    #[test]
    fn creates_only_owned_final_components_and_preserves_spelling() {
        let fixture = Fixture::new();
        let root = fixture.0.join("app");
        assert_eq!(prepare_directory(&root).unwrap(), root);
        let home = prepare_directory(&root.join("data")).unwrap();
        assert_eq!(prepare_directory(&home).unwrap(), home);
        let backend = prepare_worker_temp(&home, "backend-temp").unwrap();
        let inference = prepare_worker_temp(&home, "inference-temp").unwrap();
        assert_eq!(backend.parent(), Some(home.as_path()));
        assert_eq!(inference.parent(), Some(home.as_path()));
        assert_ne!(backend, inference);
        assert!(backend.is_dir() && inference.is_dir());
    }

    #[test]
    fn refuses_missing_ancestor_without_creating_it() {
        let fixture = Fixture::new();
        let missing = fixture.0.join("missing");
        assert!(prepare_directory(&missing.join("data")).is_err());
        assert!(!missing.exists());
    }

    #[test]
    fn refuses_relative_parent_traversal_and_unreviewed_scratch_names() {
        let fixture = Fixture::new();
        assert!(prepare_directory(Path::new("relative")).is_err());
        assert!(prepare_directory(&fixture.0.join("..").join("other")).is_err());
        assert!(prepare_worker_temp(&fixture.0, "../other").is_err());
        assert!(prepare_worker_temp(&fixture.0, "export_tmp").is_err());
        assert_eq!(fs::read_dir(&fixture.0).unwrap().count(), 0);
    }

    #[test]
    fn preserves_wrong_type_existing_path_and_refuses_child() {
        let fixture = Fixture::new();
        let wrong = fixture.0.join("wrong");
        fs::write(&wrong, b"preserve").unwrap();
        assert!(prepare_directory(&wrong).is_err());
        assert!(prepare_directory(&wrong.join("child")).is_err());
        assert_eq!(fs::read(&wrong).unwrap(), b"preserve");
    }

    #[cfg(unix)]
    #[test]
    fn rejects_redirected_ancestor_before_creating_any_descendant() {
        use std::os::unix::fs::symlink;
        let fixture = Fixture::new();
        let outside = fixture.0.join("outside");
        fs::create_dir(&outside).unwrap();
        let alias = fixture.0.join("alias");
        symlink(&outside, &alias).unwrap();
        assert!(prepare_directory(&alias.join("data")).is_err());
        assert!(!outside.join("data").exists());
    }

    #[cfg(unix)]
    #[test]
    fn rejects_even_same_parent_alias_and_broken_link() {
        use std::os::unix::fs::symlink;
        let fixture = Fixture::new();
        let target = fixture.0.join("other");
        fs::create_dir(&target).unwrap();
        symlink(&target, fixture.0.join("backend-temp")).unwrap();
        assert!(prepare_worker_temp(&fixture.0, "backend-temp").is_err());
        assert_eq!(fs::read_dir(&target).unwrap().count(), 0);
        let missing = fixture.0.join("absent");
        symlink(&missing, fixture.0.join("inference-temp")).unwrap();
        assert!(prepare_worker_temp(&fixture.0, "inference-temp").is_err());
        assert!(!missing.exists());
    }

    #[cfg(windows)]
    #[test]
    fn rejects_nonlocal_and_ambiguous_windows_path_shapes() {
        for value in [r"C:relative", r"\\server\share\data", r"\\?\C:\data",
                      r"C:\data:stream", r"C:\NUL.txt", r"C:\data.",
                      r"C:\data ", r"C:\data\..\elsewhere"] {
            assert!(check_path_shape(Path::new(value)).is_err());
        }
    }
}
