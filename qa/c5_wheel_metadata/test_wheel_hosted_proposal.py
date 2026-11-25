"""Inert hosted adapter and receipt transfer controls; no external service calls."""
from contextlib import contextmanager
import json
from pathlib import Path
import signal
import ssl
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import wheel_hosted_proposal as h
import wheel_acquisition_offline as a
import wheel_archive_inspector as w
import wheel_notice_evidence as n
from test_wheel_acquisition_offline import candidate,wire
from test_wheel_archive_inspector import D


class Connection:
    def __init__(self, raw):
        self.raw=raw
        self.calls=[]
        self.closed=False
    def request(self,*args,**kw):
        self.calls.append((args,kw))
    def getresponse(self):
        import http.client
        r=http.client.HTTPResponse(a._MemorySocket(self.raw))
        r.begin()
        return r
    def close(self):
        self.closed=True


class Tests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.parent=Path(tmp.name)

    def deny(self,reason,fn):
        with self.assertRaisesRegex(w.Blocked,'^'+reason+'$'):
            fn()

    def generation(self,**kw):
        raw,row=candidate(**kw)
        path,sha=a._run([row],'fixture-plan',a.Replay({row['url']:wire(raw)}),self.parent)
        return path,sha,[row]

    def bundle(self,**kw):
        p,sha,rows=self.generation(**kw)
        b,ident=h.export_generation(p,sha,rows,'fixture-plan',self.parent)
        return b,ident,rows

    def replace_bundle(self,b,raw,ident):
        b.write_bytes(raw)
        return {**ident,'bytes':len(raw),'sha256':w.sha(raw)}

    def test_live_gate_before_socket(self):
        with patch.object(h.http.client,'HTTPSConnection') as conn:
            self.deny('FRESH_APPROVAL_REQUIRED',h.collect)
            conn.assert_not_called()

    def test_env_cannot_activate(self):
        with patch.dict(h.os.environ,{'C5_APPROVED_ONCE':h.OP,'GITHUB_ACTIONS':'true'}):
            self.deny('FRESH_APPROVAL_REQUIRED',h.authorize)

    def test_request_tls_exact(self):
        raw,row=candidate()
        conn=Connection(wire(raw))
        seen=[]
        def factory(host,port,**kw):
            seen.append((host,port,kw))
            return conn
        resp=h._request(row,factory)
        self.assertEqual(resp.status,200)
        self.assertEqual(resp.read1(5),raw[:5])
        resp.close()
        self.assertTrue(conn.closed)
        self.assertEqual(seen[0][:2],(a.HOST,443))
        self.assertEqual(seen[0][2]['timeout'],15)
        self.assertTrue(seen[0][2]['context'].check_hostname)
        self.assertEqual(seen[0][2]['context'].verify_mode,ssl.CERT_REQUIRED)
        host,port,path,headers=h.request_parts(row)
        self.assertEqual(conn.calls,[(('GET',path),{'headers':headers})])
        self.assertEqual(headers['Accept-Encoding'],'identity')
        self.assertEqual(headers['Connection'],'close')
        self.assertNotIn('Authorization',headers)

    def test_wrong_url_before_connection(self):
        raw,row=candidate(); row['url']+='?secret=1'
        def factory(*args,**kwargs): self.fail('factory called')
        self.deny('URL_SCOPE',lambda:h._request(row,factory))

    def test_connection_failure_closes(self):
        raw,row=candidate()
        conn=Connection(wire(raw))
        def fail(): raise OSError('inert failure')
        conn.getresponse=fail
        with self.assertRaises(OSError):
            h._request(row,lambda *args,**kwargs:conn)
        self.assertTrue(conn.closed)

    @unittest.skipUnless(hasattr(signal,'setitimer'),'POSIX deadline only')
    def test_absolute_timer_and_restoration(self):
        old=signal.getsignal(signal.SIGALRM)
        with patch.object(a,'REQUEST_TIMEOUT',0.02):
            with self.assertRaisesRegex(w.Blocked,'^REQUEST_DEADLINE$'):
                with h.deadline(): time.sleep(0.2)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))
        self.assertEqual(signal.getsignal(signal.SIGALRM),old)

    @unittest.skipUnless(hasattr(signal,'setitimer'),'POSIX deadline only')
    def test_busy_timer_preserved(self):
        signal.setitimer(signal.ITIMER_REAL,30)
        try:
            self.deny('DEADLINE_BUSY',lambda:self.enter_deadline())
            self.assertGreater(signal.getitimer(signal.ITIMER_REAL)[0],0)
        finally:
            signal.setitimer(signal.ITIMER_REAL,0)

    def enter_deadline(self):
        with h.deadline(): pass

    def test_deadline_refusal_settled(self):
        raw,row=candidate()
        @contextmanager
        def expires():
            raise w.Blocked('REQUEST_DEADLINE')
            yield
        p,sha=a._run_core([row],'fixture-plan',lambda _:self.fail('fetch called'),
                          self.parent,expires,a.HOSTED_SCOPE)
        m=a.verify_generation(p,sha,[row],'fixture-plan',scope=a.HOSTED_SCOPE)
        self.assertEqual(m['status'],'BLOCKED')
        self.assertEqual(json.loads((p/'request-001-result.json').read_bytes())['reason'],'REQUEST_DEADLINE')
        self.deny('MANIFEST_IDENTITY',lambda:a.verify_generation(p,sha,[row],'fixture-plan'))

    def test_bundle_roundtrip(self):
        b,ident,rows=self.bundle(changes={D+'licenses/LICENSE':b'\x00\xff'})
        p,m=h.import_generation(b,ident,rows,'fixture-plan',self.parent)
        self.assertEqual(m['verified_count'],1)
        self.assertFalse(m['production_ready'])
        self.assertEqual({x.name for x in p.iterdir()},
            {'manifest.json','request-001-intent.json','request-001-result.json','wheel-001-evidence.json'})
        self.assertFalse(any(x.suffix=='.whl' for x in p.iterdir()))

    def test_bundle_digest(self):
        b,ident,rows=self.bundle()
        self.deny('BUNDLE_HASH',lambda:h.import_generation(b,{**ident,'sha256':'0'*64},rows,'fixture-plan',self.parent))

    def test_manifest_digest(self):
        b,ident,rows=self.bundle()
        self.deny('MANIFEST_HASH',lambda:h.import_generation(b,{**ident,'manifest_sha256':'0'*64},rows,'fixture-plan',self.parent))

    def test_trailing(self):
        b,ident,rows=self.bundle()
        ident=self.replace_bundle(b,b.read_bytes()+b'x',ident)
        self.deny('BUNDLE_TRAILING',lambda:h.import_generation(b,ident,rows,'fixture-plan',self.parent))

    def test_truncated(self):
        b,ident,rows=self.bundle()
        ident=self.replace_bundle(b,b.read_bytes()[:-1],ident)
        self.deny('BUNDLE_TRUNCATED',lambda:h.import_generation(b,ident,rows,'fixture-plan',self.parent))

    def test_unsafe_name(self):
        b,ident,rows=self.bundle()
        raw=h.MAGIC+struct.pack('>H',3)+h.FRAME.pack(6,1)+b'../bad'+b'x'
        ident=self.replace_bundle(b,raw,ident)
        self.deny('BUNDLE_NAME',lambda:h.import_generation(b,ident,rows,'fixture-plan',self.parent))

    def test_duplicate_name(self):
        b,ident,rows=self.bundle()
        f=h._frame('manifest.json',b'x')
        ident=self.replace_bundle(b,h.MAGIC+struct.pack('>H',3)+f+f+f,ident)
        self.deny('BUNDLE_ORDER',lambda:h.import_generation(b,ident,rows,'fixture-plan',self.parent))

    def test_count_limit(self):
        b,ident,rows=self.bundle()
        ident=self.replace_bundle(b,h.MAGIC+struct.pack('>H',h.MAX_FILES+1),ident)
        self.deny('BUNDLE_COUNT',lambda:h.import_generation(b,ident,rows,'fixture-plan',self.parent))

    def test_export_cap(self):
        p,sha,rows=self.generation()
        with patch.object(h,'MAX_BUNDLE',len(h.MAGIC)+2):
            self.deny('BUNDLE_LIMIT',lambda:h.export_generation(p,sha,rows,'fixture-plan',self.parent))

    def test_import_cap(self):
        b,ident,rows=self.bundle()
        with patch.object(h,'MAX_BUNDLE',ident['bytes']-1):
            self.deny('BUNDLE_IDENTITY',lambda:h.import_generation(b,ident,rows,'fixture-plan',self.parent))

    def test_partial_failure_export(self):
        raw,row=candidate()
        p,sha=a._run([row],'fixture-plan',a.Replay({row['url']:wire(b'',status=503)}),self.parent)
        b,ident=h.export_generation(p,sha,[row],'fixture-plan',self.parent)
        _,m=h.import_generation(b,ident,[row],'fixture-plan',self.parent)
        self.assertEqual(m['status'],'BLOCKED')
        self.assertEqual(m['verified_count'],0)

    def test_capacity_32mib_notice_batch(self):
        # Near exact raw notice ceiling across 32 members; no actual licence data.
        changes={f'demo_pkg/NOTICE-{i:02d}.txt':b'x'*(w.MAX_NOTICE-4)
                 for i in range(32)}
        b,ident,rows=self.bundle(changes=changes)
        self.assertGreater(ident['bytes'],40*1024*1024)
        self.assertLessEqual(ident['bytes'],h.MAX_BUNDLE)
        _,m=h.import_generation(b,ident,rows,'fixture-plan',self.parent)
        self.assertEqual(m['verified_count'],1)


if __name__=='__main__': unittest.main(verbosity=2)
