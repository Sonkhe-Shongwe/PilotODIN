"""Synthetic offline-staging tests only; no pip, native library or browser invocation."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from qa.c5_managed_dev import python_stage as p, validation_witnesses as w, profile_operations as o


def plan():
    return w.read_plan((Path(__file__).parent/'pdfium_use_candidate_20261127.json').read_bytes())


class PythonStageTest(unittest.TestCase):
    def test_lock_graph(self):
        for profile in plan()['profiles']:
            profile = copy.deepcopy(profile)
            raw = ('--no-index\n--only-binary=:all:\n--require-hashes\n\n'+''.join(
                r['name']+('[standard]' if r['name']=='uvicorn' else '')+'=='+r['version']+' --hash=sha256:'+r['sha256']+'\n'
                for r in profile['wheels'])).encode()
            profile['wheel_lock_blob'] = w.blob(raw)
            self.assertEqual(p.check_lock(raw.replace(b'\n',b'\r\n'),profile),raw)
            bad = raw.replace(b'--no-index',b'--index-url https://example.invalid')
            profile['wheel_lock_blob'] = w.blob(bad)
            with self.assertRaisesRegex(ValueError,'LOCK_FLAGS'):
                p.check_lock(bad,profile)

    def test_resolution(self):
        rows = plan()['profiles'][0]['wheels'][:2]
        with tempfile.TemporaryDirectory() as d:
            house = Path(d)
            doc = {'install':[{'metadata':{'name':r['name'],'version':r['version']},
                    'download_info':{'url':(house/r['filename']).as_uri(),'archive_info':{'hashes':{'sha256':r['sha256']}}},
                    'is_direct':False} for r in rows]}
            p.validate_resolution(doc,rows,house)
            for bad in ({'install':doc['install'][:1]}, {'install':doc['install']*2},
                        {'install':[dict(doc['install'][0],is_direct=True),doc['install'][1]]}):
                with self.assertRaises(ValueError):
                    p.validate_resolution(bad,rows,house)

    def test_inventory(self):
        rows = plan()['profiles'][0]['wheels']
        pin = 'a'*64
        observed = [[r['name'],r['version'],r['metadata_sha256']] for r in rows]+[['pip','26.3',pin]]
        p.validate_inventory(observed,rows,pin)
        for bad in (observed[:-1],observed+[observed[0]],observed+[['other','1',pin]]):
            with self.assertRaises(ValueError):
                p.validate_inventory(bad,rows,pin)

    def test_stream_above_32_mib(self):
        size = 33*1024**2
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'generated.bin'
            chunk = b'\0'*65536
            h = hashlib.sha256()
            with path.open('wb') as f:
                for _ in range(size//len(chunk)):
                    f.write(chunk); h.update(chunk)
            row = {'bytes':size,'sha256':h.hexdigest()}
            self.assertEqual(p.file_digest(path,row),row['sha256'])
            with self.assertRaisesRegex(ValueError,'WHEEL_HASH'):
                p.file_digest(path,dict(row,sha256='0'*64))

    def test_commands_offline(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            args = p.pip_arguments(root/'python',root/'wheels',root/'lock',root/'report')
            for key in ('dry_run','install'):
                self.assertTrue({'--no-index','--require-hashes','--only-binary=:all:','--no-cache-dir'} <= set(args[key]))
            self.assertIn('--ignore-installed',args['dry_run'])
            self.assertNotIn('--ignore-installed',args['install'])

    def test_disarmed(self):
        with self.assertRaisesRegex(ValueError,'PYTHON_STAGE_DISARMED'):
            p.require_live()
        with self.assertRaisesRegex(ValueError,'PROFILE_ADAPTER_DISARMED'):
            o.run_profile(None,None,None,None,None,None)
        with self.assertRaisesRegex(ValueError,'DISPOSITION_UNRESOLVED'):
            o.disposition(b'{}',None,None,None,None)
