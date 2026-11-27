"""C-D09 disarmed Python wheelhouse adapter, using standard locked pip.
No downloader, no live command entrypoint, no bootstrap trust expansion.
"""
import hashlib
import os
import re
import stat
from pathlib import Path

from . import validation_witnesses as w
from . import validation_coordinator as c

LIVE_ENABLED = False
MAX_WHEEL = 36607512
SHA256 = re.compile(r'[0-9a-f]{64}\Z')


def require_live():
    w.need(LIVE_ENABLED is True, 'PYTHON_STAGE_DISARMED')
    w.require_live()


def need(ok, reason):
    w.need(ok, reason)


def norm(name):
    need(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name), 'DISTRIBUTION_NAME')
    return re.sub(r'[-_.]+', '-', name).lower()


def expected_graph(rows):
    graph = {}
    for r in rows:
        name = norm(r['name'])
        need(name not in graph and SHA256.fullmatch(r['sha256']) and SHA256.fullmatch(r['metadata_sha256']), 'WHEEL_GRAPH')
        graph[name] = (r['version'], r['sha256'], r['metadata_sha256'])
    return graph


def check_lock(raw, profile):
    # Windows checkout may use CRLF; canonical Git text must still match.
    raw = raw.replace(b'\r\n', b'\n')
    need(w.blob(raw) == profile['wheel_lock_blob'], 'LOCK_BLOB')
    lines = [l for l in raw.decode('ascii').splitlines() if l and not l.startswith('#')]
    flags = [l for l in lines if l.startswith('--')]
    need(flags == ['--no-index', '--only-binary=:all:', '--require-hashes'], 'LOCK_FLAGS')
    actual = {}
    for line in lines:
        if line.startswith('--'):
            continue
        m = re.fullmatch(r'([A-Za-z0-9_.-]+)(?:\[standard\])?==([^ ]+) --hash=sha256:([a-f0-9]{64})', line)
        need(m is not None, 'LOCK_ROW')
        name, version, digest = m.groups()
        name = norm(name)
        need(name not in actual, 'LOCK_DUPLICATE')
        actual[name] = (version, digest)
    need(actual == {k:v[:2] for k,v in expected_graph(profile['wheels']).items()}, 'LOCK_GRAPH')
    return raw


def file_digest(path, row):
    path = Path(path)
    st = path.lstat()
    need(stat.S_ISREG(st.st_mode) and not path.is_symlink() and st.st_nlink == 1
         and st.st_size == row['bytes'] and 0 < st.st_size <= MAX_WHEEL, 'WHEEL_SIZE')
    need(SHA256.fullmatch(row['sha256']), 'WHEEL_PIN')
    h = hashlib.sha256()
    with path.open('rb') as f:
        need(os.fstat(f.fileno()).st_ino == st.st_ino, 'WHEEL_CHANGED')
        total = 0
        while total < row['bytes']:
            chunk = f.read(min(65536, row['bytes']-total))
            need(bool(chunk), 'WHEEL_SHORT')
            total += len(chunk); h.update(chunk)
        need(not f.read(1) and h.hexdigest() == row['sha256'], 'WHEEL_HASH')
    return h.hexdigest()


def validate_resolution(doc, rows, house):
    expected = expected_graph(rows)
    seen = set()
    for item in doc['install']:
        meta, info = item['metadata'], item['download_info']
        name = norm(meta['name'])
        need(name in expected and name not in seen, 'PIP_GRAPH')
        row = next(r for r in rows if norm(r['name']) == name)
        need(info['url'] == (Path(house)/row['filename']).resolve().as_uri()
             and info['archive_info']['hashes']['sha256'] == row['sha256']
             and meta['version'] == row['version'] and item.get('is_direct') is False, 'PIP_IDENTITY')
        seen.add(name)
    need(seen == set(expected), 'PIP_GRAPH')


def validate_inventory(items, rows, pip_meta):
    need(SHA256.fullmatch(pip_meta), 'PIP_METADATA')
    expected = {k:(v[0],v[2]) for k,v in expected_graph(rows).items()}
    need('pip' not in expected, 'PIP_GRAPH')
    expected['pip'] = ('26.3', pip_meta)
    actual = {}
    for name, version, digest in items:
        name = norm(name)
        need(name not in actual, 'INSTALLED_DUPLICATE')
        actual[name] = (version,digest)
    need(actual == expected, 'INSTALLED_INVENTORY')


def pip_arguments(python, wheelhouse, lock, report):
    need(all(Path(p).is_absolute() for p in (python,wheelhouse,lock,report)), 'PIP_PATH')
    base = (str(python), '-I', '-B', '-m', 'pip', '--isolated',
            '--disable-pip-version-check', '--no-input', '--keyring-provider', 'disabled')
    install = base + ('install', '--no-index', '--only-binary=:all:', '--require-hashes',
                      '--no-cache-dir', '--find-links', str(wheelhouse), '-r', str(lock))
    return {'dry_run': install + ('--dry-run', '--ignore-installed', '--report', str(report)),
            'install': install, 'check': base + ('check',)}


def exact_inventory(python, rows, scratch, env, pip_meta, run):
    require_live()
    script = """
import hashlib,importlib.metadata as m,json,pathlib,sys
prefix=pathlib.Path(sys.prefix).resolve()
rows=[]
for d in m.distributions():
    files=[f for f in (d.files or []) if f.name=='METADATA' and f.parent.name.endswith('.dist-info')]
    if len(files)!=1: raise RuntimeError('installed metadata missing or ambiguous')
    p=pathlib.Path(d.locate_file(files[0])).resolve(strict=True)
    if not p.is_relative_to(prefix) or p.stat().st_size>2*1024**2:
        raise RuntimeError('installed metadata outside exact environment')
    rows.append([d.metadata['Name'],d.version,hashlib.sha256(p.read_bytes()).hexdigest()])
print(json.dumps(rows))
"""
    items = w.strict_json(run((str(python), '-I', '-B', '-c', script),cwd=scratch,env=env,seconds=30))
    validate_inventory(items, rows, pip_meta)


def bootstrap_python(interpreter, pip_wheel, profile, pip_meta, scratch, env, run):
    require_live()
    scratch = w.host_scratch(scratch)
    need(Path(interpreter).is_absolute(), 'INTERPRETER_PATH')
    file_digest(pip_wheel, profile['pip'])
    probe = "import platform,sys; print(sys.implementation.name); print(platform.python_version()); print(sys.maxsize)"
    output = run((str(interpreter),'-I','-B','-c',probe),cwd=scratch,env=env,seconds=15)
    need(output.decode('ascii').splitlines() == ['cpython',profile['python'],'9223372036854775807'], 'INTERPRETER_VERSION')
    venv = scratch/'venv'
    need(not venv.exists(), 'VENV_EXISTS')
    run((str(interpreter),'-I','-B','-m','venv','--without-pip','--copies',str(venv)),cwd=scratch,env=env,seconds=60)
    python = w.owned(venv/('Scripts/python.exe' if os.name=='nt' else 'bin/python'),scratch)
    need(python.is_file(), 'VENV_PYTHON')
    lock = scratch/'pip-bootstrap.txt'
    with lock.open('x',encoding='ascii') as f:
        f.write('pip==26.3 --hash=sha256:'+profile['pip']['sha256']+'\n')
    script = "import runpy,sys; sys.path.insert(0,sys.argv.pop(1)); runpy.run_module('pip',run_name='__main__')"
    run((str(python),'-I','-B','-c',script,str(pip_wheel),'--isolated','--disable-pip-version-check',
         '--no-input','--keyring-provider','disabled','install','--no-index','--only-binary=:all:',
         '--require-hashes','--no-cache-dir','--find-links',str(Path(pip_wheel).parent),'-r',str(lock)),
        cwd=scratch,env=env,seconds=120)
    exact_inventory(python,[],scratch,env,pip_meta,run)
    return python


def resolve_install(python, rows, lock, house, scratch, env, pip_meta, run):
    require_live()
    need({p.name for p in Path(house).iterdir()} == {r['filename'] for r in rows}, 'WHEELHOUSE_INVENTORY')
    for row in rows:
        file_digest(Path(house)/row['filename'],row)
    report = Path(scratch)/'pip-report.json'
    need(not report.exists(), 'PIP_REPORT_EXISTS')
    commands = pip_arguments(python,house,lock,report)
    run(commands['dry_run'],cwd=scratch,env=env,seconds=180)
    validate_resolution(w.strict_json(w.checked_bytes(report,report.stat().st_size)),rows,house)
    run(commands['install'],cwd=scratch,env=env,seconds=180)
    run(commands['check'],cwd=scratch,env=env,seconds=60)
    exact_inventory(python,rows,scratch,env,pip_meta,run)
    report.unlink()


def verify_loaded_native(python, profile, scratch, env, run):
    """Verify installed member hash and actual loader mapping after authorised import."""
    require_live()
    wheel, = [r for r in profile['wheels'] if r['name'] == 'pypdfium2']
    expected, = wheel['native']
    script = r"""
import ctypes, hashlib, importlib.metadata as metadata, json, os, pathlib, sys
from importlib import util
spec = util.find_spec("pypdfium2_raw")
if spec is None or spec.origin is None: raise RuntimeError("native package absent")
pre = pathlib.Path(spec.origin).parent / pathlib.Path(sys.argv[1]).name
pre = pre.resolve(strict=True)
if not pre.is_relative_to(pathlib.Path(sys.prefix).resolve()) or pre.stat().st_size != int(sys.argv[4]):
    raise RuntimeError("native path/size mismatch before import")
with pre.open("rb") as stream:
    if hashlib.file_digest(stream, "sha256").hexdigest() != sys.argv[3]:
        raise RuntimeError("native digest mismatch before import")
sys.path.insert(0, sys.argv[2])
from tools.pdf_test_inspection import require_pdfium
require_pdfium()
import pypdfium2
import pypdfium2_raw
path = pathlib.Path(pypdfium2_raw.__file__).parent / pathlib.Path(__import__('sys').argv[1]).name
path = path.resolve(strict=True)
if os.name == 'nt':
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    handle = kernel.GetModuleHandleW
    handle.argtypes = [ctypes.c_wchar_p]
    handle.restype = ctypes.c_void_p
    module = handle(str(path))
    if not module: raise RuntimeError('native member not loaded')
    getname = kernel.GetModuleFileNameW
    getname.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32]
    getname.restype = ctypes.c_uint32
    buf = ctypes.create_unicode_buffer(32768)
    size = getname(module, buf, len(buf))
    if not 0 < size < len(buf): raise RuntimeError('loader path unavailable')
    loaded = pathlib.Path(buf.value).resolve(strict=True) == path
else:
    loaded = False
    for line in pathlib.Path('/proc/self/maps').read_text().splitlines():
        parts = line.split(None, 5)
        if len(parts) == 6 and parts[5].startswith('/') and not parts[5].endswith(' (deleted)'):
            if pathlib.Path(parts[5]).resolve() == path: loaded = True
with path.open('rb') as f:
    sha = hashlib.file_digest(f, 'sha256').hexdigest()
print(json.dumps({'loaded': loaded, 'sha256': sha, 'bytes': path.stat().st_size,
                  'inside_venv': path.is_relative_to(pathlib.Path(__import__('sys').prefix).resolve()),
                  'version': metadata.version('pypdfium2')}))
"""
    got = w.strict_json(run((str(python), "-I", "-B", "-c", script, expected["path"], str(w.ROOT), expected["sha256"], str(expected["bytes"])),
                                 cwd=scratch, env=env, seconds=30))
    need(got == {"loaded": True, "sha256": expected["sha256"], "bytes": expected["bytes"],
                 "inside_venv": True, "version": "5.15.2"}, "LOADED_NATIVE_IDENTITY")
    return expected["sha256"]


if __name__ == '__main__':
    raise SystemExit('PYTHON_STAGE_DISARMED')
