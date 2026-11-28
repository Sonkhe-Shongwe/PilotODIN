"""C1 single-lane admission primitive; no I/O, persistence or worker spawning.

Only trusted engine/supervisor adapters may hold Lease objects. The core does not
prove actual worker completion. Callers must retain leases through cleanup and
supply genuine completion/exit evidence before release. Not yet wired to routes.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Callable
from uuid import uuid4


GIB = 1024 ** 3


class Operation(str, Enum):
    DATA = "data"
    TRAINING = "training"
    MODEL_LOAD = "model_load"
    EXPORT = "export"
    REPORT = "report"
    LOCAL_INFERENCE = "local_inference"


class Phase(str, Enum):
    RESERVED = "reserved"
    RUNNING = "running"
    DRAINING = "draining"
    BLOCKED = "blocked"


FLOORS = {op: (2 * GIB if op is Operation.LOCAL_INFERENCE else 3 * GIB // 4)
          for op in Operation}
MODES = frozenset(("adaptive", "low_memory", "performance"))


@dataclass(frozen=True, eq=False, repr=False)
class Lease:
    """Opaque in-process identity; never serialize or accept from a request."""
    operation_id: str
    generation: str
    operation: Operation


@dataclass(frozen=True)
class Admission:
    lease: Lease | None
    code: str
    required_bytes: int
    available_bytes: int | None = None

    @property
    def allowed(self) -> bool:
        return self.lease is not None


class Coordinator:
    """A single process-local reservation authority with no wait queue or TTL.

    Read policy and sample RAM outside the mutex. Revalidate the lane revision
    before granting, so an intervening acquire/release cannot reuse an old sample.
    Even Performance cannot bypass the lane or the screening floor.
    """
    def __init__(self, read_mode: Callable[[], str],
                 read_available_bytes: Callable[[], int | None]):
        self._mode = read_mode
        self._available = read_available_bytes
        self._lock = Lock()
        self._generation = uuid4().hex
        self._revision = 0
        self._lease: Lease | None = None
        self._phase: Phase | None = None
        self._stopping = False

    def _refusal(self) -> str | None:
        if self._stopping:
            return "shutting_down"
        if self._phase is Phase.BLOCKED:
            return "ownership_unknown"
        if self._lease is not None:
            return "resource_busy"
        return None

    def try_acquire(self, operation: Operation) -> Admission:
        if not isinstance(operation, Operation):
            raise ValueError("Unknown resource operation")
        floor = FLOORS[operation]
        with self._lock:
            reason = self._refusal()
            if reason:
                return Admission(None, reason, floor)
            revision = self._revision
        try:
            mode = self._mode()
            available = self._available()
        except Exception:
            return Admission(None, "memory_unavailable", floor)
        if not isinstance(mode, str) or mode not in MODES:
            return Admission(None, "policy_unavailable", floor)
        if type(available) is not int or available < 0:
            return Admission(None, "memory_unavailable", floor)
        with self._lock:
            reason = self._refusal()
            if reason:
                return Admission(None, reason, floor)
            if revision != self._revision:
                return Admission(None, "observation_stale", floor)
            if available < floor:
                return Admission(None, "low_memory_headroom", floor, available)
            lease = Lease(uuid4().hex, self._generation, operation)
            self._lease = lease
            self._phase = Phase.RESERVED
            self._revision += 1
            return Admission(lease, "reserved", floor, available)

    def _matches(self, lease: Lease) -> bool:
        return self._lease is lease and self._lease is not None

    def start(self, lease: Lease) -> bool:
        with self._lock:
            if (not self._matches(lease) or self._stopping
                    or self._phase is not Phase.RESERVED):
                return False
            self._phase = Phase.RUNNING
            return True

    def handoff(self, lease: Lease) -> Lease | None:
        """Transfer a not-yet-running operation to its actual queued worker.

        Old identity becomes incapable of starting/releasing the new owner's
        reservation. Caller must settle failed handoff/enqueue explicitly.
        """
        with self._lock:
            if (not self._matches(lease) or self._stopping
                    or self._phase is not Phase.RESERVED):
                return None
            replacement = Lease(lease.operation_id, lease.generation, lease.operation)
            self._lease = replacement
            return replacement

    def drain(self, lease: Lease) -> bool:
        with self._lock:
            if not self._matches(lease) or self._phase not in (
                    Phase.RESERVED, Phase.RUNNING, Phase.DRAINING):
                return False
            self._phase = Phase.DRAINING
            return True

    def block(self, lease: Lease) -> bool:
        """Uncertain completion retains the lane, including after timeout."""
        with self._lock:
            if not self._matches(lease):
                return False
            self._phase = Phase.BLOCKED
            return True

    def _clear(self) -> None:
        self._lease = None
        self._phase = None
        self._revision += 1

    def release(self, lease: Lease) -> bool:
        """Trusted caller has completed work and cleanup, or never started it."""
        with self._lock:
            if not self._matches(lease) or self._phase is Phase.BLOCKED:
                return False
            self._clear()
            return True

    def reconcile_completed(self, lease: Lease) -> bool:
        """Use only after independently confirmed completion of blocked owner.

        The core deliberately cannot manufacture a process-exit witness.
        """
        with self._lock:
            if not self._matches(lease) or self._phase is not Phase.BLOCKED:
                return False
            self._clear()
            return True

    def begin_shutdown(self) -> None:
        with self._lock:
            self._stopping = True
            self._revision += 1

    def status(self) -> dict:
        with self._lock:
            return {
                "phase": self._phase.value if self._phase else "idle",
                "operation": self._lease.operation.value if self._lease else None,
                "stopping": self._stopping,
                "active": self._lease is not None,
            }
