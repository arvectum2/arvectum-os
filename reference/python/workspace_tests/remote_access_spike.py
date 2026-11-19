"""SYNTHETIC TEST HARNESS ONLY, no production providers or runtime."""
from datetime import timedelta
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, HTTPServer
from http.cookies import SimpleCookie
import hmac,json,secrets,ssl
from pathlib import Path
from workspace_app.access import AccessContext
from workspace_app.security import SessionStore
from arvectum_os_ref.identity import Identity
import p7_04_persistent_access as p704

COOKIE="__Host-arvectum_remote_spike"
OPERATION="workspace.remote.overview.read"
RESOURCE="synthetic-overview"
DATA={"coverage":"synthetic-only","open_work":1,"canonical_authority":False,
      "organizational_authority_provided":False}

class Spike:
    def __init__(self,temp,peer_hash,clock):
        self.root=temp/"remote-spike-synthetic-runtime"
        if self.root.exists():raise ValueError("fixture root must be new")
        self.org=Identity("organization","synthetic-remote-org","platform")
        self.actor=Identity("principal","synthetic-remote-owner",self.org.value)
        p704.initialize_access_store(self.root,self.org)
        p704.register_principal(self.root,self.actor,kind="human")
        issued=p704.issue_credential(self.root,self.actor)
        self.credential=issued["credential_id"]
        self.secret_path=Path(issued["secret_path"])
        self.peer_hash=peer_hash
        self.clock=clock
        self.expires=clock()+timedelta(minutes=10)
        self.store=SessionStore(idle_seconds=30,absolute_seconds=90,clock=clock)
        self.code_hash=None
        self.sid=None
        self.binding=None
        self.grant=None
        self.device_enabled=True
    def issue_code(self):
        # Local fixture action, not callable through HTTPS.
        token=secrets.token_urlsafe(32)
        self.code_hash=sha256(token.encode()).digest()
        self.code_expiry=self.clock()+timedelta(minutes=2)
        return token
    def grant_remote(self):
        self.grant=p704.grant_access(self.root,self.actor,operation=OPERATION,
                                    resource=RESOURCE,access_paths=("remote",))
    def authorize(self,peer):
        if not self.device_enabled or self.clock()>=self.expires or not peer or not hmac.compare_digest(peer,self.peer_hash):
            return None
        d=p704.authorize_from_credential_file(self.root,organization=self.org,
            principal=self.actor,credential_id=self.credential,credential_file=self.secret_path,
            operation=OPERATION,resource=RESOURCE,access_path="remote")
        if not d.allowed or d.principal_kind!="human" or d.grant_id!=self.grant:return None
        return AccessContext(self.org,self.actor,"human",self.credential,self.grant,
                             "synthetic admission + verified TLS device")
    def bootstrap(self,peer,token):
        access=self.authorize(peer)
        if access is None or self.code_hash is None or self.clock()>=self.code_expiry:return None
        if not isinstance(token,str) or len(token)>128 or not hmac.compare_digest(sha256(token.encode()).digest(),self.code_hash):return None
        self.code_hash=None
        s=self.store.rotate(self.sid,access)
        self.sid=s.session_id
        self.binding=(access.credential_id,access.grant_id,peer)
        return s
    def current(self,peer,sid):
        access=self.authorize(peer)
        if access is None:
            if peer==self.peer_hash and sid==self.sid:self.store.revoke(sid)
            return None
        if not sid or sid!=self.sid:return None
        if self.binding!=(access.credential_id,access.grant_id,peer):
            self.store.revoke(sid);return None
        s=self.store.get(sid)
        if s is None:return None
        if s.organization_key!=SessionStore._key(access.organization) or s.actor_key!=SessionStore._key(access.actor):
            self.store.revoke(sid);return None
        return s

class Handler(BaseHTTPRequestHandler):
    server_version="SyntheticRemoteSpike"
    sys_version=""
    def log_message(self,*args):pass
    def reply(self,status,payload,cookie=None):
        raw=json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("X-Frame-Options","DENY")
        if cookie:self.send_header("Set-Cookie",cookie)
        self.end_headers();self.wfile.write(raw)
    def dispatch(self):
        spike=self.server.spike
        cert=self.connection.getpeercert(binary_form=True)
        peer=sha256(cert).hexdigest() if cert else None
        if self.headers.get_all("Host")!=[self.server.host_value]:
            return self.reply(400,{"error":"host"})
        if self.command=="POST" and self.headers.get_all("Origin")!=[self.server.origin]:
            return self.reply(403,{"error":"origin"})
        sid=None
        try:
            c=SimpleCookie(self.headers.get("Cookie",""))
            sid=c[COOKIE].value if COOKIE in c else None
        except Exception:return self.reply(400,{"error":"cookie"})
        if not spike.authorize(peer):
            spike.current(peer,sid)
            return self.reply(403,{"error":"denied"})
        if self.command=="POST" and self.path=="/session/bootstrap":
            try:
                if self.headers.get("Transfer-Encoding"):raise ValueError()
                lengths=self.headers.get_all("Content-Length")
                if lengths is None or len(lengths)!=1:raise ValueError()
                length=int(lengths[0])
                if not 0<length<=1024:raise ValueError()
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict) or set(data)!={"code"}:raise ValueError()
            except (ValueError,TypeError,UnicodeError):
                return self.reply(400,{"error":"request"})
            session=spike.bootstrap(peer,data["code"])
            if not session:return self.reply(403,{"error":"admission"})
            cookie=f"{COOKIE}={session.session_id}; Secure; HttpOnly; SameSite=Strict; Path=/; Max-Age=90"
            return self.reply(200,{"csrf":session.csrf_token,"authority_provided":False},cookie)
        s=spike.current(peer,sid)
        if not s:return self.reply(401,{"error":"session"})
        if self.command=="GET" and self.path=="/api/overview":
            return self.reply(200,DATA)
        if self.command=="POST" and self.path=="/session/logout":
            if not spike.store.csrf_matches(s,self.headers.get("X-CSRF")):
                return self.reply(403,{"error":"csrf"})
            spike.store.revoke(sid)
            return self.reply(200,{"status":"logged_out"},f"{COOKIE}=; Secure; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")
        return self.reply(403,{"error":"route not admitted"})
    do_GET=dispatch
    do_POST=dispatch

def make_server(spike,cert,key,ca):
    server=HTTPServer(("127.0.0.1",0),Handler)
    server.spike=spike
    server.host_value=f"localhost:{server.server_port}"
    server.origin="https://"+server.host_value
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(str(cert),str(key))
    ctx.load_verify_locations(cafile=str(ca))
    ctx.verify_mode=ssl.CERT_REQUIRED
    server.socket=ctx.wrap_socket(server.socket,server_side=True)
    return server
