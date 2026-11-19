"""Actual TLS over an ephemeral loopback socket; all principals are synthetic."""
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from http.client import HTTPSConnection
from pathlib import Path
import json,shutil,ssl,subprocess,tempfile,threading,unittest
import p7_04_persistent_access as p704
from remote_access_spike import Spike,make_server,COOKIE,OPERATION,RESOURCE

@unittest.skipUnless(shutil.which("openssl"),"OpenSSL CLI unavailable for ephemeral test PKI")
class RemoteSpikeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pki=tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.pki.cleanup)
        cls.d=Path(cls.pki.name)
        def run(*args):
            subprocess.run(["openssl",*args],cwd=cls.d,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=20)
        (cls.d/"ca.cnf").write_text("[req]\ndistinguished_name=dn\nx509_extensions=ca\n[dn]\n[ca]\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\nsubjectKeyIdentifier=hash\n")
        run("req","-x509","-newkey","rsa:2048","-nodes","-days","1","-subj","/CN=Synthetic fixture CA",
            "-keyout","ca.key","-out","ca.pem","-config","ca.cnf")
        for name,usage in (("server","serverAuth"),("device","clientAuth"),("other","clientAuth")):
            run("req","-newkey","rsa:2048","-nodes","-subj","/CN="+name,"-keyout",name+".key","-out",name+".csr")
            ext=cls.d/(name+".ext")
            ext.write_text("basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\nextendedKeyUsage="+usage+"\n"+("subjectAltName=DNS:localhost\n" if name=="server" else ""))
            run("x509","-req","-in",name+".csr","-CA","ca.pem","-CAkey","ca.key","-CAcreateserial","-days","1",
                "-extfile",ext.name,"-out",name+".pem")
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.now=datetime.now(timezone.utc)
        pin=sha256(ssl.PEM_cert_to_DER_cert((self.d/"device.pem").read_text())).hexdigest()
        self.spike=Spike(Path(self.tmp.name).resolve(),pin,lambda:self.now)
        self.server=make_server(self.spike,self.d/"server.pem",self.d/"server.key",self.d/"ca.pem")
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={"poll_interval":0.05},daemon=True)
        self.thread.start()
        self.addCleanup(self.close)
    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)
    def call(self,method,path,*,device="device",trust=True,body=None,cookie=None,headers=None,hostname="localhost"):
        ctx=ssl.create_default_context(cafile=str(self.d/"ca.pem")) if trust else ssl.create_default_context()
        if device:ctx.load_cert_chain(str(self.d/(device+".pem")),str(self.d/(device+".key")))
        c=HTTPSConnection(hostname,self.server.server_port,context=ctx,timeout=3)
        h={"Host":self.server.host_value,"Origin":self.server.origin}
        if cookie:h["Cookie"]=cookie
        if headers:h.update(headers)
        try:
            c.request(method,path,body=json.dumps(body) if body is not None else None,headers=h)
            r=c.getresponse();raw=r.read()
            return r.status,dict(r.getheaders()),json.loads(raw)
        finally:c.close()
    def login(self,code=None):
        r=self.call("POST","/session/bootstrap",body={"code":code or self.spike.issue_code()})
        self.assertEqual(r[0],200)
        cookie=r[1]["Set-Cookie"]
        self.assertTrue(all(t in cookie for t in (COOKIE+"=","Secure","HttpOnly","SameSite=Strict","Path=/","Max-Age=90")))
        self.assertNotIn("Domain=",cookie)
        self.assertEqual(r[1]["Cache-Control"],"no-store")
        self.assertFalse(r[2]["authority_provided"])
        return cookie.split(";",1)[0],r[2]["csrf"]
    def test_real_tls_rejects_no_client_certificate_wrong_trust_and_hostname(self):
        self.spike.grant_remote()
        for options in ({"device":None},{"trust":False},{"hostname":"127.0.0.1"}):
            with self.subTest(options=options):
                with self.assertRaises((ssl.SSLError,ConnectionError)):
                    self.call("GET","/api/overview",**options)
    def test_unregistered_valid_certificate_and_forged_headers_denied(self):
        self.spike.grant_remote();token=self.spike.issue_code()
        got=self.call("POST","/session/bootstrap",device="other",body={"code":token},
                      headers={"X-Forwarded-For":"127.0.0.1","X-Client-Cert":self.spike.peer_hash})
        self.assertEqual(got[0],403)
        cookie,_=self.login(token)
        self.assertEqual(self.call("GET","/api/overview",cookie=cookie,device="other")[0],403)
        self.assertEqual(self.call("GET","/api/overview",cookie=cookie)[0],200)
    def test_local_grant_cannot_substitute_for_remote_grant(self):
        p704.grant_access(self.spike.root,self.spike.actor,operation=OPERATION,resource=RESOURCE,access_paths=("local",))
        token=self.spike.issue_code()
        self.assertEqual(self.call("POST","/session/bootstrap",body={"code":token})[0],403)
        self.spike.grant_remote()
        self.login(token)
    def test_code_single_use_required_and_expiry(self):
        self.spike.grant_remote()
        self.assertEqual(self.call("POST","/session/bootstrap",body={"code":"wrong"})[0],403)
        token=self.spike.issue_code();self.now+=timedelta(minutes=2)
        self.assertEqual(self.call("POST","/session/bootstrap",body={"code":token})[0],403)
        token=self.spike.issue_code();cookie,_=self.login(token)
        self.assertEqual(self.call("POST","/session/bootstrap",body={"code":token})[0],403)
        self.assertEqual(self.call("GET","/api/overview",cookie=cookie)[0],200)
    def test_exact_host_origin_read_allowlist_csrf_and_logout(self):
        self.spike.grant_remote();token=self.spike.issue_code()
        self.assertEqual(self.call("POST","/session/bootstrap",body={"code":token},headers={"Host":"wrong.test"})[0],400)
        self.assertEqual(self.call("POST","/session/bootstrap",body={"code":token},headers={"Origin":"https://wrong.test"})[0],403)
        self.assertEqual(self.call("GET","/api/overview")[0],401)
        cookie,csrf=self.login(token)
        status,h,payload=self.call("GET","/api/overview",cookie=cookie)
        self.assertEqual(status,200);self.assertEqual(payload["coverage"],"synthetic-only")
        self.assertFalse(payload["canonical_authority"]);self.assertEqual(h["Cache-Control"],"no-store")
        for method,path in (("GET","/api/crm"),("GET","/api/export"),("POST","/api/overview"),("POST","/api/notes"),("POST","/api/copilot"),("GET","/api/overview?extra=1")):
            self.assertEqual(self.call(method,path,cookie=cookie)[0],403)
        self.assertEqual(self.call("POST","/session/logout",cookie=cookie)[0],403)
        self.assertEqual(self.call("POST","/session/logout",cookie=cookie,headers={"X-CSRF":csrf})[0],200)
        self.assertEqual(self.call("GET","/api/overview",cookie=cookie)[0],401)
    def test_expiry_rotation_and_revocation(self):
        self.spike.grant_remote();old,_=self.login();cookie,_=self.login()
        self.assertNotEqual(old,cookie)
        self.assertEqual(self.call("GET","/api/overview",cookie=old)[0],401)
        self.now+=timedelta(seconds=30)
        self.assertEqual(self.call("GET","/api/overview",cookie=cookie)[0],401)
        cookie,_=self.login()
        p704.revoke_grant(self.spike.root,self.spike.grant)
        self.assertEqual(self.call("GET","/api/overview",cookie=cookie)[0],403)
    def test_device_and_credential_revocation(self):
        self.spike.grant_remote();cookie,_=self.login()
        self.spike.device_enabled=False
        self.assertEqual(self.call("GET","/api/overview",cookie=cookie)[0],403)
        self.spike.device_enabled=True
        self.assertEqual(self.call("GET","/api/overview",cookie=cookie)[0],401)
        cookie,_=self.login()
        p704.revoke_credential(self.spike.root,self.spike.credential)
        self.assertEqual(self.call("GET","/api/overview",cookie=cookie)[0],403)
    def test_absolute_session_expiry_even_with_active_reads(self):
        self.spike.grant_remote();cookie,_=self.login()
        for _ in range(4):
            self.now+=timedelta(seconds=20)
            self.assertEqual(self.call("GET","/api/overview",cookie=cookie)[0],200)
        self.now+=timedelta(seconds=10)
        self.assertEqual(self.call("GET","/api/overview",cookie=cookie)[0],401)
    def test_replaced_remote_grant_requires_new_session(self):
        self.spike.grant_remote();cookie,_=self.login()
        original=self.spike.grant
        p704.revoke_grant(self.spike.root,original)
        self.spike.grant_remote()
        self.assertNotEqual(original,self.spike.grant)
        self.assertEqual(self.call("GET","/api/overview",cookie=cookie)[0],401)
        cookie,_=self.login()
        self.assertEqual(self.call("GET","/api/overview",cookie=cookie)[0],200)
    def test_remote_admission_expiry_denies_fresh_session(self):
        self.spike.grant_remote()
        self.now+=timedelta(minutes=10)
        token=self.spike.issue_code()
        self.assertEqual(self.call("POST","/session/bootstrap",body={"code":token})[0],403)
