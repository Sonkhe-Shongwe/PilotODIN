"""Bind C-D09 coordinator to existing stage/witness code, not a live controller.
Acquisition and process settlement must be separately reviewed and supplied.
"""
import hashlib
import os
from pathlib import Path

from . import validation_coordinator as c, validation_witnesses as w, python_stage as p

LIVE_ENABLED = False
DISPOSITION_PIN = None
SOURCE_PIN = None


def disposition(raw, plan, profile, source, generation):
    w.need(DISPOSITION_PIN is not None and w.blob(raw) == DISPOSITION_PIN, 'DISPOSITION_UNRESOLVED')
    doc = w.strict_json(raw)
    w.need(doc['status'] == 'REVIEWED_INTERNAL_HOSTED_USE'
           and doc['manifest_blob'] == w.MANIFEST_PIN and doc['source'] == source
           and doc['generation'] == generation and doc['redistribution'] == 'NOT_AUTHORISED', 'DISPOSITION_SCOPE')
    d = doc['profiles'][profile['id']]
    rows = [profile['pip'], *profile['wheels'], *profile['fonts'], *profile['npm_archives']]
    w.need(set(d['archives']) == {r['filename'] for r in rows}, 'DISPOSITION_SET')
    for row in rows:
        a = d['archives'][row['filename']]
        key = 'sha256' if 'sha256' in row else 'sha512' if 'sha512' in row else 'git_blob_sha1'
        w.need(a['use'] == 'REVIEWED' and a[key] == row[key], 'DISPOSITION_ARCHIVE')
        if key == 'git_blob_sha1':
            w.need(p.SHA256.fullmatch(a['measured_sha256']), 'FONT_HASH')
    w.need(d['runner_reviewed'] is True and d['network_scope'] == 'EXACT_APPROVED_ENDPOINTS_ONLY'
           and d['interpreter']['version'] == profile['python'] and d['interpreter']['licence_use'] == 'REVIEWED'
           and d['font_equivalence'] == 'REVIEWED_PINNED_SIX_FILES'
           and d['font_coverage_expected'] == w.COVERAGE, 'DISPOSITION_TOOLS')
    return d, hashlib.sha256(raw).hexdigest()


class ProfileOperations:
    """Concrete callback binding; future host adapter supplies verified transport/run.

    Scratch is an exclusive TemporaryDirectory. On any exception the owner must
    confirm all command descendants settled before cleanup. This class does not
    certify process isolation, origin or the authority of injected callbacks.
    """
    def __init__(self, profile, reviewed, scratch, env, interpreter, node, npm_cli,
                 acquire, run, frontend_copy, cleanup):
        w.need(LIVE_ENABLED is True, 'PROFILE_ADAPTER_DISARMED')
        w.require_live()
        p.require_live()
        self.profile, self.reviewed = profile, reviewed
        self.scratch, self.env = w.host_scratch(scratch), env
        self.interpreter, self.node, self.npm_cli = interpreter,node,npm_cli
        self.acquire, self.run, self.frontend_copy, self.cleanup = acquire,run,frontend_copy,cleanup
        self.pip_meta = reviewed['archives'][profile['pip']['filename']]['wheel_expectation']['metadata_sha256']
        self.house = self.scratch/'wheels'; self.house.mkdir()
        self.pip_dir = self.scratch/'pip'; self.pip_dir.mkdir()
        self.extra = self.scratch/'extra'; self.extra.mkdir()
        self.counter = 0
        self.cleanup_attempted = False
        self.rows = []
        self.python = None

    def prepare_a(self, profile, rows, lock_text):
        w.need(profile == self.profile and self.python is None, 'STAGE_A_STATE')
        pip = self.pip_dir/profile['pip']['filename']
        self.acquire(profile['pip'],pip)
        p.file_digest(pip,profile['pip'])
        self.python = p.bootstrap_python(self.interpreter,pip,profile,self.pip_meta,self.scratch,self.env,self.run)
        self._wheels(rows)
        lock = self.scratch/'smoke-lock.txt'
        with lock.open('x',encoding='ascii') as f:
            f.write(lock_text)
        p.resolve_install(self.python,self.rows,lock,self.house,self.scratch,self.env,self.pip_meta,self.run)

    def _wheels(self, rows):
        for row in rows:
            path = self.house/row['filename']
            w.need(not path.exists(), 'WHEEL_ALREADY_STAGED')
            self.acquire(row,path)
            p.file_digest(path,row)
            self.rows.append(row)

    def prepare_b(self, profile, rows):
        w.need(profile == self.profile and self.python is not None, 'STAGE_B_STATE')
        p.exact_inventory(self.python,self.rows,self.scratch,self.env,self.pip_meta,self.run)
        self._wheels(rows)
        source = w.ROOT/'backend/locks'/(profile['id']+'.txt')
        raw = p.check_lock(source.read_bytes(),profile)
        lock = self.scratch/'full-lock.txt'
        with lock.open('xb') as f:
            f.write(raw)
        p.resolve_install(self.python,self.rows,lock,self.house,self.scratch,self.env,self.pip_meta,self.run)

    def verify_native(self, profile):
        w.need(profile == self.profile, 'PROFILE_IDENTITY')
        return p.verify_loaded_native(self.python,profile,self.scratch,self.env,self.run)

    def pytest(self, selector, expected):
        self.counter += 1
        return c.pytest_witness(self.python,selector,self.scratch/('pytest-'+str(self.counter)),self.env,self.run,expected)

    def mixed(self):
        return w.mixed_witness(self.python,self.scratch/'mixed-worker',self.env,self.run)

    def font(self):
        for row in self.profile['fonts']:
            self.acquire(row,self.extra/row['filename'])
        return w.font_witness(self.profile['id'],self.python,self.scratch,self.env,
                              self.reviewed,self.profile['fonts'],self.extra,self.run)

    def frontend(self):
        for row in self.profile['npm_archives']:
            self.acquire(row,self.extra/row['filename'])
        work = self.frontend_copy(self.scratch/'frontend')
        return w.frontend_witness(self.profile['id'],self.node,self.npm_cli,work,self.scratch,
                                  self.env,self.profile['npm_archives'],self.extra,self.reviewed,self.run)

    def finish_owned_scratch(self):
        w.need(not self.cleanup_attempted, 'CLEANUP_ALREADY_ATTEMPTED')
        self.cleanup_attempted = True
        result = self.cleanup()
        w.need(not self.scratch.exists() and result['cleanup'] == 'OWNED_SCRATCH_REMOVED', 'SCRATCH_CLEANUP')
        return result


def run_profile(raw_plan, raw_disposition, profile_id, source, generation, windows_receipt, **adapters):
    w.need(LIVE_ENABLED is True and SOURCE_PIN is not None and source == SOURCE_PIN
           and os.environ.get('GITHUB_SHA') == source, 'PROFILE_ADAPTER_DISARMED')
    w.require_live()
    plan = w.read_plan(raw_plan)
    profile, = [x for x in plan['profiles'] if x['id'] == profile_id]
    reviewed, sha = disposition(raw_disposition,plan,profile,source,generation)
    if profile == plan['profiles'][1]:
        w.linux_eligible(plan,windows_receipt,generation,source,sha)
    else:
        w.need(windows_receipt is None, 'WINDOWS_FIRST')
    operations = ProfileOperations(profile,reviewed,**adapters)
    try:
        return c.run_profile(plan,profile,generation,source,sha,windows_receipt,operations)
    finally:
        if operations.scratch.exists() and not operations.cleanup_attempted:
            # The supplied cleanup adapter must refuse removal until child settlement.
            operations.finish_owned_scratch()


if __name__ == '__main__':
    raise SystemExit('PROFILE_ADAPTER_DISARMED')
