//! B5 native dataset Save As source candidate. Not registered in the host yet.
//!
//! Only the future OS-dialog command may supply a destination and trusted root
//! lists. Existing files are deliberately refused. No arbitrary IPC path,
//! overwrite, directory creation, archive extraction or broad file capability.
//! Requires separate approved host compile before integration is certified.
use crate::storage_boundary::DirectoryPins;
use sha2::{Digest, Sha256};
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};

pub(crate) const MAX_BYTES: usize = 75 * 1024 * 1024;
const INVALID: &str = "Dataset export payload does not match its verified format";
const UNSAFE: &str = "Selected dataset destination is unavailable or unsafe";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Format { Csv, Xlsx }
impl Format {
    pub(crate) fn parse(value: &str) -> Result<Self, String> {
        match value {
            "csv" => Ok(Self::Csv), "xlsx" => Ok(Self::Xlsx),
            _ => Err("Choose CSV or XLSX".into()),
        }
    }
    pub(crate) fn extension(self) -> &'static str {
        match self { Self::Csv => "csv", Self::Xlsx => "xlsx" }
    }
}

pub(crate) struct Validated<'a> {
    format: Format,
    bytes: &'a [u8],
}

fn generated_name(name: &str, format: Format, version: u64) -> bool {
    let extension = format!(".{}", format.extension());
    let Some(base) = name.strip_suffix(&extension) else { return false; };
    let base = base.strip_suffix("_filtered").unwrap_or(base);
    let Some((stem, v)) = base.rsplit_once("_cleaned_v") else { return false; };
    !stem.is_empty() && stem.len() <= 70
        && stem.bytes().all(|c| c.is_ascii_alphanumeric() || c == b'_' || c == b'-')
        && v == version.to_string()
}

fn u16_at(bytes: &[u8], at: usize) -> Option<usize> {
    Some(u16::from_le_bytes(bytes.get(at..at.checked_add(2)?)?.try_into().ok()?) as usize)
}
fn u32_at(bytes: &[u8], at: usize) -> Option<usize> {
    Some(u32::from_le_bytes(bytes.get(at..at.checked_add(4)?)?.try_into().ok()?) as usize)
}

/// Structural admission for the exact single-sheet openpyxl export contract.
/// No decompression or XML execution. The authenticated backend must provide
/// the exact receipt digest; this is not a general XLSX parser or malware scan.
/// Local ZIP64 size extra fields are permitted because the producer forces
/// ZIP64 for the streamed sheet; central sizes fit within the bounded archive.
fn workbook_directory(bytes: &[u8]) -> Option<()> {
    const MEMBERS: [&[u8]; 9] = [
        b"docProps/app.xml", b"docProps/core.xml", b"xl/theme/theme1.xml",
        b"xl/worksheets/sheet1.xml", b"xl/styles.xml", b"_rels/.rels",
        b"xl/workbook.xml", b"xl/_rels/workbook.xml.rels", b"[Content_Types].xml",
    ];
    let end = bytes.len().checked_sub(22)?;
    if bytes.get(end..end+4)? != b"PK\x05\x06"
        || u16_at(bytes,end+4)? != 0 || u16_at(bytes,end+6)? != 0
        || u16_at(bytes,end+8)? != MEMBERS.len()
        || u16_at(bytes,end+10)? != MEMBERS.len() || u16_at(bytes,end+20)? != 0 {
        return None;
    }
    let central = u32_at(bytes,end+16)?;
    if central.checked_add(u32_at(bytes,end+12)?)? != end { return None; }
    let mut pos = central;
    let mut seen = [false; 9];
    let mut ranges = Vec::with_capacity(9);
    for _ in MEMBERS {
        if pos.checked_add(46)? > end || bytes.get(pos..pos+4)? != b"PK\x01\x02"
            || u16_at(bytes,pos+8)? != 0 || u16_at(bytes,pos+10)? != 8
            || u16_at(bytes,pos+34)? != 0 || u16_at(bytes,pos+32)? != 0 {
            return None;
        }
        let compressed = u32_at(bytes,pos+20)?;
        if compressed == 0 || u32_at(bytes,pos+24)? == 0 { return None; }
        let name_end = pos.checked_add(46)?.checked_add(u16_at(bytes,pos+28)?)?;
        let next = name_end.checked_add(u16_at(bytes,pos+30)?)?;
        if next > end { return None; }
        let name = bytes.get(pos+46..name_end)?;
        let member = MEMBERS.iter().position(|known| *known == name)?;
        if seen[member] { return None; }
        seen[member] = true;
        let local = u32_at(bytes,pos+42)?;
        if local.checked_add(30)? > central || bytes.get(local..local+4)? != b"PK\x03\x04"
            || u16_at(bytes,local+6)? != 0 || u16_at(bytes,local+8)? != 8 {
            return None;
        }
        let local_name_end = local.checked_add(30)?.checked_add(u16_at(bytes,local+26)?)?;
        if bytes.get(local+30..local_name_end)? != name { return None; }
        let data_end = local_name_end.checked_add(u16_at(bytes,local+28)?)?.checked_add(compressed)?;
        if data_end > central { return None; }
        ranges.push((local,data_end));
        pos = next;
    }
    if pos != end || !seen.iter().all(|v| *v) { return None; }
    ranges.sort_unstable();
    let mut expected = 0;
    for (start, finish) in ranges {
        if start != expected { return None; }
        expected = finish;
    }
    if expected != central { return None; }
    Some(())
}

pub(crate) fn validate<'a>(format: Format, filename: &str, version: u64,
    expected_size: usize, expected_sha256: &str, bytes: &'a [u8]) -> Result<Validated<'a>, String> {
    if bytes.is_empty() || bytes.len() > MAX_BYTES || expected_size != bytes.len()
        || expected_sha256.len() != 64
        || !expected_sha256.bytes().all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
        || !generated_name(filename,format,version)
        || format!("{:x}", Sha256::digest(bytes)) != expected_sha256 {
        return Err(INVALID.into());
    }
    match format {
        Format::Csv => {
            let text = bytes.strip_prefix(b"\xef\xbb\xbf").ok_or(INVALID)?;
            std::str::from_utf8(text).map_err(|_| INVALID)?;
            if text.is_empty() || !text.ends_with(b"\r\n")
                || text.iter().any(|c| matches!(*c,0..=8 | 11 | 12 | 14..=31)) {
                return Err(INVALID.into());
            }
        }
        Format::Xlsx => { workbook_directory(bytes).ok_or(INVALID)?; }
    }
    Ok(Validated { format, bytes })
}

fn same_path(a: &Path, b: &Path) -> bool {
    #[cfg(windows)]
    { a.to_string_lossy().to_lowercase() == b.to_string_lossy().to_lowercase() }
    #[cfg(not(windows))]
    { a == b }
}
fn within(path: &Path, root: &Path) -> bool {
    path.ancestors().any(|part| same_path(part,root))
}
fn redirected(info: &fs::Metadata) -> bool {
    if info.file_type().is_symlink() { return true; }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        if info.file_attributes() & 0x400 != 0 { return true; }
    }
    false
}
fn target_absent(path: &Path) -> Result<(), String> {
    match fs::symlink_metadata(path) {
        Err(error) if error.kind()==std::io::ErrorKind::NotFound => Ok(()),
        Ok(_) => Err("Destination exists; choose a new filename. No overwrite is permitted.".into()),
        Err(_) => Err(UNSAFE.into()),
    }
}
fn target_name(path: &Path, format: Format) -> bool {
    let Some(name) = path.file_name().and_then(|v| v.to_str()) else { return false; };
    if name.is_empty() || name.len() > 240 || name.ends_with(' ') || name.ends_with('.')
        || name.chars().any(|c| c.is_control() || matches!(c,'/'|'\\'|':'|'*'|'?'|'"'|'<'|'>'|'|')) {
        return false;
    }
    let stem = name.split('.').next().unwrap_or("").trim_end_matches(' ').to_ascii_uppercase();
    if stem.is_empty() || matches!(stem.as_str(),"CON"|"PRN"|"AUX"|"NUL"|"CONIN$"|"CONOUT$")
        || (stem.len()==4 && (stem.starts_with("COM")||stem.starts_with("LPT"))
            && stem.as_bytes()[3].is_ascii_digit()) {
        return false;
    }
    path.extension().and_then(|v|v.to_str()).is_some_and(|v|v.eq_ignore_ascii_case(format.extension()))
}

/// Only admitted existing user export directories; reject app-owned roots and
/// redirected paths. The caller supplies trusted OS directory roots, not IPC.
fn admit(path: &Path, format: Format, allowed: &[PathBuf], protected: &[PathBuf])
    -> Result<DirectoryPins, String> {
    if !path.is_absolute() || !target_name(path,format) || allowed.is_empty() || protected.is_empty() {
        return Err(UNSAFE.into());
    }
    let parent = path.parent().ok_or(UNSAFE)?;
    let mut pins = DirectoryPins::default();
    pins.admit_existing(parent)?;
    let resolved = parent.canonicalize().map_err(|_|UNSAFE)?;
    let mut permitted = false;
    for root in allowed {
        if let Ok(root) = root.canonicalize() { permitted |= within(&resolved,&root); }
    }
    if !permitted { return Err(UNSAFE.into()); }
    for root in protected {
        let root = root.canonicalize().map_err(|_|UNSAFE)?;
        if within(&resolved,&root) { return Err(UNSAFE.into()); }
    }
    pins.verify()?;
    target_absent(path)?;
    Ok(pins)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Stamp { volume: u64, id: u128, links: u64 }

#[cfg(unix)]
fn stamp(file: &File) -> Result<Stamp,String> {
    use std::os::unix::fs::MetadataExt;
    let m=file.metadata().map_err(|_|UNSAFE)?;
    if !m.is_file() || m.ino()==0 { return Err(UNSAFE.into()); }
    Ok(Stamp { volume:m.dev(),id:m.ino() as u128,links:m.nlink() })
}

#[cfg(windows)]
fn stamp(file: &File) -> Result<Stamp,String> {
    use std::ffi::c_void;
    use std::os::windows::io::AsRawHandle;
    #[repr(C)]
    struct Info {
        attrs:u32, created:[u32;2], accessed:[u32;2], written:[u32;2],
        volume:u32, size_high:u32, size_low:u32, links:u32, index_high:u32,index_low:u32,
    }
    #[link(name="kernel32")]
    extern "system" {
        fn GetFileInformationByHandle(file:*mut c_void, info:*mut Info)->i32;
    }
    let mut info=std::mem::MaybeUninit::<Info>::uninit();
    if unsafe {GetFileInformationByHandle(file.as_raw_handle(),info.as_mut_ptr())}==0 {
        return Err(UNSAFE.into());
    }
    let info=unsafe {info.assume_init()};
    let id=((info.index_high as u128)<<32)|info.index_low as u128;
    if id==0 || info.attrs & (0x10|0x400)!=0 { return Err(UNSAFE.into()); }
    Ok(Stamp{volume:info.volume as u64,id,links:info.links as u64})
}

fn open_named(path:&Path)->Result<File,String> {
    let m=fs::symlink_metadata(path).map_err(|_|UNSAFE)?;
    if redirected(&m)||!m.is_file(){return Err(UNSAFE.into());}
    let mut options=OpenOptions::new();
    options.read(true);
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        options.share_mode(0x7).custom_flags(0x00200000);
    }
    let file=options.open(path).map_err(|_|UNSAFE)?;
    let after=fs::symlink_metadata(path).map_err(|_|UNSAFE)?;
    if redirected(&after)||!after.is_file(){return Err(UNSAFE.into());}
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        let actual=file.metadata().map_err(|_|UNSAFE)?;
        if actual.dev()!=after.dev()||actual.ino()!=after.ino(){return Err(UNSAFE.into());}
    }
    Ok(file)
}
fn identity_at(path:&Path, expected:Stamp, links:u64)->Result<(),String>{
    let actual=stamp(&open_named(path)?)?;
    if actual.volume!=expected.volume||actual.id!=expected.id||actual.links!=links {
        return Err(UNSAFE.into());
    }
    Ok(())
}
fn verify_bytes(file:&mut File, bytes:&[u8])->Result<(),String>{
    if file.metadata().map_err(|_|UNSAFE)?.len()!=bytes.len() as u64 {
        return Err("Dataset byte count differs after writing".into());
    }
    file.seek(SeekFrom::Start(0)).map_err(|_|UNSAFE)?;
    let mut buffer=[0u8;64*1024];
    for expected in bytes.chunks(buffer.len()){
        let actual=&mut buffer[..expected.len()];
        file.read_exact(actual).map_err(|_|UNSAFE)?;
        if &*actual!=expected {return Err("Dataset bytes differ after writing".into());}
    }
    Ok(())
}
fn remove_owned(pins:&DirectoryPins,path:&Path,expected:Stamp,links:u64)->Result<(),String>{
    pins.verify()?;
    identity_at(path,expected,links)?;
    fs::remove_file(path).map_err(|_|"Dataset staging cleanup refused; review retained file".into())
}

/// Stage in the chosen directory, verify, publish without replacing any file.
/// Same-directory hard-link publication is no-clobber; unsupported filesystems
/// fail closed. Never fall back to copying, truncating, or deleting a target.
/// If post-publication identity/bytes are uncertain, retain both names and do
/// not certify success. Directory pins and observed file identities do not
/// constitute hostile-process-proof atomic confinement.
pub(crate) fn publish_new(path:&Path,payload:&Validated<'_>,id:u128,
    allowed:&[PathBuf],protected:&[PathBuf])->Result<(),String>{
    let pins=admit(path,payload.format,allowed,protected)?;
    let staging=path.with_file_name(format!(".pilotodin-dataset-{id:032x}.tmp"));
    let mut options=OpenOptions::new();
    options.read(true).write(true).create_new(true);
    #[cfg(unix)]
    { use std::os::unix::fs::OpenOptionsExt; options.mode(0o600); }
    #[cfg(windows)]
    { use std::os::windows::fs::OpenOptionsExt; options.share_mode(0x7); }
    let mut file=options.open(&staging).map_err(|_|"Could not exclusively create dataset staging file")?;
    let initial=stamp(&file)?;
    if initial.links!=1 {return Err(UNSAFE.into());}
    let prepared=(||{
        pins.verify()?;
        identity_at(&staging,initial,1)?;
        file.write_all(payload.bytes).map_err(|_|"Dataset write failed")?;
        file.sync_all().map_err(|_|"Dataset flush failed")?;
        verify_bytes(&mut file,payload.bytes)?;
        pins.verify()?;
        identity_at(&staging,initial,1)?;
        target_absent(path)?;
        Ok::<(),String>(())
    })();
    drop(file);
    if let Err(error)=prepared {
        remove_owned(&pins,&staging,initial,1)?;
        return Err(error);
    }
    pins.verify()?;
    identity_at(&staging,initial,1)?;
    if fs::hard_link(&staging,path).is_err(){
        // Destination may have appeared. Never touch it.
        remove_owned(&pins,&staging,initial,1)?;
        return Err("Dataset destination could not be published without overwrite".into());
    }
    pins.verify()?;
    identity_at(&staging,initial,2)?;
    let mut final_file=open_named(path)?;
    let final_stamp=stamp(&final_file)?;
    if final_stamp.volume!=initial.volume||final_stamp.id!=initial.id||final_stamp.links!=2 {
        return Err(UNSAFE.into());
    }
    verify_bytes(&mut final_file,payload.bytes)?;
    drop(final_file);
    identity_at(path,initial,2)?;
    remove_owned(&pins,&staging,initial,2)?;
    pins.verify()?;
    identity_at(path,initial,1)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    const CSV:&[u8]=b"\xef\xbb\xbfID,Amount\r\nA001,12\r\n";
    fn checked()->Validated<'static>{
        validate(Format::Csv,"Generated_cleaned_v0.csv",0,CSV.len(),
            &format!("{:x}",Sha256::digest(CSV)),CSV).unwrap()
    }
    #[test]
    fn rejects_wrong_version_format_size_digest_and_controls(){
        let hash=format!("{:x}",Sha256::digest(CSV));
        assert!(validate(Format::Csv,"Generated_cleaned_v1.csv",0,CSV.len(),&hash,CSV).is_err());
        assert!(validate(Format::Csv,"../Generated_cleaned_v0.csv",0,CSV.len(),&hash,CSV).is_err());
        assert!(validate(Format::Csv,"Generated_cleaned_v0.csv",0,CSV.len()+1,&hash,CSV).is_err());
        assert!(validate(Format::Csv,"Generated_cleaned_v0.csv",0,CSV.len(),&"0".repeat(64),CSV).is_err());
        assert!(validate(Format::Xlsx,"Generated_cleaned_v0.xlsx",0,CSV.len(),&hash,CSV).is_err());
        let bad=b"\xef\xbb\xbfA,\x00\r\n";
        assert!(validate(Format::Csv,"Generated_cleaned_v0.csv",0,bad.len(),
            &format!("{:x}",Sha256::digest(bad)),bad).is_err());
        assert!(workbook_directory(b"PK\x03\x04not a workbook").is_none());
        let _=checked();
    }
    #[test]
    fn new_file_publication_refuses_existing_and_protected_paths(){
        let root=std::env::temp_dir().join(format!("pilotodin-b5-source-{}",uuid::Uuid::new_v4()));
        fs::create_dir(&root).unwrap();
        // The actual runner's temp root must be an ordinary admitted directory.
        let allowed=root.join("exports");
        let protected=allowed.join("protected");
        fs::create_dir(&allowed).unwrap();
        fs::create_dir(&protected).unwrap();
        let allowed_roots=[allowed.clone()];
        let protected_roots=[protected.clone()];
        let path=allowed.join("chosen.csv");
        let payload=checked();
        publish_new(&path,&payload,1,&allowed_roots,&protected_roots).unwrap();
        assert_eq!(fs::read(&path).unwrap(),CSV);
        assert!(publish_new(&path,&payload,2,&allowed_roots,&protected_roots).is_err());
        assert_eq!(fs::read(&path).unwrap(),CSV);
        assert!(publish_new(&protected.join("refused.csv"),&payload,3,&allowed_roots,&protected_roots).is_err());
        assert!(publish_new(&root.join("outside.csv"),&payload,4,&allowed_roots,&protected_roots).is_err());
        assert!(publish_new(&allowed.join("wrong.xlsx"),&payload,5,&allowed_roots,&protected_roots).is_err());
        assert!(!protected.join("refused.csv").exists());
        assert!(!root.join("outside.csv").exists());
        assert!(!allowed.join("wrong.xlsx").exists());
        let collision=allowed.join(".pilotodin-dataset-00000000000000000000000000000006.tmp");
        fs::write(&collision,b"foreign").unwrap();
        assert!(publish_new(&allowed.join("collision.csv"),&payload,6,&allowed_roots,&protected_roots).is_err());
        assert_eq!(fs::read(&collision).unwrap(),b"foreign");
        fs::remove_file(collision).unwrap();
        fs::remove_file(path).unwrap();
        fs::remove_dir(protected).unwrap();
        fs::remove_dir(allowed).unwrap();
        fs::remove_dir(root).unwrap();
    }
}
