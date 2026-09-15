from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse

from .access import AccessContext, WorkspaceAccessError
from .company_asset_library import (
    CompanyAssetAdmissionExecutor,
    CompanyAssetAdmissionUnavailable,
    CompanyAssetLibrary,
    CompanyAssetLibraryError,
    CompanyAssetReviewError,
)
from .company_asset_retrieval import (
    CompanyAssetContentUnavailable,
    CompanyAssetRetrieval,
    CompanyAssetRetrievalError,
)
from .company_materials import (
    CompanyMaterialUnavailable,
    CompanyMaterialsError,
    CompanyMaterialsInputError,
    CompanyMaterialsStore,
)
from .company_portfolio import CompanyPortfolioError, RuntimeCompanyPortfolioProvider
from .company_portfolio_verified import VerifiedRuntimeCompanyPortfolioProvider
from .main import CSRF_HEADER, _identity_key, _security_event
from .security import WorkspaceSession

MAX_STAGE_REQUEST_BYTES = 12 * 1024 * 1024
MAX_GENERATE_REQUEST_BYTES = 16 * 1024
MAX_REVIEW_REQUEST_BYTES = 8 * 1024
MAX_REJECT_REQUEST_BYTES = 4 * 1024


def _bounded_json_body(limit: int, code: str):
    async def dependency(request: Request) -> object:
        if request.headers.get("transfer-encoding"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code)
        raw_length = request.headers.get("content-length")
        if raw_length is not None:
            try:
                length = int(raw_length)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code) from None
            if length <= 0 or length > limit:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code)
        raw = await request.body()
        if not raw or len(raw) > limit:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code) from None

    return dependency


def install_f11_routes(
    app: FastAPI,
    *,
    portfolio_provider: RuntimeCompanyPortfolioProvider | None = None,
    materials_store: CompanyMaterialsStore | None = None,
    asset_admission: CompanyAssetAdmissionExecutor | None = None,
    asset_library: CompanyAssetLibrary | None = None,
) -> FastAPI:
    """Install bounded F11/P10.04 routes inside the same-origin Workspace BFF.

    Canonical admission is intentionally injected as a server-side executor.  If
    no current governed executor is installed the UI remains readable and
    reviewable, but admission fails closed rather than manufacturing authority.
    """

    settings = app.state.settings
    store = app.state.session_store
    resolver = app.state.access_resolver
    portfolio = portfolio_provider or VerifiedRuntimeCompanyPortfolioProvider(cache_root=Path(settings.runtime_root))
    materials = materials_store or CompanyMaterialsStore(Path(settings.runtime_root))
    library = asset_library or CompanyAssetLibrary(materials, asset_admission)
    retrieval = CompanyAssetRetrieval(library, materials)
    app.state.company_portfolio_provider = portfolio
    app.state.company_materials_store = materials
    app.state.company_asset_library = library
    app.state.company_asset_retrieval = retrieval

    # Existing Workspace creates the SPA catch-all before this product boundary is
    # composed. Temporarily remove exactly that route so API routes remain reachable,
    # then restore it as the final route. Static /assets remains untouched.
    spa_routes = [route for route in app.router.routes if getattr(route, "path", None) == "/{path:path}"]
    if len(spa_routes) != 1:
        raise RuntimeError("F11 route installation requires exactly one existing Workspace SPA catch-all")
    spa_route = spa_routes[0]
    app.router.routes.remove(spa_route)

    def authorize_current(request: Request) -> tuple[WorkspaceSession, AccessContext]:
        session_id = request.cookies.get(settings.cookie_name)
        session = store.get(session_id)
        if session is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="SESSION_REQUIRED")
        try:
            access = resolver.authorize()
        except WorkspaceAccessError as exc:
            store.revoke(session_id)
            _security_event("ACCESS_REVALIDATION_DENIED", request, store, str(exc))
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ACCESS_DENIED") from exc
        if session.organization_key != _identity_key(access.organization) or session.actor_key != _identity_key(access.actor):
            store.revoke(session_id)
            _security_event("CONTEXT_BINDING_CHANGED", request, store)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CONTEXT_CHANGED")
        return session, access

    def csrf_current(
        request: Request,
        current: tuple[WorkspaceSession, AccessContext] = Depends(authorize_current),
    ) -> tuple[WorkspaceSession, AccessContext]:
        session, access = current
        if not store.csrf_matches(session, request.headers.get(CSRF_HEADER)):
            _security_event("CSRF_REJECTED", request, store)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF_REJECTED")
        return session, access

    @app.get("/api/app/v1/company/portfolio")
    async def company_portfolio(
        refresh: bool = False,
        current: tuple[WorkspaceSession, AccessContext] = Depends(authorize_current),
    ) -> dict[str, Any]:
        _, access = current
        try:
            if isinstance(portfolio, VerifiedRuntimeCompanyPortfolioProvider):
                return portfolio.project(access, force_refresh=refresh)
            return portfolio.project(access)
        except CompanyPortfolioError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="COMPANY_PORTFOLIO_UNAVAILABLE") from None

    @app.get("/api/app/v1/company-materials")
    async def company_materials(
        current: tuple[WorkspaceSession, AccessContext] = Depends(authorize_current),
    ) -> dict[str, Any]:
        _, access = current
        try:
            return materials.project(access)
        except CompanyMaterialsError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="COMPANY_MATERIALS_UNAVAILABLE") from None

    @app.post("/api/app/v1/company-materials")
    async def stage_company_material(
        payload: object = Depends(_bounded_json_body(MAX_STAGE_REQUEST_BYTES, "COMPANY_MATERIAL_INPUT_REJECTED")),
        current: tuple[WorkspaceSession, AccessContext] = Depends(csrf_current),
    ) -> dict[str, Any]:
        _, access = current
        try:
            return materials.stage(access, payload)
        except CompanyMaterialsInputError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="COMPANY_MATERIAL_INPUT_REJECTED") from None
        except CompanyMaterialsError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="COMPANY_MATERIAL_STAGE_FAILED") from None

    @app.get("/api/app/v1/company-assets")
    async def company_asset_library(
        current: tuple[WorkspaceSession, AccessContext] = Depends(authorize_current),
    ) -> dict[str, Any]:
        _, access = current
        try:
            return library.project(access)
        except (CompanyAssetLibraryError, CompanyMaterialsError):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="COMPANY_ASSET_LIBRARY_UNAVAILABLE") from None

    @app.get("/api/app/v1/company-assets/{material_id}/versions/{version_id}/content")
    async def retrieve_company_asset_content(
        material_id: str,
        version_id: str,
        download: bool = False,
        current: tuple[WorkspaceSession, AccessContext] = Depends(authorize_current),
    ) -> FileResponse:
        _, access = current
        try:
            content = retrieval.resolve(access, material_id, version_id)
        except CompanyAssetContentUnavailable:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="COMPANY_ASSET_CONTENT_UNAVAILABLE") from None
        except CompanyAssetRetrievalError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="COMPANY_ASSET_CONTENT_INTEGRITY_FAILED") from None
        disposition = "attachment" if download else "inline"
        encoded_filename = quote(content.filename, safe="")
        return FileResponse(
            content.path,
            media_type=content.media_type,
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": f"{disposition}; filename*=UTF-8''{encoded_filename}",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get("/api/app/v1/company-assets/export")
    async def export_company_asset_library(
        limit: int = 100,
        current: tuple[WorkspaceSession, AccessContext] = Depends(authorize_current),
    ) -> dict[str, Any]:
        _, access = current
        try:
            return library.export(access, limit=limit)
        except CompanyAssetReviewError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="COMPANY_ASSET_EXPORT_REJECTED") from None
        except (CompanyAssetLibraryError, CompanyMaterialsError):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="COMPANY_ASSET_LIBRARY_UNAVAILABLE") from None

    @app.post("/api/app/v1/company-assets/{material_id}/versions/{version_id}/review")
    async def submit_company_asset_review(
        material_id: str,
        version_id: str,
        payload: object = Depends(_bounded_json_body(MAX_REVIEW_REQUEST_BYTES, "COMPANY_ASSET_REVIEW_REJECTED")),
        current: tuple[WorkspaceSession, AccessContext] = Depends(csrf_current),
    ) -> dict[str, Any]:
        _, access = current
        try:
            review = library.submit_review(access, material_id, version_id, payload)
            return {
                "schema": "arvectum.workspace.company-asset-review-result/1",
                "review": review,
                "canonical_state_changed": False,
            }
        except CompanyAssetReviewError:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="COMPANY_ASSET_REVIEW_REJECTED") from None
        except CompanyMaterialUnavailable:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="COMPANY_ASSET_VERSION_UNAVAILABLE") from None
        except (CompanyAssetLibraryError, CompanyMaterialsError):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="COMPANY_ASSET_LIBRARY_UNAVAILABLE") from None

    @app.post("/api/app/v1/company-assets/{material_id}/versions/{version_id}/reject")
    async def reject_company_asset_version(
        material_id: str,
        version_id: str,
        payload: object = Depends(_bounded_json_body(MAX_REJECT_REQUEST_BYTES, "COMPANY_ASSET_REJECT_REJECTED")),
        current: tuple[WorkspaceSession, AccessContext] = Depends(csrf_current),
    ) -> dict[str, Any]:
        _, access = current
        try:
            review = library.reject(access, material_id, version_id, payload)
            return {
                "schema": "arvectum.workspace.company-asset-reject-result/1",
                "review": review,
                "canonical_state_changed": False,
            }
        except CompanyAssetReviewError:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="COMPANY_ASSET_REJECT_REJECTED") from None
        except CompanyMaterialUnavailable:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="COMPANY_ASSET_VERSION_UNAVAILABLE") from None
        except (CompanyAssetLibraryError, CompanyMaterialsError):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="COMPANY_ASSET_LIBRARY_UNAVAILABLE") from None

    @app.post("/api/app/v1/company-assets/{material_id}/versions/{version_id}/admit")
    async def admit_company_asset_version(
        material_id: str,
        version_id: str,
        current: tuple[WorkspaceSession, AccessContext] = Depends(csrf_current),
    ) -> dict[str, Any]:
        _, access = current
        try:
            admitted = library.admit(access, material_id, version_id)
            return {
                "schema": "arvectum.workspace.company-asset-admission-result/1",
                "admitted": admitted.to_payload(),
                "canonical_state_changed": True,
                "through_governed_execution": True,
            }
        except CompanyAssetReviewError:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="COMPANY_ASSET_NOT_READY_FOR_ADMISSION") from None
        except CompanyAssetAdmissionUnavailable:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="COMPANY_ASSET_ADMISSION_UNAVAILABLE") from None
        except CompanyMaterialUnavailable:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="COMPANY_ASSET_VERSION_UNAVAILABLE") from None
        except (CompanyAssetLibraryError, CompanyMaterialsError):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="COMPANY_ASSET_ADMISSION_FAILED") from None

    @app.post("/api/app/v1/company-materials/generate")
    async def generate_company_document(
        payload: object = Depends(_bounded_json_body(MAX_GENERATE_REQUEST_BYTES, "COMPANY_GENERATION_INPUT_REJECTED")),
        current: tuple[WorkspaceSession, AccessContext] = Depends(csrf_current),
    ) -> dict[str, Any]:
        _, access = current
        try:
            return library.generate_docx(access, payload)
        except CompanyMaterialsInputError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="COMPANY_GENERATION_INPUT_REJECTED") from None
        except CompanyMaterialUnavailable:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="COMPANY_MATERIAL_VERSION_UNAVAILABLE") from None
        except (CompanyAssetLibraryError, CompanyMaterialsError):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="COMPANY_GENERATION_FAILED") from None

    @app.get("/api/app/v1/company-materials/outputs/{output_id}/download")
    async def download_company_output(
        output_id: str,
        current: tuple[WorkspaceSession, AccessContext] = Depends(authorize_current),
    ) -> FileResponse:
        _, access = current
        try:
            path, manifest = materials.output_path(access, output_id)
        except CompanyMaterialUnavailable:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="COMPANY_OUTPUT_UNAVAILABLE") from None
        except CompanyMaterialsError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="COMPANY_OUTPUT_INTEGRITY_FAILED") from None
        return FileResponse(
            path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=str(manifest["filename"]),
            headers={"Cache-Control": "no-store"},
        )

    app.router.routes.append(spa_route)
    return app


__all__ = ["install_f11_routes"]
