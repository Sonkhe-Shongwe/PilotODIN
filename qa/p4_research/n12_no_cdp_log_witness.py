"""Read-only, fail-closed observation of a future no-CDP QA app log.

The caller must create an empty disposable app.log before launching the app,
then keep the exact log file identity. This module never launches a process,
changes a file, authorizes an OS close, or awards N12 acceptance.
"""
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import stat
import time

from qa.p4_native.n12_trace import EvidenceValidationError, require


MARKER = b"N12 QA native close listener registered"
MAX_LOG_BYTES = 256 * 1024
POLL_INTERVAL_SECONDS = 0.1
MAX_WAIT_SECONDS = 45


@dataclass(frozen=True)
class PrelaunchLog:
    # Internal fields can contain runner paths. Do not serialize/repr these.
    path: Path = field(repr=False)
    device: int = field(repr=False)
    inode: int = field(repr=False)
    source_sha: str
    executable_sha256: str
    # Hold this original descriptor through observation. Closing it and
    # comparing only the inode permits rapid delete/recreate inode reuse.
    handle: object = field(repr=False, compare=False)

    def close(self):
        self.handle.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


@dataclass(frozen=True)
class SeenReadiness:
    # Positive marker observation, NOT proof of a native process or N12 pass.
    size_before_close: int
    marker_lines_before_close: int = 1
    native_N12_acceptance: str = "NOT_EVALUATED"


def prepare_prelaunch_log(path, *, expected_source, actual_source,
                          expected_executable_sha256, actual_executable_sha256):
    """Call before spawning, with a new, empty app.log in the isolated run root."""
    require(type(expected_source) is str and re.fullmatch(r"[0-9a-f]{40}", expected_source)
            and actual_source == expected_source, "no-cdp-source-unverified")
    require(type(expected_executable_sha256) is str
            and re.fullmatch(r"[0-9a-f]{64}", expected_executable_sha256)
            and actual_executable_sha256 == expected_executable_sha256,
            "no-cdp-executable-unverified")
    path = Path(path)
    require(path.name == "app.log" and not path.is_symlink(), "no-cdp-log-path-unverified")
    try:
        handle = path.open("rb")
    except OSError as exc:
        raise EvidenceValidationError("no-cdp-log-unavailable") from exc
    try:
        meta = os.fstat(handle.fileno())
        require(stat.S_ISREG(meta.st_mode) and meta.st_size == 0
                and type(meta.st_ino) is int and meta.st_ino > 0,
                "no-cdp-prelaunch-log-not-empty-or-unique")
        current = path.stat()
        require((current.st_dev, current.st_ino) == (meta.st_dev, meta.st_ino)
                and current.st_size == 0 and not path.is_symlink(),
                "no-cdp-log-identity-changed")
        return PrelaunchLog(path, meta.st_dev, meta.st_ino,
                            expected_source, expected_executable_sha256, handle)
    except (OSError, EvidenceValidationError) as exc:
        handle.close()
        if isinstance(exc, EvidenceValidationError):
            raise
        raise EvidenceValidationError("no-cdp-log-unavailable") from exc


def _read_lines(witness):
    path = witness.path
    require(not witness.handle.closed and not path.is_symlink(),
            "no-cdp-log-identity-changed")
    try:
        with path.open("rb") as stream:
            meta = os.fstat(stream.fileno())
            require((meta.st_dev, meta.st_ino) == (witness.device, witness.inode)
                    and stat.S_ISREG(meta.st_mode), "no-cdp-log-identity-changed")
            require(meta.st_size <= MAX_LOG_BYTES, "no-cdp-log-size-limit")
            content = stream.read(MAX_LOG_BYTES + 1)
            require(len(content) <= MAX_LOG_BYTES, "no-cdp-log-size-limit")
            # Any shrink or incomplete read is ambiguous, not affirmative.
            require(len(content) == meta.st_size, "no-cdp-log-snapshot-inconsistent")
            after = path.stat()
            require((after.st_dev, after.st_ino) == (witness.device, witness.inode)
                    and after.st_size == meta.st_size, "no-cdp-log-changed-during-read")
    except OSError as exc:
        raise EvidenceValidationError("no-cdp-log-unavailable") from exc
    # Only fully terminated, exact byte-for-byte lines count. No private text
    # from any other line can enter an error or a public receipt.
    complete = content.split(b"\n")[:-1]
    count = sum(line == MARKER or line == MARKER + b"\r" for line in complete)
    return meta.st_size, count


def wait_for_readiness(witness, process, *, expected_pid,
                       main_window_identity_verified, timeout_seconds=30,
                       clock=time.monotonic, sleep=time.sleep):
    """A bounded provisional observation, not a replacement for WM_CLOSE."""
    require(type(expected_pid) is int and expected_pid > 0
            and getattr(process, "pid", None) == expected_pid,
            "no-cdp-app-process-identity-unverified")
    require(main_window_identity_verified is True,
            "no-cdp-window-identity-unverified")
    require(type(timeout_seconds) in (int, float)
            and 0 < timeout_seconds <= MAX_WAIT_SECONDS,
            "no-cdp-timeout-invalid")
    deadline = clock() + timeout_seconds
    previous_size = 0
    while True:
        require(process.poll() is None, "no-cdp-app-exited-before-readiness")
        size, count = _read_lines(witness)
        require(size >= previous_size, "no-cdp-log-truncated")
        previous_size = size
        require(count <= 1, "no-cdp-marker-duplicate")
        if count == 1:
            # A final check after verified normal close is still mandatory.
            return SeenReadiness(size_before_close=size)
        if clock() >= deadline:
            raise EvidenceValidationError("no-cdp-readiness-timeout")
        sleep(min(POLL_INTERVAL_SECONDS, max(0.0, deadline - clock())))


def verify_after_normal_close(witness, provisional, *, process,
                              expected_pid, close_request_verified):
    """Reject a new/duplicated marker after close; never certify N12."""
    require(isinstance(provisional, SeenReadiness)
            and provisional.marker_lines_before_close == 1,
            "no-cdp-provisional-observation-unverified")
    require(type(expected_pid) is int and expected_pid > 0
            and getattr(process, "pid", None) == expected_pid,
            "no-cdp-app-process-identity-unverified")
    require(close_request_verified is True and process.poll() == 0,
            "no-cdp-graceful-close-unverified")
    size, count = _read_lines(witness)
    require(size >= provisional.size_before_close,
            "no-cdp-log-truncated")
    require(count == 1, "no-cdp-postclose-marker-missing-or-duplicate")
    return {
        "scope": "no-cdp-app-close-log-witness-only",
        "marker": "observed-once-before-close",
        "log_identity": "prelaunch-file-identity-matched",
        "graceful_close": "caller-verified-zero-exit",
        "app_process_identity": "caller-bound",
        "browser_process_identity": "NOT_EVALUATED",
        "file_event_coverage": "NOT_EVALUATED",
        "native_N12_acceptance": "NOT_EVALUATED",
        "owner_native_execution_authorized": False,
    }
