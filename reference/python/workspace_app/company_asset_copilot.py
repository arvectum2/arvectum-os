from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Protocol

from .access import AccessContext
from .company_asset_library import (
    CompanyAssetAdmissionUnavailable,
    CompanyAssetLibrary,
    CompanyAssetLibraryError,
    P1003CompanyAssetAdmissionExecutor,
)
from .company_asset_retrieval import (
    CompanyAssetContentUnavailable,
    CompanyAssetRetrieval,
    CompanyAssetRetrievalError,
)
from .copilot import CopilotEvidence
from arvectum_os_ref.organizational_asset_admission import OrganizationalAssetHandlingPolicy

AI_GROUNDING_REUSE = "company-internal-ai-grounding"
P10_09_C_OPERATION = "workspace.copilot.ground-company-assets"
P10_09_C_VERSION = "0.3.0"
P10_09_C_LIFECYCLE = "Provisional"
P10_09_C_CANONICAL_CONTRACT_PATH = (
    "docs/contracts/P10-09-C-ARVECTUM-COMPANY-WORKSPACE-PRODUCT-CONTRACT-PROVISIONAL-v0.3.0.md"
)
P10_09_C_CANONICAL_BLOB_SHA = "58252df4079a84ff2e526124f7a1f54cee919b91"
P10_09_C_APPROVED_DRAFT_BLOB_SHA = "0b21eb3f05a0cdae5c3765a10dfdd27f9d8c4292"
P10_09_C_APPROVAL_COMMIT = "500e2adb92384cbd5008aee21a0391864e5a8a1d"
MAX_COMPANY_TEXT_CONTEXT_BYTES = 16 * 1024
MAX_COMPANY_MODEL_CONTEXT_BYTES = 4 * 1024
MAX_COMPANY_EVIDENCE = 3
_TEXT_MEDIA = frozenset({"text/plain", "text/markdown"})


def _minimized_text_context(text: str, tokens: tuple[str, ...]) -> str | None:
    """Return only bounded windows around question-term matches, never the whole eligible file by default."""

    folded = text.casefold()
    windows: list[tuple[int, int]] = []
    radius = 420
    for token in tokens:
        start = 0
        for _ in range(3):
            position = folded.find(token, start)
            if position < 0:
                break
            windows.append((max(0, position - radius), min(len(text), position + len(token) + radius)))
            start = position + len(token)
    if not windows:
        return None
    windows.sort()
    merged: list[tuple[int, int]] = []
    for start, end in windows:
        if merged and start <= merged[-1][1] + 80:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    pieces = [text[start:end].strip() for start, end in merged[:4] if text[start:end].strip()]
    if not pieces:
        return None
    joined = "\n[… question-scoped excerpt …]\n".join(pieces)
    encoded = joined.encode("utf-8")
    if len(encoded) > MAX_COMPANY_MODEL_CONTEXT_BYTES:
        joined = encoded[:MAX_COMPANY_MODEL_CONTEXT_BYTES].decode("utf-8", errors="ignore").rstrip()
    return joined or None


@dataclass(frozen=True, slots=True)
class CanonicalCompanyAssetGroundingEvidence:
    permitted_reuse: tuple[str, ...]
    content_sha256: str
    document_version: str
    designation_version: str
    event_version: str
    provenance_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.content_sha256) != 64:
            raise ValueError("canonical Company asset evidence requires exact SHA-256")


class CompanyAssetCopilotHandlingResolver(Protocol):
    def resolve(
        self, access: AccessContext, material_id: str, version_id: str
    ) -> CanonicalCompanyAssetGroundingEvidence: ...


class P1003CompanyAssetCopilotHandlingResolver:
    """Resolve AI reuse and exact Artifact integrity from canonical committed admission."""

    def __init__(self, admission: P1003CompanyAssetAdmissionExecutor) -> None:
        if not isinstance(admission, P1003CompanyAssetAdmissionExecutor):
            raise TypeError("P10.09-C handling resolver requires P10.03 canonical admission executor")
        self.admission = admission

    @staticmethod
    def _identity_text(identity: object) -> str:
        return f"{identity.namespace}:{identity.scope}:{identity.value}"  # type: ignore[attr-defined]

    def resolve(
        self, access: AccessContext, material_id: str, version_id: str
    ) -> CanonicalCompanyAssetGroundingEvidence:
        matches = tuple(
            item for item in self.admission.state.committed
            if dict(item.admitted_document.canonical_record.payload).get("source_material_id") == material_id
            and dict(item.admitted_document.canonical_record.payload).get("source_version_id") == version_id
            and item.admitted_document.canonical_record.organization.organization_id == access.organization
        )
        if len(matches) != 1:
            raise CompanyAssetAdmissionUnavailable("exact canonical Company asset handling is unavailable")
        admission = matches[0]
        payload = dict(admission.designation.payload)
        required = ("classification", "purpose", "rights", "retention_rule", "deletion_rule", "permitted_reuse")
        if any(not isinstance(payload.get(key), str) or not str(payload[key]).strip() for key in required):
            raise CompanyAssetAdmissionUnavailable("canonical Company asset handling is incomplete")
        policy = OrganizationalAssetHandlingPolicy(
            classification=str(payload["classification"]),
            purpose=str(payload["purpose"]),
            rights=tuple(part.strip() for part in str(payload["rights"]).split("|") if part.strip()),
            retention_rule=str(payload["retention_rule"]),
            deletion_rule=str(payload["deletion_rule"]),
            permitted_reuse=tuple(part.strip() for part in str(payload["permitted_reuse"]).split("|") if part.strip()),
        )
        artifacts = admission.admitted_document.artifacts
        if len(artifacts) != 1 or artifacts[0].handling != policy.cap001_constraints:
            raise CompanyAssetAdmissionUnavailable("canonical designation handling differs from admitted Artifact")
        artifact = artifacts[0]
        integrity = artifact.integrity_ref
        record_integrity = dict(admission.admitted_document.canonical_record.integrity_metadata).get("source_sha256")
        if (
            not isinstance(integrity, str)
            or len(integrity) != 64
            or artifact.content_ref != f"sha256:{integrity}"
            or record_integrity != integrity
        ):
            raise CompanyAssetAdmissionUnavailable("canonical Company Artifact integrity evidence is inconsistent")
        provenance = tuple(
            self._identity_text(ref)
            for ref in (
                *admission.admitted_document.canonical_record.provenance_refs,
                *admission.designation.provenance_refs,
                *admission.event.record.provenance_refs,
            )
        )
        return CanonicalCompanyAssetGroundingEvidence(
            permitted_reuse=policy.permitted_reuse,
            content_sha256=integrity,
            document_version=self._identity_text(admission.admitted_document.version_id),
            designation_version=self._identity_text(admission.designation.version_id),
            event_version=self._identity_text(admission.event.record.version_id),
            provenance_refs=tuple(dict.fromkeys(provenance)),
        )


@dataclass(frozen=True, slots=True)
class CompanyAssetCopilotContractGate:
    """Runtime gate populated only from an effective exact Product Contract publication."""

    version: str
    lifecycle: str
    operation: str
    canonical_source_path: str = P10_09_C_CANONICAL_CONTRACT_PATH
    canonical_source_blob_sha: str = P10_09_C_CANONICAL_BLOB_SHA
    approved_draft_blob_sha: str = P10_09_C_APPROVED_DRAFT_BLOB_SHA
    approval_commit: str = P10_09_C_APPROVAL_COMMIT

    @classmethod
    def current(cls) -> "CompanyAssetCopilotContractGate":
        return cls(P10_09_C_VERSION, P10_09_C_LIFECYCLE, P10_09_C_OPERATION)

    @property
    def effective(self) -> bool:
        return (
            self.version == P10_09_C_VERSION
            and self.lifecycle == P10_09_C_LIFECYCLE
            and self.operation == P10_09_C_OPERATION
            and self.canonical_source_path == P10_09_C_CANONICAL_CONTRACT_PATH
            and self.canonical_source_blob_sha == P10_09_C_CANONICAL_BLOB_SHA
            and self.approved_draft_blob_sha == P10_09_C_APPROVED_DRAFT_BLOB_SHA
            and self.approval_commit == P10_09_C_APPROVAL_COMMIT
        )


class CompanyAssetCopilotEvidenceSource:
    """Product-owned Company Asset evidence adapter for bounded Copilot grounding."""

    def __init__(
        self,
        library: CompanyAssetLibrary,
        retrieval: CompanyAssetRetrieval,
        handling: CompanyAssetCopilotHandlingResolver,
        contract: CompanyAssetCopilotContractGate,
    ) -> None:
        self.library = library
        self.retrieval = retrieval
        self.handling = handling
        self.contract = contract

    @staticmethod
    def _tokens(question: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(re.findall(r"[\w.-]{3,}", question.casefold(), flags=re.UNICODE)))

    @staticmethod
    def _opaque_source_id(access: AccessContext, material_id: str, version_id: str) -> str:
        raw = f"{access.organization.namespace}:{access.organization.scope}:{access.organization.value}|{material_id}|{version_id}"
        return "company-asset:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


    def evidence(
        self, access: AccessContext, question: str
    ) -> tuple[tuple[CopilotEvidence, ...], tuple[str, ...]]:
        if not self.contract.effective:
            return (), (
                "Company asset AI grounding is unavailable until exact Product Contract 0.3.0 is effective.",
            )
        try:
            projection = self.library.project(access)
        except CompanyAssetLibraryError:
            return (), ("Current admitted Company asset evidence is unavailable.",)

        candidates: list[tuple[int, CopilotEvidence]] = []
        limitations: list[str] = []
        tokens = self._tokens(question)
        views = projection.get("views", {})
        values = []
        if isinstance(views, dict):
            for view in ("accepted", "archive"):
                items = views.get(view, [])
                if isinstance(items, list):
                    values.extend(items)

        for item in values:
            if not isinstance(item, dict):
                continue
            canonical = item.get("canonical")
            if not isinstance(canonical, dict) or canonical.get("current") is not True:
                continue
            material_id = item.get("material_id")
            version_id = item.get("version_id")
            title = item.get("title")
            role = item.get("semantic_role")
            media_type = item.get("media_type")
            purpose = item.get("purpose")
            if not all(isinstance(v, str) and v for v in (material_id, version_id, title, role, media_type, purpose)):
                continue
            try:
                canonical_evidence = self.handling.resolve(access, material_id, version_id)
            except CompanyAssetAdmissionUnavailable:
                limitations.append(f"Canonical handling/integrity for Company asset “{title}” could not be revalidated and was withheld.")
                continue
            if AI_GROUNDING_REUSE not in canonical_evidence.permitted_reuse:
                continue
            try:
                content = self.retrieval.resolve(access, material_id, version_id)
            except (CompanyAssetContentUnavailable, CompanyAssetRetrievalError):
                limitations.append(f"Eligible Company source “{title}” could not be revalidated and was withheld.")
                continue
            if (
                not content.current
                or content.content_sha256 != item.get("content_sha256")
                or content.content_sha256 != canonical_evidence.content_sha256
                or canonical.get("document_version") != canonical_evidence.document_version
                or canonical.get("designation_version") != canonical_evidence.designation_version
                or canonical.get("event_version") != canonical_evidence.event_version
            ):
                limitations.append(f"Eligible Company source “{title}” differs from exact canonical admission evidence and was withheld.")
                continue

            model_context: str | None = None
            searchable = f"{title} {role} {purpose}"
            if media_type in _TEXT_MEDIA:
                try:
                    raw = content.path.read_bytes()
                except OSError:
                    limitations.append(f"Eligible Company text source “{title}” bytes became unavailable and were withheld.")
                    continue
                if len(raw) > MAX_COMPANY_TEXT_CONTEXT_BYTES:
                    limitations.append(f"Eligible Company text source “{title}” exceeds the bounded AI context size and was withheld.")
                    continue
                try:
                    decoded = raw.decode("utf-8")
                except UnicodeDecodeError:
                    limitations.append(f"Eligible Company text source “{title}” is not valid UTF-8 and was withheld.")
                    continue
                searchable += " " + decoded
                model_context = _minimized_text_context(decoded, tokens)

            folded = searchable.casefold()
            score = sum(3 if len(token) >= 8 else 1 for token in tokens if token in folded)
            if score <= 0:
                continue
            summary = (
                f"Current admitted Company asset “{title}” ({role}) is eligible for bounded AI grounding."
                if model_context is not None
                else f"Current admitted Company asset “{title}” ({role}) is eligible as metadata evidence; its {media_type} bytes are not interpreted in this slice."
            )
            evidence = CopilotEvidence(
                source_id=self._opaque_source_id(access, material_id, version_id),
                label=title,
                summary=summary,
                authority="Native · governed Arvectum Company asset",
                freshness="current-verified",
                open_href="/company-materials",
                semantic_role=f"Company asset · {role}",
                knowledge_role="Admitted document source — not validated Knowledge",
                model_context=model_context,
                server_provenance=(
                    f"material_id:{material_id}",
                    f"version_id:{version_id}",
                    f"content_sha256:{canonical_evidence.content_sha256}",
                    f"document_version:{canonical_evidence.document_version}",
                    f"designation_version:{canonical_evidence.designation_version}",
                    f"event_version:{canonical_evidence.event_version}",
                    f"contract_blob:{self.contract.canonical_source_blob_sha}",
                    *(f"provenance:{ref}" for ref in canonical_evidence.provenance_refs),
                ),
            )
            candidates.append((score, evidence))

        ordered = tuple(
            evidence
            for _, evidence in sorted(candidates, key=lambda pair: (-pair[0], pair[1].source_id))[:MAX_COMPANY_EVIDENCE]
        )
        return ordered, tuple(dict.fromkeys(limitations))


__all__ = [
    "AI_GROUNDING_REUSE",
    "CanonicalCompanyAssetGroundingEvidence",
    "CompanyAssetCopilotContractGate",
    "CompanyAssetCopilotEvidenceSource",
    "CompanyAssetCopilotHandlingResolver",
    "P1003CompanyAssetCopilotHandlingResolver",
    "MAX_COMPANY_MODEL_CONTEXT_BYTES",
    "MAX_COMPANY_TEXT_CONTEXT_BYTES",
    "P10_09_C_APPROVAL_COMMIT",
    "P10_09_C_APPROVED_DRAFT_BLOB_SHA",
    "P10_09_C_CANONICAL_BLOB_SHA",
    "P10_09_C_CANONICAL_CONTRACT_PATH",
    "P10_09_C_LIFECYCLE",
    "P10_09_C_OPERATION",
    "P10_09_C_VERSION",
]
