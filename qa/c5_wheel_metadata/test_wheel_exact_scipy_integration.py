"""Exact-row source policy tests. Only generated inert fixture archives."""
import copy
import inspect
import json
import stat
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import wheel_exact_scipy_policy as x
import wheel_exact_scipy_integration as i
import wheel_archive_inspector_v2 as v2
import wheel_archive_inspector as w
import wheel_notice_evidence_v2 as n
import wheel_license_policy as p
import wheel_hosted_final as hosted
from test_wheel_exact_path_candidate import fixture, TARGET, D, WH

PIN='a151f6cd975a32604020cb13fcb86b34b4ec6796'

def bodies():
    return {i.FIXTURE_ROWS[0][0]:fixture()[0],
            i.FIXTURE_ROWS[1][0]:fixture(changes={TARGET:None,
                D+'WHEEL':WH.replace(b'py3-none-any',b'py2-none-any')})[0]}

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=i.load_policy(PIN)
        cls.plan=i.prepare_real(PIN)

    def test_exact_plan(self):
        self.assertEqual(len(self.plan['rows']),15)
        self.assertEqual([v['sequence'] for v in self.plan['rows']],list(range(49,64)))
        self.assertEqual(self.plan['rows'][0]['inspector_policy'],x.REAL_POLICY)
        self.assertTrue(all(v['inspector_policy']==i.STRICT for v in self.plan['rows'][1:]))
        self.assertEqual(x._permit_identity(self.plan['rows'][0]['row']),x.REAL_IDENTITY)
        self.assertEqual(sum(v['row']['bytes'] for v in self.plan['rows']),78611784)
        self.assertIsNone(self.plan['cumulative_evidence_remaining'])
        for flag in ('acquisition_authorised','raw_replay_available','production_ready','license_reviewed'):
            self.assertIs(self.plan[flag],False)

    def test_real_refuses(self):
        for arg in (b'',fixture()[0],self.plan):
            with self.subTest(type=type(arg)),self.assertRaisesRegex(w.Blocked,'^FRESH_APPROVAL_REQUIRED$'):
                i.inspect_real(arg,PIN)
        self.assertFalse(hosted.ARMED);self.assertFalse(hosted.DISCOVERY_ARMED)
        self.assertIsNone(hosted.PUBLIC_REVIEW_SHA256)

    def test_wrong_policy_pin(self):
        for value in ('0'*40,None,'not-a-pin'):
            with self.subTest(value=value),self.assertRaises(w.Blocked):
                i.load_policy(value)

    def test_policy_source_drift(self):
        original=p.pinned_text
        def fail(path,blob):
            if path.name=='wheel_exact_scipy_policy.py': raise w.Blocked('PIN_DIGEST')
            return original(path,blob)
        with patch.object(p,'pinned_text',side_effect=fail):
            with self.assertRaisesRegex(w.Blocked,'^PIN_DIGEST$'): i.load_policy(PIN)

    def test_mock_success(self):
        b=bodies();raw=i.run_mock(b,PIN)
        result=i.verify_mock(b,raw,i.sha(raw),PIN)
        self.assertEqual(result['calls'],[49,50])
        self.assertEqual(result['received_bytes'],3261)
        self.assertEqual(result['status'],'SYNTHETIC_COMPLETE')
        self.assertEqual(result['results'][0]['inspector_policy'],x.FIXTURE_POLICY)
        self.assertEqual(result['results'][1]['inspector_policy'],i.STRICT)
        self.assertNotIn('member',result['results'][1])
        self.assertEqual(result['results'][0]['member'],{'path_sha256':i.TARGET_SHA,
            'bytes':24,'sha256':'c593b03d7c966e9236fd1003ff77d4a857f32d20917cd8313493226fe928ebd5',
            'central_occurrences':1,'record_occurrences':1})
        for flag in ('actual_wheel_verified','production_ready','license_reviewed','acquisition_authorised','raw_replay_available'):
            self.assertIs(result[flag],False)
        for value in (b'Synthetic notice only',b'Transparent Busy.ani',b'base64',b'generated inert fixture'):
            self.assertNotIn(value,raw)

    def test_refusal_stops(self):
        b=bodies();b[i.FIXTURE_ROWS[0][0]]=b'bad'
        result=json.loads(i.run_mock(b,PIN))
        self.assertEqual(result['calls'],[49]);self.assertEqual(len(result['results']),1)
        self.assertEqual(result['results'][0]['reason'],'FIXTURE_BYTES')
        self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(result['totals'],{'expanded':0,'notice':0,'evidence':0})

    def test_second_refusal_preserves_first(self):
        b=bodies();b[i.FIXTURE_ROWS[1][0]]=b'bad'
        result=json.loads(i.run_mock(b,PIN))
        self.assertEqual(result['calls'],[49,50])
        self.assertEqual([v['status'] for v in result['results']],['INSPECTED','REFUSED'])
        self.assertGreater(result['totals']['evidence'],0)

    def test_body_budget_before_second_fetch(self):
        result=json.loads(i.run_mock(bodies(),PIN,caps={**i.FIXTURE_CAPS,'body':1768}))
        self.assertEqual(result['calls'],[49])
        self.assertEqual(result['results'][-1]['reason'],'FIXTURE_BODY_CAP')

    def test_expansion_notice_evidence_caps(self):
        for key in ('expanded','notice','evidence'):
            with self.subTest(key=key):
                result=json.loads(i.run_mock(bodies(),PIN,caps={**i.FIXTURE_CAPS,key:1}))
                self.assertEqual(result['calls'],[49])
                self.assertEqual(result['status'],'BLOCKED')
                self.assertEqual(result['totals'],{'expanded':0,'notice':0,'evidence':0})

    def test_no_cap_increase_or_extra_input(self):
        with self.assertRaisesRegex(w.Blocked,'^FIXTURE_CAPS$'):
            i.run_mock(bodies(),PIN,caps={**i.FIXTURE_CAPS,'body':3262})
        with self.assertRaisesRegex(w.Blocked,'^FIXTURE_INPUTS$'):
            i.run_mock({**bodies(),x.REAL_IDENTITY[0]:b''},PIN)

    def test_permit_roles_and_identity(self):
        permit=x._Permit(x.FIXTURE_POLICY,x.FIXTURE_IDENTITIES[0],PIN)
        self.assertEqual(x.classify_entry(TARGET.encode(),(stat.S_IFREG|0o644)<<16,permit),(TARGET,False))
        for attrs,reason in [(0,'UNSAFE_PATH'),((stat.S_IFLNK|0o777)<<16,'ZIP_SYMLINK'),
                             (((stat.S_IFREG|0o644)<<16)|0x400,'ZIP_REPARSE_ATTRIBUTE')]:
            with self.subTest(attrs=attrs),self.assertRaisesRegex(x.Blocked,'^'+reason+'$'):
                x.classify_entry(TARGET.encode(),attrs,permit)
        for candidate in (TARGET+'/',TARGET+'/child',TARGET.lower(),'other name'):
            with self.subTest(candidate=candidate),self.assertRaises(x.Blocked):
                x.classify_entry(candidate.encode(),(stat.S_IFREG|0o644)<<16,permit)
        raw,row=fixture()
        for wrong in (x._Permit(x.REAL_POLICY,x.REAL_IDENTITY,PIN),
                      x._Permit(x.FIXTURE_POLICY,x.FIXTURE_IDENTITIES[1],PIN)):
            with self.subTest(scope=wrong.scope),self.assertRaisesRegex(x.Blocked,'^EXACT_POLICY_IDENTITY$'):
                x._ExactBudget().inspect(raw,row,wrong)

    def test_stored_deflate_and_strict_baseline(self):
        for method in (0,8):
            raw,row=fixture(method)
            with self.subTest(method=method):
                with self.assertRaisesRegex(v2.Blocked,'^UNSAFE_PATH$'): v2.InspectionBudget().inspect(raw,row)
                permit=x._Permit(x.FIXTURE_POLICY,x._permit_identity(row),PIN)
                receipt,payloads,member=x._ExactBudget().inspect(raw,row,permit,capture_notices=True)
                self.assertEqual(member['central_occurrences'],1);self.assertEqual(member['record_occurrences'],1)
                self.assertEqual(member['sha256'],'c593b03d7c966e9236fd1003ff77d4a857f32d20917cd8313493226fe928ebd5')
                self.assertFalse(receipt['license_reviewed'])
                self.assertEqual(set(payloads),{D+'licenses/LICENSE'})

    def test_record_and_missing_occurrence(self):
        permit=x._Permit(x.FIXTURE_POLICY,x.FIXTURE_IDENTITIES[0],PIN)
        with self.assertRaisesRegex(x.Blocked,'^EXACT_MEMBER_ABSENT$'):
            x.verify_record(b'RECORD,,\n','RECORD',{'RECORD':({'bytes':0},{})},permit)

    def test_wrapper_replay_and_tamper(self):
        row=i._fixture_plan()[0];raw=bodies()[row['row']['filename']]
        encoded,_,_=i._inspect_fixture(raw,row,PIN,self.doc,
            {'expanded':0,'notice':0,'evidence':0},i.FIXTURE_CAPS)
        wrapper=i.verify_fixture_receipt(raw,row,encoded,i.sha(encoded),PIN)
        self.assertEqual(wrapper['source_blob'],self.doc['source_pins'][i.DIR+'wheel_exact_scipy_policy.py'])
        self.assertEqual(wrapper['notice_evidence_sha256'],i.sha(n.canonical(wrapper['notice_evidence'])))
        for key,value in [('scope',i.REAL_SCOPE),('sequence',50),('policy_blob','0'*40),
                          ('source_blob','0'*40),('production_ready',True),('member',{})]:
            altered={**wrapper,key:value};bad=n.canonical(altered)
            with self.subTest(key=key),self.assertRaisesRegex(w.Blocked,'^EXACT_RECEIPT_REPLAY$'):
                i.verify_fixture_receipt(raw,row,bad,i.sha(bad),PIN)
        with self.assertRaisesRegex(w.Blocked,'^EXACT_RECEIPT_HASH$'):
            i.verify_fixture_receipt(raw,row,encoded,'0'*64,PIN)
        with self.assertRaisesRegex(w.Blocked,'^FIXTURE_PLAN_IDENTITY$'):
            i.verify_fixture_receipt(raw,{**row,'sequence':50},encoded,i.sha(encoded),PIN)

    def test_projection_forgery(self):
        b=bodies();raw=i.run_mock(b,PIN);doc=json.loads(raw);doc['production_ready']=True
        bad=n.canonical(doc)
        with self.assertRaisesRegex(w.Blocked,'^EXACT_PROJECTION_REPLAY$'):
            i.verify_mock(b,bad,i.sha(bad),PIN)
        with self.assertRaisesRegex(w.Blocked,'^EXACT_PROJECTION_HASH$'):
            i.verify_mock(b,raw,'0'*64,PIN)

    def test_unchanged_primitive_source(self):
        for name in ('name','norm','header','identities','member','message','single'):
            with self.subTest(name=name):
                self.assertEqual(inspect.getsource(getattr(x,name)),inspect.getsource(getattr(v2,name)))
        for name in ('MAX_ARCHIVE','MAX_MEMBERS','MAX_MEMBER','MAX_WHEEL','MAX_TOTAL','MAX_NOTICE',
                     'MAX_NOTICES','MAX_CONTROL','MAX_PATH_BYTES','MAX_DIRECTORIES','CHUNK'):
            self.assertEqual(getattr(x,name),getattr(v2,name))

    def test_prior_receipts_and_no_markers(self):
        self.assertEqual(len(p.prior_placements()),5)
        for marker in ('APPROVAL_WHEEL_PUBLIC_DISCOVERY_20261126.txt','APPROVAL_WHEEL_POLICY_V3_HOSTED_20261126.txt'):
            self.assertFalse((i.ROOT/i.DIR/marker).exists())

if __name__=='__main__':
    unittest.main(verbosity=2)
