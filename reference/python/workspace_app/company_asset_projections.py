from __future__ import annotations

from dataclasses import dataclass

from .access import AccessContext
from .company_asset_library import CompanyAssetLibrary, CompanyAssetLibraryError
from .company_asset_retrieval import (
    CompanyAssetContentUnavailable,
    CompanyAssetRetrieval,
    CompanyAssetRetrievalError,
)

_TEXT_MEDIA = frozenset({"text/plain", "text/markdown"})
MAX_DERIVED_TEXT_BYTES = 64 * 1024


class CompanyAssetProjectionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CompanyAssetTextProjection:
    """Rebuildable non-authoritative text derived from one exact admitted asset version."""

    material_id: str
    version_id: str
    title: str
    media_type: str
    content_sha256: str
    document_version: str
    designation_version: str
    text: str | None
    status: str
    limitation: str | None
    canonical_authority: bool = False
    knowledge_status: str = "not-validated-knowledge"
    rebuildable: bool = True

    def __post_init__(self) -> None:
        if len(self.content_sha256) != 64:
            raise ValueError("derived projection requires exact source SHA-256")
        if self.canonical_authority:
            raise ValueError("derived projection cannot become canonical authority")
        if self.knowledge_status != "not-validated-knowledge":
            raise ValueError("derived projection cannot claim validated Knowledge")
        if self.status == "ready":
            if not self.text or self.limitation is not None:
                raise ValueError("ready derived projection requires text without a limitation")
        elif self.status == "unsupported":
            if self.text is not None or not self.limitation:
                raise ValueError("unsupported derived projection must be explicit and contain no text")
        else:
            raise ValueError("unsupported derived projection status")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "arvectum.workspace.company-asset-text-projection/1",
            "material_id": self.material_id,
            "version_id": self.version_id,
            "title": self.title,
            "media_type": self.media_type,
            "content_sha256": self.content_sha256,
            "document_version": self.document_version,
            "designation_version": self.designation_version,
            "text": self.text,
            "status": self.status,
            "limitation": self.limitation,
            "canonical_authority": self.canonical_authority,
            "knowledge_status": self.knowledge_status,
            "rebuildable": self.rebuildable,
        }


class CompanyAssetDerivedProjectionService:
    """Product-local read-only P10.09-D projection over already-admitted Company assets."""

    def __init__(self, library: CompanyAssetLibrary, retrieval: CompanyAssetRetrieval) -> None:
        self.library = library
        self.retrieval = retrieval

    def _exact_current_item(
        self, access: AccessContext, material_id: str, version_id: str
    ) -> dict[str, object]:
        if not isinstance(access, AccessContext):
            raise CompanyAssetProjectionError("server-authorized AccessContext is required")
        try:
            projection = self.library.project(access)
        except CompanyAssetLibraryError as exc:
            raise CompanyAssetProjectionError("Company Asset Library projection unavailable") from exc
        matches: list[dict[str, object]] = []
        views = projection.get("views", {})
        if not isinstance(views, dict):
            raise CompanyAssetProjectionError("Company Asset Library projection is invalid")
        for view in ("accepted", "archive"):
            values = views.get(view, [])
            if not isinstance(values, list):
                raise CompanyAssetProjectionError("Company Asset Library projection is invalid")
            for value in values:
                if (
                    isinstance(value, dict)
                    and value.get("material_id") == material_id
                    and value.get("version_id") == version_id
                    and isinstance(value.get("canonical"), dict)
                ):
                    matches.append(value)
        if len(matches) != 1:
            raise CompanyAssetContentUnavailable("exact admitted Company asset version unavailable")
        item = matches[0]
        canonical = item["canonical"]
        assert isinstance(canonical, dict)
        if canonical.get("current") is not True:
            raise CompanyAssetContentUnavailable("derived projection requires the exact current admitted version")
        return item

    def text_projection(
        self, access: AccessContext, material_id: str, version_id: str
    ) -> CompanyAssetTextProjection:
        item = self._exact_current_item(access, material_id, version_id)
        canonical = item["canonical"]
        assert isinstance(canonical, dict)
        title = item.get("title")
        media_type = item.get("media_type")
        sha256 = item.get("content_sha256")
        document_version = canonical.get("document_version")
        designation_version = canonical.get("designation_version")
        if not all(
            isinstance(value, str) and value
            for value in (title, media_type, sha256, document_version, designation_version)
        ):
            raise CompanyAssetProjectionError("exact admitted source metadata is incomplete")

        if media_type not in _TEXT_MEDIA:
            return CompanyAssetTextProjection(
                material_id=material_id,
                version_id=version_id,
                title=title,
                media_type=media_type,
                content_sha256=sha256,
                document_version=document_version,
                designation_version=designation_version,
                text=None,
                status="unsupported",
                limitation=f"Text extraction for {media_type} is not admitted in this bounded projection.",
            )

        try:
            content = self.retrieval.resolve(access, material_id, version_id)
        except (CompanyAssetContentUnavailable, CompanyAssetRetrievalError) as exc:
            raise CompanyAssetProjectionError("exact admitted source could not be revalidated") from exc
        if (
            not content.current
            or content.media_type != media_type
            or content.content_sha256 != sha256
            or content.canonical.get("document_version") != document_version
            or content.canonical.get("designation_version") != designation_version
        ):
            raise CompanyAssetProjectionError("exact admitted source differs from canonical projection evidence")
        try:
            raw = content.path.read_bytes()
        except OSError as exc:
            raise CompanyAssetProjectionError("exact admitted source bytes unavailable") from exc
        if len(raw) > MAX_DERIVED_TEXT_BYTES:
            return CompanyAssetTextProjection(
                material_id=material_id,
                version_id=version_id,
                title=title,
                media_type=media_type,
                content_sha256=sha256,
                document_version=document_version,
                designation_version=designation_version,
                text=None,
                status="unsupported",
                limitation="Text source exceeds the bounded extraction size; no partial projection was produced.",
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return CompanyAssetTextProjection(
                material_id=material_id,
                version_id=version_id,
                title=title,
                media_type=media_type,
                content_sha256=sha256,
                document_version=document_version,
                designation_version=designation_version,
                text=None,
                status="unsupported",
                limitation="Text source is not valid UTF-8; no replacement or fabricated text was produced.",
            )
        if not text.strip():
            return CompanyAssetTextProjection(
                material_id=material_id,
                version_id=version_id,
                title=title,
                media_type=media_type,
                content_sha256=sha256,
                document_version=document_version,
                designation_version=designation_version,
                text=None,
                status="unsupported",
                limitation="Text source is empty after exact UTF-8 decoding.",
            )
        return CompanyAssetTextProjection(
            material_id=material_id,
            version_id=version_id,
            title=title,
            media_type=media_type,
            content_sha256=sha256,
            document_version=document_version,
            designation_version=designation_version,
            text=text,
            status="ready",
            limitation=None,
        )


__all__ = [
    "CompanyAssetDerivedProjectionService",
    "CompanyAssetProjectionError",
    "CompanyAssetTextProjection",
    "MAX_DERIVED_TEXT_BYTES",
]
