"""AC-403 bounded, read-only normalized reference. No authority or effect grants."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json,re
import p7_04_persistent_access as p704
from .wsf_manual_context import ManualContextError,_identity,_id,_keys,_json
from .wsf_manual_policy import _private_file
from .wsf_manual_runtime import RuntimeManualPilot
from .wsf_company_control_reference import read_snapshot,sha
from .wsf_control_projection import stamp

DRAFT="46e76250a2fcbbde3cfab5098326d1886fc16f5c"
OPERATION="workspace.company_risk.read"
RESOURCE="company-risk-reference"
IDS=("RSK-001","RSK-002","RSK-003")
POSITIONS={"RSK-001":"POS-006","RSK-002":"POS-004","RSK-003":"POS-002"}
EXPIRY=stamp("2026-12-17T09:35:36.060836+00:00")
def bounded(v):
    if not isinstance(v,str) or not v.strip() or len(v)>4000:raise ManualContextError("invalid reference text")
    return v

def projection(doc,review,now):
    _keys(doc,{"schema","coverage","events"})
    if doc["schema"]!="arvectum.company.risk-exception-incident-register/1" or doc["coverage"]!="partial" or not isinstance(doc["events"],list) or len(doc["events"])!=4:raise ManualContextError("unexpected source revision")
    rows={};prior=None;last=None;concerns={}
    for n,e in enumerate(doc["events"],1):
        _keys(e,{"sequence","prior_digest","at","operator_ref","reason","concern_key","record"})
        t=stamp(e["at"])
        if type(e["sequence"]) is not int or e["sequence"]!=n or e["prior_digest"]!=prior or t>stamp(now) or (last is not None and t<last):raise ManualContextError("revision chain mismatch")
        prior=sha(_json(e)+b"\n");last=t;r=e["record"];rid=r["id"]
        if rid!=(*IDS,"RSK-001")[n-1] or r["kind"]!="risk" or r["accountable_position"]!=POSITIONS[rid] or r["risk_state"]!="active" or r["response_intent"]!="reduce" or r["risk_acceptance_decision_ref"] is not None or r["owner_attention"]!="not_required" or stamp(r["evidence_as_of"])>stamp(r["last_reviewed_at"]) or stamp(r["last_reviewed_at"])>t or r["closure_ref"] is not None:raise ManualContextError("risk semantics mismatch")
        key=bounded(e["concern_key"])
        if rid in concerns and concerns[rid]!=key:raise ManualContextError("identity mismatch")
        concerns[rid]=key
        priority=r["company_priority"]["level"]
        if priority!=("P0" if rid=="RSK-003" else "P1"):raise ManualContextError("priority mismatch")
        for k in ("source_refs","treatment_work_refs"):
            if not isinstance(r[k],list) or len(r[k])>24 or not r[k]:raise ManualContextError("invalid refs")
            for x in r[k]:bounded(x)
        if r["likelihood_evidence"]!="unknown":raise ManualContextError("unreviewed likelihood")
        rows[rid]={"id":rid,"title":bounded(r["title"]),"position":r["accountable_position"],"priority":priority,"recorded_state":"active","response_intent":"reduce","risk_accepted":False,"owner_attention":"not_required","current_applicability":"unknown","likelihood":"unknown","risk_statement":bounded(r["risk_statement"]),"residual_exposure":bounded(r["residual_exposure"]),"control_evidence":bounded(r["control_evidence_state"]),"next_control_point":bounded(r["next_control_point"]),"review_trigger":bounded(r["review_trigger"]),"source_refs":r["source_refs"],"linked_work":r["treatment_work_refs"]}
    if set(rows)!=set(IDS) or len(set(concerns.values()))!=3:raise ManualContextError("risk scope mismatch")
    return {"schema":"arvectum.workspace.company-risk-reference/1","coverage":"partial","derived":True,"canonical_authority":False,"organizational_authority_provided":False,"items":[rows[x] for x in IDS],"as_of":now}

class RiskReference:
    def __init__(self,root,*,clock=lambda:datetime.now(timezone.utc)):
        self.root=Path(root);self.clock=clock;self.manual=RuntimeManualPilot(self.root)
        self.source=Path.home()/"Library/Application Support/ArvectumCompany/risk-register/register.json"
    def gate(self,a):
        raw=_private_file(self.root/"config/company-risk-policy.json")
        receipt=json.loads(_private_file(self.root/"config/company-risk-activation.json"))
        if receipt!={"schema":"arvectum.workspace.company-risk-activation/1","draft_blob":DRAFT,"policy_sha256":sha(raw)}:raise ManualContextError("receipt mismatch")
        p=json.loads(raw)
        _keys(p,{"schema","draft_blob","scope","credential_id","grant_id","purpose","source_sha256","record_ids","starts_at","expires_at"})
        if p["schema"]!="arvectum.workspace.company-risk-policy/1" or p["draft_blob"]!=DRAFT or p["scope"]!=_identity(a) or p["credential_id"]!=a.credential_id or p["purpose"]!="owner-triggered-first-risk-reference-read" or p["record_ids"]!=list(IDS) or not re.fullmatch("[a-f0-9]{64}",p["source_sha256"]):raise ManualContextError("policy mismatch")
        _id(p["credential_id"]);_id(p["grant_id"])
        start,end=stamp(p["starts_at"]),stamp(p["expires_at"])
        if not start<=self.clock()<end<=EXPIRY or end-start>timedelta(days=30):raise ManualContextError("expired")
        review=self.manual.review_signal(a)
        if end>stamp(review["due_at"]):raise ManualContextError("pilot expired")
        d=p704.authorize_from_credential_file(self.root,organization=a.organization,principal=a.actor,credential_id=a.credential_id,credential_file=self.root/"secrets/p7-04"/(a.credential_id+".secret"),operation=OPERATION,resource=RESOURCE,access_path="local")
        if not d.allowed or d.principal_kind!="human" or d.grant_id!=p["grant_id"]:raise ManualContextError("grant denied")
        return p,sha(raw),review
    def read(self,authorize):
        try:
            a=authorize();p,pin,review=self.gate(a)
            raw=read_snapshot(self.source)
            if sha(raw)!=p["source_sha256"]:raise ManualContextError("source changed")
            result=projection(json.loads(raw),review,self.clock().isoformat())
            _,after,review2=self.gate(authorize())
            if after!=pin or review2!=review or read_snapshot(self.source)!=raw:raise ManualContextError("source or access changed")
            return result
        except (OSError,ValueError,TypeError,KeyError,AttributeError,RecursionError,p704.P704Error) as exc:raise ManualContextError("decision reference unavailable") from exc
