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

from Verify_Local_Analytics_Live_Dev import NoRedirects, ROOT, checkout, insist


FRONTEND = ROOT / 'frontend'
CRATE = FRONTEND / 'src-tauri'
TARGET = 'x86_64-pc-windows-msvc'
APP_ID = 'com.pilotodin.p4isolatednativedev'
APP_TITLE = 'PilotODIN P4 - ISOLATED NATIVE DEV (UNVERIFIED)'
APPROVAL = ROOT / 'docs/P4_R03_OWNER_NATIVE_APPROVAL_2026-11-16.md'
APPROVED_SCOPE = 'scope=one-unpackaged-build-and-launch-model-free-local-analytics'
PORTS = (5173, 8000, 9331)
READY = 'http://127.0.0.1:8000'
HTTP = build_opener(ProxyHandler({}), NoRedirects())
FIXTURE = b'id,outcome,premium\n1,Yes,20\n2,No,\n3,Yes,40\n4,,50\n'


def plain(command, **kwargs):
    return subprocess.check_output(command, text=True, timeout=20, **kwargs).strip()


def preflight():
    insist(sys.platform == 'win32', 'This check runs on the owner Windows laptop.')
    approval = APPROVAL.read_text(encoding='utf-8').splitlines()
    source = next((line.partition('=')[2] for line in approval if line.startswith('reviewed_application_source=')), '')
    insist(APPROVED_SCOPE in approval,
           'Native session approval record does not match the test scope.')
    insist(re.fullmatch(r'[0-9a-f]{40}',source), 'The approval record needs the reviewed source SHA.')
    current = checkout()
    # The approval and harness may change documentation and QA files only.
    # The native executable and UI must come from the reviewed application tree.
    changed = plain(['git','diff','--name-only',source,'HEAD','--',
                     'backend','frontend',':(exclude)frontend/e2e',
                     ':(exclude)frontend/tests'], cwd=ROOT)
    insist(not current['checkout_tracked_changes'] and not changed,
           'Use the clean checkout containing the reviewed application source.')
    insist(not any(os.path.lexists(CRATE / name) for name in
                   ('tauri.windows.conf.json','tauri.windows.conf.json5','Tauri.windows.toml')),
           'Unexpected Windows Tauri configuration override.')
    untracked = plain(['git','ls-files','--others','--exclude-standard','--','backend','frontend',
                       ':(exclude)frontend/src-tauri/Cargo.lock'], cwd=ROOT)
    insist(not untracked, 'Untracked files in application source would make the build ambiguous.')
    python = ROOT / '.venv-live/Scripts/python.exe'
    insist(python.is_file() and (FRONTEND / 'node_modules/@playwright/test/package.json').is_file()
           and (FRONTEND / 'node_modules/vite/bin/vite.js').is_file(),
           'The existing Live Dev Python and frontend dependencies are required.')
    tools = {program:shutil.which(program) for program in ('cargo','rustc','node','powershell.exe')}
    missing = [program for program,path in tools.items() if not path]
    insist(not missing, 'Missing Windows build tools: '+', '.join(missing))
    insist(f'host: {TARGET}' in plain([tools['rustc'],'-vV']), 'Rust must use the Windows x64 MSVC toolchain.')
    insist(int(plain([tools['node'],'--version']).lstrip('v').split('.')[0]) >= 20,
           'Node.js 20 or newer is required.')
    if not shutil.which('link.exe'):
        x86 = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'))
        vswhere = x86 / 'Microsoft Visual Studio/Installer/vswhere.exe'
        insist(vswhere.is_file() and plain([str(vswhere),'-latest','-products','*','-requires',
            'Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath']),
            'The Microsoft C++ x64 build tools and Windows SDK are required.')
    powershell = tools['powershell.exe']
    insist(plain([powershell,'-NoProfile','-NonInteractive','-Command',
                  '[bool](Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)']) == 'True',
           'Windows TCP listener attribution is unavailable.')
    for port in PORTS:
        with socket.socket() as check:
            check.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                check.bind(('127.0.0.1', port))
            except OSError as exc:
                raise ValueError(f'Loopback port {port} is in use. Close the running Live Dev or QA consoles first.') from exc
    return python, tools, current['checkout_git_sha'], source


def configure():
    production, previous, qa = [json.loads((CRATE / name).read_text(encoding='utf-8')) for name in
        ('tauri.conf.json','tauri.p4-native-qa.conf.json','tauri.p4-isolated-native-dev.conf.json')]
    insist([production['identifier'],previous['identifier'],qa['identifier']] ==
           ['com.pilotodin.studio','com.pilotodin.p4nativeqa',APP_ID], 'Unexpected application identifiers.')
    insist(qa['bundle'] == {'active':False,'externalBin':[],'resources':[]}
           and not any('appDirectoriesOverride' in conf['app'] for conf in (production,qa))
           and production['build']['devUrl'] == 'http://127.0.0.1:5173'
           and qa['app']['windows'][0]['title'] == APP_TITLE, 'Unexpected native build configuration.')
    qa['identifier'] += '.'+uuid4().hex
    return qa


def stage_crate(run):
    # Cargo writes its resolved lockfile alongside the manifest. Keep that file
    # and any build-script output in the disposable workspace.
    destination = run / 'frontend/src-tauri'
    files = subprocess.check_output(
        ['git','ls-files','-z','--','frontend/src-tauri'],cwd=ROOT,
    ).decode('utf-8').split('\0')
    for name in filter(None,files):
        source = ROOT / name
        insist(source.is_file() and not source.is_symlink(), 'Native source file unavailable or redirected.')
        target = destination / source.relative_to(CRATE)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
    return destination


def stop(process):
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
    stack.callback(stop, process)
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


def require_listener(powershell, port, process):
    command = (
        f'@(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction Stop '
        f'| Where-Object {{ $_.LocalAddress -eq "127.0.0.1" -and $_.OwningProcess -eq {process.pid} }}).Count'
    )
    insist(process.poll() is None and plain([powershell,'-NoProfile','-NonInteractive','-Command',command]) == '1',
           f'Port {port} is not owned by the expected disposable service.')


def import_fixture():
    boundary = 'pilotodin-r03-'+uuid4().hex
    part = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="r03-native.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n').encode()
    req = Request(READY+'/api/projects',part+FIXTURE+f'\r\n--{boundary}--\r\n'.encode(),
                  {'Content-Type':'multipart/form-data; boundary='+boundary})
    with HTTP.open(req,timeout=15) as reply:
        return json.load(reply)['id']


def memory(powershell, profile, backend=None, app=None):
    script = Path(__file__).with_name('Measure_Local_Analytics_Windows_Native.ps1')
    return json.loads(plain([powershell,'-NoProfile','-NonInteractive','-File',str(script),
                             '-ProfilePath',str(profile),'-BackendId',str(backend.pid if backend else 0),
                             '-AppId',str(app.pid if app else 0)]))


def close_window(powershell, binary, app):
    script = ROOT / 'qa/p4_native/Close_P4_Verified_Window.ps1'
    # Invoke the existing identity-checked Windows close helper.
    env = {**os.environ,'PILOTODIN_R03_CLOSE_SCRIPT':str(script),'PILOTODIN_R03_CLOSE_EXE':str(binary),
           'PILOTODIN_R03_CLOSE_PID':str(app.pid),'PILOTODIN_R03_CLOSE_TITLE':APP_TITLE}
    subprocess.run([powershell,'-NoProfile','-NonInteractive','-Command',
                    '. $env:PILOTODIN_R03_CLOSE_SCRIPT; Close-P4VerifiedWindow '
                    '-AppProcessId ([int]$env:PILOTODIN_R03_CLOSE_PID) '
                    '-ExpectedPath $env:PILOTODIN_R03_CLOSE_EXE -ExpectedTitle $env:PILOTODIN_R03_CLOSE_TITLE'],
                   env=env,check=True,timeout=25)
    insist(app.wait(timeout=5) == 0, 'The QA app did not exit normally.')


def session(run, python, tools, report):
    config = configure()
    profile = run / 'webview'
    target = run / 'cargo'
    env = {key:value for key,value in os.environ.items() if not key.startswith(('PILOTODIN_','WEBVIEW2_','VITE_'))
           and key not in ('TAURI_CONFIG','CARGO_TARGET_DIR','GEMINI_API_KEY','GROQ_API_KEY','OPENROUTER_API_KEY')}
    env.update(PILOTODIN_HOME=str(run/'data'), PYTHONDONTWRITEBYTECODE='1', VITE_PILOTODIN_NATIVE_SMOKE='1')
    report['app_identifier'] = config['identifier']
    for key in ('LOCALAPPDATA','APPDATA'):
        insist(not (Path(env[key]) / config['identifier']).exists(), 'The isolated app identity is already in use.')

    powershell = tools['powershell.exe']
    samples = report['memory_samples']
    samples.append({'stage':'before_compile',**memory(powershell,profile)})
    report['stage'] = 'compile'
    print('Compiling one unpackaged Tauri build. Keep this window open.', flush=True)
    staged_crate = stage_crate(run)
    build_env = {**env,'TAURI_CONFIG':json.dumps(config),'CARGO_TARGET_DIR':str(target),'CARGO_BUILD_JOBS':'2'}
    lockfile = staged_crate / 'Cargo.lock'
    previously_locked = lockfile.exists()
    with (run/'compile.log').open('xb') as log:
        with subprocess.Popen([tools['cargo'],'build','--bin','pilotodin-desktop','--target',TARGET,
                               '--target-dir',str(target),*(('--locked',) if previously_locked else ())],
                              cwd=staged_crate,env=build_env,stdout=log,stderr=subprocess.STDOUT) as cargo:
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
    with binary.open('rb') as stream:
        report['executable_sha256'] = hashlib.file_digest(stream,'sha256').hexdigest()
    with lockfile.open('rb') as stream:
        report['cargo_lock_sha256'] = hashlib.file_digest(stream,'sha256').hexdigest()
    source = checkout()
    insist(source['checkout_git_sha'] == report['checkout_sha'] and not source['checkout_tracked_changes'],
           'Application checkout changed during compilation.')

    report['stage'] = 'runtime'
    samples.append({'stage':'before_runtime',**memory(powershell,profile)})
    with ExitStack() as stack:
        backend = spawn(stack,run,'backend',[python,'-m','uvicorn','backend.main:app','--host','127.0.0.1',
                        '--port','8000','--no-access-log'],ROOT,env)
        wait_http(READY+'/api/health',backend)
        require_listener(powershell,8000,backend)
        with HTTP.open(READY+'/api/projects',timeout=5) as response:
            insist(json.load(response) == [], 'The backend does not have an empty disposable project catalogue.')
        project = import_fixture()
        vite = spawn(stack,run,'vite',[tools['node'],FRONTEND/'node_modules/vite/bin/vite.js',
                     '--host','127.0.0.1','--port','5173','--strictPort'],FRONTEND,env)
        wait_http('http://127.0.0.1:5173/',vite)
        require_listener(powershell,5173,vite)
        report['stage'] = 'native_launch'
        print('Opening the isolated native window and checking Ask ODIN.', flush=True)
        app_env = {**env,'WEBVIEW2_USER_DATA_FOLDER':str(profile),
                   'WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS':'--remote-debugging-port=9331 --remote-debugging-address=127.0.0.1'}
        app = spawn(stack,run,'desktop',[binary],binary.parent,app_env)
        wait_http('http://127.0.0.1:9331/json/version',app)
        ready = memory(powershell,profile,backend,app)
        require_profile_root(profile)
        insist(ready['webview']['processes'] > 0 and ready['debugger_isolated'],
               'WebView2 or its debugger could not be attributed to the disposable profile.')
        samples.append({'stage':'native_ready',**ready})
        report['stage'] = 'native_questions'
        driver = spawn(stack,run,'driver',[tools['node'],FRONTEND/'e2e/p4-r03-owner-native.mjs'],FRONTEND,
                       {**env,'PILOTODIN_R03_NATIVE_RUN':'approved-owner-session','PILOTODIN_R03_FIXTURE_ID':project})
        deadline = time.monotonic()+160
        while driver.poll() is None:
            insist(time.monotonic() < deadline and app.poll() is None and backend.poll() is None and vite.poll() is None,
                   'The native probe stalled or an owned process exited.')
            samples.append({'stage':'during_questions',**memory(powershell,profile,backend,app)})
            time.sleep(.75)
        insist(driver.returncode == 0, 'Native UI assertions failed. Inspect driver.log.')
        report['ui'] = json.loads((run/'driver.log').read_text(encoding='utf-8').strip().splitlines()[-1])
        with HTTP.open(READY+'/api/projects/'+project,timeout=5) as response:
            insist(json.load(response)['experiments'] == [], 'Unexpected model experiment in disposable workspace.')
        time.sleep(3)
        samples.append({'stage':'cooldown',**memory(powershell,profile,backend,app)})
        active = [sample for sample in samples if sample['stage'] in ('native_ready','during_questions','cooldown')]
        insist(any(sample['stage'] == 'during_questions' for sample in active) and all(
            sample['backend']['processes'] == 1 and sample['desktop']['processes'] == 1
            and sample['webview']['processes'] > 0 and sample['debugger_isolated'] for sample in active
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
        close_window(powershell,binary,app)
    report['stage'] = 'complete'
    report['status'] = 'PASS'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-approved',action='store_true',help='Run the reviewed physical Windows session')
    args = parser.parse_args()
    if not args.run_approved:
        parser.error('Use --run-approved for the approved build and launch.')
    try:
        python,tools,sha,source = preflight()
        temp = Path(tempfile.gettempdir()).absolute()
        insist(re.fullmatch(r'[A-Za-z]:\\',temp.anchor) and not any(
            path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT for path in (temp,*temp.parents)
        ), 'The Windows temp folder must be on a local drive without redirected folders.')
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
        print(f'Windows native check blocked before compile: {error}',file=sys.stderr)
        return 2
    run = Path(tempfile.mkdtemp(prefix='pilotodin-r03-native-',dir=temp))
    report = {'status':'INCOMPLETE','scope':'unpackaged_windows_webview2_with_disposable_dev_backend',
              'checkout_sha':sha,'reviewed_application_source':source,'stage':'pre_runtime','memory_samples':[]}
    print(f'Private run logs: {run}',flush=True)
    try:
        session(run,python,tools,report)
    except KeyboardInterrupt:
        report['failure'] = 'The owner stopped the session.'
    except (OSError,ValueError,KeyError,IndexError,subprocess.SubprocessError) as error:
        report['failure'] = str(error)
    with (run/'result.json').open('x',encoding='utf-8') as output:
        json.dump(report,output,indent=2)
    print(json.dumps(report,indent=2),flush=True)
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
