"""Fail-closed, offline verification of final Windows inference bundle inputs."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
import sys


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def verify(root: Path) -> None:
    tauri = root / 'frontend' / 'src-tauri'
    models = tauri / 'resources' / 'models'
    dlls = tauri / 'resources' / 'llama-runtime'
    binary = tauri / 'binaries' / 'pilotodin-inference-x86_64-pc-windows-msvc.exe'
    manifest_file = models / 'model-manifest.json'
    if not manifest_file.is_file() or not binary.is_file():
        raise ValueError('Bundled model/runtime not staged. Run desktop/Stage_Bundled_Inference.ps1 with verified vendor inputs.')
    data = json.loads(manifest_file.read_text(encoding='utf-8-sig'))
    expected = ('model_sha256', 'server_sha256', 'runtime_dll_sha256', 'model_alias')
    if any(k not in data for k in expected) or data.get('model_file') != 'qwen3-1.7b-q4_k_m.gguf':
        raise ValueError('Incomplete or inconsistent inference manifest')
    if data['model_alias'] != 'pilotodin-qwen3-1.7b':
        raise ValueError('Bundled model alias does not match the application contract')
    model = models / data['model_file']
    if not model.is_file() or model.stat().st_size < 10_000_000:
        raise ValueError('Bundled model is absent or implausibly small')
    if data.get('schema_version') != 1:
        raise ValueError('Incomplete or inconsistent inference manifest schema')
    with model.open('rb') as handle:
        if handle.read(4) != b'GGUF':
            raise ValueError('Bundled model is not a GGUF file')
    with binary.open('rb') as handle:
        if handle.read(2) != b'MZ':
            raise ValueError('Bundled Windows server is not a PE executable')
    for k in ('model_sha256', 'server_sha256'):
        if not isinstance(data[k], str) or not re.fullmatch(r'[0-9a-fA-F]{64}', data[k]):
            raise ValueError(f'Invalid {k} checksum format')
    if sha256(model) != str(data['model_sha256']).lower():
        raise ValueError('Bundled model checksum failed')
    if sha256(binary) != str(data['server_sha256']).lower():
        raise ValueError('Bundled runtime checksum failed')
    checks = data['runtime_dll_sha256']
    if not isinstance(checks, dict):
        raise ValueError('Invalid runtime DLL manifest')
    allowed = set(checks)
    unexpected = {file.name for file in dlls.glob('*.dll')} - allowed
    if unexpected:
        raise ValueError('Unmanifested DLLs found in inference runtime directory')
    for filename, expected_hash in checks.items():
        if not isinstance(filename, str) or Path(filename).name != filename or not filename.lower().endswith('.dll'):
            raise ValueError('Unsafe bundled DLL path')
        if not isinstance(expected_hash, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', expected_hash):
            raise ValueError('Invalid DLL checksum format')
        dll = dlls / filename
        if not dll.is_file() or sha256(dll) != str(expected_hash).lower():
            raise ValueError('Bundled DLL checksum failed')
    print('Bundled AI integrity verified (not a runtime or license certification).')


if __name__ == '__main__':
    try:
        verify(Path(__file__).resolve().parents[1])
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f'OFFLINE INFERENCE PRE-FLIGHT BLOCKED: {exc}', file=sys.stderr)
        raise SystemExit(2)
