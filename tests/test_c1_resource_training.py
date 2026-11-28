"""Staged C1 training ownership tests; inert callbacks, no model execution."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from backend.resource_admission import Coordinator, GIB, Operation
from backend.resource_training import TrainingOwnership


def coordinator(memory=3 * GIB):
    return Coordinator(lambda: "adaptive", lambda: memory)


def test_denied_before_preparation():
    c = coordinator(0)
    owner = TrainingOwnership(c)
    assert not owner.admission.allowed
    with pytest.raises(RuntimeError):
        owner.publication_started()
    owner.finish_request(preparation_completed=True)
    assert not c.status()["active"]


@pytest.mark.parametrize("refused", [False, True])
def test_known_no_publication_releases(refused):
    c = coordinator()
    owner = TrainingOwnership(c)
    assert c.status()["phase"] == "reserved"
    assert c.try_acquire(Operation.DATA).code == "resource_busy"
    if refused:
        owner.publication_started()
        owner.publication_refused()
    owner.finish_request(preparation_completed=True)
    assert not c.status()["active"]


@pytest.mark.parametrize("publishing", [False, True])
def test_uncertain_preparation_or_publication_blocks(publishing):
    c = coordinator()
    owner = TrainingOwnership(c)
    if publishing:
        owner.publication_started()
    owner.finish_request(preparation_completed=publishing)
    assert c.status()["phase"] == "blocked"
    assert c.try_acquire(Operation.EXPORT).code == "ownership_unknown"


def bind(owner, worker, settle, terminal):
    owner.publication_started()
    return owner.bind("experiment-a", worker, settle, terminal)


def test_worker_completion_does_not_release_before_request_completion():
    c = coordinator()
    owner = TrainingOwnership(c)
    events = []
    old = owner.admission.lease
    callback = bind(owner, lambda eid: events.append(eid),
                    lambda eid: pytest.fail("already started"), lambda eid: True)
    assert not c.release(old)
    callback()
    callback()
    assert events == ["experiment-a"]
    assert c.status()["active"]
    owner.finish_request(preparation_completed=True)
    assert not c.status()["active"]


def test_lost_response_during_worker_retains_lane_until_callback_returns():
    c = coordinator()
    owner = TrainingOwnership(c)
    entered, resume = Event(), Event()
    def worker(eid):
        assert eid == "experiment-a"
        entered.set()
        assert resume.wait(5)
    callback = bind(owner, worker, lambda eid: pytest.fail("running worker"),
                    lambda eid: True)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(callback)
        try:
            assert entered.wait(5)
            owner.finish_request(preparation_completed=False)
            callback()
            assert c.status()["phase"] == "running"
            assert c.try_acquire(Operation.DATA).code == "resource_busy"
        finally:
            resume.set()
        future.result(5)
    assert not c.status()["active"]


@pytest.mark.parametrize("confirmed", [False, True])
def test_unstarted_settlement_and_late_callback(confirmed):
    c = coordinator()
    owner = TrainingOwnership(c)
    entered, resume = Event(), Event()
    calls = []
    def settle(eid):
        calls.append(eid)
        entered.set()
        assert resume.wait(5)
        return confirmed
    callback = bind(owner, lambda eid: pytest.fail("late callback"), settle,
                    lambda eid: pytest.fail("not started"))
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(owner.finish_request, preparation_completed=False)
        try:
            assert entered.wait(5)
            callback()
            assert c.status()["active"]
        finally:
            resume.set()
        future.result(5)
    assert calls == ["experiment-a"]
    assert c.status()["phase"] == ("idle" if confirmed else "blocked")


@pytest.mark.parametrize("shutdown_before_bind", [False, True])
def test_shutdown_settles_exact_unstarted_record(shutdown_before_bind):
    c = coordinator()
    owner = TrainingOwnership(c)
    owner.publication_started()
    if shutdown_before_bind:
        c.begin_shutdown()
    settled = []
    def settle(eid):
        settled.append(eid)
        return True
    callback = owner.bind("experiment-a", lambda eid: pytest.fail("shutdown"),
                          settle, lambda eid: False)
    if not shutdown_before_bind:
        c.begin_shutdown()
    callback()
    owner.finish_request(preparation_completed=True)
    assert settled == ["experiment-a"]
    assert not c.status()["active"]
    assert c.try_acquire(Operation.DATA).code == "shutting_down"


@pytest.mark.parametrize("failure", ["worker", "terminal", "unconfirmed", "settle"])
def test_uncertain_worker_or_settlement_retains_lane(failure):
    c = coordinator()
    owner = TrainingOwnership(c)
    def fail(eid):
        raise OSError("fixture failure")
    callback = bind(owner, fail if failure == "worker" else lambda eid: None,
                    fail if failure == "settle" else lambda eid: True,
                    fail if failure == "terminal" else lambda eid: False)
    if failure == "settle":
        with pytest.raises(OSError):
            owner.finish_request(preparation_completed=False)
    else:
        if failure == "unconfirmed":
            callback()
        else:
            with pytest.raises(OSError):
                callback()
        owner.finish_request(preparation_completed=True)
    assert c.status()["phase"] == "blocked"
    assert c.try_acquire(Operation.REPORT).code == "ownership_unknown"
