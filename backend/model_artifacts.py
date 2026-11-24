"""B2 model artifact staging and publication. No model deserialization here."""
from __future__ import annotations

from contextlib import closing, ExitStack
import hashlib
import logging
import os
import stat

import joblib

try:
    from . import artifact_publication, model_publication as ledger, storage
    from .workspace_boundary import pinned_existing_directory
except ImportError:
    import artifact_publication
    import model_publication as ledger
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


class _BoundedWriter:
    """A sequential file-like sink, bounding serialized bytes during dump."""
    def __init__(self, file, limit):
        self.file=file
        self.limit=limit
        self.count=0

    def write(self, data):
        if self.count+len(data)>self.limit:
            raise Error("Model artifact byte budget exceeded")
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
                "storage_unavailable" if isinstance(error,OSError) else "integrity_mismatch")
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
                        bounded=_BoundedWriter(output,min(ledger.MAX_FILE_BYTES,remaining))
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
