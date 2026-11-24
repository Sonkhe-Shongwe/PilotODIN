"""Staged C1 owned host control protocol; no live transport registration.

Only the trusted host/engine composition can supply the private capability.
A RELEASE is a trusted host assertion, not independent process-exit evidence.
The host must prove the corresponding child/group exited (or never started).
A single owned reader dispatches frames and writes replies synchronously.
Any transport uncertainty is terminal for this session, not a retry signal.
"""
from dataclasses import dataclass
import hmac
import re
from uuid import uuid4

try:
    from .resource_admission import Operation
except ImportError:
    from resource_admission import Operation

MAX_FRAME = 4096
MAX_SEQUENCE = 2147483647
LEGACY_STOP = b"PILOTODIN_STOP\n"
_HEX32 = re.compile(r"[0-9a-f]{32}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_SEQ = re.compile(r"[1-9][0-9]{0,9}")
_DENIALS = frozenset(("resource_busy","ownership_unknown","shutting_down",
                     "memory_unavailable","policy_unavailable",
                     "observation_stale","low_memory_headroom","not_ready"))


class ProtocolFault(RuntimeError):
    """Fixed error message; never include frame bytes or credentials."""


def _fault():
    return ProtocolFault("Owned resource control protocol fault")


class FrameReader:
    """Bounded LF framing over binary chunks; no partial-line publication."""
    def __init__(self):
        self._pending = bytearray()
        self._failed = False

    @property
    def partial(self):
        return bool(self._pending)

    def feed(self, chunk):
        if self._failed or type(chunk) is not bytes or not 0 < len(chunk) <= MAX_FRAME:
            self._failed = True
            raise _fault()
        frames = []
        for byte in chunk:
            if byte != 10 and not 32 <= byte <= 126:
                self._failed = True
                raise _fault()
            self._pending.append(byte)
            if byte == 10:
                if len(self._pending) == 1:
                    self._failed = True
                    raise _fault()
                frames.append(bytes(self._pending))
                self._pending.clear()
            elif len(self._pending) >= MAX_FRAME:
                # There is no room for the required trailing LF.
                self._failed = True
                raise _fault()
        return frames


@dataclass(frozen=True, repr=False)
class Request:
    sequence: int
    command: str
    grant: str | None = None
    evidence: str | None = None


def parse_request(frame, generation, capability):
    if (type(frame) is not bytes or not 1 < len(frame) <= MAX_FRAME
            or not frame.endswith(b"\n")):
        raise _fault()
    try:
        line = frame[:-1].decode("ascii")
    except UnicodeError:
        raise _fault() from None
    if any(not 32 <= ord(c) <= 126 for c in line):
        raise _fault()
    parts = line.split(" ")
    if len(parts) < 5 or parts[0] != "POD1":
        raise _fault()
    _, gen, secret, seq, command, *args = parts
    if (not _HEX32.fullmatch(gen) or not _HEX64.fullmatch(secret)
            or not hmac.compare_digest(gen,generation)
            or not hmac.compare_digest(secret,capability)
            or not _SEQ.fullmatch(seq) or int(seq) > MAX_SEQUENCE):
        raise _fault()
    sequence = int(seq)
    if command == "GRANT_REQUEST" and args == ["LOCAL_INFERENCE"]:
        return Request(sequence,command)
    if command == "DRAIN" and len(args) == 1 and _HEX32.fullmatch(args[0]):
        return Request(sequence,command,args[0])
    if (command == "RELEASE" and len(args) == 2 and _HEX32.fullmatch(args[0])
            and args[1] in ("NEVER_STARTED","EXITED")):
        return Request(sequence,command,args[0],args[1])
    if command == "READY" and not args:
        return Request(sequence,command)
    if command == "STOP" and not args:
        return Request(sequence,command)
    raise _fault()


class HostBroker:
    """One reader, one generation, one grant, no durable queue or timeout release.

    Call receive() only from the owner of the ordered input stream, then
    reply_written() after complete write and flush; call transport_lost() on EOF, write/flush failure or uncertain reply delivery.
    Neither a frontend message nor a mere elapsed timeout can release a grant.
    Not wired to desktop_runner or Tauri yet.
    """
    def __init__(self, coordinator, generation, capability, *, ready=None):
        if (type(generation) is not str or not _HEX32.fullmatch(generation)
                or type(capability) is not str or not _HEX64.fullmatch(capability)):
            raise ValueError("Invalid owned resource session identity")
        self.coordinator = coordinator
        self._generation = generation
        self._capability = capability
        self._reader = FrameReader()
        self._last = 0
        self._lease = None
        self._grant = None
        self._stopping = False
        self._faulted = False
        self._pending_reply = None
        self._release_after_reply = False
        self._ready_check = ready
        self._ready_confirmed = ready is None
        self._ready_after_reply = False

    @property
    def shutdown_ready(self):
        return (self._stopping and not self._faulted and self._lease is None
                and self._pending_reply is None and not self._reader.partial)

    def transport_lost(self):
        self._faulted = True
        self._stopping = True
        self.coordinator.begin_shutdown()
        if self._lease is not None:
            self.coordinator.block(self._lease)

    def _stop(self):
        self._stopping = True
        self.coordinator.begin_shutdown()
        if self._lease is not None:
            if not self.coordinator.drain(self._lease):
                raise _fault()

    def _reply(self, sequence, *fields):
        return (" ".join(("POD1",self._generation,str(sequence),*fields))+"\n").encode("ascii")

    def _dispatch(self, frame):
        if frame == LEGACY_STOP:
            self._stop()
            return None
        request = parse_request(frame,self._generation,self._capability)
        if request.sequence != self._last + 1:
            raise _fault()
        self._last = request.sequence
        seq = request.sequence
        if request.command == "READY":
            if self._lease is not None:
                raise _fault()
            if self._stopping or self.coordinator.status()["stopping"]:
                return self._reply(seq,"NOT_READY")
            if self._ready_check is not None and self._ready_check() is not True:
                return self._reply(seq,"NOT_READY")
            self._ready_after_reply = True
            return self._reply(seq,"READY")
        if request.command == "STOP":
            self._stop()
            return self._reply(seq,"ADMISSION_STOPPED")
        if request.command == "GRANT_REQUEST":
            if self._stopping:
                return self._reply(seq,"GRANT_REPLY","DENIED","shutting_down")
            if not self._ready_confirmed or (
                    self._ready_check is not None and self._ready_check() is not True):
                return self._reply(seq,"GRANT_REPLY","DENIED","not_ready")
            if self._lease is not None:
                return self._reply(seq,"GRANT_REPLY","DENIED","resource_busy")
            admission = self.coordinator.try_acquire(Operation.LOCAL_INFERENCE)
            if not admission.allowed:
                if admission.code not in _DENIALS:
                    raise _fault()
                return self._reply(seq,"GRANT_REPLY","DENIED",admission.code)
            self._lease = admission.lease
            # The host may perform integrity verification immediately after
            # the grant. The lane is RUNNING before the reply is sent.
            if not self.coordinator.start(self._lease):
                if not self.coordinator.release(self._lease):
                    raise _fault()
                self._lease = None
                return self._reply(seq,"GRANT_REPLY","DENIED","shutting_down")
            self._grant = uuid4().hex
            return self._reply(seq,"GRANT_REPLY","GRANTED",self._grant)
        if self._lease is None or request.grant != self._grant:
            raise _fault()
        if request.command == "DRAIN":
            if not self.coordinator.drain(self._lease):
                raise _fault()
            return self._reply(seq,"DRAINING",self._grant)
        if request.command == "RELEASE":
            # Actual start/exit evidence is the responsibility of the
            # trusted native owner. The wire enum is NOT an exit witness.
            self._release_after_reply = True
            return self._reply(seq,"RELEASED",self._grant)
        raise _fault()

    def receive(self, chunk):
        """One request, one reply; writer must confirm exact flush before reading."""
        if self._faulted:
            raise _fault()
        try:
            if self._pending_reply is not None:
                raise _fault()
            frames = self._reader.feed(chunk)
            if len(frames) > 1 or (frames and self._reader.partial):
                raise _fault()  # reject pipelining before any command executes
            if not frames:
                return []
            reply = self._dispatch(frames[0])
            if reply is None:
                return []
            self._pending_reply = reply
            return [reply]
        except BaseException:
            self.transport_lost()
            raise

    def reply_written(self, reply):
        """Trusted writer acknowledgement after complete write AND flush.

        A release remains owned until this boundary. A write/flush failure
        must instead call transport_lost; never manufacture an acknowledgement.
        """
        if self._faulted:
            raise _fault()
        try:
            if (self._pending_reply is None or type(reply) is not bytes
                    or reply != self._pending_reply):
                raise _fault()
            if self._release_after_reply:
                if self._lease is None or not self.coordinator.release(self._lease):
                    raise _fault()
                self._lease = None
                self._grant = None
                self._release_after_reply = False
            if self._ready_after_reply:
                self._ready_confirmed = True
                self._ready_after_reply = False
            self._pending_reply = None
        except BaseException:
            self.transport_lost()
            raise


def serve_owned(broker, read_chunk, write_reply, flush_reply, *, on_shutdown=None,
                exit_on_shutdown=False):
    """Staged single-reader/writer pump over already owned binary streams.

    The caller provides read-at-most, write and flush functions. No descriptor
    is opened or closed here. STOP stops admission, not the control channel:
    a host may still need to drain/release its exact grant. EOF is a terminal
    transport fault. An independent host deadline must cover blocking I/O;
    this synchronous pump never asserts that a blocked call has completed.
    """
    if not isinstance(broker, HostBroker):
        raise TypeError("Trusted resource broker required")
    notified = False

    def notify():
        nonlocal notified
        if not notified:
            notified = True
            if on_shutdown is not None:
                on_shutdown()

    try:
        while True:
            chunk = read_chunk(MAX_FRAME)
            if type(chunk) is not bytes or not 0 < len(chunk) <= MAX_FRAME:
                raise _fault()
            for reply in broker.receive(chunk):
                count = write_reply(reply)
                if type(count) is not int or count != len(reply):
                    raise _fault()
                flush_reply()
                broker.reply_written(reply)
            if broker.shutdown_ready:
                notify()
                if exit_on_shutdown:
                    return
    except BaseException as exc:
        broker.transport_lost()
        try:
            notify()
        except Exception:
            # A faulty notification cannot clear ownership or mask the fault.
            pass
        if isinstance(exc, Exception):
            raise _fault() from None
        raise


def _binary_descriptor(fd):
    import os
    if os.name == "nt":
        import msvcrt
        msvcrt.setmode(fd, os.O_BINARY)


class _ControlWriter:
    """Exactly one private descriptor, no buffered stream or fdopen transfer."""
    def __init__(self, ops, fd):
        self._ops = ops
        self._fd = fd

    def write(self, payload):
        if self._fd is None:
            raise _fault()
        return self._ops.write(self._fd, payload)

    def flush(self):
        if self._fd is None:
            raise _fault()
        # Raw os.write has no user-space buffer to flush.

    def close(self):
        fd = self._fd
        if fd is not None:
            self._fd = None  # never retry an ambiguous close
            self._ops.close(fd)


def _redirect_native_stdout(fd):
    import os
    if os.name != "nt":
        return
    import ctypes
    import msvcrt
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    get = kernel.GetStdHandle
    get.argtypes = [wintypes.DWORD]
    get.restype = wintypes.HANDLE
    set_handle = kernel.SetStdHandle
    set_handle.argtypes = [wintypes.DWORD, wintypes.HANDLE]
    set_handle.restype = wintypes.BOOL
    target = msvcrt.get_osfhandle(fd)
    if target in (-1, 0):
        raise _fault()
    stdout_id = 0xfffffff5  # STD_OUTPUT_HANDLE ((DWORD)-11)
    if not set_handle(stdout_id, target) or get(stdout_id) != target:
        raise _fault()


def prepare_control_stdio(stdin, stdout, stderr, *, ops=None, binary_mode=None,
                          native_redirect=None):
    """Dormant pre-import desktop startup seam; never call on browser/dev paths.

    Retain a private, non-inheritable duplicate of owned stdout for POD1.
    Redirect the CRT stdout descriptor to stderr before analytical imports.
    Redirect the current Win32 standard stdout handle too. Cached native
    handles and bootloader pre-entry output still require physical verification.
    The caller must fail startup on any exception, not fall back to legacy.
    No process-global descriptor operations run merely by importing this module.
    """
    import os
    if ops is None:
        ops = os
    if binary_mode is None:
        binary_mode = _binary_descriptor
    if native_redirect is None:
        native_redirect = _redirect_native_stdout
    duplicate = None
    try:
        descriptors = (stdin.fileno(), stdout.fileno(), stderr.fileno())
        if any(type(fd) is not int for fd in descriptors) or descriptors != (0, 1, 2):
            raise _fault()
        duplicate = ops.dup(1)
        if type(duplicate) is not int or duplicate <= 2:
            duplicate = None
            raise _fault()
        ops.set_inheritable(duplicate, False)
        if ops.get_inheritable(duplicate):
            raise _fault()
        # Redirect before any subsequent Python/CRT stdout writes. Do not
        # restore stdout on failure: this startup must terminate instead.
        ops.dup2(2, 1, inheritable=False)
        native_redirect(1)
        binary_mode(0)
        binary_mode(duplicate)
        writer = _ControlWriter(ops, duplicate)
        duplicate = None  # sole descriptor owner now the raw writer
        return 0, writer
    except BaseException as exc:
        if duplicate is not None:
            try:
                ops.close(duplicate)
            except OSError:
                pass
        if isinstance(exc, Exception):
            raise _fault() from None
        raise


class ControlBootstrap:
    """Single-use, trusted startup ownership; not registered in desktop_runner."""
    def __init__(self, generation, capability, descriptor, writer, ops):
        self._generation = generation
        self._capability = capability
        self._descriptor = descriptor
        self._writer = writer
        self._ops = ops
        self._used = False

    def run(self, coordinator, on_shutdown, *, ready=None, exit_on_shutdown=False):
        if self._used:
            raise _fault()
        self._used = True
        broker = HostBroker(coordinator, self._generation, self._capability, ready=ready)
        self._capability = None
        try:
            serve_owned(broker, lambda cap: self._ops.read(self._descriptor, cap),
                        self._writer.write, self._writer.flush, on_shutdown=on_shutdown,
                        exit_on_shutdown=exit_on_shutdown)
        finally:
            try:
                self._writer.close()
            except Exception:
                broker.transport_lost()
                raise _fault() from None

    def discard_unstarted(self):
        if self._used:
            raise _fault()
        self._used = True
        self._capability = None
        try:
            self._writer.close()
        except Exception:
            raise _fault() from None


def prepare_owned_control(environ, stdin, stdout, stderr, *, ops=None,
                          binary_mode=None, native_redirect=None):
    """Explicit desktop-owned control configuration. No legacy/dev fallback.

    Consume the control-only environment fields before analytical imports or
    descendant launches. The caller must already own the desktop workspace and
    must stop startup if this raises. Never expose this object to the browser.
    """
    import os
    generation = environ.pop("PILOTODIN_CONTROL_GENERATION", None)
    capability = environ.pop("PILOTODIN_CONTROL_CAPABILITY", None)
    if (environ.get("PILOTODIN_DESKTOP_WATCH_STDIN") != "1"
            or type(generation) is not str or not _HEX32.fullmatch(generation)
            or type(capability) is not str or not _HEX64.fullmatch(capability)):
        raise _fault()
    ops = os if ops is None else ops
    descriptor, writer = prepare_control_stdio(stdin, stdout, stderr, ops=ops,
                                              binary_mode=binary_mode,
                                              native_redirect=native_redirect)
    return ControlBootstrap(generation, capability, descriptor, writer, ops)
