"""Product-local P10.05 bridge from Company TransientOutput to promotion input.

The bridge understands Company generation/staging metadata and therefore stays
outside the shared platform semantic owner. It resolves one exact transient
output, re-hashes its bytes, proves the exact generating input was already an
admitted Company Asset version, inherits that source handling without widening
it, and constructs an immutable CAP-001 promotion candidate.

It grants no Authorization, Organizational Authority, Data Governance decision,
Validation or Consequential Approval and never changes the transient manifest's
``TransientOutput`` state. Historic F11/P10.04 output manifests did not retain a
versioned generation configuration or generation-input digest; P10.05 therefore
records those fields as unavailable rather than inventing evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from arvectum_os_ref.canonical import AuthorityMode, CanonicalRecord
from arvectum_os_ref.document_artifact_governance import (
    ArtifactContent,
    DocumentVersionCandidate,
    HandlingConstraints,
)
from arvectum_os_ref.identity import Identity
from arvectum_os_ref.organizational_asset_admission import (
    CommittedOrganizationalAssetAdmission,
    OrganizationalAssetHandlingPolicy,
)
from arvectum_os_ref.security import ActorContext
from p10_05_company_output_ref.contract import PROMOTED_OUTPUT_DOCUMENT_SCOPE

from .access import AccessContext
from .company_asset_library import CompanyAssetAdmissionUnavailable, P1003CompanyAssetAdmissionExecutor
from .company_materials import CompanyMaterialUnavailable, CompanyMaterialsError, CompanyMaterialsStore


def _identity_text(identity: Identity) -> str:
    return f"{identity.namespace}:{identity.scope}:{identity.value}"


@dataclass(frozen=True, slots=True)
class ExactCompanyGeneratedOutput:
    output_id: str
    project_id: str
    filename: str
    media_type: str
    created_at: str
    created_by: str
    output_sha256: str
    source_material_id: str
    source_version_id: str
    source_sha256: str
    generation_profile: str | None
    generation_input_digest: str | None
    source_admission: CommittedOrganizationalAssetAdmission
    input_admissions: tuple[CommittedOrganizationalAssetAdmission, ...]
    input_assets: tuple[dict[str, object], ...]
    handling: OrganizationalAssetHandlingPolicy

    def __post_init__(self) -> None:
        if len(self.output_sha256) != 64 or len(self.source_sha256) != 64:
            raise ValueError("generated output must preserve exact SHA-256 digests")
        if self.generation_profile is not None and not self.generation_profile.strip():
            raise ValueError("retained generation_profile must be non-empty")
        if self.generation_input_digest is not None and len(self.generation_input_digest) != 64:
            raise ValueError("retained generation_input_digest must be SHA-256")
        if len(self.input_admissions) != len(self.input_assets):
            raise ValueError("asset-aware generated output must retain one exact admission per auxiliary input")


def _designation_handling(
    admission: CommittedOrganizationalAssetAdmission,
) -> OrganizationalAssetHandlingPolicy:
    payload = dict(admission.designation.payload)
    required = (
        "classification",
        "purpose",
        "rights",
        "retention_rule",
        "deletion_rule",
        "permitted_reuse",
    )
    if any(not isinstance(payload.get(key), str) or not str(payload[key]).strip() for key in required):
        raise CompanyAssetAdmissionUnavailable("admitted source handling evidence is incomplete")
    rights = tuple(part.strip() for part in str(payload["rights"]).split("|") if part.strip())
    reuse = tuple(part.strip() for part in str(payload["permitted_reuse"]).split("|") if part.strip())
    policy = OrganizationalAssetHandlingPolicy(
        classification=str(payload["classification"]),
        purpose=str(payload["purpose"]),
        rights=rights,
        retention_rule=str(payload["retention_rule"]),
        deletion_rule=str(payload["deletion_rule"]),
        permitted_reuse=reuse,
    )
    artifacts = admission.admitted_document.artifacts
    if len(artifacts) != 1 or artifacts[0].handling != policy.cap001_constraints:
        raise CompanyAssetAdmissionUnavailable("source designation handling differs from admitted Artifact")
    return policy


def resolve_exact_generated_output(
    *,
    store: CompanyMaterialsStore,
    asset_admission: P1003CompanyAssetAdmissionExecutor,
    access: AccessContext,
    output_id: str,
) -> ExactCompanyGeneratedOutput:
    """Resolve exact output bytes and exact already-admitted generating source."""

    if not isinstance(store, CompanyMaterialsStore):
        raise TypeError("generated-output promotion requires CompanyMaterialsStore")
    if not isinstance(asset_admission, P1003CompanyAssetAdmissionExecutor):
        raise TypeError("generated-output promotion requires the current P10.04 admission executor")
    if not isinstance(access, AccessContext):
        raise TypeError("generated-output promotion requires server-authorized AccessContext")

    path, manifest = store.output_path(access, output_id)
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise CompanyMaterialUnavailable("exact transient output bytes unavailable") from exc
    digest = hashlib.sha256(content).hexdigest()
    if digest != manifest.get("output_sha256"):
        raise CompanyMaterialsError("exact transient output integrity mismatch")
    if manifest.get("state") != "TransientOutput" or manifest.get("canonical_authority") is not False:
        raise CompanyMaterialUnavailable("promotion source must remain an explicit TransientOutput")

    required_text = (
        "project_id",
        "filename",
        "media_type",
        "created_at",
        "created_by",
        "source_material_id",
        "source_version_id",
        "source_sha256",
    )
    if any(not isinstance(manifest.get(key), str) or not str(manifest[key]).strip() for key in required_text):
        raise CompanyMaterialUnavailable("transient output generation/source evidence is incomplete")

    profile_value = manifest.get("generation_profile")
    generation_profile = str(profile_value) if isinstance(profile_value, str) and profile_value.strip() else None
    input_digest_value = manifest.get("generation_input_digest")
    generation_input_digest = (
        str(input_digest_value)
        if isinstance(input_digest_value, str) and len(input_digest_value) == 64
        else None
    )

    def exact_admission(material_id: str, version_id: str) -> CommittedOrganizationalAssetAdmission:
        matches = tuple(
            item
            for item in asset_admission.state.committed
            if dict(item.admitted_document.canonical_record.payload).get("source_material_id") == material_id
            and dict(item.admitted_document.canonical_record.payload).get("source_version_id") == version_id
            and item.admitted_document.canonical_record.organization.organization_id == access.organization
        )
        if len(matches) != 1:
            raise CompanyAssetAdmissionUnavailable(
                "exact admitted generation input is unavailable in the current bounded canonical state"
            )
        return matches[0]

    source_material_id = str(manifest["source_material_id"])
    source_version_id = str(manifest["source_version_id"])
    source = exact_admission(source_material_id, source_version_id)
    source_artifacts = source.admitted_document.artifacts
    if len(source_artifacts) != 1:
        raise CompanyAssetAdmissionUnavailable("exact admitted source Artifact is ambiguous")
    if source_artifacts[0].integrity_ref != manifest["source_sha256"]:
        raise CompanyAssetAdmissionUnavailable("generated output source digest differs from admitted source")
    handling = _designation_handling(source)

    raw_inputs = manifest.get("input_assets", [])
    if not isinstance(raw_inputs, list) or len(raw_inputs) > 8:
        raise CompanyAssetAdmissionUnavailable("asset-aware generation input evidence is invalid")
    input_admissions: list[CommittedOrganizationalAssetAdmission] = []
    normalized_inputs: list[dict[str, object]] = []
    required_input_fields = {
        "use_as", "application", "material_id", "version_id", "content_sha256", "title", "media_type",
        "semantic_role", "document_version", "designation_version", "event_version", "provenance_refs",
    }
    for raw in raw_inputs:
        if not isinstance(raw, dict) or set(raw) != required_input_fields:
            raise CompanyAssetAdmissionUnavailable("asset-aware generation input evidence is incomplete")
        material = raw.get("material_id")
        version = raw.get("version_id")
        expected_sha = raw.get("content_sha256")
        if not isinstance(material, str) or not isinstance(version, str) or not isinstance(expected_sha, str):
            raise CompanyAssetAdmissionUnavailable("asset-aware generation input identity is invalid")
        admitted_input = exact_admission(material, version)
        artifacts = admitted_input.admitted_document.artifacts
        if len(artifacts) != 1 or artifacts[0].integrity_ref != expected_sha:
            raise CompanyAssetAdmissionUnavailable("asset-aware generation input digest differs from admission")
        record = admitted_input.admitted_document.canonical_record
        payload = dict(record.payload)
        media_type = artifacts[0].media_type
        semantic_role = payload.get("semantic_role")
        filename = payload.get("filename")
        use_as = raw.get("use_as")
        if raw.get("media_type") != media_type or raw.get("semantic_role") != semantic_role or raw.get("title") != filename:
            raise CompanyAssetAdmissionUnavailable("asset-aware input metadata differs from admitted exact source")
        if use_as not in {"brand", "source", "reference"}:
            raise CompanyAssetAdmissionUnavailable("asset-aware input use is invalid")
        if use_as == "brand" and semantic_role not in {"logo", "brandbook"}:
            raise CompanyAssetAdmissionUnavailable("asset-aware brand input role differs from admitted source")
        if use_as == "source" and semantic_role != "source":
            raise CompanyAssetAdmissionUnavailable("asset-aware source input role differs from admitted source")
        if use_as == "reference" and semantic_role == "document-template":
            raise CompanyAssetAdmissionUnavailable("asset-aware reference input cannot be a document template")
        expected_application = (
            "text-included"
            if media_type in {"text/plain", "text/markdown"}
            else "embedded-image"
            if use_as == "brand" and media_type in {"image/png", "image/jpeg"}
            else "pinned-reference"
        )
        if raw.get("application") != expected_application:
            raise CompanyAssetAdmissionUnavailable("asset-aware input application evidence is inconsistent")
        if _identity_text(admitted_input.admitted_document.version_id) != raw.get("document_version"):
            raise CompanyAssetAdmissionUnavailable("asset-aware input Document Version differs from generation evidence")
        if _identity_text(admitted_input.designation.version_id) != raw.get("designation_version"):
            raise CompanyAssetAdmissionUnavailable("asset-aware input designation differs from generation evidence")
        if _identity_text(admitted_input.event.version_id) != raw.get("event_version"):
            raise CompanyAssetAdmissionUnavailable("asset-aware input admission Event differs from generation evidence")
        expected_provenance = [
            _identity_text(ref)
            for ref in dict.fromkeys((*admitted_input.designation.provenance_refs, *admitted_input.event.record.provenance_refs))
        ]
        if raw.get("provenance_refs") != expected_provenance:
            raise CompanyAssetAdmissionUnavailable("asset-aware input provenance differs from admitted exact source")
        input_handling = _designation_handling(admitted_input)
        if input_handling != handling:
            raise CompanyAssetAdmissionUnavailable(
                "asset-aware input handling differs from template handling; governed promotion is fail-closed"
            )
        input_admissions.append(admitted_input)
        normalized_inputs.append(dict(raw))

    if generation_profile == "company-docx-asset-aware-v1":
        material_basis = {
            "profile": generation_profile,
            "template": {
                "material_id": source_material_id,
                "version_id": source_version_id,
                "sha256": str(manifest["source_sha256"]),
            },
            "asset_inputs": normalized_inputs,
        }
        expected_input_digest = hashlib.sha256(
            json.dumps(material_basis, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if generation_input_digest != expected_input_digest:
            raise CompanyAssetAdmissionUnavailable("asset-aware generation material-input digest is invalid")

    return ExactCompanyGeneratedOutput(
        output_id=output_id,
        project_id=str(manifest["project_id"]),
        filename=str(manifest["filename"]),
        media_type=str(manifest["media_type"]),
        created_at=str(manifest["created_at"]),
        created_by=str(manifest["created_by"]),
        output_sha256=digest,
        source_material_id=source_material_id,
        source_version_id=source_version_id,
        source_sha256=str(manifest["source_sha256"]),
        generation_profile=generation_profile,
        generation_input_digest=generation_input_digest,
        source_admission=source,
        input_admissions=tuple(input_admissions),
        input_assets=tuple(normalized_inputs),
        handling=handling,
    )


def exact_generated_output_source_identities(
    *, output: ExactCompanyGeneratedOutput, actor: ActorContext
) -> tuple[Identity, Identity, Identity]:
    if not isinstance(output, ExactCompanyGeneratedOutput) or not isinstance(actor, ActorContext):
        raise TypeError("exact output identities require verified output and ActorContext")
    scope = actor.organization.organization_id.value
    return (
        Identity("transient-output", output.output_id, scope),
        Identity(
            "transient-output-version",
            f"{output.output_id}-{output.output_sha256[:24]}",
            scope,
        ),
        Identity("artifact", f"company-generated-{output.output_sha256[:32]}", scope),
    )


def build_generated_output_document_candidate(
    *,
    output: ExactCompanyGeneratedOutput,
    access: AccessContext,
    actor: ActorContext,
    candidate_created_at: datetime,
    document_title: str,
    semantic_role: str,
) -> DocumentVersionCandidate:
    """Map one exact transient Company output to a new Native Document candidate."""

    if not isinstance(output, ExactCompanyGeneratedOutput):
        raise TypeError("output must be ExactCompanyGeneratedOutput")
    if not isinstance(access, AccessContext) or not isinstance(actor, ActorContext):
        raise TypeError("candidate construction requires current AccessContext and ActorContext")
    if access.organization != actor.organization.organization_id or access.actor != actor.actual_principal.principal_id:
        raise PermissionError("Workspace access and governed promotion Actor/Organization must match")
    if not isinstance(candidate_created_at, datetime) or candidate_created_at.tzinfo is None or candidate_created_at.utcoffset() is None:
        raise ValueError("candidate_created_at must be timezone-aware")
    for label, value, maximum in (
        ("document_title", document_title, 320),
        ("semantic_role", semantic_role, 96),
    ):
        if not isinstance(value, str) or not value.strip() or len(" ".join(value.split())) > maximum:
            raise ValueError(f"{label} is outside the bounded Company promotion contract")

    scope = actor.organization.organization_id.value
    source_subject, source_version, artifact_id = exact_generated_output_source_identities(
        output=output, actor=actor
    )
    source_admission = output.source_admission
    all_admissions = (source_admission, *output.input_admissions)
    all_source_artifacts = tuple(item.admitted_document.artifacts[0] for item in all_admissions)
    document_subject = Identity("document", f"generated-output-{output.output_id}", scope)
    document_version = Identity(
        "document-version", f"generated-output-{output.output_id}-{output.output_sha256[:24]}", scope
    )
    handling = HandlingConstraints(
        classification=output.handling.classification,
        purpose=output.handling.purpose,
        rights=output.handling.rights,
        retention_rule=output.handling.retention_rule,
    )
    artifact = ArtifactContent(
        artifact_id=artifact_id,
        organization=actor.organization,
        content_ref=f"sha256:{output.output_sha256}",
        media_type=output.media_type,
        integrity_ref=output.output_sha256,
        rendition_role="original",
        handling=handling,
        source_artifact_ids=tuple(dict.fromkeys(item.artifact_id for item in all_source_artifacts)),
        transformation=output.generation_profile or "company-docx-generation",
        storage_locator="owner-local-company-materials/transient",
    )
    provenance_values: list[Identity] = [
        actor.actual_principal.principal_id,
        source_subject,
        source_version,
    ]
    for admission in all_admissions:
        record = admission.admitted_document.canonical_record
        source_input_artifact = admission.admitted_document.artifacts[0]
        provenance_values.extend(
            (
                record.subject_id,
                record.version_id,
                source_input_artifact.artifact_id,
                admission.designation.subject_id,
                admission.designation.version_id,
            )
        )
    provenance = tuple(dict.fromkeys(provenance_values))
    record = CanonicalRecord(
        subject_id=document_subject,
        version_id=document_version,
        semantic_type="platform.document",
        schema_version="p10.05-company-generated-output-1",
        organization=actor.organization,
        authority_mode=AuthorityMode.NATIVE,
        authority_scope=PROMOTED_OUTPUT_DOCUMENT_SCOPE,
        accountable_owner_id=actor.actual_principal.principal_id,
        creation_actor=actor,
        created_at=candidate_created_at,
        provenance_refs=provenance,
        integrity_metadata=(
            ("representation", "p10.05-exact-reviewed-transient-output"),
            ("source_output_sha256", output.output_sha256),
            ("generation_profile", output.generation_profile or "not-retained"),
            ("generation_input_digest", output.generation_input_digest or "not-retained"),
            ("source_state", "TransientOutput"),
        ),
        payload=(
            ("project_id", output.project_id),
            ("filename", output.filename),
            ("document_title", " ".join(document_title.split())),
            ("semantic_role", " ".join(semantic_role.split())),
            ("source_output_id", output.output_id),
            ("source_material_id", output.source_material_id),
            ("source_version_id", output.source_version_id),
        ),
        lifecycle_status="PromotionCandidate",
        predecessor_version_id=None,
    )
    return DocumentVersionCandidate(
        canonical_record=record,
        artifacts=(artifact,),
        designated_rendition_role="original",
    )


__all__ = [
    "ExactCompanyGeneratedOutput",
    "build_generated_output_document_candidate",
    "exact_generated_output_source_identities",
    "resolve_exact_generated_output",
]
