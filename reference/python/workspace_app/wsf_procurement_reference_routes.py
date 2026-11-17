"""Owner-triggered protected read of the admitted product reference; no storage."""
import http.client
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .wsf_manual_context import ManualContextError


def install_procurement_reference_routes(app, authorize_current, csrf_protected, runtime):
    @app.post("/api/app/v1/procurement-reference")
    async def read(request:Request,current=Depends(csrf_protected)):
        if (request.url.query or request.headers.get("content-length","0")!="0"
            or request.headers.get("transfer-encoding")):
            raise HTTPException(400,"INVALID_REFERENCE_REQUEST")
        if runtime is None:raise HTTPException(503,"REFERENCE_NOT_ADMITTED")
        def authorize():
            _,a=csrf_protected(request,authorize_current(request))
            return a
        try:
            data=await run_in_threadpool(lambda:runtime.read(authorize))
        except ManualContextError:
            raise HTTPException(503,"REFERENCE_UNAVAILABLE") from None
        except (OSError,http.client.HTTPException,ValueError,TypeError,KeyError):
            raise HTTPException(503,"REFERENCE_UNAVAILABLE") from None
        return JSONResponse(data,headers={"Cache-Control":"no-store","Pragma":"no-cache"})
