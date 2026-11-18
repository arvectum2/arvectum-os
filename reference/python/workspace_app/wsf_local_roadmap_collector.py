"""WSF-07A 0.6.2 isolated candidate, not wired to live runtime."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import stat

import p7_04_persistent_access as p704
from .access import AccessContext
from .wsf_manual_context import ManualContextError, _identity, _json, _digest, _keys, MAX_BYTES, MAX_EVENTS
from .wsf_control_projection import stamp
from .wsf_roadmap_inbox import RoadmapInbox, _InboxFile, registry_bindings, metadata_snapshot, SCHEMA as LEGACY_SCHEMA
from .company_portfolio_verified import VerifiedRuntimeCompanyPortfolioProvider

ACTIVE = frozenset(("COMPANY","OS","PORT-001","PORT-002","PORT-003","PORT-004","PORT-007","PORT-008"))
EXCLUDED = frozenset(("PORT-005","PORT-006"))
REGISTRY_SHA = "aa21ce050441c50f4b68c9dc7b16ebe43b1a5a29d4a98059a8616b35c2849016"
REGISTRY = Path(__file__).with_name("company_project_registry_061.json")
SCHEMA = "arvectum.workspace.roadmap-inbox/2"
RESOURCE = "roadmap-inbox"
OPERATION = "workspace.inbox.collect"
EXPIRY = datetime.fromisoformat("2026-12-17T09:35:36.060836+00:00")
INTERVAL = 10800
HEX32 = re.compile("[0-9a-f]{32}")
HEX64 = re.compile("[0-9a-f]{64}")

def _utc():
    return datetime.now(timezone.utc)

def _ident(i):
    return [i.namespace,i.value,i.scope]

def exact_registry():
    b=registry_bindings(REGISTRY)
    if (_digest(_json(b))!=REGISTRY_SHA or set(b)!=ACTIVE|EXCLUDED
        or any(not b[k]["repository"] or not b[k]["path"] for k in ACTIVE)
        or any(b[k]["path"] is not None for k in EXCLUDED)):
        raise ManualContextError("collector registry mismatch")
    return b

@dataclass(frozen=True)
class ServicePolicy:
    owner_scope: tuple
    organization: object
    principal: object
    credential_id: str
    grant_id: str
    release_sha: str
    starts_at: datetime
    expires_at: datetime

    def validate(self, access, now):
        scope=[list(i) for i in self.owner_scope]
        if (len(scope)!=2 or scope[0]!=_ident(self.organization)
            or not isinstance(access,AccessContext) or access.principal_kind!="service"
            or access.organization!=self.organization or access.actor!=self.principal
            or _ident(access.actor)==scope[1]
            or access.credential_id!=self.credential_id or access.grant_id!=self.grant_id
            or not HEX32.fullmatch(self.credential_id) or not HEX32.fullmatch(self.grant_id)
            or not re.fullmatch("[0-9a-f]{40}",self.release_sha)
            or not self.starts_at<=now<self.expires_at<=EXPIRY):
            raise ManualContextError("collector policy denied")
        return access

    def resolve(self,root,now=None):
        root=Path(root); now=now or _utc()
        current=root/"current"
        if (not current.is_symlink() or current.resolve()!=root/"releases"/self.release_sha
            or (root/"run"/"p7-06-deploy.lock").exists()):
            raise ManualContextError("collector release mismatch")
        if not HEX32.fullmatch(self.credential_id):
            raise ManualContextError("collector credential invalid")
        d=p704.authorize_from_credential_file(root,organization=self.organization,
            principal=self.principal,credential_id=self.credential_id,
            credential_file=root/"secrets"/"p7-04"/(self.credential_id+".secret"),
            operation=OPERATION,resource=RESOURCE,access_path="local")
        if not d.allowed or d.principal_kind!="service" or d.grant_id!=self.grant_id:
            raise ManualContextError("collector grant denied")
        return self.validate(AccessContext(self.organization,self.principal,d.principal_kind,
            self.credential_id,d.grant_id),now)

def window_key(org,window):
    return _digest(_json([org,RESOURCE,OPERATION,window]))[:32]

class _CollectorFile(_InboxFile):
    """Human APIs retain inherited human-only _authorize; service has no export."""
    def __init__(self,directory,owner_scope,legacy_sha,legacy_event_count,*,create=False):
        directory=Path(directory)
        if not directory.is_absolute() or directory.resolve()!=directory:
            raise ManualContextError("unsafe collector directory")
        if create:directory.mkdir(mode=0o700,exist_ok=False)
        s=directory.lstat()
        if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode&0o077:
            raise ManualContextError("unsafe collector directory")
        if (not isinstance(owner_scope,list) or len(owner_scope)!=2 or
            any(not isinstance(i,list) or len(i)!=3 or any(not isinstance(v,str) or not v for v in i) for i in owner_scope)
            or not HEX64.fullmatch(legacy_sha) or type(legacy_event_count) is not int
            or not 0<=legacy_event_count<=MAX_EVENTS):
            raise ManualContextError("invalid owner or legacy binding")
        self.directory=directory; self.path=directory/"inbox.json"; self.require_initialized=True
        self.scope=json.loads(_json(owner_scope)); self.legacy_sha=legacy_sha
        self.legacy_event_count=legacy_event_count
        self.bindings=exact_registry(); self.binding_digest=REGISTRY_SHA

    def _encode(self,events):
        body={"schema":SCHEMA,"resource":{"organization":self.scope[0],"name":RESOURCE},
              "legacy_owner":self.scope[1],"legacy_sha256":self.legacy_sha,"legacy_event_count":self.legacy_event_count,
              "registry_sha256":REGISTRY_SHA,"active":sorted(ACTIVE),"excluded":sorted(EXCLUDED),"events":events}
        raw=_json({**body,"sha256":_digest(_json(body))})
        if len(raw)>MAX_BYTES:raise ManualContextError("inbox capacity exceeded")
        return raw

    def _decode(self,raw):
        if not isinstance(raw,bytes) or len(raw)>MAX_BYTES:raise ManualContextError("inbox size invalid")
        try:
            data=json.loads(raw);events=data["events"]
            if self._encode(events)!=raw:raise ManualContextError("collector integrity or scope mismatch")
            if not isinstance(events,list) or len(events)<self.legacy_event_count:
                raise ManualContextError("legacy prefix missing")
            old={"schema":LEGACY_SCHEMA,"scope":self.scope,"registry_sha256":REGISTRY_SHA,
                 "events":events[:self.legacy_event_count]}
            if _digest(_json({**old,"sha256":_digest(_json(old))}))!=self.legacy_sha:
                raise ManualContextError("legacy prefix differs from original bytes")
            self.replay(events)
            return events
        except (KeyError,TypeError,ValueError,UnicodeError,RecursionError) as exc:
            raise ManualContextError("invalid collector snapshot") from exc

    def replay(self,events):
        if not isinstance(events,list) or len(events)>MAX_EVENTS:raise ManualContextError("inbox event limit")
        normalized=[]
        for e in events:
            if not isinstance(e,dict):raise ManualContextError("invalid event")
            if e.get("operation")!="service-scan":
                normalized.append(e);continue
            _keys(e,{"key","operation","at","data"})
            d=e["data"];_keys(d,{"observations","executor","window"})
            a=d["executor"];_keys(a,{"organization","principal","kind","credential_id","grant_id","release_sha","operation","resource","access_path"})
            if (a["organization"]!=self.scope[0] or a["kind"]!="service" or
                not isinstance(a["principal"],list) or len(a["principal"])!=3 or
                any(not isinstance(v,str) or not v for v in a["principal"]) or
                a["principal"]==self.scope[1] or
                not HEX32.fullmatch(a["credential_id"]) or not HEX32.fullmatch(a["grant_id"]) or
                not re.fullmatch("[0-9a-f]{40}",a["release_sha"]) or
                (a["operation"],a["resource"],a["access_path"])!=(OPERATION,RESOURCE,"local")
                or type(d["window"]) is not int or d["window"]<0
                or d["window"]!=int(stamp(e["at"]).timestamp())//INTERVAL
                or e["key"]!=window_key(self.scope[0],d["window"])):
                raise ManualContextError("invalid service attribution")
            for pid in EXCLUDED:
                if d["observations"].get(pid)!={"state":"reconciliation-required","source":None}:
                    raise ManualContextError("excluded source collected")
            normalized.append({**e,"operation":"scan","data":d["observations"]})
        latest,items,_=super().replay(normalized)
        return latest,items,{e["key"]:e for e in events}

    @contextmanager
    def cycle_lock(self):
        fd=self._open(self.directory/".collector-cycle.lock",os.O_CREAT|os.O_RDWR)
        try:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise ManualContextError("collector cycle busy") from None
            yield
        finally:os.close(fd)

class CollectorInbox(RoadmapInbox):
    def __init__(self,directory,owner_scope,legacy_sha,legacy_event_count,*,create=False):
        self.file=_CollectorFile(directory,owner_scope,legacy_sha,legacy_event_count,create=create)

    def read(self,access,now=None):
        f=self.file;f._authorize(access)
        checked=stamp(now or _utc().isoformat())
        with f._locked():
            events=f._load();sources,items,_=f.replay(events)
            for row in sources.values():
                row["freshness"]="current-observation" if row["state"]=="current-source-backed" and 0<=(checked-stamp(row["checked_at"])).total_seconds()<=4*3600 else "requires-refresh"
            active=[sources.get(k,{"source_id":k,"state":"unavailable","freshness":"requires-refresh","checkpoint":None,"checked_at":None}) for k in sorted(ACTIVE)]
            excluded=[sources.get(k,{"source_id":k,"state":"reconciliation-required","freshness":"requires-refresh","checkpoint":None,"checked_at":None}) for k in sorted(EXCLUDED)]
            service=[e for e in events if e["operation"]=="service-scan"]
            size=len(f._encode(events))
            return {"derived":True,"coverage":"partial" if sources else "unknown","canonical_authority":False,
                    "organizational_authority_provided":False,"sources":active,"excluded_sources":excluded,
                    "items":list(items.values()),"pending_count":sum(x["state"]=="pending" for x in items.values()),
                    "collector":{"last_service_scan_at":service[-1]["at"] if service else None,
                    "event_count":len(events),"bytes":size,"capacity_warning":len(events)>=MAX_EVENTS*.8 or size>=MAX_BYTES*.8}}

    def capacity(self,access):
        f=self.file;f._authorize(access)
        with f._locked():
            ev=f._load();size=len(f._encode(ev))
        return {"events":len(ev),"bytes":size,"warning":len(ev)>=MAX_EVENTS*.8 or size>=MAX_BYTES*.8}

def rehearse_migration(legacy,owner,verified_backup,target_dir):
    """Isolated preparation only. No production path selection or cutover."""
    raw=legacy.export(owner)
    if raw!=verified_backup or legacy.file.binding_digest!=REGISTRY_SHA:
        raise ManualContextError("migration requires exact verified predecessor")
    events=legacy.file._decode(raw)
    new=CollectorInbox(target_dir,_identity(owner),_digest(raw),len(events),create=True)
    candidate=new.file._encode(events)
    new.restore_empty(owner,candidate)
    if new.file._decode(new.export(owner))!=events:
        raise ManualContextError("migration history changed")
    return new,raw,candidate

class _BackupStore:
    """Internal backup capability, deliberately not a public export route."""
    def __init__(self,file,policy,resolve):
        self._file=file;self._policy=policy;self._resolve=resolve
    def _authorize(self,access):
        current=self._resolve()
        self._policy.validate(current,_utc())
        if current!=access:raise ManualContextError("backup grant changed")
    def __getattr__(self,key):
        if key not in {"directory","path","_locked","_load","_encode","_decode"}:
            raise AttributeError(key)
        return getattr(self._file,key)

def collect_cycle(inbox,policy,provider,resolve,*,backup_factory):
    """One isolated service cycle; production provisioning is not included."""
    f=inbox.file
    if [list(i) for i in policy.owner_scope]!=f.scope or f.bindings!=exact_registry():
        raise ManualContextError("collector resource mismatch")
    if not isinstance(provider,VerifiedRuntimeCompanyPortfolioProvider) or provider.cache is not None:
        raise ManualContextError("collector requires uncached verified provider")
    descriptors={d.project_id:{"repository":d.repository,"path":d.roadmap_path,"adapter":d.adapter}
                 for d in provider._descriptors}
    if descriptors!=f.bindings or len(provider._descriptors)!=len(descriptors):
        raise ManualContextError("collector source registry mismatch")
    with f.cycle_lock():
        now=_utc(); a=policy.validate(resolve(),now)
        window=int(now.timestamp())//INTERVAL;key=window_key(f.scope[0],window)
        backup=backup_factory(_BackupStore(f,policy,resolve))
        with f._locked():
            events=f._load(); raw=f._encode(events); _,_,seen=f.replay(events)
        if backup.verified_snapshot(a)!=raw:
            raise ManualContextError("collector backup reconciliation required")
        if key in seen:
            if seen[key]["operation"]!="service-scan":
                raise ManualContextError("collector idempotency conflict")
            return {"status":"already-collected","backup_status":"verified"}
        if len(events)>=MAX_EVENTS:
            raise ManualContextError("inbox event capacity exceeded")
        backup.copy_latest(a)
        projection=provider.project(a,force_refresh=True)
        checked=_utc()
        rows=metadata_snapshot(projection,f.bindings,checked.isoformat())
        if int(checked.timestamp())//INTERVAL!=window:
            raise ManualContextError("collector window elapsed; no commit")
        executor={"organization":_ident(a.organization),"principal":_ident(a.actor),"kind":"service",
                  "credential_id":a.credential_id,"grant_id":a.grant_id,"release_sha":policy.release_sha,
                  "operation":OPERATION,"resource":RESOURCE,"access_path":"local"}
        with f._locked():
            events=f._load();current=policy.validate(resolve(),_utc())
            if current!=a:raise ManualContextError("collector grant changed")
            if f._encode(events)!=raw:raise ManualContextError("inbox changed during collection")
            event={"key":key,"operation":"service-scan","at":checked.isoformat(),
                   "data":{"observations":rows,"executor":executor,"window":window}}
            candidate=f._encode(events+[event]); f._write(candidate)
        try:
            backup.copy_latest(a)
            if backup.verified_snapshot(a)!=candidate:raise ManualContextError("post-backup differs")
            status="verified"
        except (OSError,ManualContextError):
            status="saved-primary-backup-unavailable"
        return {"status":"saved","backup_status":status,"active":len(ACTIVE),
                "current":sum(rows[k]["state"]=="current-source-backed" for k in ACTIVE),
                "excluded":len(EXCLUDED),"capacity_warning":len(events)+1>=MAX_EVENTS*.8 or len(candidate)>=MAX_BYTES*.8}
