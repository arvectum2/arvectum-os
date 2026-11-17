"""WSF-04C HTTP adapter. No live operations without explicit pinned activation."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from .access import AccessContext
from .wsf_manual_context import ManualContextError, ManualContextStore
from .wsf_manual_runtime import RuntimeManualPilot
from .wsf_mission_control import project_timeline, mission_control_baseline


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


def install_manual_context_routes(app: FastAPI, authorize_current, csrf_protected, pilot: FixtureManualPilot | RuntimeManualPilot | None):
    def current_store(access, operation):
        if pilot is None:
            raise HTTPException(status_code=503, detail="MANUAL_CONTEXT_NOT_ACTIVATED")
        try:
            return pilot.authorize_operation(access, operation) if isinstance(pilot, RuntimeManualPilot) else pilot.authorize(access)
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
        s = current_store(access, "read")
        return perform(lambda: pilot.read(access) if isinstance(pilot, RuntimeManualPilot) else s.read(access))

    @app.get("/api/app/v1/manual-context/notes/{note_id}/history")
    def history(note_id: str, current=Depends(authorize_current)):
        _, access = current
        s = current_store(access, "read")
        return perform(lambda: s.history(access, note_id))

    @app.get("/api/app/v1/manual-context/projects/{project_id}/timeline")
    def timeline(project_id: str, current=Depends(authorize_current)):
        _, access = current
        s = current_store(access, "read")
        return perform(lambda: project_timeline(s, access, project_id))

    @app.get("/api/app/v1/manual-context/mission-control")
    def mission_control(current=Depends(authorize_current)):
        _, access = current
        s = current_store(access, "read")
        return perform(lambda: mission_control_baseline(s, access))

    @app.post("/api/app/v1/manual-context/submit")
    async def submit(request: Request, current=Depends(csrf_protected)):
        _, access = current
        # Do not open a store before validating the requested operation.
        if pilot is None:
            raise HTTPException(status_code=503, detail="MANUAL_CONTEXT_NOT_ACTIVATED")
        if isinstance(pilot, FixtureManualPilot):
            current_store(access, "read")
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
        # Re-check the exact time/access binding immediately before the write.
        if not isinstance(data["operation"], str) or data["operation"] not in {"project","capture","revise"}:
            raise HTTPException(status_code=400, detail="MANUAL_CONTEXT_INVALID_INPUT")
        s = current_store(access, data["operation"])
        if isinstance(pilot, RuntimeManualPilot):
            return perform(lambda: pilot.submit(access, data["key"], data["operation"], data["payload"]))
        return perform(lambda: s.submit(access, data["key"], data["operation"], data["payload"]))

    @app.get("/api/app/v1/manual-context/export")
    def export(current=Depends(authorize_current)):
        _, access = current
        s = current_store(access, "export")
        raw = perform(lambda: s.export(access))
        return Response(raw, media_type="application/json", headers={
            "Content-Disposition": 'attachment; filename="arvectum-manual-context-private.json"',
            "Cache-Control": "no-store",
        })
