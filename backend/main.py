"""PilotODIN local-first FastAPI application."""
from __future__ import annotations

import io
import asyncio
import logging
from contextlib import asynccontextmanager
import json
import math
import os
import re
import shutil
import traceback
import hmac
from fastapi.responses import JSONResponse, FileResponse, Response
from pathlib import Path
from typing import Literal

import joblib
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from starlette.background import BackgroundTask

try:
    from . import ai_provider, ai_context, engine, storage, quality, quality_investigations, analytics, explore_filters, explore_inspector, column_intelligence, saved_analyses, data_exports, quality_approvals, reports, resource_policy, semantic_profile, target_opportunities
except ImportError:
    import ai_provider, ai_context, engine, storage, quality, quality_investigations, analytics, explore_filters, explore_inspector, column_intelligence, saved_analyses, data_exports, quality_approvals, reports, resource_policy, semantic_profile, target_opportunities

@asynccontextmanager
async def _lifespan(_app:FastAPI):
    """Start responsive: verify configured cloud providers in background only after consent."""
    # FastAPI BackgroundTasks do not survive a backend restart. Explicitly
    # fail orphaned ML records before admitting new work; never auto-retrain.
    recovered=storage.recover_interrupted_experiments()
    if recovered:
        logging.warning("Marked %s unfinished ML experiment(s) failed after backend restart",recovered)
    checks=[]
    try:
        cfg=ai_provider.config_status()
        if cfg.get('cloud_enabled') and cfg.get('share_aggregates'):
            for provider in cfg['providers']:
                if provider['connected']:
                    ai_provider._health[provider['id']]={'status':'checking'}
                    checks.append(asyncio.create_task(asyncio.to_thread(ai_provider.test_connection,provider['id'])))
    except (OSError,ValueError):
        pass  # Local analysis must start even with corrupt optional AI configuration.
    yield
    for job in checks:
        if not job.done():job.cancel()

app = FastAPI(title="PilotODIN", version="0.8.0",description="Local-first intelligent analytics workspace",lifespan=_lifespan)
app.add_middleware(CORSMiddleware,
                   allow_origin_regex=r"(?:http://(?:localhost|127\.0\.0\.1):517[3-9]|https?://tauri\.localhost|tauri://localhost)",
                   allow_credentials=False,allow_methods=["*"],allow_headers=["*"],
                   expose_headers=["Content-Disposition"])
MAX_BYTES = 40 * 1024 * 1024

# Desktop mode uses a randomly generated per-launch secret supplied by the
# Rust shell through the SIDE-CAR ENVIRONMENT, never through a URL or bundle.
# CORS alone cannot protect a loopback HTTP server against local processes.
# Existing browser-only dev mode remains unchanged when the secret is absent.
_DESKTOP_ORIGINS = {"http://tauri.localhost", "https://tauri.localhost", "tauri://localhost"}


def _allowed_desktop_origin(origin: str) -> bool:
    if origin in _DESKTOP_ORIGINS:
        return True
    return bool(os.environ.get("PILOTODIN_DESKTOP_ALLOW_DEV") == "1" and
                re.fullmatch(r"http://(?:localhost|127\.0\.0\.1):517[3-9]", origin))


@app.middleware("http")
async def desktop_session_guard(request: Request, call_next):
    secret = os.environ.get("PILOTODIN_DESKTOP_SESSION", "")
    if not secret:
        return await call_next(request)
    # Let CORSMiddleware handle preflight; it must not grant an arbitrary
    # cross-site origin permission. Browser actual requests still need token.
    if request.method == "OPTIONS":
        return await call_next(request)
    origin = request.headers.get("origin", "")
    if origin and not _allowed_desktop_origin(origin):
        return JSONResponse({"detail": "Untrusted desktop request origin"}, status_code=403)
    host = request.url.hostname
    if host not in ("127.0.0.1", "localhost", "testserver"):
        return JSONResponse({"detail": "Desktop API is local-only"}, status_code=403)
    provided = request.headers.get("x-pilotodin-session", "")
    if not hmac.compare_digest(provided, secret):
        return JSONResponse({"detail": "Desktop session authentication required"}, status_code=401)
    return await call_next(request)


class ExperimentRequest(BaseModel):
    target: str
    task: str
    excluded_features: list[str] = Field(default_factory=list)
    models: list[str] = Field(min_length=1,max_length=5)
    acknowledge_random_split: bool = False
    acknowledge_feature_risks: bool = False
    split_strategy: str = 'random'
    split_column: str | None = None
    expected_quality_version: int | None = Field(default=None, ge=0)
    # An explicit cooperative soft timeout. No implicit deadline; sklearn fit
    # and cross_val_score are not forcibly interrupted mid-call.
    max_duration_seconds: int | None = Field(default=None, ge=60, le=14400)

class SelectionRequest(BaseModel):
    model_key: str

class QualityVersionRequest(BaseModel):
    expected_version: int = Field(ge=0)

class QualityDecisionRequest(QualityVersionRequest):
    issue_id: str = Field(min_length=1, max_length=128)
    decision: str

class QualityUndoRequest(QualityVersionRequest):
    action_id: str = Field(min_length=1, max_length=128)

class QualityRestoreRequest(QualityVersionRequest):
    target_version: int = Field(ge=0)

class PredictRequest(BaseModel):
    values: dict[str, str | float | int | bool | None]


def project_or_404(pid):
    p = storage.get_project(pid)
    if p is None: raise HTTPException(status_code=404,detail="Project not found")
    return p


def experiment_or_404(eid):
    exp=storage.get_experiment(eid)
    if exp is None: raise HTTPException(status_code=404,detail="Experiment not found")
    return exp


def df_for(p, expected_version: int | None = None):
    try:
        df, version = quality.current_data(p["id"])
        if expected_version is not None and expected_version != version:
            raise HTTPException(status_code=409, detail=f"Dataset version changed from {expected_version} to {version}. Refresh before training.")
        return df
    except quality.QualityError as e:
        raise HTTPException(status_code=e.status,detail=str(e)) from e
    except (ValueError, OSError) as e:
        raise HTTPException(status_code=422,detail=str(e)) from e


@app.get("/api/health")
def health():
    return {"status":"ok","mode":"local_with_opt_in_cloud","cloud_ai":ai_provider.config_status()["cloud_enabled"]}


@app.get("/api/projects")
def projects(): return storage.list_projects()


def _rollback_failed_project_import(pid: str | None, path: Path) -> None:
    """Undo import metadata transactionally before deleting staged source bytes.

    The Quality tables may not exist if a workspace upgrade/init failed.
    Never let a second 'no such table' error mask the original import failure,
    and never delete the source while a failed metadata rollback would still
    leave a database project pointing to it.
    """
    if pid is not None:
        with storage.connect() as con:
            tables = {row["name"] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            for table in ("quality_versions", "quality_state"):
                if table in tables:
                    con.execute(f"DELETE FROM {table} WHERE project_id=?", (pid,))
            con.execute("DELETE FROM projects WHERE id=?", (pid,))
    path.unlink(missing_ok=True)


@app.post("/api/projects",status_code=201)
async def create_project(file: UploadFile = File(...)):
    filename=Path(file.filename or "dataset").name
    ext=Path(filename).suffix.lower()
    if ext not in (".csv",".xlsx"):
        raise HTTPException(status_code=400,detail="Please upload a CSV or XLSX dataset")
    b=await file.read(MAX_BYTES+1)
    await file.close()
    if len(b)>MAX_BYTES:
        raise HTTPException(status_code=413,detail="File exceeds local 40 MB limit")
    if not b: raise HTTPException(status_code=400,detail="Empty file")
    path=storage.HOME / "datasets" / f"{storage.uid()}{ext}"
    # Do not expose a partially written upload as an immutable source file.
    # A unique staging name is deleted after catchable write/rename failures.
    staging=path.with_name(path.name+".uploading")
    pid=None
    try:
        with staging.open("xb") as output:
            output.write(b)
            output.flush()
            os.fsync(output.fileno())
        os.replace(staging,path)
        df=engine.read_data(str(path),ext)
        prof=engine.profile(df,filename)
        pid=storage.save_project(Path(filename).stem,filename,ext,path,prof)
        quality.register(pid)  # Anchor the immutable source hash at upload.
    except Exception as e:
        staging_cleanup_failed=False
        try:
            staging.unlink(missing_ok=True)
        except OSError:
            staging_cleanup_failed=True
            logging.exception("Failed to remove interrupted upload staging file")
        try:
            _rollback_failed_project_import(pid, path)
        except Exception:
            # Retain staged bytes if metadata could not be rolled back, so a
            # dangling database reference is not silently made unrecoverable.
            logging.exception("Import rollback incomplete; manual workspace recovery is required")
            raise HTTPException(status_code=500,
                                detail="Import failed and could not be rolled back safely. Check local logs before retrying.") from e
        if staging_cleanup_failed:
            raise HTTPException(
                status_code=500,
                detail="Import failed and temporary upload cleanup was incomplete. Check local logs before retrying.",
            ) from e
        raise HTTPException(status_code=422,detail=f"Could not process dataset: {str(e)[:280]}") from e
    return {"id":pid,"name":Path(filename).stem,"profile":prof}


@app.get("/api/projects/{project_id}")
def get_project(project_id:str):
    p=project_or_404(project_id)
    p.pop("dataset_path",None)
    return {**p, "experiments":storage.recent_experiments(project_id),"ai":ai_provider.LocalRulesProvider().interpret(p["profile"])}


@app.get("/api/projects/{project_id}/preparation")
def prepare(project_id:str,target:str):
    p=project_or_404(project_id)
    try: return engine.preparation(df_for(p),target)
    except ValueError as e: raise HTTPException(status_code=422,detail=str(e))


def train_background(eid:str,pid:str,config:dict):
    # Compare-and-set: never resurrect a job marked terminal or interrupted.
    if not storage.claim_queued_experiment(eid):
        return
    artifact_path = None
    finished = False
    try:
        storage.check_training_interruption(eid)
        p=storage.get_project(pid)
        df=df_for(p,config["quality_version"])
        if not storage.advance_running_experiment(
            eid,"training_models","Data loaded; cross-validating and fitting the selected model candidates."
        ):
            return  # A recovery/terminal transition superseded this worker.
        result, pipes, x_test, y_test = engine.run_training(
            df,**{k:config[k] for k in ("target","excluded","models","task","split_strategy","split_column")},
            stop_check=lambda: storage.check_training_interruption(eid),
        )
        if not storage.advance_running_experiment(
            eid,"saving_artifacts","Model comparisons finished; saving fitted pipelines and held-out evaluation data."
        ):
            return
        # Only locally produced artifacts are loaded; untrusted model uploads
        # are prohibited. This directory belongs exclusively to the new ID.
        path=storage.HOME / "models" / eid
        storage.check_training_interruption(eid)
        path.mkdir(parents=True,exist_ok=False)
        artifact_path = path
        for name,pipe in pipes.items():
            storage.check_training_interruption(eid)
            joblib.dump(pipe,path/f"{name}.joblib")
        storage.check_training_interruption(eid)
        joblib.dump((x_test,y_test),path/"test_set.joblib")
        storage.check_training_interruption(eid)
        finished = storage.finish_running_experiment(eid,"completed",results=result)
    except storage.TrainingInterrupted as e:
        storage.finish_interrupted_experiment(eid,e.status)
    except Exception as e:
        storage.finish_running_experiment(eid,"failed",error=f"{type(e).__name__}: {str(e)[:600]}")
    finally:
        # A failed/cancelled run never exposes partial fitted pipelines to
        # the model-library paths used by completed experiments.
        if artifact_path is not None and not finished:
            shutil.rmtree(artifact_path,ignore_errors=True)


@app.post("/api/projects/{project_id}/experiments",status_code=202)
def new_experiment(project_id:str,body:ExperimentRequest,background_tasks:BackgroundTasks):
    p=project_or_404(project_id)
    if body.split_strategy not in ('random','group','time'):
        raise HTTPException(status_code=422,detail='Choose random, group, or time validation')
    if body.split_strategy=='random' and not body.acknowledge_random_split:
        raise HTTPException(status_code=422,detail="Confirm that a random split is appropriate (no grouped individuals or time-based leakage).")
    if body.split_strategy!='random' and not body.split_column:
        raise HTTPException(status_code=422,detail='A group or date column is required')
    try:
        df, version = quality.current_data(project_id)
        if body.expected_quality_version is not None and body.expected_quality_version != version:
            raise HTTPException(status_code=409, detail=f"Dataset version changed from {body.expected_quality_version} to {version}. Refresh before training.")
        if body.split_column and body.split_column not in df.columns:raise ValueError('Split column not found')
        if body.split_strategy!='random' and body.split_column==body.target:
            raise ValueError('Target cannot also be a split column')
        # Match the worker's effective predictor set before capacity checks.
        # The split key remains available in the original frame for group/time CV.
        fit_excluded=list(dict.fromkeys([*body.excluded_features,
            *([body.split_column] if body.split_strategy!='random' else [])]))
        engine.validate_config(df,body.target,fit_excluded,body.models,body.task)
        preparation_audit=engine.preparation(df,body.target)
        included_risks=sorted(set(preparation_audit["high_risk_features"])-set(body.excluded_features)
                              -({body.split_column} if body.split_strategy!="random" else set()))
        if included_risks and not body.acknowledge_feature_risks:
            raise ValueError("Review high-risk predictors ("+", ".join(included_risks[:8])+
                             "). Exclude them or explicitly acknowledge potential leakage before training.")
    except quality.QualityError as e:
        raise HTTPException(status_code=e.status,detail=str(e)) from e
    except ValueError as e: raise HTTPException(status_code=422,detail=str(e))
    # Low-memory policy gates only NEW training requests before creating
    # experiment history or scheduling work. Existing engine model/row/matrix
    # caps and split/leakage checks still apply independently.
    admission = resource_policy.admit_new_work("training")
    if admission["decision"] == "defer":
        raise HTTPException(status_code=503, detail={
            "code": admission["code"], "operation": "training",
            "message": admission["note"],
            "available_gib": admission["available_gib"],
            "required_free_gib": admission["required_free_gib"],
            "retryable": True,
        })
    config={"target":body.target,"task":body.task,"excluded":body.excluded_features,"models":body.models,
            "quality_version":version,"split_strategy":body.split_strategy,"split_column":body.split_column,
            "acknowledge_feature_risks":bool(body.acknowledge_feature_risks),
            "reviewed_high_risk_features":included_risks,
            "max_duration_seconds":body.max_duration_seconds}
    try:
        if admission["mode"] == "low_memory":
            # Atomic across request threads/process connections: one heavy
            # ML training job at a time while Low-memory is selected.
            eid=storage.new_experiment_with_capacity(project_id,config)
        else:
            eid=storage.new_experiment(project_id,config)
    except storage.TrainingSlotBusy as exc:
        raise HTTPException(status_code=503,detail={
            "code": "ml_training_slot_busy", "operation": "training",
            "message": str(exc)+" Retry when that training finishes.",
            "retryable": True,
        }) from exc
    background_tasks.add_task(train_background,eid,project_id,config)
    return {"id":eid,"status":"queued"}


@app.get("/api/experiments/{experiment_id}")
def get_experiment(experiment_id:str):
    e=experiment_or_404(experiment_id)
    current_version=quality.current_version(e["project_id"])
    return {"dataset_version":e["config"].get("quality_version",0),"current_version":current_version,"is_stale":e["config"].get("quality_version",0)!=current_version,"id":e["id"],"project_id":e["project_id"],"status":e["status"],"config":e["config"],
            "results":e["results"],"error":e["error"],"selected_model":e["selected_model"],"final_results":e["final_results"],
            "progress":e["progress"],"control":e["control"]}


@app.post("/api/experiments/{experiment_id}/cancel")
def cancel_training(experiment_id:str, request:Request):
    _local_request(request)
    experiment_or_404(experiment_id)
    state=storage.request_training_cancel(experiment_id)
    if state is None:
        raise HTTPException(status_code=404,detail="Experiment not found")
    # A running request is NOT yet cancelled; it must reach a worker checkpoint.
    return {
        "status":state,
        "message":(
            "Queued experiment cancelled before execution." if state=="cancelled"
            else "Cancellation requested. A running sklearn CV/fit cannot be forcibly stopped; "
                 "the worker will stop at its next safe checkpoint."
            if state=="cancellation_requested"
            else "This experiment already finished and was not modified."
        ),
    }


@app.post("/api/experiments/{experiment_id}/select")
def choose_model(experiment_id:str,body:SelectionRequest):
    e=experiment_or_404(experiment_id)
    if e["status"]!="completed": raise HTTPException(status_code=409,detail="Experiment not ready")
    if e["config"].get("quality_version",0)!=quality.current_version(e["project_id"]):
        raise HTTPException(status_code=409,detail="Dataset changed since training. Start a new experiment on the current version.")
    if e["selected_model"]:
        if e["selected_model"]==body.model_key:
            return {"selected_model":e["selected_model"],"final_results":e["final_results"]}
        raise HTTPException(status_code=409,detail="This experiment already has a final selected model. Create a new experiment to compare final outcomes.")
    ready={m["key"] for m in e["results"]["models"] if m["status"]=="ready"}
    if body.model_key not in ready: raise HTTPException(status_code=422,detail="Select a successfully trained model")
    base=storage.HOME/"models"/experiment_id
    model=joblib.load(base/f"{body.model_key}.joblib")
    x_test,y_test=joblib.load(base/"test_set.joblib")
    predictions=model.predict(x_test)
    prob=None
    if e["results"]["task"]=="classification" and hasattr(model,"predict_proba"):
        if len(model.named_steps["model"].classes_)==2:
            prob=model.predict_proba(x_test)[:,1]
    metrics=engine.model_report(e["results"]["task"],y_test,predictions,prob)
    metrics["sample_count"]=len(y_test)
    metrics["target"]=e["config"]["target"]
    metrics["evaluation_rows"]=[{"actual":engine.native(a),"predicted":engine.native(b)} for a,b in list(zip(y_test,predictions))[:120]]
    metrics["baseline_cv"]=e["results"]["baseline_cv"]
    metrics["cv_score"]=next((m.get("cv_metric") for m in e["results"]["models"] if m["key"]==body.model_key),None)
    # Frozen training-only majority class / median. Final test is consulted
    # only *after* the candidate has been selected via development CV.
    if "baseline_reference" in e["results"]:
        baseline_test=engine.heldout_baseline_metric(e["results"]["task"],y_test,e["results"]["baseline_reference"])
        metric_key="f1_macro" if e["results"]["task"]=="classification" else "mae"
        metrics["baseline_test_metric"]=baseline_test
        metrics["baseline_test_label"]="Macro F1" if e["results"]["task"]=="classification" else "MAE"
        metrics["beats_heldout_baseline"]=bool(
            metrics[metric_key]>baseline_test if e["results"]["task"]=="classification"
            else metrics[metric_key]<baseline_test
        )
        metrics["baseline_test_reference"]="Majority class from development training labels" if e["results"]["task"]=="classification" else "Median of development training labels"
    else:
        metrics["baseline_test_note"]="Legacy experiment: no training-derived baseline was persisted. Not comparable."
    metrics["reliability"]=engine.reliability_report(e["results"],metrics,body.model_key)
    # A bounded post-selection analysis of frozen holdout rows. Failure of an
    # optional diagnostic must not erase a valid selected-model evaluation.
    try:
        metrics["feature_sensitivity"]=engine.bounded_feature_sensitivity(
            model,x_test,y_test,e["results"]["task"])
    except Exception:
        # Optional diagnostic failure is logged locally and must not discard a
        # successful one-time held-out evaluation or reveal private row values.
        logging.getLogger(__name__).exception("Optional feature sensitivity calculation failed")
        metrics["feature_sensitivity"]={
            "status":"unavailable",
            "reason":"Bounded sensitivity could not be calculated for this trained model."
        }
    if not storage.select_model(experiment_id,body.model_key,metrics):
        raise HTTPException(status_code=409,detail="Model was already selected")
    return {"selected_model":body.model_key,"final_results":metrics}


@app.post("/api/experiments/{experiment_id}/predict")
def predict(experiment_id:str,body:PredictRequest):
    e=experiment_or_404(experiment_id)
    if not e["selected_model"]: raise HTTPException(status_code=409,detail="Select and evaluate a model first")
    if e["config"].get("quality_version",0)!=quality.current_version(e["project_id"]):
        raise HTTPException(status_code=409,detail="This model was trained on an older dataset version. Retrain before new predictions.")
    artifact=storage.HOME/"models"/experiment_id/f"{e['selected_model']}.joblib"
    if not artifact.is_file(): raise HTTPException(status_code=500,detail="Selected model artifact not found")
    pipe=joblib.load(artifact)
    try:
        result=engine.predict_one(pipe,e["results"]["input_schema"],body.values)
        result["target"]=e["config"]["target"]
        result["task"]=e["config"]["task"]
        result["dataset_version"]=e["config"].get("quality_version",0)
        result["experimental_only"]=True
        result["warning"]="Model predictions are estimates, not guaranteed outcomes or professional advice."
        if e.get("final_results") and e["final_results"].get("reliability",{}).get("level") == "warning":
            result["warning"]="CAUTION: This model failed reliability checks. Do not use this prediction for real decisions. " + result["warning"]
        return result
    except ValueError as ex: raise HTTPException(status_code=422,detail=str(ex))


# v0.2B Increment 1. Independent versioned quality engine: existing ML routes
# still use the uploaded dataset until the approved integration increment.
def quality_response(call, *args, **kwargs):
    try:
        return call(*args, **kwargs)
    except quality.QualityError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/quality")
def get_quality(project_id: str):
    return quality_response(quality.snapshot, project_id)


@app.get("/api/projects/{project_id}/quality/investigate")
def investigate_quality_finding(project_id: str,issue_id: str = Query(min_length=1,max_length=128),
                                expected_version: int = Query(ge=0)):
    """Version-pinned read-only investigation with source-bound issue identity."""
    return quality_response(quality_investigations.inspect,project_id,issue_id,expected_version)


@app.get("/api/projects/{project_id}/quality/preview")
def get_quality_preview(project_id: str, issue_id: str | None = None,
                        offset: int = 0, limit: int = 20, expected_version: int | None = None):
    return quality_response(quality.preview, project_id, issue_id, offset, limit, expected_version)


@app.post("/api/projects/{project_id}/quality/export")
def export_cleaned_dataset(project_id: str, body: data_exports.ExportRequest):
    """Export a specific immutable version without changing the working dataset."""
    try:
        path, filename, count, version = data_exports.prepare(project_id, body)
    except quality.QualityError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    return FileResponse(
        path, filename=filename,
        media_type='text/csv' if body.format == 'csv' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'X-PilotODIN-Dataset-Version': str(version), 'X-PilotODIN-Exported-Rows': str(count),
                 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'},
        background=BackgroundTask(path.unlink, missing_ok=True))


@app.get("/api/projects/{project_id}/quality/history")
def get_quality_history(project_id: str):
    return quality_response(quality.history, project_id)


@app.post("/api/projects/{project_id}/quality/proposals")
def preview_quality_change(project_id:str, body: quality_approvals.ProposalRequest):
    return quality_response(quality_approvals.prepare, project_id, body)


@app.post("/api/projects/{project_id}/quality/commit")
def commit_quality_change(project_id:str, body: quality_approvals.ApprovalCommit):
    return quality_response(quality_approvals.commit, project_id, body)


@app.post("/api/projects/{project_id}/quality/autopilot")
def run_quality_autopilot(project_id: str, body: QualityVersionRequest):
    raise HTTPException(status_code=428,detail='First review /quality/proposals, then approve /quality/commit')


@app.post("/api/projects/{project_id}/quality/decisions")
def decide_quality(project_id: str, body: QualityDecisionRequest):
    if body.decision == 'reject':
        return quality_response(quality.decide, project_id, body.issue_id,
                                body.expected_version, body.decision)
    raise HTTPException(status_code=428,detail='Approval requires a reviewed, version-bound /quality/proposals receipt')


@app.post("/api/projects/{project_id}/quality/undo")
def undo_quality(project_id: str, body: QualityUndoRequest):
    raise HTTPException(status_code=428,detail='Undo requires a reviewed /quality/proposals receipt')


@app.post("/api/projects/{project_id}/quality/restore")
def restore_quality(project_id: str, body: QualityRestoreRequest):
    raise HTTPException(status_code=428,detail='Restore requires a reviewed /quality/proposals receipt')


# Integrated macro workspace: read-only analysis from the currently approved
# working version. Responses are intentionally bounded for browser safety.
@app.get("/api/projects/{project_id}/columns/overview")
def column_investigation_overview(project_id: str):
    """Describe each stored dtype and analytical role in the CURRENT approved version."""
    project_or_404(project_id)
    frame, version = quality.current_data(project_id)
    try:
        return column_intelligence.overview(frame, version)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/target-opportunities")
def target_opportunity_overview(
    project_id: str, request: Request, expected_version: int = Query(ge=0)
):
    """Read-only structural screening; never selects a target or trains models."""
    _local_request(request)
    project_or_404(project_id)
    frame, version = quality.current_data(project_id)
    if version != expected_version:
        raise HTTPException(
            status_code=409,
            detail="Working dataset version changed. Refresh target recommendations before selecting a target.",
        )
    try:
        return target_opportunities.recommend(
            frame, version, storage.target_contexts(project_id, version)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class TargetBusinessContextRequest(BaseModel):
    expected_version: int = Field(ge=0)
    target_column: str = Field(min_length=1, max_length=200)
    outcome_definition: str = Field(min_length=10, max_length=600)
    decision_action: str = Field(min_length=10, max_length=600)
    prediction_moment: str = Field(min_length=10, max_length=500)
    label_source: str = Field(min_length=10, max_length=500)


@app.post("/api/projects/{project_id}/target-business-context")
def save_target_business_context(
    project_id: str, request: Request, body: TargetBusinessContextRequest
):
    """Persist only explicitly submitted user descriptions, NOT verified facts."""
    _local_request(request)
    project_or_404(project_id)
    frame, version = quality.current_data(project_id)
    if version != body.expected_version:
        raise HTTPException(
            status_code=409,
            detail="Working dataset version changed. Review current columns before saving context.",
        )
    if body.target_column not in frame.columns:
        raise HTTPException(status_code=422,detail="Target column is not in the approved dataset version")
    fields = (
        body.outcome_definition, body.decision_action,
        body.prediction_moment, body.label_source,
    )
    if any(not value.strip() or len(value.strip()) < 10 for value in fields):
        raise HTTPException(status_code=422,detail="Each context description must contain at least 10 non-space characters")
    if not body.target_column.strip():
        raise HTTPException(status_code=422,detail="Target column cannot be blank")
    return storage.save_target_context(
        project_id, version, body.target_column, *(value.strip() for value in fields)
    )


@app.get("/api/projects/{project_id}/semantics")
def semantic_overview(
    project_id: str, request: Request, expected_version: int = Query(ge=0)
):
    """Read-only semantic hypotheses for a caller-pinned approved working version."""
    # CORS alone does not reject an external-origin API request. Reuse the
    # existing local-origin/host guard before reading project metadata.
    _local_request(request)
    project_or_404(project_id)
    frame, version = quality.current_data(project_id)
    if version != expected_version:
        raise HTTPException(
            status_code=409,
            detail="Working dataset changed. Refresh the data dictionary before reviewing semantics."
        )
    try:
        return semantic_profile.overview(frame, version)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/columns/detail")
def column_investigation_detail(
    project_id: str, name: str = Query(min_length=1, max_length=256),
    expected_version: int = Query(ge=0)
):
    """Bounded on-demand examination; never silently cross a quality-version change."""
    project_or_404(project_id)
    frame, version = quality.current_data(project_id)
    if version != expected_version:
        raise HTTPException(status_code=409, detail="Working dataset changed. Refresh Your data before inspecting a column.")
    try:
        return column_intelligence.detail(frame, version, name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/explore/overview")
def explore_overview(project_id: str):
    project_or_404(project_id)
    return analytics.describe(*quality.current_data(project_id))


@app.get("/api/projects/{project_id}/explore/chart")
def explore_chart(project_id: str, x: str, y: str | None = None,
                  kind: str = 'auto', aggregation: str = 'mean', bins: int = Query(16, ge=4, le=40)):
    project_or_404(project_id)
    try:
        df, version = quality.current_data(project_id)
        return analytics.chart(df,version,x,y,kind,aggregation,bins)
    except ValueError as e:
        raise HTTPException(status_code=422,detail=str(e)) from e


@app.get("/api/projects/{project_id}/explore/correlation")
def explore_correlation(project_id: str, method: str = "pearson"):
    project_or_404(project_id)
    try:
        df, version=quality.current_data(project_id)
        return analytics.correlation(df,version,method)
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc


class ExploreFilterClause(BaseModel):
    column: str = Field(min_length=1, max_length=256)
    op: str
    value: str | None = Field(default=None, max_length=256)
    min: float | None = None
    max: float | None = None


class ExploreWorkbenchRequest(BaseModel):
    expected_version: int = Field(ge=0)
    filters: list[ExploreFilterClause] = Field(default_factory=list, max_length=4)
    x: str = Field(min_length=1, max_length=256)
    y: str | None = Field(default=None, max_length=256)
    kind: str = "auto"
    aggregation: str = "mean"
    bins: int = Field(default=16, ge=4, le=40)
    correlation_method: str = "pearson"
    color_by: str | None = Field(default=None,max_length=256)


@app.get("/api/projects/{project_id}/explore/filter-options")
def explore_filter_options(project_id: str):
    project_or_404(project_id)
    frame, version = quality.current_data(project_id)
    return explore_filters.catalog(frame, version)


@app.post("/api/projects/{project_id}/explore/workbench")
def explore_workbench(project_id: str, body: ExploreWorkbenchRequest):
    """Calculate linked plots and counts on one immutable-version read snapshot."""
    project_or_404(project_id)
    frame, version = quality.current_data(project_id)
    if version != body.expected_version:
        raise HTTPException(status_code=409, detail="Working dataset version changed. Refresh Explore and review filters.")
    try:
        subset = explore_filters.apply(frame, [item.model_dump() for item in body.filters])
        summary = analytics.describe(subset, version)
        graph = None
        chart_message = ""
        if len(subset):
            try:
                graph = analytics.chart(subset, version, body.x, body.y, body.kind,
                                        body.aggregation, body.bins, body.color_by)
            except ValueError as exc:
                # An otherwise valid selection may have no eligible numeric values.
                if "requires numeric" not in str(exc).lower() and not any(
                    text in str(exc).lower() for text in ("no numeric", "needs numeric",
                      "must be numeric", "numeric values", "two numeric columns",
                      "no chartable", "requires two", "empty")
                ):
                    raise
                chart_message = str(exc)
        else:
            chart_message = "No rows match these filters. Adjust or clear them."
        matrix = analytics.correlation(subset, version, body.correlation_method)
        return {"version": version, "total_rows": int(len(frame)),
                "filtered_rows": int(len(subset)), "filter_count": len(body.filters),
                "overview": summary, "chart": graph, "chart_message": chart_message,
                "correlation": matrix,
                "note": "All displayed results use the same approved dataset version and active filters."}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc



class ExploreInspectSelection(BaseModel):
    kind: str
    label: str | None = Field(default=None, max_length=2048)
    bin_index: int | None = Field(default=None, ge=0)
    row_ref: int | None = Field(default=None, ge=0)
    value: float | None = Field(default=None, allow_inf_nan=False)


class ExploreInspectRequest(ExploreWorkbenchRequest):
    selection: ExploreInspectSelection
    offset: int = Field(default=0, ge=0, le=1_000_000)
    limit: int = Field(default=12, ge=1, le=25)


@app.post("/api/projects/{project_id}/explore/inspect")
def explore_inspect(project_id: str, body: ExploreInspectRequest):
    """Inspect only a visible chart selection under the same filters and version."""
    project_or_404(project_id)
    frame, version = quality.current_data(project_id)
    if version != body.expected_version:
        raise HTTPException(status_code=409, detail="Working dataset changed. Refresh Explore before inspecting records.")
    try:
        subset = explore_filters.apply(frame, [item.model_dump() for item in body.filters])
        response = explore_inspector.inspect(
            subset, version, x=body.x, y=body.y, kind=body.kind,
            aggregation=body.aggregation, bins=body.bins,
            selection=body.selection.model_dump(exclude_none=True),
            offset=body.offset, limit=body.limit
        )
        return {**response, "total_filtered_rows": int(len(subset))}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class SaveExploreAnalysisRequest(ExploreWorkbenchRequest):
    title: str = Field(min_length=4, max_length=120)


def _saved_analysis_call(fn):
    try:
        return fn()
    except saved_analyses.SavedAnalysisError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/explore/saved")
def list_saved_explore_analyses(project_id: str):
    project_or_404(project_id)
    return _saved_analysis_call(lambda: saved_analyses.listing(project_id))


@app.get("/api/projects/{project_id}/explore/saved/{snapshot_id}")
def read_saved_explore_analysis(project_id: str, snapshot_id: str):
    project_or_404(project_id)
    return _saved_analysis_call(lambda: saved_analyses.load(project_id, snapshot_id))


@app.post("/api/projects/{project_id}/explore/saved", status_code=201)
def save_explore_analysis(project_id: str, body: SaveExploreAnalysisRequest):
    project_or_404(project_id)
    return _saved_analysis_call(lambda: saved_analyses.save(
        project_id, title=body.title, expected_version=body.expected_version,
        x=body.x, y=body.y, kind=body.kind, aggregation=body.aggregation,
        bins=body.bins, correlation_method=body.correlation_method,
        color_by=body.color_by, filters=[item.model_dump(exclude_none=True) for item in body.filters]
    ))


@app.get("/api/projects/{project_id}/explore/insights")
def explore_insights(project_id: str):
    project_or_404(project_id)
    return analytics.insights(*quality.current_data(project_id))


@app.get("/api/projects/{project_id}/features")
def feature_recommendations(project_id: str, target: str):
    project_or_404(project_id)
    try:
        df,version=quality.current_data(project_id)
        return analytics.recommend_features(df,target,version)
    except ValueError as e:
        raise HTTPException(status_code=422,detail=str(e)) from e


class AskRequest(BaseModel):
    question: str = Field(min_length=1,max_length=350)


@app.post("/api/projects/{project_id}/assistant")
def ask_assistant(project_id: str, body: AskRequest):
    project_or_404(project_id)
    try:
        df,version=quality.current_data(project_id)
        return analytics.answer(df,version,body.question)
    except ValueError as e:
        raise HTTPException(status_code=422,detail=str(e)) from e


# v0.4: opt-in multi-provider intelligence. Keys never returned by API.
# These routes are exclusively for the localhost user interface.
class AISettingsRequest(BaseModel):
    cloud_enabled: bool = False
    share_aggregates: bool = False
    auto_insights: bool = False
    provider_order: list[str] = Field(default_factory=lambda: list(ai_provider.PROVIDERS))
    timeout_seconds: int = Field(default=20, ge=3, le=45)
    preferred_provider: str = 'auto'
    workspace_preferences: dict[str,str] = Field(default_factory=dict)
    intelligence_mode: str = 'hybrid'
    local_model: str = 'qwen3:1.7b'
    local_model_enabled: bool = True
    local_timeout_seconds: int = Field(default=60,ge=5,le=180)

class AIKeyRequest(BaseModel):
    provider: str
    key: str | None = Field(default=None, max_length=512)
    remove: bool = False

class AIInsightRequest(BaseModel):
    context: str = 'assistant'
    question: str = Field(default='', max_length=900)
    target: str | None = Field(default=None, max_length=200)
    experiment_id: str | None = Field(default=None, max_length=128)
    prediction: dict | None = None
    deep: bool = False
    selected_provider: str | None = None
    continuation_text: str | None = Field(default=None, max_length=16000)


def _local_request(request:Request):
    # CORS is not an authorization boundary. Forbid cross-site browsers from
    # writing keys or triggering paid/external calls on localhost.
    origin=request.headers.get('origin','')
    allowed = (_allowed_desktop_origin(origin) if os.environ.get('PILOTODIN_DESKTOP_SESSION')
               else bool(re.fullmatch(r'http://(?:localhost|127\.0\.0\.1):517[3-9]',origin)))
    if origin and not allowed:
        raise HTTPException(status_code=403,detail='AI controls are limited to the local PilotODIN interface')
    host=request.url.hostname
    if host not in ('localhost','127.0.0.1','testserver'):
        raise HTTPException(status_code=403,detail='Local access only')


class ResourcePolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["adaptive", "low_memory", "performance"]


@app.get('/api/resource/status')
def resource_status(request: Request):
    # Protect preference metadata with the same local-only trust boundary
    # as the existing settings controls, including session-auth desktop.
    _local_request(request)
    return resource_policy.status()


@app.get('/api/resource/preflight')
def resource_preflight(request: Request,
                       operation: Literal["training", "local_inference"] = "local_inference"):
    _local_request(request)
    # Read-only status. The decision is re-checked server-side before new
    # training/model generation; a client report is never authorization.
    return resource_policy.admit_new_work(operation)


@app.put('/api/resource/policy')
def update_resource_policy(body: ResourcePolicyRequest, request: Request):
    _local_request(request)
    try:
        resource_policy.save_policy(body.mode)
    except OSError as exc:
        logging.exception("Could not persist local resource policy")
        raise HTTPException(status_code=500,
                            detail="Could not save resource settings. Existing settings were not replaced.") from exc
    return resource_policy.status()


@app.get('/api/ai/settings')
def ai_settings(request:Request):
    _local_request(request)
    return ai_provider.config_status()


@app.put('/api/ai/settings')
def save_ai_settings(body:AISettingsRequest,request:Request):
    _local_request(request)
    try:return ai_provider.update_settings(**body.model_dump())
    except ValueError as e:raise HTTPException(status_code=422,detail=str(e)) from e


@app.put('/api/ai/key')
def save_ai_key(body:AIKeyRequest,request:Request):
    _local_request(request)
    try:return ai_provider.set_key(body.provider,body.key,body.remove)
    except ValueError as e:raise HTTPException(status_code=422,detail=str(e)) from e
    except OSError as e:raise HTTPException(status_code=500,detail='Secure credential storage unavailable') from e


@app.post('/api/projects/{project_id}/ai/insight')
def ai_insight(project_id:str,body:AIInsightRequest,request:Request):
    _local_request(request)
    project_or_404(project_id)
    if body.context not in ai_context.TASKS:
        raise HTTPException(status_code=422,detail='Unsupported workspace context')
    try:
        df,version=quality.current_data(project_id)
        question=body.question.strip() or ai_context.TASKS[body.context]
        context=ai_context.build(project_id,body.context,question,body.target,body.experiment_id,body.prediction)
        local=analytics.answer(df,version,question[:350])['answer'] if body.context=='assistant' else ai_context.local_advice(context,body.context)
        plan=None if body.continuation_text else analytics.plan_investigation(df,version,question,body.context)
        if plan:
            context['verified_investigation']=plan['safe_context']
            # This report is computed locally. Do not claim that a pattern proves MNAR.
            local=(f"Inspected {plan['local_report']['missing_rows']} missing values in {plan['column']}. "
                   f"Compared the available numeric and categorical groups; see the verified investigation below. "
                   "No treatment has been applied. Observed associations do not prove the missingness mechanism.")
        result=ai_provider.respond(context,body.context,question,local,body.deep,body.selected_provider,body.continuation_text)
        return {**result,'dataset_version':version,'privacy':'summary_only_no_rows',
                'scope':body.context,'investigation':plan['local_report'] if plan else None,
                'investigation_steps':plan['steps'] if plan else [],
                'limitations':'AI suggestions are advisory; verified local engines perform calculations and modifications.'}
    except (ValueError,quality.QualityError) as e:
        raise HTTPException(status_code=422,detail=str(e)) from e


@app.get('/api/ai/local/status')
def local_ai_status(request:Request):
    _local_request(request)
    return ai_provider.test_local_connection()


@app.post('/api/ai/verify-connected')
def verify_ai_providers(request:Request):
    """Bounded health check for opt-in configured providers, never dataset rows."""
    _local_request(request)
    return ai_provider.verify_connected()


@app.post('/api/ai/test/{provider}')
def test_ai_provider(provider:str,request:Request):
    _local_request(request)
    try:return ai_provider.test_connection(provider)
    except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc

@app.get('/api/projects/{project_id}/live-profile')
def live_profile(project_id:str):
    """Profile the CURRENT approved working version, not stale upload metadata."""
    p=project_or_404(project_id)
    df,version=quality.current_data(project_id)
    return {'version':version,'profile':engine.profile(df,p['filename'])}

# Persistent investigation objects are a v1 design spike, separate from the
# older, narrow /investigate helper. Endpoints below are read-only against data.
try:
    from . import investigations
except ImportError:
    import investigations

class NewCanvasInvestigationRequest(BaseModel):
    objective: str = Field(min_length=8, max_length=400)

class CanvasToolRunRequest(BaseModel):
    operation: str
    params: dict = Field(default_factory=dict)
    expected_version: int = Field(ge=0)

@app.get('/api/projects/{project_id}/investigations')
def list_canvas_investigations(project_id: str):
    project_or_404(project_id)
    return investigations.listing(project_id)

@app.post('/api/projects/{project_id}/investigations',status_code=201)
def create_canvas_investigation(project_id: str,body:NewCanvasInvestigationRequest):
    project_or_404(project_id)
    objective = body.objective.strip()
    if len(objective) < 8:
        raise HTTPException(status_code=422,detail='Provide a meaningful investigation objective')
    return investigations.create(project_id,objective)

@app.get('/api/investigations/{investigation_id}')
def get_canvas_investigation(investigation_id: str):
    result=investigations.load(investigation_id)
    if not result:raise HTTPException(status_code=404,detail='Investigation not found')
    return result

@app.post('/api/investigations/{investigation_id}/runs')
def run_canvas_tool(investigation_id: str,body:CanvasToolRunRequest):
    try:
        return investigations.run(investigation_id,body.operation,body.params,body.expected_version)
    except KeyError as e:
        raise HTTPException(status_code=404,detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=409,detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422,detail=str(e)) from e


# Build E: durable, bounded, local-model investigation controller. All tools
# execute through the existing read-only investigation engine.
try:
    from . import autonomy
except ImportError:
    import autonomy

class AutonomousStartRequest(BaseModel):
    max_steps: int = Field(default=5,ge=1,le=8)

@app.get('/api/investigations/{investigation_id}/autonomy')
def get_autonomous_run(investigation_id: str):
    if investigations.load(investigation_id) is None:
        raise HTTPException(status_code=404,detail='Investigation not found')
    return autonomy.for_investigation(investigation_id)

@app.post('/api/investigations/{investigation_id}/autonomy/start',status_code=202)
def start_autonomous_run(investigation_id: str,body:AutonomousStartRequest):
    try:return autonomy.start(investigation_id,max_steps=body.max_steps)
    except KeyError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    except PermissionError as exc:raise HTTPException(status_code=403,detail=str(exc)) from exc
    except RuntimeError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc
    except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc

@app.post('/api/investigations/{investigation_id}/autonomy/resume',status_code=202)
def resume_autonomous_run(investigation_id: str):
    try:return autonomy.resume(investigation_id)
    except KeyError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    except RuntimeError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc

@app.post('/api/investigations/{investigation_id}/autonomy/cancel')
def cancel_autonomous_run(investigation_id: str):
    try:return autonomy.cancel(investigation_id)
    except KeyError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc

class InvestigationRequest(BaseModel):
    operation: str
    column: str | None = None

@app.post('/api/projects/{project_id}/investigate')
def investigate_project(project_id:str,body:InvestigationRequest):
    project_or_404(project_id)
    try:
        df,version=quality.current_data(project_id)
        return analytics.investigate(df,version,body.operation,body.column)
    except ValueError as e:
        raise HTTPException(status_code=422,detail=str(e)) from e

@app.get('/api/projects/{project_id}/quality/missingness')
def quality_missingness(project_id:str,column:str):
    project_or_404(project_id)
    try:return analytics.missingness_diagnostics(*quality.current_data(project_id),column)
    except ValueError as e:raise HTTPException(status_code=422,detail=str(e)) from e


class ImputationRequest(QualityVersionRequest):
    issue_id: str = Field(min_length=1,max_length=128)
    column: str = Field(min_length=1,max_length=200)
    strategy: str = 'median'


@app.post('/api/projects/{project_id}/quality/impute')
def quality_impute(project_id:str,body:ImputationRequest,request:Request):
    _local_request(request)
    raise HTTPException(status_code=428,detail='Median imputation requires a reviewed /quality/proposals receipt')


@app.get('/api/projects/{project_id}/explore/recommended')
def recommended_exploration(project_id:str):
    project_or_404(project_id)
    return analytics.recommended_charts(*quality.current_data(project_id))


# Build E: durable evidence-backed report revision API.
class ReportSaveRequest(BaseModel):
    title: str = Field(min_length=5,max_length=180)
    narrative: str = Field(default='',max_length=6000)
    evidence_ids: list[str] = Field(min_length=1,max_length=15)


def _report_call(operation):
    try:return operation()
    except reports.ReportError as exc:
        raise HTTPException(status_code=exc.status,detail=str(exc)) from exc

@app.get('/api/projects/{project_id}/report-evidence')
def list_available_report_evidence(project_id: str):
    return _report_call(lambda: reports.evidence_options(project_id))


@app.post('/api/projects/{project_id}/report-quality',status_code=201)
def capture_quality_report_evidence(project_id: str,body: QualityVersionRequest):
    """Explicit, read-only capture; does not approve or apply any correction."""
    return _report_call(lambda: reports.capture_quality(project_id,body.expected_version))

@app.get('/api/projects/{project_id}/reports')
def list_saved_reports(project_id: str):
    return _report_call(lambda: reports.listing(project_id))

@app.post('/api/projects/{project_id}/reports',status_code=201)
def create_saved_report(project_id: str,body:ReportSaveRequest):
    return _report_call(lambda: reports.save(project_id,body.title,body.narrative,body.evidence_ids))

@app.get('/api/reports/{report_id}')
def read_saved_report(report_id: str,revision: int | None = Query(default=None,ge=1)):
    return _report_call(lambda: reports.load(report_id,revision))

@app.post('/api/reports/{report_id}/revisions',status_code=201)
def revise_saved_report(report_id: str,body:ReportSaveRequest):
    current=_report_call(lambda: reports.load(report_id))
    return _report_call(lambda: reports.save(current['project_id'],body.title,body.narrative,body.evidence_ids,report_id))

@app.get('/api/reports/{report_id}/export/{format}')
def export_saved_report(report_id: str,format: str,revision: int | None = Query(default=None,ge=1)):
    if format not in ('html','pdf'):
        raise HTTPException(status_code=404,detail='Choose html or pdf')
    current=_report_call(lambda: reports.load(report_id,revision))
    content=reports.render_html(current) if format=='html' else reports.render_pdf(current)
    mime='text/html; charset=utf-8' if format=='html' else 'application/pdf'
    fname=f"pilotodin_report_{report_id[:12]}_rev{current['revision']}.{format}"
    return Response(content=content,media_type=mime,headers={
        'Content-Disposition':f'attachment; filename="{fname}"',
        'X-Content-Type-Options':'nosniff',
        'Cache-Control':'no-store'
    })
