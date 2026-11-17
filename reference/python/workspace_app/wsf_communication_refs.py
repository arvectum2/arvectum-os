"""WSF-07C product-local communication reference candidate.

The trusted future adapter supplies reduced metadata only. No Gmail/Calendar
credentials, network calls, message bodies, titles, attendees or sender data.
No durable source is admitted by constructing a binding object in this module.
"""
from datetime import date, datetime, timezone
import re
import json
from pathlib import Path
from .wsf_manual_context import ManualContextStore, ManualContextError, _identity, _keys, _id, _json, _digest, MAX_BYTES, MAX_EVENTS
from .wsf_control_projection import stamp

SCHEMA="arvectum.workspace.communication-references/1"
KINDS={"mail","calendar"}
MAX_PAGE=100
REF_FIELDS={"native_id","revision","state","occurred_at","start","end"}
STATES={"mail":{"received","unavailable"},"calendar":{"confirmed","tentative","cancelled","unavailable"}}

def opaque(v):
    if not isinstance(v,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:@+-]{0,191}",v):
        raise ManualContextError("invalid opaque source identifier")
    return v

def interval(v):
    if not isinstance(v,str):raise ManualContextError("invalid calendar boundary")
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}",v):
        try:return ("date",date.fromisoformat(v))
        except ValueError:raise ManualContextError("invalid calendar date") from None
    return ("utc",stamp(v))

def normalize(kind,row,checked_at):
    _keys(row,REF_FIELDS)
    opaque(row["native_id"]);opaque(row["revision"])
    if row["state"] not in STATES[kind]:raise ManualContextError("source state unavailable")
    if row["occurred_at"] is not None and stamp(row["occurred_at"])>stamp(checked_at):
        raise ManualContextError("future observation")
    if kind=="mail":
        if row["start"] is not None or row["end"] is not None:raise ManualContextError("mail interval invalid")
        if row["state"]=="received" and row["occurred_at"] is None:raise ManualContextError("mail receipt time required")
    elif row["state"] in ("confirmed","tentative"):
        a,b=interval(row["start"]),interval(row["end"])
        if a[0]!=b[0] or a[1]>=b[1]:raise ManualContextError("invalid calendar interval")
    elif (row["start"] is None)!=(row["end"] is None):
        raise ManualContextError("partial calendar interval")
    elif row["start"] is not None:
        a,b=interval(row["start"]),interval(row["end"])
        if a[0]!=b[0] or a[1]>=b[1]:raise ManualContextError("invalid calendar interval")
    return json.loads(_json(row))

class _ReferenceFile(ManualContextStore):
    def __init__(self,directory,access,bindings,project_ids,require_initialized):
        directory=Path(directory)
        if directory.resolve()!=directory:raise ManualContextError("unsafe reference directory")
        super().__init__(directory,access,require_initialized=require_initialized)
        self.require_initialized=True
        self.path=directory/"communications.json"
        if not isinstance(bindings,dict) or not 1<=len(bindings)<=4:raise ManualContextError("exact bounded bindings required")
        for k,b in bindings.items():
            opaque(k);_keys(b,{"kind","account_ref","container_ref"})
            if b["kind"] not in KINDS:raise ManualContextError("unsupported source")
            opaque(b["account_ref"]);opaque(b["container_ref"])
        if len({(b["kind"],b["account_ref"],b["container_ref"]) for b in bindings.values()})!=len(bindings):
            raise ManualContextError("duplicate source binding")
        self.bindings=json.loads(_json(bindings))
        self.projects=frozenset(_id(p,"PRJ-") for p in project_ids)
        self.binding_digest=_digest(_json(self.bindings))
    def _encode(self,events):
        d={"schema":SCHEMA,"scope":self.scope,"binding_sha256":self.binding_digest,"events":events}
        raw=_json({**d,"sha256":_digest(_json(d))})
        if len(raw)>MAX_BYTES:raise ManualContextError("reference capacity exceeded")
        return raw
    def _decode(self,raw):
        if not isinstance(raw,bytes) or len(raw)>MAX_BYTES:raise ManualContextError("invalid snapshot size")
        try:
            d=json.loads(raw)
            _keys(d,{"schema","scope","binding_sha256","events","sha256"})
            if self._encode(d["events"])!=raw:raise ManualContextError("reference integrity or scope mismatch")
            self.replay(d["events"]);return d["events"]
        except (TypeError,KeyError,ValueError,AttributeError,RecursionError,UnicodeError) as exc:
            raise ManualContextError("invalid reference snapshot") from exc
    def replay(self,events):
        if not isinstance(events,list) or len(events)>MAX_EVENTS:raise ManualContextError("reference event limit")
        current={};history={};requests={};checkpoints={};last=None
        for event in events:
            _keys(event,{"key","operation","at","data"})
            key=_id(event["key"]);at=stamp(event["at"]);d=event["data"]
            if key in requests or last is not None and at<last:raise ManualContextError("event ordering conflict")
            last=at;requests[key]=event
            if event["operation"]=="page":
                _keys(d,{"binding","expected_cursor","next_cursor","complete","rows"})
                binding=self.bindings.get(d["binding"])
                if binding is None:raise ManualContextError("binding unavailable")
                for c in ("expected_cursor","next_cursor"):
                    if d[c] is not None:opaque(d[c])
                if type(d["complete"]) is not bool or not isinstance(d["rows"],list) or len(d["rows"])>MAX_PAGE:
                    raise ManualContextError("invalid bounded page")
                prior=checkpoints.get(d["binding"],{}).get("cursor")
                if d["expected_cursor"]!=prior:raise ManualContextError("checkpoint conflict")
                if d["next_cursor"]==prior or d["next_cursor"] is None:raise ManualContextError("nonadvancing checkpoint")
                revisions=set()
                natives=set()
                for raw in d["rows"]:
                    row=normalize(binding["kind"],raw,event["at"])
                    iid="COMM-"+_digest(_json([d["binding"],row["native_id"]]))[:32]
                    if iid in natives:raise ManualContextError("ambiguous page: multiple revisions")
                    natives.add(iid)
                    rk=(iid,row["revision"])
                    if rk in revisions:raise ManualContextError("duplicate page reference")
                    revisions.add(rk)
                    old=current.get(iid)
                    earlier=[r for r in history.get(iid,[]) if r["revision"]==row["revision"]]
                    if earlier:
                        if earlier[0]!=row:raise ManualContextError("immutable source revision conflict")
                        if old["source"]["revision"]!=row["revision"]:raise ManualContextError("source revision replay out of order")
                        continue
                    history.setdefault(iid,[]).append(row)
                    current[iid]={"id":iid,"binding":d["binding"],"kind":binding["kind"],"source":row,
                      "review_state":"pending","review_revision":1 if old is None else old["review_revision"]+1,
                      "project_id":None,"observed_at":event["at"],"canonical_authority":False}
                checkpoints[d["binding"]]={"cursor":d["next_cursor"],"complete":d["complete"],"checked_at":event["at"]}
            elif event["operation"]=="review":
                _keys(d,{"id","expected_revision","state","project_id"})
                r=current.get(d["id"])
                if r is None or type(d["expected_revision"]) is not int or r["review_revision"]!=d["expected_revision"] or r["review_state"]!="pending":
                    raise ManualContextError("review conflict")
                if d["state"] not in ("reviewed","dismissed"):raise ManualContextError("invalid review state")
                p=d["project_id"]
                if p is not None and (p not in self.projects or d["state"]!="reviewed"):raise ManualContextError("project link unavailable")
                current[r["id"]]={**r,"review_revision":r["review_revision"]+1,"review_state":d["state"],"project_id":p}
            else:raise ManualContextError("unsupported operation")
        return current,history,requests,checkpoints
    def submit(self,*a,**kw):raise ManualContextError("manual operations excluded")
    def read(self,*a,**kw):raise ManualContextError("use reference projection")
    def history(self,*a,**kw):raise ManualContextError("use reference projection")

class CommunicationReferences:
    def __init__(self,directory,access,*,bindings,project_ids,require_initialized=False):
        self.file=_ReferenceFile(directory,access,bindings,project_ids,require_initialized)
    def initialize(self,access):self.file.restore_empty(access,self.file._encode([]))
    def _append(self,a,key,operation,data,at):
        f=self.file;f._authorize(a);_id(key);stamp(at)
        try:data=json.loads(_json(data))
        except (TypeError,ValueError) as exc:raise ManualContextError("invalid data") from exc
        with f._locked():
            events=f._load();_,_,requests,_=f.replay(events)
            if key in requests:
                e=requests[key]
                if (e["operation"],e["data"])!=(operation,data):raise ManualContextError("request replay conflict")
                return
            try:f._write(f._encode(events+[{"key":key,"operation":operation,"data":data,"at":at}]))
            except (TypeError,KeyError,ValueError) as exc:raise ManualContextError("reference request rejected") from exc
    def admit_page(self,a,key,*,binding,expected_cursor,next_cursor,complete,rows,checked_at):
        self._append(a,key,"page",{"binding":binding,"expected_cursor":expected_cursor,"next_cursor":next_cursor,"complete":complete,"rows":rows},checked_at)
    def review(self,a,key,*,item_id,expected_revision,state,project_id,at):
        self._append(a,key,"review",{"id":item_id,"expected_revision":expected_revision,"state":state,"project_id":project_id},at)
    def read(self,a,*,authorized_bindings,now):
        self.file._authorize(a);t=stamp(now)
        if not set(authorized_bindings)<=set(self.file.bindings):raise ManualContextError("unknown rights binding")
        with self.file._locked():
            rows,_,_,ck=self.file.replay(self.file._load())
            # Suppress revoked sources AND counts; historical export separately gated.
            active=set(authorized_bindings)
            items=[r for r in rows.values() if r["binding"] in active]
            sources=[{"binding":k,"kind":self.file.bindings[k]["kind"],"state":"unknown" if k not in ck else
                "incomplete" if not ck[k]["complete"] else "observed",
                "freshness":"refresh-needed" if k not in ck or not 0<=(t-stamp(ck[k]["checked_at"])).total_seconds()<=14400 else "recent"}
                for k in sorted(active)]
            return {"derived":True,"canonical_authority":False,"coverage":"partial" if ck.keys()&active else "unknown",
                "items":items,"sources":sources,"pending":sum(r["review_state"]=="pending" for r in items)}
    def export(self,a,*,authorized_bindings):
        if set(authorized_bindings)!=set(self.file.bindings):raise ManualContextError("full export requires all current source rights")
        return self.file.export(a)
    def restore_empty(self,a,raw,*,authorized_bindings):
        if set(authorized_bindings)!=set(self.file.bindings):raise ManualContextError("restore scope unavailable")
        return self.file.restore_empty(a,raw)
