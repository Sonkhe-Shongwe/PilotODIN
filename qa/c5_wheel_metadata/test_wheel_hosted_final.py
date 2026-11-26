"""Final disarmed driver: exact hosted identity and local receipt replay."""
from contextlib import nullcontext
import io
import json
import os
import subprocess
from email.message import Message
from unittest.mock import Mock
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
    def git(self,root,*args):
        return subprocess.run(['git','-C',str(root),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                               '-c','core.autocrlf=false','-c','commit.gpgsign=false',*args],
                              check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10).stdout.decode().strip()

    def test_final_gate_independent_checkout(self):
        root=self.parent/'checkout';root.mkdir();self.git(root,'init','-q')
        pins={**rt.RUNTIME_PINS,**f.EXTRA_PINS}
        for path,pin in pins.items():
            dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(p.pinned_text(f.ROOT/path,pin))
        for path in (f.SELF,f.WORKFLOW):
            dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(b'final inert fixture\n')
        self.git(root,'add','.');self.git(root,'commit','-qm','fixture parent')
        parent=self.git(root,'rev-parse','HEAD');inputs=rt.input_identity()
        (root/f.MARKER).write_bytes(rt.marker_bytes(inputs))
        self.git(root,'add',f.MARKER);self.git(root,'commit','-qm',rt.MESSAGE)
        head=self.git(root,'rev-parse','HEAD');pin=rt.git_blob(b'final inert fixture\n')
        expected={'parent':parent,'head':head,'driver_blob':pin,'workflow_blob':pin,'inputs':inputs}
        context={'GITHUB_ACTIONS':'true','GITHUB_EVENT_NAME':'push','GITHUB_REPOSITORY':rt.REPO,
                 'GITHUB_REF':rt.BRANCH,'GITHUB_WORKFLOW':rt.WORKFLOW_NAME,'GITHUB_JOB':'collect-once',
                 'GITHUB_RUN_ATTEMPT':'1','C5_APPROVED_ONCE':rt.OP,'GITHUB_SHA':head,
                 'C5_DRIVER_BLOB':pin,'C5_WORKFLOW_BLOB':pin,'GITHUB_RUN_ID':'12345'}
        event={'ref':rt.BRANCH,'before':parent,'after':head,'forced':False,'created':False,'deleted':False,
               'repository':{'full_name':rt.REPO},'head_commit':{'id':head,'message':rt.MESSAGE}}
        got=f.review_checkout(root,event,context,expected,'collect-once')
        self.assertEqual(got['scope'],f.m.TRANSFER_SCOPE)
        self.deny('GATE_CONTEXT',lambda:f.review_checkout(root,event,{**context,'C5_DRIVER_BLOB':'0'*40},
                                                           expected,'collect-once'))
        self.deny('GATE_EVENT',lambda:f.review_checkout(root,event,context,{**expected,'parent':'0'*40},'collect-once'))
        (root/f.SELF).write_bytes(b'changed')
        self.deny('DIRTY_CHECKOUT',lambda:f.review_checkout(root,event,context,expected,'collect-once'))

    def test_live_transport_exact_request_mock(self):
        rows,_,_=c.remaining_inputs()
        # Stub the already-reviewed grant check and the HTTPS constructor only.
        # No real socket or real authorization is present.
        conn=Mock();response=Mock();response.status=503;conn.getresponse.return_value=response
        with patch.object(f,'_check_grant') as gate,patch.object(f.http.client,'HTTPSConnection',return_value=conn) as https:
            fetch=f._live_fetch(object(),rows)
            got=fetch(rows[0]['url']);got.close()
            host,port,path,headers=f.h.request_parts(rows[0])
            self.assertEqual(https.call_args.args,(host,port))
            self.assertEqual(https.call_args.kwargs['timeout'],a.REQUEST_TIMEOUT)
            tls=https.call_args.kwargs['context']
            self.assertTrue(tls.check_hostname)
            self.assertEqual(tls.verify_mode,f.ssl.CERT_REQUIRED)
            conn.request.assert_called_once_with('GET',path,headers=headers)
            conn.close.assert_called_once();response.close.assert_called_once()
            self.deny('TRANSPORT_STOPPED',lambda:fetch(rows[1]['url']))
            self.assertEqual(https.call_count,1);self.assertGreaterEqual(gate.call_count,2)

    def test_live_transport_wrong_order_no_connection(self):
        rows,_,_=c.remaining_inputs()
        with patch.object(f,'_check_grant'),patch.object(f.http.client,'HTTPSConnection') as conn:
            fetch=f._live_fetch(object(),rows)
            self.deny('URL_SCOPE',lambda:fetch(rows[1]['url']))
            self.deny('TRANSPORT_STOPPED',lambda:fetch(rows[0]['url']))
            conn.assert_not_called()

    def test_download_protocol_mock(self):
        rows,bindings,caps=c.remaining_inputs();plan=f.diagnostic.MISSING_PLAN_BLOB
        data=self.roundtrip(True);raw,meta,record=data[:3]
        class Response:
            def __init__(self,body):
                self.body=io.BytesIO(body);self.status=200;self.headers=Message()
                self.headers['Content-Length']=str(len(body))
            def read(self,count):return self.body.read(count)
            def __enter__(self):return self
            def __exit__(self,*_):self.body.close()
        class Opener:
            def __init__(self):self.calls=[]
            def open(self,req,timeout):
                self.calls.append(req)
                return Response(json.dumps(meta).encode('utf-8') if len(self.calls)==1 else raw)
        opener=Opener();grant=Mock();grant.claim={'run':'12345','source_sha':'1'*40}
        with patch.object(f,'_check_grant'),patch.object(f.t,'deadline',nullcontext):
            got,observed=f._download_exact(grant,record,'12345','1'*40,'123',w.sha(raw),'inert-token',opener,
                                           rows,plan,bindings=bindings,caps=caps,scope=f.HOSTED_SCOPE)
            self.assertEqual(got,raw);self.assertEqual(observed,meta)
            self.assertEqual([x.full_url.rsplit('/',1)[-1] for x in opener.calls],['123','zip'])
            self.assertTrue(all(x.get_method()=='GET' for x in opener.calls))
            bad=Opener()
            self.deny('ARTIFACT_UPLOAD_IDENTITY',lambda:f._download_exact(
                grant,record,'12345','1'*40,'123','0'*64,'inert-token',bad,
                rows,plan,bindings=bindings,caps=caps,scope=f.HOSTED_SCOPE))
            self.assertEqual(len(bad.calls),1)

    def test_fixture_core_compatible_receipts(self):
        replay=a.Replay({self.rows[0]['url']:wire(self.raw)})
        old,sha=c._collect(self.rows,'fixture',self.bindings,self.caps,c.FIXTURE_SCOPE,replay.get,nullcontext,self.parent)
        path,digest=f._collect(self.rows,'fixture',self.bindings,self.caps,f.FIXTURE_SCOPE,
                               a.Replay({self.rows[0]['url']:wire(self.raw)}).get,nullcontext,self.parent)
        self.assertEqual(digest,sha)
        self.assertEqual((old/'wheel-001-evidence.json').read_bytes(),(path/'wheel-001-evidence.json').read_bytes())

if __name__=='__main__':unittest.main(verbosity=2)
