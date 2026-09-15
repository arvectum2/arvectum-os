"""P10.05 Company-owned generated-output review and promotion composition.

Review/disposition state is product-local and explicitly non-canonical.  A
TransientOutput remains transient after review and even after a successful
promotion; the successful governed operation creates a separate immutable
Document/Artifact version and Organizational Asset designation instead of
relabeling the source file.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from arvectum_os_ref.document_artifact_governance import DocumentVersionCandidate
from arvectum_os_ref.governed_execution import GovernedExecutionContext
from arvectum_os_ref.identity import Identity
from arvectum_os_ref.integration_adapters import IntegrationCapabilityAdapter
from arvectum_os_ref.organizational_asset_admission import (
    AssetAdmissionAuthorityEvidence,
    AssetAdmissionControlPins,
)
from arvectum_os_ref.reviewed_generated_output_promotion import (
    ExactGeneratedOutputSource,
    ReviewedGeneratedOutputPromotionRequest,
    ReviewedGeneratedOutputPromotionState,
    promote_reviewed_generated_output,
)
from arvectum_os_ref.security import ActorContext

from .access import AccessContext
from .company_asset_library import P1003CompanyAssetAdmissionExecutor
from .company_generated_output_promotion import (
    ExactCompanyGeneratedOutput,
    build_generated_output_document_candidate,
    exact_generated_output_source_identities,
    resolve_exact_generated_output,
)
from .company_materials import (
    CompanyMaterialUnavailable,
    CompanyMaterialsError,
    CompanyMaterialsStore,
    _atomic_json,
    _identity_text as _store_identity_text,
    _utc_now,
)


_SAFE_OUTPUT_ID = re.compile(r"^OUT-[A-Za-z0-9_.-]{8,96}$")
_DISPOSITIONS = frozenset({"PendingReview", "Rejected", "KeepTransient", "PromotionRequested"})


class CompanyGeneratedOutputError(RuntimeError):
    pass


class CompanyGeneratedOutputReviewError(ValueError, CompanyGeneratedOutputError):
    pass


class CompanyGeneratedOutputPromotionUnavailable(CompanyGeneratedOutputError):
    pass


def _bounded(value: object, *, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise CompanyGeneratedOutputReviewError(f"{field} must be text")
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > maximum or "\x00" in normalized:
        raise CompanyGeneratedOutputReviewError(f"{field} is outside the bounded P10.05 contract")
    return normalized


def _identity_text(identity: Identity) -> str:
    return f"{identity.namespace}:{identity.scope}:{identity.value}"


def _handling_payload(output: ExactCompanyGeneratedOutput) -> dict[str, Any]:
    return {
        "classification": output.handling.classification,
        "purpose": output.handling.purpose,
        "rights": list(output.handling.rights),
        "retention_rule": output.handling.retention_rule,
        "deletion_rule": output.handling.deletion_rule,
        "permitted_reuse": list(output.handling.permitted_reuse),
    }


def _digest_payload(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()[:24]


@dataclass(frozen=True, slots=True)
class CompanyGeneratedOutputReviewEvidence:
    output_id: str
    disposition: str
    updated_at: str
    actor: str
    output_sha256: str
    document_title: str
    semantic_role: str
    handling_digest: str
    source_document_version: Identity
    source_artifact_id: Identity
    source_designation_version: Identity
    review_digest: str

    def __post_init__(self) -> None:
        if self.disposition != "PromotionRequested":
            raise CompanyGeneratedOutputPromotionUnavailable(
                "promotion requires an explicit current PromotionRequested review disposition"
            )
        if len(self.output_sha256) != 64 or len(self.handling_digest) != 24 or len(self.review_digest) != 24:
            raise CompanyGeneratedOutputPromotionUnavailable("exact promotion review evidence is incomplete")
        for value in (
            self.source_document_version,
            self.source_artifact_id,
            self.source_designation_version,
        ):
            if not isinstance(value, Identity):
                raise CompanyGeneratedOutputPromotionUnavailable("source promotion evidence must use exact identities")


@dataclass(frozen=True, slots=True)
class PromotedCompanyGeneratedOutput:
    output_id: str
    document_subject: str
    document_version: str
    designation_subject: str
    designation_version: str
    event_version: str
    promoted_at: str
    provenance_refs: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "output_id": self.output_id,
            "document_subject": self.document_subject,
            "document_version": self.document_version,
            "designation_subject": self.designation_subject,
            "designation_version": self.designation_version,
            "event_version": self.event_version,
            "promoted_at": self.promoted_at,
            "provenance_refs": list(self.provenance_refs),
        }


@dataclass(frozen=True, slots=True)
class PreparedCompanyGeneratedOutputPromotion:
    actor: ActorContext
    capability_adapter: IntegrationCapabilityAdapter
    execution: GovernedExecutionContext
    authority: AssetAdmissionAuthorityEvidence
    occurred_at: datetime
    recorded_at: datetime


class CompanyGeneratedOutputGovernedProvider(Protocol):
    def available(self, access: AccessContext) -> bool: ...
    def actor_for(self, access: AccessContext) -> ActorContext: ...
    def prepare(
        self,
        *,
        access: AccessContext,
        candidate: DocumentVersionCandidate,
        output: ExactCompanyGeneratedOutput,
        review: CompanyGeneratedOutputReviewEvidence,
    ) -> PreparedCompanyGeneratedOutputPromotion: ...


class CompanyGeneratedOutputPromotionExecutor(Protocol):
    def available(self, access: AccessContext) -> bool: ...
    def promoted_outputs(self, access: AccessContext) -> tuple[PromotedCompanyGeneratedOutput, ...]: ...
    def promote(
        self,
        *,
        access: AccessContext,
        store: CompanyMaterialsStore,
        output_id: str,
        review: CompanyGeneratedOutputReviewEvidence,
    ) -> PromotedCompanyGeneratedOutput: ...


class UnavailableCompanyGeneratedOutputPromotionExecutor:
    def available(self, access: AccessContext) -> bool:
        return False

    def promoted_outputs(self, access: AccessContext) -> tuple[PromotedCompanyGeneratedOutput, ...]:
        return ()

    def promote(self, **_: object) -> PromotedCompanyGeneratedOutput:
        raise CompanyGeneratedOutputPromotionUnavailable(
            "current reviewed-output Governed Execution provider is unavailable; no canonical state changed"
        )


class P1005CompanyGeneratedOutputPromotionExecutor:
    """Product-side executor delegating the canonical effect to the P10.05 semantic owner."""

    def __init__(
        self,
        provider: CompanyGeneratedOutputGovernedProvider,
        asset_admission: P1003CompanyAssetAdmissionExecutor,
    ) -> None:
        self.provider = provider
        self.asset_admission = asset_admission
        self.state = ReviewedGeneratedOutputPromotionState()
        self._intent_times: dict[tuple[str, str, str], datetime] = {}

    def available(self, access: AccessContext) -> bool:
        return bool(self.provider.available(access))

    def promoted_outputs(self, access: AccessContext) -> tuple[PromotedCompanyGeneratedOutput, ...]:
        if not isinstance(access, AccessContext):
            raise CompanyGeneratedOutputError("server-authorized AccessContext is required")
        result: list[PromotedCompanyGeneratedOutput] = []
        for item in self.state.committed:
            record = item.admitted_document.canonical_record
            if record.organization.organization_id != access.organization:
                continue
            output_id = dict(record.payload).get("source_output_id")
            if not isinstance(output_id, str):
                raise CompanyGeneratedOutputError("promoted Company document lacks source output identity")
            provenance = tuple(
                _identity_text(ref)
                for ref in dict.fromkeys(
                    (*item.designation.provenance_refs, *item.event.record.provenance_refs)
                )
            )
            result.append(
                PromotedCompanyGeneratedOutput(
                    output_id=output_id,
                    document_subject=_identity_text(record.subject_id),
                    document_version=_identity_text(record.version_id),
                    designation_subject=_identity_text(item.designation.subject_id),
                    designation_version=_identity_text(item.designation.version_id),
                    event_version=_identity_text(item.event.version_id),
                    promoted_at=item.designation.created_at.isoformat().replace("+00:00", "Z"),
                    provenance_refs=provenance,
                )
            )
        return tuple(result)

    def promote(
        self,
        *,
        access: AccessContext,
        store: CompanyMaterialsStore,
        output_id: str,
        review: CompanyGeneratedOutputReviewEvidence,
    ) -> PromotedCompanyGeneratedOutput:
        if not self.available(access):
            raise CompanyGeneratedOutputPromotionUnavailable("current promotion authorization/evidence is unavailable")
        existing = tuple(item for item in self.promoted_outputs(access) if item.output_id == output_id)
        if len(existing) == 1:
            return existing[0]
        if len(existing) > 1:
            raise CompanyGeneratedOutputPromotionUnavailable("exact promoted output is ambiguous")
        if review.output_id != output_id or review.actor != _store_identity_text(access.actor):
            raise CompanyGeneratedOutputPromotionUnavailable("review evidence no longer matches owner/output command")

        output = resolve_exact_generated_output(
            store=store,
            asset_admission=self.asset_admission,
            access=access,
            output_id=output_id,
        )
        source_artifact = output.source_admission.admitted_document.artifacts[0]
        if review.output_sha256 != output.output_sha256:
            raise CompanyGeneratedOutputPromotionUnavailable("output digest changed after review")
        if review.handling_digest != _digest_payload(_handling_payload(output)):
            raise CompanyGeneratedOutputPromotionUnavailable("inherited handling changed after review")
        if review.source_document_version != output.source_admission.admitted_document.version_id:
            raise CompanyGeneratedOutputPromotionUnavailable("exact admitted source Document Version changed")
        if review.source_artifact_id != source_artifact.artifact_id:
            raise CompanyGeneratedOutputPromotionUnavailable("exact admitted source Artifact changed")
        if review.source_designation_version != output.source_admission.designation.version_id:
            raise CompanyGeneratedOutputPromotionUnavailable("exact admitted source designation changed")

        actor = self.provider.actor_for(access)
        scope = actor.organization.organization_id.value
        intent_key = (scope, output_id, review.review_digest)
        command_at = self._intent_times.setdefault(intent_key, datetime.now(timezone.utc))
        candidate = build_generated_output_document_candidate(
            output=output,
            access=access,
            actor=actor,
            candidate_created_at=command_at,
            document_title=review.document_title,
            semantic_role=review.semantic_role,
        )
        prepared = self.provider.prepare(
            access=access,
            candidate=candidate,
            output=output,
            review=review,
        )
        if prepared.actor != actor:
            raise CompanyGeneratedOutputPromotionUnavailable("governed Actor changed during promotion")

        source_subject, source_version, artifact_id = exact_generated_output_source_identities(
            output=output, actor=actor
        )
        generation_ref_values: list[Identity] = []
        for admission in (output.source_admission, *output.input_admissions):
            record = admission.admitted_document.canonical_record
            artifact = admission.admitted_document.artifacts[0]
            generation_ref_values.extend(
                (
                    record.subject_id,
                    record.version_id,
                    artifact.artifact_id,
                    admission.designation.subject_id,
                    admission.designation.version_id,
                )
            )
        generation_refs = tuple(dict.fromkeys(generation_ref_values))
        request = ReviewedGeneratedOutputPromotionRequest(
            candidate=candidate,
            source=ExactGeneratedOutputSource(
                source_subject_id=source_subject,
                source_version_id=source_version,
                artifact_id=artifact_id,
                integrity_ref=output.output_sha256,
                generation_provenance_refs=generation_refs,
            ),
            handling=output.handling,
            authority=prepared.authority,
            controls=AssetAdmissionControlPins(
                product_contract=prepared.execution.product_contract,
                workflow=prepared.execution.workflow,
                operation_name=prepared.execution.operation_name,
            ),
            designation_subject_id=Identity(
                "organizational-asset-subject", f"company-generated-output-{output_id}", scope
            ),
            designation_version_id=Identity(
                "organizational-asset-version",
                f"company-generated-output-{output_id}-{output.output_sha256[:24]}",
                scope,
            ),
            retry_token=f"company-generated-output-promotion:{scope}:{output_id}:{review.review_digest}",
            event_id=Identity(
                "event-subject", f"company-generated-output-promoted-{output_id}-{review.review_digest}", scope
            ),
            event_version_id=Identity(
                "event-version",
                f"company-generated-output-promoted-{output_id}-{review.review_digest}-v1",
                scope,
            ),
            occurred_at=prepared.occurred_at,
            recorded_at=prepared.recorded_at,
        )
        result = promote_reviewed_generated_output(
            state=self.state,
            capability_adapter=prepared.capability_adapter,
            execution=prepared.execution,
            request=request,
        )
        self.state = result.state
        exact = tuple(item for item in self.promoted_outputs(access) if item.output_id == output_id)
        if len(exact) != 1:
            raise CompanyGeneratedOutputError("successful promotion did not resolve one exact canonical result")
        return exact[0]


class CompanyGeneratedOutputs:
    """Owner-facing generated-output review projection; never a canonical authority source."""

    def __init__(
        self,
        runtime_root: Path,
        materials: CompanyMaterialsStore,
        asset_admission: P1003CompanyAssetAdmissionExecutor,
        promotion: CompanyGeneratedOutputPromotionExecutor | None = None,
    ) -> None:
        self.runtime_root = runtime_root.expanduser()
        self.materials = materials
        self.asset_admission = asset_admission
        self.promotion = promotion or UnavailableCompanyGeneratedOutputPromotionExecutor()
        self.reviews = self.runtime_root / "workspace-company-generated-output-reviews"

    def _review_path(self, output_id: str) -> Path:
        if not _SAFE_OUTPUT_ID.fullmatch(output_id):
            raise CompanyGeneratedOutputReviewError("output identity is invalid")
        return self.reviews / f"{output_id}.json"

    def _read_review(self, access: AccessContext, output_id: str) -> dict[str, Any]:
        path = self._review_path(output_id)
        if not path.exists():
            return {
                "disposition": "PendingReview",
                "reason": None,
                "document_title": None,
                "semantic_role": None,
                "updated_at": None,
                "actor": None,
                "canonical_authority": False,
            }
        try:
            if path.is_symlink():
                raise CompanyGeneratedOutputReviewError("review evidence path must not be a symlink")
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CompanyGeneratedOutputReviewError("generated-output review evidence is unavailable") from exc
        if (
            not isinstance(value, dict)
            or value.get("schema") != "arvectum.company.generated-output-review/1"
            or value.get("output_id") != output_id
            or value.get("organization") != _store_identity_text(access.organization)
            or value.get("disposition") not in _DISPOSITIONS
            or value.get("canonical_authority") is not False
        ):
            raise CompanyGeneratedOutputReviewError("generated-output review evidence is invalid")
        return value

    def _write_review(
        self,
        access: AccessContext,
        output: ExactCompanyGeneratedOutput,
        *,
        disposition: str,
        reason: str | None,
        document_title: str | None,
        semantic_role: str | None,
    ) -> dict[str, Any]:
        if disposition not in _DISPOSITIONS - {"PendingReview"}:
            raise CompanyGeneratedOutputReviewError("unsupported generated-output disposition")
        value = {
            "schema": "arvectum.company.generated-output-review/1",
            "output_id": output.output_id,
            "organization": _store_identity_text(access.organization),
            "disposition": disposition,
            "reason": reason,
            "document_title": document_title,
            "semantic_role": semantic_role,
            "output_sha256": output.output_sha256,
            "source_document_version": _identity_text(output.source_admission.admitted_document.version_id),
            "source_artifact_id": _identity_text(output.source_admission.admitted_document.artifacts[0].artifact_id),
            "source_designation_version": _identity_text(output.source_admission.designation.version_id),
            "handling": _handling_payload(output),
            "handling_digest": _digest_payload(_handling_payload(output)),
            "updated_at": _utc_now(),
            "actor": _store_identity_text(access.actor),
            "canonical_authority": False,
            "source_state": "TransientOutput",
        }
        value["review_digest"] = _digest_payload(
            {key: value[key] for key in value if key not in {"updated_at", "review_digest"}}
        )
        _atomic_json(self._review_path(output.output_id), value)
        return value

    @staticmethod
    def _parse_identity(text: object) -> Identity:
        if not isinstance(text, str):
            raise CompanyGeneratedOutputPromotionUnavailable("review exact identity is unavailable")
        try:
            namespace, rest = text.split(":", 1)
            scope, value = rest.split(":", 1)
        except ValueError as exc:
            raise CompanyGeneratedOutputPromotionUnavailable("review exact identity is malformed") from exc
        return Identity(namespace, value, scope)

    def _promotion_evidence(
        self, access: AccessContext, output_id: str
    ) -> CompanyGeneratedOutputReviewEvidence:
        value = self._read_review(access, output_id)
        if value.get("disposition") != "PromotionRequested":
            raise CompanyGeneratedOutputPromotionUnavailable("owner has not requested governed promotion")
        required = (
            "updated_at",
            "actor",
            "output_sha256",
            "document_title",
            "semantic_role",
            "handling_digest",
            "review_digest",
        )
        if any(not isinstance(value.get(key), str) or not str(value[key]).strip() for key in required):
            raise CompanyGeneratedOutputPromotionUnavailable("promotion review evidence is incomplete")
        return CompanyGeneratedOutputReviewEvidence(
            output_id=output_id,
            disposition="PromotionRequested",
            updated_at=str(value["updated_at"]),
            actor=str(value["actor"]),
            output_sha256=str(value["output_sha256"]),
            document_title=str(value["document_title"]),
            semantic_role=str(value["semantic_role"]),
            handling_digest=str(value["handling_digest"]),
            source_document_version=self._parse_identity(value.get("source_document_version")),
            source_artifact_id=self._parse_identity(value.get("source_artifact_id")),
            source_designation_version=self._parse_identity(value.get("source_designation_version")),
            review_digest=str(value["review_digest"]),
        )

    def review(self, access: AccessContext, output_id: str, payload: object) -> dict[str, Any]:
        if not isinstance(access, AccessContext):
            raise CompanyGeneratedOutputError("server-authorized AccessContext is required")
        if not isinstance(payload, dict) or not isinstance(payload.get("disposition"), str):
            raise CompanyGeneratedOutputReviewError("generated-output review payload is invalid")
        if any(item.output_id == output_id for item in self.promotion.promoted_outputs(access)):
            raise CompanyGeneratedOutputReviewError("already-promoted output review cannot be rewritten")
        disposition = str(payload["disposition"])
        if disposition == "Rejected":
            if set(payload) != {"disposition", "reason"}:
                raise CompanyGeneratedOutputReviewError("Rejected review requires only a reason")
            reason = _bounded(payload.get("reason"), field="reason", maximum=600)
            title = role = None
        elif disposition == "KeepTransient":
            if set(payload) != {"disposition"}:
                raise CompanyGeneratedOutputReviewError("KeepTransient review has no additional fields")
            reason = title = role = None
        elif disposition == "PromotionRequested":
            if set(payload) != {"disposition", "document_title", "semantic_role"}:
                raise CompanyGeneratedOutputReviewError(
                    "PromotionRequested requires document_title and semantic_role"
                )
            reason = None
            title = _bounded(payload.get("document_title"), field="document_title", maximum=320)
            role = _bounded(payload.get("semantic_role"), field="semantic_role", maximum=96)
        else:
            raise CompanyGeneratedOutputReviewError("unsupported generated-output disposition")
        output = resolve_exact_generated_output(
            store=self.materials,
            asset_admission=self.asset_admission,
            access=access,
            output_id=output_id,
        )
        return self._write_review(
            access,
            output,
            disposition=disposition,
            reason=reason,
            document_title=title,
            semantic_role=role,
        )

    def promote(self, access: AccessContext, output_id: str) -> PromotedCompanyGeneratedOutput:
        return self.promotion.promote(
            access=access,
            store=self.materials,
            output_id=output_id,
            review=self._promotion_evidence(access, output_id),
        )

    def project(self, access: AccessContext) -> dict[str, Any]:
        if not isinstance(access, AccessContext):
            raise CompanyGeneratedOutputError("server-authorized AccessContext is required")
        promoted = {item.output_id: item for item in self.promotion.promoted_outputs(access)}
        items: list[dict[str, Any]] = []
        if self.materials.transient.is_dir():
            for path in sorted(self.materials.transient.glob("OUT-*.json")):
                output_id = path.stem
                try:
                    _, manifest = self.materials.output_path(access, output_id)
                except (CompanyMaterialUnavailable, CompanyMaterialsError):
                    continue
                review = self._read_review(access, output_id)
                exact_source: ExactCompanyGeneratedOutput | None = None
                source_error: str | None = None
                try:
                    exact_source = resolve_exact_generated_output(
                        store=self.materials,
                        asset_admission=self.asset_admission,
                        access=access,
                        output_id=output_id,
                    )
                except (CompanyGeneratedOutputError, CompanyMaterialUnavailable, CompanyMaterialsError, RuntimeError):
                    source_error = "EXACT_ADMITTED_SOURCE_UNAVAILABLE"
                item = {
                    "output_id": output_id,
                    "state": "TransientOutput",
                    "canonical_authority": False,
                    "filename": manifest.get("filename"),
                    "media_type": manifest.get("media_type"),
                    "project_id": manifest.get("project_id"),
                    "created_at": manifest.get("created_at"),
                    "created_by": manifest.get("created_by"),
                    "output_sha256": manifest.get("output_sha256"),
                    "source_material_id": manifest.get("source_material_id"),
                    "source_version_id": manifest.get("source_version_id"),
                    "source_sha256": manifest.get("source_sha256"),
                    "generation_profile": manifest.get("generation_profile"),
                    "generation_input_digest": manifest.get("generation_input_digest"),
                    "input_assets": manifest.get("input_assets", []),
                    "download_href": f"/api/app/v1/company-materials/outputs/{output_id}/download",
                    "review": review,
                    "inherited_handling": _handling_payload(exact_source) if exact_source else None,
                    "exact_source_available": exact_source is not None,
                    "source_error": source_error,
                    "canonical_promotion": promoted.get(output_id).to_payload() if output_id in promoted else None,
                    "promotion_available": bool(
                        exact_source is not None
                        and review.get("disposition") == "PromotionRequested"
                        and self.promotion.available(access)
                    ),
                    "validated_knowledge": False,
                }
                items.append(item)
        items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return {
            "schema": "arvectum.workspace.company-generated-outputs/1",
            "generated_at": _utc_now(),
            "product_contract": {
                "id": "p9-11-f11-arvectum-company-workspace",
                "version": "0.2.0",
                "lifecycle": "Provisional",
            },
            "items": items,
            "actions": {"governed_promotion_available": self.promotion.available(access)},
            "governance": {
                "output_source_state": "TransientOutput",
                "review_is_canonical": False,
                "promotion_requires_governed_execution": True,
                "promotion_relabels_transient_source": False,
                "validated_knowledge_created": False,
                "external_send_sign_publish_available": False,
            },
        }


__all__ = [
    "CompanyGeneratedOutputError",
    "CompanyGeneratedOutputGovernedProvider",
    "CompanyGeneratedOutputPromotionExecutor",
    "CompanyGeneratedOutputPromotionUnavailable",
    "CompanyGeneratedOutputReviewError",
    "CompanyGeneratedOutputReviewEvidence",
    "CompanyGeneratedOutputs",
    "P1005CompanyGeneratedOutputPromotionExecutor",
    "PreparedCompanyGeneratedOutputPromotion",
    "PromotedCompanyGeneratedOutput",
    "UnavailableCompanyGeneratedOutputPromotionExecutor",
]
