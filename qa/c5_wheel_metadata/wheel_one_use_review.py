"""Disarmed C5 one-use workflow review and independent artifact replay.

No live acquisition or artifact service calls in this module's current CLI.
Artifact bytes and digest must be supplied by an independently reviewed channel.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import zipfile

if __name__ == '__main__' and sys.argv[1:] == ['--collect']:
    raise SystemExit('FRESH_APPROVAL_REQUIRED: one-use workflow is disabled')

import wheel_acquisition_offline as a
import wheel_archive_inspector as w
import wheel_hosted_proposal as h
import wheel_notice_evidence as n

ENABLED = False
SOURCE_PINS = {
    'wheel_archive_inspector.py':'aa5ab610d711fb8f9bc1fce1020c4999e53f3571',
    'wheel_notice_evidence.py':'141f069706d0c597214829eea90a48197c381e2c',
    'wheel_acquisition_offline.py':'dc3f8ed48517ff796980ae766a4d4613c1471ef5',
    'wheel_hosted_proposal.py':'7d49568ebbcdf6209688973ab2a49a905d2125b7',
    'review_input_proposals.py':'092b806e11badc9ad8d559cf1a2d1660ef95de07',
    'wheel_acquisition_plan_20261125.json':'1aa96a7172508f94b2cdc4b7aabd65e3b8f21f89',
    'platform_lock_candidates_45703125465.json':'6b27407f4b24942c385179bb253f692370f21df7',
    'production_graph_receipt_45705552265.json':'70cdac979b732aadfad0c51d7e159a60840cc1ef',
}
MARKER_PATH = n.DIR + 'APPROVAL_WHEEL_HOSTED_20261126.txt'
MESSAGE = 'C5-WHEEL-HOSTED-ONCE-20261126 owner approved exact wheel acquisition'
ARTIFACT_PREFIX = 'c5-wheel-receipts-'
MAX_ZIP = h.MAX_BUNDLE + 1024*1024
SHA1 = re.compile(r'[0-9a-f]{40}')
RUN = re.compile(r'[1-9][0-9]{0,19}')


def need(ok, reason):
    w.require(ok, reason)


def git_blob(raw):
    import hashlib
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def verify_pins(root=n.ROOT):
    for name, digest in SOURCE_PINS.items():
        raw = a.read_bounded(Path(root)/n.DIR/name,n.MAX_PIN)
        need(git_blob(raw)==digest,'SOURCE_PIN')
    need(h.LIVE_ENABLED is False and a.LIVE_ENABLED is False and ENABLED is False,
         'DISARMED_SOURCE')
    return a.review_pinned_plan()


def activation_contract(event, env, *, head, parent, changes, message, marker):
    """Pure review of the future exact marker-only push, not authority.

    An independently approved armed tree and exact activation commit must also
    be verified by the operator before dispatch; this function cannot establish
    ownership of approval or source pins for a changed guard/workflow.
    """
    need(type(head) is str and SHA1.fullmatch(head) and type(parent) is str
         and SHA1.fullmatch(parent) and head != parent,'ACTIVATION_SHA')
    need(env.get('GITHUB_ACTIONS')=='true' and env.get('GITHUB_EVENT_NAME')=='push'
         and env.get('GITHUB_REF')==h.BRANCH and env.get('GITHUB_WORKFLOW')==h.WORKFLOW
         and env.get('GITHUB_RUN_ATTEMPT')=='1' and env.get('GITHUB_SHA')==head
         and env.get('C5_EXPECTED_SOURCE_SHA')==head and env.get('C5_APPROVED_ONCE')==h.OP
         and RUN.fullmatch(env.get('GITHUB_RUN_ID','')),'ACTIVATION_CONTEXT')
    need(event.get('ref')==h.BRANCH and event.get('before')==parent and event.get('after')==head
         and event.get('forced') is False and event.get('created') is False
         and event.get('deleted') is False,'ACTIVATION_EVENT')
    need(message==MESSAGE and changes==[('A',MARKER_PATH)] and marker==h.MARKER_BYTES,
         'ACTIVATION_SCOPE')
    return True


def identity(run_id, source_sha, bundle):
    need(type(run_id) is str and RUN.fullmatch(run_id) and type(source_sha) is str
         and SHA1.fullmatch(source_sha),'RECEIPT_CONTEXT')
    need(type(bundle) is dict and set(bundle)=={'bytes','sha256','manifest_sha256'}
         and n.bounded_int(bundle['bytes'],len(h.MAGIC)+2,h.MAX_BUNDLE)
         and n.digest(bundle['sha256']) and n.digest(bundle['manifest_sha256']),
         'BUNDLE_IDENTITY')
    return {'schema_version':1,'run_id':run_id,'run_attempt':1,'source_sha':source_sha,
            'artifact_name':ARTIFACT_PREFIX+run_id+'-1','bundle':bundle}


def verify_identity(record, expected_run, expected_sha):
    need(type(record) is dict and type(record.get('schema_version')) is int
         and type(record.get('run_attempt')) is int and 'bundle' in record
         and record==identity(expected_run,expected_sha,record['bundle']),'RECEIPT_CONTEXT')
    return record


def verify_artifact_metadata(meta, record, expected_run, expected_sha):
    """Bind artifact service metadata to independently observed job identity."""
    verify_identity(record,expected_run,expected_sha)
    need(type(meta) is dict and n.bounded_int(meta.get('id'),1,2**63-1)
         and meta.get('name')==record['artifact_name'] and meta.get('expired') is False
         and n.bounded_int(meta.get('size_in_bytes'),1,MAX_ZIP),'ARTIFACT_IDENTITY')
    workflow = meta.get('workflow_run')
    need(type(workflow) is dict and type(workflow.get('id')) is int
         and str(workflow['id'])==expected_run and workflow.get('head_sha')==expected_sha
         and workflow.get('head_branch')==h.BRANCH.removeprefix('refs/heads/'),'ARTIFACT_RUN')
    digest = meta.get('digest')
    need(type(digest) is str and re.fullmatch(r'sha256:[0-9a-f]{64}',digest),
         'ARTIFACT_DIGEST')
    return {'id':meta['id'],'bytes':meta['size_in_bytes'],'sha256':digest[7:]}


def replay_artifact(raw, meta, record, expected_run, expected_sha, rows, plan_blob, parent,
                    *, scope=a.HOSTED_SCOPE):
    """Read exact bounded artifact ZIP; never extract arbitrary archive paths."""
    ident = verify_artifact_metadata(meta,record,expected_run,expected_sha)
    need(type(raw) is bytes and len(raw)==ident['bytes'] and w.sha(raw)==ident['sha256'],
         'ARTIFACT_HASH')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos=z.infolist()
            need(len(infos)==1 and not z.comment,'ARTIFACT_INVENTORY')
            item=infos[0]
            need(item.filename==item.orig_filename=='receipts.odin' and not item.is_dir()
                 and not item.flag_bits & 1 and item.compress_type in (0,8)
                 and not item.external_attr & 0x400
                 and stat.S_IFMT(item.external_attr>>16) in (0,stat.S_IFREG),
                 'ARTIFACT_MEMBER')
            bundle=record['bundle']
            need(item.file_size==bundle['bytes'] and item.compress_size<=len(raw),
                 'ARTIFACT_MEMBER_SIZE')
            dest=Path(tempfile.mkdtemp(prefix='c5-artifact-replay-',dir=parent))/'receipts.odin'
            import hashlib
            sha=hashlib.sha256()
            total=0
            with z.open(item) as src, dest.open('xb') as out:
                while True:
                    chunk=src.read(min(a.CHUNK,bundle['bytes']-total+1))
                    if not chunk: break
                    total+=len(chunk)
                    need(total<=bundle['bytes'],'ARTIFACT_MEMBER_SIZE')
                    sha.update(chunk)
                    need(out.write(chunk)==len(chunk),'ARTIFACT_SHORT_WRITE')
                out.flush()
                os.fsync(out.fileno())
            need(total==bundle['bytes'] and sha.hexdigest()==bundle['sha256'],'BUNDLE_HASH')
        return h.import_generation(dest,bundle,rows,plan_blob,parent,scope=scope)
    except (zipfile.BadZipFile,NotImplementedError,RuntimeError,EOFError):
        raise w.Blocked('ARTIFACT_ZIP_REFUSED') from None


def collect_once():
    # Future arm must implement reviewed runtime Git/event verification and
    # independent armed-source pins before changing either disabled constant.
    # No fallback route or arbitrary artifact publication in this revision.
    need(ENABLED is True,'FRESH_APPROVAL_REQUIRED')
    raise w.Blocked('ACTIVATION_CONTRACT_NOT_ARMED')
