from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .access import AccessContext
from .company_asset_library import CompanyAssetLibrary, CompanyAssetLibraryError
from .company_materials import CompanyMaterialUnavailable, CompanyMaterialsError, CompanyMaterialsStore, _content_sha256


class CompanyAssetRetrievalError(RuntimeError):
    pass


class CompanyAssetContentUnavailable(CompanyAssetRetrievalError):
    pass


@dataclass(frozen=True, slots=True)
class CompanyAssetContent:
    path: Path
    filename: str
    media_type: str
    content_sha256: str
    lifecycle_view: str
    current: bool
    canonical: dict[str, Any]


class CompanyAssetRetrieval:
    """Read-only resolver for exact canonically admitted Company asset bytes."""

    def __init__(self, library: CompanyAssetLibrary, materials: CompanyMaterialsStore) -> None:
        self.library = library
        self.materials = materials

    def resolve(self, access: AccessContext, material_id: str, version_id: str) -> CompanyAssetContent:
        if not isinstance(access, AccessContext):
            raise CompanyAssetRetrievalError("server-authorized AccessContext is required")
        try:
            projection = self.library.project(access)
        except (CompanyAssetLibraryError, CompanyMaterialsError) as exc:
            raise CompanyAssetRetrievalError("Company Asset Library projection unavailable") from exc

        candidates: list[dict[str, Any]] = []
        for view in ("accepted", "archive"):
            values = projection.get("views", {}).get(view, [])
            if not isinstance(values, list):
                raise CompanyAssetRetrievalError("Company Asset Library projection is invalid")
            for item in values:
                if (
                    isinstance(item, dict)
                    and item.get("material_id") == material_id
                    and item.get("version_id") == version_id
                    and isinstance(item.get("canonical"), dict)
                ):
                    candidates.append(item)
        if len(candidates) != 1:
            raise CompanyAssetContentUnavailable("exact admitted Company asset version unavailable")
        item = candidates[0]

        try:
            staged = self.materials._version(access, material_id, version_id)
        except CompanyMaterialUnavailable as exc:
            raise CompanyAssetContentUnavailable("exact admitted Company asset version unavailable") from exc
        except CompanyMaterialsError as exc:
            raise CompanyAssetRetrievalError("exact admitted Company asset source unavailable") from exc

        sha256 = staged.get("content_sha256")
        filename = staged.get("filename")
        media_type = staged.get("media_type")
        canonical = item.get("canonical")
        if (
            not isinstance(sha256, str)
            or len(sha256) != 64
            or sha256 != item.get("content_sha256")
            or not isinstance(filename, str)
            or not filename
            or not isinstance(media_type, str)
            or media_type != item.get("media_type")
            or not isinstance(canonical, dict)
        ):
            raise CompanyAssetRetrievalError("admitted Company asset metadata mismatch")

        path = self.materials.blobs / sha256
        try:
            if path.is_symlink() or not path.is_file():
                raise CompanyAssetContentUnavailable("exact admitted Company asset bytes unavailable")
            content = path.read_bytes()
        except OSError as exc:
            raise CompanyAssetContentUnavailable("exact admitted Company asset bytes unavailable") from exc
        if _content_sha256(content) != sha256:
            raise CompanyAssetRetrievalError("admitted Company asset integrity mismatch")

        return CompanyAssetContent(
            path=path,
            filename=filename,
            media_type=media_type,
            content_sha256=sha256,
            lifecycle_view=str(item.get("lifecycle_view")),
            current=bool(canonical.get("current")),
            canonical=dict(canonical),
        )


__all__ = ["CompanyAssetContent", "CompanyAssetContentUnavailable", "CompanyAssetRetrieval", "CompanyAssetRetrievalError"]
