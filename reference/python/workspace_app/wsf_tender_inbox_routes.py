"""Protected tender inbox fixture composition. No browser-submitted source data."""
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
import json
from fastapi import Depends,HTTPException,Request,Response
from starlette.concurrency import run_in_threadpool
from .wsf_manual_context import ManualContextError,_id
from .wsf_manual_backup import PilotBackup
from .wsf_tender_inbox import TenderInbox

@dataclass(frozen=True)
class FixtureTenderInbox:
    inbox: TenderInbox
    fetch_window: object
    backup: PilotBackup
    credential_id: str
    grant_id: str
    starts_at: datetime
    expires_at: datetime
    operations: frozenset
    def authorize(self,a,op):
        t=datetime.now(timezone.utc)
        if (op not in self.operations or not self.starts_at<=t<self.expires_at
            or self.expires_at-self.starts_at>timedelta(days=30)
            or a.credential_id!=self.credential_id or a.grant_id!=self.grant_id):
            raise ManualContextError("tender inbox denied")
        self.inbox.file._authorize(a)
        return self.inbox
    def read(self,a):
        d=self.authorize(a,"read").read(a)
        try:d["backup_status"]="verified" if self.backup.verified_snapshot(a)==self.inbox.export(a) else "stale"
        except (ManualContextError,OSError):d["backup_status"]="unavailable"
        return d
    def mutate(self,authorize,op,data):
        def guard():
            a=authorize();self.authorize(a,op);self.authorize(a,"export");return a
        a=guard();self.backup.copy_latest(a);a=guard()
        if op=="poll":
            f=self.inbox.file
            with f._locked():
                _,_,seen,_=f.replay(f._load())
                old=seen.get(data["key"])
                if old and old["operation"]!="window":raise ManualContextError("request key conflict")
            if not old:
                until=datetime.now(timezone.utc)
                since=until-timedelta(hours=24)
                response=self.fetch_window(since,until)
                a=guard()
                from .wsf_control_projection import stamp
                if (stamp(response["since"]),stamp(response["until"]))!=(since,until):
                    raise ManualContextError("source window mismatch")
                self.inbox.admit_window(a,data["key"],response,datetime.now(timezone.utc).isoformat())
        elif op=="review":
            self.inbox.review(a,data["key"],data["item_id"],data["expected_revision"],data["state"],datetime.now(timezone.utc).isoformat())
        else:raise ManualContextError("unsupported operation")
        try:self.backup.copy_latest(guard());status="verified"
        except (ManualContextError,OSError,HTTPException):status="saved-primary-backup-unavailable"
        return {"status":"saved","backup_status":status}

def install_tender_inbox_routes(app,authorize_current,csrf_protected,pilot):
    base="/api/app/v1/tender-inbox"
    def require(a,op):
        if pilot is None:raise HTTPException(503,"TENDER_INBOX_NOT_ACTIVATED")
        try:return pilot.authorize(a,op)
        except ManualContextError:raise HTTPException(403,"TENDER_INBOX_DENIED") from None
    def perform(fn):
        try:return fn()
        except ManualContextError:raise HTTPException(409,"TENDER_INBOX_REJECTED") from None
        except (OSError,KeyError,TypeError,ValueError):raise HTTPException(503,"TENDER_SOURCE_UNAVAILABLE") from None
    @app.get(base)
    def read(current=Depends(authorize_current)):
        _,a=current;require(a,"read")
        return perform(lambda:pilot.read(a))
    @app.get(base+"/export")
    def export(current=Depends(authorize_current)):
        _,a=current;s=require(a,"export")
        return Response(perform(lambda:s.export(a)),media_type="application/json",
            headers={"Content-Disposition":'attachment; filename="tender-inbox-private.json"',"Cache-Control":"no-store"})
    @app.post(base+"/{op}")
    async def mutate(op:str,request:Request,current=Depends(csrf_protected)):
        if op not in ("poll","review"):raise HTTPException(404,"UNKNOWN_OPERATION")
        _,a=current;require(a,op);require(a,"export")
        expected={"key"} if op=="poll" else {"key","item_id","expected_revision","state"}
        try:
            n=int(request.headers.get("content-length","0"))
            if request.headers.get("transfer-encoding") or not 0<n<=4096:raise ValueError()
            raw=await request.body()
            if len(raw)!=n:raise ValueError()
            d=json.loads(raw)
            if not isinstance(d,dict) or set(d)!=expected:raise ValueError()
            _id(d["key"])
            if op=="review":
                _id(d["item_id"],"TENDERGROUP-")
                if type(d["expected_revision"]) is not int or d["expected_revision"]<1 or d["state"] not in ("reviewed","dismissed"):raise ValueError()
        except (TypeError,ValueError,RecursionError):raise HTTPException(400,"INVALID_INPUT") from None
        def guard():
            _,a=csrf_protected(request,authorize_current(request))
            require(a,op);require(a,"export")
            return a
        return await run_in_threadpool(lambda:perform(lambda:pilot.mutate(guard,op,d)))
