"""B2 verified model artifact staging, publication and private-snapshot loading."""
from __future__ import annotations

from contextlib import closing, ExitStack
import errno
import hashlib
import logging
import os
import stat
import json
import shutil
import tempfile

import joblib

try:
    from . import artifact_publication, model_publication as ledger, resource_policy, storage
    from .workspace_boundary import pinned_existing_directory
except ImportError:
    import artifact_publication
    import model_publication as ledger
    import resource_policy
    import storage
    from workspace_boundary import pinned_existing_directory

Error = artifact_publication.PublicationError
_CHUNK = 1024 * 1024


def _directory(path, expected=None):
    storage.check_write_path(path, directory=True, expected=expected)
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or not info.st_ino
            or getattr(info, "st_file_attributes", 0) & 0x400
            or (expected is not None and not os.path.samestat(expected, info))):
        raise Error("Unsafe model directory identity")
    return info


def _file(path, expected=None):
    storage.check_write_path(path, expected=expected)
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not info.st_ino
            or getattr(info, "st_file_attributes", 0) & 0x400
            or (expected is not None and not os.path.samestat(expected, info))):
        raise Error("Unsafe model file identity")
    return info


def _same(a,b):
    return (os.path.samestat(a,b) and a.st_size==b.st_size
            and a.st_mtime_ns==b.st_mtime_ns and a.st_ctime_ns==b.st_ctime_ns)


def _sync_directory(path, verify):
    verify()
    if os.name == "posix":
        fd=os.open(path, os.O_RDONLY | getattr(os,"O_DIRECTORY",0) | getattr(os,"O_NOFOLLOW",0))
        try:
            if not os.path.samestat(os.fstat(fd),_directory(path)):
                raise Error("Model directory identity changed")
            os.fsync(fd)
        finally:
            os.close(fd)
    verify()


class ArtifactBudgetExceeded(Error):
    """The serialized payload exceeds a configured capacity limit."""


class _BoundedWriter:
    """A sequential file-like sink, bounding serialized bytes during dump."""
    def __init__(self, file, limit, *, aggregate_limited=False):
        self.file=file
        self.limit=limit
        self.aggregate_limited=aggregate_limited
        self.count=0

    def write(self, data):
        if self.count+len(data)>self.limit:
            if self.aggregate_limited:
                raise ArtifactBudgetExceeded("Experiment artifact byte budget exceeded. Choose fewer model candidates or a reviewed smaller dataset and retry; existing data is unchanged.")
            raise ArtifactBudgetExceeded("Model artifact byte budget exceeded. Choose a less costly model or a reviewed smaller dataset and retry; existing data is unchanged.")
        written=self.file.write(data)
        if written!=len(data):
            raise OSError("Incomplete model artifact write")
        self.count+=written
        return written

    def tell(self):
        return self.count

    def flush(self):
        self.file.flush()


def _exclusive(path, verify, owned):
    verify()
    storage.check_write_path(path, absent=True)
    stream=path.open("xb")
    try:
        owned[path]=os.fstat(stream.fileno())
    except BaseException:
        stream.close()
        raise
    return stream


def _stream_verified(path, expected, verify, *, output=None, manifest=None, limit=None, checkpoint=lambda:None):
    """Hash a bounded exact source handle, optionally copying the same bytes."""
    verify()
    before=_file(path,expected)
    cap=ledger.MAX_FILE_BYTES if limit is None else min(limit,ledger.MAX_FILE_BYTES)
    if not 1<=before.st_size<=cap or (manifest is not None and before.st_size!=manifest["size"]):
        raise Error("Model artifact size mismatch or budget exceeded")
    digest=hashlib.sha256()
    count=0
    flags=os.O_RDONLY | getattr(os,"O_BINARY",0) | getattr(os,"O_NOFOLLOW",0)
    with os.fdopen(os.open(path,flags),"rb") as source:
        if not _same(before,os.fstat(source.fileno())):
            raise Error("Model artifact identity changed")
        while True:
            checkpoint()
            chunk=source.read(_CHUNK)
            if not chunk:
                break
            count+=len(chunk)
            if count>cap or count>before.st_size:
                raise Error("Model artifact size changed")
            digest.update(chunk)
            if output is not None and output.write(chunk)!=len(chunk):
                raise OSError("Incomplete model artifact copy")
        if not _same(before,os.fstat(source.fileno())):
            raise Error("Model artifact changed during verification")
    after=_file(path,before)
    verify()
    info={"size":count,"sha256":digest.hexdigest()}
    if not _same(before,after) or count!=before.st_size or (manifest is not None and info!=manifest):
        raise Error("Model artifact digest or identity mismatch")
    return info,after


def _inventory(path, expected, verify):
    verify()
    # Stop at the first unexpected name; never traverse a foreign tree.
    with os.scandir(path) as entries:
        names=set()
        for entry in entries:
            if entry.name not in expected or entry.name in names:
                raise Error("Unexpected model directory entry")
            names.add(entry.name)
    if names!=set(expected):
        raise Error("Missing model directory entry")
    verify()


def _create_directory(path, verify, directories):
    verify()
    storage.check_write_path(path,directory=True,absent=True)
    path.mkdir(exist_ok=False)
    info=_directory(path)
    directories[path]=info
    verify()
    return info


def _cleanup(directory, identity, owned, verify_parent):
    """Only remove known invocation-owned entries, never recursive deletion."""
    verify_parent()
    _directory(directory,identity)
    expected={p.name for p in owned if p.parent==directory}
    _inventory(directory,expected,lambda: _directory(directory,identity))
    for name in sorted(expected):
        path=directory/name
        verify_parent()
        _directory(directory,identity)
        _file(path,owned[path])
        storage.guarded_unlink(path,expected=owned[path])
    verify_parent()
    _directory(directory,identity)
    directory.rmdir()
    verify_parent()


def _settle(receipt, results, error):
    """Fresh transactional status check. Never delete on an ambiguous outcome."""
    with storage.connect() as con:
        artifact_publication.begin_durable(con)
        current=ledger.read(con,receipt.experiment_id)
        if current is None or (current.project_id,current.config_sha256,current.source_sha256,current.runtime_json)!=(
                receipt.project_id,receipt.config_sha256,receipt.source_sha256,receipt.runtime_json):
            raise Error("Model publication outcome unconfirmed")
        row=con.execute("SELECT status,project_id,config,results FROM experiments WHERE id=?",
                        (receipt.experiment_id,)).fetchone()
        if row is None or row["project_id"]!=receipt.project_id:
            raise Error("Model publication outcome unconfirmed")
        if current.state=="committed":
            import json
            if row["status"]!="completed" or json.loads(row["results"])!=results:
                raise Error("Model completion outcome unconfirmed")
            current.verify_binding(row["project_id"],json.loads(row["config"]),receipt.source_sha256,results)
            return current
        if row["status"]=="completed" or current.state not in ("intent","staged","publishing"):
            raise Error("Model publication outcome unconfirmed")
        reason=("cancelled" if isinstance(error,storage.TrainingInterrupted) else
                "storage_unavailable" if isinstance(error,(OSError,ArtifactBudgetExceeded)) else "integrity_mismatch")
        ledger.advance(con,current,"interrupted",reason=reason)
        return None


def publish(eid, config, source_sha256, results, pipes, holdout):
    """Persist intent, write exclusive stage, verify, copy, commit completion."""
    expected=ledger.expected_files(config,results)
    if {key+".joblib" for key in pipes}|{"test_set.joblib"}!=expected:
        raise Error("Fitted model inventory disagrees with ready results")
    checkpoint=lambda:storage.check_training_interruption(eid)
    checkpoint()
    receipt=storage.begin_model_publication(eid,config=config,source_sha256=source_sha256)
    parent=storage.HOME/"models"
    final=parent/receipt.experiment_id
    stage=parent/(receipt.experiment_id+".publishing")
    owned={}
    directories={}
    with pinned_existing_directory(parent) as verify_parent:
        try:
            with ExitStack() as stack:
                # Never create stage for a pre-existing final directory.
                storage.check_write_path(final,directory=True,absent=True)
                try:
                    final.lstat()
                except FileNotFoundError:
                    pass
                else:
                    raise FileExistsError("Model publication destination already exists")
                stage_id=_create_directory(stage,verify_parent,directories)
                stage_pin=stack.enter_context(pinned_existing_directory(stage,expected=stage_id))
                def verify_stage():
                    verify_parent()
                    stage_pin()
                    _directory(stage,stage_id)
                files={}
                remaining=ledger.MAX_TOTAL_BYTES
                objects={key+".joblib":value for key,value in pipes.items()}
                objects["test_set.joblib"]=holdout
                for name in sorted(expected):
                    checkpoint()
                    destination=stage/name
                    with _exclusive(destination,verify_stage,owned) as output:
                        bounded=_BoundedWriter(output,min(ledger.MAX_FILE_BYTES,remaining),
                                               aggregate_limited=remaining<ledger.MAX_FILE_BYTES)
                        joblib.dump(objects[name],bounded)
                        output.flush()
                        os.fsync(output.fileno())
                    checkpoint()
                    info,_=_stream_verified(destination,owned[destination],verify_stage,
                                            limit=remaining,checkpoint=checkpoint)
                    files[name]=info
                    remaining-=info["size"]
                _inventory(stage,expected,verify_stage)
                _sync_directory(stage,verify_stage)
                receipt=storage.stage_model_publication(receipt,results,files)
                receipt=storage.advance_model_publication(receipt,"publishing")
                final_id=_create_directory(final,verify_parent,directories)
                final_pin=stack.enter_context(pinned_existing_directory(final,expected=final_id))
                def verify_final_directory():
                    verify_parent()
                    final_pin()
                    _directory(final,final_id)
                verified={}
                for name in sorted(expected):
                    checkpoint()
                    destination=final/name
                    with _exclusive(destination,verify_final_directory,owned) as output:
                        _stream_verified(stage/name,owned[stage/name],verify_stage,output=output,
                                         manifest=files[name],checkpoint=checkpoint)
                        output.flush()
                        os.fsync(output.fileno())
                    _,verified[name]=_stream_verified(destination,owned[destination],verify_final_directory,
                                                       manifest=files[name],checkpoint=checkpoint)
                _sync_directory(final,verify_final_directory)
                _sync_directory(parent,verify_parent)
                def verify_final():
                    _inventory(final,expected,verify_final_directory)
                    for name in expected:
                        if not _same(verified[name],_file(final/name,verified[name])):
                            raise Error("Verified final model artifact changed")
                checkpoint()
                receipt=storage.commit_model_publication(receipt,results,verify_final=verify_final)
        except Exception as error:
            # Release both directory pins before attempting bounded cleanup.
            # A committed or uncertain final directory is never removed.
            try:
                committed=_settle(receipt,results,error)
            except Exception as exc:
                raise Error("Model publication outcome unconfirmed; retained artifact bytes") from exc
            if committed is not None:
                # Confirm exact files again after a lost acknowledgement.
                with pinned_existing_directory(final,expected=directories.get(final)) as verify:
                    _inventory(final,committed.files,verify)
                    for name,info in committed.files.items():
                        if final/name not in owned:
                            raise Error("Committed model identity unconfirmed")
                        _stream_verified(final/name,owned[final/name],verify,manifest=info)
                receipt=committed
            else:
                try:
                    with storage.connect() as con:
                        artifact_publication.begin_durable(con)
                        current=ledger.read(con,eid)
                        row=con.execute("SELECT status FROM experiments WHERE id=?",(eid,)).fetchone()
                        if current is None or current.state!="interrupted" or row is None or row[0]=="completed":
                            raise Error("Model cleanup outcome unconfirmed")
                        for path in (final,stage):
                            if path in directories:
                                _cleanup(path,directories[path],owned,verify_parent)
                except Exception:
                    logging.warning("Retained unverifiable interrupted model files")
                raise
        # Commit is known; stage cleanup is best-effort and cannot undo it.
        try:
            with storage.connect() as con:
                artifact_publication.begin_durable(con)
                if ledger.read(con,eid)!=receipt or receipt.state!="committed":
                    raise Error("Model receipt changed before cleanup")
                if stage in directories:
                    _cleanup(stage,directories[stage],owned,verify_parent)
        except Exception:
            logging.warning("Model staging cleanup deferred")
        return receipt


class LoadRefused(Error):
    """Controlled refusal; no unverified artifact is passed to Joblib."""


class LoadDeferred(LoadRefused):
    """Insufficient resources for a verified snapshot."""


def _load_receipt(experiment, model_key, *, holdout):
    eid=experiment["id"]
    with storage.connect() as con:
        con.execute("BEGIN")
        receipt=ledger.read(con,eid)
        if receipt is None:
            raise LoadRefused("Legacy model has no verified manifest. Historical results are preserved; retrain to use this model.")
        row=con.execute("SELECT project_id,status,config,results,selected_model FROM experiments WHERE id=?",(eid,)).fetchone()
        if row is None or row["status"]!="completed" or receipt.state!="committed":
            raise LoadRefused("Model publication is not committed. Retrain before using artifacts.")
        config=json.loads(row["config"])
        results=json.loads(row["results"])
        if (row["project_id"]!=experiment["project_id"] or config!=experiment["config"]
                or results!=experiment["results"] or row["selected_model"]!=experiment["selected_model"]):
            raise LoadRefused("Experiment changed. Refresh before using artifacts.")
        state=con.execute("SELECT original_sha256,current_version FROM quality_state WHERE project_id=?",
                          (receipt.project_id,)).fetchone()
        if state is None or state["current_version"]!=receipt.quality_version:
            raise LoadRefused("Dataset changed since training. Retrain on the current version.")
        try:
            from .project_lifecycle import require_active_for_write
        except ImportError:
            from project_lifecycle import require_active_for_write
        require_active_for_write(con,receipt.project_id)
        receipt.verify_binding(row["project_id"],config,state["original_sha256"],results,
                               runtime=ledger.runtime_versions())
        names=[model_key+".joblib"]
        if model_key not in {m["key"] for m in results["models"] if m["status"]=="ready"}:
            raise LoadRefused("Requested model is not a ready candidate.")
        if holdout:
            names.append("test_set.joblib")
        elif row["selected_model"]!=model_key:
            raise LoadRefused("Requested model is not the selected model.")
        if any(name not in receipt.files for name in names):
            raise LoadRefused("Requested artifact is absent from the manifest.")
        return receipt,names


def load_verified(experiment, model_key, *, holdout=False):
    """Verify all requested snapshots before invoking any deserializer.

    TemporaryFile owns the exclusive scratch handle and deletes it on close.
    The exact copied, hashed stream is rewound and supplied to Joblib, never
    its original filename. This protects against byte substitution, not an
    attacker controlling the database and the local process together.
    """
    try:
        receipt,names=_load_receipt(experiment,model_key,holdout=holdout)
        admission=resource_policy.admit_new_work("model_load")
        if admission["decision"]=="defer":
            raise LoadDeferred("Insufficient available memory for model loading. Retry when more memory is available.")
        total=sum(receipt.files[name]["size"] for name in names)
        scratch=storage.HOME/"backend-temp"
        directory=storage.HOME/"models"/receipt.experiment_id
        storage.check_scratch()
        with ExitStack() as stack:
            verify_home=stack.enter_context(pinned_existing_directory(storage.HOME))
            verify_home()
            storage.check_write_path(scratch,directory=True,missing=True)
            scratch.mkdir(exist_ok=True)
            storage.check_write_path(scratch,directory=True)
            verify_scratch=stack.enter_context(pinned_existing_directory(scratch))
            verify_models=stack.enter_context(pinned_existing_directory(directory))
            def verify_source():
                verify_models()
                _directory(directory)
            def verify_temp():
                verify_home()
                verify_scratch()
                storage.check_scratch()
                storage.check_write_path(scratch,directory=True)
            verify_temp()
            if shutil.disk_usage(scratch).free<total+8*1024*1024:
                raise LoadDeferred("Insufficient scratch disk space for verified model loading.")
            _inventory(directory,receipt.files,verify_source)
            snapshots=[]
            for name in names:
                verify_temp()
                stream=stack.enter_context(tempfile.TemporaryFile(mode="w+b",dir=scratch))
                _stream_verified(directory/name,None,verify_source,output=stream,
                                 manifest=receipt.files[name])
                stream.flush()
                stream.seek(0)
                if os.fstat(stream.fileno()).st_size!=receipt.files[name]["size"]:
                    raise LoadRefused("Verified scratch snapshot size mismatch.")
                # Check the actual snapshot bytes too, rather than relying on
                # successful buffered writes as a checksum proof.
                digest=hashlib.sha256()
                remaining=receipt.files[name]["size"]
                while remaining:
                    data=stream.read(min(_CHUNK,remaining))
                    if not data:
                        raise LoadRefused("Incomplete verified scratch snapshot.")
                    digest.update(data)
                    remaining-=len(data)
                if stream.read(1) or digest.hexdigest()!=receipt.files[name]["sha256"]:
                    raise LoadRefused("Verified scratch snapshot digest mismatch.")
                stream.seek(0)
                snapshots.append(stream)
            verify_temp()
            _inventory(directory,receipt.files,verify_source)
            current,current_names=_load_receipt(experiment,model_key,holdout=holdout)
            if current!=receipt or current_names!=names:
                raise LoadRefused("Model receipt changed during verification.")
            # All requested files have passed validation before first load.
            try:
                objects=[joblib.load(stream,mmap_mode=None) for stream in snapshots]
            except Exception as exc:
                raise LoadRefused("Verified model could not be decoded. Retrain before using artifacts.") from exc
            return tuple(objects) if holdout else objects[0]
    except LoadRefused:
        raise
    except (Error,OSError,storage.WorkspaceBoundaryError,ValueError,KeyError,TypeError) as exc:
        # Free space can change after the admission check or during a copy.
        # Do not tell the user to retrain a valid model for a resource failure.
        if isinstance(exc, OSError) and (exc.errno in {errno.ENOSPC, getattr(errno, "EDQUOT", errno.ENOSPC)}
                                        or getattr(exc, "winerror", None) in (39, 112)):
            raise LoadDeferred("Insufficient scratch disk space for verified model loading. Free space and retry.") from exc
        raise LoadRefused("Model integrity or runtime compatibility could not be confirmed. Historical results are preserved; retrain before use.") from exc
