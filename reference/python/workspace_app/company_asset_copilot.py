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
MAX_COMPANY_TEXT_CONTEXT_BYTES = 16 * 1024
MAX_COMPANY_EVIDENCE = 3
_TEXT_MEDIA = frozenset({"text/plain", "text/markdown"})


class CompanyAssetCopilotHandlingResolver(Protocol):
    def permitted_reuse(
        self, access: AccessContext, material_id: str, version_id: str
    ) -> tuple[str, ...]: ...


class P1003CompanyAssetCopilotHandlingResolver:
    """Resolve reuse permission from canonical committed Organizational Asset handling."""

    def __init__(self, admission: P1003CompanyAssetAdmissionExecutor) -> None:
        if not isinstance(admission, P1003CompanyAssetAdmissionExecutor):
            raise TypeError("P10.09-C handling resolver requires P10.03 canonical admission executor")
        self.admission = admission

    def permitted_reuse(
        self, access: AccessContext, material_id: str, version_id: str
    ) -> tuple[str, ...]:
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
        return policy.permitted_reuse


@dataclass(frozen=True, slots=True)
class CompanyAssetCopilotContractGate:
    """Runtime gate populated only from an effective exact Product Contract publication."""

    version: str
    lifecycle: str
    operation: str

    @property
    def effective(self) -> bool:
        return (
            self.version == P10_09_C_VERSION
            and self.lifecycle in {"Provisional", "Stable"}
            and self.operation == P10_09_C_OPERATION
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
                permitted_reuse = self.handling.permitted_reuse(access, material_id, version_id)
            except CompanyAssetAdmissionUnavailable:
                limitations.append(f"Canonical handling for Company asset “{title}” could not be revalidated and was withheld.")
                continue
            if AI_GROUNDING_REUSE not in permitted_reuse:
                continue

            model_context: str | None = None
            searchable = f"{title} {role} {purpose}"
            if media_type in _TEXT_MEDIA:
                try:
                    content = self.retrieval.resolve(access, material_id, version_id)
                    raw = content.path.read_bytes()
                except (CompanyAssetContentUnavailable, CompanyAssetRetrievalError, OSError):
                    limitations.append(f"Eligible Company text source “{title}” could not be revalidated and was withheld.")
                    continue
                if not content.current or content.content_sha256 != item.get("content_sha256"):
                    limitations.append(f"Eligible Company text source “{title}” is not the exact current admitted version and was withheld.")
                    continue
                if len(raw) > MAX_COMPANY_TEXT_CONTEXT_BYTES:
                    limitations.append(f"Eligible Company text source “{title}” exceeds the bounded AI context size and was withheld.")
                    continue
                try:
                    model_context = raw.decode("utf-8")
                except UnicodeDecodeError:
                    limitations.append(f"Eligible Company text source “{title}” is not valid UTF-8 and was withheld.")
                    continue
                searchable += " " + model_context

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
            )
            candidates.append((score, evidence))

        ordered = tuple(
            evidence
            for _, evidence in sorted(candidates, key=lambda pair: (-pair[0], pair[1].source_id))[:MAX_COMPANY_EVIDENCE]
        )
        return ordered, tuple(dict.fromkeys(limitations))


__all__ = [
    "AI_GROUNDING_REUSE",
    "CompanyAssetCopilotContractGate",
    "CompanyAssetCopilotEvidenceSource",
    "CompanyAssetCopilotHandlingResolver",
    "P1003CompanyAssetCopilotHandlingResolver",
    "MAX_COMPANY_TEXT_CONTEXT_BYTES",
    "P10_09_C_OPERATION",
    "P10_09_C_VERSION",
]
