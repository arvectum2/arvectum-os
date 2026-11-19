"""Real mutual TLS + WebAuthn library + synthetic P7.04 BFF, no live data."""
import base64,hashlib,json,shutil,ssl,struct,threading,unittest
from datetime import datetime,timedelta,timezone
from http.client import HTTPSConnection
import test_remote_access_spike as pki
from test_remote_bff_fixture import HAS_WEB,b64
from tls_asgi_fixture import new_server,bind_fixture
from workspace_app.main import create_app,RELEASE_HEADER,CSRF_HEADER
from workspace_app.release import load_release
from workspace_app.remote_read_fixture import RemoteReadFixture,PREFIX,COOKIE,OP,RESOURCE
import p7_04_persistent_access as p704

@unittest.skipUnless(HAS_WEB and shutil.which("openssl"),"isolated WebAuthn and TLS dependencies required")
class CombinedFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pki.RemoteSpikeTests.setUpClass.__func__(cls)
    def setUp(self):
        from cryptography.hazmat.primitives.asymmetric import ec
        import cbor2
        self.key=ec.generate_private_key(ec.SECP256R1())
        pub=self.key.public_key().public_numbers()
        self.cose=cbor2.dumps({1:2,3:-7,-1:1,-2:pub.x.to_bytes(32,"big"),-3:pub.y.to_bytes(32,"big")})
        self.cid=b"synthetic-device-passkey"
        self.now=datetime.now(timezone.utc)
        self.server=new_server()
        self.addCleanup(self.server.server_close)
        self.origin=f"https://localhost:{self.server.server_port}"
        result=self.register()
        self.f=RemoteReadFixture(result.credential_id,result.credential_public_key,clock=lambda:self.now,origin=self.origin)
        self.addCleanup(self.f.close)
        self.f.sign_count=result.sign_count
        self.f.grant_remote()
        self.pin=hashlib.sha256(ssl.PEM_cert_to_DER_cert((self.d/"device.pem").read_text())).hexdigest()
        app=create_app(remote_read_fixture=self.f)
        bind_fixture(self.server,self.f,app,cert=self.d/"server.pem",key=self.d/"server.key",ca=self.d/"ca.pem",peer_pin=self.pin)
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={"poll_interval":0.05},daemon=True)
        self.thread.start()
        self.addCleanup(self.shutdown)
    def shutdown(self):
        self.server.shutdown()
        self.thread.join(timeout=4)
        self.assertFalse(self.thread.is_alive())
    def register(self,*,uv=True,origin=None,rp="localhost",challenge_override=None):
        import cbor2
        from webauthn import generate_registration_options,verify_registration_response
        from webauthn.helpers.structs import AuthenticatorSelectionCriteria,UserVerificationRequirement
        opts=generate_registration_options(rp_id="localhost",rp_name="Synthetic fixture",
               user_name="synthetic-owner",user_id=b"fixture-user",
               authenticator_selection=AuthenticatorSelectionCriteria(user_verification=UserVerificationRequirement.REQUIRED))
        client=json.dumps({"type":"webauthn.create","challenge":b64(challenge_override or opts.challenge),
                 "origin":origin or self.origin,"crossOrigin":False}).encode()
        auth=hashlib.sha256(rp.encode()).digest()+bytes([0x45 if uv else 0x41])+struct.pack(">I",0)+bytes(16)+struct.pack(">H",len(self.cid))+self.cid+self.cose
        att=cbor2.dumps({"fmt":"none","attStmt":{},"authData":auth})
        credential={"id":b64(self.cid),"rawId":b64(self.cid),"type":"public-key",
                    "response":{"clientDataJSON":b64(client),"attestationObject":b64(att)}}
        out=verify_registration_response(credential=credential,expected_challenge=opts.challenge,
             expected_rp_id="localhost",expected_origin=self.origin,require_user_verification=True)
        self.assertTrue(out.user_verified)
        self.assertEqual(out.credential_id,self.cid)
        self.assertEqual(out.credential_public_key,self.cose)
        return out
    def call(self,method,path,*,device="device",trust=True,hostname="localhost",body=None,cookie=None,header=None):
        ctx=ssl.create_default_context(cafile=str(self.d/"ca.pem")) if trust else ssl.create_default_context()
        if device:ctx.load_cert_chain(str(self.d/(device+".pem")),str(self.d/(device+".key")))
        c=HTTPSConnection(hostname,self.server.server_port,context=ctx,timeout=4)
        headers={RELEASE_HEADER:load_release().release_id,"Host":self.f.host,"Origin":self.origin}
        if cookie:headers["Cookie"]=cookie
        if header:headers.update(header)
        try:
            c.request(method,path,body=json.dumps(body) if body is not None else None,headers=headers)
            r=c.getresponse()
            return r.status,dict(r.getheaders()),json.loads(r.read())
        finally:c.close()
    def assertion(self,opts,*,uv=True,tamper=False):
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        client=json.dumps({"type":"webauthn.get","challenge":opts["challenge"],"origin":self.origin,"crossOrigin":False}).encode()
        auth=hashlib.sha256(b"localhost").digest()+bytes([5 if uv else 1])+struct.pack(">I",self.f.sign_count+1)
        sig=self.key.sign(auth+hashlib.sha256(client).digest(),ec.ECDSA(hashes.SHA256()))
        if tamper:sig=sig[:-1]+bytes([sig[-1]^1])
        return {"id":b64(self.cid),"rawId":b64(self.cid),"type":"public-key",
                "response":{"clientDataJSON":b64(client),"authenticatorData":b64(auth),"signature":b64(sig),"userHandle":None}}
    def challenge(self):
        status,_,opts=self.call("POST",PREFIX+"/challenge")
        self.assertEqual(status,200);self.assertEqual(opts["rpId"],"localhost")
        return opts
    def login(self):
        status,h,out=self.call("POST",PREFIX+"/bootstrap",body=self.assertion(self.challenge()))
        self.assertEqual(status,200,out)
        self.assertTrue(all(t in h["set-cookie"] for t in (COOKIE,"Secure","HttpOnly","SameSite=strict","Path=/")))
        self.assertFalse(out["authority_provided"])
        return h["set-cookie"].split(";",1)[0],out["csrf"]
    def test_real_tls_registration_assertion_and_overview(self):
        opts=self.challenge();a=self.assertion(opts)
        status,h,out=self.call("POST",PREFIX+"/bootstrap",body=a)
        self.assertEqual(status,200,out)
        cookie=h["set-cookie"].split(";",1)[0]
        self.assertEqual(self.call("POST",PREFIX+"/bootstrap",body=a)[0],403)
        status,headers,data=self.call("GET",PREFIX+"/overview",cookie=cookie)
        self.assertEqual(status,200)
        self.assertEqual(data["coverage"],"synthetic-only")
        self.assertEqual(headers["cache-control"],"no-store")
        self.assertFalse(data["canonical_authority"])
    def test_strict_certificate_and_hostname_verification(self):
        for kw in ({"device":None},{"trust":False},{"hostname":"127.0.0.1"}):
            with self.subTest(kw=kw):
                with self.assertRaises((ssl.SSLError,ConnectionError)):
                    self.call("POST",PREFIX+"/challenge",**kw)
    def test_other_valid_device_cannot_obtain_challenge_or_use_session(self):
        forged={"X-Client-Cert":self.pin,"X-Forwarded-For":"127.0.0.1","arvectum.synthetic-device-proof":"spoof"}
        self.assertEqual(self.call("POST",PREFIX+"/challenge",device="other",header=forged)[0],403)
        cookie,_=self.login()
        self.assertEqual(self.call("GET",PREFIX+"/overview",device="other",cookie=cookie,header=forged)[0],403)
        self.assertEqual(self.call("GET",PREFIX+"/overview",cookie=cookie)[0],200)
    def test_registration_rejects_no_uv_wrong_origin_rp_and_challenge(self):
        from webauthn.helpers.exceptions import InvalidRegistrationResponse
        for kw in ({"uv":False},{"origin":"https://other.test"},{"rp":"other.test"},{"challenge_override":bytes(32)}):
            with self.subTest(kw=kw):
                with self.assertRaises(InvalidRegistrationResponse):self.register(**kw)
    def test_tls_does_not_replace_webauthn_or_remote_grant(self):
        for kw in ({"uv":False},{"tamper":True}):
            self.assertEqual(self.call("POST",PREFIX+"/bootstrap",body=self.assertion(self.challenge(),**kw))[0],403)
        cookie,_=self.login()
        p704.revoke_grant(self.f.root,self.f.grant)
        p704.grant_access(self.f.root,self.f.actor,operation=OP,resource=RESOURCE,access_paths=("local",))
        self.assertEqual(self.call("GET",PREFIX+"/overview",cookie=cookie)[0],403)
        self.assertEqual(self.call("POST",PREFIX+"/challenge")[0],403)
    def test_exact_origin_route_csrf_revocation(self):
        self.assertEqual(self.call("POST",PREFIX+"/challenge",header={"Origin":"https://other.test"})[0],403)
        self.assertEqual(self.call("POST",PREFIX+"/challenge",header={"Host":"other.test"})[0],400)
        cookie,csrf=self.login()
        for method,path in (("POST","/api/app/v1/session/bootstrap"),("GET","/api/app/v1/crm"),("GET","/api/app/v1/manual-context"),("GET",PREFIX+"/overview?all=1"),("POST",PREFIX+"/overview")):
            self.assertEqual(self.call(method,path,cookie=cookie)[0],403)
        self.assertEqual(self.call("POST",PREFIX+"/logout",cookie=cookie)[0],403)
        self.assertEqual(self.call("POST",PREFIX+"/logout",cookie=cookie,header={CSRF_HEADER:csrf})[0],200)
        self.assertEqual(self.call("GET",PREFIX+"/overview",cookie=cookie)[0],401)
        cookie,_=self.login()
        self.f.enabled=False
        self.assertEqual(self.call("GET",PREFIX+"/overview",cookie=cookie)[0],403)
    def test_manual_macbook_probe_requires_two_verified_ceremonies(self):
        import cbor2
        import tempfile
        from pathlib import Path
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        from manual_macbook_passkey_probe import Probe
        with tempfile.TemporaryDirectory() as d:
            p=Probe("http://localhost:18099",Path(d)/"result.json")
            self.assertRaises(ValueError,p.handle,"/auth/options",{})
            opts=p.handle("/register/options",{})
            self.assertEqual(opts["authenticatorSelection"]["userVerification"],"required")
            def make_reg(challenge,flags):
                client=json.dumps({"type":"webauthn.create","challenge":challenge,"origin":p.origin,"crossOrigin":False}).encode()
                data=hashlib.sha256(b"localhost").digest()+bytes([flags])+struct.pack(">I",0)+bytes(16)+struct.pack(">H",len(self.cid))+self.cid+self.cose
                return {"id":b64(self.cid),"rawId":b64(self.cid),"type":"public-key","response":{
                    "clientDataJSON":b64(client),"attestationObject":b64(cbor2.dumps({"fmt":"none","attStmt":{},"authData":data}))}}
            with self.assertRaises(Exception):
                p.handle("/register/finish",make_reg(opts["challenge"],0x41))
            self.assertIsNone(p.credential)
            opts=p.handle("/register/options",{})
            self.assertTrue(p.handle("/register/finish",make_reg(opts["challenge"],0x45))["registered"])
            self.assertFalse(p.result_path.exists())
            opts=p.handle("/auth/options",{})
            client=json.dumps({"type":"webauthn.get","challenge":opts["challenge"],"origin":p.origin,"crossOrigin":False}).encode()
            data=hashlib.sha256(b"localhost").digest()+bytes([5])+struct.pack(">I",1)
            sig=self.key.sign(data+hashlib.sha256(client).digest(),ec.ECDSA(hashes.SHA256()))
            assertion={"id":b64(self.cid),"rawId":b64(self.cid),"type":"public-key","response":{
                "clientDataJSON":b64(client),"authenticatorData":b64(data),"signature":b64(sig),"userHandle":None}}
            self.assertTrue(p.handle("/auth/finish",assertion)["authenticated"])
            proof=json.loads(p.result_path.read_text())
            self.assertEqual(proof["status"],"PASS")
            self.assertTrue(proof["registration_user_verified"] and proof["authentication_user_verified"])
            self.assertNotIn("signature",proof)
            self.assertRaises(ValueError,p.handle,"/auth/finish",assertion)
