#!/usr/bin/env python3
"""Restricted CRM operator candidate. No activation until an exact published pin."""
import argparse
from datetime import datetime,timedelta,timezone
import hashlib,json
from pathlib import Path

import p7_04_persistent_access as p704
from workspace_app.access import P704AccessResolver
from workspace_app.config import WorkspaceSettings
from workspace_app.wsf_crm import CRMStore
from workspace_app.wsf_crm_backup import crm_backup,CRM_PARTS
from workspace_app.wsf_crm_runtime import RuntimeCRMPilot,APPROVED_DRAFT,RESOURCE,OPERATIONS,SCHEMA,RECEIPT_SCHEMA
from workspace_app.wsf_manual_context import ManualContextError,_identity
from workspace_app.wsf_manual_runtime import RuntimeManualPilot
from wsf_manual_operator import prepare_destination,write_new

PUBLICATION="WSF-05-06-RESTRICTED-CRM-PRODUCT-CONTRACT-PROVISIONAL-v0.5.0.md"
DECISION="DECISION-WSF-05-06-RESTRICTED-CRM-APPROVAL"


def activate(root,draft,decision,confirm):
    if not APPROVED_DRAFT or draft!=APPROVED_DRAFT or decision!=DECISION or not confirm:
        raise ManualContextError("exact effective contract and activation decision required")
    publication=Path(__file__).resolve().parents[2]/"docs/contracts"/PUBLICATION
    if not publication.is_file() or APPROVED_DRAFT not in publication.read_text(encoding="utf-8"):
        raise ManualContextError("published exact contract unavailable")
    if root.resolve()!=root:raise ManualContextError("unsafe runtime root")
    policy_path=root/"config"/"crm-policy.json"
    receipt_path=root/"config"/"crm-activation.json"
    directory=root/"workspace-company-crm"
    if any(p.exists() or p.is_symlink() for p in (policy_path,receipt_path,directory)):
        raise ManualContextError("existing state; review, never reinitialize")
    access=P704AccessResolver(root).authorize()
    manual=RuntimeManualPilot(root)
    data=manual.authorize_operation(access,"read").read(access)
    expiry=datetime.fromisoformat(manual.review_signal(access)["due_at"])
    start=datetime.now(timezone.utc)
    if expiry<=start or expiry-start>timedelta(days=30):
        raise ManualContextError("existing pilot review window unavailable")
    state=p704.load_access_store(root)
    if any(g["operation"] in OPERATIONS.values() and g["resource"]==RESOURCE and g["status"]=="active" for g in state["grants"].values()):
        raise ManualContextError("existing CRM grants require review")
    prepare_destination(CRM_PARTS)
    s=CRMStore(directory,access,project_ids={v["id"] for v in data["projects"]},
               evidence_refs={v["id"] for v in data["notes"]},allowed_entities={"party","opportunity"})
    s.initialize(access)
    b=crm_backup(s);b.copy_latest(access)
    if b.verified_snapshot(access)!=s.export(access):
        raise ManualContextError("initial backup mismatch")
    grants={};receipt_written=False
    try:
        for op in sorted(OPERATIONS.values()):
            grants[op]=p704.grant_access(root,access.actor,operation=op,resource=RESOURCE,access_paths=("local",))
        p={"schema":SCHEMA,"draft_blob":APPROVED_DRAFT,"scope":_identity(access),
           "credential_id":access.credential_id,"starts_at":start.isoformat(),"expires_at":expiry.isoformat(),
           "grants":grants,"purpose":"non-sensitive-organization-coordination"}
        raw=json.dumps(p,sort_keys=True,separators=(",",":")).encode()
        write_new(policy_path,raw)
        receipt={"schema":RECEIPT_SCHEMA,"draft_blob":APPROVED_DRAFT,"policy_sha256":hashlib.sha256(raw).hexdigest()}
        write_new(receipt_path,json.dumps(receipt,sort_keys=True,separators=(",",":")).encode())
        receipt_written=True
        pilot=RuntimeCRMPilot(root)
        for op in OPERATIONS:pilot.authorize(access,op)
        if pilot.read(access)["backup_status"]!="verified":raise ManualContextError("CRM backup unverified")
    except Exception:
        if receipt_written and receipt_path.is_file() and not receipt_path.is_symlink():receipt_path.unlink()
        for gid in grants.values():p704.revoke_grant(root,gid)
        raise
    return {"status":"activated","expires_at":expiry.isoformat(),"operation_grants":len(grants),"backup":"verified"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("operation",choices=("activate","backup","status"))
    p.add_argument("--draft");p.add_argument("--decision");p.add_argument("--confirm",action="store_true")
    args=p.parse_args();root=WorkspaceSettings.from_env().runtime_root
    if args.operation=="activate":
        d=activate(root,args.draft,args.decision,args.confirm)
    else:
        a=P704AccessResolver(root).authorize();pilot=RuntimeCRMPilot(root)
        if args.operation=="backup":d=pilot.backup(a)
        else:
            s=pilot.read(a);d={"parties":len(s["party"]),"opportunities":len(s["opportunity"]),"backup_status":s["backup_status"]}
    print(json.dumps(d,sort_keys=True))


if __name__=="__main__":
    try:main()
    except (ManualContextError,OSError,p704.P704Error):
        raise SystemExit("CRM unavailable; review exact activation or backup state") from None
