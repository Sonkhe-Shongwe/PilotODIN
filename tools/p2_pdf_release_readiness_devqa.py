#!/usr/bin/env python3
"""P2-U2g: read-only, fail-closed release-readiness DOSSIER for DEVQA candidates.

Never a release manifest, sign-off, font converter, installer or production tool.
No copies/writes/downloads. The existing reviewed six-file source receipt is
revalidated by earlier pinned build-review helpers before any dossier is built.
Only identities and bounded notice review indicators are printed, not font data.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))

from p2_pdf_font_resource_path_devqa import MANIFEST_PATH, REVIEW_PARENT
from p2_pdf_frozen_font_onefile_devqa import verified_review_files
from p2_pdf_font_build_preflight import _expected, _not_redirected
from p2_pdf_font_asset_gate import hash_file

ROLES = ('regular', 'cjk', 'symbol')
PINNED_UPSTREAM_COMMIT = 'e7db6ca603fd4862010383ff17ffd6cc4ffac1c0'
SAFE_STATE = 'DEVQA_CANDIDATE_DOSSIER_COMPLETE_RELEASE_REVIEW_REQUIRED'
MAX_NOTICE_CHARS = 40_000
_OFL_SECTION = re.compile(r'^\s*SIL OPEN FONT LICENSE\s+Version 1\.1', re.I | re.M)
_RFN_CLAUSE = re.compile(r'(?im)^\s*[^\n]{0,120}Reserved Font Name[^\n]{0,160}$')
_HEX_SHA = re.compile(r'[a-f0-9]{64}\Z')


class CandidateAuditError(ValueError):
    """Restrict failure information to a safe class and stage."""


def inspect_ofl_notice(data: bytes) -> dict:
    """Read full supplied licence; search copyright and *header* RFN clauses.

    Boilerplate mentions 'Reserved Font Name' in definitions/conditions and
    must NOT be mistaken for an actual family-specific reservation.
    """
    if not isinstance(data, bytes) or not 500 <= len(data) <= MAX_NOTICE_CHARS:
        raise CandidateAuditError('Untrusted or excessive OFL bytes')
    try:
        text = data.decode('utf-8', errors='strict')
    except UnicodeError as exc:
        raise CandidateAuditError('Invalid OFL encoding') from exc
    match = _OFL_SECTION.search(text)
    if not match or 'copyright' not in text[:match.start()].lower():
        raise CandidateAuditError('OFL heading or copyright metadata absent')
    header = text[:match.start()]
    clauses = [re.sub(r'\s+', ' ', x.strip()) for x in _RFN_CLAUSE.findall(header)]
    if len(clauses) > 5 or any(len(x) > 240 for x in clauses):
        raise CandidateAuditError('Excessive reserved-name metadata')
    return {
        'ofl_v1_1_heading_present': True,
        'copyright_header_present': True,
        'reserved_name_header_clauses': clauses,
        'reserved_name_legal_review': 'REQUIRED',
        'license_redistribution_review': 'REQUIRED',
    }


def build_readiness_dossier(manifest: dict, *, review_resolver=verified_review_files) -> dict:
    """Reverify all six bytes from ONE reviewed source. No output files."""
    if not isinstance(manifest, dict):
        raise CandidateAuditError('Missing candidate manifest')
    expected = _expected(manifest)
    if (manifest.get('source_repo') != 'google/fonts' or
            manifest.get('source_commit') != PINNED_UPSTREAM_COMMIT or len(expected) != 6):
        raise CandidateAuditError('Unapproved source candidate manifest')
    rows = manifest.get('assets')
    if not isinstance(rows, list) or len(rows) != 3:
        raise CandidateAuditError('Invalid font candidate roles')
    by_role = {item.get('role'): item for item in rows if isinstance(item, dict)}
    if set(by_role) != set(ROLES) or len(by_role) != len(rows):
        raise CandidateAuditError('Ambiguous font candidate roles')
    _not_redirected(REVIEW_PARENT)
    folder, approved_for_review = review_resolver(REVIEW_PARENT, manifest)
    if not isinstance(folder, Path) or not folder.is_absolute() or not folder.is_dir():
        raise CandidateAuditError('Existing review source is not a real directory')
    _not_redirected(folder)
    if not isinstance(approved_for_review, list) or len(approved_for_review) != 6:
        raise CandidateAuditError('Incomplete prior source revalidation')
    prior = {(x.get('role'), x.get('kind'), x.get('name')): x for x in approved_for_review
             if isinstance(x, dict)}
    if len(prior) != 6:
        raise CandidateAuditError('Ambiguous reviewed asset identities')
    verified = []
    notes = {}
    for role, name, size, source_blob, kind in expected:
        key = (role, kind, name)
        previous = prior.get(key)
        if (not isinstance(previous, dict) or previous.get('bytes') != size or
                not isinstance(previous.get('sha256'), str) or
                not _HEX_SHA.fullmatch(previous['sha256'])):
            raise CandidateAuditError('Review record missing or malformed')
        path = folder / name
        _not_redirected(path)
        if not path.is_file() or path.is_symlink():
            raise CandidateAuditError('Review source absent or redirected')
        actual_size, actual_sha, actual_blob = hash_file(path)
        if (actual_size != size or actual_blob != source_blob or
                actual_sha != previous['sha256']):
            raise CandidateAuditError('Candidate source identity mismatch')
        verified.append({
            'role': role, 'kind': kind, 'basename': name, 'bytes': actual_size,
            'sha256': actual_sha, 'upstream_git_blob_sha1': actual_blob,
            'release_approved': False,
        })
        if kind == 'license':
            notice_bytes = path.read_bytes()
            if (len(notice_bytes) != actual_size or
                    hashlib.sha256(notice_bytes).hexdigest() != actual_sha):
                raise CandidateAuditError('OFL changed during review')
            notes[role] = inspect_ofl_notice(notice_bytes)
    if len(verified) != 6 or set(notes) != set(ROLES):
        raise CandidateAuditError('Incomplete font or OFL review')
    source_assets = []
    for role in ROLES:
        item = by_role[role]
        p, lp = (PurePosixPath(item.get('relative_path', '')),
                 PurePosixPath(item.get('license_path', '')))
        if (len(p.parts) != 3 or p.parts[0] != 'ofl' or
                p.name != item['filename'] or len(lp.parts) != 3 or
                lp.parts[:2] != p.parts[:2] or lp.name != 'OFL.txt'):
            raise CandidateAuditError('Unexpected candidate source or licence path')
        source_assets.append({
            'role': role,
            'upstream_font_path': item['relative_path'],
            'upstream_ofl_path': item['license_path'],
            'candidate_status': item['status'],
            'original_notice_indicators': notes[role],
            'static_face_or_variable_font_decision': 'REVIEW_REQUIRED',
            'reportlab_pdf_visual_review': 'NOT_TESTED',
            'distribution_authority': 'NOT_GRANTED',
        })
    return {
        'state': SAFE_STATE,
        'schema': 1, 'source_repo': 'google/fonts',
        'source_commit': manifest['source_commit'],
        'verified_candidate_file_count': 6,
        'candidate_bytes': verified,
        'candidate_families': source_assets,
        'candidate_sha256_is_release_pin': False,
        'release_font_approval': 'NOT_GRANTED',
        'release_manifest': 'NOT_CREATED',
        'production_unicode_pdf': 'VISUAL_FAIL',
        'product_acceptance': 'NOT_TESTED',
        'installer': 'NOT_TESTED',
        'next_gate': 'INDEPENDENT_FONT_LICENSE_FACE_AND_DISTRIBUTION_DECISION',
    }


def main() -> int:
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
        result = build_readiness_dossier(manifest)
    except Exception as exc:
        result = {
            'state': 'BLOCKED', 'stage': 'candidate_dossier_verification',
            'failure_class': type(exc).__name__,
            'release_font_approval': 'NOT_GRANTED',
            'production_unicode_pdf': 'VISUAL_FAIL',
            'product_acceptance': 'NOT_TESTED',
        }
    print('P2 RELEASE FONT READINESS DEVQA: ' + result['state'])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['state'] == SAFE_STATE else 2


if __name__ == '__main__':
    raise SystemExit(main())
