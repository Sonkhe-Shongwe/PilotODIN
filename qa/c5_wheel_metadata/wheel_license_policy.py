"""Offline version-bound licence placement policy; no acquisition or install.

Historical inspector/receipt schema stays unchanged. A v2 receipt is only
policy-checked when the independent METADATA identity and version are bound.
"""
from __future__ import annotations

if __name__ == '__main__':
    raise SystemExit('OFFLINE_LIBRARY_ONLY: licence placement policy')

import base64
import hashlib
import json
import re
from pathlib import Path

import wheel_archive_inspector as w
import wheel_archive_inspector_v2 as v2
import wheel_notice_evidence as old
import wheel_notice_evidence_v2 as n

FREEZER_BLOB='193b4f6f4cec8629cfd1b23da7ae9d508a1283da'
PRIOR_BLOB='1adcd112c54ffa90ee638bcd7598d879e01798bc'
FREEZER='freezer_receipt_45704870236.jsonl'
PRIOR='wheel_prior_notice_preservation_45729307962.json'
VERSIONS=frozenset({'1.0','1.1','1.2','2.1','2.2','2.3','2.4','2.5','2.6'})
REFUSALS=frozenset({'METADATA_POLICY_VERSION','METADATA_POLICY_IDENTITY',
                    'MODERN_LICENCE_LOCATION','LEGACY_LICENCE_LOCATION',
                    'LICENCE_POLICY_SOURCE'})


def pinned_text(path, blob):
    w.require(path.is_file() and not path.is_symlink(),'LICENCE_POLICY_SOURCE')
    with path.open('rb') as f:
        raw=f.read(n.MAX_PIN+1)
    w.require(0<len(raw)<=n.MAX_PIN,'LICENCE_POLICY_SOURCE')
    if b'\r\n' in raw:
        lf=raw.replace(b'\r\n',b'\n')
        w.require(b'\r' not in lf and raw==lf.replace(b'\n',b'\r\n'),'LICENCE_POLICY_SOURCE')
        raw=lf
    w.require(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==blob,
              'LICENCE_POLICY_SOURCE')
    return raw


def binding(filename, metadata_sha256, version, license_files):
    w.require(type(version) is str and version in VERSIONS,'METADATA_POLICY_VERSION')
    w.require(type(filename) is str and n.digest(metadata_sha256)
              and type(license_files) is list and all(type(x) is str for x in license_files)
              and len(set(license_files))==len(license_files),'METADATA_POLICY_IDENTITY')
    for item in license_files:
        w.name(item)
    return {'filename':filename,'metadata_sha256':metadata_sha256,
            'metadata_version':version,'license_files':list(license_files)}


def match(expected, bound):
    w.require(type(bound) is dict and set(bound)=={'filename','metadata_sha256','metadata_version','license_files'},
              'METADATA_POLICY_IDENTITY')
    checked=binding(bound['filename'],bound['metadata_sha256'],bound['metadata_version'],bound['license_files'])
    w.require(all(checked[k]==expected[k] for k in ('filename','metadata_sha256','license_files')),
              'METADATA_POLICY_IDENTITY')
    return checked['metadata_version']


def load_bindings():
    """Pinned candidate rows and exact freezer sidecars; no external requests."""
    rows=n.load_pinned_rows()
    candidates=n.pinned_json(n.ROOT/(n.DIR+'platform_lock_candidates_45703125465.json'),n.TEST_BLOB)
    result={}
    def add(b):
        fn=b['filename']
        w.require(fn not in result or result[fn]==b,'METADATA_POLICY_IDENTITY')
        result[fn]=b
    for profile in candidates['candidates']:
        for row in profile['rows']:
            add(binding(row['filename'],row['verified_metadata_sha256'],row['metadata_version'],row['license_files']))
    w.require(len(result)==62,'LICENCE_POLICY_SOURCE')
    records=[json.loads(line,object_pairs_hook=n.unique) for line in
             pinned_text(n.ROOT/(n.DIR+FREEZER),FREEZER_BLOB).splitlines()]
    w.require(len(records)==36 and records[-1]['kind']=='RESULT','LICENCE_POLICY_SOURCE')
    chunks={}; seen=set()
    for wrapper in records:
        row=wrapper['record']
        if wrapper['kind']=='BYTES':
            fn=row['filename']; prior=chunks.get(fn,'')
            w.require(fn not in seen and row['offset']==len(prior) and
                      type(row['base64']) is str and 0<len(row['base64'])<=8192,
                      'LICENCE_POLICY_SOURCE')
            chunks[fn]=prior+row['base64']
            w.require(len(chunks[fn])<=4*((1024*1024+2)//3),'LICENCE_POLICY_SOURCE')
        elif wrapper['kind']=='VERIFIED':
            fn=row['filename']
            w.require(fn in chunks and fn not in seen,'LICENCE_POLICY_SOURCE')
            raw=base64.b64decode(chunks[fn],validate=True)
            w.require(0<len(raw)<=1024*1024 and len(raw)==row['bytes']
                      and w.sha(raw)==row['metadata_sha256'],'LICENCE_POLICY_SOURCE')
            try:
                md=v2.message(raw)
                version=v2.single(md,'Metadata-Version')
                files=[str(x) for x in md.get_all('License-File',[])]
            except v2.Blocked as exc:
                raise w.Blocked('LICENCE_POLICY_SOURCE') from None
            w.require(version==row['declarations']['metadata_version'] and
                      files==row['declarations']['license_files'],'LICENCE_POLICY_SOURCE')
            add(binding(fn,row['metadata_sha256'],version,files));seen.add(fn)
    w.require(len(seen)==6 and set(chunks)==seen and len(result)==68 and
              set(result)=={r['filename'] for r in rows},'LICENCE_POLICY_SOURCE')
    for row in rows:
        match(row,result[row['filename']])
    return result


def placement(receipt, expected, bound):
    """After exact receipt validation, check each declared path, never legal clearance."""
    version=match(expected,bound)
    w.require(receipt['filename']==bound['filename'] and
              receipt['metadata_sha256']==bound['metadata_sha256'] and
              receipt['declared_license_files']==bound['license_files'],
              'METADATA_POLICY_IDENTITY')
    prefix='-'.join(expected['filename'][:-4].split('-')[:2])+'.dist-info/'
    paths={r['path'] for r in receipt['notices']}
    modern=tuple(map(int,version.split('.')))>=(2,4)
    for item in bound['license_files']:
        modern_path=prefix+'licenses/'+item
        legacy_path=prefix+item
        if modern:
            # Preserve existing exact-one ambiguity rule; require modern placement.
            w.require(modern_path in paths and legacy_path not in paths,'MODERN_LICENCE_LOCATION')
        else:
            # Historical pre-2.4 convention, not a claim of modern conformance.
            w.require(len({modern_path,legacy_path}&paths)==1,'LEGACY_LICENCE_LOCATION')
    return receipt


def verify_evidence(raw, sha, expected, plan_blob, bound):
    return placement(n.verify_evidence(raw,sha,expected,plan_blob),expected,bound)


def inspect(batch, raw, expected, bound, plan_blob):
    """Candidate producer seam; only policy-accepted evidence is counted."""
    fn=expected['filename']
    try:
        match(expected,bound)
        doc,sha=batch.inspect(fn,raw)
    except BaseException:
        batch._failed=True
        raise
    try:
        verify_evidence(doc,sha,expected,plan_blob,bound)
        return doc,sha
    except BaseException:
        # Undo only the just-encoded unpublished evidence accounting. Never
        # release attempted/expansion reservations or erase earlier successes.
        batch._failed=True
        batch._verified.pop(fn)
        batch._persisted_bytes-=len(doc)
        raise


def prior_placements():
    """Recheck the exact five durable v1 receipts; do not upgrade their schema."""
    rows=n.load_pinned_rows();bound=load_bindings()
    env=n.pinned_json(n.ROOT/(n.DIR+PRIOR),PRIOR_BLOB)
    w.require(env['schema_version']==1 and env['license_reviewed'] is False and
              env['production_ready'] is False and len(env['documents'])==5,'LICENCE_POLICY_SOURCE')
    results=[]
    for row,entry in zip(rows[:5],env['documents']):
        w.require(entry['filename']==row['filename'],'LICENCE_POLICY_SOURCE')
        raw=base64.b64decode(entry['evidence_base64'],validate=True)
        w.require(len(raw)==entry['bytes'],'LICENCE_POLICY_SOURCE')
        receipt=old.verify_evidence(raw,entry['sha256'],row,n.PLAN_BLOB)
        placement(receipt,row,bound[row['filename']])
        results.append({'filename':row['filename'],'metadata_version':bound[row['filename']]['metadata_version']})
    return results
