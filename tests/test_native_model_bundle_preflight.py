"""Offline release-gate regression checks. Synthetic bytes are NEVER a shippable model."""
import importlib.util
import json
from pathlib import Path
import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / 'desktop' / 'verify_inference_assets.py'
_spec = importlib.util.spec_from_file_location('native_bundle_gate', _SCRIPT)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

def stage(root):
    tauri = root / 'frontend' / 'src-tauri'
    model = tauri / 'resources' / 'models' / 'qwen3-1.7b-q4_k_m.gguf'
    exe = tauri / 'binaries' / 'pilotodin-inference-x86_64-pc-windows-msvc.exe'
    dlls = tauri / 'resources' / 'llama-runtime'
    for path in (model.parent, exe.parent, dlls):
        path.mkdir(parents=True)
    with model.open('wb') as out:
        out.write(b'GGUF')
        out.truncate(10_000_001)
    exe.write_bytes(b'MZ' + b'0' * 200)
    manifest = {
        'schema_version': 1, 'model_file': model.name,
        'model_sha256': mod.sha256(model), 'server_sha256': mod.sha256(exe),
        'runtime_dll_sha256': {}, 'model_alias': 'pilotodin-qwen3-1.7b',
    }
    manifest_file = model.parent / 'model-manifest.json'
    manifest_file.write_text(json.dumps(manifest))
    return model, exe, dlls, manifest_file

def test_missing_bundle_fails_closed(tmp_path):
    with pytest.raises(ValueError, match='not staged'):
        mod.verify(tmp_path)

def test_exact_manifest_checksums_pass_structural_gate(tmp_path):
    stage(tmp_path)
    mod.verify(tmp_path)  # Structural checks, not real model execution.

def test_model_hash_change_rejected(tmp_path):
    model, *_ = stage(tmp_path)
    with model.open('r+b') as file:
        file.seek(32)
        file.write(b'X')
    with pytest.raises(ValueError, match='checksum'):
        mod.verify(tmp_path)

def test_wrong_gguf_signature_rejected(tmp_path):
    model, *_ = stage(tmp_path)
    with model.open('r+b') as file:
        file.write(b'XXXX')
    with pytest.raises(ValueError, match='GGUF'):
        mod.verify(tmp_path)

def test_unmanifested_dll_rejected(tmp_path):
    _, _, dlls, _ = stage(tmp_path)
    (dlls / 'untracked.dll').write_bytes(b'MZ123')
    with pytest.raises(ValueError, match='Unmanifested'):
        mod.verify(tmp_path)

def test_invalid_schema_rejected(tmp_path):
    _, _, _, manifest_file = stage(tmp_path)
    data = json.loads(manifest_file.read_text())
    data['schema_version'] = 0
    manifest_file.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='schema'):
        mod.verify(tmp_path)
