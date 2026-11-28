"""Offline synthetic placement and deliberately narrow archive format tests."""
import json
from pathlib import Path
import struct
import sys
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
import wheel_archive_inspector as w
import wheel_archive_inspector_v2 as v2
import wheel_notice_evidence_v2 as n
import wheel_license_policy as p
from test_wheel_archive_inspector_v2 import fixture,D,MD


class Tests(unittest.TestCase):
    def deny(self,reason,fn,cls=w.Blocked):
        with self.assertRaisesRegex(cls,'^'+reason+'$'): fn()

    def make(self,version='2.4',changes=None,declared=None):
        md=MD.replace(b'Metadata-Version: 2.4',('Metadata-Version: '+version).encode())
        if declared is not None:
            md=md.replace(b'License-File: LICENSE\n',b''.join(('License-File: '+x+'\n').encode() for x in declared))
        raw,row=fixture(changes={D+'METADATA':md,**(changes or {})})
        if declared is not None: row['license_files']=declared
        return raw,row,p.binding(row['filename'],row['metadata_sha256'],version,row['license_files'])

    def produce(self,raw,row,bound):
        batch=n._EvidenceBatch([row],'fixture-plan')
        doc,sha=p.inspect(batch,raw,row,bound,'fixture-plan')
        return p.verify_evidence(doc,sha,row,'fixture-plan',bound)

    def test_pinned_bindings(self):
        b=p.load_bindings();self.assertEqual(len(b),68)
        counts={}
        for x in b.values(): counts[x['metadata_version']]=counts.get(x['metadata_version'],0)+1
        self.assertEqual(counts,{'2.4':40,'2.5':14,'2.1':13,'2.3':1})
        print('C5_METADATA_POLICY_VERSIONS '+json.dumps(counts,sort_keys=True))

    def test_prior_five(self):
        prior=p.prior_placements()
        self.assertEqual(len(prior),5)
        print('C5_PRIOR_PLACEMENT_PASS '+json.dumps(prior,sort_keys=True))

    def test_modern(self):
        for version in ('2.4','2.5','2.6'):
            with self.subTest(version=version): self.assertFalse(self.produce(*self.make(version))['license_reviewed'])

    def test_legacy_root(self):
        raw,row,b=self.make('2.1',{D+'licenses/LICENSE':None,D+'LICENSE':b'legacy'})
        self.assertEqual(self.produce(raw,row,b)['notice_bytes'],len(b'legacy')+len(b'Other synthetic notice'))

    def test_legacy_nested(self):
        self.produce(*self.make('2.3'))

    def test_modern_root_refusal(self):
        raw,row,b=self.make('2.4',{D+'licenses/LICENSE':None,D+'LICENSE':b'legacy'})
        batch=n._EvidenceBatch([row],'fixture-plan')
        self.deny('MODERN_LICENCE_LOCATION',lambda:p.inspect(batch,raw,row,b,'fixture-plan'))
        self.deny('BATCH_STOPPED',lambda:batch.inspect(row['filename'],raw))
        self.assertEqual(batch.settlement()['verified_count'],0)
        self.assertEqual(batch.settlement()['evidence_bytes'],0)
        self.assertEqual(batch.settlement()['attempted_count'],1)
        self.assertGreater(batch._budget.expanded,0)

    def test_independent_replay_modern_root(self):
        raw,row,b=self.make('2.5',{D+'licenses/LICENSE':None,D+'LICENSE':b'legacy'})
        doc,sha=n._EvidenceBatch([row],'fixture-plan').inspect(row['filename'],raw)
        self.deny('MODERN_LICENCE_LOCATION',lambda:p.verify_evidence(doc,sha,row,'fixture-plan',b))

    def test_nested_declared(self):
        raw,row,b=self.make(changes={D+'licenses/LICENSE':None,D+'licenses/vendor/LICENSE.txt':b'notice'},
                            declared=['vendor/LICENSE.txt'])
        self.produce(raw,row,b)

    def test_duplicate_declarations(self):
        self.deny('METADATA_POLICY_IDENTITY',lambda:self.make(declared=['LICENSE','LICENSE']))

    def test_both_locations(self):
        raw,row,b=self.make(changes={D+'LICENSE':b'duplicate'})
        self.deny('DECLARED_NOTICE_MISSING_OR_AMBIGUOUS',lambda:self.produce(raw,row,b))

    def test_missing(self):
        self.deny('DECLARED_NOTICE_MISSING_OR_AMBIGUOUS',lambda:self.produce(*self.make(changes={D+'licenses/LICENSE':None})))

    def test_no_declarations(self):
        self.produce(*self.make(declared=[]))

    def test_bound_identity(self):
        raw,row,b=self.make(); b['metadata_sha256']='0'*64
        self.deny('METADATA_POLICY_IDENTITY',lambda:self.produce(raw,row,b))

    def test_bound_files(self):
        raw,row,b=self.make(); b['license_files']=[]
        self.deny('METADATA_POLICY_IDENTITY',lambda:self.produce(raw,row,b))

    def test_unknown_version(self):
        self.deny('METADATA_POLICY_VERSION',lambda:self.make('3.0'))

    def test_unsupported_names(self):
        for path in ('demo_pkg/space name','demo_pkg/caf\u00e9.txt','demo_pkg/aux.txt','demo_pkg/a.'):
            with self.subTest(path=path):
                self.deny('UNSAFE_PATH',lambda:v2.InspectionBudget().inspect(*fixture(changes={path:b'x'})),v2.Blocked)

    def test_extra(self):
        i=zipfile.ZipInfo('extra');i.extra=b'\xff\xff\x00\x00'
        self.deny('ZIP_UNSUPPORTED',lambda:v2.InspectionBudget().inspect(*fixture(extras=[(i,b'x')])),v2.Blocked)

    def test_member_comment(self):
        i=zipfile.ZipInfo('comment');i.comment=b'x'
        self.deny('ZIP_UNSUPPORTED',lambda:v2.InspectionBudget().inspect(*fixture(extras=[(i,b'x')])),v2.Blocked)

    def test_descriptor_flag(self):
        raw,row=fixture();b=bytearray(raw);cd=b.find(b'PK\x01\x02')
        struct.pack_into('<H',b,cd+8,8);raw=bytes(b);row['sha256']=w.sha(raw)
        self.deny('ZIP_UNSUPPORTED',lambda:v2.InspectionBudget().inspect(raw,row),v2.Blocked)

    def test_signature(self):
        for name in ('RECORD.jws','RECORD.p7s'):
            self.deny('RECORD_SIGNATURE_UNSUPPORTED',lambda:v2.InspectionBudget().inspect(*fixture(changes={D+name:b'x'})),v2.Blocked)

    def test_policy_refusal_preserves_prior_success(self):
        raw,row,b=self.make()
        raw2,row2,b2=self.make('2.4',{D+'licenses/LICENSE':None,D+'LICENSE':b'legacy'})
        row2['filename']='demo_pkg-1.2-2-py3-none-any.whl'
        b2['filename']=row2['filename']
        batch=n._EvidenceBatch([row,row2],'fixture-plan')
        p.inspect(batch,raw,row,b,'fixture-plan')
        before=batch.settlement()
        self.deny('MODERN_LICENCE_LOCATION',lambda:p.inspect(batch,raw2,row2,b2,'fixture-plan'))
        after=batch.settlement()
        self.assertEqual(after['status'],'BLOCKED')
        self.assertEqual(after['verified_count'],1)
        self.assertEqual(after['attempted_count'],2)
        self.assertEqual(after['records'],before['records'])
        self.assertEqual(after['evidence_bytes'],before['evidence_bytes'])
        self.assertEqual(after['missing'],[row2['filename']])

    def test_duplicate_preserves_prior_success(self):
        raw,row,b=self.make()
        batch=n._EvidenceBatch([row],'fixture-plan')
        p.inspect(batch,raw,row,b,'fixture-plan')
        before=batch.settlement()
        self.deny('BATCH_DUPLICATE',lambda:p.inspect(batch,raw,row,b,'fixture-plan'))
        self.assertEqual(batch.settlement()['records'],before['records'])
        self.assertEqual(batch.settlement()['evidence_bytes'],before['evidence_bytes'])

if __name__=='__main__': unittest.main(verbosity=2)
