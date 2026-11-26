"""Disarmed exact-row integration, versioned evidence and mock-only suffix.
No socket, acquisition, artifact upload or live workflow frontdoor.
"""
from __future__ import annotations

if __name__ == '__main__':
    raise SystemExit('DISARMED: exact SciPy integration has no acquisition CLI')

import json
import re
import wheel_archive_inspector as w
import wheel_archive_inspector_v2 as v2
import wheel_notice_evidence_v2 as n
import wheel_license_policy as p
import wheel_settlement_core as c
import wheel_exact_scipy_policy as x

ROOT=n.ROOT
DIR=n.DIR
PLAN_BLOB='9938c0f8cc5be3e118dec2eff953cae94f4b5a76'
RETENTION_BLOB='9eb11ff031ea7ff3b73ffd503ea499c7d4e290ba'
RETENTION_PATH='docs/C5_PUBLIC_DISCOVERY_RETENTION_45801369045.json'
PIN_PATH=DIR+'wheel_exact_scipy_policy_pins.json'
TARGET_SHA='0e92ff91c7d99c4f928455e4ee2714b081f67d97cebd128d781a05d44ef3d13b'
FIXTURE_SCOPE='SYNTHETIC_EXACT_SUFFIX_V1'
REAL_SCOPE='DISARMED_EXACT_SUFFIX_PROPOSAL_V1'
STRICT='STRICT_V2'
FIXTURE_STRICT=('demo_pkg-1.2-py2-none-any.whl',1493,
                'ba28b19cb0c778472ccbeb259afb371a22e04f34da5c8ebcdc3486bd4cc26203',
                x.FIXTURE_IDENTITIES[0][3])
FIXTURE_ROWS=(x.FIXTURE_IDENTITIES[0],FIXTURE_STRICT)
FIXTURE_CAPS={'body':3261,'expanded':65536,'notice':65536,'evidence':65536}
PROPOSED_CAPS={'body':78611784,'expanded':3861562676,'notice':32947888,
               'evidence':67097955,'projection':8388608}
REQUIRED_PINS={DIR+f for f in (
    'wheel_exact_scipy_policy.py','wheel_exact_scipy_integration.py',
    'wheel_archive_inspector_v2.py','wheel_archive_inspector.py','wheel_notice_evidence.py',
    'wheel_notice_evidence_v2.py','wheel_license_policy.py','wheel_settlement_core.py',
    'wheel_acquisition_offline.py','wheel_diagnostic_v3_offline.py','wheel_diagnostic_offline.py',
    'wheel_hosted_final.py','wheel_exact_path_candidate.py','review_input_proposals.py',
    'wheel_missing_plan_20261126.json','wheel_acquisition_plan_20261125.json',
    'platform_lock_candidates_45703125465.json','production_graph_receipt_45705552265.json',
    'wheel_prior_notice_preservation_45729307962.json','wheel_receipt_diagnosis_45753813079.json',
    'freezer_receipt_45704870236.jsonl')}
REQUIRED_PINS |= {RETENTION_PATH,'.github/workflows/c5-wheel-exact-scipy-integration.yml',
                  '.github/workflows/c5-wheel-public-discovery.yml',
                  '.github/workflows/c5-wheel-hosted-final-review.yml'}

def require(ok, reason): w.require(ok,reason)
def sha(raw): return w.sha(raw)

def load_policy(expected_blob):
    """Caller supplies independent pin; no environment-derived or default pin."""
    require(type(expected_blob) is str and re.fullmatch(r'[0-9a-f]{40}',expected_blob),
            'EXACT_POLICY_PIN')
    raw=p.pinned_text(ROOT/PIN_PATH,expected_blob)
    doc=json.loads(raw,object_pairs_hook=n.unique)
    require(n.canonical(doc)==raw and type(doc) is dict and set(doc)=={
        'schema_version','scope','plan_blob','prior_projection_blob','row_sequence',
        'target_identity','path_sha256','baseline_blob','source_pins','fixture_rows',
        'proposed_caps','acquisition_authorised'},'EXACT_POLICY_SCHEMA')
    require(type(doc['schema_version']) is int and doc['schema_version']==1
            and doc['scope']==REAL_SCOPE and doc['plan_blob']==PLAN_BLOB
            and doc['prior_projection_blob']==RETENTION_BLOB and doc['row_sequence']==49
            and doc['target_identity']==list(x.REAL_IDENTITY) and doc['path_sha256']==TARGET_SHA
            and doc['baseline_blob']==x.BASELINE_BLOB and doc['fixture_rows']==[list(i) for i in FIXTURE_ROWS]
            and doc['proposed_caps']==PROPOSED_CAPS and doc['acquisition_authorised'] is False,
            'EXACT_POLICY_IDENTITY')
    pins=doc['source_pins']
    require(type(pins) is dict and set(pins)==REQUIRED_PINS
            and pins[DIR+'wheel_archive_inspector_v2.py']==x.BASELINE_BLOB
            and pins[DIR+'wheel_missing_plan_20261126.json']==PLAN_BLOB
            and pins[RETENTION_PATH]==RETENTION_BLOB,'EXACT_SOURCE_PINS')
    for path,blob in pins.items():
        require(type(blob) is str and re.fullmatch(r'[0-9a-f]{40}',blob),'EXACT_SOURCE_PIN')
        p.pinned_text(ROOT/path,blob)
    return doc

def prepare_real(expected_blob):
    """Independently pinned read-only proposal. Never a grant or fetch execution."""
    doc=load_policy(expected_blob)
    rows,bindings,caps=c.remaining_inputs()
    require(len(rows)==63 and x._permit_identity(rows[48])==x.REAL_IDENTITY
            and rows[48]['name']=='scipy' and rows[48]['version']=='1.17.1'
            and rows[48]['profiles']==['linux-x64-cp311-source-test']
            and rows[48]['license_files']==[] and rows[48]['license_expression'] is None
            and rows[48]['requires_python']=='>=3.11','EXACT_REAL_ROW')
    p.match(rows[48],bindings[rows[48]['filename']])
    env=n.pinned_json(ROOT/RETENTION_PATH,RETENTION_BLOB)
    projection=env['projection']; results=projection['results']
    require(projection['status']=='DISCOVERY_REFUSED' and projection['raw_replay_available'] is False
            and len(results)==49 and projection['caps']==caps,'EXACT_PRIOR_PROJECTION')
    for i,(row,result) in enumerate(zip(rows,results),1):
        require(result['sequence']==i and result['filename']==row['filename']
                and result['received_bytes']==row['bytes'] and result['received_sha256']==row['sha256']
                and result['status']==('INSPECTED' if i<49 else 'REFUSED'),'EXACT_PRIOR_ROW')
    require(results[-1]['inspection_reason']=='UNSAFE_PATH','EXACT_PRIOR_REFUSAL')
    expanded=sum(r['expanded_bytes'] for r in results[:-1])
    notice=sum(v['bytes'] for r in results[:-1] for v in r['notices'])
    suffix=rows[48:]
    require(len(suffix)==15 and sum(r['bytes'] for r in suffix)==PROPOSED_CAPS['body']
            and caps['expanded']-expanded==PROPOSED_CAPS['expanded']
            and caps['notice']-notice==PROPOSED_CAPS['notice']
            and caps['evidence']==PROPOSED_CAPS['evidence'],'EXACT_SUFFIX_CAPS')
    plan=[{'sequence':i,'row':row,'inspector_policy':x.REAL_POLICY if i==49 else STRICT,
           'metadata_binding':bindings[row['filename']]} for i,row in enumerate(suffix,49)]
    return {'schema_version':1,'scope':REAL_SCOPE,'policy_blob':expected_blob,
            'policy_sha256':sha(n.canonical(doc)),'rows':plan,'caps':dict(PROPOSED_CAPS),
            'raw_replay_available':False,'cumulative_evidence_remaining':None,
            'acquisition_authorised':False,'production_ready':False,'license_reviewed':False}

def inspect_real(*args,**kwargs):
    raise w.Blocked('FRESH_APPROVAL_REQUIRED')

def _fixture_row(identity):
    return dict(zip(('filename','bytes','sha256','metadata_sha256'),identity)) | {
        'name':'demo-pkg','version':'1.2','license_files':['LICENSE'],
        'license_expression':'MIT','requires_python':'>=3.11'}

def _fixture_plan():
    return [{'sequence':i,'row':_fixture_row(identity),
             'inspector_policy':x.FIXTURE_POLICY if i==49 else STRICT}
            for i,identity in enumerate(FIXTURE_ROWS,49)]

def _wrap(receipt,payloads,member,row,bound,sequence,policy_blob,policy_doc):
    require(type(sequence) is int and sequence==49 and x._permit_identity(row) in x.FIXTURE_IDENTITIES,
            'EXACT_FIXTURE_ROW')
    require(set(member)=={'path_sha256','bytes','sha256','central_occurrences','record_occurrences'}
            and member['path_sha256']==TARGET_SHA and n.digest(member['sha256'])
            and n.bounded_int(member['bytes'],0,v2.MAX_MEMBER)
            and type(member['central_occurrences']) is int and member['central_occurrences']==1
            and type(member['record_occurrences']) is int and member['record_occurrences']==1,
            'EXACT_MEMBER_EVIDENCE')
    inner=n.encode_evidence(receipt,payloads,row,policy_blob)
    p.verify_evidence(inner,sha(inner),row,policy_blob,bound)
    out=n.canonical({'schema_version':1,'scope':FIXTURE_SCOPE,'inspector_policy':x.FIXTURE_POLICY,
        'policy_blob':policy_blob,'policy_sha256':sha(n.canonical(policy_doc)),
        'source_blob':policy_doc['source_pins'][DIR+'wheel_exact_scipy_policy.py'],
        'verifier_blob':policy_doc['source_pins'][DIR+'wheel_exact_scipy_integration.py'],
        'sequence':sequence,'wheel_identity':list(x._permit_identity(row)),
        'member':member,'notice_evidence_sha256':sha(inner),'notice_evidence':json.loads(inner),
        'actual_wheel_verified':False,'production_ready':False,'license_reviewed':False})
    require(len(out)<=n.MAX_DOCUMENT,'EXACT_EVIDENCE_LIMIT')
    return out

def _inspect_fixture(raw,entry,policy_blob,policy_doc,totals,caps):
    row=entry['row'];seq=entry['sequence'];selected=entry['inspector_policy']
    require(type(raw) is bytes and len(raw)==row['bytes'] and sha(raw)==row['sha256'],'FIXTURE_BYTES')
    bound=p.binding(row['filename'],row['metadata_sha256'],'2.4',row['license_files'])
    require(selected==(x.FIXTURE_POLICY if seq==49 else STRICT),'EXACT_SELECTED_POLICY')
    if selected==x.FIXTURE_POLICY:
        budget=x._ExactBudget()
        permit=x._Permit(selected,x._permit_identity(row),policy_blob)
        budget.expanded=v2.MAX_TOTAL-caps['expanded']+totals['expanded']
        budget.notices=v2.MAX_NOTICES-caps['notice']+totals['notice']
        receipt,payloads,member=budget.inspect(raw,row,permit,capture_notices=True)
        encoded=_wrap(receipt,payloads,member,row,bound,seq,policy_blob,policy_doc)
    else:
        budget=v2.InspectionBudget()
        budget.expanded=v2.MAX_TOTAL-caps['expanded']+totals['expanded']
        budget.notices=v2.MAX_NOTICES-caps['notice']+totals['notice']
        receipt,payloads=budget.inspect(raw,row,capture_notices=True)
        encoded=n.encode_evidence(receipt,payloads,row,policy_blob)
        p.verify_evidence(encoded,sha(encoded),row,policy_blob,bound)
    next_totals={'expanded':totals['expanded']+receipt['expanded_bytes'],
                 'notice':totals['notice']+receipt['notice_bytes'],
                 'evidence':totals['evidence']+len(encoded)}
    require(all(next_totals[k]<=caps[k] for k in next_totals),'EXACT_BATCH_CAP')
    return encoded,receipt,next_totals

def verify_fixture_receipt(raw,entry,encoded,expected_sha,expected_blob):
    doc=load_policy(expected_blob)
    require(entry in _fixture_plan(),'FIXTURE_PLAN_IDENTITY')
    require(type(encoded) is bytes and 0<len(encoded)<=n.MAX_DOCUMENT and n.digest(expected_sha)
            and sha(encoded)==expected_sha,'EXACT_RECEIPT_HASH')
    observed,_,_=_inspect_fixture(raw,entry,expected_blob,doc,
                  {'expanded':0,'notice':0,'evidence':0},FIXTURE_CAPS)
    require(encoded==observed,'EXACT_RECEIPT_REPLAY')
    return json.loads(encoded,object_pairs_hook=n.unique)

def _safe_reason(exc):
    value=str(exc)
    return value if value in c.INSPECTION_REASONS | {
        'EXACT_POLICY_IDENTITY','EXACT_MEMBER_ABSENT','EXACT_MEMBER_ROLE',
        'EXACT_BATCH_CAP','EXACT_EVIDENCE_LIMIT','FIXTURE_BYTES','EXACT_SELECTED_POLICY'} else 'EXACT_REFUSED'

def run_mock(bodies,expected_blob,*,caps=None):
    """Only exact fixture identities; mapping-backed mock fetch, no network callback."""
    doc=load_policy(expected_blob);plan=_fixture_plan()
    require(type(bodies) is dict and set(bodies)=={r['row']['filename'] for r in plan},'FIXTURE_INPUTS')
    limits=dict(FIXTURE_CAPS if caps is None else caps)
    require(set(limits)==set(FIXTURE_CAPS) and all(type(v) is int and 0<v<=FIXTURE_CAPS[k]
            for k,v in limits.items()),'FIXTURE_CAPS')
    totals={'expanded':0,'notice':0,'evidence':0};body=0;results=[];calls=[]
    for entry in plan:
        row=entry['row']; seq=entry['sequence']; reason=None; encoded=None
        if body+row['bytes']>limits['body']:
            reason='FIXTURE_BODY_CAP'
        else:
            calls.append(seq); raw=bodies[row['filename']]
            if type(raw) is not bytes or len(raw)>row['bytes']:
                reason='FIXTURE_BYTES'
            else:
                body+=len(raw)
                try:
                    encoded,receipt,totals_next=_inspect_fixture(raw,entry,expected_blob,doc,totals,limits)
                except (w.Blocked,v2.Blocked,x.Blocked) as exc:
                    reason=_safe_reason(exc)
                else:
                    totals=totals_next
        result={'sequence':seq,'filename':row['filename'],'inspector_policy':entry['inspector_policy'],
                'status':'INSPECTED' if reason is None else 'REFUSED','reason':reason,
                'evidence_sha256':sha(encoded) if encoded is not None else None}
        if reason is None:
            result['notice_fingerprints']=sorted(
                [{'path_sha256':sha(v['path'].encode('ascii')),'bytes':v['bytes'],'sha256':v['sha256']}
                 for v in receipt['notices']],key=lambda v:v['path_sha256'])
            if seq==49:
                result['member']=json.loads(encoded)['member']
        results.append(result)
        if reason is not None: break
    out=n.canonical({'schema_version':1,'scope':FIXTURE_SCOPE,'policy_blob':expected_blob,
        'policy_sha256':sha(n.canonical(doc)),'plan_sha256':sha(n.canonical(plan)),
        'caps':limits,'calls':calls,'received_bytes':body,'totals':totals,'results':results,
        'status':'SYNTHETIC_COMPLETE' if len(results)==len(plan) and results[-1]['reason'] is None else 'BLOCKED',
        'raw_replay_available':False,'actual_wheel_verified':False,
        'license_reviewed':False,'production_ready':False,'acquisition_authorised':False})
    require(len(out)<=8*1024*1024,'EXACT_PROJECTION_LIMIT')
    return out

def verify_mock(bodies,raw,expected_sha,expected_blob,*,caps=None):
    require(type(raw) is bytes and 0<len(raw)<=8*1024*1024 and n.digest(expected_sha)
            and sha(raw)==expected_sha,'EXACT_PROJECTION_HASH')
    require(run_mock(bodies,expected_blob,caps=caps)==raw,'EXACT_PROJECTION_REPLAY')
    return json.loads(raw,object_pairs_hook=n.unique)
