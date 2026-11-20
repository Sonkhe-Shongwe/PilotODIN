//! Verified publication of a report at a destination chosen by the native dialog.
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Seek, SeekFrom, Write};
use std::path::Path;

pub(crate) fn publish_report(path: &Path, bytes: &[u8], id: u128) -> io::Result<()> {
    stage_and_publish(path, bytes, id, |file| file.write_all(bytes))
}

fn stage_and_publish(
    path: &Path,
    bytes: &[u8],
    id: u128,
    write: impl FnOnce(&mut File) -> io::Result<()>,
) -> io::Result<()> {
    let staging = path.with_file_name(format!(".pilotodin-report-{id:032x}.tmp"));
    let mut file = OpenOptions::new()
        .read(true)
        .write(true)
        .create_new(true)
        .open(&staging)?;

    let verified = write(&mut file)
        .and_then(|()| file.sync_all())
        .and_then(|()| verify_bytes(&mut file, bytes));
    drop(file);

    // Both names are in the same directory. A failed replacement never
    // falls back to deleting the destination or copying over its contents.
    let result = verified.and_then(|()| fs::rename(&staging, path));
    if let Err(save_error) = result {
        if let Err(cleanup_error) = fs::remove_file(&staging) {
            if cleanup_error.kind() != io::ErrorKind::NotFound {
                return Err(io::Error::new(
                    save_error.kind(),
                    format!("{save_error}. Could not remove the staged report: {cleanup_error}"),
                ));
            }
        }
        return Err(save_error);
    }
    Ok(())
}

fn verify_bytes(file: &mut File, expected: &[u8]) -> io::Result<()> {
    if file.metadata()?.len() != expected.len() as u64 {
        return Err(io::Error::new(io::ErrorKind::InvalidData, "Saved report size verification failed"));
    }
    file.seek(SeekFrom::Start(0))?;
    let mut buffer = [0; 65_536];
    for expected_chunk in expected.chunks(buffer.len()) {
        let actual_chunk = &mut buffer[..expected_chunk.len()];
        file.read_exact(actual_chunk)?;
        if &*actual_chunk != expected_chunk {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "The saved report failed content verification"));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicUsize, Ordering};

    const ORIGINAL: &[u8] = b"%PDF-1.7\noriginal export\n";
    const REPLACEMENT: &[u8] = b"%PDF-1.7\nnew export\n";

    struct Fixture(PathBuf);

    impl Fixture {
        fn new() -> Self {
            static NEXT: AtomicUsize = AtomicUsize::new(0);
            let root = std::env::temp_dir().join(format!(
                "pilotodin-report-write-{}-{}",
                std::process::id(),
                NEXT.fetch_add(1, Ordering::Relaxed),
            ));
            fs::create_dir(&root).unwrap();
            Self(root)
        }

        fn destination(&self) -> PathBuf {
            self.0.join("existing.pdf")
        }

        fn existing_report(&self) -> PathBuf {
            let path = self.destination();
            fs::write(&path, ORIGINAL).unwrap();
            path
        }

        fn assert_single_destination(&self) {
            let entries: Vec<_> = fs::read_dir(&self.0).unwrap()
                .map(|entry| entry.unwrap().path()).collect();
            assert_eq!(entries, vec![self.destination()]);
        }
    }

    impl Drop for Fixture {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn publishes_new_and_replacement_reports_with_exact_bytes() {
        let fixture = Fixture::new();
        let path = fixture.destination();
        publish_report(&path, ORIGINAL, 1).unwrap();
        assert_eq!(fs::read(&path).unwrap(), ORIGINAL);
        let mut bytes = REPLACEMENT.to_vec();
        bytes.resize(140_000, 0x81);
        publish_report(&path, &bytes, 2).unwrap();
        assert_eq!(fs::read(path).unwrap(), bytes);
        fixture.assert_single_destination();
    }

    #[test]
    fn short_write_error_leaves_the_old_export_intact() {
        let fixture = Fixture::new();
        let path = fixture.existing_report();
        let failure = stage_and_publish(&path, REPLACEMENT, 1, |file| {
            file.write_all(&REPLACEMENT[..5])?;
            Err(io::Error::new(io::ErrorKind::WriteZero, "injected partial write"))
        });
        assert_eq!(failure.unwrap_err().kind(), io::ErrorKind::WriteZero);
        assert_eq!(fs::read(path).unwrap(), ORIGINAL);
        fixture.assert_single_destination();
    }

    #[test]
    fn size_and_content_validation_fail_before_replacing_the_destination() {
        let fixture = Fixture::new();
        let path = fixture.existing_report();
        let mut corrupt = REPLACEMENT.to_vec();
        corrupt[7] ^= 1;
        for (stage, message) in [
            (&REPLACEMENT[..5], "Saved report size verification failed"),
            (corrupt.as_slice(), "The saved report failed content verification"),
        ] {
            let failure = stage_and_publish(&path, REPLACEMENT, 1, |file| file.write_all(stage));
            assert_eq!(failure.unwrap_err().to_string(), message);
            assert_eq!(fs::read(&path).unwrap(), ORIGINAL);
            fixture.assert_single_destination();
        }
    }

    #[test]
    fn failed_rename_removes_staging_without_deleting_the_destination() {
        let fixture = Fixture::new();
        let path = fixture.destination();
        fs::create_dir(&path).unwrap();
        let contents = path.join("keep");
        fs::write(&contents, ORIGINAL).unwrap();
        assert!(publish_report(&path, REPLACEMENT, 1).is_err());
        assert_eq!(fs::read(contents).unwrap(), ORIGINAL);
        fixture.assert_single_destination();
    }

    #[test]
    fn staging_collision_does_not_change_either_file() {
        let fixture = Fixture::new();
        let path = fixture.existing_report();
        let staging = path.with_file_name(".pilotodin-report-00000000000000000000000000000001.tmp");
        fs::write(&staging, b"existing staging file").unwrap();
        let failure = publish_report(&path, REPLACEMENT, 1).unwrap_err();
        assert_eq!(failure.kind(), io::ErrorKind::AlreadyExists);
        assert_eq!(fs::read(path).unwrap(), ORIGINAL);
        assert_eq!(fs::read(staging).unwrap(), b"existing staging file");
    }
}
