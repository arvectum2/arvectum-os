"""Proposed exact two-work successor to active 0.5.5; no authority by itself."""
import json,re
from dataclasses import dataclass
from .wsf_company_control_reference import sha,BINDINGS
from .wsf_control_projection import stamp,project_controls
from .wsf_manual_context import ManualContextError,_json,_keys,_identity

ADDITIONS={"WORK-002":("POS-002","baltika-procurement-discovery-disposition"),
           "WORK-003":("POS-005","management-finance-evidence-completeness")}
STEPS=("source_first","backup_first","source_second","backup_second","policy","receipt")
WORK_FIELDS=set("id kind concern_key title control_summary accountable_position scope_refs company_priority control_state attention_state due_or_trigger next_control_point source_refs evidence_as_of escalation_need classification_handling last_reviewed_at closure_ref bounded_outcome completion_or_stop_condition execution_refs".split())

@dataclass(frozen=True)
class MaterialPlan:
    predecessor:str
    intermediate:str
    successor:str
    previous_plan:str
    old_policy:str
    old_receipt:str
    policy:str
    receipt:str
    decision:str
    contract:str
    steps=STEPS

    def __post_init__(self):
        for name in ("predecessor","intermediate","successor","previous_plan","old_policy","old_receipt","policy","receipt"):
            if not isinstance(getattr(self,name),str) or not re.fullmatch(r"[a-f0-9]{64}",getattr(self,name)):
                raise ManualContextError("invalid exact digest")
        if len({self.predecessor,self.intermediate,self.successor})!=3:
            raise ManualContextError("distinct source revisions required")
        if not isinstance(self.contract,str) or not re.fullmatch(r"[a-f0-9]{40}",self.contract):
            raise ManualContextError("invalid publication pin")
        if not isinstance(self.decision,str) or not re.fullmatch(r"OWNER-[A-Z0-9-]{4,154}",self.decision):
            raise ManualContextError("invalid decision reference")

    def journal(self):
        return _json({"schema":"arvectum.workspace.ac401-material-cutover/1",**self.__dict__})

    def phase(self,observed):
        if not isinstance(observed,dict) or set(observed)!={"source","backup","policy","receipt"}:
            raise ManualContextError("invalid observation")
        a,b,c=self.predecessor,self.intermediate,self.successor
        states=[(a,a,None,None),(b,a,None,None),(b,b,None,None),
                (c,b,None,None),(c,c,None,None),(c,c,self.policy,None),(c,c,self.policy,self.receipt)]
        value=tuple(observed[k] for k in ("source","backup","policy","receipt"))
        try:return states.index(value)
        except ValueError:raise ManualContextError("unexpected partial state") from None

def material_rows(base_rows,old_raw,mid_raw,new_raw,*,plan,now):
    """The caller independently verifies the previously admitted base projection.
    Exact snapshots must independently pass the full Company replay before writes.
    """
    try:
        for raw,pin in zip((old_raw,mid_raw,new_raw),(plan.predecessor,plan.intermediate,plan.successor)):
            if type(raw) is not bytes or len(raw)>2*1024*1024 or sha(raw)!=pin:
                raise ManualContextError("snapshot pin")
        docs=[json.loads(raw) for raw in (old_raw,mid_raw,new_raw)]
        for n,d in enumerate(docs,4):
            _keys(d,{"schema","coverage","events"})
            if d["schema"]!="arvectum.company.work-obligation-register/1" or d["coverage"]!="partial" or len(d["events"])!=n:
                raise ManualContextError("snapshot shape")
        if docs[1]["events"][:4]!=docs[0]["events"] or docs[2]["events"][:5]!=docs[1]["events"]:
            raise ManualContextError("history changed")
        if {r["id"]:r["accountable_position"] for r in base_rows}!=BINDINGS or len(base_rows)!=3:
            raise ManualContextError("predecessor projection")
        rows=list(base_rows)
        concerns={e["record"]["concern_key"] for e in docs[0]["events"]}
        for n,(rid,(pos,key)) in enumerate(ADDITIONS.items(),5):
            event=docs[2]["events"][n-1];previous=docs[2]["events"][n-2]
            _keys(event,{"sequence","prior_digest","at","authority_ref","reason","record"})
            if (type(event["sequence"]) is not int or event["sequence"]!=n
                or event["prior_digest"]!=sha(_json(previous)+b"\n") or event["authority_ref"]!=plan.decision
                or not isinstance(event["reason"],str) or not event["reason"].strip()
                or not stamp(previous["at"])<=stamp(event["at"])<=stamp(now)):
                raise ManualContextError("event provenance")
            r=event["record"];_keys(r,WORK_FIELDS)
            if (r["id"]!=rid or r["kind"]!="work" or r["concern_key"]!=key or key in concerns
                or r["accountable_position"]!=pos or r["control_state"]!="open" or r["attention_state"]!="needs_attention"
                or r["company_priority"]["level"]!="P1" or r["due_or_trigger"]!={"kind":"none","value":None,"source_ref":None}
                or r["closure_ref"] is not None or r["escalation_need"] is not None
                or not stamp(r["evidence_as_of"])<=stamp(r["last_reviewed_at"])<=stamp(event["at"])):
                raise ManualContextError("material scope mismatch")
            concerns.add(key)
            rows.append({"id":rid,"title":r["title"],"accountable_position":pos,
                "scope_refs":r["scope_refs"],"source_refs":r["source_refs"],"evidence_as_of":r["evidence_as_of"],
                "freshness":"unknown","review_condition":"Verify current underlying evidence before advancing",
                "control_state":"open","priority":"P1","next_control_point":r["next_control_point"],
                "due_or_trigger":r["due_or_trigger"],"owner_action":"not_required",
                "material_consequence":"Company-level material work; no new obligation or approval",
                "substantive_unknowns":["Current business outcome and underlying evidence completeness not established"],"decision_card":None})
        return rows
    except (ValueError,TypeError,KeyError,AttributeError,IndexError,RecursionError) as exc:
        raise ManualContextError("invalid material successor") from exc

def project_material(a,p,rows,now):
    result=project_controls(a,{"scope":_identity(a),"source_ref":"Company AC-401",
       "as_of":now,"coverage":"partial","records":rows},admitted_scope=p["scope"],
       admitted_positions=set(BINDINGS.values())|{v[0] for v in ADDITIONS.values()},now=now)
    # A Position's work is not a proven executor Assignment. Do not imply
    # delegation or turn it into a separate Owner-reserved decision.
    result["position_work"]=[r for r in result["delegated_work"] if r["id"] in ADDITIONS]
    result["delegated_work"]=[r for r in result["delegated_work"] if r["id"] not in ADDITIONS]
    return result
