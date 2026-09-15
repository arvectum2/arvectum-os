"""P10.04 owner-facing Company Asset Library composition.

Product-local staging/review remains non-canonical. Consequential admission is
performed only through the P10.03 governed Organizational Asset entrypoint.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from arvectum_os_ref.canonical import AuthorityMode
from arvectum_os_ref.canonical_lineage import CanonicalLineage
from arvectum_os_ref.document_artifact_governance import DocumentVersionCandidate
from arvectum_os_ref.governed_execution import GovernedExecutionContext
from arvectum_os_ref.identity import Identity
from arvectum_os_ref.integration_adapters import IntegrationCapabilityAdapter
from arvectum_os_ref.organizational_asset_admission import (
    AssetAdmissionAuthorityEvidence,
    AssetAdmissionControlPins,
    AssetAdmissionSourceKind,
    ExactAssetAdmissionSource,
    OrganizationalAssetAdmissionRequest,
    OrganizationalAssetAdmissionState,
    OrganizationalAssetHandlingPolicy,
)
from arvectum_os_ref.organizational_asset_admission_guard import admit_governed_organizational_asset
from arvectum_os_ref.security import ActorContext

from .access import AccessContext
from .company_asset_admission import (
    ExactCompanyStagedMaterial,
    build_staged_document_candidate,
    exact_staged_source_identities,
    resolve_exact_staged_material,
)
from .company_materials import (
    CompanyMaterialUnavailable,
    CompanyMaterialsInputError,
    CompanyMaterialsStore,
    _atomic_json,
    _identity_text as _staging_identity_text,
    _utc_now,
)

_REVIEW_STATES = frozenset({"Draft", "InReview", "Rejected"})


class CompanyAssetLibraryError(RuntimeError):
    pass


class CompanyAssetReviewError(ValueError, CompanyAssetLibraryError):
    pass


class CompanyAssetAdmissionUnavailable(CompanyAssetLibraryError):
    pass


def _bounded_text(value: object, *, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise CompanyAssetReviewError(f"{field} must be text")
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > maximum or "\x00" in normalized:
        raise CompanyAssetReviewError(f"{field} is outside the bounded P10.04 contract")
    return normalized


def _identity_text(identity: Identity) -> str:
    return f"{identity.namespace}:{identity.scope}:{identity.value}"


def _policy_digest(policy: "CompanyAssetReviewPolicy") -> str:
    encoded = json.dumps(
        policy.to_payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]


@dataclass(frozen=True, slots=True)
class CompanyAssetReviewPolicy:
    deletion_rule: str
    permitted_reuse: tuple[str, ...]

    @classmethod
    def from_payload(cls, payload: object) -> "CompanyAssetReviewPolicy":
        if not isinstance(payload, dict) or set(payload) != {"deletion_rule", "permitted_reuse"}:
            raise CompanyAssetReviewError("review payload fields are invalid")
        deletion = _bounded_text(payload.get("deletion_rule"), field="deletion_rule", maximum=240)
        raw = payload.get("permitted_reuse")
        if not isinstance(raw, list) or not raw or len(raw) > 8:
            raise CompanyAssetReviewError("permitted_reuse must contain 1..8 explicit values")
        return cls(
            deletion_rule=deletion,
            permitted_reuse=tuple(
                _bounded_text(value, field="permitted_reuse", maximum=160) for value in raw
            ),
        )

    def to_payload(self) -> dict[str, Any]:
        return {"deletion_rule": self.deletion_rule, "permitted_reuse": list(self.permitted_reuse)}


@dataclass(frozen=True, slots=True)
class CompanyAssetReviewEvidence:
    updated_at: str
    actor: str
    policy_digest: str

    def __post_init__(self) -> None:
        if not self.updated_at or not self.actor or len(self.policy_digest) != 24:
            raise CompanyAssetAdmissionUnavailable("exact review evidence is incomplete")


@dataclass(frozen=True, slots=True)
class AdmittedCompanyAssetVersion:
    material_id: str
    version_id: str
    document_subject: str
    document_version: str
    designation_subject: str
    designation_version: str
    event_version: str
    admitted_at: str
    provenance_refs: tuple[str, ...]
    current: bool

    def to_payload(self) -> dict[str, Any]:
        return {
            "material_id": self.material_id,
            "version_id": self.version_id,
            "document_subject": self.document_subject,
            "document_version": self.document_version,
            "designation_subject": self.designation_subject,
            "designation_version": self.designation_version,
            "event_version": self.event_version,
            "admitted_at": self.admitted_at,
            "provenance_refs": list(self.provenance_refs),
            "current": self.current,
        }


class CompanyAssetAdmissionExecutor(Protocol):
    def available(self, access: AccessContext) -> bool: ...
    def admitted_versions(self, access: AccessContext) -> tuple[AdmittedCompanyAssetVersion, ...]: ...
    def admit(
        self,
        *,
        access: AccessContext,
        store: CompanyMaterialsStore,
        material_id: str,
        version_id: str,
        policy: CompanyAssetReviewPolicy,
    ) -> AdmittedCompanyAssetVersion: ...


class UnavailableCompanyAssetAdmissionExecutor:
    def available(self, access: AccessContext) -> bool:
        return False

    def admitted_versions(self, access: AccessContext) -> tuple[AdmittedCompanyAssetVersion, ...]:
        return ()

    def admit(self, **_: object) -> AdmittedCompanyAssetVersion:
        raise CompanyAssetAdmissionUnavailable(
            "current RFC-0005 governed admission provider is unavailable; no canonical state changed"
        )


@dataclass(frozen=True, slots=True)
class PreparedCompanyAssetAdmission:
    actor: ActorContext
    capability_adapter: IntegrationCapabilityAdapter
    execution: GovernedExecutionContext
    authority: AssetAdmissionAuthorityEvidence
    occurred_at: datetime
    recorded_at: datetime


class CompanyAssetGovernedAdmissionProvider(Protocol):
    def available(self, access: AccessContext) -> bool: ...
    def actor_for(self, access: AccessContext) -> ActorContext: ...
    def prepare(
        self,
        *,
        access: AccessContext,
        candidate: DocumentVersionCandidate,
        staged: ExactCompanyStagedMaterial,
        policy: CompanyAssetReviewPolicy,
        review: CompanyAssetReviewEvidence,
    ) -> PreparedCompanyAssetAdmission: ...


class P1003CompanyAssetAdmissionExecutor:
    """Reference executor delegating canonical change only to the P10.03 guard."""

    def __init__(self, provider: CompanyAssetGovernedAdmissionProvider) -> None:
        self.provider = provider
        self.state = OrganizationalAssetAdmissionState()
        self._intent_times: dict[tuple[str, str, str, str], datetime] = {}

    def available(self, access: AccessContext) -> bool:
        return bool(self.provider.available(access))

    def _views(self, access: AccessContext) -> tuple[AdmittedCompanyAssetVersion, ...]:
        matching = tuple(
            item
            for item in self.state.committed
            if item.admitted_document.canonical_record.organization.organization_id == access.organization
        )
        by_subject: dict[Identity, list[Any]] = {}
        for item in matching:
            record = item.admitted_document.canonical_record
            by_subject.setdefault(record.subject_id, []).append(record)
        heads: set[Identity] = set()
        for records in by_subject.values():
            heads.add(CanonicalLineage(tuple(records)).head.version_id)

        result: list[AdmittedCompanyAssetVersion] = []
        for item in matching:
            record = item.admitted_document.canonical_record
            payload = dict(record.payload)
            material_id = payload.get("source_material_id")
            version_id = payload.get("source_version_id")
            if not isinstance(material_id, str) or not isinstance(version_id, str):
                raise CompanyAssetLibraryError("admitted Company asset lacks exact staged source identity")
            provenance = tuple(
                _identity_text(ref)
                for ref in dict.fromkeys(
                    (*item.designation.provenance_refs, *item.event.record.provenance_refs)
                )
            )
            result.append(
                AdmittedCompanyAssetVersion(
                    material_id=material_id,
                    version_id=version_id,
                    document_subject=_identity_text(record.subject_id),
                    document_version=_identity_text(record.version_id),
                    designation_subject=_identity_text(item.designation.subject_id),
                    designation_version=_identity_text(item.designation.version_id),
                    event_version=_identity_text(item.event.version_id),
                    admitted_at=item.designation.created_at.isoformat().replace("+00:00", "Z"),
                    provenance_refs=provenance,
                    current=record.version_id in heads,
                )
            )
        return tuple(result)

    def admitted_versions(self, access: AccessContext) -> tuple[AdmittedCompanyAssetVersion, ...]:
        if not isinstance(access, AccessContext):
            raise CompanyAssetLibraryError("server-authorized AccessContext is required")
        return self._views(access)

    def _require_linear_successor(self, access: AccessContext, staged: ExactCompanyStagedMaterial) -> None:
        versions = tuple(value for value in self._views(access) if value.material_id == staged.material_id)
        current = tuple(value for value in versions if value.current)
        if not versions:
            if staged.predecessor_version_id is not None:
                raise CompanyAssetAdmissionUnavailable(
                    "first canonical admission for a material must start from its initial staged version"
                )
            return
        if len(current) != 1:
            raise CompanyAssetAdmissionUnavailable("current canonical Company Asset version is ambiguous")
        if staged.predecessor_version_id != current[0].version_id:
            raise CompanyAssetAdmissionUnavailable(
                "admission must extend the exact current canonical predecessor without branching or skipping"
            )

    def _require_review_evidence(
        self,
        *,
        access: AccessContext,
        store: CompanyMaterialsStore,
        material_id: str,
        version_id: str,
        policy: CompanyAssetReviewPolicy,
    ) -> CompanyAssetReviewEvidence:
        manifest = store._read_manifest(material_id, _staging_identity_text(access.organization))
        states = manifest.get("p10_04_review_states", {})
        if not isinstance(states, dict):
            raise CompanyAssetAdmissionUnavailable("review evidence registry is invalid")
        value = states.get(version_id)
        if not isinstance(value, dict) or value.get("state") != "InReview":
            raise CompanyAssetAdmissionUnavailable("exact staged version lacks current InReview evidence")
        if value.get("canonical_authority") is not False:
            raise CompanyAssetAdmissionUnavailable("review evidence must remain explicitly non-canonical")
        if value.get("actor") != _staging_identity_text(access.actor):
            raise CompanyAssetAdmissionUnavailable("review Actor no longer matches the current owner command")
        if value.get("policy") != policy.to_payload():
            raise CompanyAssetAdmissionUnavailable("review handling policy changed before admission")
        updated_at = value.get("updated_at")
        if not isinstance(updated_at, str) or not updated_at:
            raise CompanyAssetAdmissionUnavailable("review timestamp is unavailable")
        return CompanyAssetReviewEvidence(
            updated_at=updated_at,
            actor=str(value["actor"]),
            policy_digest=_policy_digest(policy),
        )

    def admit(
        self,
        *,
        access: AccessContext,
        store: CompanyMaterialsStore,
        material_id: str,
        version_id: str,
        policy: CompanyAssetReviewPolicy,
    ) -> AdmittedCompanyAssetVersion:
        if not self.available(access):
            raise CompanyAssetAdmissionUnavailable("current governed admission evidence is unavailable")
        existing = tuple(
            item
            for item in self._views(access)
            if item.material_id == material_id and item.version_id == version_id
        )
        if len(existing) == 1:
            return existing[0]
        if len(existing) > 1:
            raise CompanyAssetAdmissionUnavailable("exact Company Asset version is ambiguous")

        review = self._require_review_evidence(
            access=access,
            store=store,
            material_id=material_id,
            version_id=version_id,
            policy=policy,
        )
        staged = resolve_exact_staged_material(
            store=store, access=access, material_id=material_id, version_id=version_id
        )
        self._require_linear_successor(access, staged)
        actor = self.provider.actor_for(access)
        scope = actor.organization.organization_id.value
        intent_key = (scope, material_id, version_id, review.policy_digest)
        command_at = self._intent_times.setdefault(intent_key, datetime.now(timezone.utc))
        candidate = build_staged_document_candidate(
            staged=staged,
            access=access,
            actor=actor,
            candidate_created_at=command_at,
        )
        prepared = self.provider.prepare(
            access=access,
            candidate=candidate,
            staged=staged,
            policy=policy,
            review=review,
        )
        if prepared.actor != actor:
            raise CompanyAssetAdmissionUnavailable("governed actor changed during command revalidation")

        source_subject, source_version, artifact_id = exact_staged_source_identities(
            staged=staged, actor=actor
        )
        handling = OrganizationalAssetHandlingPolicy(
            classification=staged.classification,
            purpose=staged.purpose,
            rights=(staged.rights,),
            retention_rule=staged.retention_rule,
            deletion_rule=policy.deletion_rule,
            permitted_reuse=policy.permitted_reuse,
        )
        designation_subject = Identity(
            "organizational-asset-subject", f"company-asset-{material_id}", scope
        )
        designation_version = Identity(
            "organizational-asset-version", f"company-asset-{version_id}", scope
        )
        designation_predecessor = (
            Identity(
                "organizational-asset-version",
                f"company-asset-{staged.predecessor_version_id}",
                scope,
            )
            if staged.predecessor_version_id is not None
            else None
        )
        retry_token = (
            f"company-asset-admission:{scope}:{material_id}:{version_id}:{review.policy_digest}"
        )
        request = OrganizationalAssetAdmissionRequest(
            candidate=candidate,
            source=ExactAssetAdmissionSource(
                kind=AssetAdmissionSourceKind.STAGED_VERSION,
                source_subject_id=source_subject,
                source_version_id=source_version,
                artifact_id=artifact_id,
                integrity_ref=staged.content_sha256,
                authority_mode=AuthorityMode.NATIVE,
            ),
            handling=handling,
            authority=prepared.authority,
            controls=AssetAdmissionControlPins(
                product_contract=prepared.execution.product_contract,
                workflow=prepared.execution.workflow,
                operation_name=prepared.execution.operation_name,
            ),
            designation_subject_id=designation_subject,
            designation_version_id=designation_version,
            designation_predecessor_version_id=designation_predecessor,
            retry_token=retry_token,
            event_id=Identity(
                "event-subject",
                f"company-asset-admitted-{version_id}-{review.policy_digest}",
                scope,
            ),
            event_version_id=Identity(
                "event-version",
                f"company-asset-admitted-{version_id}-{review.policy_digest}-v1",
                scope,
            ),
            occurred_at=prepared.occurred_at,
            recorded_at=prepared.recorded_at,
        )
        result = admit_governed_organizational_asset(
            state=self.state,
            capability_adapter=prepared.capability_adapter,
            execution=prepared.execution,
            request=request,
        )
        self.state = result.state
        exact = tuple(
            item
            for item in self._views(access)
            if item.material_id == material_id and item.version_id == version_id
        )
        if len(exact) != 1:
            raise CompanyAssetLibraryError("successful admission did not resolve one exact library version")
        return exact[0]


class CompanyAssetLibrary:
    """Owner-facing projection plus non-authoritative review transitions."""

    def __init__(
        self,
        materials: CompanyMaterialsStore,
        admission: CompanyAssetAdmissionExecutor | None = None,
    ) -> None:
        self.materials = materials
        self.admission = admission or UnavailableCompanyAssetAdmissionExecutor()

    def _manifest(self, access: AccessContext, material_id: str) -> dict[str, Any]:
        return self.materials._read_manifest(material_id, _staging_identity_text(access.organization))

    def _review_state(self, access: AccessContext, material_id: str, version_id: str) -> dict[str, Any]:
        self.materials._version(access, material_id, version_id)
        states = self._manifest(access, material_id).get("p10_04_review_states", {})
        if not isinstance(states, dict):
            raise CompanyAssetLibraryError("staged review metadata is invalid")
        value = states.get(version_id)
        if value is None:
            return {"state": "Draft", "policy": None, "reason": None, "updated_at": None}
        if not isinstance(value, dict) or value.get("state") not in _REVIEW_STATES:
            raise CompanyAssetLibraryError("staged review state is invalid")
        return dict(value)

    def _write_review_state(
        self,
        access: AccessContext,
        material_id: str,
        version_id: str,
        *,
        state: str,
        policy: CompanyAssetReviewPolicy | None,
        reason: str | None,
    ) -> dict[str, Any]:
        if state not in _REVIEW_STATES:
            raise CompanyAssetReviewError("unsupported review state")
        self.materials._version(access, material_id, version_id)
        manifest = self._manifest(access, material_id)
        states = manifest.get("p10_04_review_states") or {}
        if not isinstance(states, dict):
            raise CompanyAssetLibraryError("staged review metadata is invalid")
        value = {
            "state": state,
            "policy": policy.to_payload() if policy else None,
            "reason": reason,
            "updated_at": _utc_now(),
            "actor": _staging_identity_text(access.actor),
            "canonical_authority": False,
        }
        states[version_id] = value
        manifest["p10_04_review_states"] = states
        _atomic_json(self.materials._manifest_path(material_id), manifest)
        return value

    def submit_review(
        self, access: AccessContext, material_id: str, version_id: str, payload: object
    ) -> dict[str, Any]:
        current = self._review_state(access, material_id, version_id)
        if current["state"] not in {"Draft", "Rejected"}:
            raise CompanyAssetReviewError("only Draft or Rejected staged versions can enter review")
        return self._write_review_state(
            access,
            material_id,
            version_id,
            state="InReview",
            policy=CompanyAssetReviewPolicy.from_payload(payload),
            reason=None,
        )

    def reject(
        self, access: AccessContext, material_id: str, version_id: str, payload: object
    ) -> dict[str, Any]:
        current = self._review_state(access, material_id, version_id)
        if current["state"] != "InReview":
            raise CompanyAssetReviewError("only InReview staged versions can be rejected")
        if not isinstance(payload, dict) or set(payload) != {"reason"}:
            raise CompanyAssetReviewError("reject payload is invalid")
        policy_payload = current.get("policy")
        policy = (
            CompanyAssetReviewPolicy.from_payload(policy_payload)
            if isinstance(policy_payload, dict)
            else None
        )
        return self._write_review_state(
            access,
            material_id,
            version_id,
            state="Rejected",
            policy=policy,
            reason=_bounded_text(payload.get("reason"), field="reason", maximum=600),
        )

    def admit(
        self, access: AccessContext, material_id: str, version_id: str
    ) -> AdmittedCompanyAssetVersion:
        current = self._review_state(access, material_id, version_id)
        if current["state"] != "InReview" or not isinstance(current.get("policy"), dict):
            raise CompanyAssetReviewError(
                "exact staged version must be InReview with explicit handling policy"
            )
        return self.admission.admit(
            access=access,
            store=self.materials,
            material_id=material_id,
            version_id=version_id,
            policy=CompanyAssetReviewPolicy.from_payload(current["policy"]),
        )

    @staticmethod
    def _entry(
        version: dict[str, Any],
        review: dict[str, Any],
        admitted: AdmittedCompanyAssetVersion | None,
        lifecycle: str,
    ) -> dict[str, Any]:
        return {
            "material_id": version["material_id"],
            "version_id": version["version_id"],
            "title": version["filename"],
            "project_id": version["project_id"],
            "semantic_role": version["semantic_role"],
            "media_type": version["media_type"],
            "classification": version["classification"],
            "purpose": version["purpose"],
            "rights": version["rights"],
            "retention_rule": version["retention_rule"],
            "received_at": version["received_at"],
            "uploader": version["uploader"],
            "content_sha256": version["content_sha256"],
            "size_bytes": version["size_bytes"],
            "predecessor_version_id": version.get("predecessor_version_id"),
            "staging_state": "StagedNonCanonical",
            "review": review,
            "canonical": admitted.to_payload() if admitted else None,
            "lifecycle_view": lifecycle,
            "technical_identity_available": True,
        }

    def project(self, access: AccessContext) -> dict[str, Any]:
        staged = self.materials.project(access)
        by_source = {
            (value.material_id, value.version_id): value
            for value in self.admission.admitted_versions(access)
        }
        views: dict[str, list[dict[str, Any]]] = {
            "drafts": [],
            "review": [],
            "accepted": [],
            "archive": [],
        }
        for material in staged["materials"]:
            for version in material["versions"]:
                key = (str(version["material_id"]), str(version["version_id"]))
                canonical = by_source.get(key)
                review = self._review_state(access, *key)
                if canonical is not None:
                    view = "accepted" if canonical.current else "archive"
                elif review["state"] == "InReview":
                    view = "review"
                elif review["state"] == "Rejected":
                    view = "archive"
                else:
                    view = "drafts"
                views[view].append(self._entry(version, review, canonical, view))
        for values in views.values():
            values.sort(key=lambda item: str(item["received_at"]), reverse=True)
        return {
            "schema": "arvectum.workspace.company-asset-library/1",
            "generated_at": _utc_now(),
            "product_contract": {
                "id": "p9-11-f11-arvectum-company-workspace",
                "version": "0.2.0",
                "lifecycle": "Provisional",
            },
            "views": views,
            "actions": {"governed_admission_available": self.admission.available(access)},
            "scope": {
                "organization_resolved_server_side": True,
                "actor_resolved_server_side": True,
                "cross_organization_access": False,
            },
            "governance": {
                "workspace_is_authority_source": False,
                "staging_is_canonical": False,
                "review_state_is_canonical": False,
                "canonical_admission_requires_governed_execution": True,
                "generated_output_default": "TransientOutput",
                "validated_knowledge_created": False,
            },
        }

    def generate_docx(self, access: AccessContext, payload: object) -> dict[str, Any]:
        required = {"material_id", "version_id", "title", "body", "date"}
        allowed = required | {"asset_inputs"}
        if not isinstance(payload, dict) or not required.issubset(payload) or not set(payload).issubset(allowed):
            raise CompanyMaterialsInputError("generation payload is invalid")
        material_id, version_id = payload.get("material_id"), payload.get("version_id")
        if not isinstance(material_id, str) or not isinstance(version_id, str):
            raise CompanyMaterialsInputError("generation source identity is invalid")

        projection = self.project(access)
        admitted_items = tuple((*projection["views"]["accepted"], *projection["views"]["archive"]))

        def exact_item(candidate_material_id: object, candidate_version_id: object) -> dict[str, Any]:
            if not isinstance(candidate_material_id, str) or not isinstance(candidate_version_id, str):
                raise CompanyMaterialsInputError("generation input identity is invalid")
            matches = tuple(
                item
                for item in admitted_items
                if item["material_id"] == candidate_material_id
                and item["version_id"] == candidate_version_id
                and item.get("canonical") is not None
            )
            if len(matches) != 1:
                raise CompanyMaterialUnavailable("generation requires exact admitted Company Asset versions")
            return matches[0]

        source = exact_item(material_id, version_id)
        canonical = source["canonical"]
        if (
            not canonical.get("current")
            or source.get("semantic_role") != "document-template"
            or source.get("media_type") != "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            raise CompanyMaterialUnavailable("generation template must be the current admitted DOCX template version")

        raw_inputs = payload.get("asset_inputs", [])
        if not isinstance(raw_inputs, list) or len(raw_inputs) > 8:
            raise CompanyMaterialsInputError("asset_inputs must contain at most 8 exact admitted inputs")
        seen = {(material_id, version_id)}
        resolved_inputs: list[dict[str, Any]] = []
        for raw in raw_inputs:
            if not isinstance(raw, dict) or set(raw) != {"material_id", "version_id", "use_as"}:
                raise CompanyMaterialsInputError("asset input fields are invalid")
            use_as = raw.get("use_as")
            if use_as not in {"brand", "source", "reference"}:
                raise CompanyMaterialsInputError("asset input use is unsupported")
            key = (raw.get("material_id"), raw.get("version_id"))
            if key in seen:
                raise CompanyMaterialsInputError("generation inputs must not repeat an exact asset version")
            item = exact_item(*key)
            item_canonical = item["canonical"]
            if not item_canonical.get("current"):
                raise CompanyMaterialUnavailable("asset-aware generation requires current admitted auxiliary inputs")
            role = item.get("semantic_role")
            if use_as == "brand" and role not in {"logo", "brandbook"}:
                raise CompanyMaterialsInputError("brand generation inputs must be admitted logo or brandbook assets")
            if use_as == "source" and role != "source":
                raise CompanyMaterialsInputError("source generation inputs must use the admitted source semantic role")
            if use_as == "reference" and role == "document-template":
                raise CompanyMaterialsInputError("document templates cannot be auxiliary reference inputs")
            seen.add(key)
            resolved_inputs.append(
                {
                    "use_as": use_as,
                    "material_id": item["material_id"],
                    "version_id": item["version_id"],
                    "content_sha256": item["content_sha256"],
                    "title": item["title"],
                    "media_type": item["media_type"],
                    "semantic_role": item["semantic_role"],
                    "document_version": item_canonical["document_version"],
                    "designation_version": item_canonical["designation_version"],
                    "event_version": item_canonical["event_version"],
                    "provenance_refs": list(item_canonical["provenance_refs"]),
                }
            )

        base_payload = {key: payload[key] for key in required}
        result = self.materials.generate_docx(
            access, base_payload, admitted_inputs=tuple(resolved_inputs)
        )
        result["governance"] = {
            **result["governance"],
            "source_admitted_company_asset": True,
            "source_document_version": canonical["document_version"],
            "source_designation_version": canonical["designation_version"],
            "all_generation_inputs_exact_admitted": True,
            "generation_input_count": 1 + len(resolved_inputs),
        }
        return result

    def export(self, access: AccessContext, *, limit: int = 100) -> dict[str, Any]:
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise CompanyAssetReviewError("export limit must be between 1 and 100")
        projection = self.project(access)
        ordered = [
            *projection["views"]["accepted"],
            *projection["views"]["archive"],
            *projection["views"]["review"],
            *projection["views"]["drafts"],
        ][:limit]
        return {
            "schema": "arvectum.workspace.company-asset-library-export/1",
            "generated_at": _utc_now(),
            "organization": _staging_identity_text(access.organization),
            "items": ordered,
            "bounded": True,
            "limit": limit,
            "canonical_authority": False,
        }


__all__ = [
    "AdmittedCompanyAssetVersion",
    "CompanyAssetAdmissionExecutor",
    "CompanyAssetAdmissionUnavailable",
    "CompanyAssetGovernedAdmissionProvider",
    "CompanyAssetLibrary",
    "CompanyAssetLibraryError",
    "CompanyAssetReviewError",
    "CompanyAssetReviewEvidence",
    "CompanyAssetReviewPolicy",
    "P1003CompanyAssetAdmissionExecutor",
    "PreparedCompanyAssetAdmission",
    "UnavailableCompanyAssetAdmissionExecutor",
]
