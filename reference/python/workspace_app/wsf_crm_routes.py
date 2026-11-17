"""Synthetic CRM API adapter; production remains denied by default."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json

from fastapi import Depends, HTTPException, Request, Response
from .wsf_manual_context import ManualContextError
from .wsf_crm import CRMStore


@dataclass(frozen=True)
class FixtureCRMPilot:
    store: CRMStore
    credential_id: str
    grant_id: str
    starts_at: datetime
    expires_at: datetime
    allowed_operations: frozenset[str]

    def authorize(self,access,operation):
        now=datetime.now(timezone.utc)
        if (operation not in self.allowed_operations or self.starts_at.tzinfo is None
                or self.expires_at.tzinfo is None or self.expires_at-self.starts_at>timedelta(days=30)
                or not self.starts_at<=now<self.expires_at
                or access.credential_id!=self.credential_id or access.grant_id!=self.grant_id):
            raise ManualContextError("CRM fixture unavailable")
        self.store._auth(access)
        return self.store


def install_crm_routes(app,authorize_current,csrf_protected,pilot):
    def store(access,operation):
        if pilot is None:
            raise HTTPException(status_code=503,detail="CRM_NOT_ACTIVATED")
        try:return pilot.authorize(access,operation)
        except ManualContextError:raise HTTPException(status_code=403,detail="CRM_UNAVAILABLE") from None

    def perform(fn):
        try:return fn()
        except ManualContextError:raise HTTPException(status_code=409,detail="CRM_REQUEST_REJECTED") from None
        except (OSError,ValueError):raise HTTPException(status_code=503,detail="CRM_UNAVAILABLE") from None

    @app.get("/api/app/v1/crm")
    def read(query:str="",project_id:str|None=None,current=Depends(authorize_current)):
        _,access=current;s=store(access,"read")
        return perform(lambda:s.read(access,query,project_id))

    @app.get("/api/app/v1/crm/records/{record_id}/history")
    def history(record_id:str,current=Depends(authorize_current)):
        _,access=current;s=store(access,"read")
        return perform(lambda:s.history(access,record_id))

    @app.get("/api/app/v1/crm/parties/{party_id}/timeline")
    def timeline(party_id:str,current=Depends(authorize_current)):
        _,access=current;s=store(access,"read")
        return perform(lambda:s.timeline(access,party_id))

    @app.post("/api/app/v1/crm/submit")
    async def submit(request:Request,current=Depends(csrf_protected)):
        _,access=current
        s=store(access,"write")
        try:
            length=int(request.headers.get("content-length","0"))
            if request.headers.get("transfer-encoding") or not 0<length<=24576:raise ValueError()
            raw=await request.body()
            if len(raw)!=length:raise ValueError()
            data=json.loads(raw)
            if not isinstance(data,dict) or set(data)!={"key","entity","data","record_id","expected_revision"}:raise ValueError()
        except (ValueError,UnicodeError,RecursionError):
            raise HTTPException(status_code=400,detail="CRM_INVALID_INPUT") from None
        s=store(access,"write")
        return perform(lambda:s.submit(access,data["key"],data["entity"],data["data"],
                                        record_id=data["record_id"],expected_revision=data["expected_revision"]))

    @app.get("/api/app/v1/crm/export")
    def export(current=Depends(authorize_current)):
        _,access=current;s=store(access,"export")
        raw=perform(lambda:s.export(access))
        return Response(raw,media_type="application/json",headers={
            "Content-Disposition":'attachment; filename="arvectum-crm-private.json"',
            "Cache-Control":"no-store"})
