"""C4 settings foundation: isolated generated files; no real DPAPI or provider I/O."""
import base64
import json
import os
from pathlib import Path

import pytest

from backend import settings_storage as settings


def wire(value):
    return json.dumps(value).encode("utf-8")


def fake_decrypt(blob):
    assert blob.startswith(b"fixture:")
    return blob[len(b"fixture:"):]


def protected(value):
    return base64.b64encode(b"fixture:" + wire(value))


@pytest.fixture
def store(tmp_path):
    # Explicit disposable adapter, not production lease evidence.
    def check(path, **options):
        assert path.parent == tmp_path
        if options.get("absent") and path.exists():
            raise OSError("Expected absent")
    return settings.Store(tmp_path, check_path=check)


@pytest.mark.parametrize("raw", [
    b"[]", b"null", b"", b"{", b'{"x":1,"x":2}',
    b'{"nested":{"x":1,"x":2}}', b'{"x":NaN}', b'{"x":Infinity}',
    b'{"x":-Infinity}', b'{"x":"\xff"}', b'{"x":1e999}', b'{"x":-1e999}',
])
def test_strict_json_refuses_ambiguous_input(raw):
    with pytest.raises(settings.InvalidSettings):
        settings.strict_object(raw, 4096)


def test_byte_bound_and_exact_resource_schema():
    assert settings.strict_object(b"{}", 2) == {}
    with pytest.raises(settings.InvalidSettings):
        settings.strict_object(b"{} ", 2)
    for value in [
        {"schema_version": True, "mode": "adaptive"},
        {"schema_version": 1.0, "mode": "adaptive"},
        {"schema_version": 2, "mode": "adaptive"},
        {"schema_version": 1, "mode": "adaptive", "future": 1},
        {"schema_version": 1, "mode": []},
    ]:
        with pytest.raises(settings.InvalidSettings):
            settings.validate_resource(value)


@pytest.mark.parametrize("field,value", [
    ("cloud_enabled", "false"), ("share_aggregates", 1),
    ("auto_insights", []), ("local_model_enabled", "true"),
    ("timeout_seconds", True), ("timeout_seconds", 45.0),
    ("local_timeout_seconds", "60"), ("provider_order", ["gemini"] * 3),
    ("provider_order", ["gemini", "groq", []]),
    ("workspace_preferences", {"scope": []}), ("workspace_preferences", []),
    ("preferred_provider", "unknown"), ("intelligence_mode", "other"),
    ("local_model", "http://127.0.0.1"), ("future_field", True),
])
def test_ai_exact_types_and_enums(field, value):
    with pytest.raises(settings.InvalidSettings):
        settings.validate_ai({field: value})


def test_legacy_missing_fields_and_mutable_defaults():
    first = settings.validate_ai({"timeout_seconds": 12, "auto_insights": True})
    first["provider_order"].reverse()
    first["workspace_preferences"]["scope"] = "groq"
    next_value = settings.validate_ai({})
    assert next_value == settings.ai_defaults()
    assert next_value["provider_order"] == list(settings.PROVIDERS)
    assert next_value["workspace_preferences"] == {}
    with pytest.raises(settings.InvalidSettings):
        settings.validate_ai({"cloud_enabled": True})


def test_legacy_maximum_escaped_shapes_fit_bounds():
    # Non-ASCII may occupy 12 bytes per character in existing json.dumps.
    mapping = {str(i) + "\U0001f600" * 38: "openrouter" for i in range(12)}
    ai = {**settings.ai_defaults(), "workspace_preferences": mapping}
    assert len(wire(ai)) < settings.Kind.AI.limit
    assert settings.decode(settings.Kind.AI, wire(ai)) == ai
    keys = {p: "\U0001f600" * 512 for p in settings.PROVIDERS}
    assert 16 * 1024 < len(wire(keys)) <= settings.SECRET_PLAINTEXT_LIMIT
    assert settings.decode(settings.Kind.SECRET, protected(keys),
                           decrypt=fake_decrypt) == keys


@pytest.mark.parametrize("raw", [b"bad base64!", b"====", b"", b"YQ==\n"])
def test_bad_ciphertext_does_not_invoke_decrypt(raw):
    def forbidden(_):
        pytest.fail("invalid ciphertext reached DPAPI adapter")
    with pytest.raises(settings.InvalidSettings):
        settings.decode(settings.Kind.SECRET, raw, decrypt=forbidden)


def test_invalid_decrypted_map_and_adapter_errors_are_redacted():
    for value in [{"unknown": "x" * 20}, {"gemini": "too short"},
                  {"groq": "x" * 513}, {"gemini": 123}]:
        with pytest.raises(settings.InvalidSettings):
            settings.decode(settings.Kind.SECRET, protected(value), decrypt=fake_decrypt)
    def fail(_):
        raise OSError("private-marker")
    with pytest.raises(settings.InvalidSettings) as caught:
        settings.decode(settings.Kind.SECRET, protected({}), decrypt=fail)
    assert "private-marker" not in str(caught.value)


def test_missing_and_confirmed_replace_are_distinct(store, tmp_path):
    for kind, raw, options in (
        (settings.Kind.RESOURCE, wire({"schema_version": 1, "mode": "low_memory"}), {}),
        (settings.Kind.AI, wire({"timeout_seconds": 12}), {}),
        (settings.Kind.SECRET, protected({"groq": "fixture-key-12345"}), {"decrypt": fake_decrypt}),
    ):
        assert store.read(kind, **options) is None
        value = store.replace(kind, raw, **options)
        assert store.read(kind, **options) == value
        assert (tmp_path / kind.filename).read_bytes() == raw
        assert list(tmp_path.glob(kind.prefix + "*")) == []


@pytest.mark.parametrize("kind,original,new,options", [
    (settings.Kind.RESOURCE, b'{"schema_version":2,"mode":"adaptive"}',
     wire({"schema_version": 1, "mode": "adaptive"}), {}),
    (settings.Kind.AI, b'{"cloud_enabled":"false"}', wire({}), {}),
    (settings.Kind.SECRET, b"malformed", protected({}), {"decrypt": fake_decrypt}),
])
def test_invalid_existing_target_is_not_overwritten(store, tmp_path, kind, original, new, options):
    target = tmp_path / kind.filename
    target.write_bytes(original)
    with pytest.raises(settings.InvalidSettings):
        store.read(kind, **options)
    with pytest.raises(settings.InvalidSettings):
        store.replace(kind, new, **options)
    assert target.read_bytes() == original
    assert list(tmp_path.glob(kind.prefix + "*")) == []


@pytest.mark.parametrize("kind", list(settings.Kind))
def test_oversize_is_refused_before_decode(store, tmp_path, kind):
    target = tmp_path / kind.filename
    original = b"x" * (kind.limit + 1)
    target.write_bytes(original)
    with pytest.raises(settings.InvalidSettings):
        store.read(kind, decrypt=fake_decrypt)
    assert target.read_bytes() == original


def resource(mode):
    return wire({"schema_version": 1, "mode": mode})


@pytest.mark.parametrize("failure", ["fsync", "replace"])
def test_precommit_failure_preserves_old_bytes_and_cleans_owned_stage(store, tmp_path, monkeypatch, failure):
    kind = settings.Kind.RESOURCE
    old = resource("low_memory")
    store.replace(kind, old)
    def fail(*_args):
        raise OSError("private-path-marker")
    monkeypatch.setattr(settings.os, failure, fail)
    with pytest.raises(settings.SettingsWriteError) as caught:
        store.replace(kind, resource("performance"))
    assert caught.value.code == "settings_not_committed"
    assert "private-path-marker" not in str(caught.value)
    assert (tmp_path / kind.filename).read_bytes() == old
    assert not list(tmp_path.glob(kind.prefix + "*"))


def test_replace_error_after_actual_rename_is_uncertain(store, tmp_path, monkeypatch):
    kind = settings.Kind.RESOURCE
    old, new = resource("adaptive"), resource("performance")
    store.replace(kind, old)
    real = os.replace
    def ambiguous(src, dst):
        real(src, dst)
        raise OSError("lost acknowledgement")
    monkeypatch.setattr(settings.os, "replace", ambiguous)
    with pytest.raises(settings.SettingsWriteError) as caught:
        store.replace(kind, new)
    assert caught.value.code == "settings_commit_uncertain"
    assert (tmp_path / kind.filename).read_bytes() == new
    assert not list(tmp_path.glob(kind.prefix + "*"))


def test_postcommit_readback_failure_does_not_claim_rollback(store, tmp_path, monkeypatch):
    kind = settings.Kind.RESOURCE
    old, new = resource("adaptive"), resource("performance")
    store.replace(kind, old)
    original = store._read
    committed = False
    real = os.replace
    def replace(src, dst):
        nonlocal committed
        real(src, dst)
        committed = True
    def read(path, limit):
        if committed:
            raise settings.SettingsIOError("postcommit observation failed")
        return original(path, limit)
    monkeypatch.setattr(settings.os, "replace", replace)
    monkeypatch.setattr(store, "_read", read)
    with pytest.raises(settings.SettingsWriteError) as caught:
        store.replace(kind, new)
    assert caught.value.code == "settings_commit_uncertain"
    assert (tmp_path / kind.filename).read_bytes() == new


def test_concurrent_same_identity_target_edit_is_not_overwritten(store, tmp_path, monkeypatch):
    kind = settings.Kind.RESOURCE
    old, foreign = resource("adaptive"), resource("low_memory")
    target = tmp_path / kind.filename
    target.write_bytes(old)
    real = os.fsync
    def edit(fd):
        real(fd)
        target.write_bytes(foreign)
    monkeypatch.setattr(settings.os, "fsync", edit)
    with pytest.raises(settings.SettingsWriteError) as caught:
        store.replace(kind, resource("performance"))
    assert caught.value.code == "settings_not_committed"
    assert target.read_bytes() == foreign


def test_foreign_stage_replacement_is_retained(store, tmp_path, monkeypatch):
    kind = settings.Kind.RESOURCE
    old = resource("adaptive")
    store.replace(kind, old)
    real = os.fsync
    foreign = tmp_path / "foreign"
    foreign.write_bytes(b"foreign marker")
    def swap(fd):
        real(fd)
        stage = next(tmp_path.glob(kind.prefix + "*"))
        # Move the original away and put a different identity at its name.
        stage.rename(tmp_path / "retained-original-stage")
        foreign.rename(stage)
    monkeypatch.setattr(settings.os, "fsync", swap)
    with pytest.raises(settings.SettingsWriteError) as caught:
        store.replace(kind, resource("performance"))
    assert caught.value.code == "settings_not_committed_stage_retained"
    assert (tmp_path / kind.filename).read_bytes() == old
    assert next(tmp_path.glob(kind.prefix + "*")).read_bytes() == b"foreign marker"
    assert (tmp_path / "retained-original-stage").exists()


def test_hardlinked_target_and_redirected_target_refused(store, tmp_path):
    kind = settings.Kind.RESOURCE
    foreign = tmp_path / "other"
    foreign.write_bytes(resource("adaptive"))
    target = tmp_path / kind.filename
    os.link(foreign, target)
    with pytest.raises(settings.SettingsIOError):
        store.read(kind)
    target.unlink()
    target.symlink_to(foreign)
    with pytest.raises(settings.SettingsIOError):
        store.replace(kind, resource("performance"))
    assert foreign.read_bytes() == resource("adaptive")


def test_existing_historical_fixed_stage_not_touched(store, tmp_path):
    old = tmp_path / "ai_settings.tmp"
    old.write_bytes(b"historical marker")
    store.replace(settings.Kind.AI, wire({}))
    assert old.read_bytes() == b"historical marker"
