"""Bounded private Tender event observation journal; no live endpoint binding."""
from datetime import timedelta
import json
from pathlib import Path
from .wsf_manual_context import (ManualContextStore, ManualContextError, _identity,
    _keys, _id, _json, _digest, MAX_BYTES, MAX_EVENTS)
from .wsf_control_projection import stamp
from .wsf_tender_events import normalize, opaque, KINDS

SCHEMA="arvectum.workspace.tender-inbox/1"
SOURCE_SCHEMA="arvectum.tender.workspace-event-window/1"

def group_id(row):
    return "TENDERGROUP-"+_digest(_json([row[k] for k in ("binding_id","source_project_id","case_ref","run_ref")]))[:32]

def reduced(row,tenant):
    """Reconstruct only the admitted producer metadata for validation on replay."""
    kind=row["kind"]
    a=row["run_ref"] if kind=="analysis_completed" else row["case_ref"]
    data={"project_id":row["source_project_id"]}
    if kind=="analysis_completed":
        data.update(case_id=row["case_ref"],status="completed")
    else:
        data.update(run_id=row["run_ref"],reason="analysis_completed_operator_review")
    common={"event_key":row["event_key"],"event_type":kind,"tenant_id":tenant,
            "aggregate_type":KINDS[kind],"aggregate_id":a}
    return {"id":row["source_record_id"],**common,"created_at":row["created_at"],
        "envelope":{"schema_version":"integration-event-v1",**common,"occurred_at":row["occurred_at"],"data":data}}

class _TenderFile(ManualContextStore):
    def __init__(self,directory,access,*,binding_id,tenant,project_map,require_initialized):
        directory=Path(directory)
        if directory.resolve()!=directory:raise ManualContextError("unsafe inbox directory")
        opaque(binding_id);opaque(tenant)
        if not isinstance(project_map,dict) or not 1<=len(project_map)<=32:
            raise ManualContextError("bounded project map required")
        for k,v in project_map.items():opaque(k);_id(v,"PRJ-")
        super().__init__(directory,access,require_initialized=require_initialized)
        self.require_initialized=True
        self.path=directory/"tender-inbox.json"
        self.access=access
        self.binding_id=binding_id;self.tenant=tenant
        self.project_map=json.loads(_json(project_map))
        self.binding_digest=_digest(_json([binding_id,tenant,self.project_map]))
    def _encode(self,events):
        d={"schema":SCHEMA,"scope":self.scope,"binding_sha256":self.binding_digest,"events":events}
        raw=_json({**d,"sha256":_digest(_json(d))})
        if len(raw)>MAX_BYTES:raise ManualContextError("tender inbox capacity exceeded")
        return raw
    def _decode(self,raw):
        if not isinstance(raw,bytes) or len(raw)>MAX_BYTES:raise ManualContextError("invalid snapshot size")
        try:
            d=json.loads(raw);_keys(d,{"schema","scope","binding_sha256","events","sha256"})
            if self._encode(d["events"])!=raw:raise ManualContextError("snapshot scope or integrity mismatch")
            self.replay(d["events"])
            return d["events"]
        except (TypeError,KeyError,ValueError,UnicodeError,RecursionError,AttributeError) as exc:
            raise ManualContextError("invalid tender snapshot") from exc
    def replay(self,events):
        if not isinstance(events,list) or len(events)>MAX_EVENTS:raise ManualContextError("event limit")
        rows={};groups={};seen={};last=None;observation=None
        for e in events:
            _keys(e,{"key","operation","at","data"});key=_id(e["key"]);at=stamp(e["at"])
            if key in seen or last is not None and at<last:raise ManualContextError("event order conflict")
            last=at;seen[key]=e;d=e["data"]
            if e["operation"]=="window":
                _keys(d,{"state","since","until","rows"})
                left,right=stamp(d["since"]),stamp(d["until"])
                if not left<right<=at or right-left>timedelta(hours=24):raise ManualContextError("invalid observation interval")
                if d["state"] not in ("observed","overflow") or not isinstance(d["rows"],list) or len(d["rows"])>100:
                    raise ManualContextError("invalid observation")
                if d["state"]=="overflow" and d["rows"]:raise ManualContextError("overflow must not supply rows")
                rebuilt=normalize(self.access,[reduced(r,self.tenant) for r in d["rows"]],scope=self.scope,binding_id=self.binding_id,
                    tenant=self.tenant,project_map=self.project_map,now=e["at"])
                if rebuilt!=d["rows"]:raise ManualContextError("normalized event mismatch")
                for r in rebuilt:
                    if not left<=stamp(r["created_at"])<right:raise ManualContextError("event outside observation")
                    if r["id"] in rows:
                        if rows[r["id"]]!=r:raise ManualContextError("immutable event conflict")
                        continue
                    rows[r["id"]]=r;gid=group_id(r);old=groups.get(gid)
                    g=old or {"id":gid,"project_id":r["project_id"],"case_ref":r["case_ref"],"run_ref":r["run_ref"],
                              "event_ids":[],"review_signal":False,"revision":0}
                    groups[gid]={**g,"event_ids":g["event_ids"]+[r["id"]],
                        "review_signal":g["review_signal"] or r["kind"]=="review_required",
                        "revision":g["revision"]+1,"state":"pending","reviewed_at":None,
                        "owner_action":"unknown","canonical_authority":False}
                observation={"state":d["state"],"since":d["since"],"until":d["until"],"checked_at":e["at"],
                             "coverage":"partial"}
            elif e["operation"]=="review":
                _keys(d,{"group_id","expected_revision","state"})
                g=groups.get(d["group_id"])
                if (g is None or type(d["expected_revision"]) is not int or g["revision"]!=d["expected_revision"]
                    or g["state"]!="pending" or d["state"] not in ("reviewed","dismissed")):
                    raise ManualContextError("review conflict")
                groups[g["id"]]={**g,"revision":g["revision"]+1,"state":d["state"],"reviewed_at":e["at"]}
            else:raise ManualContextError("unknown operation")
        return rows,groups,seen,observation
    def submit(self,*args,**kw):raise ManualContextError("note operations unavailable")
    def read(self,*args,**kw):raise ManualContextError("use tender projection")
    def history(self,*args,**kw):raise ManualContextError("use tender projection")

class TenderInbox:
    def __init__(self,directory,access,*,binding_id,tenant,project_map,require_initialized=False):
        self.file=_TenderFile(directory,access,binding_id=binding_id,tenant=tenant,project_map=project_map,
                              require_initialized=require_initialized)
    def initialize(self,a):self.file.restore_empty(a,self.file._encode([]))
    def _append(self,a,key,operation,data,at):
        f=self.file;f._authorize(a);_id(key);stamp(at)
        try:data=json.loads(_json(data))
        except (ValueError,TypeError) as exc:raise ManualContextError("invalid observation") from exc
        with f._locked():
            events=f._load();_,_,seen,_=f.replay(events)
            if key in seen:
                previous=seen[key]
                if (previous["operation"],previous["data"])!=(operation,data):raise ManualContextError("request replay conflict")
                return
            try:f._write(f._encode(events+[{"key":key,"operation":operation,"at":at,"data":data}]))
            except (ValueError,TypeError,KeyError) as exc:raise ManualContextError("observation rejected") from exc
    def admit_window(self,a,key,response,checked_at):
        f=self.file;f._authorize(a)
        _keys(response,{"schema","state","since","until","coverage","rows"})
        if response["schema"]!=SOURCE_SCHEMA or response["coverage"]!="partial":raise ManualContextError("source contract mismatch")
        if response["state"]=="overflow" and response["rows"]!=[]:raise ManualContextError("invalid overflow")
        rows=normalize(a,response["rows"],scope=f.scope,binding_id=f.binding_id,tenant=f.tenant,
                       project_map=f.project_map,now=checked_at)
        self._append(a,key,"window",{"state":response["state"],"since":response["since"],"until":response["until"],"rows":rows},checked_at)
    def review(self,a,key,item_id,expected_revision,state,at):
        self._append(a,key,"review",{"group_id":_id(item_id,"TENDERGROUP-"),"expected_revision":expected_revision,"state":state},at)
    def read(self,a):
        f=self.file;f._authorize(a)
        with f._locked():
            rows,groups,_,observation=f.replay(f._load())
            return {"coverage":"partial" if observation else "unknown","observation":observation,
                    "events":list(rows.values()),"groups":list(groups.values()),
                    "pending_count":sum(r["state"]=="pending" for r in groups.values()),
                    "canonical_authority":False,"organizational_authority_provided":False}
    def export(self,a):return self.file.export(a)
    def restore_empty(self,a,raw):return self.file.restore_empty(a,raw)
