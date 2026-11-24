"""B2 model publication metadata. No serialization or deserialization here.

A receipt binds locally produced bytes to one experiment and its training
provenance. It is not an authenticity proof against an attacker controlling
both the database and files. Legacy experiments get no inferred receipts.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib import metadata
import json
import re
import sys

try:
    from .artifact_publication import PublicationError
except ImportError:
    from artifact_publication import PublicationError

TABLE = "model_publications_v1"
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
MAX_MANIFEST_JSON = 8192
_RUNTIME_KEYS = ("python", "joblib", "scikit-learn", "numpy", "scipy", "pandas")
_ID = re.compile(r"[a-f0-9]{32}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_VERSION = re.compile(r"[A-Za-z0-9.+!_-]{1,128}\Z")
_STATES = frozenset(("intent", "staged", "publishing", "committed", "interrupted", "blocked"))
_NONTERMINAL = frozenset(("intent", "staged", "publishing"))
_REASONS = frozenset(("interrupted_before_commit", "storage_unavailable", "integrity_mismatch",
                      "reference_conflict", "cancelled", "unknown_commit", "unsafe_identity"))

_DDL = """CREATE TABLE model_publications_v1 (
    experiment_id TEXT NOT NULL PRIMARY KEY
        CHECK(length(experiment_id)=32 AND experiment_id NOT GLOB '*[^a-f0-9]*'),
    project_id TEXT NOT NULL
        CHECK(length(project_id)=32 AND project_id NOT GLOB '*[^a-f0-9]*'),
    schema_version INTEGER NOT NULL CHECK(schema_version=1),
    quality_version INTEGER NOT NULL CHECK(typeof(quality_version)='integer' AND quality_version>=0),
    source_sha256 TEXT NOT NULL CHECK(length(source_sha256)=64 AND source_sha256 NOT GLOB '*[^a-f0-9]*'),
    config_sha256 TEXT NOT NULL CHECK(length(config_sha256)=64 AND config_sha256 NOT GLOB '*[^a-f0-9]*'),
    runtime_json TEXT NOT NULL CHECK(length(runtime_json)<=1024),
    manifest_json TEXT CHECK(length(manifest_json)<=8192),
    state TEXT NOT NULL CHECK(state IN ('intent','staged','publishing','committed','interrupted','blocked')),
    reason_code TEXT CHECK(reason_code IN ('interrupted_before_commit','storage_unavailable','integrity_mismatch',
        'reference_conflict','cancelled','unknown_commit','unsafe_identity')),
    CHECK((state IN ('interrupted','blocked') AND reason_code IS NOT NULL)
       OR (state NOT IN ('interrupted','blocked') AND reason_code IS NULL)),
    CHECK(state!='intent' OR manifest_json IS NULL),
    CHECK(state NOT IN ('staged','publishing','committed') OR manifest_json IS NOT NULL),
    FOREIGN KEY(experiment_id) REFERENCES experiments(id),
    FOREIGN KEY(project_id) REFERENCES projects(id)
)"""
_INDEX = "CREATE INDEX model_publications_v1_project ON model_publications_v1(project_id)"
_COLUMNS = ("experiment_id,project_id,schema_version,quality_version,source_sha256,"
            "config_sha256,runtime_json,manifest_json,state,reason_code")


def ensure_schema(con):
    for name, kind, ddl in ((TABLE,"table",_DDL),("model_publications_v1_project","index",_INDEX)):
        row = con.execute("SELECT type,sql FROM sqlite_master WHERE name=?", (name,)).fetchone()
        shape = lambda sql: re.sub(r"\s+", "", sql or "").lower()
        if row is None:
            con.execute(ddl)
        elif row[0] != kind or shape(row[1]) != shape(ddl):
            raise PublicationError("Incompatible model publication schema")


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",",":"), ensure_ascii=True, allow_nan=False)


def config_digest(config):
    return hashlib.sha256(_json(config).encode("ascii")).hexdigest()


def runtime_versions():
    """Capture actual installed versions, not requirement ranges."""
    result = {"python": f"{sys.version_info.major}.{sys.version_info.minor}"}
    result.update({key: metadata.version(key) for key in _RUNTIME_KEYS if key != "python"})
    _validate_runtime(result)
    return result


def _validate_runtime(runtime):
    if (not isinstance(runtime, dict) or set(runtime) != set(_RUNTIME_KEYS)
            or any(not isinstance(v,str) or not _VERSION.fullmatch(v) for v in runtime.values())
            or not re.fullmatch(r"[0-9]+\.[0-9]+", runtime["python"])):
        raise PublicationError("Invalid model runtime metadata")


def _model_keys(config):
    # Lazy import: schema initialization does not import the numerical stack.
    try:
        from .engine import CLASS_MODELS, REG_MODELS
    except ImportError:
        from engine import CLASS_MODELS, REG_MODELS
    allowed = {"classification": CLASS_MODELS, "regression": REG_MODELS}
    keys = config.get("models")
    if (config.get("task") not in allowed or not isinstance(keys,list)
            or not 1 <= len(keys) <= 5 or any(not isinstance(k,str) for k in keys)
            or len(set(keys)) != len(keys)
            or any(k not in allowed[config["task"]] for k in keys)):
        raise PublicationError("Invalid model configuration keys")
    return set(keys)


def expected_files(config, results):
    """Exact ready model keys plus mandatory holdout; never accept arbitrary names."""
    keys = _model_keys(config)
    if not isinstance(results,dict) or results.get("task") != config["task"]:
        raise PublicationError("Model results disagree with configuration")
    rows = results.get("models")
    if not isinstance(rows,list) or len(rows) != len(keys):
        raise PublicationError("Incomplete model result inventory")
    seen, ready = set(), set()
    for row in rows:
        if (not isinstance(row,dict) or not isinstance(row.get("key"),str)
                or row["key"] not in keys or row["key"] in seen
                or row.get("status") not in ("ready","failed")):
            raise PublicationError("Invalid model result inventory")
        seen.add(row["key"])
        if row["status"] == "ready":
            ready.add(row["key"])
    if not ready:
        raise PublicationError("No ready model artifacts")
    return {key+".joblib" for key in ready} | {"test_set.joblib"}


def validate_manifest(files, expected=None):
    # Check generic filename shape even when reading an isolated receipt.
    # Provenance validation below additionally requires exact expected keys.
    if not isinstance(files,dict) or not 2 <= len(files) <= 6 or "test_set.joblib" not in files:
        raise PublicationError("Invalid model file inventory")
    if expected is not None and set(files) != set(expected):
        raise PublicationError("Model files disagree with ready results")
    total = 0
    for name, entry in files.items():
        if (not isinstance(name,str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}\.joblib",name)
                or not isinstance(entry,dict) or set(entry) != {"size","sha256"}
                or type(entry["size"]) is not int or not 1 <= entry["size"] <= MAX_FILE_BYTES
                or not isinstance(entry["sha256"],str) or not _SHA.fullmatch(entry["sha256"])):
            raise PublicationError("Invalid model file metadata")
        total += entry["size"]
    if total > MAX_TOTAL_BYTES:
        raise PublicationError("Model artifact aggregate budget exceeded")


def _decode(raw, limit):
    if not isinstance(raw,str) or len(raw)>limit:
        raise PublicationError("Invalid model receipt JSON")
    try:
        value=json.loads(raw)
        if _json(value)!=raw:
            raise ValueError
        return value
    except (ValueError,TypeError,RecursionError):
        raise PublicationError("Invalid model receipt JSON") from None


@dataclass(frozen=True)
class Receipt:
    experiment_id: str
    project_id: str
    schema_version: int
    quality_version: int
    source_sha256: str
    config_sha256: str
    runtime_json: str
    manifest_json: str | None
    state: str
    reason_code: str | None

    def validate(self):
        if (not isinstance(self.experiment_id,str) or not _ID.fullmatch(self.experiment_id)
                or not isinstance(self.project_id,str) or not _ID.fullmatch(self.project_id)
                or type(self.schema_version) is not int or self.schema_version != 1
                or type(self.quality_version) is not int or self.quality_version < 0
                or not isinstance(self.source_sha256,str) or not _SHA.fullmatch(self.source_sha256)
                or not isinstance(self.config_sha256,str) or not _SHA.fullmatch(self.config_sha256)
                or self.state not in _STATES):
            raise PublicationError("Invalid model publication receipt")
        _validate_runtime(self.runtime)
        if self.state in ("interrupted","blocked"):
            if self.reason_code not in _REASONS:
                raise PublicationError("Invalid model publication reason")
        elif self.reason_code is not None:
            raise PublicationError("Unexpected model publication reason")
        if self.state == "intent" and self.manifest_json is not None:
            raise PublicationError("Unexpected intent manifest")
        if self.state in ("staged","publishing","committed") and self.manifest_json is None:
            raise PublicationError("Missing model file manifest")
        if self.manifest_json is not None:
            validate_manifest(self.files)

    @property
    def runtime(self):
        return _decode(self.runtime_json,1024)

    @property
    def files(self):
        return _decode(self.manifest_json,MAX_MANIFEST_JSON)

    def verify_binding(self, project_id, config, source_sha256, results=None, *, runtime=None):
        self.validate()
        if (self.project_id != project_id or self.quality_version != config.get("quality_version")
                or self.config_sha256 != config_digest(config) or self.source_sha256 != source_sha256):
            raise PublicationError("Model publication provenance mismatch")
        _model_keys(config)
        if runtime is not None and self.runtime != runtime:
            raise PublicationError("Model artifact runtime incompatible; retrain")
        if results is not None:
            validate_manifest(self.files, expected_files(config,results))


def read(con, experiment_id):
    if not isinstance(experiment_id,str) or not _ID.fullmatch(experiment_id):
        raise PublicationError("Invalid experiment ID")
    row=con.execute(f"SELECT {_COLUMNS} FROM {TABLE} WHERE experiment_id=?",(experiment_id,)).fetchone()
    if row is None:
        return None
    receipt=Receipt(*row)
    receipt.validate()
    return receipt


def _require_write(con):
    if not con.in_transaction:
        raise PublicationError("Model publication requires active transaction")


def insert_intent(con, experiment_id, project_id, config, source_sha256, runtime):
    _require_write(con)
    _model_keys(config)
    receipt=Receipt(experiment_id,project_id,1,config.get("quality_version"),source_sha256,
                    config_digest(config),_json(runtime),None,"intent",None)
    receipt.validate()
    con.execute(f"INSERT INTO {TABLE} ({_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (receipt.experiment_id,receipt.project_id,receipt.schema_version,receipt.quality_version,
                 receipt.source_sha256,receipt.config_sha256,receipt.runtime_json,receipt.manifest_json,
                 receipt.state,receipt.reason_code))
    return receipt


def _cas(con, expected, state, *, manifest=None, reason=None):
    _require_write(con)
    expected.validate()
    if read(con,expected.experiment_id)!=expected:
        raise PublicationError("Model publication receipt changed")
    changed=con.execute(f"UPDATE {TABLE} SET state=?,manifest_json=?,reason_code=? WHERE experiment_id=? AND state=?",
                        (state,expected.manifest_json if manifest is None else _json(manifest),
                         reason,expected.experiment_id,expected.state))
    if changed.rowcount!=1:
        raise PublicationError("Model publication transition conflict")
    return read(con,expected.experiment_id)


def stage(con, expected, config, results, files):
    if expected.state!="intent" or expected.config_sha256!=config_digest(config):
        raise PublicationError("Invalid model staging transition")
    validate_manifest(files,expected_files(config,results))
    return _cas(con,expected,"staged",manifest=files)


def advance(con, expected, state, *, reason=None):
    if expected.state not in _NONTERMINAL:
        raise PublicationError("Terminal model receipt cannot transition")
    if state in ("interrupted","blocked"):
        if reason not in _REASONS:
            raise PublicationError("Invalid model publication reason")
    elif (expected.state,state)!=("staged","publishing") or reason is not None:
        raise PublicationError("Illegal model publication transition")
    return _cas(con,expected,state,reason=reason)


def commit(con, expected, results, config, source_sha256):
    """Requires completed experiment CAS inside the caller's transaction."""
    _require_write(con)
    if expected.state!="publishing":
        raise PublicationError("Model artifacts are not publishing")
    row=con.execute("SELECT project_id,status,config,results FROM experiments WHERE id=?",
                    (expected.experiment_id,)).fetchone()
    if (row is None or row[1]!="completed" or json.loads(row[2])!=config
            or json.loads(row[3])!=results):
        raise PublicationError("Model completion metadata disagrees")
    expected.verify_binding(row[0],config,source_sha256,results)
    return _cas(con,expected,"committed")
