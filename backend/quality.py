"""Local, versioned, evidence-based data quality.

Original uploads are never overwritten. Explicitly approved transformations
are replayed into the working dataset used by exploration and new ML training.
Cloud LLM output never directly triggers transformations.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from . import artifact_publication, dataset_publication, engine, storage
except ImportError:
    import artifact_publication, dataset_publication, engine, storage


class QualityError(ValueError):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


class QualityArchivedError(QualityError):
    """Archive observed during metadata snapshot; adapters preserve HTTP 409."""


# Provisional defensive metadata budgets, not native memory acceptance.
# Retain all evidence; refuse rather than truncate, compact or rewrite history.
MAX_ACTIVE_ACTIONS = 4096
MAX_HISTORY_ROWS = 16384
MAX_HISTORY_BYTES = 32 * 1024 * 1024
MAX_REPLAY_METADATA_BYTES = 16 * 1024 * 1024


def _metadata_limit():
    return QualityError(
        "Quality history exceeds the supported metadata safety budget. "
        "Original and history preserved; use a reviewed recovery or backup workflow. "
        "No Quality changes were applied.", 409)


def _row_bytes(row):
    return sum(len(str(value).encode("utf-8")) if value is not None else 0
               for value in row)


def _bounded_rows(con, sql, params, *, max_rows=None, max_bytes=None, collect=True, validate=None):
    """Bound SQLite row allocation and aggregate transfer without truncating results.

    Only internal fixed SELECT statements are accepted. A connection-local
    length limit prevents a single huge row crossing into Python; restore it
    even on failure. Count one extra row to distinguish overflow from success.
    """
    max_rows = MAX_HISTORY_ROWS if max_rows is None else max_rows
    max_bytes = MAX_HISTORY_BYTES if max_bytes is None else max_bytes
    previous = con.getlimit(sqlite3.SQLITE_LIMIT_LENGTH)
    con.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, min(previous, max(65536, max_bytes + 1024)))
    result = []
    total = 0
    cursor = None
    try:
        cursor = con.execute("SELECT * FROM (" + sql + ") LIMIT ?", (*params, max_rows + 1))
        for index, row in enumerate(cursor):
            total += _row_bytes(row)
            if index >= max_rows or total > max_bytes:
                raise _metadata_limit()
            if validate is not None:
                validate(row)
            if collect:
                result.append(row)
    except sqlite3.DataError as exc:
        raise _metadata_limit() from exc
    finally:
        if cursor is not None:
            cursor.close()
        con.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, previous)
    return result


def _operation_ids(raw):
    if len(raw.encode("utf-8")) > MAX_REPLAY_METADATA_BYTES:
        raise _metadata_limit()
    try:
        ops = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise QualityError("Invalid Quality operation history. Original and history preserved.", 409) from exc
    if not isinstance(ops, list):
        raise QualityError("Invalid Quality operation history. Original and history preserved.", 409)
    if len(ops) > MAX_ACTIVE_ACTIONS:
        raise _metadata_limit()
    if any(not isinstance(item, str) or not item for item in ops):
        raise QualityError("Invalid Quality operation history. Original and history preserved.", 409)
    return ops


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _fingerprint(*parts: Any) -> str:
    return hashlib.sha256(_json(parts).encode("utf-8")).hexdigest()[:24]


def _digest(path: str) -> str:
    hasher = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _init_tables() -> None:
    with storage.connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS quality_state (
          project_id TEXT PRIMARY KEY, original_sha256 TEXT NOT NULL,
          current_version INTEGER NOT NULL DEFAULT 0,
          FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        CREATE TABLE IF NOT EXISTS quality_versions (
          project_id TEXT NOT NULL, version INTEGER NOT NULL,
          operations_json TEXT NOT NULL, event TEXT NOT NULL,
          details_json TEXT NOT NULL, created_at TEXT NOT NULL,
          PRIMARY KEY (project_id,version),
          FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        CREATE TABLE IF NOT EXISTS quality_actions (
          id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
          kind TEXT NOT NULL, column_name TEXT NOT NULL, params_json TEXT NOT NULL,
          source TEXT NOT NULL, affected_rows INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        CREATE TABLE IF NOT EXISTS quality_decisions (
          project_id TEXT NOT NULL, issue_id TEXT NOT NULL,
          status TEXT NOT NULL, created_at TEXT NOT NULL,
          PRIMARY KEY(project_id,issue_id),
          FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        """)


def _require_active_for_write(con, pid: str) -> None:
    """Fence Quality writes under the SAME SQLite transaction as archiving.

    Caller must acquire BEGIN IMMEDIATE before this check. Archive uses that
    same SQLite write lock, so archive-first must reject this mutation; write-
    first must finish before archive commits. A stale project object obtained
    prior to BEGIN IMMEDIATE is never authority to write after archive.
    """
    if not con.in_transaction:
        raise RuntimeError("Quality archive fence requires an active write transaction")
    row = con.execute(
        "SELECT l.archived_at FROM projects p "
        "LEFT JOIN project_lifecycle l ON l.project_id=p.id WHERE p.id=?",
        (pid,),
    ).fetchone()
    if row is None:
        raise QualityError("Project no longer exists. No Quality changes were applied.",404)
    if row["archived_at"] is not None:
        raise QualityError(
            "Project is archived. Restore it in Manage projects before making Quality changes.",409
        )


def _project(pid: str) -> dict:
    project = storage.get_project(pid)
    if project is None:
        raise QualityError("Project not found", 404)
    return project


def _source_contract(con, p: dict):
    pid = p["id"]
    state = con.execute("SELECT original_sha256 FROM quality_state WHERE project_id=?", (pid,)).fetchone()
    if state is None:
        raise QualityError(
            "The original dataset has no recorded checksum. Import a verified original as a new project to continue. "
            "This project and its history were preserved.", 409,
        )
    receipt = None
    # Legacy projects have no receipt and keep their original checksum
    # contract. New publication receipts must agree with preserved lineage.
    try:
        row = con.execute(
            "SELECT operation_id FROM artifact_publications_v1 WHERE kind='dataset' AND subject_id=?",
            (pid,)).fetchone()
        if row is not None:
            receipt = artifact_publication.read(con, row[0])
            original = con.execute(
                "SELECT operations_json,event FROM quality_versions WHERE project_id=? AND version=0",
                (pid,)).fetchone()
            if (receipt is None or receipt.state != "committed"
                    or receipt.sha256 != state["original_sha256"]
                    or receipt.suffix != p["file_ext"]
                    or original is None or tuple(original) != ("[]", "original")):
                raise artifact_publication.PublicationError("Dataset receipt disagrees with lineage")
    except artifact_publication.PublicationError as exc:
        raise QualityError("Dataset publication integrity cannot be confirmed. Original and history preserved.", 409) from exc
    return state["original_sha256"], receipt


def _read_source(p, contract, *, capture=False, with_identity=False):
    digest, receipt = contract
    try:
        return dataset_publication.read_verified_source(
            p["dataset_path"], digest,
            size=receipt.expected_bytes if receipt is not None else None,
            capture=capture, with_identity=with_identity)
    except (OSError, storage.WorkspaceBoundaryError, artifact_publication.PublicationError) as exc:
        # Physical validation can wrap missing or inaccessible parents.
        cause = exc
        while cause.__cause__ is not None:
            cause = cause.__cause__
        if isinstance(cause, FileNotFoundError):
            raise QualityError(
                "The original dataset is missing from its recorded location. "
                "Restore or verify the exact original source before retrying. "
                "No Quality changes were applied.", 409) from exc
        if isinstance(cause, PermissionError):
            raise QualityError(
                "The original dataset cannot be read at its recorded location. "
                "Check file access before retrying. No Quality changes were applied.", 409) from exc
        if isinstance(exc, artifact_publication.PublicationError):
            raise QualityError(
                "Uploaded source file has changed outside PilotODIN or exceeds the supported "
                "40 MiB source limit. Restore the exact original or review its size. "
                "Quality history cannot be replayed safely.", 409) from exc
        raise QualityError(
            "The original dataset cannot be safely read at its recorded location. "
            "Original and history preserved.", 409) from exc


def _ensure(con, p: dict, *, capture=False) -> bytes | None:
    return _read_source(p, _source_contract(con, p), capture=capture)


def _state(con, pid: str) -> tuple[int, list[str]]:
    state = con.execute("SELECT current_version FROM quality_state WHERE project_id=?", (pid,)).fetchone()
    if state is None:
        raise QualityError("Quality state not initialized", 500)
    version = state["current_version"]
    rows = _bounded_rows(con, "SELECT operations_json FROM quality_versions WHERE project_id=? AND version=?",
                         (pid, version), max_rows=1, max_bytes=MAX_REPLAY_METADATA_BYTES)
    if not rows:
        raise QualityError("Missing current Quality version. Original and history preserved.", 409)
    return version, _operation_ids(rows[0]["operations_json"])


def _source_df(p: dict, *, raw: bytes | None = None) -> pd.DataFrame:
    """Use the same CSV decoder and identifier typing as initial import.

    Production replay supplies verified immutable bytes. The direct path
    form is retained for isolated reader-compatibility tests.
    """
    path, ext = (raw if raw is not None else p["dataset_path"]), p["file_ext"]
    if ext in (".csv", ".xlsx"):
        try:
            engine.import_preflight.preflight_dataset(path, ext)
        except ValueError as exc:
            raise QualityError(f"Source dataset failed import preflight: {exc}", 409) from exc
    if ext == ".csv":
        df = engine.read_csv_with_identifiers(path, _named_identifier)
    elif ext == ".xlsx":
        df = engine.read_xlsx_with_identifiers(path, _named_identifier)
    else:
        raise QualityError("Unsupported dataset extension")
    if df.empty or df.shape[1] < 2 or len(df) > 100000 or len(df.columns) > 100 or df.shape[0]*df.shape[1] > 6000000:
        raise QualityError("Quality engine currently supports 1–100,000 rows, 2–100 columns, at most 6 million cells")
    if not df.columns.is_unique:
        raise QualityError("Duplicate source column names")
    df.columns = [str(c).strip() for c in df.columns]
    if len(set(df.columns)) != len(df.columns) or not all(df.columns):
        raise QualityError("Invalid column names after normalization")
    return df


def _named_identifier(name: str) -> bool:
    """Delegate CSV identifier typing and Quality safety decisions to one rule."""
    return engine.is_identifier_column(name)


def _excluded_text_column(name: str) -> bool:
    compact = name.lower().replace("_", " ")
    return _named_identifier(name) or any(t in compact for t in (
        "name", "address", "description", "comment", "remark", "message", "note",
        "text", "url", "email", "password", "identifier", "reference", "free form"))


def _temporal_column(name: str) -> bool:
    """Recognise temporal field names without treating e.g. Candidate as a date."""
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    tokens = set(filter(None, re.split(r"[^a-z0-9]+", words.lower())))
    return bool(tokens & {"date", "dates", "datetime", "timestamp", "time", "dob", "period"}) or (
        "at" in tokens and bool(tokens & {"created", "updated", "modified", "deleted", "expires"})
    )


def _structured_text_value(value: str) -> bool:
    """Conservatively exclude dates, numeric tokens, URLs and codes from fuzzy spelling.

    These are heuristic vetoes, NOT permission to convert structured values.
    A false negative here means a proposed spelling fix, never an auto-change.
    """
    value = value.strip()
    if not value:
        return False
    if re.fullmatch(r"(?:https?://|www\.)\S+|\S+@\S+\.\S+", value, flags=re.I):
        return True
    if re.fullmatch(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}(?:[T ]\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?", value, flags=re.I):
        return True
    if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:\s*[AP]M)?", value, flags=re.I):
        return True
    if re.fullmatch(r"[+\-]?(?:R\s*|[$€£])?[\d\s,./:%+\-]+", value, flags=re.I):
        return True
    # Conservative protection for machine-readable or mixed alphanumeric codes:
    # AB-100, INV/2025/A, SKU001, version2. Never fuzzy-merge these.
    if any(c.isdigit() for c in value) and any(c.isalpha() for c in value):
        if not any(c.isspace() for c in value) or any(c in "-_/" for c in value):
            return True
    return False


def _safe_category(series: pd.Series, column: str) -> bool:
    if (_excluded_text_column(column) or _temporal_column(column)
            or not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series))):
        return False
    values = series.dropna()
    if len(values) < 3 or not values.map(lambda x: isinstance(x, str)).all():
        return False
    if values.map(len).max() > 75:
        return False
    count = int(values.nunique())
    if count > 100 or (count / len(values)) > .35:
        return False
    # Avoid strings that may be numbers or dates; stripping could change identifiers/semantics.
    if values.astype(str).str.fullmatch(r"[\s\d+.,/:\-]+", na=False).any():
        return False
    return True


def _native(value: Any) -> Any:
    return engine.native(value)


def _issue(kind: str, column: str | None, count: int, title: str, explanation: str,
           *, severity: str = "review", proposal: dict | None = None,
           automatic: bool = False, evidence: dict | None = None) -> dict:
    params = [kind, column, proposal or {}]
    return {"id": _fingerprint(*params), "kind": kind, "column": column,
            "affected_rows": int(count), "title": title, "explanation": explanation,
            "severity": severity, "automatic": automatic,
            "proposal": proposal, "evidence": evidence or {}}



def _outlier_profile(series: pd.Series) -> dict | None:
    """One finite-value Tukey rule for detection, preview and investigation.

    A Boolean is not a measurement. Non-finite values are not quietly treated
    as outside the IQR fences; they are counted separately as unusable values.
    """
    if not pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
        return None
    numeric = pd.to_numeric(series,errors="coerce").replace([float("inf"),float("-inf")],float("nan"))
    finite = numeric.dropna()
    if len(finite)<20 or finite.nunique()<6:
        return None
    q1,q3=float(finite.quantile(.25)),float(finite.quantile(.75))
    iqr=q3-q1
    if not iqr>0:
        return None
    low,high=q1-1.5*iqr,q3+1.5*iqr
    mask=(numeric.lt(low)|numeric.gt(high)).fillna(False)
    return {"mask":mask, "q1":q1,"q3":q3,"iqr":iqr,"low":float(low),
            "high":float(high),"outliers":int(mask.sum()),"finite_count":int(len(finite)),
            "excluded_count":int(series.notna().sum()-len(finite)),
            "median":float(finite.median()),"min":float(finite.min()),"max":float(finite.max())}


def _issues(df: pd.DataFrame) -> list[dict]:
    issues: list[dict] = []
    count = len(df)
    duplicates = int(df.duplicated().sum())
    if duplicates:
        issues.append(_issue("exact_duplicates", None, duplicates, "Exact duplicate records",
                             "Identical rows were found. Repeated records may still be legitimate; no rows were deleted.",
                             evidence={"duplicate_rows_after_first": duplicates}))
    for name in df.columns:
        s = df[name]
        missing = int(s.isna().sum())
        blanks = int(s.map(lambda v: isinstance(v, str) and not v.strip()).sum())
        if missing or blanks:
            issues.append(_issue("missing", name, missing + blanks, "Missing or blank values",
                                 "Missing values require context before treatment. No imputation was performed.",
                                 evidence={"null_count": missing, "blank_string_count": blanks,
                                           "missing_pct": round(100 * (missing + blanks) / count, 2)}))
        if _named_identifier(name) or (s.nunique(dropna=True) >= max(10, int(.98 * count)) and not pd.api.types.is_numeric_dtype(s)):
            issues.append(_issue("identifier", name, count, "Possible identifier or high-cardinality feature",
                                 "Inspect before modelling; leading zeros and unique values may be meaningful.",
                                 severity="information", evidence={"unique": int(s.nunique(dropna=True))}))
        profile=_outlier_profile(s)
        if profile and profile["outliers"]:
            issues.append(_issue("outliers", name, profile["outliers"], "Unusual numerical values",
                                 "Values outside finite-data IQR fences warrant investigation, not automatic removal.",
                                 evidence={"lower_fence":round(profile["low"],4),
                                           "upper_fence":round(profile["high"],4),
                                           "finite_values":profile["finite_count"],
                                           "excluded_nonfinite":profile["excluded_count"]}))
        if not (pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s)):
            continue
        vals = s.dropna()
        if vals.empty or not vals.map(lambda v: isinstance(v, str)).all():
            continue
        text = vals.astype(str)
        mask = text.map(lambda v: bool(v.strip()) and v != v.strip())
        n_whitespace = int(mask.sum())
        if n_whitespace:
            safe = _safe_category(s, name)
            issues.append(_issue("whitespace", name, n_whitespace, "Surrounding whitespace",
                                 "Trim surrounding spaces in ordinary category labels." if safe else
                                 "Whitespace found, but this field is not safe to normalize automatically.",
                                 severity="automatic" if safe else "review",
                                 proposal={"kind":"trim_whitespace", "column":name} if safe else None,
                                 automatic=safe, evidence={"examples": text[mask].head(5).tolist()}))
        if "date" in name.lower():
            ambig = int(text.str.fullmatch(r"(0?[1-9]|1[0-2])/(0?[1-9]|1[0-2])/(\d{2}|\d{4})", na=False).sum())
            if ambig:
                issues.append(_issue("ambiguous_dates", name, ambig, "Ambiguous date formats",
                                     "Day/month ordering is ambiguous. Confirm the date convention before conversion."))
        # Numeric text is a read-only finding, and must not silently become a
        # spelling proposal merely because one formatted number looks similar.
        numeric_like = text.str.fullmatch(r"\s*(?:R\s*)?-?\d[\d,]*(?:\.\d+)?\s*", na=False)
        if len(text) >= 3 and float(numeric_like.mean()) >= .95 and text.str.contains(r"[R,]", regex=True).any():
            issues.append(_issue("numeric_text", name, int(numeric_like.sum()), "Numbers stored as text",
                                 "Potential currency or thousands-separator formatting; review conversion and units."))
        # Temporal fields must only receive date-specific investigations. Other
        # structured values are vetoed individually even in unnamed columns.
        if _excluded_text_column(name) or _temporal_column(name) or text.nunique() > 100 or text.nunique() / len(text) > .4:
            continue
        freqs = text.value_counts()
        buckets: dict[str, list[str]] = {}
        for value in freqs.index:
            if value.strip() and value == value.strip() and not _structured_text_value(value):
                buckets.setdefault(value.casefold(), []).append(value)
        considered: set[str] = set()
        for labels in buckets.values():
            if len(labels) <= 1: continue
            target = sorted(labels, key=lambda v: (-int(freqs[v]), v))[0]
            for label in labels:
                if label == target: continue
                considered.add(label)
                issues.append(_issue("case_variant", name, int(freqs[label]), "Possible case inconsistency",
                                     f"The labels {label!r} and {target!r} differ by case. Confirm they mean the same thing.",
                                     proposal={"kind":"replace_exact", "column":name, "from":label, "to":target},
                                     evidence={"source_frequency":int(freqs[label]),"target_frequency":int(freqs[target])}))
        for source in freqs.index:
            # Whitespace findings take precedence; re-scan after normalization.
            # Avoid comparing dates, IDs, codes or structured values as words.
            if (source in considered or len(source.strip()) < 5 or not source.strip()
                    or source != source.strip() or _structured_text_value(source)):
                continue
            choices = [candidate for candidate in freqs.index if candidate != source
                       and candidate == candidate.strip() and not _structured_text_value(candidate)
                       and candidate.strip().casefold() != source.strip().casefold()
                       and len(candidate.strip()) >= 5 and int(freqs[candidate]) >= int(freqs[source]) * 2]
            matches = [(SequenceMatcher(None, source.casefold(), c.casefold()).ratio(), c) for c in choices]
            matches = sorted((ratio, c) for ratio, c in matches if ratio >= .80)
            if not matches: continue
            ratio, target = matches[-1]
            # Avoid ambiguous near-ties and duplicate proposals for the same value.
            if len(matches) > 1 and matches[-2][0] >= ratio - .04: continue
            considered.add(source)
            issues.append(_issue("spelling", name, int(freqs[source]), "Possible spelling inconsistency",
                                 f"{source!r} resembles the more common label {target!r}. Verify before merging.",
                                 proposal={"kind":"replace_exact", "column":name, "from":source, "to":target},
                                 evidence={"similarity":round(ratio,3),"source_frequency":int(freqs[source]),
                                           "target_frequency":int(freqs[target])}))
    order = {"automatic":0,"review":1,"information":2}
    return sorted(issues, key=lambda issue: (order.get(issue["severity"],3), -issue["affected_rows"], issue["kind"]))


def _decisions(con, pid: str) -> dict[str, str]:
    return {r["issue_id"]: r["status"] for r in con.execute(
        "SELECT issue_id,status FROM quality_decisions WHERE project_id=?", (pid,)).fetchall()}


def _reviewed_issues(frame: pd.DataFrame, choices: dict[str, str]) -> list[dict]:
    issues = _issues(frame)
    for issue in issues:
        issue["decision"] = choices.get(issue["id"], "pending")
    return issues


def _apply(df: pd.DataFrame, action: dict, *, expected_affected: int | None = None) -> tuple[pd.DataFrame,int]:
    name, kind = action["column"], action["kind"]
    if name not in df.columns:
        raise QualityError(f"Transformation references missing column: {name}",409)
    result = df.copy()
    s = result[name]
    if kind == "trim_whitespace":
        if not _safe_category(s, name):
            raise QualityError(f"Column {name!r} is not eligible for automatic whitespace normalization",409)
        mask = s.map(lambda x: isinstance(x,str) and bool(x.strip()) and x != x.strip())
        affected = int(mask.sum())
        result.loc[mask,name] = s[mask].map(str.strip)
    elif kind == "replace_exact":
        a,b=action.get("from"),action.get("to")
        if not isinstance(a,str) or not isinstance(b,str) or not a or not b or a==b:
            raise QualityError("Invalid category correction")
        if _excluded_text_column(name) or not (pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s)):
            raise QualityError("Category correction requires a suitable textual categorical field",409)
        mask=s.map(lambda x: isinstance(x,str) and x==a)
        affected=int(mask.sum())
        result.loc[mask,name]=b
    elif kind == "impute_numeric_median":
        if not pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s):
            raise QualityError("Median imputation requires a numeric column",409)
        if not s.isna().any():raise QualityError("No missing numeric values remain",409)
        present=pd.to_numeric(s,errors='coerce').replace([float('inf'),-float('inf')],float('nan')).dropna()
        if present.empty:raise QualityError("No observed numeric values to calculate a median",409)
        actual=float(present.median())
        chosen=action.get('value')
        if not isinstance(chosen,(int,float)) or not math.isfinite(float(chosen)) or not math.isclose(float(chosen),actual,rel_tol=1e-10,abs_tol=1e-9):
            raise QualityError("Imputation median changed; review the updated dataset before applying",409)
        affected=int(s.isna().sum())
        result[name]=s.fillna(actual)
    else:
        raise QualityError("Unsupported transformation type")
    if affected == 0:
        raise QualityError("No matching values remain for this correction",409)
    if expected_affected is not None and affected != expected_affected:
        raise QualityError("Dependent transformation changed its affected rows; restore a compatible version instead",409)
    before_missing=int(df.isna().sum().sum())
    after_missing=int(result.isna().sum().sum())
    expected_missing=before_missing-affected if kind=='impute_numeric_median' else before_missing
    if len(df)!=len(result) or list(df.columns)!=list(result.columns) or after_missing!=expected_missing:
        raise QualityError("Transformation failed row, schema or missingness validation",409)
    return result,affected


def _materialize(con, p: dict, ops: list[str], *, raw: bytes | None = None) -> pd.DataFrame:
    if raw is None:
        raw = _ensure(con, p, capture=True)
    df = _source_df(p, raw=raw)
    del raw
    for action_id in ops:
        row = con.execute("SELECT * FROM quality_actions WHERE project_id=? AND id=?", (p["id"],action_id)).fetchone()
        if row is None: raise QualityError("Missing transformation from history", 409)
        df,_ = _apply(df, json.loads(row["params_json"]), expected_affected=row["affected_rows"])
    return df


def _metadata_snapshot(con, pid, *, target_version=None):
    """Capture metadata only in the caller's short explicit transaction."""
    row = con.execute(
        "SELECT p.*, l.revision AS lifecycle_revision,l.archived_at AS lifecycle_archived "
        "FROM projects p LEFT JOIN project_lifecycle l ON p.id=l.project_id WHERE p.id=?", (pid,)
    ).fetchone()
    if row is None:
        raise QualityError("Project not found", 404)
    if row["lifecycle_archived"] is not None:
        raise QualityArchivedError("Project is archived. Restore it in Manage projects before making Quality changes.", 409)
    p = dict(row)
    contract = _source_contract(con, p)
    version, ops = _state(con, pid)
    selected_version = version if target_version is None else target_version
    selected = _bounded_rows(con, "SELECT * FROM quality_versions WHERE project_id=? AND version=?",
                             (pid, selected_version), max_rows=1, max_bytes=MAX_REPLAY_METADATA_BYTES)
    if not selected:
        raise QualityError("Requested dataset version does not exist", 404)
    version_row = selected[0]
    selected_ops = _operation_ids(version_row["operations_json"])
    remaining = MAX_REPLAY_METADATA_BYTES - _row_bytes(version_row) - len(_json(ops).encode("utf-8"))
    if remaining < 0:
        raise _metadata_limit()
    rows = []
    for action_id in selected_ops:
        actions = _bounded_rows(con, "SELECT * FROM quality_actions WHERE project_id=? AND id=?",
                                (pid, action_id), max_rows=1, max_bytes=remaining)
        if not actions:
            raise QualityError("Missing transformation from history", 409)
        action = actions[0]
        remaining -= _row_bytes(action)
        rows.append(dict(action))
    decisions = [dict(r) for r in _bounded_rows(con,
        "SELECT * FROM quality_decisions WHERE project_id=? ORDER BY issue_id", (pid,),
        max_bytes=remaining)]
    return {"project": p, "contract": contract, "version": version, "ops": ops,
            "selected_version": selected_version, "version_row": dict(version_row),
            "actions": rows, "decisions": decisions}


def _read_metadata(pid, *, target_version=None):
    _project(pid)
    with storage.connect() as con:
        con.execute("BEGIN")
        return _metadata_snapshot(con, pid, target_version=target_version)


def _replay_snapshot(frame, metadata):
    for row in metadata["actions"]:
        frame, _ = _apply(frame, json.loads(row["params_json"]), expected_affected=row["affected_rows"])
    return frame


def _snapshot_frame(metadata, *, original=False, with_identity=False):
    raw, identity = _read_source(metadata["project"], metadata["contract"], capture=True, with_identity=True)
    base = _source_df(metadata["project"], raw=raw)
    del raw
    frame = _replay_snapshot(base, metadata)
    return (base if original else None), frame, identity if with_identity else None


def _snapshot_decisions(metadata):
    return {row["issue_id"]: row["status"] for row in metadata["decisions"]}


def _stage_current(pid, expected_version):
    metadata = _read_metadata(pid)
    _check_version(metadata["version"], expected_version)
    _, frame, identity = _snapshot_frame(metadata, with_identity=True)
    return metadata, frame, identity


def _verify_staged_write(con, pid, metadata, identity):
    _require_active_for_write(con, pid)
    current = _metadata_snapshot(con, pid, target_version=metadata["selected_version"])
    _check_version(current["version"], metadata["version"])
    if current != metadata:
        raise QualityError("Quality project, history or decisions changed. Review the updated findings.", 409)
    _, observed = _read_source(current["project"], current["contract"], with_identity=True)
    if not dataset_publication._same_bytes_metadata(identity, observed):
        raise QualityError("Original dataset identity changed during Quality review. No changes applied.", 409)


def _check_version(actual: int, expected: int) -> None:
    if actual!=expected:
        raise QualityError(f"Dataset version changed from {expected} to {actual}. Review the updated findings before applying changes.",409)


def _add_version(con, pid: str, ops: list[str], event: str, detail: dict) -> int:
    # Never reuse a version number after restore/undo.
    encoded = _json(ops)
    _operation_ids(encoded)
    new = con.execute("SELECT COALESCE(MAX(version), -1)+1 FROM quality_versions WHERE project_id=?",(pid,)).fetchone()[0]
    con.execute("INSERT INTO quality_versions VALUES(?,?,?,?,?,?)",
                (pid,new,encoded,event,_json(detail),storage.now()))
    con.execute("UPDATE quality_state SET current_version=? WHERE project_id=?",(new,pid))
    return new


def _record_validated_action(con, p: dict, ops: list[str], proposal: dict,
                             source: str, issue_id: str, affected: int) -> tuple[int, dict]:
    """Persist metadata for an action already validated against the exact version.

    The caller owns the BEGIN IMMEDIATE transaction and must fence the active
    project, original checksum, history, receipt and decision states before use.
    This helper does not validate or replay user data on its own.
    """
    if not con.in_transaction:
        raise RuntimeError("Validated Quality actions require the current write transaction")
    action_id=storage.uid()
    con.execute("INSERT INTO quality_actions VALUES(?,?,?,?,?,?,?,?)",
                (action_id,p["id"],proposal["kind"],proposal["column"],_json(proposal),source,affected,storage.now()))
    nxt=_add_version(con,p["id"],[*ops,action_id],"apply",{"action_id":action_id,"issue_id":issue_id,"source":source})
    con.execute("INSERT OR REPLACE INTO quality_decisions VALUES(?,?,?,?)",
                (p["id"],issue_id,"applied",storage.now()))
    return nxt,{"id":action_id,"kind":proposal["kind"],"column":proposal["column"],
                "source":source,"affected_rows":affected}


def _record_action(con, p: dict, ops: list[str], proposal: dict, source: str,
                   issue_id: str) -> tuple[int,dict]:
    df=_materialize(con,p,ops)
    _,affected=_apply(df,proposal)
    return _record_validated_action(con,p,ops,proposal,source,issue_id,affected)


def snapshot(pid: str, preview_limit: int = 7) -> dict:
    metadata = _read_metadata(pid)
    version, ops = metadata["version"], metadata["ops"]
    _, df, _ = _snapshot_frame(metadata)
    issues = _reviewed_issues(df, _snapshot_decisions(metadata))
    actionable=[x for x in issues if x["decision"]=="pending"]
    return {"project_id":pid,"version":version,"rows":len(df),"columns":len(df.columns),
            "summary":{"issues":len(issues),"automatic_available":sum(x["automatic"] for x in actionable),
                       "review_required":sum(x["severity"]=="review" for x in actionable),
                       "information":sum(x["severity"]=="information" for x in actionable),
                       "applied_actions":len(ops)},
            "issues":issues,"preview":engine.native(df.head(min(preview_limit,20)).to_dict(orient="records")),
            "integration_note":"Approved working versions are now used for new analysis and ML experiments."}


def autopilot(pid: str, expected_version: int) -> dict:
    metadata, frame, identity = _stage_current(pid, expected_version)
    decisions = _snapshot_decisions(metadata)
    staged = []
    # Preserve original finding order and sequential validation. Do not
    # recalculate candidate findings mid-batch or silently skip failures.
    for issue in _issues(frame):
        if not issue["automatic"] or not issue["proposal"] or issue["id"] in decisions:
            continue
        frame, affected = _apply(frame, issue["proposal"])
        staged.append((issue["id"], issue["proposal"], affected))
        decisions[issue["id"]] = "applied"
    del frame
    version, ops = metadata["version"], list(metadata["ops"])
    completed = []
    with storage.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        _verify_staged_write(con, pid, metadata, identity)
        for issue_id, proposal, affected in staged:
            version, action = _record_validated_action(con, metadata["project"], ops, proposal,
                                                        "autopilot", issue_id, affected)
            ops.append(action["id"])
            completed.append(action)
        _check_history_budget(con, pid)
        return {"version":version,"applied":completed,"count":len(completed),
                "message":f"{len(completed)} narrowly safe correction(s) applied; see history for details."}

def decide(pid: str, issue_id: str, expected_version: int, decision: str) -> dict:
    if decision not in ("approve","reject"):
        raise QualityError("Decision must be approve or reject")
    metadata, frame, identity = _stage_current(pid, expected_version)
    matching = next((x for x in _issues(frame) if x["id"] == issue_id), None)
    if matching is None:
        raise QualityError("Finding no longer exists; refresh quality scan",409)
    prior = _snapshot_decisions(metadata).get(issue_id)
    if prior == "applied" or (prior is not None and decision == "reject"):
        raise QualityError("This finding has already been decided; review its audit entry",409)
    affected = None
    if decision == "approve":
        if not matching["proposal"]:
            raise QualityError("This issue is investigation-only; no executable correction was proposed")
        transformed, affected = _apply(frame, matching["proposal"])
        del transformed
    del frame
    version, ops = metadata["version"], metadata["ops"]
    with storage.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        _verify_staged_write(con, pid, metadata, identity)
        if decision == "reject":
            con.execute("INSERT INTO quality_decisions VALUES(?,?,?,?)",(pid,issue_id,"rejected",storage.now()))
            _check_history_budget(con, pid)
            return {"version":version,"decision":"rejected","issue_id":issue_id,"applied":False}
        version, action = _record_validated_action(con, metadata["project"], ops, matching["proposal"],
                                                    "user_approved", issue_id, affected)
        _check_history_budget(con, pid)
        return {"version":version,"decision":"approved","issue_id":issue_id,"applied":True,"action":action}


def approve_imputation(pid:str,column:str,issue_id:str,expected_version:int,strategy:str='median')->dict:
    """Stage approved numeric imputation outside the metadata write lock."""
    if strategy!='median':raise QualityError('Only reviewed numeric median imputation is supported')
    metadata, df, identity = _stage_current(pid, expected_version)
    matching=next((x for x in _issues(df) if x['id']==issue_id and x['kind']=='missing' and x['column']==column),None)
    if matching is None:raise QualityError('Missing-value issue changed; refresh findings',409)
    if column not in df or not pd.api.types.is_numeric_dtype(df[column]) or pd.api.types.is_bool_dtype(df[column]):
        raise QualityError('Only numeric columns are eligible for median imputation')
    if not df[column].notna().any():raise QualityError('No observed numeric values to impute from')
    median=float(df[column].dropna().median())
    if not math.isfinite(median):raise QualityError('Median is not finite')
    proposal={'kind':'impute_numeric_median','column':column,'value':median}
    transformed, affected = _apply(df, proposal)
    del transformed, df
    with storage.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        _verify_staged_write(con, pid, metadata, identity)
        nxt, action = _record_validated_action(con, metadata["project"], metadata["ops"], proposal,
                                                "user_approved", issue_id, affected)
        _check_history_budget(con, pid)
        return {'version':nxt,'decision':'approved','strategy':'median','filled_value':median,
                'affected_rows':action['affected_rows'],'action':action,
                'note':'Reviewed working-version imputation. Original retained; use History to undo. An imputation indicator column was not added.'}


def _check_history_budget(con, pid):
    """Fence the resulting state inside the same mutation transaction.

    Do not publish a new version that the bounded replay/history paths cannot
    read. Legacy over-budget records remain intact, including on refusal.
    """
    _metadata_snapshot(con, pid)
    _bounded_rows(con, "SELECT * FROM quality_versions WHERE project_id=?", (pid,),
                  collect=False, validate=lambda row: _operation_ids(row["operations_json"]))
    for table in ("quality_actions", "quality_decisions"):
        _bounded_rows(con, f"SELECT * FROM {table} WHERE project_id=?", (pid,), collect=False)


def history(pid: str) -> dict:
    p=_project(pid)
    with storage.connect() as con:
        _ensure(con,p)
        con.execute("BEGIN")
        current,ops=_state(con,pid)
        active = set(ops)
        versions=[{"version":r["version"],"operations":_operation_ids(r["operations_json"]),
                   "event":r["event"],"details":json.loads(r["details_json"]),"created_at":r["created_at"]}
                  for r in _bounded_rows(con,"SELECT * FROM quality_versions WHERE project_id=? ORDER BY version",(pid,))]
        actions=[{"id":r["id"],"kind":r["kind"],"column":r["column_name"],
                  "params":json.loads(r["params_json"]),"source":r["source"],
                  "affected_rows":r["affected_rows"],"created_at":r["created_at"],"active":r["id"] in active}
                 for r in _bounded_rows(con,"SELECT * FROM quality_actions WHERE project_id=? ORDER BY created_at, id",(pid,))]
        decisions=[dict(r) for r in _bounded_rows(con,"SELECT * FROM quality_decisions WHERE project_id=? ORDER BY created_at",(pid,))]
        return {"current_version":current,"versions":versions,"actions":actions,"decisions":decisions}


def _apply_event_rows(con, pid):
    return [tuple(row) for row in _bounded_rows(con,
        "SELECT version,details_json FROM quality_versions WHERE project_id=? AND event='apply' ORDER BY version",
        (pid,))]


def _stage_history_transition(pid, expected_version, *, action_id=None, target_version=None):
    _project(pid)
    with storage.connect() as con:
        con.execute("BEGIN")
        current = _metadata_snapshot(con, pid)
        _check_version(current["version"], expected_version)
        if action_id is not None:
            if action_id not in current["ops"]:
                raise QualityError("Action is not active in the current dataset version",409)
            target = [x for x in current["ops"] if x != action_id]
            replay = {**current, "actions": [r for r in current["actions"] if r["id"] != action_id]}
            historical = None
        else:
            historical = _metadata_snapshot(con, pid, target_version=target_version)
            target = json.loads(historical["version_row"]["operations_json"])
            replay = historical
        events = _apply_event_rows(con, pid)
    # Validate the remaining operations against a single verified original,
    # not against the already-transformed working frame.
    _, frame, identity = _snapshot_frame(replay, with_identity=True)
    del frame
    removed = set(current["ops"]) - set(target)
    suppress = {}
    for _, raw in events:
        detail = json.loads(raw)
        aid = detail.get("action_id")
        if aid in removed and detail.get("issue_id") and aid not in suppress:
            suppress[aid] = detail["issue_id"]
    return current, historical, target, events, suppress, identity


def _commit_history_transition(pid, expected_version, *, action_id=None, target_version=None):
    current, historical, target, events, suppress, identity = _stage_history_transition(
        pid, expected_version, action_id=action_id, target_version=target_version)
    with storage.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        _verify_staged_write(con, pid, current, identity)
        if historical is not None and _metadata_snapshot(con, pid, target_version=target_version) != historical:
            raise QualityError("Restore target history changed. Review the updated findings.",409)
        if _apply_event_rows(con, pid) != events:
            raise QualityError("Quality action audit history changed. Review the updated findings.",409)
        if action_id is not None:
            nxt = _add_version(con, pid, target, "undo", {"action_id":action_id,"prior_version":expected_version})
        else:
            nxt = _add_version(con, pid, target, "restore", {"from_version":target_version,"prior_version":expected_version})
        for issue_id in suppress.values():
            con.execute("INSERT OR REPLACE INTO quality_decisions VALUES(?,?,?,?)",
                        (pid,issue_id,"undone",storage.now()))
        _check_history_budget(con, pid)
        if action_id is not None:
            return {"version":nxt,"undone":action_id,"active_actions":len(target)}
        return {"version":nxt,"restored_from":target_version,"active_actions":len(target)}


def undo(pid: str, action_id: str, expected_version: int) -> dict:
    return _commit_history_transition(pid, expected_version, action_id=action_id)


def restore(pid: str, target_version: int, expected_version: int) -> dict:
    return _commit_history_transition(pid, expected_version, target_version=target_version)

def preview(pid: str, issue_id: str | None = None, offset: int = 0, limit: int = 20,
            expected_version: int | None = None) -> dict:
    if offset < 0 or limit < 1 or limit > 200:
        raise QualityError("Offset must be nonnegative; limit must be 1–200")
    metadata = _read_metadata(pid)
    version = metadata["version"]
    if expected_version is not None and expected_version != version:
        raise QualityError('Working dataset changed. Refresh Quality before inspecting rows.',409)
    original, current, _ = _snapshot_frame(metadata, original=True)
    issue=None
    if issue_id is not None:
        issue=next((x for x in _issues(current) if x["id"]==issue_id),None)
        if issue is None: raise QualityError("Finding no longer exists",404)
        col=issue["column"]
        if col and issue["proposal"]:
            prop=issue["proposal"]
            if prop["kind"]=="replace_exact":
                indexes=current.index[current[col].map(lambda v: isinstance(v,str) and v==prop["from"])].tolist()
            elif prop["kind"]=="trim_whitespace":
                indexes=current.index[current[col].map(lambda v: isinstance(v,str) and bool(v.strip()) and v!=v.strip())].tolist()
            else: indexes=list(current.index)
        elif issue["kind"]=="missing" and col:
            indexes=current.index[current[col].map(lambda v: pd.isna(v) or (isinstance(v,str) and not v.strip()))].tolist()
        elif issue["kind"]=="outliers" and col:
            outlier_profile=_outlier_profile(current[col])
            indexes=current.index[outlier_profile["mask"]].tolist() if outlier_profile else []
        elif issue["kind"]=="exact_duplicates":
            indexes=current.index[current.duplicated(keep="first")].tolist()
        elif issue["kind"]=="identifier" and col:
            # Include missing identifier cells in the same review population
            # represented by the finding's affected row count.
            indexes=list(current.index)
        else:
            indexes=list(current.index)
    else:
        indexes=list(current.index)
    selected=indexes[offset:offset+limit]
    rows=[]
    for i in selected:
        before=engine.native(original.loc[i].to_dict())
        after=engine.native(current.loc[i].to_dict())
        proposed=dict(after)
        if issue and issue["proposal"]:
            prop=issue["proposal"]
            col=prop["column"]
            if prop["kind"]=="replace_exact" and after[col]==prop["from"]:
                proposed[col]=prop["to"]
            if prop["kind"]=="trim_whitespace" and isinstance(after[col],str):
                proposed[col]=after[col].strip()
        rows.append({"row_number":int(i)+1,"original":before,"working":after,
                     "proposed":proposed if issue and issue["proposal"] else None})
    return {"version":version,"total_matching_rows":len(indexes),"offset":offset,
            "limit":limit,"issue_id":issue_id,"rows":rows}


_init_tables()


def current_data(pid: str) -> tuple[pd.DataFrame,int]:
    """Materialize the exact captured working version outside a database lock."""
    metadata = _read_metadata(pid)
    _, frame, _ = _snapshot_frame(metadata)
    return frame, metadata["version"]


def current_data_with_findings(pid: str) -> tuple[pd.DataFrame, int, list[dict]]:
    """Read one working version and its captured review decisions."""
    metadata = _read_metadata(pid)
    _, frame, _ = _snapshot_frame(metadata)
    return frame, metadata["version"], _reviewed_issues(frame, _snapshot_decisions(metadata))


def data_at_version(pid: str, version: int) -> pd.DataFrame:
    """Read an exact historical working version without holding a DB lock."""
    if version < 0:
        raise QualityError("Dataset version must be nonnegative")
    metadata = _read_metadata(pid, target_version=version)
    _, frame, _ = _snapshot_frame(metadata)
    return frame


def current_version(pid: str) -> int:
    p = _project(pid)
    with storage.connect() as con:
        _ensure(con,p)
        version,_=_state(con,pid)
        return version
