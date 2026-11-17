"""Draft WSF-04C HTTP adapter. Default disabled; no live activation path.

The injected fixture policy is for synthetic tests only. An effective Product
Contract, real operation grants and retention/purge approval are prerequisites
to replacing this test-only provider with a production activation path.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from .access import AccessContext
from .wsf_manual_context import ManualContextError, ManualContextStore


@dataclass(frozen=True)
class FixtureManualPilot:
    store: ManualContextStore
    credential_id: str
    grant_id: str
    starts_at: datetime
    expires_at: datetime

    def authorize(self, access: AccessContext) -> ManualContextStore:
        now = datetime.now(timezone.utc)
        if (self.starts_at.tzinfo is None or self.expires_at.tzinfo is None
                or self.expires_at - self.starts_at > timedelta(days=30)
                or not self.starts_at <= now < self.expires_at
                or access.credential_id != self.credential_id
                or access.grant_id != self.grant_id):
            raise ManualContextError("pilot unavailable")
        self.store._authorize(access)
        return self.store


def install_manual_context_routes(app: FastAPI, authorize_current, csrf_protected, pilot: FixtureManualPilot | None):
    def current_store(access):
        if pilot is None:
            raise HTTPException(status_code=503, detail="MANUAL_CONTEXT_NOT_ACTIVATED")
        try:
            return pilot.authorize(access)
        except ManualContextError:
            raise HTTPException(status_code=403, detail="MANUAL_CONTEXT_UNAVAILABLE") from None

    def perform(fn):
        try:
            return fn()
        except ManualContextError:
            raise HTTPException(status_code=409, detail="MANUAL_CONTEXT_REQUEST_REJECTED") from None
        except (OSError, ValueError):
            raise HTTPException(status_code=503, detail="MANUAL_CONTEXT_UNAVAILABLE") from None

    @app.get("/api/app/v1/manual-context")
    def read(current=Depends(authorize_current)):
        _, access = current
        s = current_store(access)
        return perform(lambda: s.read(access))

    @app.get("/api/app/v1/manual-context/notes/{note_id}/history")
    def history(note_id: str, current=Depends(authorize_current)):
        _, access = current
        s = current_store(access)
        return perform(lambda: s.history(access, note_id))

    @app.post("/api/app/v1/manual-context/submit")
    async def submit(request: Request, current=Depends(csrf_protected)):
        _, access = current
        s = current_store(access)
        try:
            length = int(request.headers.get("content-length", "0"))
            if request.headers.get("transfer-encoding") or not 0 < length <= 24576:
                raise ValueError()
            raw = await request.body()
            if len(raw) != length or len(raw) > 24576:
                raise ValueError()
            data = json.loads(raw)
            if not isinstance(data, dict) or set(data) != {"key", "operation", "payload"}:
                raise ValueError()
        except (ValueError, UnicodeError, RecursionError):
            raise HTTPException(status_code=400, detail="MANUAL_CONTEXT_INVALID_INPUT") from None
        # Re-check the fixture time/access binding immediately before the write.
        s = current_store(access)
        return perform(lambda: s.submit(access, data["key"], data["operation"], data["payload"]))

    @app.get("/api/app/v1/manual-context/export")
    def export(current=Depends(authorize_current)):
        _, access = current
        s = current_store(access)
        raw = perform(lambda: s.export(access))
        return Response(raw, media_type="application/json", headers={
            "Content-Disposition": 'attachment; filename="arvectum-manual-context-private.json"',
            "Cache-Control": "no-store",
        })
