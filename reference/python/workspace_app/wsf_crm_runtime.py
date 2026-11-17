"""Restricted native CRM runtime candidate.

Activation requires exact separately published successor contract. No policy
pin is admitted in this candidate; no production grant is supplied. Named
contacts and communications are excluded in the first operational slice.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re

import p7_04_persistent_access as p704
from .wsf_manual_context import ManualContextError, _identity
from .wsf_manual_policy import _private_file
from .wsf_manual_runtime import RuntimeManualPilot, APPROVED_DRAFT as MANUAL_DRAFT
from .wsf_crm import CRMStore
from .wsf_crm_backup import crm_backup

# Deliberately unset until exact approved publication and implementation review.
APPROVED_DRAFT = None
RESOURCE = "crm-lite"
OPERATIONS = {op:"workspace.crm."+op for op in ("read","party","opportunity","export")}
SCHEMA = "arvectum.workspace.crm-restricted-policy/1"
RECEIPT_SCHEMA = "arvectum.workspace.crm-activation/1"


class RuntimeCRMPilot:
    def __init__(self,root,*,approved_draft=APPROVED_DRAFT):
        self.root=Path(root)
        self.approved_draft=approved_draft
        self.manual=RuntimeManualPilot(self.root)

    def _gate(self,access,operation):
        if operation not in OPERATIONS or not self.approved_draft:
            raise ManualContextError("CRM operation not admitted")
        try:
            if not self.root.is_absolute() or self.root.resolve()!=self.root:
                raise ManualContextError("unsafe root")
            receipt=json.loads(_private_file(self.root/"config"/"crm-activation.json"))
            if set(receipt)!={"schema","draft_blob","policy_sha256"} or receipt["schema"]!=RECEIPT_SCHEMA or receipt["draft_blob"]!=self.approved_draft:
                raise ManualContextError("approval pin mismatch")
            raw=_private_file(self.root/"config"/"crm-policy.json")
            if hashlib.sha256(raw).hexdigest()!=receipt["policy_sha256"]:
                raise ManualContextError("policy pin mismatch")
            p=json.loads(raw)
            if (set(p)!={"schema","draft_blob","scope","credential_id","starts_at","expires_at","grants","purpose"}
                 or p["schema"]!=SCHEMA or p["draft_blob"]!=self.approved_draft or p["scope"]!=_identity(access)
                 or p["credential_id"]!=access.credential_id or p["purpose"]!="non-sensitive-organization-coordination"
                 or set(p["grants"])!=set(OPERATIONS.values())
                 or any(not re.fullmatch("[0-9a-f]{32}",x) for x in p["grants"].values())
                 or len(set(p["grants"].values()))!=len(OPERATIONS)):
                raise ManualContextError("policy scope mismatch")
            start,end=(datetime.fromisoformat(p[k]) for k in ("starts_at","expires_at"))
            if start.utcoffset()!=timedelta(0) or end.utcoffset()!=timedelta(0) or not start<=datetime.now(timezone.utc)<end or end-start>timedelta(days=30):
                raise ManualContextError("CRM policy expired")
            # The first CRM slice cannot outlive or bypass the existing pilot.
            notes=self.manual.authorize_operation(access,"read")
            manual=json.loads(_private_file(self.root/"config"/"manual-context-policy.json"))
            if manual["contract_draft_blob"]!=MANUAL_DRAFT or end>datetime.fromisoformat(manual["expires_at"]):
                raise ManualContextError("predecessor window exceeded")
            if not re.fullmatch("[0-9a-f]{32}",access.credential_id):
                raise ManualContextError("credential invalid")
            exact=OPERATIONS[operation]
            d=p704.authorize_from_credential_file(self.root,organization=access.organization,principal=access.actor,
                credential_id=access.credential_id,credential_file=self.root/"secrets"/"p7-04"/(access.credential_id+".secret"),
                operation=exact,resource=RESOURCE,access_path="local")
            if not d.allowed or d.principal_kind!="human" or d.grant_id!=p["grants"][exact]:
                raise ManualContextError("exact grant unavailable")
            data=notes.read(access)
            projects={x["id"]:x["label"] for x in data["projects"]}
            refs={x["id"] for x in data["notes"]}
            path=self.root/"workspace-company-crm"
            if path.resolve()!=path or not path.is_dir() or not (path/"crm.json").is_file():
                raise ManualContextError("initialized CRM unavailable")
            store=CRMStore(path,access,project_ids=set(projects),evidence_refs=refs,require_initialized=True,
                           allowed_entities={"party","opportunity"})
            # Existing historical data must also satisfy this exact restricted scope.
            store.read(access)
            return store,projects
        except (OSError,ValueError,TypeError,KeyError,AttributeError,RecursionError,p704.P704Error) as exc:
            raise ManualContextError("CRM unavailable") from exc

    def authorize(self,access,operation):
        return self._gate(access,operation)[0]

    def catalog(self,access):
        store,projects=self._gate(access,"read")
        return {"projects":[{"id":k,"label":v} for k,v in sorted(projects.items(),key=lambda kv:kv[1])],
                "evidence_refs":sorted(store.refs),"allowed_entities":["party","opportunity"],
                "handling":"non-sensitive-organization-coordination"}

    def backup(self,access):
        return crm_backup(self.authorize(access,"export")).copy_latest(access)

    def submit(self,access,key,entity,data,*,record_id=None,expected_revision=0):
        if entity not in {"party","opportunity"}:
            raise ManualContextError("entity not admitted")
        self.authorize(access,entity)
        self.backup(access)
        s=self.authorize(access,entity)
        row=s.submit(access,key,entity,data,record_id=record_id,expected_revision=expected_revision)
        try:
            self.backup(access)
            return {**row,"backup_status":"verified"}
        except (OSError,ManualContextError):
            return {**row,"backup_status":"saved-primary-backup-unavailable"}
