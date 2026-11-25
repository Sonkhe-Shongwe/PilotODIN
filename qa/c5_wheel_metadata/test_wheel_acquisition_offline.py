"""Generated inert responses, no network or real wheel bytes."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import wheel_acquisition_offline as a
import wheel_archive_inspector as w
import wheel_notice_evidence as n
from test_wheel_archive_inspector import fixture, D


def candidate(build=None, **kw):
    raw,row = fixture(**kw)
    if build is not None:
        row['filename'] = f'demo_pkg-1.2-{build}-py3-none-any.whl'
    row['url'] = ('https://files.pythonhosted.org/packages/aa/bb/'+'c'*60+'/'+row['filename'])
    return raw,row


def wire(body, *, status=200, headers=None):
    if headers is None:
        headers = [('Content-Type','application/octet-stream'),('Content-Length',str(len(body)))]
    return (f'HTTP/1.1 {status} Fixture\r\n'+''.join(f'{k}: {v}\r\n' for k,v in headers)
            +'\r\n').encode('ascii')+body


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name)

    def deny(self, reason, f):
        with self.assertRaisesRegex(w.Blocked,'^'+reason+'$'):
            f()

    def run_one(self, response=None, **kw):
        raw,row = candidate(**kw)
        replay = a.Replay({row['url']:wire(raw) if response is None else response})
        path,sha = a._run([row],'fixture-plan',replay,self.parent)
        m = a.verify_generation(path,sha,[row],'fixture-plan')
        return path,sha,m,row,replay

    def refuse_response(self, raw, row, response, reason, count=0):
        replay = a.Replay({row['url']:response})
        path,sha = a._run([row],'fixture-plan',replay,self.parent)
        m = a.verify_generation(path,sha,[row],'fixture-plan')
        self.assertEqual(m['status'],'BLOCKED')
        self.assertEqual(m['verified_count'],0)
        self.assertEqual(m['received_bytes'],count)
        self.assertEqual(len(replay.requests),1)
        result=json.loads((path/'request-001-result.json').read_bytes())
        self.assertEqual(result['reason'],reason)
        self.assertEqual(result['status'],'REFUSED')
        self.assertEqual(result['evidence'],None)
        self.assertFalse((path/'wheel-001-evidence.json').exists())

    def test_pinned_plan(self):
        self.assertEqual(a.review_pinned_plan(),{'scope':a.SCOPE,'plan_blob':n.PLAN_BLOB,
            'requests':68,'expected_bytes':225699980,'live_enabled':False})

    def test_live_disabled(self):
        self.deny('FRESH_APPROVAL_REQUIRED',a.live_connection)

    def test_fake_adapter_denied(self):
        _,row=candidate()
        self.deny('OFFLINE_FIXTURE_ONLY',lambda:a._run([row],'fixture-plan',object(),self.parent))
        self.assertEqual(list(self.parent.iterdir()),[])

    def test_success_and_notice_replay(self):
        path,sha,m,row,replay=self.run_one(changes={D+'licenses/LICENSE':b'\x00\xff'})
        self.assertEqual(m['status'],'CANDIDATE_EVIDENCE_RECORDED')
        self.assertEqual(m['received_bytes'],row['bytes'])
        self.assertEqual(m['verified_count'],1)
        self.assertEqual(len(replay.requests),1)
        self.assertEqual(replay.requests[0],{'method':'GET','url':row['url'],'host':a.HOST,
            'timeout':15,'accept_encoding':'identity'})
        self.assertFalse(m['production_ready'])
        self.assertFalse(m['license_reviewed'])
        self.assertEqual({x.name for x in path.iterdir()},{'request-001-intent.json',
            'wheel-001-evidence.json','request-001-result.json','manifest.json'})

    def test_two_wheels(self):
        x,r=candidate(); y,s=candidate(1)
        replay=a.Replay({r['url']:wire(x),s['url']:wire(y)})
        path,sha=a._run([r,s],'fixture-plan',replay,self.parent)
        m=a.verify_generation(path,sha,[r,s],'fixture-plan')
        self.assertEqual(m['verified_count'],2)
        self.assertEqual(m['received_bytes'],len(x)+len(y))

    def test_stop_no_retry(self):
        x,r=candidate(); y,s=candidate(1)
        replay=a.Replay({r['url']:wire(x,status=302),s['url']:wire(y)})
        path,sha=a._run([r,s],'fixture-plan',replay,self.parent)
        m=a.verify_generation(path,sha,[r,s],'fixture-plan')
        self.assertEqual(m['missing'],[r['filename'],s['filename']])
        self.assertEqual(len(replay.requests),1)
        self.assertFalse((path/'request-002-intent.json').exists())

    def test_partial_success(self):
        x,r=candidate(); y,s=candidate(1)
        replay=a.Replay({r['url']:wire(x),s['url']:wire(y,status=503)})
        path,sha=a._run([r,s],'fixture-plan',replay,self.parent)
        m=a.verify_generation(path,sha,[r,s],'fixture-plan')
        self.assertEqual(m['verified_count'],1)
        self.assertEqual(m['missing'],[s['filename']])
        self.assertEqual(m['status'],'BLOCKED')

    def test_origin_and_query(self):
        raw,row=candidate()
        for url in [row['url']+'?x=1',row['url']+'#x',row['url'].replace(a.HOST,'evil.invalid'),
                    row['url'].replace('https:','http:'),row['url'].replace(a.HOST,a.HOST+':443')]:
            with self.subTest(url=url):
                self.deny('URL_SCOPE',lambda:a.plan_rows([{**row,'url':url}]))

    def test_duplicate_plan(self):
        _,row=candidate()
        self.deny('DUPLICATE_PLAN',lambda:a.plan_rows([row,row]))

    def test_request_limit(self):
        _,row=candidate()
        self.deny('REQUEST_COUNT',lambda:a.plan_rows([row]*69))

    def test_byte_budget(self):
        _,row=candidate()
        with patch.object(a,'MAX_BYTES',1):
            self.deny('TOTAL_BUDGET',lambda:a.plan_rows([row]))

    def test_redirect_refused(self):
        raw,row=candidate()
        self.refuse_response(raw,row,wire(b'',status=302,
            headers=[('Location','https://example.invalid/wheel')]),'HTTP_STATUS')

    def test_content_type(self):
        raw,row=candidate()
        self.refuse_response(raw,row,wire(raw,headers=[('Content-Type','text/html'),
            ('Content-Length',str(len(raw)))]),'CONTENT_TYPE')

    def test_content_encoding(self):
        raw,row=candidate()
        self.refuse_response(raw,row,wire(raw,headers=[('Content-Type','application/zip'),
            ('Content-Encoding','gzip'),('Content-Length',str(len(raw)))]),'CONTENT_ENCODING')

    def test_chunked_refused(self):
        raw,row=candidate()
        self.refuse_response(raw,row,wire(raw,headers=[('Content-Type','application/zip'),
            ('Transfer-Encoding','chunked')]),'FRAMING')

    def test_duplicate_length(self):
        raw,row=candidate()
        self.refuse_response(raw,row,wire(raw,headers=[('Content-Type','application/zip'),
            ('Content-Length',str(len(raw))),('Content-Length',str(len(raw)))]),'DUPLICATE_HEADER')

    def test_missing_length(self):
        raw,row=candidate()
        self.refuse_response(raw,row,wire(raw,headers=[('Content-Type','application/zip')]),'BODY_LENGTH')

    def test_wrong_length(self):
        raw,row=candidate()
        self.refuse_response(raw,row,wire(raw,headers=[('Content-Type','application/zip'),
            ('Content-Length',str(len(raw)+1))]),'BODY_LENGTH')

    def test_short_body(self):
        raw,row=candidate()
        self.refuse_response(raw,row,wire(raw[:-1],headers=[('Content-Type','application/zip'),
            ('Content-Length',str(len(raw)))]),'INCOMPLETE_BODY',len(raw)-1)

    def test_wrong_digest(self):
        raw,row=candidate(); bad=raw[:-1]+bytes([raw[-1]^1])
        self.refuse_response(raw,row,wire(bad),'BODY_HASH',len(raw))

    def test_transport_failure(self):
        raw,row=candidate()
        self.refuse_response(raw,row,None,'TRANSPORT_ERROR')

    def test_inspection_failure(self):
        raw,row=candidate(changes={D+'licenses/LICENSE':None})
        self.refuse_response(raw,row,wire(raw),'INSPECTION_REFUSED',len(raw))

    def test_write_ahead(self):
        raw,row=candidate()
        replay=a.Replay({row['url']:wire(raw)})
        real=replay.get
        def witness(url):
            dirs=list(self.parent.iterdir())
            self.assertEqual(len(dirs),1)
            self.assertEqual(json.loads((dirs[0]/'request-001-intent.json').read_bytes()),
                             a.request_intent(row,1))
            self.assertFalse((dirs[0]/'manifest.json').exists())
            return real(url)
        replay.get=witness
        a._run([row],'fixture-plan',replay,self.parent)

    def test_unsettled_after_persistence_failure(self):
        raw,row=candidate()
        real=a._Generation.put
        def fail(store,name,data):
            if name.endswith('-result.json'):
                raise OSError('inert disk failure')
            return real(store,name,data)
        with patch.object(a._Generation,'put',fail):
            with self.assertRaises(OSError):
                a._run([row],'fixture-plan',a.Replay({row['url']:wire(raw)}),self.parent)
        p=next(self.parent.iterdir())
        self.assertTrue((p/'request-001-intent.json').exists())
        self.assertTrue((p/'wheel-001-evidence.json').exists())
        self.deny('UNSETTLED_GENERATION',lambda:a.verify_generation(p,'0'*64,[row],'fixture-plan'))

    def test_exclusive_no_overwrite(self):
        g=a._Generation(self.parent)
        name='request-001-intent.json'
        g.put(name,b'one')
        with self.assertRaises(FileExistsError):
            g.put(name,b'two')
        self.assertEqual((g.path/name).read_bytes(),b'one')

    def test_manifest_hash(self):
        p,sha,m,row,_=self.run_one()
        self.deny('MANIFEST_HASH',lambda:a.verify_generation(p,'0'*64,[row],'fixture-plan'))

    def test_wrong_plan(self):
        p,sha,m,row,_=self.run_one()
        self.deny('MANIFEST_IDENTITY',lambda:a.verify_generation(p,sha,[row],'other'))

    def test_tamper_evidence(self):
        p,sha,m,row,_=self.run_one()
        f=p/'wheel-001-evidence.json'; f.write_bytes(f.read_bytes()+b'x')
        self.deny('RECEIPT_HASH',lambda:a.verify_generation(p,sha,[row],'fixture-plan'))

    def test_unexpected_file(self):
        p,sha,m,row,_=self.run_one()
        (p/'extra').write_bytes(b'x')
        self.deny('GENERATION_INVENTORY',lambda:a.verify_generation(p,sha,[row],'fixture-plan'))

    def test_missing_file(self):
        p,sha,m,row,_=self.run_one()
        (p/'request-001-result.json').unlink()
        self.deny('GENERATION_INVENTORY',lambda:a.verify_generation(p,sha,[row],'fixture-plan'))

    def test_false_clearance(self):
        p,sha,m,row,_=self.run_one()
        m['license_reviewed']=True
        raw=n.canonical(m); (p/'manifest.json').write_bytes(raw)
        self.deny('MANIFEST_IDENTITY',lambda:a.verify_generation(p,w.sha(raw),[row],'fixture-plan'))


if __name__ == '__main__': unittest.main(verbosity=2)
