"""Approved 0.7.0 reference-only runtime. Missing private admission denies all reads."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import http.client
import json
from pathlib import Path
import re

import p7_04_persistent_access as p704
from .wsf_manual_context import ManualContextError, _identity, _id, _keys
from .wsf_manual_policy import _private_file
from .wsf_manual_runtime import RuntimeManualPilot

DRAFT = "9c0f7caa552613ab598d9de05b819524a74e8c73"
OPERATION = "workspace.procurement.read"
RESOURCE = "internal-procurement-reference"
SOURCE_PATH = "/api/internal/workspace/procurement-reference"
MAX_BYTES = 65536
MAX_EXPIRY = datetime.fromisoformat("2026-12-17T09:35:36.060836+00:00")
WORKFLOW = frozenset("""NEW CANDIDATE DOCS_ANALYSIS SUPPLIER_SOURCING ECONOMICS_REVIEW
WAITING_CEO_APPROVAL_TO_BID BID_PREPARATION PRE_SUBMISSION SUBMISSION POST_SUBMISSION
OUTCOME_CAPTURE DECLINED_TO_BID REJECTED_EARLY UNKNOWN""".split())
DECISION_CODES = frozenset("""PORTFOLIO_BID_DECISION CEO_APPROVAL_DECISION APPROVE_TO_BID DECLINE_TO_BID
DEAL_MARKED_REJECTED_EARLY OPERATOR_REJECTED_PREBID OPERATOR_MARKED_NEEDS_MORE_REVIEW""".split())
BID = frozenset({"GO","NO_GO","NEEDS_REVIEW","DEFER","GO_WITH_CONDITIONS","UNKNOWN"})


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def match(value, pattern):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def ref(value):
    if not match(value, r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}"):
        raise ManualContextError("invalid evidence reference")


def stamp(value):
    if not isinstance(value,str):raise ManualContextError("timestamp required")
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.utcoffset()!=timedelta(0):raise ManualContextError("UTC required")
    return d


def validate_source(raw, policy, started, finished):
    """Strict closed shape and exact set check before releasing any source fields."""
    if not isinstance(raw, bytes) or len(raw)>MAX_BYTES:raise ManualContextError("source size")
    try:
        data = json.loads(raw)
        _keys(data,{"schema","binding_id","source_release","database_binding","observed_at",
                    "coverage","items","canonical_authority"})
        if (data["schema"]!="arvectum.tender.internal-procurement-reference/1"
            or data["binding_id"]!=policy["binding_id"] or data["source_release"]!=policy["source_release"]
            or data["database_binding"]!=policy["database_binding"]
            or data["coverage"]!="admitted-identity-set-only" or data["canonical_authority"] is not False):
            raise ManualContextError("source identity mismatch")
        observed=stamp(data["observed_at"])
        if not started-timedelta(seconds=5)<=observed<=finished+timedelta(seconds=5):
            raise ManualContextError("stale source observation")
        items=data["items"]
        if not isinstance(items,list) or not 1<=len(items)<=21:raise ManualContextError("invalid result size")
        seen=set()
        for r in items:
            _keys(r,{"deal_id","procurement_number","workflow_status","updated_at",
                "recorded_decision","recommendation","submission","outcome","current_legal_status"})
            ref(r["deal_id"])
            if r["deal_id"] not in policy["deal_ids"] or r["deal_id"] in seen:
                raise ManualContextError("unexpected identity")
            seen.add(r["deal_id"])
            if (r["procurement_number"] is not None and not match(r["procurement_number"],r"[0-9]{11}|[0-9]{19}")
                or r["workflow_status"] not in WORKFLOW or r["current_legal_status"]!="unknown"
                or stamp(r["updated_at"])>observed):
                raise ManualContextError("invalid workflow metadata")
            for name in ("recorded_decision","recommendation","submission","outcome"):
                e=r[name]
                if e is None:continue
                fields={
                    "recorded_decision":{"ref","code","value","actor_type","actor_reference_present","at","owner_approval_verified"},
                    "recommendation":{"ref","source","value","at"},
                    "submission":{"ref","source","at","external_submission_verified"},
                    "outcome":{"ref","code","at","artifact_ref","external_outcome_verified"},
                }[name]
                _keys(e,fields);ref(e["ref"])
                if stamp(e["at"])>observed:raise ManualContextError("future evidence")
                if name=="recorded_decision":
                    if (e["code"] not in DECISION_CODES or e["value"] not in BID
                        or e["actor_type"] not in ("HUMAN","AGENT","SYSTEM","MODULE","UNKNOWN")
                        or type(e["actor_reference_present"]) is not bool or e["owner_approval_verified"] is not False):
                        raise ManualContextError("decision semantics mismatch")
                elif name=="recommendation":
                    if e["source"]!="AGENT_SCREENING" or e["value"] not in BID:
                        raise ManualContextError("recommendation mismatch")
                elif name=="submission":
                    if e["source"]!="RECORDED_SUBMISSION_EVENT" or e["external_submission_verified"] is not False:
                        raise ManualContextError("submission mismatch")
                else:
                    if e["code"] not in ("WON","LOST","REJECTED","CANCELLED","UNKNOWN") or e["external_outcome_verified"] is not False:
                        raise ManualContextError("outcome mismatch")
                    if e["artifact_ref"] is not None:ref(e["artifact_ref"])
        if seen!=set(policy["deal_ids"]):raise ManualContextError("incomplete admitted identity set")
        return {"schema":"arvectum.workspace.internal-procurement-reference/1",
                "source_release":data["source_release"],"observed_at":data["observed_at"],
                "project_id":policy["project_id"],"coverage":data["coverage"],
                "items":sorted(items,key=lambda r:r["deal_id"]),"canonical_authority":False}
    except (ValueError,TypeError,KeyError,AttributeError,RecursionError) as exc:
        raise ManualContextError("source result rejected") from exc


def fetch_source(token):
    """No redirects, arbitrary URL, browser headers, proxies or shared credentials."""
    conn=http.client.HTTPConnection("127.0.0.1",8001,timeout=5)
    try:
        conn.request("GET",SOURCE_PATH,headers={"Authorization":"Bearer "+token,"Accept":"application/json"})
        r=conn.getresponse()
        if r.status!=200 or r.getheader("Content-Encoding") not in (None,"identity") or (
            r.getheader("Content-Type") or "").split(";",1)[0].strip().lower()!="application/json":
            raise ManualContextError("source unavailable")
        raw=r.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ManualContextError("source too large")
        return raw
    finally:conn.close()


class RuntimeProcurementReference:
    def __init__(self, root, *, clock=lambda:datetime.now(timezone.utc)):
        self.root=Path(root)
        self.manual=RuntimeManualPilot(self.root)
        self.clock=clock

    def _gate(self,access):
        try:
            if self.root.resolve()!=self.root:raise ManualContextError("unsafe runtime root")
            receipt=json.loads(_private_file(self.root/"config"/"procurement-reference-activation.json"))
            _keys(receipt,{"schema","draft_blob","policy_sha256"})
            raw=_private_file(self.root/"config"/"procurement-reference-policy.json")
            if (receipt["schema"]!="arvectum.workspace.procurement-reference-activation/1"
                or receipt["draft_blob"]!=DRAFT or receipt["policy_sha256"]!=sha(raw)):
                raise ManualContextError("activation pin mismatch")
            p=json.loads(raw)
            _keys(p,{"schema","draft_blob","scope","credential_id","grant_id","purpose","binding_id",
                "source_release","database_binding","deal_ids","project_id","starts_at","expires_at","source_credential_sha256"})
            if (p["schema"]!="arvectum.workspace.procurement-reference-policy/1" or p["draft_blob"]!=DRAFT
                or p["scope"]!=_identity(access) or p["credential_id"]!=access.credential_id
                or p["purpose"]!="owner-triggered-internal-procurement-read"):
                raise ManualContextError("policy scope mismatch")
            _id(p["credential_id"]);_id(p["grant_id"]);_id(p["project_id"],"PRJ-");ref(p["binding_id"])
            if not match(p["source_release"],r"[a-f0-9]{40}") or not match(p["database_binding"],r"[a-f0-9]{64}"):
                raise ManualContextError("source pins invalid")
            ids=p["deal_ids"]
            if not isinstance(ids,list) or not 1<=len(ids)<=21 or any(not match(i,r"DL-[A-Za-z0-9-]{1,60}") for i in ids) or len(set(ids))!=len(ids):
                raise ManualContextError("invalid admitted identifiers")
            start,end=stamp(p["starts_at"]),stamp(p["expires_at"])
            if not start<=self.clock()<end<=MAX_EXPIRY or end-start>timedelta(days=30):
                raise ManualContextError("policy expired")
            if end>stamp(self.manual.review_signal(access)["due_at"]):
                raise ManualContextError("pilot deadline exceeded")
            store=self.manual.authorize_operation(access,"read")
            if p["project_id"] not in {r["id"] for r in store.read(access)["projects"]}:
                raise ManualContextError("project binding missing")
            decision=p704.authorize_from_credential_file(self.root,organization=access.organization,principal=access.actor,
                credential_id=access.credential_id,credential_file=self.root/"secrets"/"p7-04"/(access.credential_id+".secret"),
                operation=OPERATION,resource=RESOURCE,access_path="local")
            if not decision.allowed or decision.principal_kind!="human" or decision.grant_id!=p["grant_id"]:
                raise ManualContextError("exact local read grant unavailable")
            token=_private_file(self.root/"secrets"/"procurement-reference.secret")
            if not match(p["source_credential_sha256"],r"[a-f0-9]{64}") or not hmac.compare_digest(sha(token),p["source_credential_sha256"]):
                raise ManualContextError("source credential pin invalid")
            value=token.decode("ascii")
            if not match(value,r"[a-f0-9]{64}"):raise ManualContextError("source credential invalid")
            return p,value,sha(raw)
        except (OSError,ValueError,TypeError,KeyError,AttributeError,RecursionError,p704.P704Error) as exc:
            raise ManualContextError("procurement reference not admitted") from exc

    def read(self,authorize):
        a=authorize()
        p,token,pin=self._gate(a)
        started=self.clock()
        raw=fetch_source(token)
        finished=self.clock()
        a=authorize()
        _,_,current=self._gate(a)
        if current!=pin:raise ManualContextError("admission changed during request")
        return validate_source(raw,p,started,finished)
