"""Offline provisioning. No launchctl mutation, no automatic startup."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from uuid import uuid4

import p7_04_persistent_access as p704
from arvectum_os_ref.identity import Identity
from .wsf_manual_context import ManualContextError, _identity, _digest, _json
from .wsf_manual_policy import _private_file
from .wsf_inbox_registry_migration import atomic, syncdir
from .wsf_collector_runtime import CONFIG, RECEIPT, JOURNAL, PROVISION_JOURNAL, DRAFT_BLOB, validate_documents, present
from .wsf_collector_cutover import prepare, cutover, rollback_interrupted
from .wsf_local_roadmap_collector import EXPIRY, REGISTRY_SHA, CollectorInbox, exact_registry

SCHEMA = "arvectum.workspace.collector-provision/1"
SOURCE_REVIEW = "roadmap-collector-source-review.json"
APPROVAL = "roadmap-collector-owner-approval.json"
GRANT = ("workspace.inbox.collect","roadmap-inbox",["local"])

def _now(): return datetime.now(timezone.utc)
def _sha(v): return isinstance(v,str) and re.fullmatch("[0-9a-f]{40}",v)
def _remove(p):
    if p.is_symlink(): raise ManualContextError("unsafe provision path")
    p.unlink(missing_ok=True); syncdir(p.parent)

def _isolated_state(state,key):
    return {**state,
        "principals":{k:v for k,v in state["principals"].items() if k!=key},
        "credentials":{k:v for k,v in state["credentials"].items() if v["principal_key"]!=key},
        "grants":{k:v for k,v in state["grants"].items() if v["principal_key"]!=key}}

def _source_review():
    b=exact_registry()
    return {"schema":"arvectum.workspace.collector-source-review/1","mode":"anonymous-public",
            "repositories":sorted(b[k]["repository"] for k in b if b[k]["path"]),
            "contents":"read-only","metadata":"read-only","credential":"none",
            "external_verification_required":True}

def approval_document(root,owner,legacy,backup,release,publication,decision,archive,expires):
    """Read-only review input, not approval."""
    root=Path(root); archive=Path(archive)
    if not _sha(release) or not _sha(publication) or not re.fullmatch("[A-Z0-9-]{12,160}",decision):
        raise ManualContextError("exact release, publication and decision required")
    if archive.parent!=backup.volume.joinpath(*backup.parts) or archive.resolve()!=archive or archive.exists() or archive.is_symlink():
        raise ManualContextError("invalid or already used archive")
    raw=legacy.export(owner)
    if backup.verified_snapshot(owner)!=raw:
        raise ManualContextError("predecessor backup differs")
    return {"schema":"arvectum.workspace.collector-owner-approval/1",
        "decision":decision,"publication":publication,"draft_blob":DRAFT_BLOB,
        "release_sha":release,"owner_scope":_identity(owner),
        "legacy_sha256":_digest(raw),"access_sha256":_digest(_json(p704.load_access_store(root))),
        "archive":str(archive),"expires_at":expires.isoformat(),"source_review_sha256":_digest(_json(_source_review()))}

def _verify_exact_service(root,s,cred,grant):
    state=p704.load_access_store(root);key=p704._principal_key(s)
    entries=[g for g in state["grants"].values() if g["principal_key"]==key and g["status"]=="active"]
    active=[c for c in state["credentials"].values() if c["principal_key"]==key and c["status"]=="active"]
    if len(entries)!=1 or len(active)!=1 or entries[0]["grant_id"]!=grant or active[0]["credential_id"]!=cred or (
        entries[0]["operation"],entries[0]["resource"],entries[0]["access_paths"])!=GRANT:
        raise ManualContextError("collector service has unexpected authority")
    d=p704.authorize_from_credential_file(root,organization=p704._id_load(state["organization"],"organization"),
        principal=s,credential_id=cred,credential_file=root/"secrets"/"p7-04"/(cred+".secret"),
        operation=GRANT[0],resource=GRANT[1],access_path="local")
    if not d.allowed or d.principal_kind!="service" or d.grant_id!=grant:
        raise ManualContextError("collector grant unavailable")

def provision(root,owner,legacy,backup,*,release,publication,decision,archive,expires,quiescent,confirm,source_verified):
    root=Path(root);archive=Path(archive)
    if not confirm or not source_verified or publication is None or owner.principal_kind!="human":
        raise ManualContextError("explicit production approval and source review required")
    quiescent()
    if any(present(root,k) for k in (CONFIG,RECEIPT,JOURNAL,PROVISION_JOURNAL,SOURCE_REVIEW)):
        raise ManualContextError("existing collector state requires reconciliation")
    expected=approval_document(root,owner,legacy,backup,release,publication,decision,archive,expires)
    if json.loads(_private_file(root/"config"/APPROVAL))!=expected:
        raise ManualContextError("owner approval does not match exact current state")
    now=_now()
    if not now<expires<=EXPIRY or (expires-now).total_seconds()>30*86400:
        raise ManualContextError("collector expiry outside predecessor window")
    s=Identity("principal",uuid4().hex,owner.organization.value)
    key=p704._principal_key(s)
    before=p704.load_access_store(root)
    if key in before["principals"] or expected["access_sha256"]!=_digest(_json(before)):
        raise ManualContextError("access state changed")
    # Durable intent before creating any identity or credential.
    j={"schema":SCHEMA,"approval":expected,"principal":p704._id_dict(s),
       "starts_at":now.isoformat(),"expires_at":expires.isoformat()}
    path=root/"config"/PROVISION_JOURNAL
    atomic(path,_json(j))
    quiescent()
    p704.register_principal(root,s,kind="service")
    credential=p704.issue_credential(root,s)["credential_id"]
    grant=p704.grant_access(root,s,operation=GRANT[0],resource=GRANT[1],access_paths=("local",))
    _verify_exact_service(root,s,credential,grant)
    if _isolated_state(p704.load_access_store(root),key)!=before:
        raise ManualContextError("unrelated access state changed")
    raw=_json(_source_review())
    atomic(root/"config"/SOURCE_REVIEW,raw)
    doc={"schema":"arvectum.workspace.collector-policy/1","draft_blob":DRAFT_BLOB,
        "publication":publication,"registry_sha256":REGISTRY_SHA,
        "owner_scope":_identity(owner),"organization":_identity(owner)[0],
        "principal":[s.namespace,s.value,s.scope],"credential_id":credential,"grant_id":grant,
        "release_sha":release,"starts_at":now.isoformat(),"expires_at":expires.isoformat(),
        "source_mode":"anonymous-public","source_review_sha256":_digest(raw)}
    docs=prepare(root,legacy,owner,backup,doc,publication)
    if _digest(docs["legacy.json"])!=expected["legacy_sha256"]:
        raise ManualContextError("predecessor changed after approval")
    result=cutover(root,legacy,owner,backup,archive,docs,publication,quiescent=quiescent,confirm=True)
    _verify_exact_service(root,s,credential,grant)
    if _isolated_state(p704.load_access_store(root),key)!=before:
        raise ManualContextError("unrelated access state changed after cutover")
    quiescent()
    _remove(path)
    return {**result,"service_registered":True,"grants_created":1,"schedule_installed":False,
            "other_access_unchanged":True,"expires_at":expires.isoformat()}

def recover(root,owner,legacy,backup,*,release,publication,decision,quiescent,confirm):
    """Reconcile only the journal-selected identity; no later history overwrite."""
    if not confirm or publication is None:
        raise ManualContextError("explicit recovery decision required")
    root=Path(root);quiescent()
    path=root/"config"/PROVISION_JOURNAL
    j=json.loads(_private_file(path));a=j["approval"]
    if (j["schema"]!=SCHEMA or a["owner_scope"]!=_identity(owner) or
        a["publication"]!=publication or a["release_sha"]!=release or a["decision"]!=decision or
        json.loads(_private_file(root/"config"/APPROVAL))!=a):
        raise ManualContextError("provision recovery binding mismatch")
    s=p704._id_load(j["principal"],"collector")
    key=p704._principal_key(s)
    state=p704.load_access_store(root)
    if s.scope!=owner.organization.value or s==owner.actor or _digest(_json(_isolated_state(state,key)))!=a["access_sha256"]:
        raise ManualContextError("unrelated access state differs; manual reconciliation required")
    record=state["principals"].get(key)
    if record and (record["identity"]!=j["principal"] or record["kind"]!="service"):
        raise ManualContextError("wrong recovery principal")
    if any((g["operation"],g["resource"],g["access_paths"])!=GRANT for g in state["grants"].values() if g["principal_key"]==key):
        raise ManualContextError("unexpected recovery service grant")
    if present(root,JOURNAL):
        rollback_interrupted(root,legacy,owner,backup,Path(a["archive"]),quiescent=quiescent,confirm=True)
    elif present(root,CONFIG) or present(root,RECEIPT):
        # Cutover finished but journal removal was interrupted. Preserve v2 bytes.
        p,policy=validate_documents(_private_file(root/"config"/CONFIG),_private_file(root/"config"/RECEIPT),publication)
        if policy.principal!=s or p["legacy_sha256"]!=a["legacy_sha256"] or p["owner_scope"]!=_identity(owner) or p["release_sha"]!=release:
            raise ManualContextError("completed cutover mismatch")
        _verify_exact_service(root,s,policy.credential_id,policy.grant_id)
        new=CollectorInbox(legacy.file.directory,p["owner_scope"],p["legacy_sha256"],p["legacy_event_count"])
        from .wsf_manual_backup import PilotBackup
        copy=PilotBackup(new.file,volume=backup.volume,uuid=backup.uuid,parts=backup.parts,verifier=backup.verifier)
        raw=new.export(owner)
        if copy.verified_snapshot(owner)!=raw or len(new.file._decode(raw))!=p["legacy_event_count"]:
            raise ManualContextError("completed cutover requires exact unchanged verified history")
        if _digest(_private_file(root/"config"/SOURCE_REVIEW))!=a["source_review_sha256"]:
            raise ManualContextError("source review changed")
        quiescent();_remove(path)
        return {"status":"finalized","other_access_unchanged":True,"schedule_installed":False}
    if _digest(legacy.export(owner))!=a["legacy_sha256"] or backup.verified_snapshot(owner)!=legacy.export(owner):
        raise ManualContextError("predecessor recovery mismatch")
    if record and record["status"]=="enabled":
        p704.disable_principal(root,s)
    if _digest(_json(_isolated_state(p704.load_access_store(root),key)))!=a["access_sha256"]:
        raise ManualContextError("unrelated access state changed during recovery")
    if present(root,SOURCE_REVIEW):
        if _digest(_private_file(root/"config"/SOURCE_REVIEW))!=a["source_review_sha256"]:
            raise ManualContextError("source review changed")
        _remove(root/"config"/SOURCE_REVIEW)
    # Retain approval and any archives; only the recovery gate is cleared.
    quiescent();_remove(path)
    return {"status":"aborted","original_history_preserved":True,"other_access_unchanged":True,"schedule_installed":False}
