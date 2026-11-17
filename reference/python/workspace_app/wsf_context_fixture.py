"""WSF-03 isolated in-memory context prototype. No route, storage or runtime wiring.

AccessContext is assumed to have been resolved by the caller; this module is
not an authentication or organizational-authority provider. Fixture use only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from uuid import uuid4

from workspace_app.access import AccessContext


class ContextError(ValueError):
    pass


Scope = tuple[tuple[str, str, str], tuple[str, str, str]]


def _scope(access: AccessContext) -> Scope:
    if not isinstance(access, AccessContext) or access.principal_kind != "human":
        raise ContextError("context unavailable")
    return tuple((x.namespace, x.value, x.scope) for x in (access.organization, access.actor))  # type: ignore[return-value]


def _text(value: str, limit: int = 320) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ContextError("invalid bounded metadata")
    return value


def _time(value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ContextError("timezone-aware observation required")


@dataclass(frozen=True)
class SourceBinding:
    binding_id: str
    source_kind: str
    scope: Scope
    purpose: str
    rights: str
    retention_rule: str
    classification: str

    def __post_init__(self):
        if self.source_kind not in {"fixture-manual", "fixture-roadmap"}:
            raise ContextError("source kind not admitted in prototype")
        for value in (self.binding_id, self.purpose, self.rights, self.retention_rule, self.classification):
            _text(value)


@dataclass(frozen=True)
class SourceRef:
    binding_id: str
    native_id: str
    revision: str
    digest: str
    observed_at: datetime
    predecessor_revision: str | None = None

    def __post_init__(self):
        for value in (self.binding_id, self.native_id, self.revision):
            _text(value)
        if not isinstance(self.digest, str) or not re.fullmatch(r"[0-9a-f]{64}", self.digest):
            raise ContextError("exact content digest required")
        _time(self.observed_at)
        if self.predecessor_revision is not None:
            _text(self.predecessor_revision)
            if self.predecessor_revision == self.revision:
                raise ContextError("self predecessor")

    @property
    def object_key(self) -> tuple[str, str]:
        return self.binding_id, self.native_id


@dataclass(frozen=True)
class Workstream:
    id: str
    label: str
    kind: str
    parent_port: str | None


@dataclass(frozen=True)
class InboxItem:
    id: str
    source: SourceRef
    title: str


@dataclass(frozen=True)
class LinkEvent:
    item_id: str
    workstream_id: str
    state: str
    at: datetime


class FixtureContext:
    """One organization/actor scope, append-only fixture history, no external effects."""

    def __init__(self, access: AccessContext, bindings: tuple[SourceBinding, ...], approved_ports: frozenset[str]):
        self._scope = _scope(access)
        self._bindings = {}
        for binding in bindings:
            if binding.scope != self._scope or binding.binding_id in self._bindings:
                raise ContextError("invalid fixture source binding")
            self._bindings[binding.binding_id] = binding
        self._ports = frozenset(approved_ports)
        if any(not re.fullmatch(r"PORT-[0-9]{3}", p) for p in self._ports):
            raise ContextError("invalid portfolio reference")
        self._workstreams: dict[str, Workstream] = {}
        self._items: dict[str, InboxItem] = {}
        self._revisions: dict[tuple[str, str, str], str] = {}
        self._latest: dict[tuple[str, str], str] = {}
        self._links: list[LinkEvent] = []
        self._revoked: set[str] = set()

    def _authorize(self, access: AccessContext) -> None:
        if _scope(access) != self._scope:
            raise ContextError("context unavailable")

    def _binding(self, binding_id: str) -> SourceBinding:
        binding = self._bindings.get(binding_id)
        if binding is None or binding_id in self._revoked:
            raise ContextError("source unavailable")
        return binding

    def create_workstream(self, access: AccessContext, label: str, kind: str, *, parent_port: str | None = None) -> Workstream:
        self._authorize(access)
        if kind not in {"customer", "internal"}:
            raise ContextError("invalid workstream kind")
        if parent_port is not None and parent_port not in self._ports:
            raise ContextError("unregistered portfolio reference")
        result = Workstream("PRJ-" + uuid4().hex, _text(label), kind, parent_port)
        self._workstreams[result.id] = result
        return result

    def receive(self, access: AccessContext, source: SourceRef, title: str) -> InboxItem:
        self._authorize(access)
        self._binding(source.binding_id)
        title = _text(title)
        revision_key = (*source.object_key, source.revision)
        existing_id = self._revisions.get(revision_key)
        if existing_id is not None:
            existing = self._items[existing_id]
            if (existing.source.digest, existing.source.predecessor_revision, existing.title) != (
                source.digest, source.predecessor_revision, title
            ):
                raise ContextError("conflicting source revision")
            return existing
        if self._latest.get(source.object_key) != source.predecessor_revision:
            raise ContextError("unknown or non-current predecessor")
        item = InboxItem("INBOX-" + uuid4().hex, source, title)
        self._items[item.id] = item
        self._revisions[revision_key] = item.id
        self._latest[source.object_key] = source.revision
        return item

    def _visible_item(self, item_id: str) -> InboxItem:
        item = self._items.get(item_id)
        if item is None or item.source.binding_id in self._revoked:
            raise ContextError("item unavailable")
        self._binding(item.source.binding_id)
        return item

    def propose_link(self, access: AccessContext, item_id: str, workstream_id: str, at: datetime) -> LinkEvent:
        self._authorize(access)
        self._visible_item(item_id)
        _time(at)
        if workstream_id not in self._workstreams:
            raise ContextError("workstream unavailable")
        previous = self._last_link(item_id, workstream_id)
        if previous is not None:
            raise ContextError("link already proposed or resolved")
        event = LinkEvent(item_id, workstream_id, "proposed", at)
        self._links.append(event)
        return event

    def _last_link(self, item_id: str, workstream_id: str) -> LinkEvent | None:
        return next((x for x in reversed(self._links) if (x.item_id, x.workstream_id) == (item_id, workstream_id)), None)

    def review_link(self, access: AccessContext, item_id: str, workstream_id: str, state: str, at: datetime) -> LinkEvent:
        self._authorize(access)
        self._visible_item(item_id)
        _time(at)
        previous = self._last_link(item_id, workstream_id)
        if previous is None or at < previous.at:
            raise ContextError("invalid link review history")
        allowed = {"proposed": {"confirmed", "rejected"}, "confirmed": {"superseded"}}
        if state not in allowed.get(previous.state, set()):
            raise ContextError("invalid link review transition")
        event = LinkEvent(item_id, workstream_id, state, at)
        self._links.append(event)
        return event

    def inbox(self, access: AccessContext) -> tuple[InboxItem, ...]:
        self._authorize(access)
        return tuple(x for x in self._items.values() if x.source.binding_id not in self._revoked
                     and self._latest[x.source.object_key] == x.source.revision)

    def timeline(self, access: AccessContext, workstream_id: str) -> tuple[InboxItem, ...]:
        self._authorize(access)
        if workstream_id not in self._workstreams:
            raise ContextError("workstream unavailable")
        result = []
        for item in self.inbox(access):
            latest = self._last_link(item.id, workstream_id)
            if latest is not None and latest.state == "confirmed":
                result.append(item)
        return tuple(sorted(result, key=lambda item: (item.source.observed_at, item.id)))

    def revoke_fixture_source(self, access: AccessContext, binding_id: str) -> None:
        self._authorize(access)
        self._binding(binding_id)
        self._revoked.add(binding_id)
