from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .access import AccessContext, AccessResolver, P704AccessResolver, WorkspaceAccessError
from .actionable_work import ActionableWorkError, ActionableWorkProvider, RuntimeActionableWorkProvider
from .attention import AttentionProvider, RuntimeAttentionProvider
from .config import WorkspaceSettings
from .copilot import CopilotError, CopilotProvider, LoopbackChatModel, RuntimeCopilotProvider, normalize_question
from .discovery import DiscoveryError, DiscoveryKind, DiscoveryProvider, ObjectUnavailable, RuntimeDiscoveryProvider
from .dogfooding import DogfoodingError, DogfoodingInputError, DogfoodingStore
from .governed import GovernedExperienceError, GovernedExperienceProvider, RuntimeGovernedExperienceProvider
from .organization import OrganizationCompositionError, OrganizationCompositionProvider, RuntimeOrganizationCompositionProvider
from .products import ProductCompositionError, ProductCompositionProvider, RuntimeProductCompositionProvider
from .release import WorkspaceRelease, load_release
from .security import SessionStore, WorkspaceSession

logger = logging.getLogger("arvectum.workspace.security")
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
RELEASE_HEADER = "X-Arvectum-Workspace-Release"
CSRF_HEADER = "X-Arvectum-CSRF"
MAX_COPILOT_REQUEST_BYTES = 4096
MAX_DOGFOODING_REQUEST_BYTES = 2048


def _is_loopback_client(host: str | None) -> bool:
    if not host:
        return False
    normalized = host.strip("[]").lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _identity_key(identity: object) -> tuple[str, str, str]:
    return (identity.namespace, identity.value, identity.scope)  # type: ignore[attr-defined]


def _security_event(code: str, request: Request, store: SessionStore, detail: str = "") -> None:
    session_id = request.cookies.get(request.app.state.settings.cookie_name)
    logger.warning(
        "workspace_security_event code=%s method=%s path=%s session=%s detail=%s",
        code,
        request.method,
        request.url.path,
        store.correlation_id(session_id),
        detail[:160],
    )


def _navigation() -> list[dict[str, Any]]:
    return [
        {"id": "today", "label": "Today", "href": "/", "availability": "available"},
        {"id": "work", "label": "Work", "href": "/work", "availability": "available"},
        {"id": "information", "label": "Information", "href": "/information", "availability": "available"},
        {"id": "copilot", "label": "Arvectum AI", "href": "/copilot", "availability": "available"},
        {"id": "system", "label": "System", "href": "/system", "availability": "available"},
    ]


def _context_payload(*, settings: WorkspaceSettings, release: WorkspaceRelease, session: WorkspaceSession) -> dict[str, Any]:
    return {
        "schema": "arvectum.workspace.shell-context/1",
        "release": {
            "id": release.release_id,
            "app_api_contract": release.app_api_contract,
            "classification": release.classification,
            "public_api": release.public_api,
        },
        "organization": {"label": settings.organization_label, "scope_resolved_server_side": True},
        "actor": {
            "label": settings.actor_label,
            "attributable": True,
            "scope_resolved_server_side": True,
            "authentication_source": session.authentication_source,
        },
        "session": {
            "csrf_token": session.csrf_token,
            "bounded": True,
            "revocable": True,
            "authority_provided": False,
        },
        "navigation": _navigation(),
        "data_governance": {
            "protected_read_revalidated": True,
            "response_minimized": "shell-context-only",
            "canonical_state_in_browser": False,
        },
    }


def create_app(
    settings: WorkspaceSettings | None = None,
    *,
    access_resolver: AccessResolver | None = None,
    attention_provider: AttentionProvider | None = None,
    actionable_work_provider: ActionableWorkProvider | None = None,
    discovery_provider: DiscoveryProvider | None = None,
    governed_provider: GovernedExperienceProvider | None = None,
    product_provider: ProductCompositionProvider | None = None,
    organization_provider: OrganizationCompositionProvider | None = None,
    copilot_provider: CopilotProvider | None = None,
    dogfooding_store: DogfoodingStore | None = None,
    session_store: SessionStore | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    settings = settings or WorkspaceSettings.from_env()
    release = load_release()
    resolver = access_resolver or P704AccessResolver(settings.runtime_root)
    attention = attention_provider or RuntimeAttentionProvider(settings.runtime_root)
    actionable_work = actionable_work_provider or RuntimeActionableWorkProvider()
    discovery = discovery_provider or RuntimeDiscoveryProvider(settings.runtime_root)
    governed = governed_provider or RuntimeGovernedExperienceProvider(settings.runtime_root)
    products = product_provider or RuntimeProductCompositionProvider(settings.runtime_root)
    organization = organization_provider or RuntimeOrganizationCompositionProvider(products, discovery, attention)
    model = (
        LoopbackChatModel(
            settings.copilot_model_url,
            settings.copilot_model_name,
            settings.copilot_model_timeout_seconds,
        )
        if settings.copilot_model_url
        else None
    )
    copilot = copilot_provider or RuntimeCopilotProvider(discovery, products, model=model)
    dogfooding = dogfooding_store or DogfoodingStore(settings.runtime_root)
    store = session_store or SessionStore(
        idle_seconds=settings.session_idle_seconds,
        absolute_seconds=settings.session_absolute_seconds,
    )
    static_root = static_dir or (Path(__file__).resolve().parent.parent / "workspace_frontend" / "dist")

    app = FastAPI(title="Arvectum OS Productive Workspace BFF", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.release = release
    app.state.access_resolver = resolver
    app.state.attention_provider = attention
    app.state.actionable_work_provider = actionable_work
    app.state.discovery_provider = discovery
    app.state.governed_provider = governed
    app.state.product_provider = products
    app.state.organization_provider = organization
    app.state.copilot_provider = copilot
    app.state.dogfooding_store = dogfooding
    app.state.session_store = store
    app.state.static_root = static_root

    @app.middleware("http")
    async def trust_boundary(request: Request, call_next):  # type: ignore[no-untyped-def]
        host = request.headers.get("host", "").lower()
        if host not in settings.allowed_hosts:
            _security_event("HOST_REJECTED", request, store, host)
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"code": "HOST_REJECTED"})

        if request.method not in SAFE_METHODS:
            origin = request.headers.get("origin")
            if origin != settings.public_origin:
                _security_event("ORIGIN_REJECTED", request, store, origin or "missing")
                return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"code": "ORIGIN_REJECTED"})

        if request.url.path.startswith("/api/app/v1"):
            supplied_release = request.headers.get(RELEASE_HEADER)
            if supplied_release != release.release_id:
                _security_event("RELEASE_MISMATCH", request, store, supplied_release or "missing")
                return JSONResponse(
                    status_code=status.HTTP_409_CONFLICT,
                    content={"code": "RELEASE_MISMATCH", "reload_required": True},
                    headers={RELEASE_HEADER: release.release_id, "Cache-Control": "no-store"},
                )

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers[RELEASE_HEADER] = release.release_id
        elif request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-store"
        return response

    def _authorize_current(request: Request) -> tuple[WorkspaceSession, AccessContext]:
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

    def _csrf_protected(
        request: Request,
        current: tuple[WorkspaceSession, AccessContext] = Depends(_authorize_current),
    ) -> tuple[WorkspaceSession, AccessContext]:
        session, access = current
        if not store.csrf_matches(session, request.headers.get(CSRF_HEADER)):
            _security_event("CSRF_REJECTED", request, store)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF_REJECTED")
        return session, access

    def _require_empty_governed_request(request: Request) -> None:
        if request.headers.get("transfer-encoding"):
            _security_event("GOVERNED_PREFLIGHT_INPUT_REJECTED", request, store, "transfer-encoding")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GOVERNED_PREFLIGHT_INPUT_REJECTED")
        raw_length = request.headers.get("content-length")
        if raw_length is None:
            return
        try:
            length = int(raw_length)
        except ValueError:
            _security_event("GOVERNED_PREFLIGHT_INPUT_REJECTED", request, store, "invalid-content-length")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GOVERNED_PREFLIGHT_INPUT_REJECTED") from None
        if length != 0:
            _security_event("GOVERNED_PREFLIGHT_INPUT_REJECTED", request, store, "non-empty-body")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GOVERNED_PREFLIGHT_INPUT_REJECTED")

    async def _copilot_question(request: Request) -> str:
        if request.headers.get("transfer-encoding"):
            _security_event("COPILOT_INPUT_REJECTED", request, store, "transfer-encoding")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="COPILOT_INPUT_REJECTED")
        raw_length = request.headers.get("content-length")
        if raw_length is not None:
            try:
                length = int(raw_length)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="COPILOT_INPUT_REJECTED") from None
            if length <= 0 or length > MAX_COPILOT_REQUEST_BYTES:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="COPILOT_INPUT_REJECTED")
        raw = await request.body()
        if not raw or len(raw) > MAX_COPILOT_REQUEST_BYTES:
            _security_event("COPILOT_INPUT_REJECTED", request, store, "body-size")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="COPILOT_INPUT_REJECTED")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="COPILOT_INPUT_REJECTED") from None
        if not isinstance(payload, dict) or set(payload) != {"question"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="COPILOT_INPUT_REJECTED")
        try:
            return normalize_question(payload["question"])
        except CopilotError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="COPILOT_QUESTION_INVALID") from None

    async def _dogfooding_payload(request: Request) -> object:
        if request.headers.get("transfer-encoding"):
            _security_event("DOGFOODING_INPUT_REJECTED", request, store, "transfer-encoding")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DOGFOODING_INPUT_REJECTED")
        raw_length = request.headers.get("content-length")
        if raw_length is not None:
            try:
                length = int(raw_length)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DOGFOODING_INPUT_REJECTED") from None
            if length <= 0 or length > MAX_DOGFOODING_REQUEST_BYTES:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DOGFOODING_INPUT_REJECTED")
        raw = await request.body()
        if not raw or len(raw) > MAX_DOGFOODING_REQUEST_BYTES:
            _security_event("DOGFOODING_INPUT_REJECTED", request, store, "body-size")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DOGFOODING_INPUT_REJECTED")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DOGFOODING_INPUT_REJECTED") from None

    @app.post("/api/app/v1/session/bootstrap")
    async def bootstrap_session(request: Request, response: Response) -> dict[str, Any]:
        if not _is_loopback_client(request.client.host if request.client else None):
            _security_event("BOOTSTRAP_NON_LOOPBACK", request, store)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="LOOPBACK_REQUIRED")
        if not settings.allow_loopback_http and not settings.secure_cookie:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="SECURITY_PROFILE_UNAVAILABLE")
        try:
            access = resolver.authorize()
        except WorkspaceAccessError as exc:
            _security_event("BOOTSTRAP_ACCESS_DENIED", request, store, str(exc))
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ACCESS_DENIED") from exc
        session = store.rotate(request.cookies.get(settings.cookie_name), access)
        response.set_cookie(
            key=settings.cookie_name,
            value=session.session_id,
            max_age=settings.session_absolute_seconds,
            httponly=True,
            secure=settings.secure_cookie,
            samesite="strict",
            path="/",
        )
        return _context_payload(settings=settings, release=release, session=session)

    @app.get("/api/app/v1/context")
    async def read_context(current: tuple[WorkspaceSession, AccessContext] = Depends(_authorize_current)) -> dict[str, Any]:
        session, _ = current
        return _context_payload(settings=settings, release=release, session=session)

    @app.get("/api/app/v1/my-work")
    async def read_my_work(current: tuple[WorkspaceSession, AccessContext] = Depends(_authorize_current)) -> dict[str, Any]:
        _, access = current
        return attention.project(access).to_payload()

    @app.get("/api/app/v1/actionable-work")
    async def read_actionable_work(
        current: tuple[WorkspaceSession, AccessContext] = Depends(_authorize_current),
    ) -> dict[str, Any]:
        _, access = current
        try:
            return actionable_work.project(access).to_payload()
        except ActionableWorkError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="ACTIONABLE_WORK_UNAVAILABLE") from None

    @app.get("/api/app/v1/discovery")
    async def read_discovery(
        q: str = "",
        kind: str | None = None,
        current: tuple[WorkspaceSession, AccessContext] = Depends(_authorize_current),
    ) -> dict[str, Any]:
        _, access = current
        try:
            kind_filter = DiscoveryKind(kind) if kind is not None else None
            return discovery.search(access, query=q, kind=kind_filter).to_payload()
        except (ValueError, DiscoveryError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DISCOVERY_QUERY_INVALID") from None

    @app.get("/api/app/v1/objects/{object_id}")
    async def read_object_context(
        object_id: str,
        current: tuple[WorkspaceSession, AccessContext] = Depends(_authorize_current),
    ) -> dict[str, Any]:
        _, access = current
        try:
            return discovery.inspect(access, object_id).to_payload()
        except ObjectUnavailable:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OBJECT_UNAVAILABLE") from None
        except DiscoveryError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="DISCOVERY_UNAVAILABLE") from None

    @app.get("/api/app/v1/products")
    async def read_product_composition(
        current: tuple[WorkspaceSession, AccessContext] = Depends(_authorize_current),
    ) -> dict[str, Any]:
        _, access = current
        try:
            return products.project(access).to_payload()
        except ProductCompositionError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="PRODUCT_COMPOSITION_UNAVAILABLE") from None

    @app.get("/api/app/v1/organization")
    async def read_organization_composition(
        current: tuple[WorkspaceSession, AccessContext] = Depends(_authorize_current),
    ) -> dict[str, Any]:
        _, access = current
        try:
            return organization.project(access).to_payload()
        except OrganizationCompositionError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="ORGANIZATION_COMPOSITION_UNAVAILABLE") from None

    @app.get("/api/app/v1/dogfooding")
    async def read_dogfooding_backlog(
        current: tuple[WorkspaceSession, AccessContext] = Depends(_authorize_current),
    ) -> dict[str, Any]:
        _, access = current
        try:
            return dogfooding.project(access).to_payload()
        except DogfoodingError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="DOGFOODING_UNAVAILABLE") from None

    @app.post("/api/app/v1/dogfooding/observations")
    async def record_dogfooding_observation(
        request: Request,
        current: tuple[WorkspaceSession, AccessContext] = Depends(_csrf_protected),
    ) -> dict[str, Any]:
        payload = await _dogfooding_payload(request)
        _, access = current
        try:
            return dogfooding.record(access, release.release_id, payload)
        except DogfoodingInputError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DOGFOODING_INPUT_INVALID") from None
        except DogfoodingError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="DOGFOODING_UNAVAILABLE") from None

    @app.post("/api/app/v1/dogfooding/observations/{observation_id}/disposition")
    async def disposition_dogfooding_observation(
        observation_id: str,
        request: Request,
        current: tuple[WorkspaceSession, AccessContext] = Depends(_csrf_protected),
    ) -> dict[str, Any]:
        payload = await _dogfooding_payload(request)
        _, access = current
        try:
            return dogfooding.disposition(access, observation_id, payload)
        except DogfoodingInputError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DOGFOODING_DISPOSITION_INVALID") from None
        except DogfoodingError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="DOGFOODING_UNAVAILABLE") from None

    @app.post("/api/app/v1/copilot/ask")
    async def ask_copilot(
        request: Request,
        current: tuple[WorkspaceSession, AccessContext] = Depends(_csrf_protected),
    ) -> dict[str, object]:
        question = await _copilot_question(request)
        _, access = current
        try:
            answer = await asyncio.to_thread(copilot.answer, access, question)
            return answer.to_payload()
        except CopilotError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="COPILOT_UNAVAILABLE") from None

    @app.get("/api/app/v1/governed")
    async def read_governed_experience(
        current: tuple[WorkspaceSession, AccessContext] = Depends(_authorize_current),
    ) -> dict[str, object]:
        _, access = current
        try:
            return governed.inspect(access).to_payload()
        except GovernedExperienceError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GOVERNED_EXPERIENCE_UNAVAILABLE") from None

    @app.post("/api/app/v1/governed/preflight")
    async def run_governed_preflight(
        request: Request,
        current: tuple[WorkspaceSession, AccessContext] = Depends(_csrf_protected),
    ) -> dict[str, object]:
        _require_empty_governed_request(request)
        _, access = current
        try:
            return governed.run_preflight(access).to_payload()
        except GovernedExperienceError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GOVERNED_PREFLIGHT_UNAVAILABLE") from None

    @app.post("/api/app/v1/session/logout")
    async def logout(
        request: Request,
        response: Response,
        current: tuple[WorkspaceSession, AccessContext] = Depends(_csrf_protected),
    ) -> dict[str, str]:
        session, _ = current
        store.revoke(session.session_id)
        response.delete_cookie(
            settings.cookie_name,
            path="/",
            secure=settings.secure_cookie,
            httponly=True,
            samesite="strict",
        )
        return {"status": "logged_out"}

    if static_root.is_dir():
        assets = static_root / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="workspace-assets")

    @app.get("/{path:path}")
    async def spa(path: str) -> Response:
        if path.startswith("api/") or path.startswith("assets/"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        index = static_root / "index.html"
        if not index.is_file():
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"code": "WORKSPACE_ASSETS_UNAVAILABLE"},
            )
        return FileResponse(index, media_type="text/html")

    return app
