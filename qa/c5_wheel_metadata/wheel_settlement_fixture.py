"""Only inert Replay is a callable collection frontdoor in this revision."""
from __future__ import annotations

if __name__=='__main__':
    raise SystemExit('FRESH_APPROVAL_REQUIRED: policy settlement fixture-only')

from contextlib import nullcontext
import wheel_acquisition_offline as a
import wheel_settlement_core as core

LIVE_ENABLED=False

def run_fixture(rows,plan_blob,replay,parent,*,bindings,caps):
    a.need(type(replay) is a.Replay and LIVE_ENABLED is False,'OFFLINE_FIXTURE_ONLY')
    return core._collect(rows,plan_blob,bindings,caps,core.FIXTURE_SCOPE,replay.get,nullcontext,parent)

def verify_fixture(path,sha,rows,plan_blob,*,bindings,caps):
    return core.verify_generation(path,sha,rows,plan_blob,scope=core.FIXTURE_SCOPE,
                                  bindings=bindings,caps=caps)
