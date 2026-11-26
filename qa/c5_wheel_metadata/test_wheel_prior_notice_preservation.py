"""Generated inert fixtures; no artifact retrieval or notice publication."""
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from contextlib import nullcontext

sys.path.insert(0,str(Path(__file__).resolve().parent))
import wheel_prior_notice_preservation as p
from test_wheel_acquisition_offline import candidate,wire

q,d,mods,historic,prior,rows=p.modules()
a,w,h,n,g,t=mods

class Tests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
    def fixture(self):
        raw,row=candidate();raw2,row2=candidate(build=2)
        plan='fixture-plan';rr=[row,row2]
        replay=a.Replay({row['url']:wire(raw),row2['url']:wire(raw2,status=503)})
        dest,sha=a._run_core(rr,plan,replay.get,self.root,nullcontext,a.HOSTED_SCOPE)
        manifest=a.verify_generation(dest,sha,rr,plan,scope=a.HOSTED_SCOPE)
        bundle,ident=h.export_generation(dest,sha,rr,plan,self.root,scope=a.HOSTED_SCOPE)
        record=g.identity('12345','1'*40,ident)
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_STORED) as z:
            z.writestr('receipts.odin',bundle.read_bytes())
        data=out.getvalue()
        meta={'id':123,'name':record['artifact_name'],'expired':False,'size_in_bytes':len(data),
              'digest':'sha256:'+w.sha(data),'workflow_run':{'id':12345,'head_sha':'1'*40,
              'head_branch':h.BRANCH.removeprefix('refs/heads/')}}
        entries=q.inspect_zip(data,meta,record,'12345','1'*40,rr,plan,d.summary(manifest),self.root,mods)
        dest,m=g.replay_artifact(data,meta,record,'12345','1'*40,rr,plan,self.root,scope=a.HOSTED_SCOPE)
        documents=p.collect_documents(dest,m,rr[:1],entries[:1],plan,mods)
        return documents,rr[:1],entries[:1],plan
    def test_historical_pins(self):
        self.assertEqual(sum(x['evidence_bytes'] for x in prior['records'][:5]),p.EVIDENCE_BYTES)
        self.assertEqual(sum(x['inspection_receipt']['notice_bytes'] for x in prior['records'][:5]),p.NOTICE_BYTES)
    def test_roundtrip(self):
        docs,rr,entries,plan=self.fixture()
        self.assertEqual(p.verify_documents(docs,rr,entries,plan,mods),
                         (entries[0]['evidence_bytes'],entries[0]['inspection_receipt']['notice_bytes']))
    def test_tamper(self):
        docs,rr,entries,plan=self.fixture()
        docs[0]['evidence_base64']='A'+docs[0]['evidence_base64'][1:]
        with self.assertRaises((ValueError,w.Blocked)):p.verify_documents(docs,rr,entries,plan,mods)
    def test_missing_or_extra(self):
        docs,rr,entries,plan=self.fixture()
        for x in ([],docs+docs):
            with self.assertRaisesRegex(ValueError,'DOCUMENT_COUNT'):p.verify_documents(x,rr,entries,plan,mods)
    def test_wrong_identity(self):
        docs,rr,entries,plan=self.fixture();docs[0]['filename']='other.whl'
        with self.assertRaisesRegex(ValueError,'DOCUMENT_IDENTITY'):p.verify_documents(docs,rr,entries,plan,mods)
    def test_disabled(self):
        with patch.object(p,'modules') as m,patch.object(q,'download') as fetch:
            with self.assertRaisesRegex(ValueError,'FRESH_APPROVAL_REQUIRED'):p.retrieve()
            m.assert_not_called();fetch.assert_not_called()

if __name__=='__main__':unittest.main(verbosity=2)
