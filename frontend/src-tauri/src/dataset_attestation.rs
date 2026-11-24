//! Unregistered B5 native receipt verifier; requires locked Windows host review.
//! The API session token is not the MAC key. No new crates or network access.
use crate::dataset_file::{self, Format, MAX_BYTES};
const INVALID: &str = "Dataset export receipt authentication failed";
const MAX_SAFE: u64 = (1u64 << 53) - 1;

pub(crate) struct Metadata {
    pub(crate) project: String,
    pub(crate) operation: String,
    pub(crate) version: u64,
    pub(crate) format: Format,
    pub(crate) size: usize,
    pub(crate) sha256: String,
    pub(crate) filename: String,
    pub(crate) rows: u64,
    pub(crate) mac: String,
}
fn hex(value: &str, len: usize) -> bool {
    value.len() == len && value.bytes().all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
}
impl Metadata {
    fn message(&self) -> Result<String, String> {
        if !hex(&self.project,32) || !hex(&self.operation,32)
            || !hex(&self.sha256,64) || !hex(&self.mac,64)
            || self.version > MAX_SAFE || self.rows > MAX_SAFE
            || self.size == 0 || self.size > MAX_BYTES
            || !dataset_file::generated_name(&self.filename,self.format,self.version) {
            return Err(INVALID.into());
        }
        Ok(format!("PilotODIN/export-receipt/v1\n{}\n{}\n{}\n{}\n{}\n{}\n{}\n{}\n",
            self.project,self.operation,self.version,self.format.extension(),
            self.size,self.sha256,self.filename,self.rows))
    }
    pub(crate) fn verify(&self, key: &str) -> Result<(), String> {
        if !hex(key,64) { return Err(INVALID.into()); }
        let computed = hmac_sha256(key.as_bytes(),self.message()?.as_bytes())?;
        let mut supplied = [0u8;32];
        for (i, byte) in supplied.iter_mut().enumerate() {
            *byte = u8::from_str_radix(&self.mac[i*2..i*2+2],16).map_err(|_| INVALID)?;
        }
        // Fixed 32-byte comparison, no early exit at a differing byte.
        // Not a claim of hostile-OS timing/side-channel immunity.
        let mut difference = 0u8;
        for i in 0..32 {
            difference |= unsafe { std::ptr::read_volatile(&computed[i]) }
                ^ unsafe { std::ptr::read_volatile(&supplied[i]) };
        }
        if difference != 0 { return Err(INVALID.into()); }
        Ok(())
    }
}
#[cfg(windows)]
fn hmac_sha256(key: &[u8], message: &[u8]) -> Result<[u8;32],String> {
    use std::ffi::c_void;
    #[link(name="bcrypt")]
    extern "system" {
        fn BCryptOpenAlgorithmProvider(handle:*mut *mut c_void, algorithm:*const u16,
            implementation:*const u16, flags:u32)->i32;
        fn BCryptHash(handle:*mut c_void, secret:*const u8, secret_len:u32,
            input:*const u8, input_len:u32, output:*mut u8, output_len:u32)->i32;
        fn BCryptCloseAlgorithmProvider(handle:*mut c_void, flags:u32)->i32;
    }
    let mut handle = std::ptr::null_mut();
    let algorithm = [83u16,72,65,50,53,54,0]; // SHA256
    let key_len=u32::try_from(key.len()).map_err(|_| INVALID)?;
    let input_len=u32::try_from(message.len()).map_err(|_| INVALID)?;
    let opened=unsafe{BCryptOpenAlgorithmProvider(&mut handle,algorithm.as_ptr(),std::ptr::null(),0x00000008)};
    if opened < 0 || handle.is_null() { return Err(INVALID.into()); }
    let mut output=[0u8;32];
    let hashed=unsafe{BCryptHash(handle,key.as_ptr(),key_len,message.as_ptr(),
        input_len,output.as_mut_ptr(),32)};
    let closed=unsafe{BCryptCloseAlgorithmProvider(handle,0)};
    if hashed < 0 || closed < 0 { return Err(INVALID.into()); }
    Ok(output)
}
#[cfg(not(windows))]
fn hmac_sha256(_: &[u8], _: &[u8]) -> Result<[u8;32],String> {
    Err("Native dataset receipt verification requires Windows".into())
}
#[cfg(test)]
mod tests {
    use super::*;
    fn fixture() -> Metadata {
        Metadata { project:"a".repeat(32),operation:"b".repeat(32),version:7,
            format:Format::Csv,size:25,sha256:"c".repeat(64),
            filename:"Generated_cleaned_v7_filtered.csv".into(),rows:2,
            mac:"6e628fe3aaae0e3f2d01ddc839d74b607b730b09f893108632ef63dde2e55fb3".into() }
    }
    #[test]
    fn canonical_metadata_rejects_mismatched_filename_and_bounds() {
        let mut m=fixture();
        assert!(m.message().is_ok());
        m.version=8; assert!(m.message().is_err());
        m.version=7; m.size=MAX_BYTES+1; assert!(m.message().is_err());
    }
    #[cfg(windows)]
    #[test]
    fn python_hmac_vector_and_tampering() {
        let mut m=fixture();
        assert!(m.verify(&"1".repeat(64)).is_ok());
        assert!(m.verify(&"2".repeat(64)).is_err());
        m.rows=3; assert!(m.verify(&"1".repeat(64)).is_err());
    }
}
