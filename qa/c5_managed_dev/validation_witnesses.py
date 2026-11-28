"""C-D09 conditional validation witnesses. No live activation or acquisition."""
import hashlib
import json
import os
import re
from pathlib import Path
import stat
import sys

LIVE_ENABLED = False
ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PIN = '7d89ba820429b2005f7a70cc1b5ed1415f7b1161'
FONT_PIN = '73c49622be94353123af3dd99fe88326c0696cdd'
LOCK_PIN = '845bc92192a1b77432f4d472c7a056f47ca3a3a7'
COVERAGE = dict.fromkeys(('latin', 'greek', 'cyrillic', 'rupee', 'cjk'), 'EXTRACTED_EXACT')
COVERAGE.update(emoji='MISMATCH', mixed='MISMATCH')
MODES = ('unit', 'baseline', 'corrected', 'actual', 'context', 'coverage', 'research')
FONT_NODES = ('font:scoped_cmap_unit', 'font:baseline_extraction_mismatch',
              'font:corrected_extraction_exact', 'font:same_engine_rgb_identity',
              'font:actual_unicode_exact', 'font:actual_unicode_continuation',
              'font:actual_unicode_line_bounds', 'font:context_order_and_bounds',
              'font:coverage_outcomes', 'font:tounicode_research')
FRONTEND_NODES = ('frontend:offline_install', 'frontend:installed_lock_identity',
                  'frontend:typescript', 'frontend:vite_build')


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def require_live():
    need(LIVE_ENABLED is True, 'C5_VALIDATION_WITNESSES_DISARMED')
    need(os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'HOSTED_SCOPE')


def blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'DUPLICATE_JSON_KEY'); result[key] = value
        return result
    need(len(raw) <= 2 * 1024**2, 'JSON_CAP')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: need(False, 'NONFINITE_JSON'))


def read_plan(raw):
    need(blob(raw) == MANIFEST_PIN, 'MANIFEST_PIN')
    plan = strict_json(raw)
    need(len(plan['source_overlay']['paths']) == 29 and len(plan['stage_a']['expected_node_ids']) == 19, 'PLAN_SCOPE')
    need([len(plan['stage_b'][k]) for k in ('regular_modules', 'contract_modules', 'selected_nodes')] == [10, 3, 6], 'PLAN_STAGE_B')
    return plan


def stage_commands(plan, python):
    base = (str(python), '-B', '-m', 'pytest', '-p', 'no:cacheprovider', '--strict-markers', '-q')
    stage = plan['stage_b']
    return base + (plan['stage_a']['test_file'],), tuple(base + (path,) for path in
        stage['regular_modules'] + stage['contract_modules'] + stage['selected_nodes'])


def owned(path, root):
    path, root = Path(path), Path(root)
    need(path.is_absolute() and root.is_absolute() and path.resolve().is_relative_to(root.resolve()), 'OWNED_PATH')
    need(not any(p.is_symlink() or getattr(os.path, 'isjunction', lambda _: False)(p) for p in (path, *path.parents)), 'LINKED_PATH')
    return path


def checked_bytes(path, size, sha256=None, git_blob=None):
    path = Path(path)
    st = path.lstat()
    need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size == size and 0 < size <= 32 * 1024**2, 'FILE_IDENTITY')
    with path.open('rb') as stream:
        raw = stream.read(size + 1)
    need(len(raw) == size and (sha256 is None or hashlib.sha256(raw).hexdigest() == sha256)
         and (git_blob is None or blob(raw) == git_blob), 'FILE_HASH')
    return raw


def host_scratch(scratch):
    path = owned(scratch, os.environ['RUNNER_TEMP'])
    need(path.resolve() != Path(os.environ['RUNNER_TEMP']).resolve() and
         not path.resolve().is_relative_to(ROOT.resolve()) and not ROOT.resolve().is_relative_to(path.resolve()), 'SCRATCH_SCOPE')
    return path


def profile_inputs(profile_id):
    raw = (ROOT / 'qa/c5_managed_dev/pdfium_use_candidate_20261127.json').read_bytes()
    plan = read_plan(raw)
    profile, = [p for p in plan['profiles'] if p['id'] == profile_id]
    return profile


def stage_fonts(profile_id, rows, disposition, extra, scratch):
    require_live()
    scratch = host_scratch(scratch); extra = host_scratch(extra)
    need(rows == profile_inputs(profile_id)['fonts'], 'FONT_PROFILE')
    need(disposition['font_equivalence'] == 'REVIEWED_PINNED_SIX_FILES' and disposition['font_coverage_expected'] == COVERAGE, 'FONT_AUTHORITY')
    need(len(rows) == 6 and len({r['filename'] for r in rows}) == 6 and
         {(r['kind'], r['role']) for r in rows} == {(k, role) for k in ('font', 'font_notice') for role in ('regular', 'cjk', 'symbol')}, 'FONT_SET')
    local = owned(Path(scratch) / 'localappdata', scratch)
    fonts = local / 'PilotODIN/DevQA/font-candidates'; fonts.mkdir(parents=True)
    for row in rows:
        name = row['filename']; need(Path(name).name == name and '/' not in name and '\\' not in name, 'FONT_NAME')
        approved = disposition['archives'][name]
        need(approved['use'] == 'REVIEWED' and approved['git_blob_sha1'] == row['git_blob_sha1'], 'FONT_USE')
        digest = approved['measured_sha256']
        need(re.fullmatch(r'[0-9a-f]{64}', digest), 'FONT_DIGEST')
        raw = checked_bytes(owned(Path(extra) / name, extra), row['bytes'], digest, row['git_blob_sha1'])
        with (fonts / name).open('xb') as stream:
            stream.write(raw)
        checked_bytes(fonts / name, row['bytes'], digest, row['git_blob_sha1'])
    return local, fonts


def font_mode(mode, fonts):
    require_live()
    need(mode in MODES, 'FONT_MODE')
    local = owned(os.environ['LOCALAPPDATA'], os.environ['RUNNER_TEMP'])
    fonts = owned(fonts, local)
    need(fonts == local / 'PilotODIN/DevQA/font-candidates', 'FONT_ROOT')
    raw = (ROOT / 'tools/p2_pdf_font_candidates.json').read_bytes()
    need(blob(raw) == FONT_PIN, 'FONT_MANIFEST_PIN')
    sys.path.insert(0, str(ROOT / 'tools'))
    from qa_foundation import safe_root
    from p2_pdf_font_build_preflight import audited_sources
    entries = audited_sources(safe_root(fonts, ROOT), strict_json(raw))
    from tools.pdf_test_inspection import require_pdfium
    require_pdfium()
    from p2_pdf_cmap_scoped_devqa import render_child, run_unit_worker
    from p2_pdf_unicode_context_devqa import (probe_in_memory, selected_review_sources,
        register_scoped_faces, verified_font_coverage, FONT_NAMES)
    from p2_pdf_font_coverage_probe import audit
    from p2_pdf_tounicode_research import local_experiment
    if mode == 'unit':
        return run_unit_worker()
    if mode in ('baseline', 'corrected'):
        return render_child(mode)
    if mode == 'context':
        return probe_in_memory(fonts, entries)
    if mode == 'coverage':
        paths = selected_review_sources(fonts, entries)
        return audit({'regular': paths['regular'], 'cjk': paths['cjk'], 'emoji': paths['symbol']})
    if mode == 'research':
        return local_experiment(fonts, strict_json(raw))
    from p2_actual_unicode_report_devqa import proof_bytes, synthetic_revision
    from backend.pdf_unicode_seam import UnicodePDFContext
    faces = register_scoped_faces(selected_review_sources(fonts, entries))
    _, evidence = proof_bytes(synthetic_revision(), UnicodePDFContext(FONT_NAMES, faces, verified_font_coverage(faces)))
    return evidence


def font_result(evidence):
    need(set(evidence) == set(MODES), 'FONT_MODE_SET')
    unit, baseline, corrected = (evidence[k] for k in MODES[:3])
    need(unit == {'state': 'PASS', 'expected': 9, 'executed': 9, 'failures': 0, 'errors': 0, 'skipped': 0}, 'CMAP_UNIT')
    need(baseline['exact'] is False and corrected['exact'] is True and re.fullmatch(r'[0-9a-f]{64}', baseline['pixel_sha256'])
         and baseline['pixel_sha256'] == corrected['pixel_sha256'] and baseline['reportlab_version'] == corrected['reportlab_version'] == '4.5.1', 'CMAP_EQUIVALENCE')
    actual = evidence['actual']
    need(all(actual[k] is True for k in ('real_backend_report_pdf', 'legacy_default_report_preserved',
         'unicode_title_narrative_table_chart', 'chart_metric_values_unchanged', 'immutable_revision_and_html',
         'footer_and_pages', 'page_bounds')), 'ACTUAL_REPORT_PREDICATE')
    need(type(actual['pages']) is int and 1 <= actual['pages'] <= 4, 'ACTUAL_REPORT_PAGES')
    context = evidence['context']
    need(context['state'] == 'SCOPED_FONT_CONTEXT_IN_MEMORY_PASS' and all(context[k] is True for k in
        ('paragraph_exact', 'vector_label_exact', 'one_page', 'page_bounds_ok')), 'FONT_CONTEXT')
    coverage = evidence['coverage']
    need(coverage['scope'] == 'DEVELOPER_PROBE_NOT_ACCEPTANCE' and
         {k: v['state'] for k, v in coverage['samples'].items()} == COVERAGE, 'FONT_COVERAGE_REGRESSION')
    research = evidence['research']
    need(research['state'] == 'RESEARCH_ONLY' and research['baseline_matches'] is False and
         research['corrected_matches'] is True and research['same_rendered_pixels'] is True and
         research['product_acceptance'] == research['visual_acceptance'] == 'NOT_TESTED', 'FONT_RESEARCH')
    return {'collected': list(FONT_NODES), 'passed': list(FONT_NODES), 'state': 'PASS'}


def font_witness(profile_id, python, scratch, env, disposition, rows, extra, run):
    require_live()
    local, fonts = stage_fonts(profile_id, rows, disposition, extra, scratch)
    evidence = {}
    for mode in MODES:
        home = owned(Path(scratch) / ('font-home-' + mode), scratch); home.mkdir()
        child = dict(env, LOCALAPPDATA=str(local), PILOTODIN_HOME=str(home), PYTHONPATH=str(ROOT),
                     GITHUB_ACTIONS=os.environ['GITHUB_ACTIONS'], GITHUB_RUN_ATTEMPT=os.environ['GITHUB_RUN_ATTEMPT'], RUNNER_TEMP=os.environ['RUNNER_TEMP'])
        reply = run((str(python), '-B', '-m', 'qa.c5_managed_dev.validation_witnesses', 'font', mode, str(fonts)), cwd=ROOT, env=child, seconds=180)
        evidence[mode] = strict_json(reply)
    return font_result(evidence)


def mixed_witness(python, scratch, env, run):
    require_live()
    from tools.qa_foundation import create_run
    from tools.p2_mixed_report_devqa import worker_status_path, simple_status
    scratch = host_scratch(scratch); scratch.mkdir()
    run_dir, _ = create_run(scratch / 'mixed', 'P2-MIXED-REPORT', ROOT)
    child = dict(env, PILOTODIN_HOME=str(run_dir / 'workspace'), PILOTODIN_DEVQA_RUN=str(run_dir), PYTHONPATH=str(ROOT), RL_invariant='1')
    result = {}
    for kind, count in (('contract', 3), ('mixed', 9)):
        run((str(python), '-B', str(ROOT / 'tools/p2_mixed_report_devqa.py'), '--worker', kind), cwd=ROOT, env=child, seconds=180)
        path = worker_status_path(run_dir, kind)
        reply = strict_json(checked_bytes(owned(path, scratch), path.stat().st_size))
        need(simple_status(reply, count) == 'PASS', 'MIXED_REFUSED')
        result['mixed:' + kind] = {'collected': reply['cases'], 'passed': reply['cases'], 'state': 'PASS'}
    return result


def installed_graph(work, expected):
    work = Path(work); modules = owned(work / 'node_modules', work)
    observed = {}
    for entry in modules.iterdir():
        if entry.name in ('.bin', '.package-lock.json'):
            continue
        need(owned(entry, work).is_dir(), 'INSTALLED_PATH')
        for package in entry.iterdir() if entry.name.startswith('@') else [entry]:
            need(owned(package, work).is_dir(), 'INSTALLED_PATH')
            path = owned(package / 'package.json', work)
            doc = strict_json(checked_bytes(path, path.stat().st_size))
            key = package.relative_to(work).as_posix()
            need(doc['name'] == key[len('node_modules/'):], 'INSTALLED_NAME')
            observed[key] = doc['version']
    need(observed == expected, 'INSTALLED_GRAPH')
    return observed


def frontend_witness(profile_id, node, npm_cli, work, scratch, env, rows, extra, disposition, run):
    require_live()
    scratch = host_scratch(scratch); work = owned(work, scratch); extra = owned(extra, scratch)
    need(rows == profile_inputs(profile_id)['npm_archives'], 'NPM_PROFILE')
    need(Path(node).is_absolute() and Path(npm_cli).is_absolute(), 'NODE_TOOL_PATH')
    need(len(rows) == len({r['id'] for r in rows}) == 30 and not (work / 'node_modules').exists(), 'NPM_INPUT_SET')
    lock = work / 'package-lock.json'; original = checked_bytes(lock, lock.stat().st_size, git_blob=LOCK_PIN)
    for row in rows:
        approved = disposition['archives'][row['filename']]
        need(approved['use'] == 'REVIEWED' and approved['sha512'] == row['sha512'], 'NPM_USE')
        raw = checked_bytes(owned(extra / row['filename'], extra), row['bytes'])
        need(hashlib.sha512(raw).hexdigest() == row['sha512'], 'NPM_ARCHIVE_HASH')
    cache = Path(scratch) / 'npm-cache'; cache.mkdir()
    config = Path(scratch) / 'npmrc'; config.touch(exist_ok=False)
    child = dict(env, PATH=str(Path(node).parent), NPM_CONFIG_USERCONFIG=str(config), NPM_CONFIG_GLOBALCONFIG=str(config), NPM_CONFIG_CACHE=str(cache),
                 NPM_CONFIG_OFFLINE='true', NPM_CONFIG_IGNORE_SCRIPTS='true', NPM_CONFIG_AUDIT='false', NPM_CONFIG_FUND='false',
                 NPM_CONFIG_UPDATE_NOTIFIER='false', PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD='1')
    need(run((str(node), '--version'), cwd=work, env=child, seconds=10).strip() == b'v22.23.5', 'NODE_VERSION')
    base = (str(node), str(npm_cli))
    need(run(base + ('--version',), cwd=work, env=child, seconds=10).strip() == b'10.9.9', 'NPM_VERSION')
    flags = ('--offline', '--ignore-scripts', '--no-audit', '--no-fund', '--cache', str(cache))
    for row in rows:
        path = owned(extra / row['filename'], extra)
        raw = checked_bytes(path, row['bytes'])
        need(hashlib.sha512(raw).hexdigest() == row['sha512'], 'NPM_ARCHIVE_HASH')
        run(base + ('cache', 'add', str(path), *flags), cwd=work, env=child, seconds=60)
    run(base + ('ci', *flags), cwd=work, env=child, seconds=180)
    expected = {r['id']: r['version'] for r in rows}
    installed_graph(work, expected)
    modules = work / 'node_modules'
    run((str(node), str(work / 'scripts/verify-npm-lock.mjs'), *(('--installed',) if os.name == 'nt' else ())), cwd=work, env=child, seconds=60)
    run((str(node), str(modules / 'typescript/bin/tsc'), '--noEmit'), cwd=work, env=child, seconds=180)
    run((str(node), str(modules / 'vite/bin/vite.js'), 'build'), cwd=work, env=child, seconds=180)
    need(lock.read_bytes() == original, 'NPM_LOCK_MUTATION')
    installed_graph(work, expected)
    return {'collected': list(FRONTEND_NODES), 'passed': list(FRONTEND_NODES), 'state': 'PASS'}


def stage_a_eligible(plan, report, profile, generation, source, disposition_sha256):
    need(re.fullmatch(r'[0-9a-f]{64}', generation) and re.fullmatch(r'[0-9a-f]{40}', source)
         and re.fullmatch(r'[0-9a-f]{64}', disposition_sha256), 'GENERATION_IDENTITY')
    need(set(report) == {'profile', 'generation', 'source', 'stage', 'state', 'collected', 'passed',
         'failed', 'skipped', 'xfailed', 'native_sha256', 'pre_use_disposition_sha256'}, 'STAGE_A_FIELDS')
    need((report['profile'], report['generation'], report['source'], report['stage'], report['state']) ==
         (profile['id'], generation, source, 'A', 'PASS'), 'STAGE_A_IDENTITY')
    expected = {plan['stage_a']['test_file'] + '::' + n for n in plan['stage_a']['expected_node_ids']}
    need(len(expected) == 19 and all(len(report[k]) == 19 and set(report[k]) == expected for k in ('collected', 'passed'))
         and report['failed'] == report['skipped'] == report['xfailed'] == [], 'STAGE_A_CASES')
    wheel, = [r for r in profile['wheels'] if r['name'] == 'pypdfium2']
    native, = wheel['native']
    need(report['native_sha256'] == native['sha256'] and report['pre_use_disposition_sha256'] == disposition_sha256, 'STAGE_A_NATIVE_OR_USE')


def terminal_profile(plan, receipt, profile, generation, source, disposition_sha256):
    need(set(receipt) == {'profile', 'generation', 'source', 'attempt', 'state', 'stage_a', 'stage_b',
         'archive_uses', 'body_bytes', 'requests', 'cleanup'}, 'TERMINAL_FIELDS')
    need((receipt['profile'], receipt['generation'], receipt['source'], receipt['state'], receipt['cleanup']) ==
         (profile['id'], generation, source, 'PASS', 'OWNED_SCRATCH_REMOVED') and type(receipt['attempt']) is int and receipt['attempt'] == 1, 'TERMINAL_IDENTITY')
    stage_a_eligible(plan, receipt['stage_a'], profile, generation, source, disposition_sha256)
    b = plan['stage_b']; selectors = b['regular_modules'] + b['contract_modules'] + b['selected_nodes']
    expected = selectors + ['mixed:contract', 'mixed:mixed', 'font:equivalence', 'frontend:compatibility']
    need(set(receipt['stage_b']) == set(expected), 'STAGE_B_SET')
    all_nodes = set()
    for key in expected:
        row = receipt['stage_b'][key]; nodes = row['collected']
        need(set(row) == {'collected', 'passed', 'state'} and row['state'] == 'PASS' and isinstance(nodes, list)
             and nodes and all(isinstance(n, str) and n for n in nodes) and len(set(nodes)) == len(nodes)
             and row['passed'] == nodes and not all_nodes.intersection(nodes), 'STAGE_B_NODES')
        all_nodes.update(nodes)
        if key in selectors:
            need(all(n == key or n.startswith(key + '::') or ('::' in key and n.startswith(key + '[')) for n in nodes), 'FOREIGN_NODE')
        elif key.startswith('mixed:'):
            need(len(nodes) == (3 if key == 'mixed:contract' else 9), 'MIXED_COUNT')
        else:
            need(tuple(nodes) == (FONT_NODES if key == 'font:equivalence' else FRONTEND_NODES), 'WITNESS_SET')
    bounds = profile['application_bounds']
    need(all(type(receipt[k]) is int for k in ('archive_uses', 'requests', 'body_bytes')) and
         receipt['archive_uses'] == receipt['requests'] == bounds['archive_uses'] == 86 and
         receipt['body_bytes'] == bounds['body_bytes'], 'TERMINAL_BUDGET')


def linux_eligible(plan, windows, generation, source, disposition_sha256):
    need(plan['profiles'][0]['id'] == 'windows-x64-cp311-source-test', 'WINDOWS_FIRST')
    terminal_profile(plan, windows, plan['profiles'][0], generation, source, disposition_sha256)


def final_eligible(plan, receipts, generation, source, disposition_sha256):
    need(len(receipts) == 2 and [p['id'] for p in plan['profiles']] ==
         ['windows-x64-cp311-source-test', 'linux-x64-cp311-source-test'], 'TERMINAL_SET')
    for profile, receipt in zip(plan['profiles'], receipts):
        terminal_profile(plan, receipt, profile, generation, source, disposition_sha256)


if __name__ == '__main__':
    require_live()
    need(len(sys.argv) == 4 and sys.argv[1] == 'font', 'FONT_ARGUMENTS')
    print(json.dumps(font_mode(sys.argv[2], sys.argv[3]), ensure_ascii=True, sort_keys=True))
