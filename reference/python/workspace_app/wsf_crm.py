"""WSF-06 native CRM Lite, product-local fixture implementation.

No external messaging, bank facts, legal authority, Principal allocation or
production activation. The caller must supply independently admitted scope,
reference catalog, and current permissions; synthetic data only until review.
"""
from datetime import datetime, timezone
import fcntl
from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat
import tempfile
import unicodedata
from uuid import uuid4

from .wsf_manual_context import ManualContextError, _identity, _id, _keys, _json, _digest, _text

SCHEMA = "arvectum.workspace.crm-lite/1"
MAX_BYTES = 2 * 1024 * 1024
MAX_EVENTS = 500
PREFIX = {"party":"PARTY-", "contact":"CONTACT-", "opportunity":"OPP-", "interaction":"INT-"}
FIELDS = {
    "party": {"name","registry_ref","description"},
    "contact": {"party_id","name","role","channel_ref"},
    "opportunity": {"party_id","contact_id","title","stage","next_action","next_contact_at",
                    "project_id","evidence_refs","outcome_ref"},
    "interaction": {"party_id","contact_id","opportunity_id","project_id","kind","occurred_at",
                    "summary","evidence_ref"},
}
STAGES = {"discovery","qualified","proposal","negotiation","paused","won","lost"}
TERMINAL = {"won","lost"}


def _norm(value):
    return " ".join(unicodedata.normalize("NFKC",value).casefold().split())


def _time(value):
    try:
        d=datetime.fromisoformat(value)
        if d.utcoffset()!=timezone.utc.utcoffset(d):
            raise ValueError()
        return d
    except (ValueError,TypeError):
        raise ManualContextError("UTC timestamp required") from None


class CRMStore:
    def __init__(self,directory,access,*,project_ids,evidence_refs):
        self.directory=Path(directory)
        self.scope=_identity(access)
        self.projects=frozenset(_id(x,"PRJ-") for x in project_ids)
        self.refs=frozenset(_text(x,500) for x in evidence_refs)
        if not self.directory.is_absolute() or self.directory.resolve()!=self.directory:
            raise ManualContextError("unsafe CRM directory")
        self.directory.mkdir(mode=0o700,exist_ok=True)
        s=self.directory.lstat()
        if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode&0o077:
            raise ManualContextError("unsafe CRM directory")
        self.path=self.directory/"crm.json"

    def _auth(self,access):
        if _identity(access)!=self.scope:
            raise ManualContextError("CRM unavailable")

    def _ref(self,value,required=False):
        if value is None and not required:return
        if not isinstance(value,str) or value not in self.refs:
            raise ManualContextError("evidence reference unavailable")

    def _project(self,pid):
        if pid is not None and (not isinstance(pid,str) or pid not in self.projects):
            raise ManualContextError("project unavailable")

    def _validate(self,kind,data,current,previous,at):
        _keys(data,FIELDS[kind])
        if kind=="party":
            _text(data["name"],160);_text(data["description"],1000)
            self._ref(data["registry_ref"])
            if previous and previous["registry_ref"] is not None and previous["registry_ref"]!=data["registry_ref"]:
                raise ManualContextError("registered party reference cannot silently change")
            for other in current[kind].values():
                if previous and other["id"]==previous["id"]:continue
                if _norm(other["name"])==_norm(data["name"]) or (data["registry_ref"] and other["registry_ref"]==data["registry_ref"]):
                    raise ManualContextError("possible duplicate party; review existing record")
            return
        pid=_id(data["party_id"],PREFIX["party"])
        if pid not in current["party"] or previous and previous["party_id"]!=pid:
            raise ManualContextError("party missing or immutable association changed")
        if kind=="contact":
            _text(data["name"],160);_text(data["role"],160)
            self._ref(data["channel_ref"])
            for other in current[kind].values():
                if previous and other["id"]==previous["id"]:continue
                if other["party_id"]==pid and _norm(other["name"])==_norm(data["name"]):
                    raise ManualContextError("possible duplicate contact; review existing record")
            return
        cid=data["contact_id"]
        if cid is not None:
            _id(cid,PREFIX["contact"])
            if cid not in current["contact"] or current["contact"][cid]["party_id"]!=pid:
                raise ManualContextError("contact/party mismatch")
        self._project(data["project_id"])
        if kind=="opportunity":
            _text(data["title"],160)
            if data["stage"] not in STAGES:raise ManualContextError("invalid opportunity stage")
            if previous and previous["stage"] in TERMINAL and data["stage"]!=previous["stage"]:
                raise ManualContextError("closed opportunity cannot be silently reopened")
            if data["stage"] in TERMINAL:
                self._ref(data["outcome_ref"],True)
                if data["next_action"] is not None or data["next_contact_at"] is not None:
                    raise ManualContextError("closed opportunity cannot carry active follow-up")
            else:
                if data["outcome_ref"] is not None:raise ManualContextError("unclosed opportunity has outcome")
                _text(data["next_action"],500)
                if data["next_contact_at"] is not None:_time(data["next_contact_at"])
            refs=data["evidence_refs"]
            if not isinstance(refs,list) or len(refs)>24 or any(not isinstance(x,str) for x in refs) or len(set(refs))!=len(refs):
                raise ManualContextError("invalid opportunity evidence")
            for ref in refs:self._ref(ref,True)
            for other in current[kind].values():
                if previous and other["id"]==previous["id"]:continue
                if other["party_id"]==pid and _norm(other["title"])==_norm(data["title"]):
                    raise ManualContextError("possible duplicate opportunity; review existing record")
            return
        oid=data["opportunity_id"]
        if oid is not None:
            _id(oid,PREFIX["opportunity"])
            opp=current["opportunity"].get(oid)
            if not opp or opp["party_id"]!=pid:
                raise ManualContextError("opportunity/party mismatch")
            if data["project_id"] is not None and opp["project_id"] is not None and opp["project_id"]!=data["project_id"]:
                raise ManualContextError("interaction/project mismatch at observation")
        if data["kind"] not in {"meeting","call","email","message","other"}:
            raise ManualContextError("unsupported interaction kind")
        if _time(data["occurred_at"])>_time(at):raise ManualContextError("future interaction")
        _text(data["summary"],1500)
        self._ref(data["evidence_ref"],True)
        if previous and previous["evidence_ref"]!=data["evidence_ref"]:
            raise ManualContextError("interaction evidence identity cannot change")
        for other in current[kind].values():
            if previous and other["id"]==previous["id"]:continue
            if other["evidence_ref"]==data["evidence_ref"]:
                raise ManualContextError("interaction evidence already recorded")

    def _replay(self,events):
        if not isinstance(events,list) or len(events)>MAX_EVENTS:raise ManualContextError("CRM capacity exceeded")
        current={k:{} for k in FIELDS};history={};requests={}
        for event in events:
            _keys(event,{"key","entity","id","expected_revision","data","at"})
            key=_id(event["key"])
            if key in requests:raise ManualContextError("duplicate request")
            kind=event["entity"]
            if kind not in FIELDS:raise ManualContextError("unknown CRM entity")
            rid=_id(event["id"],PREFIX[kind]);rev=event["expected_revision"]
            _time(event["at"])
            old=current[kind].get(rid)
            if type(rev) is not int or rev!=(old["revision"] if old else 0):
                raise ManualContextError("revision conflict")
            self._validate(kind,event["data"],current,old,event["at"])
            row={**event["data"],"id":rid,"revision":rev+1,"recorded_at":event["at"],
                 "authority_provided":False}
            current[kind][rid]=row
            history.setdefault(rid,[]).append(row)
            requests[key]=(event,row)
        return current,history,requests

    def _encode(self,events):
        body={"schema":SCHEMA,"scope":self.scope,"events":events}
        raw=_json({**body,"sha256":_digest(_json(body))})
        if len(raw)>MAX_BYTES:raise ManualContextError("CRM size exceeded")
        return raw

    def _decode(self,raw):
        if not isinstance(raw,bytes) or len(raw)>MAX_BYTES:raise ManualContextError("invalid CRM snapshot size")
        try:
            obj=json.loads(raw);_keys(obj,{"schema","scope","events","sha256"})
            if obj["schema"]!=SCHEMA or obj["scope"]!=self.scope or self._encode(obj["events"])!=raw:
                raise ManualContextError("CRM integrity or scope mismatch")
            self._replay(obj["events"])
            return obj["events"]
        except (TypeError,KeyError,AttributeError,UnicodeError,RecursionError,ValueError) as exc:
            raise ManualContextError("invalid CRM snapshot") from exc

    def _open(self,path,flags):
        fd=os.open(path,flags|os.O_NOFOLLOW,0o600);s=os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode&0o077 or s.st_nlink!=1:
            os.close(fd);raise ManualContextError("unsafe private CRM file")
        return fd

    @contextmanager
    def _lock(self):
        fd=self._open(self.directory/".lock",os.O_CREAT|os.O_RDWR)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX);yield
        finally:os.close(fd)

    def _load(self):
        try:fd=self._open(self.path,os.O_RDONLY)
        except FileNotFoundError:raise ManualContextError("CRM unavailable; restore or initialize explicitly") from None
        with os.fdopen(fd,"rb") as f:return self._decode(f.read(MAX_BYTES+1))

    def _write(self,raw):
        self._decode(raw)
        fd,name=tempfile.mkstemp(dir=self.directory,prefix=".crm-")
        try:
            with os.fdopen(fd,"wb") as f:f.write(raw);f.flush();os.fsync(f.fileno())
            os.replace(name,self.path)
            fd=os.open(self.directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            try:os.fsync(fd)
            finally:os.close(fd)
        finally:
            if os.path.exists(name):os.unlink(name)

    def initialize(self,access):
        self.restore_empty(access,self._encode([]))

    def submit(self,access,key,entity,data,*,record_id=None,expected_revision=0):
        self._auth(access);_id(key)
        if not isinstance(entity,str) or entity not in FIELDS:raise ManualContextError("unknown CRM entity")
        if record_id is not None:_id(record_id,PREFIX[entity])
        if type(expected_revision) is not int or (record_id is None and expected_revision!=0) or (record_id is not None and expected_revision<1):
            raise ManualContextError("invalid revision")
        try:data=json.loads(_json(data))
        except (ValueError,TypeError):raise ManualContextError("invalid CRM data") from None
        with self._lock():
            events=self._load();_,_,requests=self._replay(events)
            if key in requests:
                e,row=requests[key]
                if (e["entity"],e["data"],e["expected_revision"],e["id"] if expected_revision else None)!=(entity,data,expected_revision,record_id):
                    raise ManualContextError("idempotency conflict")
                return row
            event={"key":key,"entity":entity,"id":record_id or PREFIX[entity]+uuid4().hex,
                   "expected_revision":expected_revision,"data":data,"at":datetime.now(timezone.utc).isoformat()}
            updated=events+[event]
            try:_,_,requests=self._replay(updated)
            except (TypeError,KeyError,AttributeError,UnicodeError,RecursionError,ValueError) as exc:
                raise ManualContextError("invalid CRM record or revision") from exc
            self._write(self._encode(updated))
            return requests[key][1]

    def read(self,access,query="",project_id=None):
        self._auth(access);self._project(project_id)
        if not isinstance(query,str) or len(query)>160:raise ManualContextError("invalid search")
        with self._lock():
            current,_,_=self._replay(self._load())
            # Filter by project without pulling unrelated parties/contacts.
            if project_id is not None:
                for kind in ("opportunity","interaction"):
                    current[kind]={k:v for k,v in current[kind].items() if v["project_id"]==project_id}
                pids={v["party_id"] for kind in ("opportunity","interaction") for v in current[kind].values()}
                current["party"]={k:v for k,v in current["party"].items() if k in pids}
                cids={v["contact_id"] for kind in ("opportunity","interaction") for v in current[kind].values() if v["contact_id"] is not None}
                current["contact"]={k:v for k,v in current["contact"].items() if k in cids}
            q=_norm(query)
            return {k:[v for v in rows.values() if not q or any(q in _norm(v.get(f) or "") for f in ("name","title","role","summary","next_action","description"))]
                    for k,rows in current.items()}

    def history(self,access,rid):
        self._auth(access)
        with self._lock():
            _,history,_=self._replay(self._load())
            if rid not in history:raise ManualContextError("CRM record unavailable")
            return history[rid]

    def timeline(self,access,party_id):
        self._auth(access);_id(party_id,PREFIX["party"])
        with self._lock():
            current,_,_=self._replay(self._load())
            if party_id not in current["party"]:raise ManualContextError("party unavailable")
            return sorted((x for x in current["interaction"].values() if x["party_id"]==party_id),
                          key=lambda x:_time(x["occurred_at"]))

    def export(self,access):
        self._auth(access)
        with self._lock():return self._encode(self._load())

    def restore_empty(self,access,raw):
        self._auth(access)
        with self._lock():
            if self.path.exists() or self.path.is_symlink():raise ManualContextError("restore refuses existing CRM")
            self._write(raw)
