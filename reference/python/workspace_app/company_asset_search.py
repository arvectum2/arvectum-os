from __future__ import annotations

from dataclasses import dataclass

from .access import AccessContext
from .company_asset_library import CompanyAssetLibrary, CompanyAssetLibraryError
from .company_asset_projections import CompanyAssetDerivedProjectionService, CompanyAssetProjectionError

MAX_SEARCH_QUERY_CHARS = 200
MAX_SEARCH_RESULTS = 20
_EXCERPT_RADIUS = 80


class CompanyAssetSearchError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CompanyAssetSearchHit:
    material_id: str
    version_id: str
    title: str
    content_sha256: str
    document_version: str
    designation_version: str
    excerpt: str
    canonical_authority: bool = False
    knowledge_status: str = "not-validated-knowledge"
    rebuildable: bool = True

    def to_payload(self) -> dict[str, object]:
        return {
            "material_id": self.material_id,
            "version_id": self.version_id,
            "title": self.title,
            "content_sha256": self.content_sha256,
            "document_version": self.document_version,
            "designation_version": self.designation_version,
            "excerpt": self.excerpt,
            "canonical_authority": self.canonical_authority,
            "knowledge_status": self.knowledge_status,
            "rebuildable": self.rebuildable,
        }


class CompanyAssetSearchService:
    """Bounded read-only substring search rebuilt from current exact admitted text projections."""

    def __init__(self, library: CompanyAssetLibrary, projections: CompanyAssetDerivedProjectionService) -> None:
        self.library = library
        self.projections = projections

    @staticmethod
    def _query(value: object) -> str:
        if not isinstance(value, str):
            raise CompanyAssetSearchError("search query must be text")
        query = value.strip()
        if not query or len(query) > MAX_SEARCH_QUERY_CHARS:
            raise CompanyAssetSearchError("search query must contain 1..200 characters")
        return query

    @staticmethod
    def _excerpt(text: str, start: int, length: int) -> str:
        left = max(0, start - _EXCERPT_RADIUS)
        right = min(len(text), start + length + _EXCERPT_RADIUS)
        prefix = "…" if left else ""
        suffix = "…" if right < len(text) else ""
        return f"{prefix}{text[left:right]}{suffix}"

    def search(self, access: AccessContext, query: object, *, limit: int = 10) -> dict[str, object]:
        if not isinstance(access, AccessContext):
            raise CompanyAssetSearchError("server-authorized AccessContext is required")
        needle = self._query(query)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_SEARCH_RESULTS:
            raise CompanyAssetSearchError("search limit must be an integer from 1 to 20")
        try:
            library_projection = self.library.project(access)
        except CompanyAssetLibraryError as exc:
            raise CompanyAssetSearchError("Company Asset Library projection unavailable") from exc
        views = library_projection.get("views")
        if not isinstance(views, dict) or not isinstance(views.get("accepted"), list):
            raise CompanyAssetSearchError("Company Asset Library projection is invalid")

        folded = needle.casefold()
        hits: list[CompanyAssetSearchHit] = []
        unsupported_current_sources = 0
        for item in views["accepted"]:
            if not isinstance(item, dict):
                raise CompanyAssetSearchError("Company Asset Library projection is invalid")
            canonical = item.get("canonical")
            material_id = item.get("material_id")
            version_id = item.get("version_id")
            if not isinstance(canonical, dict) or canonical.get("current") is not True:
                continue
            if not isinstance(material_id, str) or not isinstance(version_id, str):
                raise CompanyAssetSearchError("Company Asset Library projection is invalid")
            try:
                projection = self.projections.text_projection(access, material_id, version_id)
            except CompanyAssetProjectionError as exc:
                raise CompanyAssetSearchError("exact admitted source could not be safely searched") from exc
            if projection.status != "ready" or projection.text is None:
                unsupported_current_sources += 1
                continue
            folded_text = projection.text.casefold()
            position = folded_text.find(folded)
            if position < 0:
                continue
            hits.append(
                CompanyAssetSearchHit(
                    material_id=projection.material_id,
                    version_id=projection.version_id,
                    title=projection.title,
                    content_sha256=projection.content_sha256,
                    document_version=projection.document_version,
                    designation_version=projection.designation_version,
                    excerpt=self._excerpt(projection.text, position, len(needle)),
                )
            )
            if len(hits) >= limit:
                break

        return {
            "schema": "arvectum.workspace.company-asset-search/1",
            "query": needle,
            "hits": [hit.to_payload() for hit in hits],
            "limitations": {
                "mode": "bounded-case-insensitive-substring",
                "persisted_index": False,
                "semantic_search": False,
                "unsupported_current_sources": unsupported_current_sources,
            },
            "governance": {
                "canonical_authority": False,
                "rebuildable_from_exact_admitted_sources": True,
                "validated_knowledge_created": False,
                "organization_scope_resolved_server_side": True,
            },
        }


__all__ = [
    "CompanyAssetSearchError",
    "CompanyAssetSearchHit",
    "CompanyAssetSearchService",
    "MAX_SEARCH_QUERY_CHARS",
    "MAX_SEARCH_RESULTS",
]
