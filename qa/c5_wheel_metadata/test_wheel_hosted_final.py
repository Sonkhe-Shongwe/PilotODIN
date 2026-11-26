"""Final disarmed driver: exact hosted identity and local receipt replay."""
from contextlib import nullcontext
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
import wheel_hosted_final as f
import wheel_settlement_core as c
import wheel_hosted_runtime as rt
import wheel_acquisition_offline as a
import wheel_archive_inspector as w
import wheel_notice_evidence_v2 as n
import wheel_license_policy as p
from test_wheel_acquisition_offline import candidate,wire

class Tests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.parent=Path(tmp.name)
        raw,row=candidate();self.rows=[row]
        self.bindings={row['filename']:p.binding(row['filename'],row['metadata_sha256'],'2.4',row['license_files'])}
        self.caps={'body':row['bytes'],'expanded':w.MAX_TOTAL,'notice':w.MAX_NOTICES,'evidence':n.MAX_EVIDENCE_BATCH}
        self.raw=raw
    def deny(self,reason,fn):
        with self.assertRaisesRegex(w.Blocked,'^'+reason+'$'):fn()
    def test_disarmed_all_live_seams(self):
        with patch.object(f,'review_checkout') as gate,patch.object(f.http.client,'HTTPSConnection') as conn,patch.object(f,'build_opener') as opener:
            self.deny('FRESH_APPROVAL_REQUIRED',f.produce)
            self.deny('FRESH_APPROVAL_REQUIRED',f.retrieve)
            self.deny('FRESH_APPROVAL_REQUIRED',lambda:f._live_fetch(None,[]))
            self.deny('FRESH_APPROVAL_REQUIRED',lambda:f._download_exact(None,None,'1','1'*40,'1','0'*64,'fixture',None,[], 'fixture',bindings={},caps=self.caps,scope=f.HOSTED_SCOPE))
            gate.assert_not_called();conn.assert_not_called();opener.assert_not_called()
        self.assertEqual(list(self.parent.iterdir()),[])
    def test_exact_hosted_plan(self):
        rows,bindings,caps=c.remaining_inputs()
        result=f.prepare(rows,f.diagnostic.MISSING_PLAN_BLOB,bindings,caps,f.HOSTED_SCOPE)
        self.assertEqual(len(result[0]),63)
        self.assertEqual(f.bundle_cap(caps),68457827)
    def test_fixture_cannot_be_hosted(self):
        self.deny('HOSTED_INPUT_IDENTITY',lambda:f.prepare(self.rows,'fixture',self.bindings,self.caps,f.HOSTED_SCOPE))
        self.assertEqual(list(self.parent.iterdir()),[])
    def test_hosted_policy_and_cap_drift(self):
        rows,bindings,caps=c.remaining_inputs()
        altered={**caps,'notice':caps['notice']-1}
        self.deny('HOSTED_INPUT_IDENTITY',lambda:f.prepare(rows,f.diagnostic.MISSING_PLAN_BLOB,bindings,altered,f.HOSTED_SCOPE))
        bindings[rows[0]['filename']]['metadata_version']='2.1' if bindings[rows[0]['filename']]['metadata_version']!='2.1' else '2.4'
        self.deny('HOSTED_INPUT_IDENTITY',lambda:f.prepare(rows,f.diagnostic.MISSING_PLAN_BLOB,bindings,caps,f.HOSTED_SCOPE))
    def roundtrip(self,hosted=False):
        if hosted:
            rows,bindings,caps=c.remaining_inputs();plan=f.diagnostic.MISSING_PLAN_BLOB;scope=f.HOSTED_SCOPE
            replay=a.Replay({rows[0]['url']:b'HTTP/1.1 503 Unavailable\r\nContent-Length: 0\r\n\r\n'})
        else:
            rows,bindings,caps,plan,scope=self.rows,self.bindings,self.caps,'fixture',f.FIXTURE_SCOPE
            replay=a.Replay({rows[0]['url']:wire(self.raw)})
        bundle,record,expected=f._produce(rows,bindings,caps,scope,plan,replay.get,nullcontext,self.parent,'12345','1'*40)
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_STORED) as z:z.writestr('receipts.odin',bundle.read_bytes())
        raw=out.getvalue()
        meta={'id':123,'name':record['artifact_name'],'expired':False,'size_in_bytes':len(raw),
              'digest':'sha256:'+w.sha(raw),'workflow_run':{'id':12345,'head_sha':'1'*40,'head_branch':f.BRANCH.removeprefix('refs/heads/')}}
        return raw,meta,record,expected,rows,plan,bindings,caps,scope,replay
    def replay(self,data):
        raw,meta,record,expected,rows,plan,bindings,caps,scope,_=data
        return f._replay(raw,meta,record,expected,'12345','1'*40,123,w.sha(raw),rows,plan,self.parent,
                         bindings=bindings,caps=caps,scope=scope)
    def test_fixture_roundtrip(self):
        data=self.roundtrip();self.assertEqual(self.replay(data),data[3])
        self.assertEqual(data[3]['verified_count'],1)
    def test_hosted_exact_plan_inert_refusal(self):
        data=self.roundtrip(True);self.assertEqual(self.replay(data),data[3])
        self.assertEqual(data[3]['attempted_count'],1);self.assertEqual(data[3]['verified_count'],0)
        self.assertEqual(data[3]['last_result']['reason'],'HTTP_STATUS')
        self.assertEqual(len(data[-1].requests),1)
    def test_hosted_record_cannot_replay_as_fixture(self):
        data=list(self.roundtrip(True));data[8]=f.FIXTURE_SCOPE
        self.deny('RECEIPT_CONTEXT',lambda:self.replay(data))
    def test_settlement_tamper(self):
        data=self.roundtrip();data[3]['received_bytes']+=1
        self.deny('PRODUCER_VERIFIER_SETTLEMENT',lambda:self.replay(data))
    def test_artifact_digest_tamper(self):
        data=self.roundtrip();data[1]['digest']='sha256:'+'0'*64
        self.deny('ARTIFACT_UPLOAD_IDENTITY',lambda:self.replay(data))
    def test_old_record_scope_refused(self):
        data=self.roundtrip();data[2]['scope']=f.m.TRANSFER_SCOPE
        self.deny('RECEIPT_CONTEXT',lambda:self.replay(data))
    def test_exact_runtime_source_pin_observation(self):
        for path,pin in f.EXTRA_PINS.items():
            self.assertEqual(rt.git_blob(p.pinned_text(f.ROOT/path,pin)),pin)
    def test_fixture_core_compatible_receipts(self):
        replay=a.Replay({self.rows[0]['url']:wire(self.raw)})
        old,sha=c._collect(self.rows,'fixture',self.bindings,self.caps,c.FIXTURE_SCOPE,replay.get,nullcontext,self.parent)
        path,digest=f._collect(self.rows,'fixture',self.bindings,self.caps,f.FIXTURE_SCOPE,
                               a.Replay({self.rows[0]['url']:wire(self.raw)}).get,nullcontext,self.parent)
        self.assertEqual(digest,sha)
        self.assertEqual((old/'wheel-001-evidence.json').read_bytes(),(path/'wheel-001-evidence.json').read_bytes())

if __name__=='__main__':unittest.main(verbosity=2)
