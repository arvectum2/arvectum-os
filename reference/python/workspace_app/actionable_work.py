from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import urlsplit

from .access import AccessContext


class ActionableWorkError(RuntimeError):
    """Actionable Work source evidence is unavailable, unsafe, or inconsistent."""


def _identity_key(identity: object) -> tuple[str, str, str]:
    return (identity.namespace, identity.value, identity.scope)  # type: ignore[attr-defined]


def _bounded_text(value: str, *, label: str, limit: int) -> str:
    if not isinstance(value, str):
        raise ActionableWorkError(f"{label} must be text")
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > limit:
        raise ActionableWorkError(f"{label} outside bounded length")
    return normalized


def _entry_href(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = _bounded_text(value, label="entry href", limit=512)
    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/") or parsed.path.startswith("//"):
        raise ActionableWorkError("entry href must be a same-origin Workspace path")
    if parsed.fragment:
        raise ActionableWorkError("entry href fragments are not admitted")
    if parsed.path.startswith("/api/") or parsed.path == "/governed" or parsed.path.startswith("/governed/"):
        raise ActionableWorkError("entry href cannot bypass the no-side-effect product/company context boundary")
    return candidate


@dataclass(frozen=True, slots=True)
class ActionableWorkRequest:
    """A projection input for an already-real product/company-owned request.

    This is deliberately not a Kernel Subject, universal Task, approval request,
    or execution command. A source adapter may contribute one only after the
    owning product/company source has independently established that the request
    exists in the current AccessContext.
    """

    organization_key: tuple[str, str, str]
    actor_key: tuple[str, str, str]
    source_kind: str
    source_id: str
    source_label: str
    request_ref: str
    title: str
    context: str
    attention_reason: str
    source_state: str
    freshness: str
    observed_at: datetime
    next_steps: tuple[str, ...]
    entry_href: str | None
    source_authority: str
    product_contract_id: str
    product_contract_version: str
    product_contract_lifecycle: str
    preflight_state: str
    provenance_refs: tuple[str, ...]

    def validated(self, access: AccessContext) -> "ActionableWorkRequest":
        if self.organization_key != _identity_key(access.organization) or self.actor_key != _identity_key(access.actor):
            raise ActionableWorkError("Actionable Work request scope does not match current Organization/Actor")
        if self.source_kind not in {"product", "company"}:
            raise ActionableWorkError("Actionable Work source kind is not admitted")
        if self.freshness not in {"fresh", "stale", "unknown"}:
            raise ActionableWorkError("Actionable Work freshness is invalid")
        if self.product_contract_lifecycle not in {"Provisional", "Stable"}:
            raise ActionableWorkError("Actionable Work requires an effective Product Contract lifecycle")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ActionableWorkError("Actionable Work observation time must be timezone-aware")
        _bounded_text(self.source_id, label="source id", limit=128)
        _bounded_text(self.source_label, label="source label", limit=160)
        _bounded_text(self.request_ref, label="source request reference", limit=240)
        _bounded_text(self.title, label="title", limit=320)
        _bounded_text(self.context, label="context", limit=2000)
        _bounded_text(self.attention_reason, label="attention reason", limit=600)
        _bounded_text(self.source_state, label="source state", limit=96)
        _bounded_text(self.source_authority, label="source authority", limit=320)
        _bounded_text(self.product_contract_id, label="Product Contract id", limit=160)
        _bounded_text(self.product_contract_version, label="Product Contract version", limit=64)
        _bounded_text(self.preflight_state, label="preflight state", limit=160)
        if not self.next_steps or len(self.next_steps) > 8:
            raise ActionableWorkError("Actionable Work next-step descriptions must be bounded and non-empty")
        for value in self.next_steps:
            _bounded_text(value, label="next-step description", limit=320)
        if not self.provenance_refs or len(self.provenance_refs) > 16:
            raise ActionableWorkError("Actionable Work provenance must be explicit and bounded")
        for value in self.provenance_refs:
            _bounded_text(value, label="provenance reference", limit=320)
        _entry_href(self.entry_href)
        return self

    @property
    def projection_id(self) -> str:
        source_id = _bounded_text(self.source_id, label="source id", limit=128)
        request_ref = _bounded_text(self.request_ref, label="source request reference", limit=240)
        raw = f"{self.source_kind}\0{source_id}\0{request_ref}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:24]

    def to_payload(self) -> dict[str, Any]:
        href = _entry_href(self.entry_href)
        entry_available = self.freshness == "fresh" and href is not None
        return {
            "id": self.projection_id,
            "title": _bounded_text(self.title, label="title", limit=320),
            "context": _bounded_text(self.context, label="context", limit=2000),
            "attention_reason": _bounded_text(self.attention_reason, label="attention reason", limit=600),
            "source": {
                "kind": self.source_kind,
                "id": _bounded_text(self.source_id, label="source id", limit=128),
                "label": _bounded_text(self.source_label, label="source label", limit=160),
                "request_ref": _bounded_text(self.request_ref, label="source request reference", limit=240),
                "authority": _bounded_text(self.source_authority, label="source authority", limit=320),
                "state": _bounded_text(self.source_state, label="source state", limit=96),
                "freshness": self.freshness,
                "observed_at": self.observed_at.astimezone(timezone.utc).isoformat(),
                "product_contract": {
                    "id": _bounded_text(self.product_contract_id, label="Product Contract id", limit=160),
                    "version": _bounded_text(self.product_contract_version, label="Product Contract version", limit=64),
                    "lifecycle": self.product_contract_lifecycle,
                },
            },
            "next_steps": [
                _bounded_text(value, label="next-step description", limit=320)
                for value in self.next_steps
            ],
            "governed_execution": {
                "preflight_state": _bounded_text(self.preflight_state, label="preflight state", limit=160),
                "current_gate_revalidation_required_for_effect": True,
                "consequential_action_available": False,
                "organizational_authority_provided": False,
                "consequential_approval_provided": False,
            },
            "entry": {
                "kind": "no-side-effect-context-entry",
                "available": entry_available,
                "href": href if entry_available else None,
                "consequential": False,
                "canonical_mutation_requested": False,
                "external_effect_requested": False,
                "authority_provided": False,
                "executes_product_operation": False,
            },
            "technical": {
                "provenance_refs": [
                    _bounded_text(value, label="provenance reference", limit=320)
                    for value in self.provenance_refs
                ],
                "exact_source_request_ref_available": True,
            },
        }


@dataclass(frozen=True, slots=True)
class ActionableWorkProjection:
    items: tuple[ActionableWorkRequest, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema": "arvectum.workspace.actionable-work/1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "projection": {
                "derived": True,
                "canonical_authority": False,
                "creates_requests": False,
                "universal_task_primitive": False,
                "product_semantics_owned_by_platform": False,
                "organizational_authority_provided": False,
                "urgency_inferred": False,
                "owner_responsibility_inferred": False,
                "approval_requirement_inferred": False,
                "action_availability_inferred": False,
            },
            "scope": {
                "organization_resolved_server_side": True,
                "actor_resolved_server_side": True,
                "current_workspace_access_revalidated": True,
                "denied_request_counts_exposed": False,
            },
            "items": [item.to_payload() for item in self.items],
        }


class ActionableWorkSource(Protocol):
    def collect(self, access: AccessContext) -> tuple[ActionableWorkRequest, ...]: ...


class ActionableWorkProvider(Protocol):
    def project(self, access: AccessContext) -> ActionableWorkProjection: ...


class RuntimeActionableWorkProvider:
    """Compose current product/company-owned requests without manufacturing them.

    P10.06 intentionally registers no default sources. Product/company adapters may
    be added only when their owning source and effective Product Contract supply a
    real request. The platform owns the safe projection envelope, not request
    creation, urgency, approval rules, responsibility, or product execution.
    """

    def __init__(self, sources: tuple[ActionableWorkSource, ...] = ()) -> None:
        self.sources = sources

    def project(self, access: AccessContext) -> ActionableWorkProjection:
        items: list[ActionableWorkRequest] = []
        seen: set[str] = set()
        for source in self.sources:
            try:
                contributed = source.collect(access)
            except ActionableWorkError:
                raise
            except Exception as exc:
                raise ActionableWorkError("Actionable Work source failed closed") from exc
            if not isinstance(contributed, tuple):
                raise ActionableWorkError("Actionable Work source must return an immutable tuple")
            for item in contributed:
                if not isinstance(item, ActionableWorkRequest):
                    raise ActionableWorkError("Actionable Work source returned an invalid request type")
                item.validated(access)
                if item.projection_id in seen:
                    raise ActionableWorkError("duplicate Actionable Work projection identity")
                seen.add(item.projection_id)
                items.append(item)
        return ActionableWorkProjection(tuple(items))


__all__ = [
    "ActionableWorkError",
    "ActionableWorkProvider",
    "ActionableWorkProjection",
    "ActionableWorkRequest",
    "ActionableWorkSource",
    "RuntimeActionableWorkProvider",
]
