"""Inert archive and receipt fixtures; no dependency acquisition."""
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
import wheel_archive_inspector as w
import wheel_archive_inspector_v2 as v2
import wheel_notice_evidence_v2 as n
import wheel_acquisition_offline as a
import wheel_license_policy as p
import wheel_diagnostic_v3_offline as old
import wheel_settlement_core as c
import wheel_settlement_fixture as f
from test_wheel_acquisition_offline import candidate,wire
from test_wheel_archive_inspector import D,MD

class Tests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.parent=Path(tmp.name)

    def deny(self,reason,fn):
        with self.assertRaisesRegex(w.Blocked,'^'+reason+'$'): fn()

    def caps(self):
        return {'body':a.MAX_BYTES,'expanded':v2.MAX_TOTAL,'notice':v2.MAX_NOTICES,'evidence':n.MAX_EVIDENCE_BATCH}

    def make(self,build=None,version='2.4',root=False,**kw):
        changes=dict(kw.pop('changes',{}))
        changes[D+'METADATA']=MD.replace(b'Metadata-Version: 2.4',('Metadata-Version: '+version).encode())
        if root: changes.update({D+'licenses/LICENSE':None,D+'LICENSE':b'legacy'})
        raw,row=candidate(build=build,changes=changes,**kw)
        bound=p.binding(row['filename'],row['metadata_sha256'],version,row['license_files'])
        return raw,row,bound

    def setup_rows(self,*items):
        rows=[x[1] for x in items]
        bindings={x[1]['filename']:x[2] for x in items}
        replay=a.Replay({x[1]['url']:wire(x[0]) for x in items})
        return rows,bindings,replay

    def run_items(self,*items,caps=None):
        rows,bindings,replay=self.setup_rows(*items)
        caps=self.caps() if caps is None else caps
        path,sha=f.run_fixture(rows,'fixture-plan',replay,self.parent,bindings=bindings,caps=caps)
        m=f.verify_fixture(path,sha,rows,'fixture-plan',bindings=bindings,caps=caps)
        return path,sha,m,rows,bindings,replay

    def result(self,path,i=1):
        return json.loads((path/f'request-{i:03d}-result.json').read_bytes())

    def mutate_manifest(self,path,change):
        target=path/'manifest.json';m=json.loads(target.read_bytes());change(m)
        raw=n.canonical(m);target.write_bytes(raw);return w.sha(raw)

    def verify(self,path,sha,rows,bindings,caps=None):
        return f.verify_fixture(path,sha,rows,'fixture-plan',bindings=bindings,caps=self.caps() if caps is None else caps)

    def test_pinned_remaining(self):
        rows,bindings,caps=c.remaining_inputs()
        self.assertEqual(len(rows),63);self.assertEqual(len(bindings),63)
        self.assertEqual(rows[0]['name'],'charset-normalizer')
        self.assertEqual(caps,{'body':225397605,'expanded':4294072708,'notice':33549191,'evidence':67097955})
        self.assertEqual(len(p.load_bindings())-len(bindings),5)
        print('C5_POLICY_REMAINING_INPUTS_PASS 63 / five preserved')

    def test_success_and_exact_totals(self):
        path,_,m,rows,bindings,_=self.run_items(self.make())
        raw=(path/'wheel-001-evidence.json').read_bytes()
        r=json.loads(raw)['receipt']
        self.assertEqual(m['accepted_totals'],{'expanded':r['expanded_bytes'],'notice':r['notice_bytes'],'evidence':len(raw)})
        self.assertEqual(m['schema_version'],3)
        self.assertEqual(m['policy_sha256'],w.sha(n.canonical(bindings)))
        self.assertEqual(m['caps'],self.caps())
        self.assertEqual(m['verified_count'],1);self.assertFalse(m['production_ready'])

    def test_differential_compatible_evidence(self):
        raw,row,bound=self.make()
        path,_,_,_,_,_=self.run_items((raw,row,bound))
        prev,_=old.run_fixture([row],'fixture-plan',a.Replay({row['url']:wire(raw)}),self.parent,caps=self.caps())
        self.assertEqual((path/'wheel-001-evidence.json').read_bytes(),(prev/'wheel-001-evidence.json').read_bytes())

    def test_modern_refusal_stops_before_next(self):
        path,_,m,_,_,replay=self.run_items(self.make(root=True),self.make(build=2))
        self.assertEqual(m['verified_count'],0);self.assertEqual(m['attempted_count'],1)
        self.assertEqual(len(replay.requests),1)
        self.assertEqual(self.result(path)['inspection_reason'],'MODERN_LICENCE_LOCATION')
        self.assertEqual(m['accepted_totals'],{'expanded':0,'notice':0,'evidence':0})
        self.assertFalse((path/'wheel-001-evidence.json').exists())

    def test_prior_success_survives_policy_refusal(self):
        path,_,m,_,_,replay=self.run_items(self.make(),self.make(build=2,root=True),self.make(build=3))
        self.assertEqual(m['verified_count'],1);self.assertEqual(m['attempted_count'],2)
        self.assertEqual(len(replay.requests),2)
        self.assertEqual(self.result(path,2)['inspection_reason'],'MODERN_LICENCE_LOCATION')
        self.assertTrue((path/'wheel-001-evidence.json').is_file())
        self.assertFalse((path/'wheel-002-evidence.json').exists())

    def test_legacy_root(self):
        self.assertEqual(self.run_items(self.make(version='2.1',root=True))[2]['verified_count'],1)

    def test_independent_verifier_policy_refusal(self):
        # Manufacture a legacy-v3 success for the wrong modern placement.
        raw,row,bound=self.make(root=True)
        rows,bindings,replay=self.setup_rows((raw,row,bound))
        path,_=old.run_fixture(rows,'fixture-plan',replay,self.parent,caps=self.caps())
        evidence=(path/'wheel-001-evidence.json').read_bytes();r=json.loads(evidence)['receipt']
        def change(m):
            m.update(scope=c.FIXTURE_SCOPE,policy_sha256=w.sha(n.canonical(bindings)),caps=self.caps(),
                     accepted_totals={'expanded':r['expanded_bytes'],'notice':r['notice_bytes'],'evidence':len(evidence)})
        sha=self.mutate_manifest(path,change)
        self.deny('MODERN_LICENCE_LOCATION',lambda:self.verify(path,sha,rows,bindings))

    def test_changed_binding_refused(self):
        path,sha,_,rows,bindings,_=self.run_items(self.make())
        bindings[rows[0]['filename']]['metadata_version']='2.1'
        self.deny('MANIFEST_POLICY_IDENTITY',lambda:self.verify(path,sha,rows,bindings))

    def test_changed_caps_refused(self):
        path,sha,_,rows,bindings,_=self.run_items(self.make())
        caps=self.caps();caps['notice']-=1
        self.deny('MANIFEST_POLICY_IDENTITY',lambda:self.verify(path,sha,rows,bindings,caps))

    def test_bool_caps_refused(self):
        rows,bindings,replay=self.setup_rows(self.make())
        caps=self.caps();caps['notice']=True
        self.deny('RESIDUAL_CAPS',lambda:f.run_fixture(rows,'fixture-plan',replay,self.parent,bindings=bindings,caps=caps))
        self.assertEqual(replay.requests,[]);self.assertEqual(list(self.parent.iterdir()),[])

    def test_bad_binding_before_mutation(self):
        rows,bindings,replay=self.setup_rows(self.make());bindings[rows[0]['filename']]['metadata_sha256']='0'*64
        self.deny('METADATA_POLICY_IDENTITY',lambda:f.run_fixture(rows,'fixture-plan',replay,self.parent,bindings=bindings,caps=self.caps()))
        self.assertEqual(replay.requests,[]);self.assertEqual(list(self.parent.iterdir()),[])

    def test_missing_binding(self):
        rows,bindings,replay=self.setup_rows(self.make())
        self.deny('METADATA_POLICY_IDENTITY',lambda:f.run_fixture(rows,'fixture-plan',replay,self.parent,bindings={},caps=self.caps()))
        self.assertEqual(replay.requests,[])

    def test_body_budget_before_mutation(self):
        rows,bindings,replay=self.setup_rows(self.make());caps=self.caps();caps['body']=rows[0]['bytes']-1
        self.deny('RESIDUAL_BODY_LIMIT',lambda:f.run_fixture(rows,'fixture-plan',replay,self.parent,bindings=bindings,caps=caps))
        self.assertEqual(replay.requests,[]);self.assertEqual(list(self.parent.iterdir()),[])

    def test_expansion_budget(self):
        caps=self.caps();caps['expanded']=1
        path,_,m,_,_,_=self.run_items(self.make(),caps=caps)
        self.assertEqual(m['verified_count'],0)
        self.assertEqual(self.result(path)['inspection_reason'],'BATCH_EXPANSION_LIMIT')

    def test_notice_budget(self):
        caps=self.caps();caps['notice']=1
        path,_,m,_,_,_=self.run_items(self.make(),caps=caps)
        self.assertEqual(m['verified_count'],0)
        self.assertEqual(self.result(path)['inspection_reason'],'BATCH_EXPANSION_LIMIT')

    def test_evidence_budget(self):
        caps=self.caps();caps['evidence']=1
        path,_,m,_,_,_=self.run_items(self.make(),caps=caps)
        self.assertEqual(m['verified_count'],0);self.assertEqual(m['accepted_totals']['evidence'],0)
        self.assertEqual(self.result(path)['inspection_reason'],'EVIDENCE_BATCH_LIMIT')

    def test_evidence_exact_boundary(self):
        raw,row,bound=self.make()
        ledger=c.InspectionLedger(self.caps());doc,_=ledger.inspect(raw,row,bound,'fixture-plan')
        caps=self.caps();caps['evidence']=len(doc)
        self.assertEqual(self.run_items((raw,row,bound),caps=caps)[2]['accepted_totals']['evidence'],len(doc))

    def test_ledger_keeps_reservation_and_stops(self):
        raw,row,bound=self.make(root=True);ledger=c.InspectionLedger(self.caps())
        self.deny('MODERN_LICENCE_LOCATION',lambda:ledger.inspect(raw,row,bound,'fixture-plan'))
        self.assertGreater(ledger.budget.expanded,0)
        self.assertEqual(ledger.accepted,{'expanded':0,'notice':0,'evidence':0})
        self.deny('BATCH_STOPPED',lambda:ledger.inspect(raw,row,bound,'fixture-plan'))

    def test_tampered_accepted_totals(self):
        path,_,_,rows,bindings,_=self.run_items(self.make())
        sha=self.mutate_manifest(path,lambda m:m['accepted_totals'].update(notice=0))
        self.deny('MANIFEST_RESOURCE_TOTALS',lambda:self.verify(path,sha,rows,bindings))

    def test_unknown_reason_sanitized(self):
        with patch.object(c.InspectionLedger,'inspect',side_effect=w.Blocked('secret/path')):
            path,_,_,_,_,_=self.run_items(self.make())
        self.assertEqual(self.result(path)['inspection_reason'],'UNCLASSIFIED_INSPECTION_REFUSAL')
        self.assertNotIn('secret',json.dumps(self.result(path)))

    def test_explicit_directory(self):
        i=zipfile.ZipInfo('demo_pkg/');i.create_system=3;i.external_attr=((stat.S_IFDIR|0o755)<<16)|0x10
        path,_,m,_,_,_=self.run_items(self.make(extras=[(i,b'')]))
        self.assertEqual(m['verified_count'],1)
        self.assertEqual(json.loads((path/'wheel-001-evidence.json').read_bytes())['receipt']['directory_entries'],1)

    def test_forbidden_directory_payload(self):
        i=zipfile.ZipInfo('demo_pkg/');i.create_system=3;i.external_attr=((stat.S_IFDIR|0o755)<<16)|0x10
        path,_,m,_,_,_=self.run_items(self.make(extras=[(i,b'x')]))
        self.assertEqual(m['verified_count'],0)
        self.assertEqual(self.result(path)['inspection_reason'],'ZIP_DIRECTORY_PAYLOAD')

    def test_historical_scope_not_accepted(self):
        raw,row,bound=self.make();rows,bindings,replay=self.setup_rows((raw,row,bound))
        path,sha=old.run_fixture(rows,'fixture-plan',replay,self.parent,caps=self.caps())
        self.deny('MANIFEST_IDENTITY',lambda:self.verify(path,sha,rows,bindings))

    def test_non_fixture_denied(self):
        self.deny('OFFLINE_FIXTURE_ONLY',lambda:f.run_fixture([],'fixture-plan',object(),self.parent,bindings={},caps=self.caps()))
        self.assertEqual(list(self.parent.iterdir()),[])

    def test_hosted_scope_denied(self):
        rows,bindings,_=self.setup_rows(self.make())
        self.deny('SCOPE',lambda:c.prepare(rows,'fixture-plan',bindings,self.caps(),'HOSTED_POLICY_V3_CANDIDATE_ONLY'))

if __name__=='__main__':unittest.main(verbosity=2)
