"""Disabled hosted policy-v3 transfer proposal.

Only generated fixtures and local receipt bundles are callable. There is no
live transport, service client, activation switch or arbitrary CLI. The pure
activation contract models a future exact gate, not permission to run it.
"""
from __future__ import annotations

if __name__=='__main__':
    raise SystemExit('FRESH_APPROVAL_REQUIRED: hosted policy-v3 adapter disabled')

import copy
import hashlib
import io
import os
from pathlib import Path
import re
import stat
import struct
import tempfile
import zipfile
import zlib

import wheel_acquisition_offline as a
import wheel_archive_inspector as w
import wheel_notice_evidence_v2 as n
import wheel_license_policy as p
import wheel_settlement_core as c
import wheel_settlement_fixture as f
import wheel_hosted_proposal as h
import wheel_diagnostic_offline as diagnostic

ROOT=n.ROOT
DIR=n.DIR
SELF=DIR+'wheel_hosted_policy_v3.py'
WORKFLOW='.github/workflows/c5-wheel-hosted-policy-v3-review.yml'
REPO='Sonkhe-Shongwe/PilotODIN'
BRANCH='refs/heads/feature/live-dev-workspace-20261023'
WORKFLOW_NAME='C5 hosted policy-v3 one-use acquisition'
OP='C5-WHEEL-POLICY-V3-HOSTED-ONCE-20261126'
MESSAGE=OP+' owner approved exact remaining-only acquisition'
MARKER=DIR+'APPROVAL_WHEEL_POLICY_V3_HOSTED_20261126.txt'
HOSTED_SCOPE='HOSTED_POLICY_V3_CANDIDATE_ONLY'
TRANSFER_SCOPE='SYNTHETIC_HOSTED_POLICY_V3_TRANSFER_DISABLED'
ARTIFACT_PREFIX='c5-policy-v3-receipts-'
SHA1=re.compile(r'[0-9a-f]{40}')
RUN=re.compile(r'[1-9][0-9]{0,19}')
SOURCE_PINS={
    DIR+'wheel_settlement_core.py':'263d2565d744f4e53289fb973ff0a205561e4a7c',
    DIR+'wheel_settlement_fixture.py':'e1343538f30e951f83213c1152f6cb76d8268309',
    DIR+'wheel_archive_inspector_v2.py':'9bf91fb983bd354f0b6db20dbb4eec32c447f369',
    DIR+'wheel_notice_evidence_v2.py':'81693017a1f287cafe521e6a7e958831cfd9dc6a',
    DIR+'wheel_license_policy.py':'876bb701544cee28e5f06851bc85c05acb74af35',
    DIR+'wheel_archive_inspector.py':'aa5ab610d711fb8f9bc1fce1020c4999e53f3571',
    DIR+'wheel_notice_evidence.py':'141f069706d0c597214829eea90a48197c381e2c',
    DIR+'wheel_acquisition_offline.py':'dc3f8ed48517ff796980ae766a4d4613c1471ef5',
    DIR+'wheel_hosted_proposal.py':'7d49568ebbcdf6209688973ab2a49a905d2125b7',
    DIR+'wheel_diagnostic_offline.py':'6aa10f588e24e582d7edf6226635adc6a591faad',
    DIR+'wheel_diagnostic_v3_offline.py':'8ad2a4af09f62e367863658351c3b3adc27731d5',
    DIR+'wheel_missing_hosted.py':'73311acf23aa6653c534678dd7710ff1a4e6a150',
    DIR+'wheel_acquisition_driver.py':'e888774ce5cabc5737c413ee47f3da64781443c2',
    '.github/workflows/c5-wheel-missing-hosted.yml':'7bf52665598af6619de024f143288ab626f7ccc2',
    DIR+'wheel_prior_notice_preservation_45729307962.json':'1adcd112c54ffa90ee638bcd7598d879e01798bc',
}
LEGACY_MARKERS=(DIR+'APPROVAL_WHEEL_HOSTED_20261126.txt',
                DIR+'APPROVAL_WHEEL_MISSING_HOSTED_20261126.txt',
                DIR+'APPROVAL_WHEEL_PRIOR_NOTICE_PRESERVATION_20261126.txt')
need=a.need

def plan():
    for path,pin in SOURCE_PINS.items():
        p.pinned_text(ROOT/path,pin)
    for path in (*LEGACY_MARKERS,MARKER):
        item=ROOT/path
        need(not item.exists() and not item.is_symlink(),'DISARMED_MARKER')
    return c.remaining_inputs()

def plan_identity():
    rows,bindings,caps=plan()
    return {'plan_blob':diagnostic.MISSING_PLAN_BLOB,'rows_sha256':w.sha(n.canonical(rows)),
            'policy_sha256':w.sha(n.canonical(bindings)), 'caps':caps,
            'count':len(rows),'redirects':0,'retries':0}

def marker_bytes(inputs):
    return (OP+'\n'+w.sha(n.canonical(inputs))+'\n'
            '63 exact wheel GETs; 225397605 body bytes; no redirects or retries.\n').encode('ascii')

def activation_contract(event, context, checkout, expected, phase):
    """Pure fixture check. Expected values must come from separate review.

    No environment read, Git call, network, file mutation or live capability.
    The independently reviewed future parent/child and source/workflow blobs
    must be fixed before a marker-only push; the current proposal is disarmed.
    """
    need(phase in ('collect-once','retrieve-once'),'GATE_PHASE')
    keys={'parent','head','driver_blob','workflow_blob','inputs'}
    need(type(expected) is dict and set(expected)==keys
         and all(type(expected[k]) is str and SHA1.fullmatch(expected[k])
                 for k in ('parent','head','driver_blob','workflow_blob'))
         and expected['head']!=expected['parent']
         and n.canonical(expected['inputs'])==n.canonical(plan_identity()),'GATE_EXPECTATION')
    need(type(context) is dict and context.get('GITHUB_ACTIONS')=='true'
         and context.get('GITHUB_EVENT_NAME')=='push'
         and context.get('GITHUB_REPOSITORY')==REPO and context.get('GITHUB_REF')==BRANCH
         and context.get('GITHUB_WORKFLOW')==WORKFLOW_NAME
         and context.get('GITHUB_JOB')==phase and context.get('GITHUB_RUN_ATTEMPT')=='1'
         and context.get('C5_APPROVED_ONCE')==OP and context.get('GITHUB_SHA')==expected['head']
         and context.get('C5_DRIVER_BLOB')==expected['driver_blob']
         and context.get('C5_WORKFLOW_BLOB')==expected['workflow_blob']
         and type(context.get('GITHUB_RUN_ID')) is str and RUN.fullmatch(context['GITHUB_RUN_ID']),
         'GATE_CONTEXT')
    need(type(event) is dict and event.get('ref')==BRANCH and event.get('before')==expected['parent']
         and event.get('after')==expected['head'] and event.get('forced') is False
         and event.get('created') is False and event.get('deleted') is False
         and type(event.get('repository')) is dict and event['repository'].get('full_name')==REPO
         and type(event.get('head_commit')) is dict and event['head_commit'].get('id')==expected['head']
         and event['head_commit'].get('message')==MESSAGE,'GATE_EVENT')
    need(type(checkout) is dict and checkout.get('head')==expected['head']
         and checkout.get('parents')==[expected['parent']] and checkout.get('message')==MESSAGE
         and checkout.get('changes')==[('A',MARKER)] and checkout.get('marker')==marker_bytes(expected['inputs'])
         and checkout.get('driver_blob')==expected['driver_blob']
         and checkout.get('workflow_blob')==expected['workflow_blob']
         and checkout.get('marker_blob')==git_blob(marker_bytes(expected['inputs']))
         and checkout.get('legacy_markers_absent') is True,'GATE_CHECKOUT')
    return {'scope':TRANSFER_SCOPE,'run':context['GITHUB_RUN_ID'],'phase':phase,
            'source_sha':expected['head'],'inputs_sha256':w.sha(n.canonical(expected['inputs']))}

def git_blob(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()

def fixture_claim(parent,event,context,checkout,expected,phase):
    """Only a disposable synthetic claim; never consumed as live authority."""
    claim=activation_contract(event,context,checkout,expected,phase)
    parent=Path(parent)
    need(parent.is_dir() and not parent.is_symlink(),'CLAIM_SCOPE')
    name='fixture-policy-v3-'+claim['run']+'-'+phase+'.claim'
    try:
        with (parent/name).open('xb') as out:
            raw=n.canonical(claim)
            need(out.write(raw)==len(raw),'CLAIM_WRITE')
            out.flush()
            os.fsync(out.fileno())
    except FileExistsError:
        raise w.Blocked('ONE_USE_CLAIM_CONSUMED') from None
    a.sync_dir(parent)
    return claim

def produce():
    raise w.Blocked('FRESH_APPROVAL_REQUIRED')

def retrieve():
    raise w.Blocked('FRESH_APPROVAL_REQUIRED')

def run_fixture(rows,plan_blob,replay,parent,*,bindings,caps):
    return f.run_fixture(rows,plan_blob,replay,parent,bindings=bindings,caps=caps)

def verify_generation(path,manifest_sha,rows,plan_blob,*,bindings,caps):
    return f.verify_fixture(path,manifest_sha,rows,plan_blob,bindings=bindings,caps=caps)

def bundle_cap(caps):
    c.prior.check_caps(caps)
    # Remaining-only bound; up to 63 intents/results, one manifest and framing.
    return caps['evidence']+2*63*a.MAX_RECORD+a.MAX_MANIFEST+65536

def artifact_record(run,source,bundle,rows,plan_blob,*,bindings,caps):
    rows,bindings,caps,policy_sha=c.prepare(rows,plan_blob,bindings,caps,c.FIXTURE_SCOPE)
    need(len(rows)<=63,'REMAINING_COUNT')
    need(type(run) is str and RUN.fullmatch(run) and type(source) is str and SHA1.fullmatch(source),
         'RECEIPT_CONTEXT')
    need(type(bundle) is dict and set(bundle)=={'bytes','sha256','manifest_sha256'}
         and n.bounded_int(bundle['bytes'],len(h.MAGIC)+2,bundle_cap(caps))
         and n.digest(bundle['sha256']) and n.digest(bundle['manifest_sha256']),'BUNDLE_IDENTITY')
    return {'schema_version':2,'scope':TRANSFER_SCOPE,'run_id':run,'run_attempt':1,
            'source_sha':source,'artifact_name':ARTIFACT_PREFIX+run+'-1',
            'plan_blob':plan_blob,'rows_sha256':w.sha(n.canonical(rows)),
            'policy_sha256':policy_sha,'caps':caps,'bundle':copy.deepcopy(bundle)}

def verify_artifact_metadata(meta,record,expected_run,expected_sha,expected_id,upload_sha,
                             rows,plan_blob,*,bindings,caps):
    need(type(record) is dict and 'bundle' in record,'RECEIPT_CONTEXT')
    reviewed=artifact_record(expected_run,expected_sha,record['bundle'],rows,plan_blob,bindings=bindings,caps=caps)
    need(n.canonical(record)==n.canonical(reviewed),'RECEIPT_CONTEXT')
    need(type(meta) is dict and n.bounded_int(expected_id,1,2**63-1)
         and type(meta.get('id')) is int and meta['id']==expected_id
         and meta.get('name')==reviewed['artifact_name'] and meta.get('expired') is False
         and n.bounded_int(meta.get('size_in_bytes'),1,bundle_cap(caps)+1024*1024),'ARTIFACT_IDENTITY')
    workflow=meta.get('workflow_run')
    need(type(workflow) is dict and type(workflow.get('id')) is int
         and str(workflow['id'])==expected_run and workflow.get('head_sha')==expected_sha
         and workflow.get('head_branch')==BRANCH.removeprefix('refs/heads/'),'ARTIFACT_RUN')
    need(n.digest(upload_sha) and meta.get('digest')=='sha256:'+upload_sha,'ARTIFACT_UPLOAD_IDENTITY')
    return {'id':expected_id,'bytes':meta['size_in_bytes'],'sha256':upload_sha}

def export_generation(path, manifest_sha, rows, plan_blob, parent, *, bindings, caps):
    """Verify before packaging; exclusive file in fresh disposable directory."""
    need(len(rows)<=63,'REMAINING_COUNT')
    m = verify_generation(path,manifest_sha,rows,plan_blob,bindings=bindings,caps=caps)
    names = sorted([x['name'] for x in m['files']]+['manifest.json'])
    need(len(names)<=h.MAX_FILES,'BUNDLE_COUNT')
    expected = {f['name']:f for f in m['files']}
    dest = Path(tempfile.mkdtemp(prefix='c5-wheel-export-',dir=parent))/'receipts.odin'
    digest = hashlib.sha256()
    size = 0
    with dest.open('xb') as out:
        def write(raw):
            nonlocal size
            size += len(raw)
            need(size <= bundle_cap(caps),'BUNDLE_LIMIT')
            need(out.write(raw)==len(raw),'BUNDLE_SHORT_WRITE')
            digest.update(raw)
        write(h.MAGIC+struct.pack('>H',len(names)))
        for name in names:
            raw = a.read_bounded(Path(path)/name,h.limit_for(name))
            need(w.sha(raw)==manifest_sha if name=='manifest.json' else
                 a.file_identity(name,raw)==expected[name],'EXPORT_CHANGED')
            write(h._frame(name,raw))
        out.flush()
        os.fsync(out.fileno())
    a.sync_dir(dest.parent)
    a.sync_dir(dest.parent.parent)
    return dest,{'bytes':size,'sha256':digest.hexdigest(),'manifest_sha256':manifest_sha}


def import_generation(bundle, identity, rows, plan_blob, parent, *, bindings, caps):
    """Verify exact bundle snapshot against separately retained identity, then replay."""
    c.prepare(rows,plan_blob,bindings,caps,c.FIXTURE_SCOPE)
    need(len(rows)<=63,'REMAINING_COUNT')
    need(type(identity) is dict and set(identity)=={'bytes','sha256','manifest_sha256'}
         and n.bounded_int(identity['bytes'],len(h.MAGIC)+2,bundle_cap(caps))
         and n.digest(identity['sha256']) and n.digest(identity['manifest_sha256']),
         'BUNDLE_IDENTITY')
    raw = a.read_bounded(Path(bundle),bundle_cap(caps))
    need(len(raw)==identity['bytes'] and w.sha(raw)==identity['sha256'],'BUNDLE_HASH')
    stream = io.BytesIO(raw)
    need(stream.read(len(h.MAGIC))==h.MAGIC,'BUNDLE_MAGIC')
    count_raw=stream.read(2)
    need(len(count_raw)==2,'BUNDLE_HEADER')
    count=struct.unpack('>H',count_raw)[0]
    need(3<=count<=3*len(rows)+1,'BUNDLE_COUNT')
    dest=Path(tempfile.mkdtemp(prefix='c5-wheel-import-',dir=parent))
    seen=[]
    evidence_bytes=0
    for _ in range(count):
        hdr=stream.read(h.FRAME.size)
        need(len(hdr)==h.FRAME.size,'BUNDLE_TRUNCATED')
        name_len,size=h.FRAME.unpack(hdr)
        need(1<=name_len<=64,'BUNDLE_NAME')
        try:
            name=stream.read(name_len).decode('ascii')
        except UnicodeError:
            raise w.Blocked('BUNDLE_NAME') from None
        need(len(name)==name_len and (not seen or seen[-1]<name),'BUNDLE_ORDER')
        need(0<size<=h.limit_for(name),'BUNDLE_FILE_SIZE')
        if name.startswith('wheel-'):
            evidence_bytes+=size
            need(evidence_bytes<=caps['evidence'],'EVIDENCE_BATCH_LIMIT')
        data=stream.read(size)
        need(len(data)==size,'BUNDLE_TRUNCATED')
        with (dest/name).open('xb') as out:
            need(out.write(data)==len(data),'BUNDLE_SHORT_WRITE')
            out.flush()
            os.fsync(out.fileno())
        seen.append(name)
    need(not stream.read(1),'BUNDLE_TRAILING')
    a.sync_dir(dest)
    a.sync_dir(dest.parent)
    m=verify_generation(dest,identity['manifest_sha256'],rows,plan_blob,bindings=bindings,caps=caps)
    return dest,m


def replay_artifact(raw, meta, record, expected_run, expected_sha, expected_id, upload_sha,
                    rows, plan_blob, parent,
                    *, bindings, caps):
    """Read exact bounded artifact ZIP; never extract arbitrary archive paths."""
    ident = verify_artifact_metadata(meta,record,expected_run,expected_sha,expected_id,upload_sha,
                                     rows,plan_blob,bindings=bindings,caps=caps)
    need(type(raw) is bytes and len(raw)==ident['bytes']<=bundle_cap(caps)+1024*1024 and w.sha(raw)==ident['sha256'],
         'ARTIFACT_HASH')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos=z.infolist()
            need(len(infos)==1 and not z.comment,'ARTIFACT_INVENTORY')
            item=infos[0]
            need(item.filename==item.orig_filename=='receipts.odin' and not item.is_dir()
                 and not item.flag_bits & 1 and item.compress_type in (0,8)
                 and not item.external_attr & (0x400 | 0x08 | 0x10 | 0x40)
                 and not (item.external_attr>>16) & (stat.S_ISUID|stat.S_ISGID|stat.S_ISVTX)
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
        return import_generation(dest,bundle,rows,plan_blob,parent,bindings=bindings,caps=caps)
    except (zipfile.BadZipFile,NotImplementedError,RuntimeError,EOFError,zlib.error):
        raise w.Blocked('ARTIFACT_ZIP_REFUSED') from None



