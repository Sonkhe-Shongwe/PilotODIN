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
                     "observation_stale","low_memory_headroom"))


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
    def __init__(self, coordinator, generation, capability):
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
        if request.command == "STOP":
            self._stop()
            return self._reply(seq,"ADMISSION_STOPPED")
        if request.command == "GRANT_REQUEST":
            if self._stopping:
                return self._reply(seq,"GRANT_REPLY","DENIED","shutting_down")
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
            self._pending_reply = None
        except BaseException:
            self.transport_lost()
            raise


def serve_owned(broker, read_chunk, write_reply, flush_reply):
    """Staged single-reader/writer pump over already owned binary streams.

    The caller provides read-at-most, write and flush functions. No descriptor
    is opened or closed here. STOP stops admission, not the control channel:
    a host may still need to drain/release its exact grant. EOF is a terminal
    transport fault. An independent host deadline must cover blocking I/O;
    this synchronous pump never asserts that a blocked call has completed.
    """
    if not isinstance(broker, HostBroker):
        raise TypeError("Trusted resource broker required")
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
    except BaseException as exc:
        broker.transport_lost()
        if isinstance(exc, Exception):
            raise _fault() from None
        raise
