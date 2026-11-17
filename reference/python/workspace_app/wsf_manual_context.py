"""Isolated WSF-04C manual context store candidate; not wired to live BFF.

Caller must establish current access and an effective handling policy before any
future production use. This candidate is for synthetic test directories only.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from uuid import uuid4

from workspace_app.access import AccessContext


class ManualContextError(ValueError):
    pass


SCHEMA = "arvectum.workspace.manual-context/1"
MAX_BYTES = 2 * 1024 * 1024
MAX_EVENTS = 500
HEX_ID = re.compile(r"[0-9a-f]{32}")


def _identity(access):
    if not isinstance(access, AccessContext) or access.principal_kind != "human":
        raise ManualContextError("context unavailable")
    return [[x.namespace, x.value, x.scope] for x in (access.organization, access.actor)]


def _text(value, limit):
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(ord(c) < 32 and c not in "\n\t" for c in value)):
        raise ManualContextError("invalid bounded text")
    return value


def _id(value, prefix=""):
    if not isinstance(value, str) or not value.startswith(prefix) or not HEX_ID.fullmatch(value[len(prefix):]):
        raise ManualContextError("invalid identity")
    return value


def _keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ManualContextError("invalid record shape")


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _payload(op, data):
    if op == "project":
        _keys(data, {"label", "kind"})
        _text(data["label"], 160)
        if data["kind"] not in ("customer", "internal"):
            raise ManualContextError("invalid workstream kind")
    elif op in ("capture", "revise"):
        _keys(data, {"title", "text", "project_id"} | ({"note_id", "expected_revision"} if op == "revise" else set()))
        _text(data["title"], 160)
        _text(data["text"], 4000)
        if data["project_id"] is not None:
            _id(data["project_id"], "PRJ-")
        if op == "revise":
            _id(data["note_id"], "NOTE-")
            if type(data["expected_revision"]) is not int or data["expected_revision"] < 1:
                raise ManualContextError("invalid predecessor")
    else:
        raise ManualContextError("unknown operation")
    return data


def _replay(events):
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise ManualContextError("invalid event count")
    projects, notes, requests = {}, {}, {}
    for event in events:
        _keys(event, {"key", "operation", "payload", "record_id", "at"})
        key = _id(event["key"])
        if key in requests:
            raise ManualContextError("duplicate stored request")
        op, data, rid = event["operation"], event["payload"], event["record_id"]
        _payload(op, data)
        try:
            at = datetime.fromisoformat(event["at"])
            if at.utcoffset() != timezone.utc.utcoffset(at):
                raise ValueError()
        except (ValueError, TypeError):
            raise ManualContextError("invalid event time") from None
        if op == "project":
            _id(rid, "PRJ-")
            if rid in projects:
                raise ManualContextError("duplicate project")
            projects[rid] = {"id": rid, **data, "created_at": event["at"]}
            result = projects[rid]
        else:
            _id(rid, "NOTE-")
            if data["project_id"] is not None and data["project_id"] not in projects:
                raise ManualContextError("unknown project")
            if op == "capture":
                if rid in notes:
                    raise ManualContextError("duplicate note")
                notes[rid] = []
            elif rid != data["note_id"] or rid not in notes or len(notes[rid]) != data["expected_revision"]:
                raise ManualContextError("revision conflict")
            result = {"id": rid, "revision": len(notes[rid]) + 1, "at": event["at"],
                      "title": data["title"], "text": data["text"], "project_id": data["project_id"],
                      "provenance": "manual-observation", "canonical_authority": False}
            notes[rid].append(result)
        requests[key] = (op, data, result)
    return projects, notes, requests


class ManualContextStore:
    def __init__(self, directory: Path, access: AccessContext):
        self.directory = Path(directory)
        self.scope = _identity(access)
        if not self.directory.is_absolute():
            raise ManualContextError("absolute private directory required")
        # Parent is a trusted caller-selected directory, never browser input.
        self.directory.mkdir(mode=0o700, exist_ok=True)
        s = self.directory.lstat()
        if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077:
            raise ManualContextError("unsafe private directory")
        self.path = self.directory / "context.json"

    def _authorize(self, access):
        if _identity(access) != self.scope:
            raise ManualContextError("context unavailable")

    def _open(self, path, flags):
        fd = os.open(path, flags | os.O_NOFOLLOW, 0o600)
        s = os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077 or s.st_nlink != 1:
            os.close(fd)
            raise ManualContextError("unsafe private file")
        return fd

    @contextmanager
    def _locked(self):
        fd = self._open(self.directory / ".lock", os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def _decode(self, raw):
        if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
            raise ManualContextError("snapshot size exceeded")
        try:
            obj = json.loads(raw)
            _keys(obj, {"schema", "scope", "events", "sha256"})
            if obj["schema"] != SCHEMA or obj["scope"] != self.scope:
                raise ManualContextError("scope/schema unavailable")
            unsigned = {k: v for k, v in obj.items() if k != "sha256"}
            if _digest(_json(unsigned)) != obj["sha256"] or _json(obj) != raw:
                raise ManualContextError("snapshot integrity failed")
            _replay(obj["events"])
            return obj["events"]
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, KeyError, RecursionError) as exc:
            raise ManualContextError("invalid snapshot") from exc

    def _load(self):
        try:
            fd = self._open(self.path, os.O_RDONLY)
        except FileNotFoundError:
            return []
        with os.fdopen(fd, "rb") as f:
            return self._decode(f.read(MAX_BYTES + 1))

    def _encode(self, events):
        body = {"schema": SCHEMA, "scope": self.scope, "events": events}
        return _json({**body, "sha256": _digest(_json(body))})

    def _write(self, raw):
        self._decode(raw)
        fd, name = tempfile.mkstemp(dir=self.directory, prefix=".context-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, self.path)
            dirfd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def submit(self, access: AccessContext, key: str, operation: str, payload: dict):
        self._authorize(access)
        _id(key)
        # Detach mutable caller input; reject non-JSON or unexpected fields.
        try:
            data = json.loads(_json(_payload(operation, payload)))
        except (TypeError, ValueError) as exc:
            raise ManualContextError("invalid request") from exc
        with self._locked():
            events = self._load()
            _, _, requests = _replay(events)
            if key in requests:
                op, old, result = requests[key]
                if (op, old) != (operation, data):
                    raise ManualContextError("idempotency conflict")
                return result
            if len(events) >= MAX_EVENTS:
                raise ManualContextError("event capacity exceeded")
            rid = data["note_id"] if operation == "revise" else ("PRJ-" if operation == "project" else "NOTE-") + uuid4().hex
            event = {"key": key, "operation": operation, "payload": data, "record_id": rid,
                     "at": datetime.now(timezone.utc).isoformat()}
            next_events = events + [event]
            _, _, result = _replay(next_events)
            self._write(self._encode(next_events))
            return result[key][2]

    def read(self, access: AccessContext):
        self._authorize(access)
        with self._locked():
            projects, notes, _ = _replay(self._load())
            return {"projects": list(projects.values()), "notes": [v[-1] for v in notes.values()]}

    def history(self, access: AccessContext, note_id: str):
        self._authorize(access)
        with self._locked():
            _, notes, _ = _replay(self._load())
            if note_id not in notes:
                raise ManualContextError("note unavailable")
            return notes[note_id]

    def export(self, access: AccessContext):
        self._authorize(access)
        with self._locked():
            return self._encode(self._load())

    def restore_empty(self, access: AccessContext, raw: bytes):
        self._authorize(access)
        with self._locked():
            if self.path.exists() or self.path.is_symlink():
                raise ManualContextError("restore refuses existing store")
            self._decode(raw)
            self._write(raw)
