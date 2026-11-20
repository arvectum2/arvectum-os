"""Offline review of a candidate Company source revision, not an admission operator.

No disk writes, authority, new identity allocation, runtime route or provider.
The Company register owns validation and append semantics. Reviewed bytes and
position mappings must be explicitly approved separately before activation.
"""
from workspace_app.wsf_company_control_reference import sha,BINDINGS
from workspace_app.wsf_manual_context import ManualContextError,_json
from workspace_app.wsf_control_projection import stamp
import json

def reject(message):
    raise ManualContextError(message)

def review(old_raw,new_raw,*,now):
    if any(type(raw) is not bytes or len(raw)>2*1024*1024 for raw in (old_raw,new_raw)):
        reject("bounded source bytes required")
    def replay(raw):
        d=json.loads(raw)
        if set(d)!={"schema","coverage","events"} or d["schema"]!="arvectum.company.work-obligation-register/1" or d["coverage"]!="partial":
            reject("source envelope")
        events=d["events"]
        if not isinstance(events,list) or not 1<=len(events)<=1000:
            reject("event count")
        latest={};concerns={};counts={"WORK":0,"OBL":0};prior=None;last=None
        for n,e in enumerate(events,1):
            if set(e)!={"sequence","prior_digest","at","authority_ref","reason","record"} or type(e["sequence"]) is not int or e["sequence"]!=n or e["prior_digest"]!=prior:
                reject("revision chain")
            at=stamp(e["at"])
            if at>stamp(now) or (last is not None and at<last):
                reject("revision time")
            if not all(isinstance(e[k],str) and e[k].strip() for k in ("authority_ref","reason")):
                reject("revision provenance")
            r=e["record"];rid=r["id"];key=r["concern_key"]
            prefix={"work":"WORK","obligation":"OBL"}.get(r["kind"])
            if prefix is None or not isinstance(key,str) or not key or not isinstance(rid,str):
                reject("identity")
            if rid in latest:
                if (latest[rid]["kind"],latest[rid]["concern_key"])!=(r["kind"],key):
                    reject("identity changed")
                if stamp(r["last_reviewed_at"])<stamp(latest[rid]["last_reviewed_at"]):
                    reject("review regressed")
            else:
                counts[prefix]+=1
                if key in concerns or rid!=prefix+"-%03d"%counts[prefix]:
                    reject("identity allocation")
                concerns[key]=rid
            if not stamp(r["evidence_as_of"])<=stamp(r["last_reviewed_at"])<=at:
                reject("evidence time")
            latest[rid]=r;last=at;prior=sha(_json(e)+b"\n")
        return events,latest
    try:
        before,old=replay(old_raw);after,new=replay(new_raw)
        if len(after)<=len(before) or after[:len(before)]!=before:
            reject("not append-only successor")
        if {k:v["accountable_position"] for k,v in old.items()}!=BINDINGS:
            reject("expected predecessor identities not present")
        if set(new)!=set(old):
            reject("new identities require separate scope")
        changes=[]
        # First successor is deliberately limited to review/control metadata.
        allowed={"attention_state","control_state","next_control_point","evidence_as_of","last_reviewed_at","source_refs","escalation_need"}
        for rid,r in new.items():
            p=old[rid]
            if set(p)!=set(r):
                reject("record schema changed")
            fields=sorted(k for k in r if r[k]!=p[k])
            if set(fields)-allowed:
                reject("change outside bounded successor review")
            if r["control_state"] not in ("open","waiting","blocked") or r["attention_state"] not in ("normal","needs_attention","escalated"):
                reject("closure or invalid state")
            if r["control_state"] in ("waiting","blocked") and r["attention_state"]=="normal":
                reject("explicit review required in this slice")
            if r["attention_state"]=="escalated" and not r["escalation_need"]:
                reject("escalation evidence missing")
            if fields:changes.append({"id":rid,"fields":fields,"position":r["accountable_position"],"review_required":True})
        # Check intermediate revisions too, not merely the tail.
        for e in after[len(before):]:
            r=e["record"];p=old[r["id"]]
            if set(r)!=set(p) or any(r[k]!=p[k] for k in p if k not in allowed):
                reject("intermediate revision exceeds scope")
            if r["control_state"] not in ("open","waiting","blocked") or r["attention_state"] not in ("normal","needs_attention","escalated"):
                reject("intermediate state")
            if r["control_state"] in ("waiting","blocked") and r["attention_state"]=="normal":
                reject("intermediate review required")
            if r["attention_state"]=="escalated" and not r["escalation_need"]:
                reject("intermediate escalation evidence missing")
        if not changes:reject("no effective record change")
        return {"old_sha256":sha(old_raw),"candidate_sha256":sha(new_raw),"prior_events":len(before),"candidate_events":len(after),"changes":changes,"coverage":"partial","authority_provided":False,"activation_permitted":False}
    except (TypeError,KeyError,AttributeError,ValueError) as exc:
        raise ManualContextError("invalid revision candidate") from exc
