"""Inert missing-only producer/verifier regressions."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import os
import subprocess
from email.message import Message
from unittest.mock import patch
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
import wheel_missing_hosted as m
from test_wheel_acquisition_offline import candidate,wire

a,w,h,n,g,t=m.MODS

class Tests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.parent=Path(temp.name)
        self.raw,self.row=candidate()
        self.caps={'body':self.row['bytes'],'expanded':w.MAX_TOTAL,'notice':w.MAX_NOTICES,'evidence':n.MAX_EVIDENCE_BATCH}

    def deny(self,reason,fn):
        with self.assertRaisesRegex(w.Blocked,'^'+reason+'$'): fn()

    def generate(self,caps=None):
        caps=self.caps if caps is None else caps
        replay=a.Replay({self.row['url']:wire(self.raw)})
        path,digest=m.run_fixture([self.row],replay,self.parent,caps)
        manifest=m.verify_generation(path,digest,[self.row],'fixture',scope=m.FIXTURE_SCOPE,caps=caps)
        return path,digest,manifest

    def test_exact_plan(self):
        rows,caps=m.plan()
        self.assertEqual(len(rows),63);self.assertEqual(sum(r['bytes'] for r in rows),225397605)
        self.assertEqual(caps,{'body':225397605,'expanded':4294072708,'notice':33549191,'evidence':67097955})

    def test_disarmed(self):
        with patch.object(m,'plan') as plan,patch.object(m.http.client,'HTTPSConnection') as conn:
            self.deny('FRESH_APPROVAL_REQUIRED',m.produce)
            self.deny('FRESH_APPROVAL_REQUIRED',m.retrieve)
            plan.assert_not_called();conn.assert_not_called()

    def test_body_cap(self):
        self.deny('RESIDUAL_BODY_LIMIT',lambda:self.generate({**self.caps,'body':self.row['bytes']-1}))

    def test_expanded_cap(self):
        p,s,manifest=self.generate({**self.caps,'expanded':1})
        self.assertEqual(manifest['verified_count'],0)
        self.assertEqual(m.settlement(p,manifest,[self.row])['last_result']['inspection_reason'],'BATCH_EXPANSION_LIMIT')

    def test_notice_cap(self):
        p,s,manifest=self.generate({**self.caps,'notice':0})
        self.assertEqual(m.settlement(p,manifest,[self.row])['last_result']['inspection_reason'],'BATCH_EXPANSION_LIMIT')

    def test_evidence_cap(self):
        p,s,manifest=self.generate({**self.caps,'evidence':1})
        self.assertEqual(m.settlement(p,manifest,[self.row])['last_result']['inspection_reason'],'EVIDENCE_BATCH_LIMIT')

    def test_verifier_residual_caps(self):
        p,s,manifest=self.generate()
        for key,reason in [('expanded','BATCH_EXPANSION_LIMIT'),('notice','BATCH_EXPANSION_LIMIT'),('evidence','EVIDENCE_BATCH_LIMIT')]:
            self.deny(reason,lambda:m.verify_generation(p,s,[self.row],'fixture',scope=m.FIXTURE_SCOPE,caps={**self.caps,key:1}))

    def roundtrip(self, caps):
        p,s,manifest=self.generate(caps)
        bundle,ident=m.export_generation(p,s,[self.row],'fixture',self.parent,scope=m.FIXTURE_SCOPE,caps=caps)
        record=g.identity('12345','1'*40,ident)
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_STORED) as z:
            z.writestr('receipts.odin',bundle.read_bytes())
        raw=out.getvalue()
        meta={'id':123,'name':record['artifact_name'],'expired':False,'size_in_bytes':len(raw),'digest':'sha256:'+w.sha(raw),
              'workflow_run':{'id':12345,'head_sha':'1'*40,'head_branch':h.BRANCH.removeprefix('refs/heads/')}}
        dest,got=m.replay_artifact(raw,meta,record,'12345','1'*40,[self.row],'fixture',self.parent,scope=m.FIXTURE_SCOPE,caps=caps)
        self.assertEqual(m.settlement(dest,got,[self.row]),m.settlement(p,manifest,[self.row]))
        return got

    def test_verified_roundtrip(self):
        self.assertEqual(self.roundtrip(self.caps)['verified_count'],1)

    def test_blocked_roundtrip(self):
        self.assertEqual(self.roundtrip({**self.caps,'expanded':0})['status'],'BLOCKED')

    def test_scope_separation(self):
        p,s,_=self.generate()
        self.deny('MANIFEST_IDENTITY',lambda:m.verify_generation(p,s,[self.row],'fixture',scope=m.HOSTED_SCOPE,caps=self.caps))

    def test_no_arbitrary_fixture(self):
        self.deny('OFFLINE_FIXTURE_ONLY',lambda:m.run_fixture([self.row],object(),self.parent,self.caps))

    def test_activation_marker_and_claim(self):
        root=self.parent/'checkout';root.mkdir()
        runner=self.parent/'runner';runner.mkdir()
        def git(*args):
            return subprocess.run(['git','-C',str(root),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','-c','core.hooksPath=/dev/null',*args],
                                  check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout.decode().strip()
        git('init','-q')
        for path in (m.SELF,m.WORKFLOW):
            dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((m.ROOT/path).read_bytes())
        git('add','.');git('commit','-qm','inert source')
        parent=git('rev-parse','HEAD')
        (root/m.MARKER).write_bytes(m.MARKER_BYTES)
        git('add',m.MARKER);git('commit','-qm',m.MESSAGE)
        head=git('rev-parse','HEAD')
        event=self.parent/'event.json'
        payload={'ref':h.BRANCH,'before':parent,'after':head,'forced':False,'created':False,'deleted':False,
                 'repository':{'full_name':m.d.REPO},'head_commit':{'id':head,'message':m.MESSAGE}}
        event.write_text(json.dumps(payload))
        env={'GITHUB_ACTIONS':'true','GITHUB_EVENT_NAME':'push','GITHUB_REPOSITORY':m.d.REPO,'GITHUB_REF':h.BRANCH,
             'GITHUB_WORKFLOW':m.WORKFLOW_NAME,'GITHUB_JOB':'collect-once','GITHUB_RUN_ATTEMPT':'1',
             'GITHUB_WORKSPACE':str(root),'C5_APPROVED_ONCE':m.OP,'GITHUB_RUN_ID':'12345','GITHUB_SHA':head,
             'C5_DRIVER_BLOB':m.d.git_blob((root/m.SELF).read_bytes()),'GITHUB_EVENT_PATH':str(event),'RUNNER_TEMP':str(runner)}
        with patch.object(m,'ROOT',root),patch.object(m,'ARMED',True),patch.dict(os.environ,env,clear=True),patch.object(m.http.client,'HTTPSConnection') as conn:
            with patch.dict(os.environ,{'GITHUB_RUN_ATTEMPT':'2'}):
                self.deny('MISSING_CONTEXT',lambda:m.authorize('collect-once'))
            event.write_text(json.dumps({**payload,'forced':True}))
            self.deny('MISSING_EVENT',lambda:m.authorize('collect-once'))
            event.write_text(json.dumps(payload))
            self.assertEqual(m.authorize('collect-once'),(runner,'12345',head))
            self.deny('ONE_USE_CLAIM_CONSUMED',lambda:m.authorize('collect-once'))
            conn.assert_not_called()

    def test_artifact_download_exact_and_residual_cap(self):
        caps={**self.caps,'evidence':1024}
        identity=g.identity('12345','1'*40,{'bytes':100,'sha256':'2'*64,'manifest_sha256':'3'*64})
        payload=b'x'*200
        meta={'id':123,'name':identity['artifact_name'],'expired':False,'size_in_bytes':len(payload),
              'digest':'sha256:'+w.sha(payload),'workflow_run':{'id':12345,'head_sha':'1'*40,
              'head_branch':h.BRANCH.removeprefix('refs/heads/')}}
        class Response:
            def __init__(self,raw):
                self.raw=io.BytesIO(raw);self.status=200;self.headers=Message()
                self.headers['Content-Length']=str(len(raw))
            def read(self,count):return self.raw.read(count)
            def __enter__(self):return self
            def __exit__(self,*_):self.raw.close()
        class Opener:
            def __init__(self,metadata):self.calls=[];self.metadata=metadata
            def open(self,req,timeout):
                self.calls.append(req.full_url)
                return Response(json.dumps(self.metadata).encode() if len(self.calls)==1 else payload)
        opener=Opener(meta)
        got,observed=m.download_exact(identity,'12345','1'*40,'123',w.sha(payload),'fixture',opener,caps)
        self.assertEqual(got,payload);self.assertEqual(observed,meta);self.assertEqual(len(opener.calls),2)
        over=Opener({**meta,'size_in_bytes':m.bundle_cap(caps)+1024*1024+1})
        self.deny('ARTIFACT_UPLOAD_IDENTITY',lambda:m.download_exact(identity,'12345','1'*40,'123',w.sha(payload),'fixture',over,caps))
        self.assertEqual(len(over.calls),1)

if __name__=='__main__': unittest.main(verbosity=2)

