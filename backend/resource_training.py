"""Staged training ownership seam; no live route registration or model work.

A trusted request adapter acquires before preparation, calls publication_started
before durable queue creation, binds the exact queued record, and invokes
finish_request after the full ASGI call (including failure). Worker and terminal
callbacks are synchronous and must not detach work. The storage adapter must
provide exact queued-only settlement and a durable terminal-state witness.
"""
from threading import Lock

try:
    from .resource_admission import Coordinator, Operation
except ImportError:
    from resource_admission import Coordinator, Operation


class TrainingOwnership:
    def __init__(self, coordinator: Coordinator):
        self.coordinator = coordinator
        self.admission = coordinator.try_acquire(Operation.TRAINING)
        self._lease = self.admission.lease
        self._lock = Lock()
        self._state = "preparing" if self._lease is not None else "denied"
        self._request_done = False
        self._transferred = False
        self._eid = None

    def publication_started(self):
        """Call immediately before the durable queue transaction."""
        with self._lock:
            if self._state != "preparing" or self._request_done:
                raise RuntimeError("Training publication not permitted")
            self._state = "publishing"

    def publication_refused(self):
        """Only for a confirmed no-publication outcome, never a lost ack."""
        with self._lock:
            if self._state != "publishing" or self._request_done:
                raise RuntimeError("Training publication not pending")
            self._state = "preparing"

    def bind(self, eid, worker, settle_unstarted, terminal):
        """Bind exact durable ID; return a once-only synchronous callback.

        settle_unstarted(eid) must confirm terminal after queued-only CAS.
        terminal(eid) must confirm the durable state after actual worker return.
        A false or raising witness must retain the lane.
        """
        if not isinstance(eid, str) or not eid or len(eid) > 128:
            raise ValueError("Invalid queued experiment identity")
        if not all(callable(f) for f in (worker, settle_unstarted, terminal)):
            raise TypeError("Missing training ownership callbacks")
        with self._lock:
            if self._state != "publishing" or self._request_done:
                raise RuntimeError("Training handoff not permitted")
            self._eid = eid
            self._worker = worker
            self._settle = settle_unstarted
            self._terminal = terminal
            replacement = self.coordinator.handoff(self._lease)
            if replacement is not None:
                self._lease = replacement
                self._transferred = True
            # If shutdown prevented handoff, still own the known queued record.
            # The callback may only settle it; it cannot start model work.
            self._state = "queued"
        return self.run

    def _block_locked(self):
        self._state = "blocked"
        self.coordinator.block(self._lease)

    def _release_if_complete_locked(self):
        if self._request_done and self._state == "done":
            if self.coordinator.release(self._lease):
                self._state = "released"
            else:
                self._block_locked()

    def _complete(self, witness):
        with self._lock:
            if witness is not True:
                self._block_locked()
                return
            self._state = "done"
            self._release_if_complete_locked()

    def _settle_unstarted(self):
        try:
            witness = self._settle(self._eid)
        except BaseException:
            with self._lock:
                self._block_locked()
            raise
        self._complete(witness)

    def run(self):
        # Race against response finalization and duplicate/late callback.
        with self._lock:
            if self._state != "queued":
                return
            started = self._transferred and self.coordinator.start(self._lease)
            self._state = "running" if started else "settling"
        if not started:
            self._settle_unstarted()
            return
        try:
            self._worker(self._eid)
            witness = self._terminal(self._eid)
        except BaseException:
            with self._lock:
                self._block_locked()
            raise
        self._complete(witness)

    def finish_request(self, *, preparation_completed):
        """Settle the full request; never treat an escaped worker as stopped.

        preparation_completed is a trusted adapter witness: no worker or
        detached preparation remains and publication outcome is known.
        A running callback remains the owner even if its response is lost.
        """
        settle = False
        with self._lock:
            if self._request_done:
                return
            self._request_done = True
            if self._state == "preparing":
                if preparation_completed is True:
                    self._state = "done"
                else:
                    self._block_locked()
            elif self._state == "publishing":
                # A queue commit may have succeeded without returning its ID.
                self._block_locked()
            elif self._state == "queued":
                # Exclude a late callback before exact queued-only settlement.
                self._state = "settling"
                settle = True
            self._release_if_complete_locked()
        if settle:
            self._settle_unstarted()
