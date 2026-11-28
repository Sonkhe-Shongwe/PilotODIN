"""Runtime gate rehearsal with disposable Git and inert HTTP only."""
import copy
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
import wheel_hosted_runtime as rt
import wheel_hosted_policy_v3 as m
import wheel_acquisition_offline as a
import wheel_archive_inspector as w
import wheel_notice_evidence_v2 as n
import wheel_license_policy as p
import wheel_settlement_core as c
from test_wheel_acquisition_offline import candidate,wire

class Tests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.parent=Path(tmp.name)
        self.caps={'body':a.MAX_BYTES,'expanded':w.MAX_TOTAL,'notice':w.MAX_NOTICES,'evidence':n.MAX_EVIDENCE_BATCH}

    def deny(self,reason,fn):
        with self.assertRaisesRegex(w.Blocked,'^'+reason+'$'):fn()

    def git(self,root,*args):
        return subprocess.run(['git','-C',str(root),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                               '-c','core.autocrlf=false','-c','commit.gpgsign=false',*args],
                              check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10).stdout.decode().strip()

    def gate(self):
        root=self.parent/'checkout';root.mkdir();runner=self.parent/'runner';runner.mkdir()
        self.git(root,'init','-q')
        for path,pin in rt.RUNTIME_PINS.items():
            dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(p.pinned_text(rt.ROOT/path,pin))
        for path in (rt.SELF,rt.WORKFLOW):
            dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(b'inert fixture source\n')
        self.git(root,'add','.');self.git(root,'commit','-qm','fixture parent')
        parent=self.git(root,'rev-parse','HEAD');inputs=rt.input_identity()
        (root/rt.MARKER).write_bytes(rt.marker_bytes(inputs))
        self.git(root,'add',rt.MARKER);self.git(root,'commit','-qm',rt.MESSAGE)
        head=self.git(root,'rev-parse','HEAD')
        expected={'parent':parent,'head':head,'driver_blob':rt.git_blob(b'inert fixture source\n'),
                  'workflow_blob':rt.git_blob(b'inert fixture source\n'),'inputs':inputs}
        context={'GITHUB_ACTIONS':'true','GITHUB_EVENT_NAME':'push','GITHUB_REPOSITORY':rt.REPO,
                 'GITHUB_REF':rt.BRANCH,'GITHUB_WORKFLOW':rt.WORKFLOW_NAME,'GITHUB_JOB':'collect-once',
                 'GITHUB_RUN_ATTEMPT':'1','C5_APPROVED_ONCE':rt.OP,'GITHUB_SHA':head,
                 'C5_DRIVER_BLOB':expected['driver_blob'],'C5_WORKFLOW_BLOB':expected['workflow_blob'],
                 'GITHUB_RUN_ID':'12345','GITHUB_WORKSPACE':str(root)}
        payload={'ref':rt.BRANCH,'before':parent,'after':head,'forced':False,'created':False,'deleted':False,
                 'repository':{'full_name':rt.REPO},'head_commit':{'id':head,'message':rt.MESSAGE}}
        event=self.parent/'event.json';event.write_text(json.dumps(payload),encoding='utf-8')
        return runner,root,event,context,expected

    def test_git_gate_and_claim(self):
        args=self.gate()
        claim=rt.fixture_claim(*args,'collect-once')
        self.assertEqual(claim['scope'],m.TRANSFER_SCOPE)
        self.deny('ONE_USE_CLAIM_CONSUMED',lambda:rt.fixture_claim(*args,'collect-once'))
        self.assertEqual(len(list(args[0].iterdir())),1)

    def test_dirty_checkout(self):
        args=self.gate();(args[1]/rt.SELF).write_bytes(b'changed')
        self.deny('DIRTY_CHECKOUT',lambda:rt.fixture_claim(*args,'collect-once'))
        self.assertEqual(list(args[0].iterdir()),[])

    def test_wrong_expected_parent(self):
        args=self.gate();args[4]['parent']='0'*40
        self.deny('GATE_EVENT',lambda:rt.fixture_claim(*args,'collect-once'))
        self.assertEqual(list(args[0].iterdir()),[])

    def test_wrong_workspace(self):
        args=self.gate();args[3]['GITHUB_WORKSPACE']=str(self.parent)
        self.deny('RUNTIME_CONTEXT',lambda:rt.fixture_claim(*args,'collect-once'))

    def test_duplicate_event_keys(self):
        args=self.gate();args[2].write_bytes(b'{"ref":"a","ref":"b"}')
        self.deny('DUPLICATE_JSON_KEY',lambda:rt.fixture_claim(*args,'collect-once'))
        self.assertEqual(list(args[0].iterdir()),[])

    def test_wrong_job_and_attempt(self):
        args=self.gate()
        for key,value in [('GITHUB_JOB','retrieve-once'),('GITHUB_RUN_ATTEMPT','2')]:
            with self.subTest(key=key):
                ctx={**args[3],key:value}
                self.deny('GATE_CONTEXT',lambda:rt.fixture_claim(*args[:3],ctx,args[4],'collect-once'))
        self.assertEqual(list(args[0].iterdir()),[])

    def test_wrong_diff(self):
        args=self.gate();root=args[1]
        (root/'extra').write_bytes(b'new')
        self.git(root,'add','extra');self.git(root,'commit','--amend','--no-edit','-q')
        self.deny('MARKER_ONLY_DIFF',lambda:rt.fixture_claim(*args,'collect-once'))

    def test_pinned_source_drift(self):
        args=self.gate();root=args[1]
        path=next(iter(rt.RUNTIME_PINS))
        self.git(root,'reset','--hard',args[4]['parent'])
        (root/path).write_bytes(b'changed pinned source')
        self.git(root,'add',path);self.git(root,'commit','--amend','--no-edit','-q')
        (root/rt.MARKER).write_bytes(rt.marker_bytes(rt.input_identity()))
        self.git(root,'add',rt.MARKER);self.git(root,'commit','-qm',rt.MESSAGE)
        self.deny('SOURCE_PIN',lambda:rt.observe_checkout(root))

    def test_disarmed_before_mutation(self):
        with patch.object(rt,'observe_checkout') as check,patch.object(rt.http.client,'HTTPSConnection') as conn:
            self.deny('FRESH_APPROVAL_REQUIRED',rt.produce)
            self.deny('FRESH_APPROVAL_REQUIRED',rt.retrieve)
            check.assert_not_called();conn.assert_not_called()
        self.assertEqual(list(self.parent.iterdir()),[])

    def items(self,*builds):
        rows=[];bindings={};responses={}
        for build in builds:
            raw,row=candidate(build=build);rows.append(row)
            bindings[row['filename']]=p.binding(row['filename'],row['metadata_sha256'],'2.4',row['license_files'])
            responses[row['url']]=wire(raw)
        return rows,bindings,responses

    def test_ordered_success(self):
        rows,bindings,responses=self.items(None,2)
        factory=rt.FixtureHTTPS(responses)
        with patch.object(rt.http.client,'HTTPSConnection') as conn:
            path,sha=rt.collect_fixture(rows,'fixture',factory,self.parent,bindings=bindings,caps=self.caps)
            conn.assert_not_called()
        result=m.verify_generation(path,sha,rows,'fixture',bindings=bindings,caps=self.caps)
        self.assertEqual(result['verified_count'],2)
        self.assertEqual(factory.requests,[x['url'] for x in rows])
        self.assertTrue(all(x.closed for x in factory.connections))

    def test_redirect_not_followed(self):
        rows,bindings,responses=self.items(None,2)
        raw,_=candidate();responses[rows[0]['url']]=wire(raw,status=302)
        factory=rt.FixtureHTTPS(responses)
        path,sha=rt.collect_fixture(rows,'fixture',factory,self.parent,bindings=bindings,caps=self.caps)
        result=m.verify_generation(path,sha,rows,'fixture',bindings=bindings,caps=self.caps)
        self.assertEqual(result['verified_count'],0);self.assertEqual(result['attempted_count'],1)
        self.assertEqual(factory.requests,[rows[0]['url']])
        self.assertTrue(all(x.closed for x in factory.connections))

    def test_connection_failure_no_retry(self):
        rows,bindings,responses=self.items(None,2);responses[rows[0]['url']]=None
        factory=rt.FixtureHTTPS(responses)
        path,sha=rt.collect_fixture(rows,'fixture',factory,self.parent,bindings=bindings,caps=self.caps)
        result=m.verify_generation(path,sha,rows,'fixture',bindings=bindings,caps=self.caps)
        self.assertEqual(result['attempted_count'],1)
        self.assertEqual(factory.requests,[rows[0]['url']]);self.assertTrue(factory.connections[0].closed)

    def test_order_violation_no_connection(self):
        rows,_,responses=self.items(None,2)
        factory=rt.FixtureHTTPS(responses);fetch=rt._OrderedFetch(rows,factory)
        self.deny('URL_SCOPE',lambda:fetch.get(rows[1]['url']))
        self.deny('TRANSPORT_STOPPED',lambda:fetch.get(rows[0]['url']))
        self.assertEqual(factory.connections,[])

    def test_arbitrary_factory_refused(self):
        rows,bindings,_=self.items(None)
        self.deny('OFFLINE_FIXTURE_ONLY',lambda:rt.collect_fixture(rows,'fixture',object(),self.parent,
                                                                   bindings=bindings,caps=self.caps))
        self.assertEqual(list(self.parent.iterdir()),[])

    def transfer(self,blocked=False):
        rows,bindings,responses=self.items(None,2)
        if blocked:
            raw,_=candidate();responses[rows[1]['url']]=wire(raw,status=503)
        bundle,record,expected=rt.produce_fixture(rows,'fixture',rt.FixtureHTTPS(responses),self.parent,
                                                   '12345','1'*40,bindings=bindings,caps=self.caps)
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_STORED) as z:z.writestr('receipts.odin',bundle.read_bytes())
        raw=out.getvalue()
        meta={'id':123,'name':record['artifact_name'],'expired':False,'size_in_bytes':len(raw),
              'digest':'sha256:'+w.sha(raw),'workflow_run':{'id':12345,'head_sha':'1'*40,
              'head_branch':rt.BRANCH.removeprefix('refs/heads/')}}
        return raw,meta,record,expected,rows,bindings

    def replay(self,data):
        raw,meta,record,expected,rows,bindings=data
        return rt.retrieve_fixture(raw,meta,record,expected,'12345','1'*40,123,w.sha(raw),
                                   rows,'fixture',self.parent,bindings=bindings,caps=self.caps)

    def test_exact_producer_verifier_success(self):
        data=self.transfer();self.assertEqual(self.replay(data),data[3]);self.assertEqual(data[3]['verified_count'],2)

    def test_exact_producer_verifier_partial(self):
        data=self.transfer(True);observed=self.replay(data)
        self.assertEqual(observed['status'],'BLOCKED');self.assertEqual(observed['verified_count'],1)
        self.assertEqual(observed['last_result']['reason'],'HTTP_STATUS')

    def test_producer_tamper(self):
        data=self.transfer();data[3]['accepted_totals']['notice']+=1
        self.deny('PRODUCER_VERIFIER_SETTLEMENT',lambda:self.replay(data))

if __name__=='__main__':unittest.main(verbosity=2)
