"""Fixture-only v3 settlement for inspector-v2 evidence. No live adapter."""
from __future__ import annotations

if __name__ == '__main__':
    raise SystemExit('FRESH_APPROVAL_REQUIRED: v3 diagnostic collection is fixture-only')

from contextlib import nullcontext
import hashlib
import http.client
import os
from pathlib import Path
import re
import wheel_acquisition_offline as a
import wheel_archive_inspector as w
import wheel_archive_inspector_v2 as v2
import wheel_notice_evidence_v2 as n
import wheel_diagnostic_offline as historical

LIVE_ENABLED=False
FIXTURE_SCOPE='SYNTHETIC_DIAGNOSTIC_V3_DISABLED'
INSPECTION_REASONS=historical.INSPECTION_REASONS | frozenset({
    'INSPECTOR_SCHEMA','DIRECTORY_RECEIPT_IDENTITY','ZIP_REPARSE_ATTRIBUTE',
    'ZIP_SPECIAL_ATTRIBUTE','ZIP_SYMLINK','ZIP_SPECIAL_MODE',
    'ZIP_DIRECTORY_ATTRIBUTES','ZIP_DIRECTORY_PAYLOAD'
})
MAX_BYTES=a.MAX_BYTES
MAX_MANIFEST=a.MAX_MANIFEST
MAX_REQUESTS=a.MAX_REQUESTS
MAX_RECORD=a.MAX_RECORD
FAILURES=a.FAILURES
need=a.need
plan_rows=a.plan_rows
_Generation=a._Generation
_receive=a._receive
request_intent=a.request_intent
file_identity=a.file_identity
read_bounded=a.read_bounded
parse=a.parse

def safe_inspection_reason(exc):
    value=str(exc)
    return value if value in INSPECTION_REASONS else 'UNCLASSIFIED_INSPECTION_REFUSAL'

def check_caps(caps):
    limits={'body':a.MAX_BYTES,'expanded':v2.MAX_TOTAL,'notice':v2.MAX_NOTICES,
            'evidence':n.MAX_EVIDENCE_BATCH}
    need(type(caps) is dict and set(caps)==set(limits)
         and all(n.bounded_int(caps[k],0,v) for k,v in limits.items()),'RESIDUAL_CAPS')

def review_missing_plan():
    return historical.review_missing_plan()

def residual_caps(plan):
    return {'body':plan['remaining_bytes'],'expanded':plan['max_expanded_remaining'],
            'notice':plan['max_notice_remaining'],'evidence':plan['max_evidence_remaining']}

def run_fixture(rows, plan_blob, replay, parent, *, caps):
    need(type(replay) is a.Replay and LIVE_ENABLED is False,'OFFLINE_FIXTURE_ONLY')
    fetch=replay.get
    deadline=nullcontext
    scope=FIXTURE_SCOPE
    check_caps(caps)
    need(scope == FIXTURE_SCOPE,'SCOPE')
    rows = plan_rows(rows)
    need(sum(row['bytes'] for row in rows)<=caps['body'],'RESIDUAL_BODY_LIMIT')
    batch = n._EvidenceBatch(rows, plan_blob)
    batch._budget.expanded=w.MAX_TOTAL-caps['expanded']
    batch._budget.notices=w.MAX_NOTICES-caps['notice']
    batch._persisted_bytes=n.MAX_EVIDENCE_BATCH-caps['evidence']
    store = _Generation(parent)
    total = verified = attempted = 0
    for i, row in enumerate(rows, 1):
        prefix = f'request-{i:03d}'
        intent = request_intent(row, i)
        # Before issuing the request, persist exact scope and consume sequence.
        store.put(prefix+'-intent.json', n.canonical(intent))
        attempted += 1
        state = {'http_status':None,'received_bytes':0,'hash':hashlib.sha256()}
        reason = None
        inspection_reason = None
        evidence = None
        response = None
        try:
            with deadline():
                try:
                    response = fetch(intent['url'])
                    raw = _receive(row, response, state, store.path)
                finally:
                    if response is not None:
                        response.close()
                        response = None
        except w.Blocked as exc:
            reason = str(exc)
            need(reason in FAILURES, 'UNEXPECTED_REFUSAL')
        except (OSError, http.client.HTTPException):
            reason = 'TRANSPORT_ERROR'
        finally:
            if response is not None:
                response.close()
        total += state['received_bytes']
        need(total <= caps['body'], 'TOTAL_BUDGET')
        if reason is None:
            try:
                doc, digest = batch.inspect(row['filename'], raw)
            except w.Blocked as exc:
                reason = 'INSPECTION_REFUSED'
                inspection_reason = safe_inspection_reason(exc)
            else:
                evidence = f'wheel-{i:03d}-evidence.json'
                store.put(evidence, doc)
                need(w.sha(doc) == digest, 'EVIDENCE_HASH')
                verified += 1
            finally:
                del raw
        result = {'sequence':i,'http_status':state['http_status'],
                  'received_bytes':state['received_bytes'],
                  'received_sha256':state['hash'].hexdigest(),
                  'status':'VERIFIED' if reason is None else 'REFUSED',
                  'reason':reason,'inspection_reason':inspection_reason,'evidence':evidence}
        store.put(prefix+'-result.json', n.canonical(result))
        if reason is not None:
            break
    manifest = {'schema_version':3,'scope':scope,'plan_blob':plan_blob,
                'status':'CANDIDATE_EVIDENCE_RECORDED' if verified == len(rows) else 'BLOCKED',
                'expected_count':len(rows),'attempted_count':attempted,
                'verified_count':verified,'received_bytes':total,
                'missing':[r['filename'] for r in rows[verified:]],
                'license_reviewed':False,'production_ready':False}
    digest = store.finish(manifest)
    return store.path, digest




def verify_generation(path, manifest_sha, rows, plan_blob, *, scope, caps):
    """Independent read-only replay. Missing terminal manifest is unsettled."""
    check_caps(caps)
    need(scope == FIXTURE_SCOPE,'SCOPE')
    rows = plan_rows(rows)
    need(sum(row['bytes'] for row in rows)<=caps['body'],'RESIDUAL_BODY_LIMIT')
    path = Path(path)
    need(path.is_dir() and not path.is_symlink(), 'GENERATION_PATH')
    manifest_path = path/'manifest.json'
    need(manifest_path.is_file() and not manifest_path.is_symlink(), 'UNSETTLED_GENERATION')
    raw = read_bounded(manifest_path, MAX_MANIFEST)
    need(n.digest(manifest_sha) and w.sha(raw) == manifest_sha, 'MANIFEST_HASH')
    m = parse(raw)
    keys = {'schema_version','scope','plan_blob','status','expected_count',
            'attempted_count','verified_count','received_bytes','missing',
            'license_reviewed','production_ready','files'}
    need(set(m) == keys and type(m['schema_version']) is int and m['schema_version'] == 3
         and m['scope'] == scope and m['plan_blob'] == plan_blob
         and m['license_reviewed'] is False and m['production_ready'] is False,
         'MANIFEST_IDENTITY')
    count = m['attempted_count']
    need(type(count) is int and 1 <= count <= len(rows)
         and type(m['expected_count']) is int and m['expected_count'] == len(rows),
         'MANIFEST_COUNTS')
    files = m['files']
    need(type(files) is list and 2*count <= len(files) <= 3*count, 'MANIFEST_FILES')
    filemap = {}
    for entry in files:
        need(type(entry) is dict and set(entry) == {'name','bytes','sha256'},'MANIFEST_FILE')
        name = entry['name']
        need(type(name) is str and re.fullmatch(
            r'(?:request-\d{3}-(?:intent|result)|wheel-\d{3}-evidence)\.json',name)
            and name not in filemap and n.digest(entry['sha256']), 'MANIFEST_FILE')
        limit = n.MAX_DOCUMENT if name.startswith('wheel-') else MAX_RECORD
        need(n.bounded_int(entry['bytes'],1,limit), 'MANIFEST_FILE')
        filemap[name] = entry
    actual = set()
    with os.scandir(path) as it:
        for item in it:
            need(len(actual) < 3*MAX_REQUESTS+1 and item.is_file(follow_symlinks=False),
                 'GENERATION_INVENTORY')
            actual.add(item.name)
    need(actual == set(filemap) | {'manifest.json'}, 'GENERATION_INVENTORY')
    used = []
    evidence_bytes = total = verified = expanded = notices = 0
    stopped = False

    def get(name, limit):
        need(name in filemap and name not in used, 'MANIFEST_FILE')
        raw = read_bounded(path/name, limit)
        need(file_identity(name,raw) == filemap[name], 'RECEIPT_HASH')
        used.append(name)
        return raw

    for i,row in enumerate(rows[:count],1):
        need(not stopped,'REQUEST_AFTER_REFUSAL')
        prefix = f'request-{i:03d}'
        need(get(prefix+'-intent.json',MAX_RECORD) == n.canonical(request_intent(row,i)),
             'INTENT_IDENTITY')
        evidence_name = f'wheel-{i:03d}-evidence.json'
        # Read result via manifest without consuming its order yet.
        result_name = prefix+'-result.json'
        result_raw = read_bounded(path/result_name,MAX_RECORD)
        need(file_identity(result_name,result_raw) == filemap.get(result_name),'RECEIPT_HASH')
        result = parse(result_raw)
        need(set(result) == {'sequence','http_status','received_bytes','received_sha256',
                            'status','reason','inspection_reason','evidence'} and
             type(result['sequence']) is int and result['sequence'] == i
             and n.bounded_int(result['received_bytes'],0,row['bytes'])
             and n.digest(result['received_sha256'])
             and (result['http_status'] is None or n.bounded_int(result['http_status'],100,599)),
             'RESULT_IDENTITY')
        detail=result['inspection_reason']
        if result['reason']=='INSPECTION_REFUSED':
            need(type(detail) is str and detail in INSPECTION_REASONS
                 and result['status']=='REFUSED' and result['http_status']==200
                 and result['received_bytes']==row['bytes'] and result['received_sha256']==row['sha256'],
                 'INSPECTION_DETAIL_IDENTITY')
        else:
            need(detail is None,'INSPECTION_DETAIL_IDENTITY')
        if result['received_bytes'] == 0:
            need(result['received_sha256'] == w.sha(b''),'RESULT_IDENTITY')
        total += result['received_bytes']
        if result['status'] == 'VERIFIED':
            need(result['reason'] is None and result['http_status'] == 200
                 and result['received_bytes'] == row['bytes']
                 and result['received_sha256'] == row['sha256']
                 and result['evidence'] == evidence_name,'RESULT_IDENTITY')
            evidence_raw = get(evidence_name,n.MAX_DOCUMENT)
            evidence_bytes += len(evidence_raw)
            need(evidence_bytes <= caps['evidence'],'EVIDENCE_BATCH_LIMIT')
            receipt=n.verify_evidence(evidence_raw,filemap[evidence_name]['sha256'],row,plan_blob)
            expanded+=receipt['expanded_bytes']; notices+=receipt['notice_bytes']
            need(expanded<=caps['expanded'] and notices<=caps['notice'],'BATCH_EXPANSION_LIMIT')
            verified += 1
        else:
            need(result['status'] == 'REFUSED' and type(result['reason']) is str and result['reason'] in FAILURES
                 and result['evidence'] is None,'RESULT_IDENTITY')
            stopped = True
        need(get(result_name,MAX_RECORD) == result_raw,'RECEIPT_HASH')
    need(used == [f['name'] for f in files],'MANIFEST_FILE_ORDER')
    need(type(m['verified_count']) is int and m['verified_count'] == verified
         and type(m['received_bytes']) is int and m['received_bytes'] == total <= caps['body']
         and m['missing'] == [r['filename'] for r in rows[verified:]]
         and ((m['status'] == 'BLOCKED' and stopped and count == verified+1)
              or (m['status'] == 'CANDIDATE_EVIDENCE_RECORDED' and not stopped
                  and count == verified == len(rows))), 'MANIFEST_SETTLEMENT')
    return m


