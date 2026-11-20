"""Bounded candidate projection for the first reviewed AC-401 successor.

Not installed in the productive BFF. Approval and snapshot pin are independent
of source text; the caller must already establish them through governed access.
"""
import json
from .wsf_company_control_reference import normalized_rows,sha
from .wsf_control_projection import stamp
from .wsf_manual_context import ManualContextError,_json,_keys

FIELDS={"attention_state","evidence_as_of","last_reviewed_at","next_control_point","source_refs"}

def first_successor(old_raw,new_raw,*,review,now,expected_old,expected_new,decision):
    """Exactly one WORK-001 checkpoint revision, preserving customer controls."""
    try:
        if (type(old_raw) is not bytes or type(new_raw) is not bytes
            or max(len(old_raw),len(new_raw))>2*1024*1024
            or sha(old_raw)!=expected_old or sha(new_raw)!=expected_new
            or not isinstance(decision,str) or not decision.startswith("OWNER-")
            or len(decision)>160):
            raise ManualContextError("exact reviewed successor required")
        prior=json.loads(old_raw);candidate=json.loads(new_raw)
        rows=normalized_rows(prior,review,now)
        _keys(candidate,{"schema","coverage","events"})
        if candidate["schema"]!=prior["schema"] or candidate["coverage"]!="partial":
            raise ManualContextError("source envelope")
        events=candidate["events"]
        if not isinstance(events,list) or len(events)!=4 or events[:3]!=prior["events"]:
            raise ManualContextError("exact append required")
        e=events[-1]
        _keys(e,{"sequence","prior_digest","at","authority_ref","reason","record"})
        if (type(e["sequence"]) is not int or e["sequence"]!=4
            or e["prior_digest"]!=sha(_json(events[-2])+b"\n")
            or e["authority_ref"]!=decision
            or not isinstance(e["reason"],str) or not e["reason"].strip()
            or not stamp(events[-2]["at"])<=stamp(e["at"])<=stamp(now)):
            raise ManualContextError("revision provenance mismatch")
        old=next(x["record"] for x in prior["events"] if x["record"]["id"]=="WORK-001")
        r=e["record"]
        if (set(old)!=set(r) or any(old[k]!=r[k] for k in old if k not in FIELDS)
            or r["attention_state"]!="needs_attention"
            or old["control_state"]!="open"
            or r["control_state"]!="open"
            or r["next_control_point"]==old["next_control_point"]
            or not stamp(old["evidence_as_of"])<=stamp(r["evidence_as_of"])<=stamp(r["last_reviewed_at"])<=stamp(e["at"])
            or stamp(r["last_reviewed_at"])<stamp(old["last_reviewed_at"])):
            raise ManualContextError("revision exceeds first successor scope")
        old_refs=old["source_refs"];refs=r["source_refs"]
        if (not isinstance(refs,list) or refs[:len(old_refs)]!=old_refs or len(refs)!=len(old_refs)+1
            or not isinstance(refs[-1],str) or not refs[-1].strip() or refs[-1] in old_refs):
            raise ManualContextError("one additive evidence reference required")
        # Reuse the established projection and genuine pilot expiry; never
        # interpret source prose as an approval or a delegated assignment.
        target=next(x for x in rows if x["id"]=="WORK-001")
        target.update(next_control_point=r["next_control_point"],
                      evidence_as_of=r["evidence_as_of"],source_refs=refs)
        return rows
    except (ValueError,TypeError,KeyError,AttributeError,StopIteration,RecursionError) as exc:
        raise ManualContextError("invalid successor") from exc
