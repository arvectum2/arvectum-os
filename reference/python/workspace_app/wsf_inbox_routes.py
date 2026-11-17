"""Protected owner-triggered inbox fixture API; absent production provider denies."""
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
import json
from fastapi import Depends,HTTPException,Request,Response
from starlette.concurrency import run_in_threadpool
from .wsf_manual_context import ManualContextError,_id
from .wsf_roadmap_inbox import collect_once,inbox_review_brief,RoadmapInbox
from .company_portfolio import CompanyPortfolioError
from .wsf_manual_backup import PilotBackup

INBOX_PARTS=("Arvectum","backups","arvectum-os","roadmap-inbox")


@dataclass(frozen=True)
class FixtureInboxPilot:
    inbox: RoadmapInbox
    provider: object
    backup: PilotBackup
    credential_id: str
    grant_id: str
    starts_at: datetime
    expires_at: datetime
    operations: frozenset

    def authorize(self,access,operation):
        now=datetime.now(timezone.utc)
        if (operation not in self.operations or not self.starts_at<=now<self.expires_at
                or self.expires_at-self.starts_at>timedelta(days=30)
                or access.credential_id!=self.credential_id or access.grant_id!=self.grant_id):
            raise ManualContextError("inbox access unavailable")
        self.inbox.file._authorize(access)
        return self.inbox

    def read(self,access):
        d=self.authorize(access,"read").read(access)
        try:
            raw=self.backup.verified_snapshot(access)
            d["backup_status"]="verified" if raw==self.inbox.export(access) else "stale"
        except (OSError,ManualContextError):
            d["backup_status"]="unavailable"
        return d

    def mutate(self,authorize,operation,data):
        a=authorize();self.authorize(a,operation)
        self.backup.copy_latest(a)
        a=authorize();self.authorize(a,operation)
        if operation=="poll":
            # Replayed poll keys never refetch or advance the checkpoint.
            with self.inbox.file._locked():
                _,_,seen=self.inbox.file.replay(self.inbox.file._load())
                old=seen.get(data["key"])
                if old and old["operation"]!="scan":raise ManualContextError("request replay conflict")
            if not old:
                def guard():
                    current=authorize();self.authorize(current,"poll");return current
                collect_once(self.inbox,provider=self.provider,authorize=guard,
                     expected_scope=self.inbox.file.scope,request_key=data["key"])
        else:
            self.inbox.review(a,data["key"],data["item_id"],data["expected_revision"],
                              data["state"],datetime.now(timezone.utc).isoformat())
        try:
            self.backup.copy_latest(a)
            status="verified"
        except (OSError,ManualContextError):
            status="saved-primary-backup-unavailable"
        return {"status":"saved","backup_status":status}


def install_inbox_routes(app,authorize_current,csrf_protected,pilot):
    base="/api/app/v1/roadmap-inbox"
    def require(access,op):
        if pilot is None:raise HTTPException(503,"INBOX_NOT_ACTIVATED")
        try:return pilot.authorize(access,op)
        except ManualContextError:raise HTTPException(403,"INBOX_ACCESS_DENIED") from None
    def perform(fn):
        try:return fn()
        except ManualContextError:raise HTTPException(409,"INBOX_REQUEST_REJECTED") from None
        except (CompanyPortfolioError,OSError):raise HTTPException(503,"INBOX_UNAVAILABLE") from None

    @app.get(base)
    def read(current=Depends(authorize_current)):
        _,a=current;require(a,"read")
        return perform(lambda:pilot.read(a))

    @app.get(base+"/brief")
    def brief(current=Depends(authorize_current)):
        _,a=current;s=require(a,"read")
        return perform(lambda:inbox_review_brief(s,a))

    @app.get(base+"/export")
    def export(current=Depends(authorize_current)):
        _,a=current;s=require(a,"export")
        return Response(perform(lambda:s.export(a)),media_type="application/json",
             headers={"Content-Disposition":'attachment; filename="roadmap-inbox-private.json"',"Cache-Control":"no-store"})

    @app.post(base+"/{operation}")
    async def mutate(operation:str,request:Request,current=Depends(csrf_protected)):
        if operation not in {"poll","review"}:raise HTTPException(404,"INBOX_UNKNOWN_OPERATION")
        _,a=current;require(a,operation)
        expected={"key"} if operation=="poll" else {"key","item_id","expected_revision","state"}
        try:
            length=int(request.headers.get("content-length","0"))
            if request.headers.get("transfer-encoding") or not 0<length<=4096:raise ValueError()
            raw=await request.body()
            if len(raw)!=length:raise ValueError()
            d=json.loads(raw)
            if not isinstance(d,dict) or set(d)!=expected:raise ValueError()
            _id(d["key"])
            if operation=="review":
                _id(d["item_id"],"INBOX-")
                if type(d["expected_revision"]) is not int or d["expected_revision"]<1 or d["state"] not in ("reviewed","dismissed"):raise ValueError()
        except (ValueError,TypeError,RecursionError):raise HTTPException(400,"INBOX_INVALID_INPUT") from None
        def revalidate():
            _,a=csrf_protected(request,authorize_current(request))
            require(a,operation)
            return a
        return await run_in_threadpool(lambda:perform(lambda:pilot.mutate(revalidate,operation,d)))
