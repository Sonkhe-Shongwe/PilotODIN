"""Generated inert native-wheel fixtures and diagnostic schema regressions."""
import copy
import json
from pathlib import Path
import stat
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
import wheel_diagnostic_offline as d
import wheel_acquisition_offline as a
import wheel_archive_inspector as w
import wheel_notice_evidence as n
from test_wheel_archive_inspector import fixture,D,WH
from test_wheel_acquisition_offline import candidate,wire


class Tests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.parent=Path(tmp.name)

    def deny(self,reason,fn):
        with self.assertRaisesRegex(w.Blocked,'^'+reason+'$'): fn()

    def run_one(self,raw,row,status=200):
        replay=a.Replay({row['url']:wire(raw,status=status)})
        path,sha=d.run_fixture([row],'fixture-plan',replay,self.parent)
        manifest=d.verify_generation(path,sha,[row],'fixture-plan')
        result=json.loads((path/'request-001-result.json').read_bytes())
        return path,sha,manifest,result

    def native(self):
        tags=b'Tag: cp311-cp311-manylinux1_x86_64\nTag: cp311-cp311-manylinux_2_28_x86_64\nTag: cp311-cp311-manylinux_2_5_x86_64'
        raw,row=candidate(changes={D+'WHEEL':WH.replace(b'Root-Is-Purelib: true',b'Root-Is-Purelib: false').replace(b'Tag: py3-none-any',tags),
             'demo_pkg/md.cpython-311-x86_64-linux-gnu.so':b'inert native member, not executable'})
        row['filename']='demo_pkg-1.2-cp311-cp311-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl'
        row['url']=row['url'].rsplit('/',1)[0]+'/'+row['filename']
        return raw,row

    def test_missing_plan(self):
        p=d.review_missing_plan()
        self.assertEqual((p['remaining_count'],p['remaining_bytes'],p['prior_verified_bytes']),(63,225397605,302375))
        self.assertEqual(p['wheels'][0]['name'],'charset-normalizer')
        self.assertEqual(len(p['prior_verified']),5)
        self.assertFalse(set(x['filename'] for x in p['prior_verified']) & set(x['filename'] for x in p['wheels']))
        self.assertFalse(p['raw_prior_notices_retained_in_git'])
        self.assertFalse(p['production_ready'])

    def test_prior_tamper(self):
        rows=n.load_pinned_rows()
        diag=n.pinned_json(n.ROOT/(n.DIR+'wheel_receipt_diagnosis_45753813079.json'),d.DIAGNOSIS_BLOB)
        diag['records'][0]['result']['received_sha256']='0'*64
        self.deny('PRIOR_RESULT_IDENTITY',lambda:d.derive_missing(rows,diag))

    def test_native_multitag(self):
        raw,row=self.native()
        _,_,manifest,result=self.run_one(raw,row)
        self.assertEqual(manifest['verified_count'],1)
        self.assertEqual(manifest['schema_version'],2)
        self.assertIsNone(result['inspection_reason'])

    def test_native_inventory(self):
        raw,row=self.native()
        receipt=w.InspectionBudget().inspect(raw,row)
        self.assertEqual(len(receipt['tags']),3)
        self.assertTrue(any(x['path'].endswith('.so') for x in receipt['native_candidates']))

    def test_exact_inspection_reason(self):
        raw,row=candidate()
        row['metadata_sha256']='0'*64
        _,_,m,result=self.run_one(raw,row)
        self.assertEqual(m['status'],'BLOCKED')
        self.assertEqual(result['reason'],'INSPECTION_REFUSED')
        self.assertEqual(result['inspection_reason'],'METADATA_DIGEST')
        self.assertEqual(result['received_sha256'],row['sha256'])

    def test_generic_unknown_reason_not_leaked(self):
        raw,row=candidate()
        with patch.object(n._EvidenceBatch,'inspect',side_effect=w.Blocked('untrusted path /secret/data')):
            _,_,m,result=self.run_one(raw,row)
        self.assertEqual(result['inspection_reason'],'UNCLASSIFIED_INSPECTION_REFUSAL')
        self.assertNotIn('secret',json.dumps(result))

    def test_transport_not_inspection(self):
        raw,row=candidate()
        _,_,m,result=self.run_one(raw,row,503)
        self.assertEqual(result['reason'],'HTTP_STATUS')
        self.assertIsNone(result['inspection_reason'])

    def test_native_explicit_directory_refusal(self):
        i=zipfile.ZipInfo('demo_pkg.libs/');i.create_system=3;i.external_attr=(stat.S_IFDIR|0o755)<<16|0x10
        raw,row=candidate(extras=[(i,b'')])
        self.assertEqual(self.run_one(raw,row)[3]['inspection_reason'],'ZIP_NONREGULAR')

    def test_unknown_extra_refusal(self):
        i=zipfile.ZipInfo('native-extra');i.extra=b'\xff\xff\x00\x00'
        raw,row=candidate(extras=[(i,b'x')])
        self.assertEqual(self.run_one(raw,row)[3]['inspection_reason'],'ZIP_UNSUPPORTED')

    def test_zip64_needed_version_refusal(self):
        raw,row=candidate()
        buf=bytearray(raw);cd=buf.find(b'PK\x01\x02');struct.pack_into('<H',buf,cd+6,45)
        raw=bytes(buf);row['sha256']=w.sha(raw)
        self.assertEqual(self.run_one(raw,row)[3]['inspection_reason'],'ZIP_UNSUPPORTED')

    def test_descriptor_flag_refusal(self):
        raw,row=candidate()
        buf=bytearray(raw);cd=buf.find(b'PK\x01\x02');struct.pack_into('<H',buf,cd+8,8)
        raw=bytes(buf);row['sha256']=w.sha(raw)
        self.assertEqual(self.run_one(raw,row)[3]['inspection_reason'],'ZIP_UNSUPPORTED')

    def test_symlink_stays_refused(self):
        i=zipfile.ZipInfo('native-link');i.create_system=3;i.external_attr=(stat.S_IFLNK|0o777)<<16
        raw,row=candidate(extras=[(i,b'target')])
        self.assertEqual(self.run_one(raw,row)[3]['inspection_reason'],'ZIP_NONREGULAR')

    def test_fail_closed_no_second_request(self):
        raw,row=candidate();row['metadata_sha256']='0'*64
        raw2,row2=candidate(build=2)
        replay=a.Replay({row['url']:wire(raw),row2['url']:wire(raw2)})
        p,sha=d.run_fixture([row,row2],'fixture-plan',replay,self.parent)
        m=d.verify_generation(p,sha,[row,row2],'fixture-plan')
        self.assertEqual(m['attempted_count'],1)
        self.assertEqual(len(replay.requests),1)

    def alter(self,path,field,value):
        target=path/'request-001-result.json'
        result=json.loads(target.read_bytes());result[field]=value
        raw=n.canonical(result);target.write_bytes(raw)
        mp=path/'manifest.json';manifest=json.loads(mp.read_bytes())
        for i,x in enumerate(manifest['files']):
            if x['name']==target.name:manifest['files'][i]=a.file_identity(target.name,raw)
        raw=n.canonical(manifest);mp.write_bytes(raw);return w.sha(raw)

    def test_unapproved_detail_refused(self):
        raw,row=candidate();row['metadata_sha256']='0'*64
        path,_,_,_=self.run_one(raw,row)
        sha=self.alter(path,'inspection_reason','UNTRUSTED_MESSAGE')
        self.deny('INSPECTION_DETAIL_IDENTITY',lambda:d.verify_generation(path,sha,[row],'fixture-plan'))

    def test_detail_on_verified_refused(self):
        raw,row=candidate()
        path,_,_,_=self.run_one(raw,row)
        sha=self.alter(path,'inspection_reason','METADATA_DIGEST')
        self.deny('INSPECTION_DETAIL_IDENTITY',lambda:d.verify_generation(path,sha,[row],'fixture-plan'))

    def test_wrong_http_status_on_inspection_refused(self):
        raw,row=candidate();row['metadata_sha256']='0'*64
        path,_,_,_=self.run_one(raw,row)
        sha=self.alter(path,'http_status',503)
        self.deny('INSPECTION_DETAIL_IDENTITY',lambda:d.verify_generation(path,sha,[row],'fixture-plan'))

    def test_historical_schema_unchanged(self):
        raw,row=candidate()
        path,sha=a._run([row],'fixture-plan',a.Replay({row['url']:wire(raw)}),self.parent)
        self.assertEqual(a.verify_generation(path,sha,[row],'fixture-plan')['schema_version'],1)
        self.deny('MANIFEST_IDENTITY',lambda:d.verify_generation(path,sha,[row],'fixture-plan'))

    def test_non_fixture_refused(self):
        self.deny('OFFLINE_FIXTURE_ONLY',lambda:d.run_fixture([], 'fixture-plan',object(),self.parent))

if __name__=='__main__': unittest.main(verbosity=2)
