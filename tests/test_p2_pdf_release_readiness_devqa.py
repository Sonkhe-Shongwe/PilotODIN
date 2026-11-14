"""P2-U2g synthetic, no six real font files, network, build or installation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import p2_pdf_release_readiness_devqa as qa


def identities(data: bytes) -> tuple[int, str, str]:
    return (len(data), hashlib.sha256(data).hexdigest(),
            hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest())


def fixture(folder: Path, *, rfn: bool = True):
    assets = []
    prior = []
    header = ('Copyright 2026 Synthetic test authors.\n' +
              ('Reserved Font Name "Example".\n' if rfn else '') +
              'SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007\n')
    notice = (header + 'PREAMBLE\n' + 'This licence defines Reserved Font Name terms.\n'*20).encode()
    for role, family in (('regular','alpha'),('cjk','beta'),('symbol','gamma')):
        font_name = role + '.ttf'
        licence_name = role + '-OFL.txt'
        file_data = (role*17).encode()
        font = identities(file_data)
        licence = identities(notice)
        (folder / font_name).write_bytes(file_data)
        (folder / licence_name).write_bytes(notice)
        assets.append(dict(role=role,filename=font_name,bytes=font[0],
                           git_blob_sha1=font[2],license_filename=licence_name,
                           license_bytes=licence[0],license_git_blob_sha1=licence[2],
                           relative_path=f'ofl/{family}/{font_name}',
                           license_path=f'ofl/{family}/OFL.txt',
                           status='CANDIDATE_NOT_FOR_RELEASE'))
        prior.extend((dict(role=role,kind=kind,name=name,bytes=ident[0],sha256=ident[1])
                      for kind,name,ident in (('font',font_name,font),('license',licence_name,licence))))
    manifest = dict(schema=1,status='CANDIDATES_UNVERIFIED_DO_NOT_SHIP',
                    source_repo='google/fonts',source_commit=qa.PINNED_UPSTREAM_COMMIT,assets=assets)
    return manifest, prior


class CandidateDossierContracts(unittest.TestCase):
    def local(self, mutate=None):
        td = TemporaryDirectory(prefix='p2-u2g-test-')
        root=Path(td.name)
        manifest,prior=fixture(root)
        if mutate:mutate(root,manifest,prior)
        def resolver(_parent,_manifest):return root,prior
        return td,manifest,resolver

    def test_exact_six_candidate_hashes_but_never_release_approval(self):
        td,manifest,resolve=self.local()
        try:
            with patch.object(qa,'REVIEW_PARENT',Path(td.name)):
                result=qa.build_readiness_dossier(manifest,review_resolver=resolve)
            self.assertEqual(result['state'],qa.SAFE_STATE)
            self.assertEqual(len(result['candidate_bytes']),6)
            self.assertFalse(result['candidate_sha256_is_release_pin'])
            self.assertEqual(result['release_font_approval'],'NOT_GRANTED')
            self.assertEqual(result['release_manifest'],'NOT_CREATED')
            self.assertEqual(result['production_unicode_pdf'],'VISUAL_FAIL')
            self.assertTrue(all(not v['release_approved'] for v in result['candidate_bytes']))
        finally:td.cleanup()

    def test_reserved_name_declaration_header_distinguished_from_boilerplate(self):
        for rfn,expected in ((True,1),(False,0)):
            with self.subTest(rfn=rfn):
                s=('Copyright 2026 Example\n'+('Reserved Font Name "Example"\n' if rfn else '')+
                    'SIL OPEN FONT LICENSE Version 1.1\n'+'The Reserved Font Name means X.\n'*30)
                result=qa.inspect_ofl_notice(s.encode())
                self.assertEqual(len(result['reserved_name_header_clauses']),expected)
                self.assertEqual(result['reserved_name_legal_review'],'REQUIRED')

    def test_unicode_or_missing_ofl_heading_blocks(self):
        for candidate in (b'\xff'*550, b'copyright abc\n' + b'a'*600,
                          b'SIL OPEN FONT LICENSE Version 1.1\n'+b'a'*600,
                          b'a'*490):
            with self.subTest(size=len(candidate)),self.assertRaises(qa.CandidateAuditError):
                qa.inspect_ofl_notice(candidate)

    def test_sha_change_after_review_rejected(self):
        def mutate(root,manifest,prior):
            p=root/'regular.ttf';p.write_bytes(b'Q'*len(p.read_bytes()))
        td,manifest,resolve=self.local(mutate)
        try:
            with patch.object(qa,'REVIEW_PARENT',Path(td.name)),self.assertRaises(qa.CandidateAuditError):
                qa.build_readiness_dossier(manifest,review_resolver=resolve)
        finally:td.cleanup()

    def test_ambiguous_prior_role_and_missing_review_is_blocked(self):
        def mutate(root,manifest,prior):prior[1]=dict(prior[0])
        td,manifest,resolve=self.local(mutate)
        try:
            with patch.object(qa,'REVIEW_PARENT',Path(td.name)),self.assertRaises(qa.CandidateAuditError):
                qa.build_readiness_dossier(manifest,review_resolver=resolve)
        finally:td.cleanup()

    def test_missing_or_redirected_asset_blocked(self):
        with TemporaryDirectory(prefix='p2-u2g-symlink-') as td:
            root=Path(td);manifest,prior=fixture(root)
            (root/'regular.ttf').unlink()
            with patch.object(qa,'REVIEW_PARENT',root),self.assertRaises(Exception):
                qa.build_readiness_dossier(manifest,review_resolver=lambda *a:(root,prior))
            try:
                (root/'regular.ttf').symlink_to(root/'cjk.ttf')
            except (OSError,NotImplementedError):return
            with patch.object(qa,'REVIEW_PARENT',root),self.assertRaises(Exception):
                qa.build_readiness_dossier(manifest,review_resolver=lambda *a:(root,prior))

    def test_rejects_incomplete_manifest_and_unknown_family(self):
        td,manifest,resolve=self.local()
        try:
            cases=[dict(manifest,status='APPROVED'),dict(manifest,assets=manifest['assets'][:2]),
                   dict(manifest,source_repo='other'),
                   dict(manifest,source_commit='b'*40),
                   dict(manifest,assets=[dict(manifest['assets'][0],relative_path='../escape.ttf'),*manifest['assets'][1:]]),
                   dict(manifest,assets=[dict(manifest['assets'][0],role='wrong'),*manifest['assets'][1:]])]
            with patch.object(qa,'REVIEW_PARENT',Path(td.name)):
                for invalid in cases:
                    with self.subTest(invalid=str(invalid)[:60]),self.assertRaises(Exception):
                        qa.build_readiness_dossier(invalid,review_resolver=resolve)
        finally:td.cleanup()

    def test_licence_checksum_corruption_is_detected(self):
        def mutate(root,manifest,prior):
            p=root/'cjk-OFL.txt';p.write_bytes(p.read_bytes()[:-1]+b'X')
        td,manifest,resolve=self.local(mutate)
        try:
            with patch.object(qa,'REVIEW_PARENT',Path(td.name)),self.assertRaises(Exception):
                qa.build_readiness_dossier(manifest,review_resolver=resolve)
        finally:td.cleanup()

    def test_read_only_audit_never_creates_any_file(self):
        td,manifest,resolve=self.local()
        try:
            root=Path(td.name)
            before={p.name:(p.stat().st_size,p.stat().st_mtime_ns) for p in root.iterdir()}
            with patch.object(qa,'REVIEW_PARENT',root):
                qa.build_readiness_dossier(manifest,review_resolver=resolve)
            after={p.name:(p.stat().st_size,p.stat().st_mtime_ns) for p in root.iterdir()}
            self.assertEqual(before,after)
        finally:td.cleanup()

    def test_main_error_is_safe_and_no_approval(self):
        with patch.object(qa,'MANIFEST_PATH',Path('/missing/manifest')):
            with patch('builtins.print') as out:
                self.assertEqual(qa.main(),2)
                payload=json.loads(out.call_args.args[0])
                self.assertEqual(payload['state'],'BLOCKED')
                self.assertEqual(payload['release_font_approval'],'NOT_GRANTED')
                self.assertNotIn('path',payload)


if __name__=='__main__':unittest.main()
