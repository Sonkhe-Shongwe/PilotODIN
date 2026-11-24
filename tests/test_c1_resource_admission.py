"""Pure C1 reservation tests: no app import, owner files, real model or native run."""
import ast
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event

import pytest

from backend.resource_admission import Coordinator, GIB, Lease, Operation, Phase, FLOORS
from backend.resource_routes import ROUTES


@pytest.mark.parametrize("mode", ["adaptive", "low_memory", "performance"])
@pytest.mark.parametrize("operation", list(Operation))
def test_all_modes_and_operations_enforce_exact_floor(mode, operation):
    floor = FLOORS[operation]
    memory = [floor - 1]
    c = Coordinator(lambda: mode, lambda: memory[0])
    assert c.try_acquire(operation).code == "low_memory_headroom"
    assert not c.status()["active"]
    memory[0] = floor
    accepted = c.try_acquire(operation)
    assert accepted.allowed and accepted.available_bytes == floor
    assert c.start(accepted.lease)
    assert c.try_acquire(Operation.DATA).code == "resource_busy"
    assert c.release(accepted.lease)
    assert c.status()["phase"] == "idle"


@pytest.mark.parametrize("sample", [None, -1, True, 1.5, "2147483648"])
def test_invalid_memory_fails_closed(sample):
    c = Coordinator(lambda: "performance", lambda: sample)
    assert c.try_acquire(Operation.DATA).code == "memory_unavailable"
    assert not c.status()["active"]


def test_observer_error_and_bad_mode_fail_closed():
    def fail():
        raise OSError("private path must not appear")
    assert Coordinator(lambda: "adaptive", fail).try_acquire(Operation.DATA).code == "memory_unavailable"
    assert Coordinator(lambda: [], lambda: 3 * GIB).try_acquire(Operation.DATA).code == "policy_unavailable"
    with pytest.raises(ValueError):
        Coordinator(lambda: "adaptive", lambda: 3 * GIB).try_acquire("data")


def test_atomic_mixed_workload_race():
    n = 12
    entered = Barrier(n)
    def sample():
        entered.wait(timeout=5)
        return 3 * GIB
    c = Coordinator(lambda: "performance", sample)
    with ThreadPoolExecutor(max_workers=n) as pool:
        results = list(pool.map(c.try_acquire, list(Operation) * 2))
    winners = [r for r in results if r.allowed]
    assert len(winners) == 1
    assert all(r.code == "resource_busy" for r in results if not r.allowed)
    assert c.release(winners[0].lease)


def test_sample_invalidated_by_intervening_completed_work():
    sampled = Event()
    resume = Event()
    first = [True]
    def read():
        if first[0]:
            first[0] = False
            sampled.set()
            assert resume.wait(timeout=5)
        return 3 * GIB
    c = Coordinator(lambda: "adaptive", read)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(c.try_acquire, Operation.DATA)
        try:
            assert sampled.wait(timeout=5)
            other = c.try_acquire(Operation.TRAINING).lease
            assert other and c.release(other)
        finally:
            resume.set()
        assert pending.result(timeout=5).code == "observation_stale"
    assert not c.status()["active"]


def test_handoff_and_stale_release_are_identity_bound():
    c = Coordinator(lambda: "adaptive", lambda: 3 * GIB)
    old = c.try_acquire(Operation.TRAINING).lease
    new = c.handoff(old)
    assert new is not None and old.operation_id == new.operation_id
    forged = Lease(new.operation_id, new.generation, new.operation)
    for invalid in (old, forged):
        assert not c.start(invalid)
        assert not c.release(invalid)
    assert c.start(new)
    assert c.handoff(new) is None
    assert c.release(new)
    later = c.try_acquire(Operation.EXPORT).lease
    assert not c.release(new)
    assert c.status()["operation"] == "export"
    assert c.release(later)


def test_uncertain_completion_and_drain_do_not_free_lane():
    c = Coordinator(lambda: "adaptive", lambda: 3 * GIB)
    lease = c.try_acquire(Operation.LOCAL_INFERENCE).lease
    assert c.start(lease) and c.drain(lease)
    assert c.try_acquire(Operation.DATA).code == "resource_busy"
    assert c.block(lease)
    assert c.status()["phase"] == Phase.BLOCKED.value
    assert not c.release(lease)
    assert c.try_acquire(Operation.DATA).code == "ownership_unknown"
    assert c.reconcile_completed(lease)
    assert not c.reconcile_completed(lease)
    assert c.try_acquire(Operation.DATA).allowed


def test_shutdown_preserves_outstanding_owner():
    c = Coordinator(lambda: "adaptive", lambda: 3 * GIB)
    lease = c.try_acquire(Operation.TRAINING).lease
    c.begin_shutdown()
    assert c.status()["active"]
    assert not c.start(lease)
    assert c.handoff(lease) is None
    assert c.try_acquire(Operation.DATA).code == "shutting_down"
    assert c.release(lease)
    assert c.try_acquire(Operation.DATA).code == "shutting_down"


def test_shutdown_invalidates_inflight_observation():
    started, resume = Event(), Event()
    def read():
        started.set()
        assert resume.wait(timeout=5)
        return 3 * GIB
    c = Coordinator(lambda: "adaptive", read)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(c.try_acquire, Operation.DATA)
        try:
            assert started.wait(timeout=5)
            c.begin_shutdown()
        finally:
            resume.set()
        assert pending.result(timeout=5).code == "shutting_down"


def test_route_inventory_matches_actual_source_without_importing_app():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "backend/main.py").read_text(encoding="utf-8"))
    actual = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for d in node.decorator_list:
            if (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                    and isinstance(d.func.value, ast.Name) and d.func.value.id == "app"
                    and d.func.attr in {"get", "post", "put", "patch", "delete", "head", "options", "api_route", "route", "websocket"}):
                assert d.func.attr in {"get", "post", "put", "patch", "delete", "head", "options"}, "Review new registration form"
                key = (d.func.attr.upper(), ast.literal_eval(d.args[0]))
                assert key not in actual
                actual[key] = node.name
    assert actual == {key: plan.endpoint for key, plan in ROUTES.items()}
    assert all(plan.operation is None or plan.operation in {x.value for x in Operation}
               for plan in ROUTES.values())
    assert ROUTES["POST", "/api/projects"].lifetime == "upload"
    assert ROUTES["POST", "/api/projects/{project_id}/experiments"].lifetime == "training_handoff"
    assert ROUTES["POST", "/api/projects/{project_id}/quality/export"].lifetime == "stream"
    assert ROUTES["POST", "/api/projects/{project_id}/ai/insight"].lifetime == "staged_inference"
    assert ROUTES["POST", "/api/experiments/{experiment_id}/cancel"].operation is None
