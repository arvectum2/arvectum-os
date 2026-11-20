"""AC-402 bounded, read-only normalized reference. No authority or effect grants."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json,re
import p7_04_persistent_access as p704
from .wsf_manual_context import ManualContextError,_identity,_id,_keys,_json
from .wsf_manual_policy import _private_file
from .wsf_manual_runtime import RuntimeManualPilot
from .wsf_company_control_reference import read_snapshot,sha
from .wsf_control_projection import stamp

DRAFT="d9e0c691d730327df50c872ca52f8bf2326de47d"
OPERATION="workspace.company_decision.read"
RESOURCE="company-decision-reference"
IDS=("DEC-001","DEC-002","DEC-003","APR-001")
EXPIRY=stamp("2026-12-17T09:35:36.060836+00:00")
def bounded(v):
    if not isinstance(v,str) or not v.strip() or len(v)>4000:raise ManualContextError("invalid reference text")
    return v

def projection(doc,review,now):
    _keys(doc,{"schema","coverage","events"})
    if doc["schema"]!="arvectum.company.decision-approval-escalation-register/1" or doc["coverage"]!="partial" or not isinstance(doc["events"],list) or len(doc["events"])!=4:raise ManualContextError("unexpected source revision")
    rows=[];prior=None;last=None
    for n,e in enumerate(doc["events"],1):
        _keys(e,{"sequence","prior_digest","at","operator_ref","reason","concern_key","record"})
        t=stamp(e["at"])
        if e["sequence"]!=n or e["prior_digest"]!=prior or t>stamp(now) or (last is not None and t<last):raise ManualContextError("revision chain mismatch")
        last=t;prior=sha(_json(e)+b"\n")
        r=e["record"];rid=r["id"]
        if rid!=IDS[n-1] or stamp(r["last_reviewed_at"])>t or stamp(r["evidence_as_of"])>stamp(r["last_reviewed_at"]):raise ManualContextError("identity or time mismatch")
        if n<4:
            pending=n==3
            if r["decision_state"]!=("preparing" if pending else "decided") or r["decision_outcome"]!=("none" if pending else "approve_with_conditions") or r["accountable_position"]!="POS-001" or r["decision_authority"]!="Owner" or r["effect_readiness"]!=("blocked" if pending else "not_applicable"):raise ManualContextError("decision semantics mismatch")
            if pending:
                if r["decision_act_ref"] is not None or r["effective_at"] is not None or "WORK-001" not in r["scope_refs"] or r["review_expiry_trigger"]!="До "+review["due_at"]:raise ManualContextError("review trigger mismatch")
            elif not bounded(r["decision_act_ref"]):raise ManualContextError("act absent")
            rows.append({"id":rid,"kind":"decision","title":bounded(r["title"]),"question":bounded(r["decision_question"]),"position":r["accountable_position"],"capacity":r["decision_authority"],"authority_basis":bounded(r["authority_basis"]),"recorded_state":r["decision_state"],"recorded_outcome":r["decision_outcome"],"act_ref":r["decision_act_ref"],"constraints":bounded(r["constraints_excluded_effects"]),"review_trigger":bounded(r["review_expiry_trigger"]),"review_due_at":review["due_at"] if pending else None,"linked_work":"WORK-001" if pending else None,"decision_ready":False,"current_applicability":"unknown"})
        else:
            if r["approval_state"]!="approved" or r["approval_domain"]!="arvectum_os" or r["required_approver_capacity"]!="Owner" or r["approval_act_ref"]!=r["authoritative_source_ref"]:raise ManualContextError("approval reference mismatch")
            rows.append({"id":rid,"kind":"approval","title":bounded(r["title"]),"domain":r["approval_domain"],"capacity":r["required_approver_capacity"],"authority_basis":bounded(r["authority_basis"]),"recorded_state":r["approval_state"],"act_ref":bounded(r["approval_act_ref"]),"scope":bounded(r["approval_scope"]),"constraints":bounded(r["conditions_excluded_effects"]),"effective_period":bounded(r["effective_period"]),"decision_ready":False,"current_applicability":"unknown"})
    return {"schema":"arvectum.workspace.company-decision-reference/1","coverage":"partial","derived":True,"canonical_authority":False,"organizational_authority_provided":False,"items":rows,"as_of":now}

class DecisionReference:
    def __init__(self,root,*,clock=lambda:datetime.now(timezone.utc)):
        self.root=Path(root);self.clock=clock;self.manual=RuntimeManualPilot(self.root)
        self.source=Path.home()/"Library/Application Support/ArvectumCompany/decision-register/register.json"
    def gate(self,a):
        raw=_private_file(self.root/"config/company-decision-policy.json")
        receipt=json.loads(_private_file(self.root/"config/company-decision-activation.json"))
        if receipt!={"schema":"arvectum.workspace.company-decision-activation/1","draft_blob":DRAFT,"policy_sha256":sha(raw)}:raise ManualContextError("receipt mismatch")
        p=json.loads(raw)
        _keys(p,{"schema","draft_blob","scope","credential_id","grant_id","purpose","source_sha256","record_ids","starts_at","expires_at"})
        if p["schema"]!="arvectum.workspace.company-decision-policy/1" or p["draft_blob"]!=DRAFT or p["scope"]!=_identity(a) or p["credential_id"]!=a.credential_id or p["purpose"]!="owner-triggered-first-decision-reference-read" or p["record_ids"]!=list(IDS) or not re.fullmatch("[a-f0-9]{64}",p["source_sha256"]):raise ManualContextError("policy mismatch")
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
            from .wsf_local_control import enabled,read_local
            if enabled(self.root):return read_local(self,authorize,'decision')
            a=authorize();p,pin,review=self.gate(a)
            raw=read_snapshot(self.source)
            if sha(raw)!=p["source_sha256"]:raise ManualContextError("source changed")
            result=projection(json.loads(raw),review,self.clock().isoformat())
            _,after,review2=self.gate(authorize())
            if after!=pin or review2!=review or read_snapshot(self.source)!=raw:raise ManualContextError("source or access changed")
            return result
        except (OSError,ValueError,TypeError,KeyError,AttributeError,RecursionError,p704.P704Error) as exc:raise ManualContextError("decision reference unavailable") from exc
