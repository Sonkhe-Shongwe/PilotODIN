"""Generated fixtures only, no real approval, wheels or artifact service."""
import copy
import io
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
import wheel_hosted_policy_v3 as m
import wheel_acquisition_offline as a
import wheel_archive_inspector as w
import wheel_notice_evidence_v2 as n
import wheel_license_policy as p
import wheel_settlement_core as c
import wheel_hosted_proposal as h
from test_wheel_acquisition_offline import candidate,wire
from test_wheel_archive_inspector import D

class Tests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.parent=Path(tmp.name)
        raw,row=candidate()
        self.raw=raw;self.row=row;self.rows=[row]
        self.bindings={row['filename']:p.binding(row['filename'],row['metadata_sha256'],'2.4',row['license_files'])}
        self.caps={'body':row['bytes'],'expanded':w.MAX_TOTAL,'notice':w.MAX_NOTICES,'evidence':n.MAX_EVIDENCE_BATCH}

    def deny(self,reason,fn):
        with self.assertRaisesRegex(w.Blocked,'^'+reason+'$'):fn()

    def generate(self,caps=None):
        caps=self.caps if caps is None else caps
        replay=a.Replay({self.row['url']:wire(self.raw)})
        path,sha=m.run_fixture(self.rows,'fixture',replay,self.parent,bindings=self.bindings,caps=caps)
        manifest=m.verify_generation(path,sha,self.rows,'fixture',bindings=self.bindings,caps=caps)
        bundle,ident=m.export_generation(path,sha,self.rows,'fixture',self.parent,bindings=self.bindings,caps=caps)
        record=m.artifact_record('12345','1'*40,ident,self.rows,'fixture',bindings=self.bindings,caps=caps)
        return manifest,bundle,record

    def zip(self,bundle,name='receipts.odin',extras=False,attrs=None):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_STORED) as z:
            i=zipfile.ZipInfo(name)
            if attrs is not None:i.external_attr=attrs
            z.writestr(i,bundle)
            if extras:z.writestr('extra',b'bad')
        return out.getvalue()

    def meta(self,raw,record):
        return {'id':123,'name':record['artifact_name'],'expired':False,'size_in_bytes':len(raw),
                'digest':'sha256:'+w.sha(raw),
                'workflow_run':{'id':12345,'head_sha':'1'*40,'head_branch':m.BRANCH.removeprefix('refs/heads/')}}

    def replay(self,raw,record,meta=None,*,caps=None,id=123,digest=None):
        caps=self.caps if caps is None else caps
        return m.replay_artifact(raw,self.meta(raw,record) if meta is None else meta,record,
                                 '12345','1'*40,id,w.sha(raw) if digest is None else digest,
                                 self.rows,'fixture',self.parent,bindings=self.bindings,caps=caps)

    def fixture_gate(self):
        inputs=m.plan_identity()
        expected={'parent':'1'*40,'head':'2'*40,'driver_blob':'3'*40,'workflow_blob':'4'*40,'inputs':inputs}
        context={'GITHUB_ACTIONS':'true','GITHUB_EVENT_NAME':'push','GITHUB_REPOSITORY':m.REPO,
                 'GITHUB_REF':m.BRANCH,'GITHUB_WORKFLOW':m.WORKFLOW_NAME,'GITHUB_JOB':'collect-once',
                 'GITHUB_RUN_ATTEMPT':'1','C5_APPROVED_ONCE':m.OP,'GITHUB_SHA':expected['head'],
                 'C5_DRIVER_BLOB':expected['driver_blob'],'C5_WORKFLOW_BLOB':expected['workflow_blob'],
                 'GITHUB_RUN_ID':'12345'}
        event={'ref':m.BRANCH,'before':expected['parent'],'after':expected['head'],'forced':False,
               'created':False,'deleted':False,'repository':{'full_name':m.REPO},
               'head_commit':{'id':expected['head'],'message':m.MESSAGE}}
        marker=m.marker_bytes(inputs)
        checkout={'head':expected['head'],'parents':[expected['parent']],'changes':[('A',m.MARKER)],
                  'message':m.MESSAGE,'marker':marker,'marker_blob':m.git_blob(marker),
                  'driver_blob':expected['driver_blob'],'workflow_blob':expected['workflow_blob'],
                  'legacy_markers_absent':True}
        return event,context,checkout,expected

    def test_exact_plan(self):
        rows,bindings,caps=m.plan()
        self.assertEqual(len(rows),len(bindings));self.assertEqual(len(rows),63)
        self.assertEqual(caps['body'],225397605)
        self.assertEqual(m.bundle_cap(caps),68457827)
        self.assertEqual(m.bundle_cap(caps)+1024*1024,69506403)
        print('C5_HOSTED_POLICY_V3_PLAN_PASS 63; five prior notices; disarmed')

    def test_disarmed(self):
        with patch.object(m,'plan') as plan,patch.object(m,'activation_contract') as gate:
            self.deny('FRESH_APPROVAL_REQUIRED',m.produce)
            self.deny('FRESH_APPROVAL_REQUIRED',m.retrieve)
            plan.assert_not_called();gate.assert_not_called()
        self.assertEqual(list(self.parent.iterdir()),[])

    def test_gate_and_claim(self):
        args=self.fixture_gate()
        self.assertEqual(m.fixture_claim(self.parent,*args,'collect-once')['scope'],m.TRANSFER_SCOPE)
        self.deny('ONE_USE_CLAIM_CONSUMED',lambda:m.fixture_claim(self.parent,*args,'collect-once'))
        self.assertEqual(len(list(self.parent.iterdir())),1)

    def test_gate_wrong_context(self):
        args=self.fixture_gate()
        for key,value in [('GITHUB_RUN_ATTEMPT','2'),('GITHUB_JOB','retrieve-once'),
                          ('GITHUB_EVENT_NAME','workflow_dispatch'),('GITHUB_SHA','0'*40),
                          ('C5_DRIVER_BLOB','0'*40),('C5_WORKFLOW_BLOB','0'*40),
                          ('C5_APPROVED_ONCE','C5-WHEEL-MISSING-HOSTED-ONCE-20261126')]:
            with self.subTest(key=key):
                e,ctx,ch,ex=copy.deepcopy(args);ctx[key]=value
                self.deny('GATE_CONTEXT',lambda:m.fixture_claim(self.parent,e,ctx,ch,ex,'collect-once'))
        self.assertEqual(list(self.parent.iterdir()),[])

    def test_gate_wrong_event(self):
        args=self.fixture_gate()
        for key,value in [('forced',True),('before','0'*40),('created',True),('deleted',True)]:
            with self.subTest(key=key):
                e,ctx,ch,ex=copy.deepcopy(args);e[key]=value
                self.deny('GATE_EVENT',lambda:m.fixture_claim(self.parent,e,ctx,ch,ex,'collect-once'))
        self.assertEqual(list(self.parent.iterdir()),[])

    def test_gate_checkout(self):
        args=self.fixture_gate()
        for key,value in [('parents',['0'*40]),('changes',[('M',m.MARKER)]),
                          ('changes',[('A',m.MARKER),('M',m.SELF)]),('marker',b''),
                          ('marker_blob','0'*40),('driver_blob','0'*40),
                          ('workflow_blob','0'*40),('legacy_markers_absent',False)]:
            with self.subTest(key=key,value=value):
                e,ctx,ch,ex=copy.deepcopy(args);ch[key]=value
                self.deny('GATE_CHECKOUT',lambda:m.fixture_claim(self.parent,e,ctx,ch,ex,'collect-once'))
        self.assertEqual(list(self.parent.iterdir()),[])

    def test_gate_scope_drift(self):
        e,ctx,ch,ex=self.fixture_gate();ex['inputs']['caps']['body']+=1
        self.deny('GATE_EXPECTATION',lambda:m.fixture_claim(self.parent,e,ctx,ch,ex,'collect-once'))
        self.assertEqual(list(self.parent.iterdir()),[])

    def test_gate_retriever_distinct(self):
        e,ctx,ch,ex=self.fixture_gate()
        m.fixture_claim(self.parent,e,ctx,ch,ex,'collect-once')
        ctx['GITHUB_JOB']='retrieve-once'
        self.assertEqual(m.fixture_claim(self.parent,e,ctx,ch,ex,'retrieve-once')['phase'],'retrieve-once')
        self.deny('ONE_USE_CLAIM_CONSUMED',lambda:m.fixture_claim(self.parent,e,ctx,ch,ex,'retrieve-once'))

    def test_roundtrip_success(self):
        manifest,bundle,record=self.generate()
        path,got=self.replay(self.zip(bundle.read_bytes()),record)
        self.assertEqual(got,manifest)
        self.assertEqual(got['verified_count'],1)
        self.assertFalse(got['production_ready'])
        self.assertTrue((path/'wheel-001-evidence.json').is_file())

    def test_roundtrip_refusal(self):
        caps={**self.caps,'expanded':0}
        manifest,bundle,record=self.generate(caps)
        path,got=self.replay(self.zip(bundle.read_bytes()),record,caps=caps)
        self.assertEqual(manifest,got);self.assertEqual(got['status'],'BLOCKED')
        self.assertFalse((path/'wheel-001-evidence.json').exists())

    def test_wrong_artifact_id(self):
        _,bundle,record=self.generate();raw=self.zip(bundle.read_bytes())
        before=set(self.parent.iterdir())
        self.deny('ARTIFACT_IDENTITY',lambda:self.replay(raw,record,id=124))
        self.assertEqual(set(self.parent.iterdir()),before)

    def test_wrong_upload_digest(self):
        _,bundle,record=self.generate();raw=self.zip(bundle.read_bytes())
        self.deny('ARTIFACT_UPLOAD_IDENTITY',lambda:self.replay(raw,record,digest='0'*64))

    def test_wrong_run(self):
        _,bundle,record=self.generate();raw=self.zip(bundle.read_bytes());meta=self.meta(raw,record)
        meta['workflow_run']['id']=12346
        self.deny('ARTIFACT_RUN',lambda:self.replay(raw,record,meta))

    def test_expired(self):
        _,bundle,record=self.generate();raw=self.zip(bundle.read_bytes());meta=self.meta(raw,record);meta['expired']=True
        self.deny('ARTIFACT_IDENTITY',lambda:self.replay(raw,record,meta))

    def test_record_scope_and_policy(self):
        _,bundle,record=self.generate();raw=self.zip(bundle.read_bytes())
        for key,value in [('scope',m.HOSTED_SCOPE),('policy_sha256','0'*64),('run_attempt',True),('rows_sha256','0'*64)]:
            with self.subTest(key=key):
                changed={**record,key:value}
                self.deny('RECEIPT_CONTEXT',lambda:self.replay(raw,changed))

    def test_outer_hash(self):
        _,bundle,record=self.generate();raw=self.zip(bundle.read_bytes());meta=self.meta(raw,record)
        corrupted=bytes([raw[0]^1])+raw[1:]
        self.deny('ARTIFACT_HASH',lambda:self.replay(corrupted,record,meta,digest=w.sha(raw)))

    def test_outer_extra_file(self):
        _,bundle,record=self.generate()
        self.deny('ARTIFACT_INVENTORY',lambda:self.replay(self.zip(bundle.read_bytes(),extras=True),record))

    def test_outer_path(self):
        _,bundle,record=self.generate()
        self.deny('ARTIFACT_MEMBER',lambda:self.replay(self.zip(bundle.read_bytes(),name='../receipts.odin'),record))

    def test_outer_special_attributes(self):
        _,bundle,record=self.generate()
        for attrs in (0x400,0x10,0x08,(stat.S_IFLNK|0o777)<<16):
            with self.subTest(attrs=attrs):
                self.deny('ARTIFACT_MEMBER',lambda:self.replay(self.zip(bundle.read_bytes(),attrs=attrs),record))

    def test_bundle_hash(self):
        _,bundle,record=self.generate();payload=bundle.read_bytes()
        self.deny('BUNDLE_HASH',lambda:self.replay(self.zip(payload[:-1]+bytes([payload[-1]^1])),record))

    def test_bundle_extra_trailing(self):
        _,bundle,record=self.generate();payload=bundle.read_bytes()+b'x'
        record=m.artifact_record('12345','1'*40',{'bytes':len(payload),'sha256':w.sha(payload),
                                 'manifest_sha256':record['bundle']['manifest_sha256']},
                                 self.rows,'fixture',bindings=self.bindings,caps=self.caps)
        self.deny('BUNDLE_TRAILING',lambda:self.replay(self.zip(payload),record))

    def test_manifest_digest_independent(self):
        _,bundle,record=self.generate();record['bundle']['manifest_sha256']='0'*64
        self.deny('MANIFEST_HASH',lambda:self.replay(self.zip(bundle.read_bytes()),record))

    def test_unsupported_hosted_core_scope(self):
        self.deny('SCOPE',lambda:c.prepare(self.rows,'fixture',self.bindings,self.caps,m.HOSTED_SCOPE))

    def test_nonfixture_replay(self):
        self.deny('OFFLINE_FIXTURE_ONLY',lambda:m.run_fixture(self.rows,'fixture',object(),self.parent,
                                                            bindings=self.bindings,caps=self.caps))

if __name__=='__main__': unittest.main(verbosity=2)
