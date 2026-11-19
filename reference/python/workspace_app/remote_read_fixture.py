"""EXPERIMENT ONLY: explicit synthetic composition, never a live remote provider.

The device proof is an in-process test seam, NOT a network header, TLS
implementation or production authentication. No environment/runtime root input.
"""
import json
import secrets
import threading
import tempfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from arvectum_os_ref.identity import Identity
import p7_04_persistent_access as p704
from .access import AccessContext
from .security import SessionStore

ORIGIN="https://workspace-fixture.test"
HOST="workspace-fixture.test"
COOKIE="__Host-arvectum_remote_fixture"
OP="workspace.remote.overview.read"
RESOURCE="synthetic-overview"
PREFIX="/api/app/v1/remote"
ROUTES={("POST",PREFIX+"/challenge"),("POST",PREFIX+"/bootstrap"),
        ("GET",PREFIX+"/overview"),("POST",PREFIX+"/logout")}
OVERVIEW={"coverage":"synthetic-only","open_work":1,"canonical_authority":False,
          "organizational_authority_provided":False}

class RemoteReadFixture:
    def __init__(self,credential_id:bytes,public_key:bytes,*,clock=None):
        # Optional library is imported ONLY in this explicit experiment.
        from webauthn import verify_authentication_response,generate_authentication_options
        from webauthn.helpers import options_to_json
        from webauthn.helpers.structs import PublicKeyCredentialDescriptor,UserVerificationRequirement
        self.verify=verify_authentication_response
        self.options=generate_authentication_options
        self.options_json=options_to_json
        self.descriptor=PublicKeyCredentialDescriptor
        self.uv=UserVerificationRequirement.REQUIRED
        self.temp=tempfile.TemporaryDirectory(prefix="arvectum-remote-fixture-")
        self.root=Path(self.temp.name).resolve()/"synthetic-runtime"
        self.org=Identity("organization","remote-fixture-org","platform")
        self.actor=Identity("principal","remote-fixture-owner",self.org.value)
        p704.initialize_access_store(self.root,self.org)
        p704.register_principal(self.root,self.actor,kind="human")
        issued=p704.issue_credential(self.root,self.actor)
        self.credential=issued["credential_id"]
        self.secret_path=Path(issued["secret_path"])
        self.grant=None
        self.device_proof=object()
        self.enabled=True
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        self.expires=self.clock()+timedelta(minutes=10)
        self.sessions=SessionStore(idle_seconds=30,absolute_seconds=90,clock=self.clock)
        self.passkey_id=credential_id
        self.public_key=public_key
        self.sign_count=0
        self.challenge=None
        self.sid=None
        self.binding=None
        self.lock=threading.Lock()

    def close(self):self.temp.cleanup()
    def grant_remote(self):
        self.grant=p704.grant_access(self.root,self.actor,operation=OP,resource=RESOURCE,access_paths=("remote",))
    def authorize(self,proof):
        if not self.enabled or proof is not self.device_proof or self.clock()>=self.expires:return None
        d=p704.authorize_from_credential_file(self.root,organization=self.org,principal=self.actor,
            credential_id=self.credential,credential_file=self.secret_path,operation=OP,resource=RESOURCE,access_path="remote")
        if not d.allowed or d.grant_id!=self.grant or d.principal_kind!="human":return None
        return AccessContext(self.org,self.actor,"human",self.credential,self.grant,"synthetic WebAuthn fixture")
    def bind(self,access):
        return (access.organization,access.actor,access.credential_id,access.grant_id,self.device_proof,self.passkey_id)
    def begin(self,access):
        raw=secrets.token_bytes(32)
        self.challenge=(raw,self.clock()+timedelta(seconds=60),self.bind(access))
        opts=self.options(rp_id=HOST,challenge=raw,timeout=60000,
            allow_credentials=[self.descriptor(id=self.passkey_id)],user_verification=self.uv)
        return json.loads(self.options_json(opts))
    def finish(self,access,payload):
        # Invalidate before verification; even an invalid attempt is single-use.
        saved=self.challenge
        self.challenge=None
        if saved is None or self.clock()>=saved[1] or saved[2]!=self.bind(access):return None
        try:
            from webauthn.helpers import parse_authentication_credential_json
            credential=parse_authentication_credential_json(payload)
            if credential.raw_id!=self.passkey_id:return None
            # Do not admit cross-origin/top-origin ceremonies in this slice.
            client=json.loads(credential.response.client_data_json)
            if client.get("crossOrigin",False) is not False or "topOrigin" in client:return None
            v=self.verify(credential=credential,expected_challenge=saved[0],expected_rp_id=HOST,
                expected_origin=ORIGIN,credential_public_key=self.public_key,
                credential_current_sign_count=self.sign_count,require_user_verification=True)
            if v.credential_id!=self.passkey_id or not v.user_verified:return None
        except Exception:return None
        self.sign_count=v.new_sign_count
        s=self.sessions.rotate(self.sid,access)
        self.sid=s.session_id
        self.binding=self.bind(access)
        return s
    def current(self,access,sid):
        if not sid or sid!=self.sid:return None
        if access is None or self.binding!=self.bind(access):
            self.sessions.revoke(sid);return None
        return self.sessions.get(sid)

def create_fixture_app(fixture,release):
    """Explicit test-mode BFF composition. Nothing from local app is mounted."""
    if type(fixture) is not RemoteReadFixture:raise ValueError("exact fixture required")
    app=FastAPI(title="Synthetic remote overview",docs_url=None,redoc_url=None,openapi_url=None)
    def response(status,data):
        return JSONResponse(data,status_code=status,headers={
            "Cache-Control":"no-store","X-Content-Type-Options":"nosniff",
            "Referrer-Policy":"no-referrer","X-Frame-Options":"DENY",
            "Content-Security-Policy":"default-src 'none'; frame-ancestors 'none'",
            "X-Arvectum-Workspace-Release":release.release_id})
    @app.middleware("http")
    async def boundary(request:Request,call_next):
        # Scope proof established only by an explicitly constructed ASGI TEST
        # request; normal HTTP servers cannot populate this Python object.
        if request.scope.get("scheme")!="https" or request.headers.getlist("host")!=[HOST]:
            return response(400,{"code":"TRANSPORT_PROFILE_REJECTED"})
        if request.method=="POST" and request.headers.getlist("origin")!=[ORIGIN]:
            return response(403,{"code":"ORIGIN_REJECTED"})
        if (request.method,request.url.path) not in ROUTES or request.url.query:
            return response(403,{"code":"ROUTE_NOT_ADMITTED"})
        if request.headers.get("X-Arvectum-Workspace-Release")!=release.release_id:
            return response(409,{"code":"RELEASE_MISMATCH","reload_required":True})
        return await call_next(request)
    def proof(request):return request.scope.get("arvectum.synthetic-device-proof")
    def access(request):return fixture.authorize(proof(request))
    def denied():return response(403,{"code":"ACCESS_DENIED"})
    @app.post(PREFIX+"/challenge")
    async def challenge(request:Request):
        with fixture.lock:
            a=access(request)
            if a is None:return denied()
            return response(200,fixture.begin(a))
    @app.post(PREFIX+"/bootstrap")
    async def bootstrap(request:Request):
        if access(request) is None:return denied()
        try:
            if request.headers.get("transfer-encoding"):raise ValueError()
            raw=bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw)>16384:raise ValueError()
            payload=json.loads(raw)
            if not isinstance(payload,dict):raise ValueError()
        except Exception:return response(400,{"code":"INVALID_REQUEST"})
        with fixture.lock:
            a=access(request)
            if a is None:return denied()
            s=fixture.finish(a,payload)
            if s is None:return denied()
            r=response(200,{"csrf":s.csrf_token,"authority_provided":False,"coverage":"synthetic-only"})
            r.set_cookie(COOKIE,s.session_id,max_age=90,secure=True,httponly=True,samesite="strict",path="/")
            return r
    @app.get(PREFIX+"/overview")
    async def overview(request:Request):
        with fixture.lock:
            a=access(request)
            if a is None:
                if proof(request) is fixture.device_proof:fixture.current(None,request.cookies.get(COOKIE))
                return denied()
            if fixture.current(a,request.cookies.get(COOKIE)) is None:return response(401,{"code":"SESSION_REQUIRED"})
            return response(200,OVERVIEW)
    @app.post(PREFIX+"/logout")
    async def logout(request:Request):
        with fixture.lock:
            a=access(request)
            if a is None:return denied()
            s=fixture.current(a,request.cookies.get(COOKIE))
            if s is None:return response(401,{"code":"SESSION_REQUIRED"})
            if not fixture.sessions.csrf_matches(s,request.headers.get("X-Arvectum-CSRF")):
                return response(403,{"code":"CSRF_REJECTED"})
            fixture.sessions.revoke(s.session_id)
            r=response(200,{"status":"logged_out"})
            r.delete_cookie(COOKIE,path="/",secure=True,httponly=True,samesite="strict")
            return r
    return app
