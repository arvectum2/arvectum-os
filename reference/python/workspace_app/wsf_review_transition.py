"""Single append reviewed transition for AC-402/403. Detached candidate only.

Authority backend must provide independently protected current head, live
eligibility, and compare-and-set. Local file state is not that authority.
"""
import json
from .wsf_review_ticket import need,digest
from .wsf_manual_context import _json
from .wsf_control_projection import stamp

RISK_FIELDS=frozenset(("source_refs","current_controls_refs","control_evidence_state",
    "residual_exposure","next_control_point","review_trigger","evidence_as_of","last_reviewed_at"))

def validate_append(ticket,old,new,company,verify_historical_act,now):
    need(all(type(x) is bytes and len(x)<=2*1024*1024 for x in (old,new)),"snapshot bound")
    need((digest(old),digest(new))==(ticket.predecessor,ticket.successor),"source pins")
    a,b=map(json.loads,(old,new))
    for raw,doc in ((old,a),(new,b)):
        company.replay(doc);need(company.canonical(doc)==raw,"canonical Company bytes")
    schema={"decision":"arvectum.company.decision-approval-escalation-register/1",
            "risk":"arvectum.company.risk-exception-incident-register/1"}[ticket.register]
    need(a["schema"]==b["schema"]==schema and a["coverage"]==b["coverage"]=="partial","schema drift")
    need(len(b["events"])==len(a["events"])+1 and b["events"][:-1]==a["events"],"one append only")
    e=b["events"][-1];r=e["record"];rid=r["id"]
    need(rid==ticket.record_id and stamp(e["at"])<=stamp(ticket.issued_at)<=stamp(now),"record/time binding")
    prior=company.replay(a);after=company.replay(b)
    if ticket.register=="decision":
        baseline={"DEC-001","DEC-002","DEC-003","APR-001"}
        if rid=="DEC-005":baseline.add("DEC-004")
        need(rid in ("DEC-004","DEC-005") and set(prior)==baseline and set(after)==baseline|{rid},"historical decision scope")
        need(r["decision_state"]=="decided" and r["decision_outcome"]=="approve_with_conditions"
             and r["decision_authority"]=="Owner" and r["accountable_position"]=="POS-001"
             and r["effect_readiness"]=="blocked" and r["required_approval_refs"]==[]
             and bool(r["decision_act_ref"]) and verify_historical_act(r),"historical act not independently verified")
    else:
        need(rid=="RSK-002" and set(prior)==set(after)=={"RSK-001","RSK-002","RSK-003"},"risk scope")
        before=prior[rid]
        changes={k for k in before if before[k]!=r[k]}
        need(bool(changes) and changes<=RISK_FIELDS,"risk field scope")
        need(r["risk_state"]=="active" and r["risk_acceptance_decision_ref"] is None
             and r["closure_ref"] is None and r["owner_attention"]=="not_required","risk acceptance/closure denied")
        for k in ("source_refs","current_controls_refs"):
            need(set(before[k])<=set(r[k]),"provenance loss")
    need(all(after[k]==v for k,v in prior.items() if k!=rid),"unrelated record drift")
    return after

def transition(ticket,signature,*,trust,authority,io,company,verify_historical_act,clock):
    """Forward only. Head commits last. A resumed exact ticket may finish cleanup."""
    def gate():
        now=clock();trust.verify(ticket,signature,now)
        authority.check_live(trust,ticket,now)
        return now
    old_head=(ticket.sequence-1,ticket.previous_ticket,ticket.predecessor)
    new_head=(ticket.sequence,ticket.id(),ticket.successor)
    before=(ticket.predecessor,ticket.predecessor,False,old_head)
    states=[before,(ticket.successor,ticket.predecessor,False,old_head),
            (ticket.successor,ticket.successor,False,old_head),
            (ticket.successor,ticket.successor,True,old_head),
            (ticket.successor,ticket.successor,True,new_head)]
    journal=_json({"schema":"arvectum.review-transition-journal/1","ticket":ticket.id(),"signature":digest(signature)})
    def phase():
        observed=(*io.observe(ticket,signature),authority.head(trust.register))
        need(observed in states,"unexpected transition state");return states.index(observed)
    with io.exclusive():
        gate();io.check_write();old,new=io.candidates(ticket)
        validate_append(ticket,old,new,company,verify_historical_act,clock())
        n=phase();saved=io.journal()
        if saved is None:
            if n==4:return "already-completed"
            need(n==0,"partial state without journal");io.begin(journal)
        else:need(saved==journal,"different transaction journal")
        for i in range(n,4):
            gate();io.check_write();need(io.journal()==journal and phase()==i,"transaction drift")
            if i==0:io.append_source(new,ticket.predecessor)
            elif i==1:io.append_backup(new,ticket.predecessor)
            elif i==2:io.archive_ticket(ticket,signature)
            else:authority.compare_and_set(trust.register,old_head,new_head,trust,ticket,signature)
            need(phase()==i+1,"write verification")
        gate();io.check_write();need(phase()==4 and io.journal()==journal,"final verification")
        io.finish();return "completed"

def admitted_bytes(*,trust,authority,io,clock):
    """Verify independently anchored head and source/backup; no stale fallback."""
    need(io.journal() is None,"unfinished transition")
    head=authority.head(trust.register)
    need(head[0]>0,"no successor admitted")
    t,sig=io.read_ticket(head[1])
    trust.verify(t,sig,clock());authority.check_live(trust,t,clock())
    need(head==(t.sequence,t.id(),t.successor),"head binding")
    raw=io.read_source();backup=io.read_backup()
    need(raw==backup and digest(raw)==t.successor,"snapshot pair mismatch")
    trust.bind(t,clock());authority.check_live(trust,t,clock())
    need(authority.head(trust.register)==head and io.journal() is None
         and io.read_source()==raw and io.read_backup()==raw,"read changed")
    return raw
