"""Private versioned control-source cache candidate, not an authoritative register.

Only synthetic tests until explicit source/contract admission. Caller binds the
source, scope, read permission, admitted positions and existing project IDs.
No API or live path is enabled by this module.
"""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import tempfile
import json
import re

from .wsf_manual_context import ManualContextError, _identity, _keys, _json, _digest, _id
from .wsf_control_projection import project_controls, stamp, text

SCHEMA = "arvectum.workspace.control-source-cache/1"
MAX_BYTES = 2 * 1024 * 1024
MAX_REVISIONS = 100


class ControlSourceCache:
    def __init__(self, directory, access, *, source_ref, positions, project_ids):
        self.directory = Path(directory)
        self.scope = _identity(access)
        self.source_ref = text(source_ref, 500)
        self.positions = frozenset(positions)
        self.project_ids = frozenset(_id(x, "PRJ-") for x in project_ids)
        if not self.directory.is_absolute() or self.directory.resolve() != self.directory:
            raise ManualContextError("unsafe cache path")
        self.directory.mkdir(mode=0o700, exist_ok=True)
        s = self.directory.lstat()
        if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077:
            raise ManualContextError("unsafe cache directory")
        self.path = self.directory / "control-source.json"

    def _auth(self, access):
        if _identity(access) != self.scope:
            raise ManualContextError("control cache unavailable")

    def _open(self, path, flags):
        fd = os.open(path, flags | os.O_NOFOLLOW, 0o600)
        s = os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077 or s.st_nlink != 1:
            os.close(fd)
            raise ManualContextError("unsafe cache file")
        return fd

    @contextmanager
    def _lock(self):
        fd = self._open(self.directory / ".lock", os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def _validate(self, access, revisions, now):
        if not isinstance(revisions, list) or len(revisions) > MAX_REVISIONS:
            raise ManualContextError("invalid revisions")
        previous = None
        for i, revision in enumerate(revisions, 1):
            _keys(revision, {"sequence","predecessor","source_version","review_until","packet","project_links"})
            if type(revision["sequence"]) is not int or revision["sequence"] != i or revision["predecessor"] != previous:
                raise ManualContextError("revision chain invalid")
            if not isinstance(revision["source_version"], str) or not re.fullmatch("[0-9a-f]{64}",revision["source_version"]):
                raise ManualContextError("invalid source version")
            packet = revision["packet"]
            if packet["source_ref"] != self.source_ref:
                raise ManualContextError("source binding mismatch")
            if stamp(revision["review_until"]) <= stamp(packet["as_of"]):
                raise ManualContextError("review expiry invalid")
            project_controls(access, packet, admitted_scope=self.scope, admitted_positions=self.positions, now=now)
            ids={r["id"] for r in packet["records"]}
            links=revision["project_links"]
            if not isinstance(links,dict) or set(links)-ids:
                raise ManualContextError("unknown control link")
            for pid in links.values():
                if pid not in self.project_ids:
                    raise ManualContextError("unknown project link")
            if i>1:
                old=revisions[i-2]
                if stamp(packet["as_of"]) < stamp(old["packet"]["as_of"]):
                    raise ManualContextError("source timestamp regressed")
                if any(x["source_version"]==revision["source_version"] for x in revisions[:i-1]):
                    raise ManualContextError("duplicate source version")
            previous=_digest(_json(revision))

    def _encode(self, revisions):
        data={"schema":SCHEMA,"scope":self.scope,"source_ref":self.source_ref,"revisions":revisions}
        raw=_json({**data,"sha256":_digest(_json(data))})
        if len(raw)>MAX_BYTES:
            raise ManualContextError("cache capacity exceeded")
        return raw

    def _decode(self, access, raw, now):
        if not isinstance(raw,bytes) or len(raw)>MAX_BYTES:
            raise ManualContextError("cache size invalid")
        try:
            data=json.loads(raw)
            _keys(data,{"schema","scope","source_ref","revisions","sha256"})
            if data["schema"]!=SCHEMA or data["scope"]!=self.scope or data["source_ref"]!=self.source_ref:
                raise ManualContextError("cache binding mismatch")
            revisions=data["revisions"]
            if self._encode(revisions)!=raw:
                raise ManualContextError("cache integrity failed")
            self._validate(access,revisions,now)
            return revisions
        except (TypeError,KeyError,AttributeError,UnicodeError,RecursionError,ValueError) as exc:
            raise ManualContextError("invalid cache snapshot") from exc

    def _load(self,access,now):
        try:
            fd=self._open(self.path,os.O_RDONLY)
        except FileNotFoundError:
            raise ManualContextError("cache missing; explicit initialization or recovery required") from None
        with os.fdopen(fd,"rb") as f:
            return self._decode(access,f.read(MAX_BYTES+1),now)

    def _write(self,raw):
        fd,name=tempfile.mkstemp(dir=self.directory,prefix=".control-")
        try:
            with os.fdopen(fd,"wb") as f:
                f.write(raw);f.flush();os.fsync(f.fileno())
            os.replace(name,self.path)
            d=os.open(self.directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            try:os.fsync(d)
            finally:os.close(d)
        finally:
            if os.path.exists(name):os.unlink(name)

    def initialize(self,access):
        self._auth(access)
        with self._lock():
            if self.path.exists() or self.path.is_symlink():
                raise ManualContextError("cache already exists")
            self._write(self._encode([]))

    def admit_revision(self,access,*,source_version,expected_predecessor,review_until,packet,project_links,now):
        self._auth(access)
        with self._lock():
            revisions=self._load(access,now)
            detached=json.loads(_json({"source_version":source_version,"review_until":review_until,
                                      "packet":packet,"project_links":project_links}))
            for old in revisions:
                if old["source_version"]==source_version:
                    if {k:old[k] for k in detached}!=detached or old["predecessor"]!=expected_predecessor:
                        raise ManualContextError("source replay conflict")
                    return {"sequence":old["sequence"],"digest":_digest(_json(old))}
            previous=_digest(_json(revisions[-1])) if revisions else None
            if previous!=expected_predecessor:
                raise ManualContextError("source predecessor conflict")
            rev={**detached,"sequence":len(revisions)+1,"predecessor":previous}
            updated=revisions+[rev]
            self._validate(access,updated,now)
            self._write(self._encode(updated))
            return {"sequence":rev["sequence"],"digest":_digest(_json(rev))}

    def read(self,access,now):
        self._auth(access)
        with self._lock():
            revisions=self._load(access,now)
            if not revisions:
                return project_controls(access,None,admitted_scope=self.scope,admitted_positions=self.positions,now=now)
            rev=revisions[-1]
            packet=json.loads(_json(rev["packet"]))
            expired=stamp(now)>=stamp(rev["review_until"])
            if expired:
                for row in packet["records"]:
                    if row["freshness"] in {"current_for_declared_use","not_time_sensitive"}:
                        row["freshness"]="stale_for_declared_use"
            result=project_controls(access,packet,admitted_scope=self.scope,admitted_positions=self.positions,now=now)
            # Historical records missing from a partial snapshot are not closed.
            prior={r["id"] for v in revisions[:-1] for r in v["packet"]["records"]}
            current={r["id"] for r in packet["records"]}
            result.update(source_version=rev["source_version"],review_expired=expired,
                          missing_from_latest=sorted(prior-current),project_links=rev["project_links"])
            return result

    def history(self,access,rid,now):
        self._auth(access)
        with self._lock():
            return [{"sequence":v["sequence"],"source_version":v["source_version"],
                     "record":r,"project_id":v["project_links"].get(rid)}
                    for v in self._load(access,now) for r in v["packet"]["records"] if r["id"]==rid]

    def export(self,access,now):
        self._auth(access)
        with self._lock():
            return self._encode(self._load(access,now))

    def restore_empty(self,access,raw,now):
        self._auth(access)
        with self._lock():
            if self.path.exists() or self.path.is_symlink():
                raise ManualContextError("restore refuses existing cache")
            self._decode(access,raw,now)
            self._write(raw)
