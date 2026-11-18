"""Offline, exact compatible release re-pin. Never change ledger or access grants."""
import json
from datetime import datetime,timezone
from pathlib import Path
import re
from .wsf_collector_runtime import CONFIG, RECEIPT, PROVISION_JOURNAL, JOURNAL, present, validate_documents
from .wsf_collector_runner import STATUS, launchd_template, read_status
from .wsf_collector_provision import _verify_exact_service
from .wsf_local_roadmap_collector import CollectorInbox
from .wsf_manual_context import ManualContextError,_identity,_digest,_json
from .wsf_manual_policy import _private_file
from .wsf_inbox_registry_migration import atomic,syncdir,write_archive
import p7_04_persistent_access as p704

SCHEMA="arvectum.workspace.collector-compatible-repin/1"

def _now():return datetime.now(timezone.utc)

def _paths(root,plist):
    return {"policy":root/"config"/CONFIG,"receipt":root/"config"/RECEIPT,
            "status":root/"run"/STATUS,"plist":Path(plist)}

def _check(root,owner,policy,cfg,inbox,backup,expected):
    if _identity(owner)!=cfg["owner_scope"] or owner.principal_kind!="human":
        raise ManualContextError("re-pin owner mismatch")
    if not policy.starts_at<=_now()<policy.expires_at:
        raise ManualContextError("re-pin cannot renew expiry")
    old=_private_file(root/"config"/"roadmap-inbox-policy.json")
    p=json.loads(old); receipt=json.loads(_private_file(root/"config"/"roadmap-inbox-activation.json"))
    if (receipt.get("policy_sha256")!=_digest(old) or receipt.get("draft_blob")!=p.get("draft_blob")
        or p.get("scope")!=cfg["owner_scope"] or p.get("registry_sha256")!=cfg["registry_sha256"]
        or datetime.fromisoformat(p["expires_at"])<policy.expires_at
        or _digest(_private_file(root/"config"/"roadmap-collector-source-review.json"))!=cfg["source_review_sha256"]):
        raise ManualContextError("predecessor or source review changed")
    _verify_exact_service(root,policy.principal,policy.credential_id,policy.grant_id)
    raw=inbox.export(owner)
    if backup.verified_snapshot(owner)!=raw:
        raise ManualContextError("backup differs")
    pins={"ledger_sha256":_digest(raw),"access_sha256":_digest(_json(p704.load_access_store(root)))}
    if expected is not None and pins!=expected:raise ManualContextError("history or access changed")
    return pins

def switch(root,owner,*,source,target,publication,decision,archive,plist,backup_factory,quiescent,verify_release,confirm,write=atomic):
    """Caller proves exact canonical releases, successful governed transition and unloaded jobs.
    Resume only the identical journal after interruption. No rollback of later events."""
    root,archive=Path(root),Path(archive)
    if not confirm or source==target or not all(re.fullmatch("[0-9a-f]{40}",x) for x in (source,target,publication)) or not re.fullmatch("[A-Z0-9-]{12,160}",decision):
        raise ManualContextError("exact re-pin approval required")
    quiescent();verify_release()
    if present(root,JOURNAL):raise ManualContextError("Inbox cutover separately incomplete")
    journal=root/"config"/PROVISION_JOURNAL
    paths=_paths(root,plist)
    binding={"schema":SCHEMA,"source":source,"target":target,"publication":publication,"decision":decision,"archive":str(archive)}
    if present(root,PROVISION_JOURNAL):
        j=json.loads(_private_file(journal))
        if {k:j.get(k) for k in binding}!=binding or set(j)!=set(binding)|{"hashes","pins"}:
            raise ManualContextError("another operation requires reconciliation")
        manifest=json.loads(_private_file(archive/"sha256.json"))
        names={side+"-"+key for side in ("old","new") for key in paths}
        if manifest!=j["hashes"] or set(manifest)!=names:raise ManualContextError("archive manifest mismatch")
        docs={k:_private_file(archive/k) for k in names}
        if any(_digest(v)!=manifest[k] for k,v in docs.items()):raise ManualContextError("archive corrupted")
        old={k:docs["old-"+k] for k in paths};new={k:docs["new-"+k] for k in paths}
        pins=j["pins"]
    else:
        old={k:_private_file(v) for k,v in paths.items()}
        cfg,policy=validate_documents(old["policy"],old["receipt"],publication)
        status=read_status(root)
        if (cfg["release_sha"]!=source or not status or status["release_sha"]!=source
            or status["state"]!="verified" or old["plist"]!=launchd_template(root,source)):
            raise ManualContextError("existing state requires reconciliation")
        raw=_json({**cfg,"release_sha":target})
        new={"policy":raw,"receipt":_json({"schema":"arvectum.workspace.collector-activation/1","publication":publication,"policy_sha256":_digest(raw)}),
             "status":_json({**status,"release_sha":target}),"plist":launchd_template(root,target)}
        pins=None
    cfg,policy=validate_documents(old["policy"],old["receipt"],publication)
    nc,np=validate_documents(new["policy"],new["receipt"],publication)
    if cfg["release_sha"]!=source or nc!={**cfg,"release_sha":target} or new["status"]!=_json({**json.loads(old["status"]),"release_sha":target}) or old["plist"]!=launchd_template(root,source) or new["plist"]!=launchd_template(root,target):
        raise ManualContextError("re-pin would alter scope or history")
    inbox=CollectorInbox(root/"workspace-company-roadmap-inbox",cfg["owner_scope"],cfg["legacy_sha256"],cfg["legacy_event_count"])
    backup=backup_factory(inbox.file)
    if archive.parent!=backup.volume.joinpath(*backup.parts) or archive.resolve()!=archive:
        raise ManualContextError("archive outside approved backup destination")
    with inbox.file.cycle_lock(), backup._destination():
        quiescent();verify_release()
        verified=_check(root,owner,policy,cfg,inbox,backup,pins)
        for k,p in paths.items():
            if _private_file(p) not in (old[k],new[k]):raise ManualContextError("re-pin files changed")
        if pins is None:
            docs={side+"-"+k:v for side,values in (("old",old),("new",new)) for k,v in values.items()}
            write_archive(archive,docs)
            hashes={k:_digest(v) for k,v in docs.items()}
            if json.loads(_private_file(archive/"sha256.json"))!=hashes or any(_private_file(archive/k)!=v for k,v in docs.items()):
                raise ManualContextError("re-pin archive verification failed")
            atomic(journal,_json({**binding,"pins":verified,"hashes":hashes}))
        for k in ("policy","receipt","status","plist"):
            write(paths[k],new[k])
        if any(_private_file(p)!=new[k] for k,p in paths.items()):raise ManualContextError("re-pin verification failed")
        _check(root,owner,np,nc,inbox,backup,verified)
        quiescent();verify_release()
        journal.unlink();syncdir(journal.parent)
    return {"status":"repinned","release":target,"ledger_unchanged":True,"access_unchanged":True,"window_preserved":True,"schedule_loaded":False}
