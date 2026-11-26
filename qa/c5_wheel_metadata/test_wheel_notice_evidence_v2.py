"""Inert wheel notice evidence; no wheel acquisition or real notice claims."""
import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wheel_archive_inspector as w
import wheel_notice_evidence_v2 as n
import wheel_notice_evidence as legacy
import wheel_archive_inspector_v2 as v2
import stat, zipfile
from test_wheel_archive_inspector import fixture, D


class Tests(unittest.TestCase):
    def make(self, **kw):
        raw, row = fixture(**kw)
        batch = n._EvidenceBatch([row], 'synthetic-plan')
        return raw, row, batch

    def doc(self, **kw):
        raw, row, b = self.make(**kw)
        doc, sha = b.inspect(row['filename'], raw)
        return doc, sha, row, b

    def deny(self, reason, call):
        with self.assertRaisesRegex(w.Blocked, '^'+reason+'$'):
            call()

    def mutate(self, edit, reason):
        doc, sha, row, b = self.doc()
        value = json.loads(doc); edit(value)
        changed = n.canonical(value)
        self.deny(reason, lambda: b.verify(row['filename'], changed, w.sha(changed)))

    def test_pinned_real_plan(self):
        rows = n.load_pinned_rows()
        self.assertEqual(len(rows), 68)
        self.assertEqual(sum(x['bytes'] for x in rows), 225699980)
        self.assertEqual(len({x['filename'] for x in rows}), 68)
        b = n.PinnedBatch()
        self.assertEqual(b.settlement()['status'], 'INCOMPLETE')
        self.assertEqual(b.settlement()['expected_count'], 68)

    def test_plan_cannot_accept_fixture(self):
        b = n.PinnedBatch(); raw, row = fixture()
        self.deny('UNPLANNED_WHEEL', lambda: b.inspect(row['filename'],raw))
        self.assertEqual(b.settlement()['status'],'BLOCKED')

    def test_real_filename_wrong_bytes(self):
        b = n.PinnedBatch(); row=n.load_pinned_rows()[0]
        self.deny('ARCHIVE_SIZE',lambda:b.inspect(row['filename'],b'x'))
        self.assertEqual(b.settlement()['verified_count'],0)

    def test_pinned_text_crlf_and_mutation(self):
        import hashlib
        raw=b'{"a":1}\n'
        pin=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'fixture.json'
            p.write_bytes(raw.replace(b'\n',b'\r\n'))
            self.assertEqual(n.pinned_json(p,pin),{'a':1})
            p.write_bytes(b'{"a":2}\n')
            self.deny('PIN_DIGEST',lambda:n.pinned_json(p,pin))
            p.write_bytes(b'{\r\n"a":1\n}\n')
            self.deny('PIN_LINE_ENDINGS',lambda:n.pinned_json(p,pin))

    def test_legacy_api_unchanged(self):
        raw,row=fixture()
        self.assertIsInstance(w.InspectionBudget().inspect(raw,row),dict)

    def test_capture_binary_notices(self):
        raw,row=fixture(changes={D+'licenses/LICENSE':b'\x00\xff\x01'})
        receipt, payloads=w.InspectionBudget().inspect(raw,row,capture_notices=True)
        self.assertEqual(payloads[D+'licenses/LICENSE'],b'\x00\xff\x01')
        self.assertEqual(set(payloads),{x['path'] for x in receipt['notices']})

    def test_roundtrip_disposable_file(self):
        doc,sha,row,b=self.doc(changes={D+'licenses/LICENSE':b'\x00\xff\x01'})
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'evidence.json'
            with path.open('xb') as f: f.write(doc)
            receipt=b.verify(row['filename'],path.read_bytes(),sha)
            self.assertFalse(receipt['license_reviewed'])
            self.assertEqual(receipt['notice_bytes'],3+len(b'Other synthetic notice'))
        self.assertEqual(b.settlement()['status'],'CANDIDATE_EVIDENCE_ENCODED')
        self.assertFalse(b.settlement()['production_ready'])

    def test_document_hash(self):
        doc,sha,row,b=self.doc()
        self.deny('EVIDENCE_DOCUMENT_HASH',lambda:b.verify(row['filename'],doc,'0'*64))

    def test_noncanonical(self):
        doc,sha,row,b=self.doc()
        self.deny('EVIDENCE_CANONICAL',lambda:b.verify(row['filename'],doc+b'\n',w.sha(doc+b'\n')))

    def test_duplicate_json(self):
        doc,sha,row,b=self.doc()
        bad=doc.replace(b'{"notice_payloads":',b'{"schema_version":2,"notice_payloads":',1)
        self.deny('DUPLICATE_JSON_KEY',lambda:b.verify(row['filename'],bad,w.sha(bad)))

    def test_wrong_plan(self): self.mutate(lambda d:d.update(plan_blob='other'),'EVIDENCE_IDENTITY')
    def test_false_clearance(self): self.mutate(lambda d:d['receipt'].update(license_reviewed=True),'FALSE_CLEARANCE')
    def test_wrong_archive(self): self.mutate(lambda d:d['receipt'].update(sha256='0'*64),'RECEIPT_PLAN_IDENTITY')
    def test_wrong_metadata(self): self.mutate(lambda d:d['receipt'].update(metadata_sha256='0'*64),'RECEIPT_PLAN_IDENTITY')
    def test_wrong_tags(self): self.mutate(lambda d:d['receipt'].update(tags=['cp311-none-any']),'RECEIPT_TAGS')
    def test_missing_payload(self): self.mutate(lambda d:d['notice_payloads'].pop(),'NOTICE_PAYLOAD_INVENTORY')
    def test_duplicate_payload(self): self.mutate(lambda d:d['notice_payloads'].__setitem__(1,d['notice_payloads'][0]),'NOTICE_PAYLOAD_INVENTORY')
    def test_wrong_payload(self):
        def edit(d):
            v=d['notice_payloads'][0]['base64']; data=base64.b64decode(v)
            d['notice_payloads'][0]['base64']=base64.b64encode(b'x'*len(data)).decode()
        self.mutate(edit,'NOTICE_PAYLOAD_IDENTITY')
    def test_wrong_length(self): self.mutate(lambda d:d['notice_payloads'][0].update(base64=''),'NOTICE_PAYLOAD_LENGTH')
    def test_notice_total(self): self.mutate(lambda d:d['receipt'].update(notice_bytes=1),'NOTICE_TOTAL')
    def test_member_path(self): self.mutate(lambda d:d['receipt']['notices'][0].update(path='../bad'),'UNSAFE_PATH')
    def test_duplicate_notice(self):
        self.mutate(lambda d:d['receipt']['notices'].__setitem__(1,d['receipt']['notices'][0]),'MEMBER_INVENTORY')
    def test_document_limit(self):
        raw,row,b=self.make()
        with patch.object(n,'MAX_DOCUMENT',10):
            self.deny('EVIDENCE_DOCUMENT_LIMIT',lambda:b.inspect(row['filename'],raw))
        self.assertEqual(b.settlement()['status'],'BLOCKED')
    def test_batch_limit(self):
        raw,row,b=self.make()
        with patch.object(n,'MAX_EVIDENCE_BATCH',10):
            self.deny('EVIDENCE_BATCH_LIMIT',lambda:b.inspect(row['filename'],raw))
        self.assertEqual(b.settlement()['verified_count'],0)
    def test_no_retry_after_failure(self):
        raw,row,b=self.make()
        self.deny('ARCHIVE_SIZE',lambda:b.inspect(row['filename'],raw+b'x'))
        self.deny('BATCH_STOPPED',lambda:b.inspect(row['filename'],raw))
    def test_no_duplicate_after_success(self):
        raw,row,b=self.make(); b.inspect(row['filename'],raw)
        self.deny('BATCH_DUPLICATE',lambda:b.inspect(row['filename'],raw))
        self.assertEqual(b.settlement()['status'],'BLOCKED')
        self.assertEqual(b.settlement()['verified_count'],1)


    def test_v2_directory_notice_roundtrip(self):
        i=zipfile.ZipInfo('demo_pkg/'); i.create_system=3
        i.external_attr=((stat.S_IFDIR|0o755)<<16)|0x10
        doc,sha,row,b=self.doc(extras=[(i,b'')])
        r=b.verify(row['filename'],doc,sha)
        self.assertEqual(r['inspector_schema'],2)
        self.assertEqual(r['directory_entries'],1)
        self.assertEqual(r['directory_inventory_sha256'],w.sha(b'demo_pkg/\n'))
        self.assertEqual(json.loads(doc)['schema_version'],2)

    def test_directory_count_bool(self):
        self.mutate(lambda d:d['receipt'].update(directory_entries=False),'DIRECTORY_RECEIPT_IDENTITY')

    def test_directory_count_excess(self):
        self.mutate(lambda d:d['receipt'].update(directory_entries=v2.MAX_MEMBERS),'DIRECTORY_RECEIPT_IDENTITY')

    def test_directory_digest_empty_mismatch(self):
        self.mutate(lambda d:d['receipt'].update(directory_inventory_sha256='0'*64),'DIRECTORY_RECEIPT_IDENTITY')

    def test_directory_count_nonzero_empty_digest(self):
        self.mutate(lambda d:d['receipt'].update(directory_entries=1),'DIRECTORY_RECEIPT_IDENTITY')

    def test_directory_schema(self):
        self.mutate(lambda d:d['receipt'].update(inspector_schema=1),'INSPECTOR_SCHEMA')

    def test_missing_directory_fields(self):
        self.mutate(lambda d:d['receipt'].pop('directory_entries'),'RECEIPT_FIELDS')

    def test_v1_v2_no_schema_confusion(self):
        raw,row=fixture()
        old,old_sha=legacy._EvidenceBatch([row],'synthetic-plan').inspect(row['filename'],raw)
        new,new_sha=n._EvidenceBatch([row],'synthetic-plan').inspect(row['filename'],raw)
        self.deny('EVIDENCE_IDENTITY',lambda:n.verify_evidence(old,old_sha,row,'synthetic-plan'))
        self.deny('EVIDENCE_IDENTITY',lambda:legacy.verify_evidence(new,new_sha,row,'synthetic-plan'))
        self.assertEqual(legacy.verify_evidence(old,old_sha,row,'synthetic-plan')['members'],7)

    def test_directory_digest_bound_to_document_hash(self):
        i=zipfile.ZipInfo('demo_pkg/'); i.create_system=3
        i.external_attr=((stat.S_IFDIR|0o755)<<16)|0x10
        doc,sha,row,b=self.doc(extras=[(i,b'')])
        changed=json.loads(doc);changed['receipt']['directory_inventory_sha256']='f'*64
        self.deny('EVIDENCE_DOCUMENT_HASH',lambda:b.verify(row['filename'],n.canonical(changed),sha))

if __name__ == '__main__': unittest.main(verbosity=2)
