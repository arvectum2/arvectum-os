"""Dormant exact second admission. No publication or authority is created here."""
from hashlib import sha1
from pathlib import Path
import json
from .wsf_company_control_admission import (Admission,DiskCutover,load_plan,exists,
    write_atomic,JOURNAL as PREVIOUS_JOURNAL)
from .wsf_company_control_material import MaterialPlan,ADDITIONS,material_rows,project_material
from .wsf_company_control_reference import sha,read_snapshot,BINDINGS
from .wsf_manual_context import ManualContextError,_json
from .wsf_manual_policy import _private_file

PUBLICATION='c95048e0ba0d797214c64d28ebfea5db43d100f7'
APPROVED_PLAN_SHA='163f49d3b0eadbff70296ede8a5c851746f4ea7300c6d3f68b2c66e8c650bdb7'
PUBLICATION_PATH="ac401-material-approved-publication.md"
PREFIX="company-control-material"
JOURNAL=PREFIX+"-cutover.json"

def load_material_plan(root):
    if PUBLICATION is None or APPROVED_PLAN_SHA is None:
        raise ManualContextError("material successor not published")
    raw=(Path(__file__).resolve().parent/PUBLICATION_PATH).read_bytes()
    if sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()!=PUBLICATION:
        raise ManualContextError("material publication mismatch")
    try:raw=_private_file(root/"config"/(PREFIX+"-approved.json"))
    except FileNotFoundError:raise ManualContextError("material approval not staged") from None
    if sha(raw)!=APPROVED_PLAN_SHA:raise ManualContextError("material approval mismatch")
    p=MaterialPlan(**json.loads(raw))
    if p.contract!=PUBLICATION:raise ManualContextError("material contract mismatch")
    return p

def policy_bytes(p,plan):
    return _json({"schema":"arvectum.workspace.ac401-material-policy/1",
       "scope":p["scope"],"credential_id":p["credential_id"],"grant_id":p["grant_id"],
       "starts_at":p["starts_at"],"expires_at":p["expires_at"],
       "records":{**BINDINGS,**{k:v[0] for k,v in ADDITIONS.items()}},
       "predecessor":plan.predecessor,"intermediate":plan.intermediate,
       "source_sha256":plan.successor,"previous_plan":plan.previous_plan,
       "old_policy":plan.old_policy,"contract":plan.contract,"decision":plan.decision})

def receipt_bytes(plan):
    return _json({"schema":"arvectum.workspace.ac401-material-receipt/1",
                  "policy_sha256":plan.policy,"decision":plan.decision,"contract":plan.contract})

class MaterialAdmission(DiskCutover):
    def __init__(self,runtime,authorize,company=None,maintenance=None):
        super().__init__(runtime,authorize,company,maintenance)
        self.previous=Admission(runtime,authorize)
        self.archive=self.source.parent/"material-work-review"
        self.policy=self.config/(PREFIX+"-policy.json")
        self.receipt=self.config/(PREFIX+"-activation.json")
        self.journal=self.config/JOURNAL

    def check(self,plan):
        if exists(self.config/PREVIOUS_JOURNAL) or load_material_plan(self.root)!=plan:
            raise ManualContextError("material approval unavailable")
        prior=load_plan(self.root)
        if (sha(_private_file(self.config/"company-control-successor-approved.json"))!=plan.previous_plan
            or prior.successor!=plan.predecessor or prior.policy!=plan.old_policy or prior.receipt!=plan.old_receipt
            or sha(_private_file(self.previous.policy))!=plan.old_policy
            or sha(_private_file(self.previous.receipt))!=plan.old_receipt):
            raise ManualContextError("previous approval changed")
        a,p,base,_,previous_source=self.previous.check(prior)
        old,mid,new=(read_snapshot(self.archive/name) for name in
                     ("predecessor.private.json","intermediate.private.json","successor.private.json"))
        if previous_source!=old or sha(policy_bytes(p,plan))!=plan.policy or sha(receipt_bytes(plan))!=plan.receipt:
            raise ManualContextError("material admission mismatch")
        rows=material_rows(base,old,mid,new,plan=plan,now=self.runtime.clock().isoformat())
        return a,p,rows,old,mid,new

    def preflight(self,plan):
        if self.quiet is None or len(self.writers)!=2:raise ManualContextError("maintenance required")
        self.quiet();self.check_destination()
        a,p,rows,*raws=self.check(plan)
        project_material(a,p,rows,self.runtime.clock().isoformat())
        for raw in raws:
            doc=json.loads(raw);self.company.replay(doc)
            if self.company.canonical(doc)!=raw:raise ManualContextError("Company format")

    def write(self,step,plan):
        self.preflight(plan)
        _,p,_,old,mid,new=self.check(plan)
        if step in plan.steps[:4]:
            name,stage=step.split("_")
            predecessor,successor=(old,mid) if stage=="first" else (mid,new)
            self.writers[name](json.loads(successor),expected_digest=sha(predecessor))
            self.check_destination()
        elif step=="policy":write_atomic(self.policy,policy_bytes(p,plan))
        elif step=="receipt":write_atomic(self.receipt,receipt_bytes(plan))
        else:raise ManualContextError("unknown write")

    def verify_final(self,plan):
        self.preflight(plan);self.project(plan,internal=True)

    def project(self,plan,*,internal=False):
        if not internal and exists(self.journal):raise ManualContextError("material cutover incomplete")
        a,p,rows,*_=self.check(plan)
        if plan.phase(self.observe())!=len(plan.steps):raise ManualContextError("material successor unavailable")
        result=project_material(a,p,rows,self.runtime.clock().isoformat())
        self.check(plan)
        if plan.phase(self.observe())!=len(plan.steps) or (not internal and exists(self.journal)):
            raise ManualContextError("material state changed")
        return result

def selected_material(runtime,authorize):
    cfg=runtime.root/"config"
    if exists(cfg/JOURNAL):raise ManualContextError("material transition incomplete")
    if any(exists(cfg/(PREFIX+s)) for s in ("-policy.json","-activation.json")):
        return MaterialAdmission(runtime,authorize).project(load_material_plan(runtime.root))
    return None
