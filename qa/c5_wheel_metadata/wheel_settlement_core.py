"""Internal policy-bound schema-3 settlement algorithms.

Transport is supplied by a reviewed frontdoor; this revision admits only the
fixture scope. No sockets, artifact service, activation or arbitrary CLI.
Internal Python seams are not an adversarial in-process sandbox.
"""
from __future__ import annotations

if __name__ == '__main__':
    raise SystemExit('OFFLINE_LIBRARY_ONLY: policy-bound settlement core')

import base64
import copy
import hashlib
import http.client
import os
from pathlib import Path
import re

import wheel_acquisition_offline as a
import wheel_archive_inspector as w
import wheel_archive_inspector_v2 as v2
import wheel_notice_evidence_v2 as n
import wheel_notice_evidence as old
import wheel_license_policy as p
import wheel_diagnostic_v3_offline as prior

FIXTURE_SCOPE='SYNTHETIC_POLICY_V3_DISABLED'
INSPECTION_REASONS=prior.INSPECTION_REASONS | p.REFUSALS
MAX_MANIFEST=a.MAX_MANIFEST
MAX_REQUESTS=a.MAX_REQUESTS
MAX_RECORD=a.MAX_RECORD
FAILURES=a.FAILURES
need=a.need
_Generation=a._Generation
_receive=a._receive
request_intent=a.request_intent
file_identity=a.file_identity
read_bounded=a.read_bounded
parse=a.parse

def safe_inspection_reason(exc):
    value=str(exc)
    return value if value in INSPECTION_REASONS else 'UNCLASSIFIED_INSPECTION_REFUSAL'

def prepare(rows, plan_blob, bindings, caps, scope):
    need(scope==FIXTURE_SCOPE,'SCOPE')
    need(type(plan_blob) is str and 0<len(plan_blob)<=128,'EVIDENCE_IDENTITY')
    prior.check_caps(caps)
    rows=a.plan_rows(copy.deepcopy(rows))
    caps=dict(caps)
    need(sum(r['bytes'] for r in rows)<=caps['body'],'RESIDUAL_BODY_LIMIT')
    need(type(bindings) is dict and set(bindings)=={r['filename'] for r in rows},
         'METADATA_POLICY_IDENTITY')
    bindings=copy.deepcopy(bindings)
    for row in rows:
        p.match(row,bindings[row['filename']])
    policy_sha=w.sha(n.canonical(bindings))
    return rows,bindings,caps,policy_sha

def remaining_inputs():
    """Reconcile independently pinned plan, five historical notices and limits.
    Return data only, never authority. Historical plan bytes stay unchanged.
    """
    plan=prior.review_missing_plan()
    full=n.load_pinned_rows()
    bindings=p.load_bindings()
    env=n.pinned_json(n.ROOT/(n.DIR+p.PRIOR),p.PRIOR_BLOB)
    need(env['schema_version']==1 and env['scope']=='PRIOR_NOTICE_EVIDENCE_ONLY'
         and env['license_reviewed'] is False and env['production_ready'] is False
         and len(env['documents'])==len(plan['prior_verified'])==5,'PRIOR_POLICY_IDENTITY')
    totals={'body':0,'expanded':0,'notice':0,'evidence':0}
    for row,entry,expected in zip(full[:5],env['documents'],plan['prior_verified']):
        need(entry['filename']==row['filename']==expected['filename']
             and entry['bytes']==expected['evidence_bytes']
             and entry['sha256']==expected['evidence_sha256'],'PRIOR_POLICY_IDENTITY')
        raw=base64.b64decode(entry['evidence_base64'],validate=True)
        need(len(raw)==entry['bytes'] and base64.b64encode(raw).decode('ascii')==entry['evidence_base64'],
             'PRIOR_POLICY_IDENTITY')
        receipt=old.verify_evidence(raw,entry['sha256'],row,n.PLAN_BLOB)
        p.placement(receipt,row,bindings[row['filename']])
        need(receipt['expanded_bytes']==expected['expanded_bytes'] and
             receipt['notice_bytes']==expected['notice_bytes'] and
             row['bytes']==expected['expected_bytes'] and row['sha256']==expected['expected_sha256'],
             'PRIOR_POLICY_IDENTITY')
        totals['body']+=row['bytes'];totals['expanded']+=receipt['expanded_bytes']
        totals['notice']+=receipt['notice_bytes'];totals['evidence']+=len(raw)
    caps=prior.residual_caps(plan)
    ceilings={'body':a.MAX_BYTES,'expanded':v2.MAX_TOTAL,'notice':v2.MAX_NOTICES,'evidence':n.MAX_EVIDENCE_BATCH}
    need(caps=={k:ceilings[k]-totals[k] for k in ceilings}
         and totals['evidence']==env['evidence_bytes']==10909
         and totals['notice']==env['notice_bytes']==5241
         and plan['wheels']==full[5:] and len(plan['wheels'])==63
         and caps=={'body':225397605,'expanded':4294072708,'notice':33549191,'evidence':67097955},
         'PRIOR_POLICY_IDENTITY')
    return plan['wheels'],{r['filename']:bindings[r['filename']] for r in plan['wheels']},caps

class InspectionLedger:
    """Own accepted totals, never mutate historical evidence batch counters.
    V2's public expansion/notice counters reserve before decompression.
    Offsets adapt its unchanged fixed ceilings to the exact residual caps.
    """
    def __init__(self,caps):
        self.caps=dict(caps)
        self.budget=v2.InspectionBudget()
        self.budget.expanded=v2.MAX_TOTAL-caps['expanded']
        self.budget.notices=v2.MAX_NOTICES-caps['notice']
        self.accepted={'expanded':0,'notice':0,'evidence':0}
        self.stopped=False

    def inspect(self,raw,row,bound,plan_blob):
        need(not self.stopped,'BATCH_STOPPED')
        try:
            try:
                receipt,payloads=self.budget.inspect(raw,row,capture_notices=True)
            except v2.Blocked as exc:
                raise w.Blocked(str(exc)) from None
            n.validate_receipt(receipt,row)
            p.placement(receipt,row,bound)
            doc=n.encode_evidence(receipt,payloads,row,plan_blob)
            digest=w.sha(doc)
            # Verify canonical persisted representation before counting acceptance.
            p.verify_evidence(doc,digest,row,plan_blob,bound)
            next_totals={'expanded':self.accepted['expanded']+receipt['expanded_bytes'],
                         'notice':self.accepted['notice']+receipt['notice_bytes'],
                         'evidence':self.accepted['evidence']+len(doc)}
            need(next_totals['expanded']<=self.caps['expanded'] and
                 next_totals['notice']<=self.caps['notice'],'BATCH_EXPANSION_LIMIT')
            need(next_totals['evidence']<=self.caps['evidence'],'EVIDENCE_BATCH_LIMIT')
            self.accepted=next_totals
            return doc,digest
        except BaseException:
            self.stopped=True
            raise

def _collect(rows, plan_blob, bindings, caps, scope, fetch, deadline, parent):
    rows,bindings,caps,policy_sha=prepare(rows,plan_blob,bindings,caps,scope)
    batch=InspectionLedger(caps)
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
                doc, digest = batch.inspect(raw,row,bindings[row['filename']],plan_blob)
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
                'license_reviewed':False,'production_ready':False,
                'policy_sha256':policy_sha,'caps':caps,'accepted_totals':batch.accepted.copy()}
    digest = store.finish(manifest)
    return store.path, digest




def verify_generation(path, manifest_sha, rows, plan_blob, *, scope, caps, bindings):
    """Independent read-only replay. Missing terminal manifest is unsettled."""
    rows,bindings,caps,policy_sha=prepare(rows,plan_blob,bindings,caps,scope)
    path = Path(path)
    need(path.is_dir() and not path.is_symlink(), 'GENERATION_PATH')
    manifest_path = path/'manifest.json'
    need(manifest_path.is_file() and not manifest_path.is_symlink(), 'UNSETTLED_GENERATION')
    raw = read_bounded(manifest_path, MAX_MANIFEST)
    need(n.digest(manifest_sha) and w.sha(raw) == manifest_sha, 'MANIFEST_HASH')
    m = parse(raw)
    keys = {'schema_version','scope','plan_blob','status','expected_count',
            'attempted_count','verified_count','received_bytes','missing',
            'license_reviewed','production_ready','files','policy_sha256','caps','accepted_totals'}
    need(set(m) == keys and type(m['schema_version']) is int and m['schema_version'] == 3
         and m['scope'] == scope and m['plan_blob'] == plan_blob
         and m['license_reviewed'] is False and m['production_ready'] is False,
         'MANIFEST_IDENTITY')
    need(m['policy_sha256']==policy_sha and n.canonical(m['caps'])==n.canonical(caps),'MANIFEST_POLICY_IDENTITY')
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
            receipt=p.verify_evidence(evidence_raw,filemap[evidence_name]['sha256'],row,plan_blob,bindings[row['filename']])
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
    need(n.canonical(m['accepted_totals'])==n.canonical({'expanded':expanded,'notice':notices,'evidence':evidence_bytes}),
         'MANIFEST_RESOURCE_TOTALS')
    return m


