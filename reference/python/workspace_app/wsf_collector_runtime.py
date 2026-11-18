"""0.6.2 composition; publication pin is not an activation receipt."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from arvectum_os_ref.identity import Identity
from .wsf_manual_context import ManualContextError, _identity, _digest, _json
from .wsf_manual_policy import _private_file
from .wsf_local_roadmap_collector import CollectorInbox, ServicePolicy, EXPIRY, REGISTRY_SHA, exact_registry

# Exact proposed publication blob; only effective after owner-approved main publication.
PUBLICATION_PIN = "725e89b43ef346fa6408cfc4484cb46548b6b1cc"
DRAFT_BLOB = "290d7cf7eef5461bfce86ff39871b9267e6efcff"
CONFIG = "roadmap-collector-policy.json"
RECEIPT = "roadmap-collector-activation.json"
JOURNAL = "roadmap-collector-cutover.json"
PROVISION_JOURNAL = "roadmap-collector-provision.json"
KEYS = {"schema","draft_blob","publication","registry_sha256","owner_scope",
        "organization","principal","credential_id","grant_id","release_sha",
        "starts_at","expires_at","legacy_sha256","legacy_event_count",
        "source_mode","source_review_sha256"}

def present(root,name):
    p=Path(root)/"config"/name
    return p.exists() or p.is_symlink()

def _utc():
    return datetime.now(timezone.utc)

def _ident(v):
    if not isinstance(v,list) or len(v)!=3 or any(not isinstance(x,str) or not x for x in v):
        raise ManualContextError("collector identity invalid")
    return Identity(*v)

def load_config(root,*,publication=None):
    root=Path(root)
    if publication is None or not re.fullmatch("[0-9a-f]{40}",publication):
        raise ManualContextError("collector publication not admitted")
    if not root.is_absolute() or root.resolve()!=root or present(root,JOURNAL) or present(root,PROVISION_JOURNAL):
        raise ManualContextError("collector cutover incomplete")
    try:
        return validate_documents(_private_file(root/"config"/CONFIG),_private_file(root/"config"/RECEIPT),publication)
    except OSError as exc:
        raise ManualContextError("collector policy unavailable") from exc

def validate_documents(raw,receipt_raw,publication):
    if publication is None or not re.fullmatch("[0-9a-f]{40}",publication):
        raise ManualContextError("collector publication not admitted")
    try:
        receipt=json.loads(receipt_raw)
        p=json.loads(raw)
        if (receipt!={"schema":"arvectum.workspace.collector-activation/1",
                     "publication":publication,"policy_sha256":_digest(raw)}
            or set(p)!=KEYS or p["schema"]!="arvectum.workspace.collector-policy/1"
            or p["draft_blob"]!=DRAFT_BLOB or p["publication"]!=publication
            or p["registry_sha256"]!=REGISTRY_SHA
            or p["source_mode"]!="anonymous-public"
            or not re.fullmatch("[0-9a-f]{64}",p["source_review_sha256"])
            or not re.fullmatch("[0-9a-f]{64}",p["legacy_sha256"])
            or type(p["legacy_event_count"]) is not int or not 0<=p["legacy_event_count"]<=500):
            raise ManualContextError("collector policy or receipt mismatch")
        exact_registry()
        org,svc=_ident(p["organization"]),_ident(p["principal"])
        scope=p["owner_scope"]
        if not isinstance(scope,list) or len(scope)!=2 or scope[0]!=p["organization"]:
            raise ManualContextError("collector owner scope mismatch")
        _ident(scope[1])
        start,end=(datetime.fromisoformat(p[k]) for k in ("starts_at","expires_at"))
        if (start.utcoffset().total_seconds()!=0 or end.utcoffset().total_seconds()!=0
            or not start<end<=EXPIRY or end.timestamp()-start.timestamp()>30*86400
            or not re.fullmatch("[0-9a-f]{32}",p["credential_id"])
            or not re.fullmatch("[0-9a-f]{32}",p["grant_id"])
            or not re.fullmatch("[0-9a-f]{40}",p["release_sha"])):
            raise ManualContextError("collector policy bounds invalid")
        policy=ServicePolicy(tuple(tuple(i) for i in scope),org,svc,p["credential_id"],
                             p["grant_id"],p["release_sha"],start,end)
        return p,policy
    except (OSError,ValueError,TypeError,KeyError,AttributeError,RecursionError) as exc:
        raise ManualContextError("collector policy unavailable") from exc

def human_inbox(root,access,*,publication=None):
    p,_=load_config(root,publication=publication)
    if p["owner_scope"]!=_identity(access):
        raise ManualContextError("collector human scope mismatch")
    # Service expiry or revocation must not independently revoke the existing human pilot.
    return CollectorInbox(Path(root)/"workspace-company-roadmap-inbox",p["owner_scope"],
                          p["legacy_sha256"],p["legacy_event_count"])

def service_inbox(root,*,publication=None):
    p,policy=load_config(root,publication=publication)
    inbox=CollectorInbox(Path(root)/"workspace-company-roadmap-inbox",p["owner_scope"],
                         p["legacy_sha256"],p["legacy_event_count"])
    def resolve():
        current,fresh=load_config(root,publication=publication)
        if current!=p or fresh!=policy:
            raise ManualContextError("collector policy changed")
        # Pin the still-admitted predecessor and source-review document at each
        # authorization boundary; never extend an earlier owner pilot expiry.
        oldraw=_private_file(Path(root)/"config"/"roadmap-inbox-policy.json")
        old=json.loads(oldraw)
        receipt=json.loads(_private_file(Path(root)/"config"/"roadmap-inbox-activation.json"))
        if (receipt.get("policy_sha256")!=_digest(oldraw) or receipt.get("draft_blob")!=old.get("draft_blob")
            or old.get("scope")!=p["owner_scope"] or old.get("registry_sha256")!=REGISTRY_SHA
            or datetime.fromisoformat(old["expires_at"])<policy.expires_at
            or _digest(_private_file(Path(root)/"config"/"roadmap-collector-source-review.json"))!=p["source_review_sha256"]):
            raise ManualContextError("collector predecessor or source review changed")
        return fresh.resolve(root)
    return inbox,p,policy,resolve
