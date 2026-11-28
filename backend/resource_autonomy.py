"""Staged autonomous workload stages; not registered in production.

The trusted host adapter must own inference admission and actual worker exit.
This module never starts inference itself, accepts no browser capability, and
does not infer native exit from a planner return. The host seam is unimplemented.
"""
import json
import math

try:
    from .resource_admission import Operation
except ImportError:
    from resource_admission import Operation


MAX_CONTEXT_BYTES = 64 * 1024
MAX_CONTEXT_NODES = 8192
MAX_CONTEXT_DEPTH = 16
MAX_EVIDENCE_BYTES = 256 * 1024


class ResourceDeferred(RuntimeError):
    """No heavy stage began; preserve the existing resumable checkpoint."""


class LaunchRefused(RuntimeError):
    """Known refusal before durable publication, or confirmed no launch."""


class ContextLimit(ValueError):
    """Known context size refusal, with no detached work."""


def bounded_context_bytes(value):
    """Bound work before encoding; never create an unbounded JSON buffer."""
    nodes = 0
    chars = 0

    def visit(item, depth):
        nonlocal nodes, chars
        nodes += 1
        if nodes > MAX_CONTEXT_NODES or depth > MAX_CONTEXT_DEPTH:
            raise ContextLimit("context structure limit")
        kind = type(item)
        if kind is str:
            chars += len(item)
            if chars > MAX_CONTEXT_BYTES:
                raise ContextLimit("context character limit")
        elif kind is dict:
            if len(item) > MAX_CONTEXT_NODES - nodes:
                raise ContextLimit("context item limit")
            for key, child in item.items():
                if type(key) is not str:
                    raise ValueError("Context keys must be strings")
                visit(key, depth + 1)
                visit(child, depth + 1)
        elif kind is list:
            if len(item) > MAX_CONTEXT_NODES - nodes:
                raise ContextLimit("context item limit")
            for child in item:
                visit(child, depth + 1)
        elif kind is int:
            if item.bit_length() > 256:
                raise ContextLimit("context integer limit")
        elif kind is float:
            if not math.isfinite(item):
                raise ValueError("Non-finite context number")
        elif item is not None and kind is not bool:
            raise ValueError("Unsupported context value")

    visit(value, 0)
    encoded = bytearray()
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False,
                               separators=(",", ":"))
    for piece in encoder.iterencode(value):
        # Each individual string is already character-bounded by visit().
        chunk = piece.encode("utf-8")
        if len(chunk) > MAX_CONTEXT_BYTES - len(encoded):
            raise ContextLimit("context UTF-8 limit")
        encoded.extend(chunk)
    return bytes(encoded)


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
            try:
                value = callback(*args)
                if value is None:
                    return None
                return bounded_context_bytes(value)
            except ContextLimit:
                return b""  # known refusal, no ambiguous worker cleanup
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
