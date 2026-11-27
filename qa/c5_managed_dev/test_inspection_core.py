import gzip
import io
import json
import stat
import tarfile
import unittest
import zipfile
from unittest.mock import patch
import inspection_core as c


def wheel(entries=(), metadata=b'Name: demo\nVersion: 1.0\nLicense-File: LICENSE\n\n'):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('demo-1.0.dist-info/METADATA', metadata)
        z.writestr('demo-1.0.dist-info/licenses/LICENSE', b'fixture licence')
        for path, data in entries:
            z.writestr(path, data)
    return buf.getvalue()


def npm(entries=(), trailing=b''):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w', format=tarfile.USTAR_FORMAT) as t:
        for path, data in [('package/package.json', b'{"name":"demo","version":"1.0","license":"MIT"}'), *entries]:
            info = path if isinstance(path, tarfile.TarInfo) else tarfile.TarInfo(path)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    return gzip.compress(buf.getvalue() + trailing)


def row(raw, kind='wheel'):
    common = {'kind': kind, 'version': '1.0', 'bytes': len(raw)}
    if kind == 'npm':
        return {**common, 'name': 'node_modules/demo', 'filename': 'demo-1.0.tgz', 'url': 'https://registry.npmjs.org/demo/-/demo-1.0.tgz', 'sha512': c.digest(raw, 'sha512'), 'declared_license': 'MIT'}
    return {**common, 'name': 'demo', 'filename': 'demo-1.0-py3-none-any.whl', 'url': 'https://files.pythonhosted.org/packages/demo-1.0-py3-none-any.whl', 'sha256': c.digest(raw)}


class InspectionTest(unittest.TestCase):
    def inspect(self, raw, kind='wheel'):
        return c.inspect(raw, row(raw, kind))

    def test_zip_directory_notice_native(self):
        data = wheel([('demo/', b''), ('demo/native.pyd', b'MZfixture')])
        result = self.inspect(data)
        self.assertEqual(result['members'], 4)
        self.assertEqual(result['native'][0]['format'], 'PE')
        self.assertEqual(result['notices'][0]['sha256'], c.digest(b'fixture licence'))
        self.assertEqual(result['status'], 'UNRESOLVED_USE_RIGHTS')

    def test_zip_symlink(self):
        entry = zipfile.ZipInfo('demo/link'); entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaisesRegex(c.Refused, 'ZIP_MODE'):
            self.inspect(wheel([(entry, b'outside')]))

    def test_path_collisions(self):
        for entries in [[('../escape', b'x')], [('/absolute', b'x')], [('A/x', b'x'), ('a/y', b'y')], [('a', b'x'), ('a/b', b'y')], [('a', b'x'), ('A', b'y')]]:
            with self.subTest(entries=entries), self.assertRaises(c.Refused):
                self.inspect(wheel(entries))

    def test_zip_expansion_cap(self):
        raw = wheel([('demo/huge', b'x' * 5000)])
        with patch.object(c, 'MAX_MEMBER', 4096), self.assertRaisesRegex(c.Refused, 'MEMBER_CAP'):
            self.inspect(raw)

    def test_hash_before_parse(self):
        raw = b'not an archive'; r = row(raw); r['sha256'] = '0' * 64
        with patch.object(c, 'members', side_effect=AssertionError('parsed')), self.assertRaisesRegex(c.Refused, 'ARCHIVE_IDENTITY'):
            c.inspect(raw, r)

    def test_tar_regular_and_directory(self):
        directory = tarfile.TarInfo('package/bin'); directory.type = tarfile.DIRTYPE
        result = self.inspect(npm([(directory, b''), ('package/bin/tool', b'\x7fELFfixture'), ('package/LICENSE', b'notice')]), 'npm')
        self.assertEqual(result['native'][0]['format'], 'ELF')
        self.assertEqual(len(result['notices']), 1)

    def test_tar_symlink_and_traversal(self):
        link = tarfile.TarInfo('package/link'); link.type = tarfile.SYMTYPE; link.linkname = '../outside'
        for item in [link, '../escape']:
            with self.subTest(item=item), self.assertRaises(c.Refused):
                self.inspect(npm([(item, b'')]), 'npm')

    def test_tar_trailing_and_gzip_trailing(self):
        for raw in [npm(trailing=b'payload'), npm() + gzip.compress(b'other'), npm()[:-3]]:
            with self.subTest(raw=raw[-12:]), self.assertRaises((c.Refused, c.zlib.error)):
                self.inspect(raw, 'npm')

    def test_gzip_expansion_cap(self):
        raw = npm()
        with patch.object(c, 'MAX_EXPANDED', 2048), self.assertRaisesRegex(c.Refused, 'GZIP_CAP'):
            self.inspect(raw, 'npm')

    def test_metadata_and_notice(self):
        for meta in [b'Name: other\nVersion: 1.0\n\n', b'Name: demo\nVersion: 1.0\nLicense-File: MISSING\n\n']:
            with self.subTest(meta=meta), self.assertRaises(c.Refused):
                self.inspect(wheel(metadata=meta))

    def test_transport_refusals(self):
        raw = wheel(); r = row(raw)
        command = c.curl_command('/usr/bin/curl', r, 'scratch/archive')
        self.assertIn('--max-filesize', command); self.assertNotIn('--location', command)
        c.transfer_result(0, ('200 ' + str(len(raw))).encode(), raw, r)
        for code, output, body in [(0, b'302 0', raw), (1, b'200 0', raw), (0, ('200 ' + str(len(raw))).encode(), raw[:-1])]:
            with self.assertRaises(c.Refused):
                c.transfer_result(code, output, body, r)
        with self.assertRaises(c.Refused):
            c.curl_command('curl', {**r, 'url': 'https://files.pythonhosted.org.evil.test/demo.whl'}, 'scratch/archive')

    def test_tool_and_receipt_caps(self):
        self.assertEqual(c.tool_command('readelf', 'ELF', '/tmp/member'), ['readelf', '-h', '-d', '-V', '/tmp/member'])
        for args in [(0, b'x' * (c.MAX_TOOL_OUTPUT + 1), b''), (0, b'', b'', True), (1, b'', b''), (0, b'', b'error')]:
            with self.assertRaises(c.Refused):
                c.tool_result(*args)
        with patch.object(c, 'MAX_OUTPUT', 1), self.assertRaisesRegex(c.Refused, 'RECEIPT_CAP'):
            self.inspect(wheel())

    def test_plan_and_json(self):
        with self.assertRaisesRegex(c.Refused, 'PLAN_PIN'):
            c.projection(b'{}')
        with self.assertRaisesRegex(c.Refused, 'JSON_DUPLICATE'):
            c.strict_json(b'{"a":1,"a":2}')


if __name__ == '__main__':
    unittest.main()
