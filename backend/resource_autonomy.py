"""Staged autonomous workload stages; not registered in production.

The trusted host adapter must own inference admission and actual worker exit.
This module never starts inference itself, accepts no browser capability, and
does not infer native exit from a planner return. The host seam is unimplemented.
"""
import json

try:
    from .resource_admission import Operation
except ImportError:
    from resource_admission import Operation


MAX_CONTEXT_BYTES = 64 * 1024


class ResourceDeferred(RuntimeError):
    """No heavy stage began; preserve the existing resumable checkpoint."""


class AutonomyStages:
    def __init__(self, coordinator, owned_planner):
        if not callable(owned_planner):
            raise TypeError("An owned host planner adapter is required")
        self.coordinator = coordinator
        self._owned_planner = owned_planner

    def data(self, callback, *args, **kwargs):
        """Only synchronous, non-detached data work; no inference inside."""
        admission = self.coordinator.try_acquire(Operation.DATA)
        lease = admission.lease
        if lease is None:
            raise ResourceDeferred(admission.code)
        if not self.coordinator.start(lease):
            self.coordinator.release(lease)
            raise ResourceDeferred("shutting_down")
        try:
            result = callback(*args, **kwargs)
        except BaseException:
            self.coordinator.block(lease)
            raise
        if not self.coordinator.release(lease):
            self.coordinator.block(lease)
            raise RuntimeError("Autonomy data ownership unconfirmed")
        return result

    def context(self, callback, *args):
        def serialize():
            value = callback(*args)
            if value is None:
                return None
            payload = json.dumps(value, ensure_ascii=False, allow_nan=False,
                                 separators=(",", ":")).encode("utf-8")
            if len(payload) > MAX_CONTEXT_BYTES:
                return b""  # known refusal, no ambiguous worker cleanup
            return payload
        payload = self.data(serialize)
        if payload == b"":
            raise ResourceDeferred("context_limit")
        return payload

    def plan(self, payload):
        if type(payload) is not bytes or not 0 < len(payload) <= MAX_CONTEXT_BYTES:
            raise ValueError("Invalid bounded planner context")
        # Host callback must acquire/own the shared inference grant, respect
        # cancellation and prove actual native exit before releasing. No
        # fallback to the legacy planner or second Python inference reservation.
        return self._owned_planner(payload)
