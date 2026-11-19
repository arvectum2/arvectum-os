"""Ephemeral TLS-to-ASGI adapter for synthetic test fixtures only.

Not a production HTTP server, proxy, deployment entrypoint or TLS profile.
The actual verified TLS peer is the only source of the fixture device proof.
"""
import asyncio
import hmac
from hashlib import sha256
from http.server import BaseHTTPRequestHandler,HTTPServer
import ssl
from urllib.parse import urlsplit
from workspace_app.remote_read_fixture import RemoteReadFixture

class Handler(BaseHTTPRequestHandler):
    server_version="SyntheticTlsAsgi"
    sys_version=""
    def log_message(self,*args):pass
    def setup(self):
        super().setup()
        self.connection.settimeout(3)
    def dispatch(self):
        self.close_connection=True
        # No proxy semantics, duplicate length, chunked bodies or arbitrary URI.
        lengths=self.headers.get_all("Content-Length") or ["0"]
        target=urlsplit(self.path)
        if (self.headers.get("Transfer-Encoding") or len(lengths)!=1
            or not lengths[0].isdigit() or int(lengths[0])>16384
            or target.scheme or target.netloc or target.fragment):
            self.send_error(400);return
        body=self.rfile.read(int(lengths[0]))
        if len(body)!=int(lengths[0]):
            self.send_error(400);return
        cert=self.connection.getpeercert(binary_form=True)
        if not cert:
            self.send_error(403);return
        # Never infer proof from IP, Host, X-Forwarded-* or any HTTP header.
        scope={"type":"http","asgi":{"version":"3.0","spec_version":"2.4"},
            "http_version":"1.1","method":self.command,"scheme":"https",
            "root_path":"","path":target.path,"raw_path":target.path.encode(),
            "query_string":target.query.encode(),
            "headers":[(k.lower().encode("ascii"),v.encode("latin1")) for k,v in self.headers.raw_items()],
            "client":self.client_address,"server":self.server.server_address}
        if hmac.compare_digest(sha256(cert).hexdigest(),self.server.peer_pin):
            scope["arvectum.synthetic-device-proof"]=self.server.fixture.device_proof
        async def run():
            sent=[];first=True
            async def receive():
                nonlocal first
                if first:
                    first=False
                    return {"type":"http.request","body":body,"more_body":False}
                await asyncio.Event().wait()
            async def send(message):sent.append(message)
            await asyncio.wait_for(self.server.app(scope,receive,send),timeout=3)
            return sent
        messages=asyncio.run(run())
        start=next(m for m in messages if m["type"]=="http.response.start")
        raw=b"".join(m.get("body",b"") for m in messages if m["type"]=="http.response.body")
        self.send_response(start["status"])
        for k,v in start["headers"]:
            if k.lower() not in (b"content-length",b"connection",b"transfer-encoding"):
                self.send_header(k.decode("ascii"),v.decode("latin1"))
        self.send_header("Content-Length",str(len(raw)))
        self.send_header("Connection","close")
        self.end_headers();self.wfile.write(raw)
    do_GET=dispatch
    do_POST=dispatch

def new_server():
    return HTTPServer(("127.0.0.1",0),Handler)

def bind_fixture(server,fixture,app,*,cert,key,ca,peer_pin):
    if type(fixture) is not RemoteReadFixture or fixture.origin!=f"https://localhost:{server.server_port}" or server.server_address[0]!="127.0.0.1":
        raise ValueError("exact synthetic loopback profile required")
    server.fixture=fixture
    server.app=app
    server.peer_pin=peer_pin
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(str(cert),str(key))
    ctx.load_verify_locations(cafile=str(ca))
    ctx.verify_mode=ssl.CERT_REQUIRED
    server.socket=ctx.wrap_socket(server.socket,server_side=True)
