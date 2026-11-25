"""C5 offline notice evidence codec and independently pinned candidate plan.

No transport, archive extraction, install, filesystem publication or execution.
A caller must retain the returned bytes and their independent digest in a
reviewed evidence channel. Replaying an evidence document verifies its
consistency, not the original wheel again, legal clearance or approval.
"""
from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import json
from pathlib import Path
import re

import wheel_archive_inspector as w
import review_input_proposals as proposals

ROOT = Path(__file__).resolve().parents[2]
DIR = 'qa/c5_wheel_metadata/'
PLAN_BLOB = '1aa96a7172508f94b2cdc4b7aabd65e3b8f21f89'
TEST_BLOB = '6b27407f4b24942c385179bb253f692370f21df7'
PROD_BLOB = '70cdac979b732aadfad0c51d7e159a60840cc1ef'
MAX_PIN = 2 * 1024 * 1024
MAX_DOCUMENT = 64 * 1024 * 1024
MAX_EVIDENCE_BATCH = 64 * 1024 * 1024
RECEIPT_KEYS = {'filename','bytes','sha256','metadata_sha256','tags','members',
                'expanded_bytes','notice_bytes','notices','native_candidates',
                'declared_license_files','license_expression','license_reviewed','status'}


def require(ok, reason):
    w.require(ok, reason)


def unique(pairs):
    out = {}
    for k, v in pairs:
        require(k not in out, 'DUPLICATE_JSON_KEY')
        out[k] = v
    return out


def canonical(doc):
    return (json.dumps(doc, ensure_ascii=True, sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode('ascii')


def pinned_json(path, blob):
    """Read only a checkout text blob; normalize wholly CRLF checkout text."""
    require(path.is_file() and not path.is_symlink(), 'PIN_PATH')
    try:
        with path.open('rb') as f:
            raw = f.read(MAX_PIN + 1)
    except OSError:
        raise w.Blocked('PIN_READ') from None
    require(0 < len(raw) <= MAX_PIN, 'PIN_SIZE')
    if b'\r\n' in raw:
        converted = raw.replace(b'\r\n', b'\n')
        require(b'\r' not in converted and raw == converted.replace(b'\n', b'\r\n'),
                'PIN_LINE_ENDINGS')
        raw = converted
    require(hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            == blob, 'PIN_DIGEST')
    return json.loads(raw, object_pairs_hook=unique)


def load_pinned_rows():
    plan = pinned_json(ROOT / (DIR+'wheel_acquisition_plan_20261125.json'), PLAN_BLOB)
    test = pinned_json(ROOT / (DIR+'platform_lock_candidates_45703125465.json'), TEST_BLOB)
    prod = pinned_json(ROOT / (DIR+'production_graph_receipt_45705552265.json'), PROD_BLOB)
    require(plan['source_pins'] == [
        {'path':DIR+'platform_lock_candidates_45703125465.json','blob':TEST_BLOB},
        {'path':DIR+'production_graph_receipt_45705552265.json','blob':PROD_BLOB}],
        'PLAN_SOURCE_PINS')
    rows = proposals.check_wheel(plan, test, prod)
    require(len(rows) == 68 and sum(row['bytes'] for row in rows) == 225699980,
            'PLAN_COUNTS')
    return rows


def bounded_int(value, low, high):
    return type(value) is int and low <= value <= high


def digest(value):
    return type(value) is str and bool(w.HEX.fullmatch(value))


def member_rows(rows, *, notice):
    require(type(rows) is list and len(rows) <= w.MAX_MEMBERS, 'MEMBER_ROWS')
    paths = []
    for row in rows:
        require(type(row) is dict and set(row) == {'path','bytes','sha256'}, 'MEMBER_ROW')
        path = w.name(row['path'])
        require(bounded_int(row['bytes'], 0, w.MAX_NOTICE if notice else w.MAX_MEMBER)
                and digest(row['sha256']), 'MEMBER_IDENTITY')
        if not notice:
            require(w.NATIVE.search(path), 'NATIVE_CANDIDATE')
        paths.append(path)
    require(paths == sorted(paths) and len({p.casefold() for p in paths}) == len(paths),
            'MEMBER_INVENTORY')
    return {row['path']:row for row in rows}


def validate_receipt(receipt, expected):
    require(type(receipt) is dict and set(receipt) == RECEIPT_KEYS, 'RECEIPT_FIELDS')
    require(receipt['status'] == 'CANDIDATE_INTEGRITY_ONLY' and
            receipt['license_reviewed'] is False, 'FALSE_CLEARANCE')
    for key in ('filename','bytes','sha256','metadata_sha256','license_expression'):
        require(receipt[key] == expected[key] and type(receipt[key]) is type(expected[key]),
                'RECEIPT_PLAN_IDENTITY')
    require(receipt['declared_license_files'] == expected['license_files'],
            'RECEIPT_PLAN_IDENTITY')
    require(bounded_int(receipt['members'], 1, w.MAX_MEMBERS) and
            bounded_int(receipt['expanded_bytes'], 0, w.MAX_WHEEL) and
            bounded_int(receipt['notice_bytes'], 0, w.MAX_NOTICES), 'RECEIPT_BOUNDS')
    parts = expected['filename'][:-4].split('-')
    tags = [p.split('.') for p in parts[-3:]]
    require(receipt['tags'] == sorted({f'{p}-{a}-{t}' for p in tags[0]
                                      for a in tags[1] for t in tags[2]}),
            'RECEIPT_TAGS')
    notices = member_rows(receipt['notices'], notice=True)
    natives = member_rows(receipt['native_candidates'], notice=False)
    require(len(set(notices) | set(natives)) <= receipt['members'] and
            all(notices[p] == natives[p] for p in set(notices) & set(natives)),
            'MEMBER_INVENTORY')
    require(sum(row['bytes'] for row in notices.values()) == receipt['notice_bytes'] <=
            receipt['expanded_bytes'], 'NOTICE_TOTAL')
    distinfo = '-'.join(parts[:2]) + '.dist-info/'
    for item in expected['license_files']:
        item = w.name(item)
        require(len({distinfo+'licenses/'+item, distinfo+item} & set(notices)) == 1,
                'DECLARED_NOTICE_MISSING_OR_AMBIGUOUS')
    return notices


def encode_evidence(receipt, payloads, expected, plan_blob):
    notices = validate_receipt(receipt, expected)
    require(type(payloads) is dict and set(payloads) == set(notices), 'NOTICE_PAYLOAD_INVENTORY')
    encoded = []
    for path in sorted(notices):
        data = payloads[path]
        ident = notices[path]
        require(type(data) is bytes and len(data) == ident['bytes'] and w.sha(data) == ident['sha256'],
                'NOTICE_PAYLOAD_IDENTITY')
        encoded.append({'path':path,'base64':base64.b64encode(data).decode('ascii')})
    raw = canonical({'schema_version':1,'plan_blob':plan_blob,'receipt':receipt,
                     'notice_payloads':encoded})
    require(len(raw) <= MAX_DOCUMENT, 'EVIDENCE_DOCUMENT_LIMIT')
    return raw


def verify_evidence(raw, expected_sha256, expected, plan_blob):
    """Revalidate persisted bytes against an independent document digest and plan."""
    require(type(raw) is bytes and 0 < len(raw) <= MAX_DOCUMENT, 'EVIDENCE_DOCUMENT_LIMIT')
    require(digest(expected_sha256) and w.sha(raw) == expected_sha256, 'EVIDENCE_DOCUMENT_HASH')
    try:
        doc = json.loads(raw, object_pairs_hook=unique)
        require(type(doc) is dict and set(doc) == {'schema_version','plan_blob','receipt','notice_payloads'}
                and type(doc['schema_version']) is int and doc['schema_version'] == 1
                and doc['plan_blob'] == plan_blob, 'EVIDENCE_IDENTITY')
        require(canonical(doc) == raw, 'EVIDENCE_CANONICAL')
        notices = validate_receipt(doc['receipt'], expected)
        rows = doc['notice_payloads']
        require(type(rows) is list and len(rows) == len(notices), 'NOTICE_PAYLOAD_INVENTORY')
        seen = []
        total = 0
        for row in rows:
            require(type(row) is dict and set(row) == {'path','base64'}, 'NOTICE_PAYLOAD_ROW')
            path = w.name(row['path'])
            require(path in notices, 'NOTICE_PAYLOAD_INVENTORY')
            ident = notices[path]
            value = row['base64']
            require(type(value) is str and len(value) == 4*((ident['bytes']+2)//3),
                    'NOTICE_PAYLOAD_LENGTH')
            data = base64.b64decode(value, validate=True)
            require(base64.b64encode(data).decode('ascii') == value and
                    len(data) == ident['bytes'] and w.sha(data) == ident['sha256'],
                    'NOTICE_PAYLOAD_IDENTITY')
            total += len(data)
            require(total <= w.MAX_NOTICES, 'NOTICE_TOTAL')
            seen.append(path)
        require(seen == sorted(notices) and total == doc['receipt']['notice_bytes'],
                'NOTICE_PAYLOAD_INVENTORY')
        return doc['receipt']
    except (UnicodeError, json.JSONDecodeError, binascii.Error, RecursionError):
        raise w.Blocked('MALFORMED_EVIDENCE') from None


class _EvidenceBatch:
    """Internal synthetic seam; public candidate batch always loads fixed pins."""
    def __init__(self, rows, plan_blob):
        self._rows = {row['filename']:copy.deepcopy(row) for row in rows}
        require(len(self._rows) == len(rows) and 0 < len(rows) <= 68, 'PLAN_COUNTS')
        self._plan = plan_blob
        self._budget = w.InspectionBudget()
        self._attempted = set()
        self._verified = {}
        self._failed = False
        self._persisted_bytes = 0

    def inspect(self, filename, raw):
        require(not self._failed, 'BATCH_STOPPED')
        try:
            require(type(filename) is str and filename in self._rows, 'UNPLANNED_WHEEL')
            require(filename not in self._attempted, 'BATCH_DUPLICATE')
            self._attempted.add(filename)
            expected = self._rows[filename]
            receipt, payloads = self._budget.inspect(raw, expected, capture_notices=True)
            doc = encode_evidence(receipt, payloads, expected, self._plan)
            require(self._persisted_bytes + len(doc) <= MAX_EVIDENCE_BATCH, 'EVIDENCE_BATCH_LIMIT')
            sha = w.sha(doc)
            verify_evidence(doc, sha, expected, self._plan)
            self._persisted_bytes += len(doc)
            self._verified[filename] = {'filename':filename,'evidence_bytes':len(doc),
                                        'evidence_sha256':sha,'notice_bytes':receipt['notice_bytes']}
            return doc, sha
        except BaseException:
            self._failed = True
            raise

    def verify(self, filename, raw, expected_sha256):
        require(type(filename) is str and filename in self._rows, 'UNPLANNED_WHEEL')
        return verify_evidence(raw, expected_sha256, self._rows[filename], self._plan)

    def settlement(self):
        return {'plan_blob':self._plan, 'status':'BLOCKED' if self._failed else
                ('CANDIDATE_EVIDENCE_ENCODED' if len(self._verified)==len(self._rows) else 'INCOMPLETE'),
                'expected_count':len(self._rows), 'attempted_count':len(self._attempted),
                'verified_count':len(self._verified), 'evidence_bytes':self._persisted_bytes,
                'records':[copy.deepcopy(self._verified[k]) for k in sorted(self._verified)],
                'missing':sorted(set(self._rows)-set(self._verified)),
                'license_reviewed':False, 'production_ready':False}


class PinnedBatch(_EvidenceBatch):
    def __init__(self):
        super().__init__(load_pinned_rows(), PLAN_BLOB)


if __name__ == '__main__':
    raise SystemExit('OFFLINE_LIBRARY_ONLY: no acquisition or evidence publication CLI')
