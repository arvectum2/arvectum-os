"""Bounded single-owner local read admission. No write API or new authority.
Same trusted Mac/user boundary as existing Workspace, not hostile-admin isolation.
"""
from pathlib import Path
from types import SimpleNamespace
from hashlib import sha1
import json
from .wsf_manual_context import ManualContextError,_json
from .wsf_manual_backup import PilotBackup
from .wsf_company_control_reference import read_snapshot,sha
from .wsf_control_projection import stamp

# Approval of this standing read policy is separate from candidate development.
PUBLICATION="5863ad8ef2b970456073f53746a96a5494f44e3d"
PUBLICATION_PATH="ac402-403-local-publication.md"
ACTS={
 "DEC-004":"DECISION-2026-11-20-AC401-WORK001-SUCCESSOR",
 "DEC-005":"DECISION-2026-11-20-AC401-MATERIAL-WORK-002-003"}
COMPANY_COMMIT="da51e6a1bb44bce282270ea0d88c72e3c07d1d6b"
RISK_FIELDS={"source_refs","current_controls_refs","control_evidence_state","residual_exposure",
 "next_control_point","review_trigger","evidence_as_of","last_reviewed_at"}

def need(value,msg):
    if not value:raise ManualContextError(msg)

def enabled(root):
    if PUBLICATION is None:return False
    raw=(Path(__file__).resolve().parent/PUBLICATION_PATH).read_bytes()
    need(sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()==PUBLICATION,"publication mismatch")
    from .wsf_manual_policy import _private_file
    try:receipt=json.loads(_private_file(Path(root)/'config/ac402-403-local-activation.json'))
    except FileNotFoundError:return False
    need(receipt=={'schema':'arvectum.workspace.local-control-activation/1','publication':PUBLICATION,'owner_act':'edc59e48b1788859e275907d3d6749b7a88e1da6'},'local receipt mismatch')
    return True

def validate(raw,pin,kind,now):
    doc=json.loads(raw)
    schema={"decision":"decision-approval-escalation","risk":"risk-exception-incident"}[kind]
    need(set(doc)=={"schema","coverage","events"} and doc["schema"]=="arvectum.company."+schema+"-register/1"
         and doc["coverage"]=="partial" and isinstance(doc["events"],list)
         and _json(doc)+b"\n"==raw,"noncanonical source")
    events=doc["events"]
    need(4<=len(events)<=(6 if kind=="decision" else 128),"bounded history")
    base={**doc,"events":events[:4]}
    need(sha(_json(base)+b"\n")==pin,"original admitted history changed")
    old={e["record"]["id"]:e["record"] for e in events[:4]}
    concern={e["record"]["id"]:e["concern_key"] for e in events[:4]}
    prior=sha(_json(events[3])+b"\n");last=stamp(events[3]["at"])
    for n,e in enumerate(events[4:],5):
        need(set(e)=={"sequence","prior_digest","at","operator_ref","reason","concern_key","record"}
             and type(e["sequence"]) is int and e["sequence"]==n and e["prior_digest"]==prior
             and last<=stamp(e["at"])<=stamp(now),"history chain")
        r=e["record"];rid=r["id"]
        need(stamp(r["evidence_as_of"])<=stamp(r["last_reviewed_at"])<=stamp(e["at"]),"evidence dates")
        for k in ("operator_ref","reason","concern_key"):
            need(isinstance(e[k],str) and bool(e[k].strip()) and len(e[k])<=4000,"event provenance")
        if kind=="decision":
            rid_expected="DEC-00"+str(n-1)
            ref="arvectum2/arvectum-company@"+COMPANY_COMMIT+":docs/governance/decisions/"+ACTS[rid_expected]+".md"
            need(rid==rid_expected and rid not in old and e["concern_key"] not in concern.values()
                 and set(r)==set(old["DEC-003"]) and r["accountable_position"]=="POS-001"
                 and r["decision_authority"]=="Owner" and r["decision_state"]=="decided"
                 and r["decision_outcome"]=="approve_with_conditions" and r["effect_readiness"]=="blocked"
                 and not r["required_approval_refs"] and r["decision_act_ref"]==ref
                 and r["effective_at"]=="2026-11-20" and ref in r["evidence_refs"],"historical index outside bounds")
        else:
            need(rid=="RSK-002" and e["concern_key"]==concern[rid] and set(r)==set(old[rid]),"risk identity changed")
            before=old[rid]
            changes={k for k in r if r[k]!=before[k]}
            need(bool(changes) and changes<=RISK_FIELDS and stamp(r["last_reviewed_at"])>=stamp(before["last_reviewed_at"]),"risk scope changed")
            for k in ("source_refs","current_controls_refs"):
                need(isinstance(r[k],list) and len(r[k])<=(24 if k=='source_refs' else 128) and all(isinstance(x,str) and x.strip() and len(x)<=4000 for x in r[k])
                     and set(before[k])<=set(r[k]),"provenance loss")
            for k in RISK_FIELDS-{"source_refs","current_controls_refs","evidence_as_of","last_reviewed_at"}:
                need(isinstance(r[k],str) and r[k].strip() and len(r[k])<=4000,"risk text")
        old[rid]=r;concern[rid]=e["concern_key"];prior=sha(_json(e)+b"\n");last=stamp(e["at"])
    return base,old

def project(raw,pin,kind,review,now):
    base,rows=validate(raw,pin,kind,now)
    if kind=="decision":
        from .wsf_decision_reference import projection,bounded
        result=projection(base,review,now)
        for rid in ACTS:
            if rid not in rows:continue
            r=rows[rid]
            result["items"].append({"id":rid,"kind":"decision","title":bounded(r["title"]),
                "question":bounded(r["decision_question"]),"position":"POS-001","capacity":"Owner",
                "authority_basis":bounded(r["authority_basis"]),"recorded_state":"decided",
                "recorded_outcome":"approve_with_conditions","act_ref":r["decision_act_ref"],
                "constraints":bounded(r["constraints_excluded_effects"]),"review_trigger":bounded(r["review_expiry_trigger"]),
                "review_due_at":None,"linked_work":None,"decision_ready":False,"current_applicability":"unknown"})
    else:
        from .wsf_risk_reference import projection,bounded
        result=projection(base,review,now);r=rows["RSK-002"]
        target=next(x for x in result["items"] if x["id"]=="RSK-002")
        for k,field in (("residual_exposure","residual_exposure"),("control_evidence","control_evidence_state"),
           ("next_control_point","next_control_point"),("review_trigger","review_trigger")):
            target[k]=bounded(r[field])
        target["source_refs"]=r["source_refs"]
    return result

def backup_bytes(runtime,kind):
    backup=PilotBackup(SimpleNamespace(directory=runtime.source.parent),
             parts=("Arvectum","backups","arvectum-company",kind+"-register"))
    with backup._destination() as fd:return backup._read(fd)

def read_local(runtime,authorize,kind):
    a=authorize();p,pin,review=runtime.gate(a)
    raw=read_snapshot(runtime.source)
    need(raw==backup_bytes(runtime,kind),"source backup mismatch")
    result=project(raw,p["source_sha256"],kind,review,runtime.clock().isoformat())
    _,after,review2=runtime.gate(authorize())
    need(pin==after and review==review2 and read_snapshot(runtime.source)==raw
         and backup_bytes(runtime,kind)==raw and enabled(runtime.root),"source or access changed")
    return result
