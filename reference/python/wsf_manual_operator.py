#!/usr/bin/env python3
"""Owner-local WSF-04C operator. Explicit activation only, no renewal or purge."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path

import p7_04_persistent_access as p704
from workspace_app.access import P704AccessResolver
from workspace_app.config import WorkspaceSettings
from workspace_app.wsf_manual_context import ManualContextStore, ManualContextError, _identity
from workspace_app.wsf_manual_policy import OPERATIONS, POLICY_SCHEMA, RESOURCE
from workspace_app.wsf_manual_backup import PilotBackup, VOLUME, VOLUME_UUID, BACKUP_PARTS, verify_volume
from workspace_app.wsf_manual_runtime import RuntimeManualPilot, APPROVAL_DECISION, APPROVED_DRAFT, ACTIVATION_SCHEMA, ACTIVATION_FILE


def write_new(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def prepare_destination(parts=BACKUP_PARTS):
    verify_volume(VOLUME, VOLUME_UUID)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(VOLUME, flags)
    try:
        dev = os.fstat(fd).st_dev
        verify_volume(VOLUME, VOLUME_UUID)
        if VOLUME.stat().st_dev != dev:
            raise ManualContextError("mount changed")
        for i, part in enumerate(parts):
            if i >= 2:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
            if os.fstat(fd).st_dev != dev:
                raise ManualContextError("backup mount crossed")
        st = os.fstat(fd)
        if st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise ManualContextError("backup directory unsafe")
        if os.listdir(fd):
            raise ManualContextError("backup destination not empty; manual review required")
    finally:
        os.close(fd)


def activate(root, decision, draft, confirm):
    if not confirm or decision != APPROVAL_DECISION or draft != APPROVED_DRAFT:
        raise ManualContextError("exact explicit activation decision required")
    if root.resolve() != root:
        raise ManualContextError("runtime root unsafe")
    # The receipt is written last; any interruption leaves production denied.
    policy_path = root/"config"/"manual-context-policy.json"
    receipt_path = root/"config"/ACTIVATION_FILE
    directory = root/"workspace-company-manual-context"
    if any(p.exists() or p.is_symlink() for p in (policy_path,receipt_path,directory)):
        raise ManualContextError("existing activation or state; no renewal/reinitialize")
    publication = Path(__file__).resolve().parents[2]/"docs/contracts/WSF-04C-ARVECTUM-COMPANY-WORKSPACE-PRODUCT-CONTRACT-PROVISIONAL-v0.4.0.md"
    if not publication.is_file() or APPROVED_DRAFT not in publication.read_text(encoding="utf-8"):
        raise ManualContextError("published exact contract unavailable")
    access = P704AccessResolver(root).authorize()
    state = p704.load_access_store(root)
    if any(g["operation"] in OPERATIONS and g["resource"] == RESOURCE and g["status"] == "active" for g in state["grants"].values()):
        raise ManualContextError("existing manual grants; review required")
    prepare_destination()
    store = ManualContextStore(directory, access)
    store.restore_empty(access, store.export(access))
    backup = PilotBackup(store)
    backup.copy_latest(access)
    if backup.verified_snapshot(access) != store.export(access):
        raise ManualContextError("initial backup verification failed")
    grants = {}
    try:
        for op in sorted(OPERATIONS):
            grants[op] = p704.grant_access(root,access.actor,operation=op,resource=RESOURCE,access_paths=("local",))
        start=datetime.now(timezone.utc)
        expires=start+timedelta(days=30)
        policy={"schema":POLICY_SCHEMA,"contract_draft_blob":APPROVED_DRAFT,
                "scope":_identity(access),"credential_id":access.credential_id,
                "starts_at":start.isoformat(),"expires_at":expires.isoformat(),
                "grants":grants,"purpose":"restricted-internal-project-coordination"}
        raw=json.dumps(policy,sort_keys=True,separators=(",",":")).encode()
        write_new(policy_path,raw)
        receipt={"schema":ACTIVATION_SCHEMA,"draft_blob":APPROVED_DRAFT,"decision":APPROVAL_DECISION,
                 "policy_sha256":hashlib.sha256(raw).hexdigest()}
        write_new(receipt_path,json.dumps(receipt,sort_keys=True,separators=(",",":")).encode())
        pilot=RuntimeManualPilot(root)
        for op in ("project","capture","revise","read","export"):
            pilot.authorize_operation(access,op)
        if pilot.read(access)["backup_status"]!="verified":
            raise ManualContextError("activated backup verification failed")
    except Exception:
        # Never delete data or policy files; remove only the enable receipt
        # written by this activation and revoke only newly issued grants.
        if receipt_path.is_file() and not receipt_path.is_symlink():
            receipt_path.unlink()
        for gid in grants.values():
            p704.revoke_grant(root,gid)
        raise
    return {"status":"activated","starts_at":start.isoformat(),"expires_at":expires.isoformat(),
            "policy_sha256":receipt["policy_sha256"],"operation_grants":len(grants),"backup":"verified"}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("operation",choices=("activate","backup","status"))
    parser.add_argument("--decision")
    parser.add_argument("--draft")
    parser.add_argument("--confirm",action="store_true")
    args=parser.parse_args()
    root=WorkspaceSettings.from_env().runtime_root
    if args.operation=="activate":
        result=activate(root,args.decision,args.draft,args.confirm)
    else:
        access=P704AccessResolver(root).authorize()
        pilot=RuntimeManualPilot(root)
        if args.operation=="backup":
            result=pilot.backup(access)
        else:
            d=pilot.read(access)
            result={"status":"available","projects":len(d["projects"]),"notes":len(d["notes"]),"backup_status":d["backup_status"]}
    print(json.dumps(result,sort_keys=True))

if __name__=="__main__":
    try:
        main()
    except (ManualContextError,OSError,p704.P704Error) as exc:
        raise SystemExit("WSF-04C unavailable; review exact activation/backup state") from None
