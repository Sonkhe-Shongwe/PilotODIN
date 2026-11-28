"""Inert actual-driver preflight and hosted receipt contract tests."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
import wheel_acquisition_driver as d
from test_wheel_acquisition_offline import candidate,wire
from contextlib import nullcontext

MODS=d.load_modules()
a,w,h,n,g,t=MODS


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def deny(self,reason,fn):
        with self.assertRaisesRegex(d.Refused,'^'+reason+'$'): fn()

    def test_pins_and_plan(self):
        self.assertTrue(d.verify_sources())
        self.assertEqual(a.review_pinned_plan()['requests'],68)
        self.assertEqual(h.MAX_BUNDLE,d.MAX_BUNDLE)
        self.assertEqual(g.MAX_ZIP,d.MAX_ZIP)

    def test_adapter_flag_source_change_refused(self):
        with patch.object(d,'read_file',wraps=d.read_file) as read:
            original=read._mock_wraps
            read.side_effect=lambda path: (original(path).replace(b'LIVE_ENABLED = False',b'LIVE_ENABLED = True')
                       if path.name=='wheel_hosted_proposal.py' else original(path))
            self.deny('SOURCE_PIN',d.verify_sources)

    def test_disabled_both_phases(self):
        with patch.object(d,'load_modules') as load, patch.object(d,'claim') as claim:
            for phase in ('collect-once','retrieve-once'):
                self.deny('FRESH_APPROVAL_REQUIRED',lambda:d.authorize(phase))
            load.assert_not_called(); claim.assert_not_called()

    def test_armed_flag_alone_refuses(self):
        with patch.object(d,'ARMED',True),patch.dict(d.os.environ,{},clear=True):
            self.deny('DRIVER_CONTEXT',lambda:d.authorize('collect-once'))

    def test_process_local_gate_restored(self):
        def fake_collect():
            self.assertIs(h.LIVE_ENABLED,True)
            return ('fixture','digest')
        with patch.object(h,'collect',side_effect=fake_collect):
            self.assertEqual(d.collect_after_authorization(h),('fixture','digest'))
        self.assertIs(h.LIVE_ENABLED,False)
        with patch.object(h,'collect',side_effect=OSError('inert')):
            with self.assertRaises(OSError): d.collect_after_authorization(h)
        self.assertIs(h.LIVE_ENABLED,False)
        with patch.object(h,'LIVE_ENABLED',True),patch.object(h,'collect') as collect:
            self.deny('ADAPTER_ALREADY_ENABLED',lambda:d.collect_after_authorization(h))
            collect.assert_not_called()

    def test_complete_runtime_contract_inert(self):
        import shutil
        checkout=self.root/'checkout'; checkout.mkdir()
        runner=self.root/'runner'; runner.mkdir()
        old_root=self.root
        self.root=checkout
        self.addCleanup(setattr,self,'root',old_root)
        self.cmd('init','-q')
        for relative in [d.DIR+x for x in d.PINS]+[d.SELF,d.WORKFLOW_PATH]:
            dst=checkout/relative; dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(d.ROOT/relative,dst)
        self.cmd('add','.'); self.cmd('commit','-qm','reviewed inert arm fixture')
        parent=self.cmd('rev-parse','HEAD').decode().strip()
        marker=checkout/d.MARKER; marker.write_bytes(d.MARKER_BYTES)
        self.cmd('add',d.MARKER); self.cmd('commit','-qm',d.MESSAGE)
        head=self.cmd('rev-parse','HEAD').decode().strip()
        event=old_root/'event.json'
        event.write_text(json.dumps({'ref':h.BRANCH,'before':parent,'after':head,
            'forced':False,'created':False,'deleted':False,'repository':{'full_name':d.REPO},
            'head_commit':{'id':head,'message':d.MESSAGE}}))
        env={'GITHUB_ACTIONS':'true','GITHUB_EVENT_NAME':'push','GITHUB_REPOSITORY':d.REPO,
             'GITHUB_JOB':'collect-once','GITHUB_WORKSPACE':str(checkout),
             'GITHUB_RUN_ID':'12345','GITHUB_RUN_ATTEMPT':'1','GITHUB_REF':h.BRANCH,
             'GITHUB_WORKFLOW':h.WORKFLOW,'GITHUB_SHA':head,'C5_EXPECTED_SOURCE_SHA':head,
             'C5_APPROVED_ONCE':h.OP,'GITHUB_EVENT_PATH':str(event),'RUNNER_TEMP':str(runner),
             'C5_DRIVER_BLOB':d.git_blob((checkout/d.SELF).read_bytes())}
        with patch.object(d,'ROOT',checkout),patch.object(d,'ARMED',True), \
             patch.object(d,'load_modules',return_value=MODS),patch.dict(d.os.environ,env,clear=True), \
             patch.object(h,'collect') as collect:
            result=d.authorize('collect-once')
            self.assertEqual(len(result[6]),68)
            self.assertEqual(result[-1],head)
            self.assertIs(h.LIVE_ENABLED,False)
            self.deny('ONE_USE_CLAIM_CONSUMED',lambda:d.authorize('collect-once'))
            collect.assert_not_called()

    def test_exclusive_claim(self):
        d.claim(self.root,'123','collect-once')
        self.deny('ONE_USE_CLAIM_CONSUMED',lambda:d.claim(self.root,'123','collect-once'))
        d.claim(self.root,'123','retrieve-once')
        self.assertEqual(len(list(self.root.iterdir())),2)

    def cmd(self,*args):
        return subprocess.run(['git','-C',str(self.root),'-c','user.name=Fixture',
                               '-c','user.email=fixture@example.invalid',
                               '-c','core.hooksPath=/dev/null',*args],
                              check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout

    def setup_git(self):
        self.cmd('init','-q')
        (self.root/'base').write_text('inert\n')
        self.cmd('add','base'); self.cmd('commit','-qm','fixture base')
        parent=self.cmd('rev-parse','HEAD').decode().strip()
        marker=self.root/d.MARKER; marker.parent.mkdir(parents=True)
        marker.write_bytes(d.MARKER_BYTES)
        self.cmd('add',d.MARKER)
        return parent

    def test_real_git_marker_only(self):
        parent=self.setup_git()
        self.cmd('commit','-qm',d.MESSAGE)
        head,actual,msg,marker=d.checkout_identity(self.root)
        self.assertEqual(actual,parent); self.assertNotEqual(head,parent)
        self.assertEqual(msg,d.MESSAGE); self.assertEqual(marker,d.MARKER_BYTES)

    def test_real_git_extra_path_refused(self):
        self.setup_git()
        (self.root/'base').write_text('changed')
        self.cmd('add','base'); self.cmd('commit','-qm',d.MESSAGE)
        self.deny('MARKER_ONLY_DIFF',lambda:d.checkout_identity(self.root))

    def test_real_git_wrong_message_refused(self):
        self.setup_git(); self.cmd('commit','-qm','wrong message')
        self.deny('ACTIVATION_MESSAGE',lambda:d.checkout_identity(self.root))

    def test_real_git_dirty_marker_refused(self):
        self.setup_git(); self.cmd('commit','-qm',d.MESSAGE)
        (self.root/d.MARKER).write_bytes(b'wrong')
        self.deny('MARKER_BYTES',lambda:d.checkout_identity(self.root))

    def settled(self,status=200):
        raw,row=candidate()
        replay=a.Replay({row['url']:wire(raw,status=status)})
        path,sha=a._run_core([row],'fixture-plan',replay.get,self.root,nullcontext,a.HOSTED_SCOPE)
        bundle,record,summary=d.prepare_receipt(path,sha,[row],'fixture-plan',self.root,
                                               '12345','1'*40,MODS)
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_STORED) as z:
            z.writestr('receipts.odin',bundle.read_bytes())
        payload=out.getvalue()
        meta={'id':123,'name':record['artifact_name'],'expired':False,'size_in_bytes':len(payload),
              'digest':'sha256:'+w.sha(payload),'workflow_run':{'id':12345,'head_sha':'1'*40,
                    'head_branch':h.BRANCH.removeprefix('refs/heads/')}}
        return payload,meta,record,[row],summary

    def replay(self,status=200):
        raw,meta,record,rows,expected=self.settled(status)
        result=d.replay_transfer(raw,meta,record,'12345','1'*40,rows,'fixture-plan',
                                 self.root,expected,MODS)
        self.assertEqual(result,expected)
        return result

    def test_hosted_full_receipt(self):
        self.assertEqual(self.replay()['verified_count'],1)

    def test_hosted_refusal_receipt_preserved(self):
        result=self.replay(503)
        self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(result['attempted_count'],1)
        self.assertEqual(result['verified_count'],0)

    def test_verifier_mismatch(self):
        raw,meta,record,rows,expected=self.settled()
        expected['received_bytes']+=1
        self.deny('PRODUCER_VERIFIER_SETTLEMENT',lambda:d.replay_transfer(raw,meta,record,
                  '12345','1'*40,rows,'fixture-plan',self.root,expected,MODS))

    def test_exact_api_retrieval_fixture(self):
        from email.message import Message
        class Response:
            def __init__(self,raw):
                self.raw=io.BytesIO(raw); self.status=200
                self.headers=Message(); self.headers['Content-Length']=str(len(raw))
            def read(self,count): return self.raw.read(count)
            def __enter__(self): return self
            def __exit__(self,*_): self.raw.close()
        raw,meta,record,rows,expected=self.settled()
        class Opener:
            def __init__(self): self.calls=[]
            def open(self,req,timeout):
                self.calls.append((req.full_url,req.get_header('Authorization'),timeout))
                return Response(json.dumps(meta).encode() if len(self.calls)==1 else raw)
        opener=Opener()
        payload,observed=d.download_exact(record,'12345','1'*40,'123',w.sha(raw),
                                          'fixture-token',opener,MODS)
        self.assertEqual(payload,raw); self.assertEqual(observed,meta)
        url='https://api.github.com/repos/'+d.REPO+'/actions/artifacts/123'
        self.assertEqual(opener.calls,[(url,'Bearer fixture-token',15),(url+'/zip','Bearer fixture-token',15)])

    def test_workflow_disarmed(self):
        source=(d.ROOT/d.WORKFLOW_PATH).read_text()
        self.assertEqual(source.count('if: '+chr(36)+'{{ false }}'),3)
        self.assertNotIn(d.MARKER,source.split('permissions:')[0])
        self.assertNotIn('workflow_dispatch:',source)
        self.assertIn('actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02',source)

if __name__=='__main__': unittest.main(verbosity=2)
