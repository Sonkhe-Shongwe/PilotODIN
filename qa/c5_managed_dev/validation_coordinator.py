"""C-D09 conditional source validation coordinator; disarmed, no transport or installer."""
from pathlib import Path
import re

from . import validation_witnesses as w

LIVE_ENABLED = False
SMOKE = frozenset(('iniconfig', 'packaging', 'pillow', 'pluggy', 'pygments', 'pypdfium2', 'pytest'))
RECEIPT_FIELDS = {'collected', 'passed', 'failed', 'skipped', 'xfailed', 'exitstatus', 'mode'}


def split_inputs(plan, profile):
    w.need(profile in plan['profiles'], 'PROFILE')
    names = SMOKE | ({'colorama'} if profile['id'].startswith('windows-') else set())
    a = [r for r in profile['wheels'] if r['name'] in names]
    b = [r for r in profile['wheels'] if r['name'] not in names]
    w.need(len(a) == len(names) and {r['name'] for r in a} == names and len(a+b) == 49, 'WHEEL_SPLIT')
    rows = [profile['pip'], *a, *b, *profile['fonts'], *profile['npm_archives']]
    w.need(len(rows) == len({r['filename'] for r in rows}) == 86
           and len({r['url'] for r in rows}) == 86
           and sum(r['bytes'] for r in rows) == profile['application_bounds']['body_bytes'], 'INPUT_BUDGET')
    return a, b


def smoke_lock(rows):
    for row in rows:
        w.need(re.fullmatch(r'[a-z0-9-]+', row['name']) and re.fullmatch(r'[0-9A-Za-z.+!-]+', row['version'])
               and re.fullmatch(r'[0-9a-f]{64}', row['sha256']), 'SMOKE_LOCK')
    return ''.join(r['name']+'=='+r['version']+' --hash=sha256:'+r['sha256']+'\n' for r in rows)


def receipt_pair(collection, execution, selector, expected=None):
    for report, mode in ((collection, 'COLLECTION'), (execution, 'EXECUTION')):
        w.need(set(report) == RECEIPT_FIELDS and report['mode'] == mode
               and type(report['exitstatus']) is int and report['exitstatus'] == 0
               and report['failed'] == report['skipped'] == report['xfailed'] == [], 'PYTEST_REFUSED')
    nodes = collection['collected']
    w.need(isinstance(nodes, list) and nodes and len(nodes) == len(set(nodes))
           and all(isinstance(n, str) and (n == selector or n.startswith(selector+'::')
               or ('::' in selector and n.startswith(selector+'['))) for n in nodes), 'PYTEST_NODE_SCOPE')
    w.need(collection['passed'] == [] and execution['collected'] == execution['passed'] == nodes, 'PYTEST_DRIFT')
    if expected is not None:
        w.need(len(nodes) == len(expected) and set(nodes) == set(expected), 'PYTEST_EXPECTED_SET')
    return {'collected': nodes, 'passed': nodes, 'state': 'PASS'}


def pytest_witness(python, selector, scratch, env, run, expected=None):
    w.need(LIVE_ENABLED is True, 'VALIDATION_COORDINATOR_DISARMED')
    w.require_live()
    scratch = w.host_scratch(scratch)
    scratch.mkdir()
    home = scratch/'home'
    home.mkdir()
    base = (str(python), '-B', '-m', 'pytest', '-p', 'no:cacheprovider',
            '-p', 'qa.c5_managed_dev.pytest_receipt', '--strict-markers', '-q')
    reports = []
    for mode in ('COLLECTION', 'EXECUTION'):
        path = w.owned(scratch/(mode.lower()+'.json'), scratch)
        child = dict(env, PILOTODIN_HOME=str(home), PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                     C5_PDFIUM_TEST_STATUS=str(path), PYTHONPATH=str(w.ROOT))
        child.pop('PYTEST_ADDOPTS', None)
        child.pop('PYTEST_PLUGINS', None)
        run(base+(('--collect-only',) if mode == 'COLLECTION' else ())+(selector,),
            cwd=w.ROOT, env=child, seconds=180)
        reports.append(w.strict_json(w.checked_bytes(path, path.stat().st_size)))
    return receipt_pair(*reports, selector, expected)


def stage_a_report(plan, profile, result, native_sha, generation, source, disposition_sha):
    report = dict(result, profile=profile['id'], generation=generation, source=source, stage='A',
                  failed=[], skipped=[], xfailed=[], native_sha256=native_sha,
                  pre_use_disposition_sha256=disposition_sha)
    w.stage_a_eligible(plan, report, profile, generation, source, disposition_sha)
    return report


def run_profile(plan, profile, generation, source, disposition_sha, windows_receipt, operations):
    """Bind existing witnesses through future reviewed staging/run adapters.
    
    No acquisition, setup or process implementation here. The caller must
    establish exact source, pre-use rights, compatible tools and owned scratch.
    """
    w.need(LIVE_ENABLED is True, 'VALIDATION_COORDINATOR_DISARMED')
    w.require_live()
    a, b = split_inputs(plan, profile)
    if profile == plan['profiles'][1]:
        w.linux_eligible(plan, windows_receipt, generation, source, disposition_sha)
    else:
        w.need(profile == plan['profiles'][0] and windows_receipt is None, 'WINDOWS_FIRST')
    expected = [plan['stage_a']['test_file']+'::'+n for n in plan['stage_a']['expected_node_ids']]
    # No B preparation, download or installation before exact A acceptance.
    operations.prepare_a(profile, a, smoke_lock(a))
    native = operations.verify_native(profile)
    result = operations.pytest(plan['stage_a']['test_file'], expected)
    stage_a = stage_a_report(plan, profile, result, native, generation, source, disposition_sha)
    operations.prepare_b(profile, b)
    w.need(operations.verify_native(profile) == native, 'NATIVE_CHANGED')
    stage = plan['stage_b']
    outcome = {selector: operations.pytest(selector, None) for selector in
               stage['regular_modules'] + stage['contract_modules'] + stage['selected_nodes']}
    outcome.update(operations.mixed())
    outcome['font:equivalence'] = operations.font()
    outcome['frontend:compatibility'] = operations.frontend()
    counts = operations.finish_owned_scratch()
    receipt = dict(profile=profile['id'], generation=generation, source=source, attempt=1, state='PASS',
                   stage_a=stage_a, stage_b=outcome, **counts)
    w.terminal_profile(plan, receipt, profile, generation, source, disposition_sha)
    return receipt


if __name__ == '__main__':
    raise SystemExit('VALIDATION_COORDINATOR_DISARMED')
