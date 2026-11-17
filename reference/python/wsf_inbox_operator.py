#!/usr/bin/env python3
"""Explicit owner-local inbox operator; no active pin or scheduled collector."""
import argparse,hashlib,json
from datetime import datetime,timedelta,timezone
from pathlib import Path
import p7_04_persistent_access as p704
from workspace_app.access import P704AccessResolver
from workspace_app.config import WorkspaceSettings
from workspace_app.wsf_manual_context import ManualContextError,_identity,_digest,_json
from workspace_app.wsf_manual_runtime import RuntimeManualPilot
from workspace_app.wsf_roadmap_inbox import RoadmapInbox,registry_bindings
from workspace_app.wsf_manual_backup import PilotBackup
from workspace_app.wsf_inbox_routes import INBOX_PARTS
from workspace_app.wsf_inbox_runtime import RuntimeInboxPilot,APPROVED_DRAFT,OPERATIONS,RESOURCE,SCHEMA,RECEIPT_SCHEMA
from wsf_manual_operator import prepare_destination,write_new

PUBLICATION="WSF-07-ROADMAP-INBOX-PROVISIONAL-v0.6.0.md"
DECISION="DECISION-WSF-07-ROADMAP-INBOX-APPROVAL"

def activate(root,draft,decision,confirm):
    if not APPROVED_DRAFT or draft!=APPROVED_DRAFT or decision!=DECISION or not confirm:
        raise ManualContextError("exact effective inbox contract and activation decision required")
    publication=Path(__file__).resolve().parents[2]/"docs/contracts"/PUBLICATION
    if not publication.is_file() or APPROVED_DRAFT not in publication.read_text(encoding="utf-8"):
        raise ManualContextError("published exact contract required")
    if root.resolve()!=root:raise ManualContextError("unsafe root")
    policy=root/"config"/"roadmap-inbox-policy.json"
    receipt=root/"config"/"roadmap-inbox-activation.json"
    directory=root/"workspace-company-roadmap-inbox"
    if any(x.exists() or x.is_symlink() for x in (policy,receipt,directory)):
        raise ManualContextError("existing state requires reconciliation")
    access=P704AccessResolver(root).authorize()
    expiry=datetime.fromisoformat(RuntimeManualPilot(root).review_signal(access)["due_at"])
    start=datetime.now(timezone.utc)
    if expiry<=start or expiry-start>timedelta(days=30):raise ManualContextError("predecessor window unavailable")
    state=p704.load_access_store(root)
    if any(g["operation"] in OPERATIONS.values() and g["resource"]==RESOURCE and g["status"]=="active" for g in state["grants"].values()):
        raise ManualContextError("existing inbox grants require review")
    bindings=registry_bindings()
    prepare_destination(INBOX_PARTS)
    inbox=RoadmapInbox(directory,access,bindings=bindings)
    inbox.initialize(access)
    backup=PilotBackup(inbox.file,parts=INBOX_PARTS)
    backup.copy_latest(access)
    if backup.verified_snapshot(access)!=inbox.export(access):raise ManualContextError("initial backup mismatch")
    grants={};receipt_written=False
    try:
        for op in sorted(OPERATIONS.values()):
            grants[op]=p704.grant_access(root,access.actor,operation=op,resource=RESOURCE,access_paths=("local",))
        p={"schema":SCHEMA,"draft_blob":APPROVED_DRAFT,"registry_sha256":_digest(_json(bindings)),
           "scope":_identity(access),"credential_id":access.credential_id,"starts_at":start.isoformat(),
           "expires_at":expiry.isoformat(),"grants":grants,"purpose":"owner-triggered-roadmap-metadata"}
        raw=_json(p);write_new(policy,raw)
        write_new(receipt,_json({"schema":RECEIPT_SCHEMA,"draft_blob":APPROVED_DRAFT,"policy_sha256":hashlib.sha256(raw).hexdigest()}))
        receipt_written=True
        pilot=RuntimeInboxPilot(root)
        for op in OPERATIONS:pilot.authorize(access,op)
        if pilot.read(access)["backup_status"]!="verified":raise ManualContextError("initial backup unverified")
    except Exception:
        if receipt_written and receipt.is_file() and not receipt.is_symlink():receipt.unlink()
        for gid in grants.values():p704.revoke_grant(root,gid)
        raise
    return {"status":"activated","operation_grants":len(grants),"expires_at":expiry.isoformat(),"backup":"verified","polling":"owner-triggered-only"}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("operation",choices=("activate","backup","status"))
    parser.add_argument("--draft");parser.add_argument("--decision");parser.add_argument("--confirm",action="store_true")
    args=parser.parse_args();root=WorkspaceSettings.from_env().runtime_root
    if args.operation=="activate":r=activate(root,args.draft,args.decision,args.confirm)
    else:
        a=P704AccessResolver(root).authorize();p=RuntimeInboxPilot(root)
        if args.operation=="backup":r=p.backup(a)
        else:
            d=p.read(a);r={"backup_status":d["backup_status"],"sources":len(d["sources"]),"pending":d["pending_count"]}
    print(json.dumps(r,sort_keys=True))

if __name__=="__main__":
    try:main()
    except (ManualContextError,OSError,p704.P704Error):
        raise SystemExit("Inbox unavailable; review exact policy and backup") from None
