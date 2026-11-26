"""Generated inert ZIP fixtures and adversarial candidate-only tests."""
import base64
import csv
import hashlib
import io
import json
import stat
import struct
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wheel_exact_path_candidate as c
import wheel_archive_inspector_v2 as v2
import wheel_archive_inspector as v1
import wheel_notice_evidence_v2 as n
import wheel_license_policy as p

D = 'demo_pkg-1.2.dist-info/'
TARGET = 'scipy/io/tests/data/Transparent Busy.ani'
MD = b'Metadata-Version: 2.4\nName: demo-pkg\nVersion: 1.2\nRequires-Python: >=3.11\nLicense-Expression: MIT\nLicense-File: LICENSE\n\n'
WH = b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n'

def fixture(method=0, changes=None, record_edit=None, extras=()):
    members={'demo_pkg/__init__.py':b'# inert\n',D+'METADATA':MD,D+'WHEEL':WH,
             D+'licenses/LICENSE':b'Synthetic notice only\n','demo_pkg.libs/test.dll':b'inert not executable',
             TARGET:b'generated inert fixture\n'}
    for path,data in (changes or {}).items():
        if data is None: members.pop(path)
        else: members[path]=data
    rows=[[path,'sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('='),str(len(data))]
          for path,data in members.items()]
    rows.append([D+'RECORD','',''])
    if record_edit: record_edit(rows)
    buf=io.StringIO(newline='');csv.writer(buf,lineterminator='\n').writerows(rows)
    members[D+'RECORD']=buf.getvalue().encode('utf-8')
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        for path,data in members.items():
            i=zipfile.ZipInfo(path,(2020,1,1,0,0,0));i.create_system=3;i.external_attr=(stat.S_IFREG|0o644)<<16
            z.writestr(i,data,compress_type=method,compresslevel=0)
        for i,data in extras: z.writestr(i,data)
    raw=out.getvalue()
    return raw,{'filename':'demo_pkg-1.2-py3-none-any.whl','name':'demo-pkg','version':'1.2',
                'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
                'metadata_sha256':hashlib.sha256(members[D+'METADATA']).hexdigest(),
                'license_files':['LICENSE'],'license_expression':'MIT','requires_python':'>=3.11'}

def git_blob(path):
    root=Path(__file__).resolve().parents[2]
    return subprocess.check_output(['git','-C',str(root),'show','HEAD:'+path])

def source_sha():
    return hashlib.sha256(git_blob('qa/c5_wheel_metadata/wheel_exact_path_candidate.py')).hexdigest()

class Tests(unittest.TestCase):
    def deny(self, reason, raw, expected):
        with self.assertRaisesRegex(c.Blocked,'^'+reason+'$'):
            c._FixtureBudget().inspect(raw,expected)

    def test_exact_stored_and_deflate(self):
        for method in (0,8):
            with self.subTest(method=method):
                raw,expected=fixture(method)
                for historical in (v1,v2):
                    with self.assertRaisesRegex(historical.Blocked,'^UNSAFE_PATH$'):
                        historical.InspectionBudget().inspect(raw,expected)
                receipt=c.inspect_fixture(raw)
                doc=c.verify_fixture(raw,receipt,hashlib.sha256(receipt).hexdigest(),source_sha())
                self.assertEqual(doc['scope'],'SYNTHETIC_EXACT_MEMBER_V1')
                self.assertEqual(doc['central_occurrences'],1)
                self.assertEqual(doc['record_occurrences'],1)
                self.assertEqual(doc['member_path_sha256'],hashlib.sha256(TARGET.encode()).hexdigest())
                self.assertFalse(doc['actual_wheel_verified'])
                self.assertFalse(doc['production_ready'])
                self.assertFalse(doc['license_reviewed'])
                nested=doc['strict_notice_evidence']['receipt']
                self.assertEqual(nested['notices'],[{'path':D+'licenses/LICENSE','bytes':22,
                    'sha256':hashlib.sha256(b'Synthetic notice only\n').hexdigest()}])
                self.assertEqual(nested['native_candidates'][0]['path'],'demo_pkg.libs/test.dll')
                self.assertEqual(receipt,c.inspect_fixture(raw))

    def test_public_gate_rejects_other_bytes(self):
        for raw in (b'',fixture(changes={TARGET:b'other'})[0],fixture(changes={TARGET:None})[0]):
            with self.subTest(length=len(raw)),self.assertRaisesRegex(c.Blocked,'^SYNTHETIC_IDENTITY_ONLY$'):
                c.inspect_fixture(raw)

    def test_identity_and_hash(self):
        raw,e=fixture()
        for key,value,reason in [('filename','scipy-1.17.1-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl','SYNTHETIC_IDENTITY_ONLY'),
                                 ('sha256','0'*64,'ARCHIVE_HASH'),('bytes',len(raw)+1,'ARCHIVE_SIZE'),
                                 ('metadata_sha256','0'*64,'METADATA_DIGEST')]:
            with self.subTest(key=key): self.deny(reason,raw,{**e,key:value})

    def test_replay_cross_policy_and_tamper(self):
        raw,_=fixture();receipt=c.inspect_fixture(raw)
        for key,value in [('scope','HISTORICAL'),('central_occurrences',0),('record_occurrences',2),
                          ('member_path_sha256','0'*64),('production_ready',True),
                          ('candidate_source_sha256','0'*64)]:
            doc=json.loads(receipt);doc[key]=value;bad=n.canonical(doc)
            with self.subTest(key=key),self.assertRaisesRegex(c.Blocked,'^CANDIDATE_REPLAY$'):
                c.verify_fixture(raw,bad,c.sha(bad),source_sha())
        with self.assertRaisesRegex(c.Blocked,'^CANDIDATE_SOURCE_IDENTITY$'):
            c.verify_fixture(raw,receipt,c.sha(receipt),'0'*64)
        with self.assertRaisesRegex(c.Blocked,'^CANDIDATE_RECEIPT_HASH$'):
            c.verify_fixture(raw,receipt,'0'*64,source_sha())
        with self.assertRaisesRegex(c.Blocked,'^CANDIDATE_REPLAY$'):
            c.verify_fixture(fixture(8)[0],receipt,c.sha(receipt),source_sha())

    def test_unsafe_and_near_match(self):
        for path in ('../evil','/evil','C:/evil','a\\b','con.txt','a/..','a./file','a//file',
                     'a/ leading','a/trailing ','a/Double  Space','a/CON .txt','a/x\tz',
                     'a/\u00e9',TARGET.lower(),TARGET+'/child','a/other space.txt',
                     'a/'+('x'*256),'a/'*32+'x'):
            with self.subTest(path=path): self.deny('UNSAFE_PATH',*fixture(changes={path:b'x'}))

    def test_absent(self):
        self.deny('EXACT_MEMBER_ABSENT',*fixture(changes={TARGET:None}))

    def test_nonregular_target(self):
        for mode,attrs,reason in [(stat.S_IFLNK|0o777,0,'ZIP_SYMLINK'),
                                  (stat.S_IFREG|0o644,0x400,'ZIP_REPARSE_ATTRIBUTE'),
                                  (stat.S_IFIFO|0o644,0,'ZIP_SPECIAL_MODE'),
                                  (0,0,'UNSAFE_PATH')]:
            info=zipfile.ZipInfo(TARGET);info.create_system=3;info.external_attr=(mode<<16)|attrs
            # zero attr would be rewritten by zipfile: choose a nonzero mode with no kind.
            if not info.external_attr: info.external_attr=0o644<<16
            with self.subTest(mode=mode,attrs=attrs):
                self.deny(reason,*fixture(changes={TARGET:None},extras=[(info,b'x')]))

    def test_directory_exception_refused(self):
        info=zipfile.ZipInfo(TARGET+'/');info.create_system=3
        info.external_attr=((stat.S_IFDIR|0o755)<<16)|0x10
        self.deny('UNSAFE_PATH',*fixture(changes={TARGET:None},extras=[(info,b'')]))

    def test_duplicate_exact_member(self):
        info=zipfile.ZipInfo(TARGET);info.create_system=3;info.external_attr=(stat.S_IFREG|0o644)<<16
        with self.assertWarns(UserWarning):
            args=fixture(extras=[(info,b'x')])
        self.deny('ZIP_DUPLICATE',*args)

    def test_collision_controls(self):
        for path,reason in [('demo_pkg/__INIT__.py','ZIP_DUPLICATE'),('Demo_pkg/other','ZIP_DIRECTORY_CASE'),
                            ('scipy/io/tests/data','ZIP_CENTRAL_LAYOUT')]:
            with self.subTest(path=path): self.deny(reason,*fixture(changes={path:b'x'}))

    def test_record_binding(self):
        def row(rows): return next(r for r in rows if r[0]==TARGET)
        for edit,reason in [(lambda r:r.remove(row(r)),'RECORD_INVENTORY'),
                            (lambda r:r.append(row(r).copy()),'RECORD_INVENTORY'),
                            (lambda r:row(r).__setitem__(0,TARGET.lower()),'UNSAFE_PATH'),
                            (lambda r:row(r).__setitem__(1,'sha256=AAAA'),'RECORD_DIGEST_SIZE'),
                            (lambda r:row(r).__setitem__(2,'999'),'RECORD_DIGEST_SIZE')]:
            with self.subTest(reason=reason): self.deny(reason,*fixture(record_edit=edit))

    def test_local_name_and_crc(self):
        raw,e=fixture()
        for offset,reason in [(raw.find(TARGET.encode()),'ZIP_LOCAL_NAME'),
                              (raw.find(b'generated inert fixture\n'),'ZIP_CRC_SIZE')]:
            data=bytearray(raw);self.assertGreater(offset,0);data[offset]^=1
            bad=bytes(data);self.deny(reason,bad,{**e,'sha256':c.sha(bad)})

    def test_metadata_and_licence(self):
        self.deny('WHEEL_TAG_MISMATCH',*fixture(changes={D+'WHEEL':WH.replace(b'py3-none-any',b'cp311-cp311-win_amd64')}))
        self.deny('DECLARED_NOTICE_MISSING_OR_AMBIGUOUS',*fixture(changes={D+'LICENSE':b'ambiguous'}))
        self.deny('DECLARED_NOTICE_MISSING_OR_AMBIGUOUS',*fixture(changes={D+'licenses/LICENSE':None}))
        raw,e=fixture()
        self.deny('UNSAFE_PATH',raw,{**e,'license_files':[TARGET]})

    def test_resource_fences(self):
        raw,e=fixture()
        for key,value,reason in [('MAX_PATH_BYTES',10,'ZIP_PATH_BUDGET'),('MAX_WHEEL',10,'ZIP_WHEEL_EXPANSION'),
                                 ('MAX_NOTICE',1,'NOTICE_FILE_LIMIT'),('MAX_TOTAL',10,'BATCH_EXPANSION_LIMIT')]:
            with self.subTest(key=key),patch.object(c,key,value): self.deny(reason,raw,e)

    def test_batch_no_repeat(self):
        raw,e=fixture();b=c._FixtureBudget();b.inspect(raw,e)
        with self.assertRaisesRegex(c.Blocked,'^BATCH_DUPLICATE
    def test_historical_pins_and_prior_five(self):
        for path,expected in [
            ('wheel_archive_inspector.py','aa5ab610d711fb8f9bc1fce1020c4999e53f3571'),
            ('wheel_archive_inspector_v2.py','9bf91fb983bd354f0b6db20dbb4eec32c447f369'),
            ('wheel_notice_evidence.py','141f069706d0c597214829eea90a48197c381e2c'),
            ('wheel_notice_evidence_v2.py','81693017a1f287cafe521e6a7e958831cfd9dc6a'),
            ('wheel_license_policy.py','876bb701544cee28e5f06851bc85c05acb74af35'),
            ('wheel_settlement_core.py','263d2565d744f4e53289fb973ff0a205561e4a7c'),
            ('wheel_hosted_final.py','e0501942a15d61f50bb9f3429bdee3721456461b'),
            ('wheel_hosted_policy_v3.py','939bb94802311a45a7f8e3f23183100c857df3be'),
            ('wheel_hosted_runtime.py','e20cc3f4f11c2d5a4659e9537d565687687a2f49'),
            ('wheel_prior_notice_preservation_45729307962.json','1adcd112c54ffa90ee638bcd7598d879e01798bc')]:
            raw=git_blob('qa/c5_wheel_metadata/'+path)
            self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),expected)
        self.assertEqual(len(p.prior_placements()),5)
        root=Path(__file__).resolve().parent
        self.assertFalse((root/'APPROVAL_WHEEL_PUBLIC_DISCOVERY_20261126.txt').exists())
        self.assertFalse((root/'APPROVAL_WHEEL_POLICY_V3_HOSTED_20261126.txt').exists())

if __name__=='__main__':
    unittest.main(verbosity=2)
): b.inspect(raw,e)
        with self.assertRaisesRegex(c.Blocked,'^BATCH_STOPPED
    def test_historical_pins_and_prior_five(self):
        for path,expected in [
            ('wheel_archive_inspector.py','aa5ab610d711fb8f9bc1fce1020c4999e53f3571'),
            ('wheel_archive_inspector_v2.py','9bf91fb983bd354f0b6db20dbb4eec32c447f369'),
            ('wheel_notice_evidence.py','141f069706d0c597214829eea90a48197c381e2c'),
            ('wheel_notice_evidence_v2.py','81693017a1f287cafe521e6a7e958831cfd9dc6a'),
            ('wheel_license_policy.py','876bb701544cee28e5f06851bc85c05acb74af35'),
            ('wheel_settlement_core.py','263d2565d744f4e53289fb973ff0a205561e4a7c'),
            ('wheel_hosted_final.py','e0501942a15d61f50bb9f3429bdee3721456461b'),
            ('wheel_prior_notice_preservation_45729307962.json','1adcd112c54ffa90ee638bcd7598d879e01798bc')]:
            raw=git_blob('qa/c5_wheel_metadata/'+path)
            self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),expected)
        self.assertEqual(len(p.prior_placements()),5)
        root=Path(__file__).resolve().parent
        self.assertFalse((root/'APPROVAL_WHEEL_PUBLIC_DISCOVERY_20261126.txt').exists())
        self.assertFalse((root/'APPROVAL_WHEEL_POLICY_V3_HOSTED_20261126.txt').exists())

if __name__=='__main__':
    unittest.main(verbosity=2)
): b.inspect(raw,e)

    def test_batch_stops_on_refusal(self):
        raw,e=fixture();b=c._FixtureBudget()
        with self.assertRaisesRegex(c.Blocked,'^ARCHIVE_HASH
    def test_historical_pins_and_prior_five(self):
        for path,expected in [
            ('wheel_archive_inspector.py','aa5ab610d711fb8f9bc1fce1020c4999e53f3571'),
            ('wheel_archive_inspector_v2.py','9bf91fb983bd354f0b6db20dbb4eec32c447f369'),
            ('wheel_notice_evidence.py','141f069706d0c597214829eea90a48197c381e2c'),
            ('wheel_notice_evidence_v2.py','81693017a1f287cafe521e6a7e958831cfd9dc6a'),
            ('wheel_license_policy.py','876bb701544cee28e5f06851bc85c05acb74af35'),
            ('wheel_settlement_core.py','263d2565d744f4e53289fb973ff0a205561e4a7c'),
            ('wheel_hosted_final.py','e0501942a15d61f50bb9f3429bdee3721456461b'),
            ('wheel_prior_notice_preservation_45729307962.json','1adcd112c54ffa90ee638bcd7598d879e01798bc')]:
            raw=git_blob('qa/c5_wheel_metadata/'+path)
            self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),expected)
        self.assertEqual(len(p.prior_placements()),5)
        root=Path(__file__).resolve().parent
        self.assertFalse((root/'APPROVAL_WHEEL_PUBLIC_DISCOVERY_20261126.txt').exists())
        self.assertFalse((root/'APPROVAL_WHEEL_POLICY_V3_HOSTED_20261126.txt').exists())

if __name__=='__main__':
    unittest.main(verbosity=2)
): b.inspect(raw,{**e,'sha256':'0'*64})
        with self.assertRaisesRegex(c.Blocked,'^BATCH_STOPPED
    def test_historical_pins_and_prior_five(self):
        for path,expected in [
            ('wheel_archive_inspector.py','aa5ab610d711fb8f9bc1fce1020c4999e53f3571'),
            ('wheel_archive_inspector_v2.py','9bf91fb983bd354f0b6db20dbb4eec32c447f369'),
            ('wheel_notice_evidence.py','141f069706d0c597214829eea90a48197c381e2c'),
            ('wheel_notice_evidence_v2.py','81693017a1f287cafe521e6a7e958831cfd9dc6a'),
            ('wheel_license_policy.py','876bb701544cee28e5f06851bc85c05acb74af35'),
            ('wheel_settlement_core.py','263d2565d744f4e53289fb973ff0a205561e4a7c'),
            ('wheel_hosted_final.py','e0501942a15d61f50bb9f3429bdee3721456461b'),
            ('wheel_prior_notice_preservation_45729307962.json','1adcd112c54ffa90ee638bcd7598d879e01798bc')]:
            raw=git_blob('qa/c5_wheel_metadata/'+path)
            self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),expected)
        self.assertEqual(len(p.prior_placements()),5)
        root=Path(__file__).resolve().parent
        self.assertFalse((root/'APPROVAL_WHEEL_PUBLIC_DISCOVERY_20261126.txt').exists())
        self.assertFalse((root/'APPROVAL_WHEEL_POLICY_V3_HOSTED_20261126.txt').exists())

if __name__=='__main__':
    unittest.main(verbosity=2)
): b.inspect(raw,e)
        self.deny('SYNTHETIC_FIXTURE_LIMIT',b'x'*65537,e)

    def test_receipt_limit(self):
        raw,_=fixture();receipt=c.inspect_fixture(raw)
        with patch.object(n,'MAX_DOCUMENT',len(receipt)-1):
            with self.assertRaisesRegex(c.Blocked,'^CANDIDATE_RECEIPT_LIMIT
    def test_historical_pins_and_prior_five(self):
        for path,expected in [
            ('wheel_archive_inspector.py','aa5ab610d711fb8f9bc1fce1020c4999e53f3571'),
            ('wheel_archive_inspector_v2.py','9bf91fb983bd354f0b6db20dbb4eec32c447f369'),
            ('wheel_notice_evidence.py','141f069706d0c597214829eea90a48197c381e2c'),
            ('wheel_notice_evidence_v2.py','81693017a1f287cafe521e6a7e958831cfd9dc6a'),
            ('wheel_license_policy.py','876bb701544cee28e5f06851bc85c05acb74af35'),
            ('wheel_settlement_core.py','263d2565d744f4e53289fb973ff0a205561e4a7c'),
            ('wheel_hosted_final.py','e0501942a15d61f50bb9f3429bdee3721456461b'),
            ('wheel_prior_notice_preservation_45729307962.json','1adcd112c54ffa90ee638bcd7598d879e01798bc')]:
            raw=git_blob('qa/c5_wheel_metadata/'+path)
            self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),expected)
        self.assertEqual(len(p.prior_placements()),5)
        root=Path(__file__).resolve().parent
        self.assertFalse((root/'APPROVAL_WHEEL_PUBLIC_DISCOVERY_20261126.txt').exists())
        self.assertFalse((root/'APPROVAL_WHEEL_POLICY_V3_HOSTED_20261126.txt').exists())

if __name__=='__main__':
    unittest.main(verbosity=2)
): c.inspect_fixture(raw)
        with patch.object(n,'MAX_DOCUMENT',len(receipt)-1):
            with self.assertRaisesRegex(c.Blocked,'^CANDIDATE_RECEIPT_LIMIT
    def test_historical_pins_and_prior_five(self):
        for path,expected in [
            ('wheel_archive_inspector.py','aa5ab610d711fb8f9bc1fce1020c4999e53f3571'),
            ('wheel_archive_inspector_v2.py','9bf91fb983bd354f0b6db20dbb4eec32c447f369'),
            ('wheel_notice_evidence.py','141f069706d0c597214829eea90a48197c381e2c'),
            ('wheel_notice_evidence_v2.py','81693017a1f287cafe521e6a7e958831cfd9dc6a'),
            ('wheel_license_policy.py','876bb701544cee28e5f06851bc85c05acb74af35'),
            ('wheel_settlement_core.py','263d2565d744f4e53289fb973ff0a205561e4a7c'),
            ('wheel_hosted_final.py','e0501942a15d61f50bb9f3429bdee3721456461b'),
            ('wheel_prior_notice_preservation_45729307962.json','1adcd112c54ffa90ee638bcd7598d879e01798bc')]:
            raw=git_blob('qa/c5_wheel_metadata/'+path)
            self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),expected)
        self.assertEqual(len(p.prior_placements()),5)
        root=Path(__file__).resolve().parent
        self.assertFalse((root/'APPROVAL_WHEEL_PUBLIC_DISCOVERY_20261126.txt').exists())
        self.assertFalse((root/'APPROVAL_WHEEL_POLICY_V3_HOSTED_20261126.txt').exists())

if __name__=='__main__':
    unittest.main(verbosity=2)
):
                c.verify_fixture(raw,receipt,c.sha(receipt),source_sha())

    def test_historical_pins_and_prior_five(self):
        for path,expected in [
            ('wheel_archive_inspector.py','aa5ab610d711fb8f9bc1fce1020c4999e53f3571'),
            ('wheel_archive_inspector_v2.py','9bf91fb983bd354f0b6db20dbb4eec32c447f369'),
            ('wheel_notice_evidence.py','141f069706d0c597214829eea90a48197c381e2c'),
            ('wheel_notice_evidence_v2.py','81693017a1f287cafe521e6a7e958831cfd9dc6a'),
            ('wheel_license_policy.py','876bb701544cee28e5f06851bc85c05acb74af35'),
            ('wheel_settlement_core.py','263d2565d744f4e53289fb973ff0a205561e4a7c'),
            ('wheel_hosted_final.py','e0501942a15d61f50bb9f3429bdee3721456461b'),
            ('wheel_prior_notice_preservation_45729307962.json','1adcd112c54ffa90ee638bcd7598d879e01798bc')]:
            raw=git_blob('qa/c5_wheel_metadata/'+path)
            self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),expected)
        self.assertEqual(len(p.prior_placements()),5)
        root=Path(__file__).resolve().parent
        self.assertFalse((root/'APPROVAL_WHEEL_PUBLIC_DISCOVERY_20261126.txt').exists())
        self.assertFalse((root/'APPROVAL_WHEEL_POLICY_V3_HOSTED_20261126.txt').exists())

if __name__=='__main__':
    unittest.main(verbosity=2)
