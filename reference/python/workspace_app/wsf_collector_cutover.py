"""Offline cutover and interrupted-cutover rollback, not a production provisioner.

Caller must prove Workspace, collector, deployment and daily backup quiescent.
Only an independent approved publication plus selected-device review may invoke
these helpers on live state. No credential/grant creation here.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from .wsf_manual_context import ManualContextError, _identity, _digest, _json
from .wsf_manual_policy import _private_file
from .wsf_inbox_registry_migration import atomic, syncdir, write_archive
from .wsf_local_roadmap_collector import rehearse_migration, CollectorInbox
from .wsf_collector_runtime import CONFIG, RECEIPT, JOURNAL, validate_documents

def _read_primary(store):
    return store._encode(store._load())

def _read_snapshot(store,path):
    fd=store._open(path,0)
    with open(fd,"rb") as stream:
        return stream.read(2*1024*1024+1)

def _remove(path):
    if path.is_symlink():raise ManualContextError("unsafe cutover path")
    path.unlink(missing_ok=True);syncdir(path.parent)

def prepare(root,legacy,owner,backup,policy_document,publication):
    """Pure preparation except isolated temp files. Does not alter existing ledger."""
    root=Path(root);raw=legacy.export(owner)
    if backup.verified_snapshot(owner)!=raw:
        raise ManualContextError("migration requires current verified backup")
    with TemporaryDirectory(prefix="collector-preview-",dir=root) as tmp:
        new,old,candidate=rehearse_migration(legacy,owner,raw,Path(tmp)/"inbox")
        if old!=raw:raise ManualContextError("predecessor changed")
        config={**policy_document,"legacy_sha256":_digest(raw),
                "legacy_event_count":len(legacy.file._decode(raw))}
        if config["owner_scope"]!=_identity(owner) or config["publication"]!=publication:
            raise ManualContextError("cutover owner or publication mismatch")
        cfg=_json(config)
        receipt=_json({"schema":"arvectum.workspace.collector-activation/1",
                       "publication":publication,"policy_sha256":_digest(cfg)})
        validate_documents(cfg,receipt,publication)
        before=legacy.read(owner);after=new.read(owner)
        if before["items"]!=after["items"] or before["pending_count"]!=after["pending_count"]:
            raise ManualContextError("history changed")
        return {"legacy.json":raw,"candidate.json":candidate,
                "policy.json":cfg,"receipt.json":receipt}

def cutover(root,legacy,owner,backup,archive,docs,publication,*,quiescent,confirm,write=atomic):
    if not confirm:raise ManualContextError("explicit exact cutover confirmation required")
    root,archive=Path(root),Path(archive);quiescent()
    config=root/"config"/CONFIG;receipt=root/"config"/RECEIPT;journal=root/"config"/JOURNAL
    if any(p.exists() or p.is_symlink() for p in (config,receipt,journal)):
        raise ManualContextError("existing collector state requires reconciliation")
    f=legacy.file
    f._authorize(owner)
    cfg,_=validate_documents(docs["policy.json"],docs["receipt.json"],publication)
    events=f._decode(docs["legacy.json"])
    if cfg["owner_scope"]!=_identity(owner) or cfg["legacy_sha256"]!=_digest(docs["legacy.json"]) or cfg["legacy_event_count"]!=len(events):
        raise ManualContextError("cutover legacy binding mismatch")
    candidate=CollectorInbox(f.directory,cfg["owner_scope"],cfg["legacy_sha256"],cfg["legacy_event_count"])
    if candidate.file._decode(docs["candidate.json"])!=events:
        raise ManualContextError("cutover candidate history mismatch")
    with backup._destination() as fd:
        destination=backup.volume.joinpath(*backup.parts)
        if archive.parent!=destination or archive.resolve()!=archive:
            raise ManualContextError("archive outside verified destination")
        backup_path=destination/"latest.private.json"
        with f._locked():
            quiescent()
            if _read_primary(f)!=docs["legacy.json"] or backup._read(fd)!=docs["legacy.json"]:
                raise ManualContextError("predecessor changed before cutover")
            write_archive(archive,docs)
            archived=json.loads(_private_file(archive/"sha256.json"))
            if archived!={k:_digest(v) for k,v in docs.items()} or any(_read_snapshot(f,archive/k)!=v for k,v in docs.items()):
                raise ManualContextError("cutover archive verification failed")
            # Journal remains on any interruption. Both service and human gates deny.
            pin={"schema":"arvectum.workspace.collector-cutover/1","archive":str(archive),
                 "hashes":{k:_digest(v) for k,v in docs.items()}}
            atomic(journal,_json(pin))
            backup.verifier(backup.volume,backup.uuid)
            write(f.path,docs["candidate.json"])
            write(backup_path,docs["candidate.json"])
            write(config,docs["policy.json"])
            write(receipt,docs["receipt.json"])
            quiescent()
            if (_read_snapshot(f,f.path)!=docs["candidate.json"] or backup._read(fd)!=docs["candidate.json"]
                or _private_file(config)!=docs["policy.json"] or _private_file(receipt)!=docs["receipt.json"]):
                raise ManualContextError("cutover byte verification failed")
            # Validate while the journal still denies both runtime paths.
            validate_documents(_private_file(config),_private_file(receipt),publication)
            _remove(journal)
    return {"status":"migrated","legacy_sha256":_digest(docs["legacy.json"]),"archive_verified":True}

def rollback_interrupted(root,legacy,owner,backup,archive,*,quiescent,confirm):
    """Only while journal exists and current bytes still match old/candidate.
    Never overwrite any subsequent legitimate observations."""
    if not confirm:raise ManualContextError("explicit rollback confirmation required")
    root,archive=Path(root),Path(archive);quiescent()
    journal=root/"config"/JOURNAL;config=root/"config"/CONFIG;receipt=root/"config"/RECEIPT
    legacy.file._authorize(owner)
    pin=json.loads(_private_file(journal))
    if pin.get("schema")!="arvectum.workspace.collector-cutover/1" or pin.get("archive")!=str(archive):
        raise ManualContextError("rollback journal mismatch")
    with backup._destination() as fd:
        destination=backup.volume.joinpath(*backup.parts)
        if archive.parent!=destination or archive.resolve()!=archive:
            raise ManualContextError("archive outside verified destination")
        manifest=json.loads(_private_file(archive/"sha256.json"))
        names={"legacy.json","candidate.json","policy.json","receipt.json"}
        if set(manifest)!=names or manifest!=pin["hashes"]:
            raise ManualContextError("rollback archive mismatch")
        docs={}
        for k in names:
            p=archive/k
            handle=legacy.file._open(p,0)
            with open(handle,"rb") as stream:
                raw=stream.read(2*1024*1024+1)
            if _digest(raw)!=manifest[k]:raise ManualContextError("archive integrity failure")
            docs[k]=raw
        legacy.file._decode(docs["legacy.json"])
        allowed=(docs["legacy.json"],docs["candidate.json"])
        with legacy.file._locked():
            quiescent()
            if _read_snapshot(legacy.file,legacy.file.path) not in allowed or backup._read(fd) not in allowed:
                raise ManualContextError("post-cutover history changed; no rollback")
            for path,key in ((config,"policy.json"),(receipt,"receipt.json")):
                if (path.exists() or path.is_symlink()) and _private_file(path)!=docs[key]:
                    raise ManualContextError("cutover policy changed; no rollback")
            atomic(legacy.file.path,docs["legacy.json"])
            backup.verifier(backup.volume,backup.uuid)
            atomic(destination/"latest.private.json",docs["legacy.json"])
            if _read_primary(legacy.file)!=docs["legacy.json"] or backup._read(fd)!=docs["legacy.json"]:
                raise ManualContextError("rollback verification failed")
            _remove(receipt);_remove(config);_remove(journal)
    return {"status":"rolled-back","legacy_sha256":manifest["legacy.json"]}
