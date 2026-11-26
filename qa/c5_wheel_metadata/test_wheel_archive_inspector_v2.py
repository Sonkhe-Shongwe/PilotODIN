"""Synthetic generated wheel fixtures only; no packages acquired or imported."""
import base64
import csv
import hashlib
import io
import stat
import struct
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wheel_archive_inspector_v2 as w
import wheel_archive_inspector as historical

D = 'demo_pkg-1.2.dist-info/'
MD = b'Metadata-Version: 2.4\nName: demo-pkg\nVersion: 1.2\nRequires-Python: >=3.11\nLicense-Expression: MIT\nLicense-File: LICENSE\n\n'
WH = b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n\n'


def fixture(*, changes=None, record_edit=None, extras=(), compress=zipfile.ZIP_DEFLATED):
    members = {'demo_pkg/__init__.py':b'# inert\n', D+'METADATA':MD, D+'WHEEL':WH,
               D+'licenses/LICENSE':b'Synthetic notice only\n', 'demo_pkg.libs/test.dll':b'inert not executable',
               'demo_pkg/NOTICE.txt':b'Other synthetic notice'}
    if changes:
        for p,v in changes.items():
            if v is None: members.pop(p)
            else: members[p]=v
    rows = [[p,'sha256='+base64.urlsafe_b64encode(hashlib.sha256(v).digest()).decode().rstrip('='),str(len(v))]
            for p,v in members.items()]
    rows.append([D+'RECORD','',''])
    if record_edit: record_edit(rows)
    buf=io.StringIO(newline=''); csv.writer(buf).writerows(rows)
    members[D+'RECORD']=buf.getvalue().encode()
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=compress) as z:
        for p,v in members.items(): z.writestr(p,v)
        for info,v in extras: z.writestr(info,v)
    raw=out.getvalue()
    expected={'filename':'demo_pkg-1.2-py3-none-any.whl','name':'demo-pkg','version':'1.2','bytes':len(raw),
              'sha256':w.sha(raw),'metadata_sha256':w.sha(members[D+'METADATA']), 'license_files':['LICENSE'],
              'license_expression':'MIT','requires_python':'>=3.11'}
    return raw,expected


class Tests(unittest.TestCase):
    def deny(self, reason, args, budget=None):
        with self.assertRaisesRegex(w.Blocked, '^'+reason+'$'):
            (budget or w.InspectionBudget()).inspect(*args)

    def mutate(self, reason, **kwargs): self.deny(reason,fixture(**kwargs))

    def test_valid_deflate(self):
        r=w.InspectionBudget().inspect(*fixture())
        self.assertEqual(r['members'],7)
        self.assertEqual(r['tags'],['py3-none-any'])
        self.assertEqual(len(r['notices']),2)
        self.assertEqual(r['native_candidates'][0]['path'],'demo_pkg.libs/test.dll')
        self.assertEqual({x['path']:x['sha256'] for x in r['notices']}['demo_pkg/NOTICE.txt'],w.sha(b'Other synthetic notice'))
        self.assertFalse(r['license_reviewed'])
        self.assertEqual(r['status'],'CANDIDATE_INTEGRITY_ONLY')
    def test_stored(self): self.assertEqual(w.InspectionBudget().inspect(*fixture(compress=0))['members'],7)
    def test_archive_hash(self):
        raw,e=fixture(); e['sha256']='0'*64; self.deny('ARCHIVE_HASH',(raw,e))
    def test_archive_size(self):
        raw,e=fixture(); e['bytes']+=1; self.deny('ARCHIVE_SIZE',(raw,e))
    def test_metadata_hash(self):
        raw,e=fixture(); e['metadata_sha256']='0'*64; self.deny('METADATA_DIGEST',(raw,e))
    def test_filename(self):
        raw,e=fixture(); e['filename']='other-1.2-py3-none-any.whl'; self.deny('WHEEL_IDENTITY',(raw,e))
    def test_metadata_name(self): self.mutate('METADATA_IDENTITY',changes={D+'METADATA':MD.replace(b'demo-pkg',b'other')})
    def test_declarations(self): self.mutate('METADATA_DECLARATIONS',changes={D+'METADATA':MD.replace(b'MIT',b'BSD-3-Clause')})
    def test_header_duplicate(self): self.mutate('HEADER_CARDINALITY',changes={D+'METADATA':MD.replace(b'Name: demo-pkg',b'Name: demo-pkg\nName: demo-pkg')})
    def test_tag(self): self.mutate('WHEEL_TAG_MISMATCH',changes={D+'WHEEL':WH.replace(b'py3-none-any',b'cp311-cp311-win_amd64')})
    def test_missing_notice(self): self.mutate('DECLARED_NOTICE_MISSING_OR_AMBIGUOUS',changes={D+'licenses/LICENSE':None})
    def test_ambiguous_notice(self): self.mutate('DECLARED_NOTICE_MISSING_OR_AMBIGUOUS',changes={D+'LICENSE':b'other'})
    def test_record_hash(self): self.mutate('RECORD_DIGEST_SIZE',record_edit=lambda r:r[0].__setitem__(1,'sha256=AAAA'))
    def test_record_size(self): self.mutate('RECORD_DIGEST_SIZE',record_edit=lambda r:r[0].__setitem__(2,'999'))
    def test_record_weak_hash(self): self.mutate('RECORD_DIGEST_SIZE',record_edit=lambda r:r[0].__setitem__(1,'md5=AAAA'))
    def test_record_missing(self): self.mutate('RECORD_INVENTORY',record_edit=lambda r:r.pop(0))
    def test_record_duplicate(self): self.mutate('RECORD_INVENTORY',record_edit=lambda r:r.append(r[0]))
    def test_record_self(self): self.mutate('RECORD_SELF',record_edit=lambda r:r[-1].__setitem__(2,'0'))
    def test_path(self):
        for p in ('../evil','/evil','C:/evil','a\\b','con.txt','a/..','a./file','a//file'):
            with self.subTest(p=p): self.mutate('UNSAFE_PATH',changes={p:b'x'})
    def test_case_collision(self): self.mutate('ZIP_DUPLICATE',changes={'demo_pkg/NOTICE.TXT':b'x'})
    def test_directory_case(self): self.mutate('ZIP_DIRECTORY_CASE',changes={'Demo_pkg/other.txt':b'x'})
    def test_file_directory(self): self.mutate('ZIP_CENTRAL_LAYOUT',changes={'demo_pkg':b'x'})
    def test_symlink(self):
        i=zipfile.ZipInfo('link');i.create_system=3;i.external_attr=(stat.S_IFLNK|0o777)<<16
        self.mutate('ZIP_SYMLINK',extras=[(i,b'target')])
    def test_extra(self):
        i=zipfile.ZipInfo('extra');i.extra=b'\xff\xff\x00\x00';self.mutate('ZIP_UNSUPPORTED',extras=[(i,b'x')])
    def test_unsupported_compression(self): self.mutate('ZIP_UNSUPPORTED',compress=zipfile.ZIP_BZIP2)
    def test_other_dist_info(self): self.mutate('DIST_INFO_IDENTITY',changes={'other-1.dist-info/METADATA':b'x'})
    def test_signature(self): self.mutate('RECORD_SIGNATURE_UNSUPPORTED',changes={D+'RECORD.jws':b'x'})
    def altered(self, reason, change):
        raw,e=fixture(); buf=bytearray(raw); change(buf); raw=bytes(buf);e.update(bytes=len(raw),sha256=w.sha(raw));self.deny(reason,(raw,e))
    def test_local_flags(self): self.altered('ZIP_LOCAL_MISMATCH',lambda b:struct.pack_into('<H',b,6,1))
    def test_local_name(self): self.altered('ZIP_LOCAL_NAME',lambda b:b.__setitem__(30,ord('x')))
    def test_trailing(self): self.altered('ZIP_END',lambda b:b.extend(b'x'))
    def test_crc(self):
        def corrupt(b):
            cd=b.find(b'PK\x01\x02');struct.pack_into('<I',b,14,0);struct.pack_into('<I',b,cd+16,0)
        self.altered('ZIP_CRC_SIZE',corrupt)
    def test_notice_budget(self):
        with patch.object(w,'MAX_NOTICE',3): self.mutate('NOTICE_FILE_LIMIT')
    def test_member_budget(self):
        with patch.object(w,'MAX_MEMBER',3): self.mutate('ZIP_BOUNDS')
    def test_batch_budget(self):
        with patch.object(w,'MAX_TOTAL',10): self.mutate('BATCH_EXPANSION_LIMIT')
    def test_batch_notice_budget(self):
        with patch.object(w,'MAX_NOTICES',2): self.mutate('BATCH_EXPANSION_LIMIT')
    def test_entry_budget(self):
        with patch.object(w,'MAX_MEMBERS',3): self.mutate('ZIP_END')
    def test_path_budget(self):
        with patch.object(w,'MAX_PATH_BYTES',10): self.mutate('ZIP_PATH_BUDGET')
    def test_directory_budget(self):
        with patch.object(w,'MAX_DIRECTORIES',1): self.mutate('ZIP_DIRECTORY_LIMIT')
    def test_duplicate_batch(self):
        b=w.InspectionBudget();args=fixture();b.inspect(*args);self.deny('BATCH_DUPLICATE',args,b)
    def test_failed_batch_reservation(self):
        b=w.InspectionBudget();raw,e=fixture();e['metadata_sha256']='0'*64
        self.deny('METADATA_DIGEST',(raw,e),b);self.assertGreater(b.expanded,0)
        self.deny('BATCH_DUPLICATE',(raw,e),b)


    @staticmethod
    def directory(path, *, attrs=None, method=zipfile.ZIP_STORED):
        i=zipfile.ZipInfo(path); i.create_system=3; i.compress_type=method
        i.external_attr=(stat.S_IFDIR|0o755)<<16|0x10 if attrs is None else attrs
        return i

    def test_v2_receipt_legacy_files_identical(self):
        args=fixture()
        before, old_notices=historical.InspectionBudget().inspect(*args,capture_notices=True)
        after, notices=w.InspectionBudget().inspect(*args,capture_notices=True)
        self.assertEqual(after.pop('inspector_schema'),2)
        self.assertEqual(after.pop('directory_entries'),0)
        self.assertEqual(after.pop('directory_inventory_sha256'),w.sha(b''))
        self.assertEqual(after,before)
        self.assertEqual(notices,old_notices)

    def test_explicit_directory_and_nested_ancestors(self):
        names=['demo_pkg/','demo_pkg.libs/','demo_pkg-1.2.dist-info/','demo_pkg-1.2.dist-info/licenses/','empty/child/']
        args=fixture(extras=[(self.directory(p),b'') for p in names])
        result, notices=w.InspectionBudget().inspect(*args,capture_notices=True)
        self.assertEqual(result['members'],7)
        self.assertEqual(result['directory_entries'],len(names))
        self.assertEqual(result['directory_inventory_sha256'],w.sha(('\n'.join(sorted(names))+'\n').encode()))
        self.assertEqual(len(notices),2)
        self.assertEqual(result['expanded_bytes'],w.InspectionBudget().inspect(*fixture())['expanded_bytes'])
        with self.assertRaisesRegex(historical.Blocked,'^ZIP_NONREGULAR unittest.main(verbosity=2)
):
            historical.InspectionBudget().inspect(*args)

    def test_deflated_empty_directory(self):
        i=self.directory('demo_pkg/',method=zipfile.ZIP_DEFLATED)
        r=w.InspectionBudget().inspect(*fixture(extras=[(i,b'')]))
        self.assertEqual(r['directory_entries'],1)

    def test_dos_only_directory(self):
        i=self.directory('demo_pkg/',attrs=0x10); i.create_system=0
        self.assertEqual(w.InspectionBudget().inspect(*fixture(extras=[(i,b'')]))['directory_entries'],1)

    def test_unix_only_directory(self):
        i=self.directory('demo_pkg/',attrs=(stat.S_IFDIR|0o755)<<16)
        self.assertEqual(w.InspectionBudget().inspect(*fixture(extras=[(i,b'')]))['directory_entries'],1)

    def test_directory_payload(self):
        for method in (0,8):
            with self.subTest(method=method):
                self.mutate('ZIP_DIRECTORY_PAYLOAD',extras=[(self.directory('demo_pkg/',method=method),b'x')])

    def test_directory_missing_slash(self):
        self.mutate('ZIP_DIRECTORY_ATTRIBUTES',extras=[(self.directory('empty'),b'')])

    def test_directory_conflicting_mode(self):
        self.mutate('ZIP_DIRECTORY_ATTRIBUTES',extras=[(self.directory('empty/',attrs=((stat.S_IFREG|0o644)<<16)|0x10),b'')])

    def test_directory_missing_attributes(self):
        self.mutate('ZIP_DIRECTORY_ATTRIBUTES',extras=[(self.directory('empty/',attrs=0x20),b'')])

    def test_directory_special_permissions(self):
        self.mutate('ZIP_DIRECTORY_ATTRIBUTES',extras=[(self.directory('empty/',attrs=((stat.S_IFDIR|0o4755)<<16)|0x10),b'')])

    def test_directory_reparse(self):
        self.mutate('ZIP_REPARSE_ATTRIBUTE',extras=[(self.directory('empty/',attrs=0x410),b'')])

    def test_directory_volume_device(self):
        for flag in (0x08,0x40):
            with self.subTest(flag=flag):
                self.mutate('ZIP_SPECIAL_ATTRIBUTE',extras=[(self.directory('empty/',attrs=0x10|flag),b'')])

    def test_special_unix_types(self):
        for kind in (stat.S_IFBLK,stat.S_IFCHR,stat.S_IFIFO,stat.S_IFSOCK):
            with self.subTest(kind=kind):
                self.mutate('ZIP_SPECIAL_MODE',extras=[(self.directory('special',attrs=(kind|0o600)<<16),b'')])

    def test_symlink_directory_suffix(self):
        self.mutate('ZIP_SYMLINK',extras=[(self.directory('link/',attrs=((stat.S_IFLNK|0o777)<<16)|0x10),b'')])

    def test_unsafe_directory_names(self):
        for p in ('../evil/','/evil/','C:/evil/','a\\b/','con/','a/../','a//','a./'):
            with self.subTest(p=p):
                self.mutate('UNSAFE_PATH',extras=[(self.directory(p),b'')])

    def test_directory_duplicate(self):
        self.mutate('ZIP_DUPLICATE',extras=[(self.directory('empty/'),b''),(self.directory('EMPTY/'),b'')])

    def test_directory_case_collision(self):
        self.mutate('ZIP_DIRECTORY_CASE',extras=[(self.directory('DEMO_PKG/'),b'')])

    def test_directory_file_collision(self):
        self.mutate('ZIP_DUPLICATE',extras=[(self.directory('demo_pkg/__init__.py/'),b'')])

    def test_directory_ancestor_file_collision(self):
        self.mutate('ZIP_CENTRAL_LAYOUT',extras=[(self.directory('demo_pkg/__init__.py/child/'),b'')])

    def test_directory_record_row_refused(self):
        self.mutate('UNSAFE_PATH',extras=[(self.directory('empty/'),b'')],record_edit=lambda r:r.append(['empty/','','']))

    def test_foreign_distinfo_directory(self):
        self.mutate('DIST_INFO_IDENTITY',extras=[(self.directory('other-1.dist-info/'),b'')])

    def test_directory_budget_counts_empty(self):
        with patch.object(w,'MAX_DIRECTORIES',5):
            self.mutate('ZIP_DIRECTORY_LIMIT',extras=[(self.directory('empty/deep/'),b'')])

    def test_directory_local_name_mismatch(self):
        raw,e=fixture(extras=[(self.directory('empty/'),b'')])
        b=bytearray(raw)
        cd=raw.find(b'PK\x01\x02')
        # Use the central directory to locate the exact last local header.
        pos=cd
        while raw[pos:pos+4]==b'PK\x01\x02':
            row=w.CENTRAL.unpack_from(raw,pos); n,el,cl=row[10:13]
            if raw[pos+w.CENTRAL.size:pos+w.CENTRAL.size+n]==b'empty/':
                b[row[-1]+w.LOCAL.size]=ord('x'); break
            pos+=w.CENTRAL.size+n+el+cl
        self.assertNotEqual(bytes(b),raw)
        raw=bytes(b);e.update(bytes=len(raw),sha256=w.sha(raw))
        self.deny('ZIP_LOCAL_NAME',(raw,e))

    def test_directory_corrupt_deflate(self):
        raw,e=fixture(extras=[(self.directory('empty/',method=zipfile.ZIP_DEFLATED),b'')])
        b=bytearray(raw);pos=raw.find(b'PK\x01\x02')
        while raw[pos:pos+4]==b'PK\x01\x02':
            row=w.CENTRAL.unpack_from(raw,pos); n,el,cl=row[10:13]
            if raw[pos+w.CENTRAL.size:pos+w.CENTRAL.size+n]==b'empty/':
                b[row[-1]+w.LOCAL.size+n]=0xff; break
            pos+=w.CENTRAL.size+n+el+cl
        self.assertNotEqual(bytes(b),raw)
        raw=bytes(b);e.update(bytes=len(raw),sha256=w.sha(raw))
        self.deny('MALFORMED_WHEEL',(raw,e))


if __name__=='__main__': unittest.main(verbosity=2)
