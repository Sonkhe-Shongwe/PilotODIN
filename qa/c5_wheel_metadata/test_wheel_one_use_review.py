"""Synthetic event, pinned source and receipt artifact replay; no upload/network."""
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
import wheel_one_use_review as g
import wheel_hosted_proposal as h
import wheel_acquisition_offline as a
import wheel_archive_inspector as w
import wheel_notice_evidence as n
from test_wheel_acquisition_offline import candidate, wire

HEAD='1'*40
PARENT='2'*40
RUN='12345'


class Tests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup); self.parent=Path(t.name)
    def deny(self,reason,fn):
        with self.assertRaisesRegex(w.Blocked,'^'+reason+'$'): fn()
    def activation(self):
        e={'ref':h.BRANCH,'before':PARENT,'after':HEAD,'forced':False,'created':False,'deleted':False}
        env={'GITHUB_ACTIONS':'true','GITHUB_EVENT_NAME':'push','GITHUB_REF':h.BRANCH,
             'GITHUB_WORKFLOW':h.WORKFLOW,'GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':HEAD,
             'C5_EXPECTED_SOURCE_SHA':HEAD,'C5_APPROVED_ONCE':h.OP,'GITHUB_RUN_ID':RUN}
        return e,env,{'head':HEAD,'parent':PARENT,'changes':[('A',g.MARKER_PATH)],
                     'message':g.MESSAGE,'marker':h.MARKER_BYTES}
    def test_pins(self):
        self.assertEqual(g.verify_pins()['requests'],68)
    def test_disabled(self):
        with patch.object(h,'collect') as collect:
            self.deny('FRESH_APPROVAL_REQUIRED',g.collect_once)
            collect.assert_not_called()
    def test_even_flag_alone_denied(self):
        with patch.object(g,'ENABLED',True):
            self.deny('ACTIVATION_CONTRACT_NOT_ARMED',g.collect_once)
    def test_exact_activation_fixture(self):
        e,v,k=self.activation(); self.assertTrue(g.activation_contract(e,v,**k))
    def test_rerun(self):
        e,v,k=self.activation(); v['GITHUB_RUN_ATTEMPT']='2'
        self.deny('ACTIVATION_CONTEXT',lambda:g.activation_contract(e,v,**k))
    def test_wrong_branch(self):
        e,v,k=self.activation(); v['GITHUB_REF']='refs/heads/main'
        self.deny('ACTIVATION_CONTEXT',lambda:g.activation_contract(e,v,**k))
    def test_wrong_parent(self):
        e,v,k=self.activation(); e['before']='3'*40
        self.deny('ACTIVATION_EVENT',lambda:g.activation_contract(e,v,**k))
    def test_force(self):
        e,v,k=self.activation(); e['forced']=True
        self.deny('ACTIVATION_EVENT',lambda:g.activation_contract(e,v,**k))
    def test_extra_path(self):
        e,v,k=self.activation(); k['changes'].append(('M','backend/main.py'))
        self.deny('ACTIVATION_SCOPE',lambda:g.activation_contract(e,v,**k))
    def test_modified_marker(self):
        e,v,k=self.activation(); k['changes']=[('M',g.MARKER_PATH)]
        self.deny('ACTIVATION_SCOPE',lambda:g.activation_contract(e,v,**k))
    def test_marker_bytes(self):
        e,v,k=self.activation(); k['marker']+=b'x'
        self.deny('ACTIVATION_SCOPE',lambda:g.activation_contract(e,v,**k))
    def test_exact_message(self):
        e,v,k=self.activation(); k['message']+=' retry'
        self.deny('ACTIVATION_SCOPE',lambda:g.activation_contract(e,v,**k))

    def bundle(self, status=200):
        raw,row=candidate()
        p,sha=a._run([row],'fixture-plan',a.Replay({row['url']:wire(raw,status=status)}),self.parent)
        bundle,ident=h.export_generation(p,sha,[row],'fixture-plan',self.parent)
        return bundle.read_bytes(),g.identity(RUN,HEAD,ident),[row]
    def zip_bytes(self, entries):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for name,data in entries: z.writestr(name,data)
        return out.getvalue()
    def meta(self,raw,record):
        return {'id':123,'name':record['artifact_name'],'expired':False,'size_in_bytes':len(raw),
                'digest':'sha256:'+w.sha(raw),'workflow_run':{'id':int(RUN),'head_sha':HEAD,
                    'head_branch':h.BRANCH.removeprefix('refs/heads/')}}
    def replay(self,raw,record,rows,meta=None):
        return g.replay_artifact(raw,self.meta(raw,record) if meta is None else meta,
                                record,RUN,HEAD,rows,'fixture-plan',self.parent,scope=a.SCOPE)
    def test_success_artifact(self):
        data,record,rows=self.bundle()
        p,m=self.replay(self.zip_bytes([('receipts.odin',data)]),record,rows)
        self.assertEqual(m['verified_count'],1)
        self.assertFalse(m['production_ready'])
        self.assertEqual({x.name for x in p.iterdir()},
            {'manifest.json','request-001-intent.json','request-001-result.json','wheel-001-evidence.json'})
    def test_failed_artifact(self):
        data,record,rows=self.bundle(503)
        _,m=self.replay(self.zip_bytes([('receipts.odin',data)]),record,rows)
        self.assertEqual(m['status'],'BLOCKED')
    def test_outer_digest(self):
        data,record,rows=self.bundle(); raw=self.zip_bytes([('receipts.odin',data)])
        meta=self.meta(raw,record); meta['digest']='sha256:'+'0'*64
        self.deny('ARTIFACT_HASH',lambda:self.replay(raw,record,rows,meta))
    def test_wrong_run(self):
        data,record,rows=self.bundle(); raw=self.zip_bytes([('receipts.odin',data)])
        meta=self.meta(raw,record); meta['workflow_run']['id']=999
        self.deny('ARTIFACT_RUN',lambda:self.replay(raw,record,rows,meta))
    def test_wrong_source(self):
        data,record,rows=self.bundle(); raw=self.zip_bytes([('receipts.odin',data)])
        meta=self.meta(raw,record); meta['workflow_run']['head_sha']='3'*40
        self.deny('ARTIFACT_RUN',lambda:self.replay(raw,record,rows,meta))
    def test_expired(self):
        data,record,rows=self.bundle(); raw=self.zip_bytes([('receipts.odin',data)])
        meta=self.meta(raw,record); meta['expired']=True
        self.deny('ARTIFACT_IDENTITY',lambda:self.replay(raw,record,rows,meta))
    def test_wrong_record(self):
        data,record,rows=self.bundle(); raw=self.zip_bytes([('receipts.odin',data)])
        record['source_sha']='3'*40
        self.deny('RECEIPT_CONTEXT',lambda:self.replay(raw,record,rows))
    def test_missing_digest(self):
        data,record,rows=self.bundle(); raw=self.zip_bytes([('receipts.odin',data)])
        meta=self.meta(raw,record); meta.pop('digest')
        self.deny('ARTIFACT_DIGEST',lambda:self.replay(raw,record,rows,meta))
    def test_extra_member(self):
        data,record,rows=self.bundle(); raw=self.zip_bytes([('receipts.odin',data),('extra.whl',b'x')])
        self.deny('ARTIFACT_INVENTORY',lambda:self.replay(raw,record,rows))
    def test_traversal(self):
        data,record,rows=self.bundle(); raw=self.zip_bytes([('../receipts.odin',data)])
        self.deny('ARTIFACT_MEMBER',lambda:self.replay(raw,record,rows))
    def test_symlink(self):
        data,record,rows=self.bundle(); info=zipfile.ZipInfo('receipts.odin')
        info.create_system=3; info.external_attr=(stat.S_IFLNK|0o777)<<16
        raw=self.zip_bytes([(info,data)])
        self.deny('ARTIFACT_MEMBER',lambda:self.replay(raw,record,rows))
    def test_inner_digest(self):
        data,record,rows=self.bundle(); bad=data[:-1]+bytes([data[-1]^1])
        self.deny('BUNDLE_HASH',lambda:self.replay(self.zip_bytes([('receipts.odin',bad)]),record,rows))
    def test_size(self):
        data,record,rows=self.bundle()
        self.deny('ARTIFACT_MEMBER_SIZE',lambda:self.replay(self.zip_bytes([('receipts.odin',data+b'x')]),record,rows))
    def test_invalid_zip(self):
        _,record,rows=self.bundle()
        self.deny('ARTIFACT_ZIP_REFUSED',lambda:self.replay(b'not zip',record,rows))
    def test_workflow_disarmed(self):
        s=(n.ROOT/'.github/workflows/c5-wheel-hosted-one-use.yml').read_text()
        self.assertIn('    if: \${{ false }}',s)
        self.assertIn('actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02',s)
        self.assertNotIn('workflow_dispatch:',s)
        self.assertNotIn('APPROVAL_WHEEL_HOSTED_20261126.txt',s.split('permissions:')[0])
        self.assertEqual(s.count('uses: actions/upload-artifact@'),1)


if __name__=='__main__': unittest.main(verbosity=2)
