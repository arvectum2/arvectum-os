"""Real WebAuthn signature verification, synthetic authenticator/device ONLY."""
import asyncio,base64,hashlib,importlib.util,json,struct,unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
import p7_04_persistent_access as p704
from workspace_app.main import create_app,RELEASE_HEADER,CSRF_HEADER
from workspace_app.release import load_release
from workspace_app.config import WorkspaceSettings
from workspace_app.remote_read_fixture import RemoteReadFixture,ORIGIN,HOST,PREFIX,COOKIE,OP,RESOURCE

HAS_WEB=all(importlib.util.find_spec(x) for x in ("webauthn","cryptography","cbor2"))
def b64(b):return base64.urlsafe_b64encode(b).decode().rstrip("=")
def unb64(s):return base64.urlsafe_b64decode(s+"="*(-len(s)%4))

@unittest.skipUnless(HAS_WEB,"isolated experimental WebAuthn dependencies absent")
class RemoteBffFixtureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from cryptography.hazmat.primitives.asymmetric import ec
        import cbor2
        self.key=ec.generate_private_key(ec.SECP256R1())
        pub=self.key.public_key().public_numbers()
        cose=cbor2.dumps({1:2,3:-7,-1:1,-2:pub.x.to_bytes(32,"big"),-3:pub.y.to_bytes(32,"big")})
        self.id=b"synthetic-credential-id"
        self.now=datetime.now(timezone.utc)
        self.f=RemoteReadFixture(self.id,cose,clock=lambda:self.now)
        self.addCleanup(self.f.close)
        self.app=create_app(remote_read_fixture=self.f)
        self.f.grant_remote()
        self.release=load_release().release_id
    async def call(self,method,path,*,body=None,cookie=None,header=None,proof=True,scheme="https"):
        headers={RELEASE_HEADER:self.release,"Host":HOST,"Origin":ORIGIN}
        if cookie:headers["Cookie"]=cookie
        if header:headers.update(header)
        raw=json.dumps(body).encode() if body is not None else b""
        headers["Content-Length"]=str(len(raw))
        scope={"type":"http","asgi":{"version":"3.0","spec_version":"2.4"},"http_version":"1.1",
          "method":method,"scheme":scheme,"path":path,"root_path":"","raw_path":path.encode(),
          "query_string":b"","headers":[(k.lower().encode(),v.encode()) for k,v in headers.items()],
          "client":("192.0.2.1",50000),"server":(HOST,443)}
        if proof:scope["arvectum.synthetic-device-proof"]=self.f.device_proof
        sent=[];delivered=False
        async def receive():
            nonlocal delivered
            if not delivered:
                delivered=True
                return {"type":"http.request","body":raw,"more_body":False}
            await asyncio.Event().wait()
        async def send(msg):sent.append(msg)
        await asyncio.wait_for(self.app(scope,receive,send),timeout=5)
        start=next(x for x in sent if x["type"]=="http.response.start")
        h={k.decode():v.decode() for k,v in start["headers"]}
        data=json.loads(b"".join(x.get("body",b"") for x in sent if x["type"]=="http.response.body"))
        return start["status"],h,data
    def assertion(self,opts,*,uv=True,origin=ORIGIN,rp=HOST,count=None,tamper=False,cross=False,cred=None):
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        client=json.dumps({"type":"webauthn.get","challenge":opts["challenge"],"origin":origin,"crossOrigin":cross},separators=(",",":")).encode()
        auth=hashlib.sha256(rp.encode()).digest()+bytes([5 if uv else 1])+struct.pack(">I",self.f.sign_count+1 if count is None else count)
        sig=self.key.sign(auth+hashlib.sha256(client).digest(),ec.ECDSA(hashes.SHA256()))
        if tamper:sig=sig[:-1]+bytes([sig[-1]^1])
        cid=b64(cred or self.id)
        return {"id":cid,"rawId":cid,"type":"public-key","response":{"clientDataJSON":b64(client),
                "authenticatorData":b64(auth),"signature":b64(sig),"userHandle":None}}
    async def challenge(self):
        s,_,opts=await self.call("POST",PREFIX+"/challenge")
        self.assertEqual(s,200);self.assertEqual(opts["userVerification"],"required")
        self.assertEqual(opts["rpId"],HOST)
        return opts
    async def login(self):
        opts=await self.challenge()
        s,h,b=await self.call("POST",PREFIX+"/bootstrap",body=self.assertion(opts))
        self.assertEqual(s,200,b)
        cookie=h["set-cookie"]
        self.assertTrue(all(x in cookie for x in (COOKIE,"Secure","HttpOnly","SameSite=strict","Path=/")))
        self.assertNotIn("Domain=",cookie)
        self.assertFalse(b["authority_provided"])
        return cookie.split(";",1)[0],b["csrf"]
    async def test_signature_and_uv_real_verifier_and_replay(self):
        opts=await self.challenge();a=self.assertion(opts)
        s,h,b=await self.call("POST",PREFIX+"/bootstrap",body=a)
        self.assertEqual(s,200,b)
        cookie=h["set-cookie"].split(";",1)[0]
        self.assertEqual((await self.call("POST",PREFIX+"/bootstrap",body=a))[0],403)
        self.assertEqual((await self.call("GET",PREFIX+"/overview",cookie=cookie))[0],200)
        self.assertEqual(self.f.sign_count,1)
    async def test_invalid_assertions_do_not_admit_or_reuse_challenge(self):
        for kw in ({"uv":False},{"origin":"https://other.test"},{"rp":"other.test"},{"tamper":True},{"cross":True},{"cred":b"wrong"}):
            opts=await self.challenge()
            self.assertEqual((await self.call("POST",PREFIX+"/bootstrap",body=self.assertion(opts,**kw)))[0],403,kw)
            self.assertEqual((await self.call("POST",PREFIX+"/bootstrap",body=self.assertion(opts)))[0],403)
        self.assertEqual(self.f.sign_count,0)
        self.assertEqual((await self.call("GET",PREFIX+"/overview"))[0],401)
    async def test_device_proof_is_not_header_or_loopback(self):
        self.assertEqual((await self.call("POST",PREFIX+"/challenge",proof=False,header={
            "X-Forwarded-For":"127.0.0.1","X-Client-Cert":"spoof","arvectum.synthetic-device-proof":"spoof"}))[0],403)
        self.assertEqual((await self.call("POST",PREFIX+"/challenge",scheme="http"))[0],400)
        self.assertEqual((await self.call("POST",PREFIX+"/challenge",header={"Host":"evil.test"}))[0],400)
        self.assertEqual((await self.call("POST",PREFIX+"/challenge",header={"Origin":"https://evil.test"}))[0],403)
        self.assertEqual((await self.call("POST",PREFIX+"/challenge",header={RELEASE_HEADER:"wrong"}))[0],409)
        cookie,_=await self.login()
        self.assertEqual((await self.call("GET",PREFIX+"/overview",cookie=cookie,proof=False))[0],403)
        self.assertEqual((await self.call("GET",PREFIX+"/overview",cookie=cookie))[0],200)
    async def test_remote_grant_absence_and_replacement(self):
        p704.revoke_grant(self.f.root,self.f.grant)
        p704.grant_access(self.f.root,self.f.actor,operation=OP,resource=RESOURCE,access_paths=("local",))
        self.assertEqual((await self.call("POST",PREFIX+"/challenge"))[0],403)
        self.f.grant_remote();cookie,_=await self.login()
        p704.revoke_grant(self.f.root,self.f.grant)
        self.f.grant_remote()
        self.assertEqual((await self.call("GET",PREFIX+"/overview",cookie=cookie))[0],401)
    async def test_allowlist_and_logout(self):
        cookie,csrf=await self.login()
        status,h,out=await self.call("GET",PREFIX+"/overview",cookie=cookie)
        self.assertEqual(status,200);self.assertEqual(out["coverage"],"synthetic-only")
        self.assertFalse(out["canonical_authority"]);self.assertEqual(h["cache-control"],"no-store")
        for method,path in (("POST","/api/app/v1/session/bootstrap"),("GET","/api/app/v1/context"),
                            ("GET","/api/app/v1/crm"),("GET","/api/app/v1/manual-context"),
                            ("POST",PREFIX+"/overview"),("GET","/"),("GET","/assets/file")):
            self.assertEqual((await self.call(method,path,cookie=cookie))[0],403,(method,path))
        self.assertEqual((await self.call("POST",PREFIX+"/logout",cookie=cookie))[0],403)
        self.assertEqual((await self.call("POST",PREFIX+"/logout",cookie=cookie,header={CSRF_HEADER:csrf}))[0],200)
        self.assertEqual((await self.call("GET",PREFIX+"/overview",cookie=cookie))[0],401)
    async def test_counter_expiry_and_credential_revocation(self):
        await self.login()
        opts=await self.challenge()
        self.assertEqual((await self.call("POST",PREFIX+"/bootstrap",body=self.assertion(opts,count=1)))[0],403)
        opts=await self.challenge();self.now+=timedelta(seconds=60)
        self.assertEqual((await self.call("POST",PREFIX+"/bootstrap",body=self.assertion(opts)))[0],403)
        cookie,_=await self.login()
        p704.revoke_credential(self.f.root,self.f.credential)
        self.assertEqual((await self.call("GET",PREFIX+"/overview",cookie=cookie))[0],403)
    async def test_fixture_cannot_mount_real_providers(self):
        with self.assertRaises(ValueError):
            create_app(remote_read_fixture=self.f,access_resolver=object())
        with self.assertRaises(ValueError):create_app(remote_read_fixture=object())
        # Default composition must not use fixture factory or experimental library.
        with patch("workspace_app.remote_read_fixture.create_fixture_app",side_effect=AssertionError):
            with patch.dict("os.environ",{"ARVECTUM_P7_02_ROOT":str(self.f.root),"ARVECTUM_WORKSPACE_ORIGIN":"http://127.0.0.1:8769","ARVECTUM_WORKSPACE_BIND_HOST":"127.0.0.1","ARVECTUM_WORKSPACE_BIND_PORT":"8769","ARVECTUM_WORKSPACE_ALLOW_LOOPBACK_HTTP":"true"},clear=True):
                local=create_app(WorkspaceSettings.from_env())
            self.assertFalse(any(getattr(r,"path","").startswith(PREFIX) for r in local.routes))
