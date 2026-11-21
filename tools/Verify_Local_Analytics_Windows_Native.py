"""Build and run the owner-approved, unpackaged Windows Local analytics check."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4
from zipfile import ZipFile

from Verify_Local_Analytics_Live_Dev import NoRedirects, ROOT, insist, measure


FRONTEND = ROOT / 'frontend'
TARGET = 'x86_64-pc-windows-msvc'
APP_ID = 'com.pilotodin.p4isolatednativedev'
APP_TITLE = 'PilotODIN P4 - ISOLATED NATIVE DEV (UNVERIFIED)'
APPROVAL = 'docs/P4_R03_OWNER_NATIVE_APPROVAL_2026-11-16.md'
APPROVED_SCOPE = 'scope=one-unpackaged-build-and-launch-model-free-local-analytics'
PORTS = (5173, 8000, 9331)
READY = 'http://127.0.0.1:8000'
HTTP = build_opener(ProxyHandler({}), NoRedirects())
FIXTURE = b'id,outcome,premium\n1,Yes,20\n2,No,\n3,Yes,40\n4,,50\n'
DRIVER = 'frontend/e2e/p4-r03-owner-native.mjs'
SAMPLER = 'tools/Measure_Local_Analytics_Windows_Native.ps1'
CLOSE_HELPER = 'qa/p4_native/Close_P4_Verified_Window.ps1'


def plain(command, **kwargs):
    return subprocess.check_output(command, text=True, timeout=20, **kwargs).strip()


def preflight(reuse=False):
    insist(sys.platform == 'win32', 'This check runs on the owner Windows laptop.')
    sha = plain(['git','rev-parse','HEAD'], cwd=ROOT)
    approval = plain(['git','show',f'{sha}:{APPROVAL}'], cwd=ROOT,encoding='utf-8').splitlines()
    source = next((line.partition('=')[2] for line in approval if line.startswith('reviewed_application_source=')), '')
    insist(APPROVED_SCOPE in approval,
           'Native session approval record does not match the test scope.')
    insist(re.fullmatch(r'[0-9a-f]{40}',source), 'The approval record needs the reviewed source SHA.')
    ancestry = subprocess.run(['git','merge-base','--is-ancestor',source,sha],cwd=ROOT,timeout=20)
    insist(ancestry.returncode == 0, 'Pull the reviewed Native QA source from the development branch.')
    python = ROOT / '.venv-live/Scripts/python.exe'
    insist(python.is_file() and (FRONTEND / 'node_modules/@playwright/test/package.json').is_file()
           and (FRONTEND / 'node_modules/vite/bin/vite.js').is_file(),
           'The existing Live Dev Python and frontend dependencies are required.')
    required = ('node','powershell.exe') if reuse else ('cargo','rustc','node','powershell.exe')
    tools = {program:shutil.which(program) for program in required}
    missing = [program for program,path in tools.items() if not path]
    insist(not missing, 'Missing Windows build tools: '+', '.join(missing))
    if not reuse:
        insist(f'host: {TARGET}' in plain([tools['rustc'],'-vV']), 'Rust must use the Windows x64 MSVC toolchain.')
    insist(int(plain([tools['node'],'--version']).lstrip('v').split('.')[0]) >= 20,
           'Node.js 20 or newer is required.')
    if not reuse and not shutil.which('link.exe'):
        x86 = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'))
        vswhere = x86 / 'Microsoft Visual Studio/Installer/vswhere.exe'
        insist(vswhere.is_file() and plain([str(vswhere),'-latest','-products','*','-requires',
            'Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath']),
            'The Microsoft C++ x64 build tools and Windows SDK are required.')
    powershell = tools['powershell.exe']
    insist(plain([powershell,'-NoProfile','-NonInteractive','-Command',
                  '[bool](Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)']) == 'True',
           'Windows TCP listener attribution is unavailable.')
    for port in (PORTS[:2] if reuse else PORTS):
        with socket.socket() as check:
            check.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                check.bind(('127.0.0.1', port))
            except OSError as exc:
                raise ValueError(f'Loopback port {port} is in use. Close the running Live Dev or QA consoles first.') from exc
    return python, tools, sha, source


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def prior_build(temp, name, source):
    insist(re.fullmatch(r'pilotodin-r03-native-[a-z0-9_]{8}', name), 'Use the prior run folder name printed in PowerShell.')
    prior = temp / name
    receipt = prior / 'result.json'
    binary = prior / 'cargo' / TARGET / 'debug/pilotodin-desktop.exe'
    lock = prior / 'source/frontend/src-tauri/Cargo.lock'
    for path in (receipt,binary,lock):
        insist(all(not part.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
                   for part in (path,*path.parents) if part != temp and temp in part.parents),
               'The previous run contains a redirected path.')
    record = json.loads(receipt.read_text(encoding='utf-8'))
    insist(record['status'] == 'INCOMPLETE' and record['stage'] == 'native_launch'
           and record['scope'] == 'unpackaged_windows_webview2_with_disposable_dev_backend'
           and record['reviewed_application_source'] == source
           and record.get('failure','').endswith('http://127.0.0.1:9331/json/version')
           and re.fullmatch(re.escape(APP_ID)+r'\.[0-9a-f]{32}', record['app_identifier']),
           'The previous receipt does not match the reviewed WebView2 startup failure.')
    insist(digest(binary) == record['executable_sha256'] and digest(lock) == record['cargo_lock_sha256'],
           'The previous executable or Cargo lockfile no longer matches its run receipt.')
    return binary, record


def configure(crate):
    insist(not any(os.path.lexists(crate / name) for name in
                   ('tauri.windows.conf.json','tauri.windows.conf.json5','Tauri.windows.toml')),
           'Unexpected Windows Tauri configuration override in the reviewed source.')
    production, previous, qa = [json.loads((crate / name).read_text(encoding='utf-8')) for name in
        ('tauri.conf.json','tauri.p4-native-qa.conf.json','tauri.p4-isolated-native-dev.conf.json')]
    insist([production['identifier'],previous['identifier'],qa['identifier']] ==
           ['com.pilotodin.studio','com.pilotodin.p4nativeqa',APP_ID], 'Unexpected application identifiers.')
    insist(qa['bundle'] == {'active':False,'externalBin':[],'resources':[]}
           and not any('appDirectoriesOverride' in conf['app'] for conf in (production,qa))
           and production['build']['devUrl'] == 'http://127.0.0.1:5173'
           and qa['app']['windows'][0]['title'] == APP_TITLE, 'Unexpected native build configuration.')
    qa['identifier'] += '.'+uuid4().hex
    return qa


def stage_source(run, source, harness):
    workspace = run / 'source'
    workspace.mkdir()
    for label, revision, paths in (
        ('application', source, ('backend', 'frontend')),
        ('harness', harness, (DRIVER, SAMPLER, CLOSE_HELPER)),
    ):
        archive = run / (label+'.zip')
        subprocess.run(['git','archive','--format=zip','--output',str(archive),revision,'--',*paths],
                       cwd=ROOT,check=True,timeout=90)
        with ZipFile(archive) as snapshot:
            for item in snapshot.infolist():
                parts = item.filename.rstrip('/').split('/')
                insist(all(part and part not in ('.','..') and ':' not in part and '\\' not in part
                           for part in parts) and not stat.S_ISLNK(item.external_attr >> 16),
                       'Unexpected path or symlink in the reviewed source.')
                insist(item.is_dir() or not (workspace / item.filename).exists(),
                       'The staged Git snapshots contain overlapping files.')
            snapshot.extractall(workspace)
        archive.unlink()
    return workspace


def stop(process, *, tree=False):
    if process.poll() is None:
        if tree and sys.platform == 'win32':
            taskkill = Path(os.environ['SystemRoot']) / 'System32/taskkill.exe'
            subprocess.run([str(taskkill),'/PID',str(process.pid),'/T','/F'],
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=15)


def require_profile_root(profile):
    insist(profile.is_dir() and not profile.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT,
           'The WebView2 profile does not match the disposable folder.')


def spawn(stack, run, role, command, directory, env):
    with (run / (role+'.log')).open('xb') as log:
        process = subprocess.Popen([str(part) for part in command], cwd=directory, env=env,
                                   stdout=log, stderr=subprocess.STDOUT)
    stack.callback(stop, process, tree=role in ('backend','vite','desktop'))
    return process


def wait_http(url, process, timeout=45):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline and process.poll() is None:
        try:
            with HTTP.open(url,timeout=1) as reply:
                if reply.status == 200:
                    return
        except (URLError, TimeoutError):
            time.sleep(.4)
    raise ValueError('The expected service exited or did not respond on '+url)


def require_listener(powershell, port, process, *, allow_child=False):
    # The Windows virtual-environment Python launcher can own a Python child.
    command = (
        f'$listeners = @(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction Stop); '
        'if ($listeners.Count -eq 1 -and $listeners[0].LocalAddress -eq "127.0.0.1") { '
        '$listeners[0].OwningProcess; '
        f'if ($listeners[0].OwningProcess -ne {process.pid}) {{ '
        '(Get-CimInstance Win32_Process -Filter ("ProcessId = " + $listeners[0].OwningProcess) '
        '-ErrorAction Stop).ParentProcessId } }'
    )
    ids = plain([powershell,'-NoProfile','-NonInteractive','-Command',command]).splitlines()
    insist(process.poll() is None and (
        ids == [str(process.pid)] or
        (allow_child and len(ids) == 2 and ids[0].isdigit() and ids[1] == str(process.pid))
    ),
           f'Port {port} is not owned by the expected disposable service.')
    return int(ids[0])


def import_fixture():
    boundary = 'pilotodin-r03-'+uuid4().hex
    part = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="r03-native.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n').encode()
    req = Request(READY+'/api/projects',part+FIXTURE+f'\r\n--{boundary}--\r\n'.encode(),
                  {'Content-Type':'multipart/form-data; boundary='+boundary})
    with HTTP.open(req,timeout=15) as reply:
        return json.load(reply)['id']


def memory(powershell, script, profile, backend_id=0, app=None):
    return json.loads(plain([powershell,'-NoProfile','-NonInteractive','-File',str(script),
                             '-ProfilePath',str(profile),'-BackendId',str(backend_id),
                             '-AppId',str(app.pid if app else 0)]))


def close_window(powershell, script, binary, app):
    # Invoke the existing identity-checked Windows close helper.
    env = {**os.environ,'PILOTODIN_R03_CLOSE_SCRIPT':str(script),'PILOTODIN_R03_CLOSE_EXE':str(binary),
           'PILOTODIN_R03_CLOSE_PID':str(app.pid),'PILOTODIN_R03_CLOSE_TITLE':APP_TITLE}
    subprocess.run([powershell,'-NoProfile','-NonInteractive','-Command',
                    '. $env:PILOTODIN_R03_CLOSE_SCRIPT; Close-P4VerifiedWindow '
                    '-AppProcessId ([int]$env:PILOTODIN_R03_CLOSE_PID) '
                    '-ExpectedPath $env:PILOTODIN_R03_CLOSE_EXE -ExpectedTitle $env:PILOTODIN_R03_CLOSE_TITLE'],
                   env=env,check=True,timeout=25)
    insist(app.wait(timeout=5) == 0, 'The QA app did not exit normally.')


def manual_check(app, backend, vite, sample):
    import msvcrt

    print('\nIn the PilotODIN window, select r03-native and open Ask ODIN. Choose Local analytics.\n'
          'Ask: What is the median premium for Yes outcomes?\n'
          'Expected: 30 from two usable values.\n'
          'Immediately ask: What about No?\n'
          'Expected: median unavailable, one matching row, zero usable values.\n'
          'Leave the test window open. Return to this terminal and press P if both matched, or F if either failed.\n',
          flush=True)
    deadline = time.monotonic()+300
    next_sample = 0
    while time.monotonic() < deadline:
        insist(all(proc.poll() is None for proc in (app,backend,vite)),
               'A test process exited before the native UI observation was recorded.')
        if time.monotonic() >= next_sample:
            sample()
            next_sample = time.monotonic()+3
        if msvcrt.kbhit():
            result = msvcrt.getwch().upper()
            if result == 'P':
                return
            insist(result != 'F', 'The owner did not confirm both native UI answers.')
        time.sleep(.2)
    raise ValueError('No owner observation was received within five minutes.')


def session(run, python, tools, report, previous=None):
    report['stage'] = 'stage_source'
    workspace = stage_source(run,report['reviewed_application_source'],report['checkout_sha'])
    frontend = workspace / 'frontend'
    crate = frontend / 'src-tauri'
    sampler = workspace / SAMPLER
    config = configure(crate)
    profile = run / 'webview'
    env = {key:value for key,value in os.environ.items() if not key.upper().startswith(('PILOTODIN_','WEBVIEW2_','VITE_'))
           and key.upper() not in ('TAURI_CONFIG','CARGO_TARGET_DIR','GEMINI_API_KEY','GROQ_API_KEY','OPENROUTER_API_KEY',
                                   'PYTHONPATH','PYTHONHOME','NODE_PATH','NODE_OPTIONS')}
    env.update(PILOTODIN_HOME=str(run/'data'), PYTHONDONTWRITEBYTECODE='1', VITE_PILOTODIN_NATIVE_SMOKE='1')
    report['app_identifier'] = previous[1]['app_identifier'] if previous else config['identifier']
    if not previous:
        for key in ('LOCALAPPDATA','APPDATA'):
            insist(not (Path(env[key]) / config['identifier']).exists(), 'The isolated app identity is already in use.')

    powershell = tools['powershell.exe']
    samples = report['memory_samples']
    report['stage'] = 'stage_dependencies'
    # Reuse the installed Live Dev packages, with a separate Vite cache.
    shutil.copytree(FRONTEND/'node_modules',frontend/'node_modules',
                    ignore=shutil.ignore_patterns('.vite','.vite-temp'))
    if previous:
        binary, prior = previous
        report['executable_sha256'] = prior['executable_sha256']
        report['cargo_lock_sha256'] = prior['cargo_lock_sha256']
        report['launch_mode'] = 'reused_executable_no_cdp'
    else:
        samples.append({'stage':'before_compile',**memory(powershell,sampler,profile)})
        binary = compile_native(run, crate, config, env, tools['cargo'], report)
    report['stage'] = 'runtime'
    samples.append({'stage':'before_runtime',**memory(powershell,sampler,profile)})
    run_native(run, workspace, profile, binary, python, tools, env, report, manual=previous is not None)


def compile_native(run, crate, config, env, cargo_path, report):
    target = run / 'cargo'
    report['stage'] = 'compile'
    print('Compiling one unpackaged Tauri build. Keep this window open.', flush=True)
    build_env = {**env,'TAURI_CONFIG':json.dumps(config),'CARGO_TARGET_DIR':str(target),'CARGO_BUILD_JOBS':'2'}
    lockfile = crate / 'Cargo.lock'
    previously_locked = lockfile.exists()
    with (run/'compile.log').open('xb') as log:
        with subprocess.Popen([cargo_path,'build','--bin','pilotodin-desktop','--target',TARGET,
                               '--target-dir',str(target),*(('--locked',) if previously_locked else ())],
                              cwd=crate,env=build_env,stdout=log,stderr=subprocess.STDOUT) as cargo:
            try:
                started = time.monotonic()
                while cargo.poll() is None:
                    try:
                        cargo.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        seconds = round(time.monotonic()-started)
                        insist(seconds < 3600, 'Compilation exceeded the one-hour test window.')
                        print(f'Compilation still running after {seconds}s. See compile.log for progress.',flush=True)
                insist(cargo.returncode == 0, 'Native compilation failed. Inspect compile.log.')
            finally:
                stop(cargo)
    binary = target / TARGET / 'debug/pilotodin-desktop.exe'
    report['executable_sha256'] = digest(binary)
    report['cargo_lock_sha256'] = digest(lockfile)
    return binary


def run_native(run, workspace, profile, binary, python, tools, env, report, *, manual):
    frontend = workspace / 'frontend'
    sampler = workspace / SAMPLER
    powershell = tools['powershell.exe']
    samples = report['memory_samples']
    with ExitStack() as stack:
        backend = spawn(stack,run,'backend',[python,'-m','uvicorn','backend.main:app','--host','127.0.0.1',
                        '--port','8000','--no-access-log'],workspace,env)
        wait_http(READY+'/api/health',backend)
        backend_id = require_listener(powershell,8000,backend,allow_child=True)
        with HTTP.open(READY+'/api/projects',timeout=5) as response:
            insist(json.load(response) == [], 'The backend does not have an empty disposable project catalogue.')
        project = import_fixture()
        vite = spawn(stack,run,'vite',[tools['node'],frontend/'node_modules/vite/bin/vite.js',
                     '--host','127.0.0.1','--port','5173','--strictPort'],frontend,env)
        wait_http('http://127.0.0.1:5173/',vite)
        require_listener(powershell,5173,vite)
        report['stage'] = 'native_launch'
        print('Opening the isolated native window and checking Ask ODIN.', flush=True)
        app_env = {**env,'WEBVIEW2_USER_DATA_FOLDER':str(profile)}
        if not manual:
            app_env['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = (
                '--remote-debugging-port=9331 --remote-debugging-address=127.0.0.1'
            )
        insist(digest(binary) == report['executable_sha256'], 'The native executable changed before launch.')
        app = spawn(stack,run,'desktop',[binary],binary.parent,app_env)
        if manual:
            deadline = time.monotonic()+45
            while True:
                insist(app.poll() is None and time.monotonic() < deadline,
                       'The app or its isolated WebView2 profile did not become ready.')
                ready = memory(powershell,sampler,profile,backend_id,app)
                if ready['webview']['processes'] > 0:
                    break
                time.sleep(.5)
        else:
            wait_http('http://127.0.0.1:9331/json/version',app)
            ready = memory(powershell,sampler,profile,backend_id,app)
        require_profile_root(profile)
        insist(ready['webview']['processes'] > 0 and (manual or ready['debugger_isolated']),
               'WebView2 or its debugger could not be attributed to the disposable profile.')
        samples.append({'stage':'native_ready',**ready})
        report['stage'] = 'native_questions'
        def sample_question():
            samples.append({'stage':'during_questions',**memory(powershell,sampler,profile,backend_id,app)})
        if manual:
            report['api_checks'] = measure(HTTP,'/projects/'+project)
            manual_check(app,backend,vite,sample_question)
            report['ui'] = {'mode':'owner_observation','checks':['filtered_median','filter_follow_up']}
        else:
            driver = spawn(stack,run,'driver',[tools['node'],workspace/DRIVER],frontend,
                           {**env,'PILOTODIN_R03_NATIVE_RUN':'approved-owner-session','PILOTODIN_R03_FIXTURE_ID':project})
            deadline = time.monotonic()+160
            while driver.poll() is None:
                insist(time.monotonic() < deadline and app.poll() is None and backend.poll() is None and vite.poll() is None,
                       'The native probe stalled or an owned process exited.')
                sample_question()
                time.sleep(.75)
            insist(driver.returncode == 0, 'Native UI assertions failed. Inspect driver.log.')
            report['ui'] = json.loads((run/'driver.log').read_text(encoding='utf-8').strip().splitlines()[-1])
        with HTTP.open(READY+'/api/projects/'+project,timeout=5) as response:
            insist(json.load(response)['experiments'] == [], 'Unexpected model experiment in disposable workspace.')
        time.sleep(3)
        samples.append({'stage':'cooldown',**memory(powershell,sampler,profile,backend_id,app)})
        active = [sample for sample in samples if sample['stage'] in ('native_ready','during_questions','cooldown')]
        insist(any(sample['stage'] == 'during_questions' for sample in active) and all(
            sample['backend']['processes'] == 1 and sample['desktop']['processes'] == 1
            and sample['webview']['processes'] > 0 and (manual or sample['debugger_isolated']) for sample in active
        ), 'The physical process measurements are incomplete.')
        report['memory_summary'] = {
            'minimum_sampled_available_mib':min(sample['available_mib'] for sample in active),
            'maximum_sampled_system_commit_mib':max(sample['system_commit_mib'] for sample in active),
            'maximum_sampled_pages_input_per_sec':max(sample['system_pages_input_per_sec'] for sample in active),
            'maximum_sampled_private_mib':{
                role:max(sample[role]['private_mib'] for sample in active) for role in ('backend','desktop','webview')
            },
        }
        report['stage'] = 'native_close'
        close_window(powershell,workspace/CLOSE_HELPER,binary,app)
    report['stage'] = 'complete'
    report['status'] = 'PASS_WITH_OWNER_OBSERVATION' if manual else 'PASS'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--run-approved',action='store_true',help='Run the reviewed physical Windows session')
    mode.add_argument('--relaunch-approved',metavar='PRIOR_RUN_FOLDER',
                      help='Explicitly approve and perform one relaunch of the verified executable')
    args = parser.parse_args()
    try:
        insist(not args.relaunch_approved or sys.stdin.isatty(), 'The relaunch requires an interactive owner terminal.')
        python,tools,sha,source = preflight(reuse=bool(args.relaunch_approved))
        temp = Path(tempfile.gettempdir()).absolute()
        insist(re.fullmatch(r'[A-Za-z]:\\',temp.anchor) and not any(
            path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT for path in (temp,*temp.parents)
        ), 'The Windows temp folder must be on a local drive without redirected folders.')
        previous = prior_build(temp,args.relaunch_approved,source) if args.relaunch_approved else None
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
        print(f'Windows native check blocked before compile: {error}',file=sys.stderr)
        return 2
    run = Path(tempfile.mkdtemp(prefix='pilotodin-r03-native-',dir=temp))
    report = {'status':'INCOMPLETE','scope':'unpackaged_windows_webview2_with_disposable_dev_backend',
              'checkout_sha':sha,'reviewed_application_source':source,'stage':'pre_runtime','memory_samples':[]}
    print(f'Private run logs: {run}',flush=True)
    try:
        session(run,python,tools,report,previous)
    except KeyboardInterrupt:
        report['failure'] = 'The owner stopped the session.'
    except (OSError,ValueError,KeyError,IndexError,subprocess.SubprocessError) as error:
        report['failure'] = str(error)
    with (run/'result.json').open('x',encoding='utf-8') as output:
        json.dump(report,output,indent=2)
    print(json.dumps(report,indent=2),flush=True)
    return 0 if report['status'] in ('PASS','PASS_WITH_OWNER_OBSERVATION') else 1


if __name__ == '__main__':
    sys.exit(main())
