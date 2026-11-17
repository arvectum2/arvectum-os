"""Bounded read-only first Company control; independently admitted exact source."""
from datetime import datetime,timedelta,timezone
import hashlib,json,os,stat,re
from pathlib import Path
import p7_04_persistent_access as p704
from .wsf_manual_context import ManualContextError,_identity,_id,_keys
from .wsf_manual_policy import _private_file
from .wsf_manual_runtime import RuntimeManualPilot
from .wsf_control_projection import project_controls,stamp

DRAFT="249b7b290eb573a6fd0721dbd6459102f376ca3b"
OPERATION="workspace.company_control.read"
RESOURCE="company-control-reference"
EXPIRY=stamp("2026-12-17T09:35:36.060836+00:00")
def sha(raw):return hashlib.sha256(raw).hexdigest()

def read_snapshot(path):
    for directory in (path.parent,path.parent.parent):
        s=directory.lstat()
        if directory.resolve()!=directory or not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode&0o077:
            raise ManualContextError("Company source directory unsafe")
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,"rb") as f:
        s=os.fstat(f.fileno())
        if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode&0o077 or s.st_nlink!=1:
            raise ManualContextError("Company source unsafe")
        raw=f.read(2*1024*1024+1)
    if len(raw)>2*1024*1024:raise ManualContextError("Company source too large")
    return raw

class CompanyControlReference:
    def __init__(self,root,*,clock=lambda:datetime.now(timezone.utc)):
        self.root=Path(root)
        self.manual=RuntimeManualPilot(self.root)
        self.clock=clock
        self.source=Path.home()/"Library/Application Support/ArvectumCompany/control-register/register.json"
    def gate(self,a):
        raw=_private_file(self.root/"config/company-control-policy.json")
        receipt=json.loads(_private_file(self.root/"config/company-control-activation.json"))
        _keys(receipt,{"schema","draft_blob","policy_sha256"})
        if receipt!={"schema":"arvectum.workspace.company-control-activation/1","draft_blob":DRAFT,"policy_sha256":sha(raw)}:raise ManualContextError("receipt mismatch")
        p=json.loads(raw)
        _keys(p,{"schema","draft_blob","scope","credential_id","grant_id","purpose","source_sha256","record_id","position","starts_at","expires_at"})
        if (p["schema"]!="arvectum.workspace.company-control-policy/1" or p["draft_blob"]!=DRAFT or p["scope"]!=_identity(a) or p["credential_id"]!=a.credential_id or p["purpose"]!="owner-triggered-first-company-control-read" or p["record_id"]!="WORK-001" or p["position"]!="POS-001" or not re.fullmatch("[a-f0-9]{64}",p["source_sha256"])):
            raise ManualContextError("policy mismatch")
        _id(p["credential_id"]);_id(p["grant_id"])
        start,end=stamp(p["starts_at"]),stamp(p["expires_at"])
        if not start<=self.clock()<end<=EXPIRY or end-start>timedelta(days=30):raise ManualContextError("admission expired")
        review=self.manual.review_signal(a)
        if end>stamp(review["due_at"]):raise ManualContextError("manual pilot deadline")
        decision=p704.authorize_from_credential_file(self.root,organization=a.organization,principal=a.actor,credential_id=a.credential_id,credential_file=self.root/"secrets/p7-04"/(a.credential_id+".secret"),operation=OPERATION,resource=RESOURCE,access_path="local")
        if not decision.allowed or decision.principal_kind!="human" or decision.grant_id!=p["grant_id"]:raise ManualContextError("grant denied")
        return p,sha(raw),review
    def read(self,authorize):
        try:
            a=authorize();p,pin,review=self.gate(a)
            raw=read_snapshot(self.source)
            if sha(raw)!=p["source_sha256"]:raise ManualContextError("source changed")
            d=json.loads(raw)
            _keys(d,{"schema","coverage","events"})
            if d["schema"]!="arvectum.company.work-obligation-register/1" or d["coverage"]!="partial" or len(d["events"])!=1:raise ManualContextError("exact initial source revision required")
            e=d["events"][0]
            _keys(e,{"sequence","prior_digest","at","authority_ref","reason","record"})
            r=e["record"]
            if e["sequence"]!=1 or e["prior_digest"] is not None or r["id"]!=p["record_id"] or r["accountable_position"]!=p["position"] or r["kind"]!="work" or r["concern_key"]!="workspace-pilot-continuation-review-2026-12" or r["control_state"]!="open" or r["due_or_trigger"]["kind"]!="exact" or stamp(r["due_or_trigger"]["value"])!=stamp(review["due_at"]):raise ManualContextError("record mismatch")
            now=self.clock().isoformat()
            if stamp(e["at"])>stamp(now):raise ManualContextError("future evidence")
            row={"id":r["id"],"title":r["title"],"accountable_position":r["accountable_position"],"scope_refs":r["scope_refs"],"source_refs":r["source_refs"],"evidence_as_of":r["evidence_as_of"],"freshness":"current_for_declared_use","review_condition":"Revalidate pilot and actual owner use before expiry","control_state":r["control_state"],"priority":r["company_priority"]["level"],"next_control_point":r["next_control_point"],"due_or_trigger":r["due_or_trigger"],"owner_action":"required_by_trigger","material_consequence":"Current internal pilot expires; continuation decision remains open","substantive_unknowns":["Genuine owner daily use and full Company coverage not established"],"decision_card":None}
            result=project_controls(a,{"scope":_identity(a),"source_ref":"Company AC-401","as_of":now,"coverage":"partial","records":[row]},admitted_scope=p["scope"],admitted_positions={p["position"]},now=now)
            a=authorize();_,after,review_after=self.gate(a)
            if after!=pin or review_after!=review or read_snapshot(self.source)!=raw:raise ManualContextError("source or authorization changed")
            return result
        except (OSError,ValueError,TypeError,KeyError,AttributeError,RecursionError,p704.P704Error) as exc:raise ManualContextError("Company control reference unavailable") from exc
