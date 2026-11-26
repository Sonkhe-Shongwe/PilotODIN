"""Versioned diagnostic receipt and exact missing-only proposal; fixture-only.

Historical schema-1 source and receipts stay pinned and unchanged. This module
has no live socket adapter, artifact upload/retrieval or production entrypoint.
"""
from __future__ import annotations

if __name__ == '__main__':
    raise SystemExit('FRESH_APPROVAL_REQUIRED: diagnostic collection is fixture-only')

from contextlib import nullcontext
import hashlib
import http.client
import os
from pathlib import Path
import re

import wheel_acquisition_offline as a
import wheel_archive_inspector as w
import wheel_notice_evidence as n

LIVE_ENABLED=False
SCOPE='SYNTHETIC_DIAGNOSTIC_V2_DISABLED'
DIAGNOSIS_BLOB='1dd2627eafba1f4695f972c1d23fac68340d05ee'
MISSING_PLAN_BLOB='9938c0f8cc5be3e118dec2eff953cae94f4b5a76'
INSPECTION_REASONS=frozenset(["ARCHIVE_HASH","ARCHIVE_SIZE","BATCH_DUPLICATE","BATCH_EXPANSION_LIMIT","BATCH_STOPPED","CONTROL_FILE_LIMIT","DECLARED_NOTICE_MISSING_OR_AMBIGUOUS","DIST_INFO_IDENTITY","DIST_NAME","DUPLICATE_JSON_KEY","EVIDENCE_BATCH_LIMIT","EVIDENCE_CANONICAL","EVIDENCE_DOCUMENT_HASH","EVIDENCE_DOCUMENT_LIMIT","EVIDENCE_IDENTITY","EXPECTED_INPUT","FALSE_CLEARANCE","HEADER_BOUNDS","HEADER_CARDINALITY","HEADER_DEFECT","HEADER_NUL","MALFORMED_EVIDENCE","MALFORMED_WHEEL","MEMBER_IDENTITY","MEMBER_INVENTORY","MEMBER_ROW","MEMBER_ROWS","METADATA_DECLARATIONS","METADATA_DIGEST","METADATA_EXPECTATION","METADATA_IDENTITY","NATIVE_CANDIDATE","NOTICE_CAPTURE_FLAG","NOTICE_EXPECTATION","NOTICE_FILE_LIMIT","NOTICE_PAYLOAD_IDENTITY","NOTICE_PAYLOAD_INVENTORY","NOTICE_PAYLOAD_LENGTH","NOTICE_PAYLOAD_ROW","NOTICE_TOTAL","PIN_DIGEST","PIN_LINE_ENDINGS","PIN_PATH","PIN_READ","PIN_SIZE","PLAN_COUNTS","PLAN_SOURCE_PINS","RECEIPT_BOUNDS","RECEIPT_FIELDS","RECEIPT_PLAN_IDENTITY","RECEIPT_TAGS","RECORD_DIGEST_SIZE","RECORD_INVENTORY","RECORD_ROW","RECORD_SELF","RECORD_SIGNATURE_UNSUPPORTED","UNPLANNED_WHEEL","UNSAFE_PATH","WHEEL_BUILD_TAG","WHEEL_FILENAME","WHEEL_HEADER","WHEEL_IDENTITY","WHEEL_TAG","WHEEL_TAG_MISMATCH","ZIP_BOUNDS","ZIP_CENTRAL_LAYOUT","ZIP_CRC_SIZE","ZIP_DEFLATE_INCOMPLETE","ZIP_DEFLATE_STALLED","ZIP_DEFLATE_TRAILING","ZIP_DIRECTORY_CASE","ZIP_DIRECTORY_LIMIT","ZIP_DUPLICATE","ZIP_END","ZIP_LOCAL_LAYOUT","ZIP_LOCAL_MISMATCH","ZIP_LOCAL_NAME","ZIP_NONREGULAR","ZIP_OBSERVED_EXPANSION","ZIP_PATH_BUDGET","ZIP_UNSUPPORTED","ZIP_WHEEL_EXPANSION","UNCLASSIFIED_INSPECTION_REFUSAL"])
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
    # Only reviewed machine codes, never arbitrary exception text or member
    # paths. Unknown exceptions stay generic; refusal is never relaxed.
    value=str(exc)
    return value if value in INSPECTION_REASONS else 'UNCLASSIFIED_INSPECTION_REFUSAL'


def derive_missing(rows, diag):
    need(len(rows)==68 and sum(x['bytes'] for x in rows)==225699980,'ORIGINAL_PLAN')
    need(diag['original_run']=='45729307962' and diag['original_source']=='d66357e3a76d6b05ca3db5fcc0be94f8d17dd269'
         and diag['artifact_id']=='15076022558' and diag['zip_bytes']==20475
         and diag['zip_sha256']=='efec26dd56725e3cf2619b9002037f37bdf118f98bac6c20c0f970fbbc39bdaf'
         and diag['status']=='REPLAY_PASS' and diag['retrievals']==1 and diag['wheel_requests']==0
         and diag['diagnosis_run_id']==45753813079 and diag['notice_payloads_republished'] is False,
         'PRIOR_DIAGNOSIS')
    settlement=diag['settlement']
    need(settlement=={'attempted_count':6,'expected_count':68,'license_reviewed':False,
         'missing':[x['filename'] for x in rows[5:]],'production_ready':False,
         'received_bytes':sum(x['bytes'] for x in rows[:6]),'status':'BLOCKED','verified_count':5},
         'PRIOR_SETTLEMENT')
    records=diag['records']
    need(type(records) is list and len(records)==6,'PRIOR_RECORDS')
    prior=[]
    for i,(row,entry) in enumerate(zip(rows[:6],records),1):
        result=entry['result']
        need(entry['filename']==row['filename'] and entry['expected_bytes']==row['bytes']
             and entry['expected_sha256']==row['sha256'] and result['sequence']==i
             and result['http_status']==200 and result['received_bytes']==row['bytes']
             and result['received_sha256']==row['sha256'],'PRIOR_RESULT_IDENTITY')
        if i==6:
            need(result['status']=='REFUSED' and result['reason']=='INSPECTION_REFUSED'
                 and result['evidence'] is None and 'inspection_receipt' not in entry,'PRIOR_REFUSAL')
            continue
        need(result['status']=='VERIFIED' and result['reason'] is None
             and result['evidence']==f'wheel-{i:03d}-evidence.json'
             and n.digest(entry['evidence_sha256'])
             and n.bounded_int(entry['evidence_bytes'],1,n.MAX_DOCUMENT),'PRIOR_VERIFIED')
        receipt=entry['inspection_receipt']
        n.validate_receipt(receipt,row)
        prior.append({'filename':row['filename'],'expected_bytes':row['bytes'],
             'expected_sha256':row['sha256'],'evidence_bytes':entry['evidence_bytes'],
             'evidence_sha256':entry['evidence_sha256'],'expanded_bytes':receipt['expanded_bytes'],
             'notice_bytes':receipt['notice_bytes']})
    remaining=plan_rows(rows[5:])
    def total(key): return sum(x[key] for x in prior)
    cap_exp=w.MAX_TOTAL-total('expanded_bytes')
    cap_notice=w.MAX_NOTICES-total('notice_bytes')
    cap_evidence=n.MAX_EVIDENCE_BATCH-total('evidence_bytes')
    need(min(cap_exp,cap_notice,cap_evidence)>=0,'PRIOR_BUDGET')
    need(len(remaining)==63 and sum(x['bytes'] for x in remaining)==225397605
         and total('expected_bytes')==302375,'MISSING_COUNTS')
    return {'schema_version':1,'status':'PROPOSED_DISABLED_MISSING_ONLY',
         'original_plan_blob':n.PLAN_BLOB,'diagnosis_blob':DIAGNOSIS_BLOB,
         'original_run_id':'45729307962','diagnosis_run_id':45753813079,
         'prior_verified':prior,'remaining_count':len(remaining),
         'remaining_bytes':sum(x['bytes'] for x in remaining),
         'prior_verified_bytes':total('expected_bytes'),
         'max_expanded_remaining':cap_exp,'max_notice_remaining':cap_notice,
         'max_evidence_remaining':cap_evidence,'max_requests':63,'redirects':0,'retries':0,
         'raw_prior_notices_retained_in_git':False,'production_ready':False,
         'license_reviewed':False,'wheels':remaining}


def review_missing_plan():
    rows=n.load_pinned_rows()
    diag=n.pinned_json(n.ROOT/(n.DIR+'wheel_receipt_diagnosis_45753813079.json'),DIAGNOSIS_BLOB)
    expected=n.pinned_json(n.ROOT/(n.DIR+'wheel_missing_plan_20261126.json'),MISSING_PLAN_BLOB)
    actual=derive_missing(rows,diag)
    need(n.canonical(expected)==n.canonical(actual),'MISSING_PLAN_IDENTITY')
    return actual


def run_fixture(rows, plan_blob, replay, parent):
    need(type(replay) is a.Replay and LIVE_ENABLED is False, 'OFFLINE_FIXTURE_ONLY')
    scope = SCOPE
    fetch = replay.get
    deadline = nullcontext
    rows = plan_rows(rows)
    batch = n._EvidenceBatch(rows, plan_blob)
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
        need(total <= MAX_BYTES, 'TOTAL_BUDGET')
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
    manifest = {'schema_version':2,'scope':scope,'plan_blob':plan_blob,
                'status':'CANDIDATE_EVIDENCE_RECORDED' if verified == len(rows) else 'BLOCKED',
                'expected_count':len(rows),'attempted_count':attempted,
                'verified_count':verified,'received_bytes':total,
                'missing':[r['filename'] for r in rows[verified:]],
                'license_reviewed':False,'production_ready':False}
    digest = store.finish(manifest)
    return store.path, digest



def verify_generation(path, manifest_sha, rows, plan_blob):
    """Independent read-only replay. Missing terminal manifest is unsettled."""
    scope = SCOPE
    rows = plan_rows(rows)
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
    need(set(m) == keys and type(m['schema_version']) is int and m['schema_version'] == 2
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
    evidence_bytes = total = verified = 0
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
            need(evidence_bytes <= n.MAX_EVIDENCE_BATCH,'EVIDENCE_BATCH_LIMIT')
            n.verify_evidence(evidence_raw,filemap[evidence_name]['sha256'],row,plan_blob)
            verified += 1
        else:
            need(result['status'] == 'REFUSED' and type(result['reason']) is str and result['reason'] in FAILURES
                 and result['evidence'] is None,'RESULT_IDENTITY')
            stopped = True
        need(get(result_name,MAX_RECORD) == result_raw,'RECEIPT_HASH')
    need(used == [f['name'] for f in files],'MANIFEST_FILE_ORDER')
    need(type(m['verified_count']) is int and m['verified_count'] == verified
         and type(m['received_bytes']) is int and m['received_bytes'] == total <= MAX_BYTES
         and m['missing'] == [r['filename'] for r in rows[verified:]]
         and ((m['status'] == 'BLOCKED' and stopped and count == verified+1)
              or (m['status'] == 'CANDIDATE_EVIDENCE_RECORDED' and not stopped
                  and count == verified == len(rows))), 'MANIFEST_SETTLEMENT')
    return m
