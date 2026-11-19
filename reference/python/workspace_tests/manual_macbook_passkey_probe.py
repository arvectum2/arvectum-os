"""Manual owner UV check. Loopback-only, ephemeral synthetic localhost RP.

No live Workspace access. No automatic enrollment. The user may create a
test passkey in the browser's authenticator; remove it manually afterwards.
"""
import base64
import json
import secrets
import time
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from datetime import datetime,timezone
from webauthn import (generate_registration_options,verify_registration_response,
                      generate_authentication_options,verify_authentication_response)
from webauthn.helpers import options_to_json
from webauthn.helpers.structs import (AuthenticatorSelectionCriteria,AuthenticatorAttachment,
    ResidentKeyRequirement,UserVerificationRequirement,PublicKeyCredentialDescriptor)

HTML="""<!doctype html><html lang="ru"><meta charset="utf-8"><title>Arvectum — тест Passkey</title>
<h1>Тест Passkey на MacBook</h1><p>Только синтетическая проверка, не вход в Workspace.
Создаваемый тестовый ключ может сохраниться или синхронизироваться в менеджере паролей.
Удалите его после проверки. Никакие данные компании не используются.</p>
<p id="status">Проверка возможностей браузера…</p>
<p>Тестовая учётная запись: <span id="account"></span></p>
<button id="register" disabled>Создать тестовый Passkey</button>
<button id="auth" disabled>Подтвердить вход</button>
<script src="/probe.js"></script></html>"""
JS="""const status=document.getElementById("status"), reg=document.getElementById("register"), auth=document.getElementById("auth");
const decode=s=>Uint8Array.from(atob(s.replace(/-/g,"+").replace(/_/g,"/").padEnd(Math.ceil(s.length/4)*4,"=")),c=>c.charCodeAt(0));
const encode=b=>btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\\+/g,"-").replace(/\\//g,"_").replace(/=+$/,"");
async function call(path,body={}){let r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body),cache:"no-store"});let d=await r.json();if(!r.ok)throw Error(d.code||"Проверка не пройдена");return d;}
(async()=>{try{if(!window.isSecureContext||!window.PublicKeyCredential){status.textContent="WebAuthn недоступен в этом контексте";return;}
let data=await call("/info");document.getElementById("account").textContent=data.account;
if(!await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable()){status.textContent="Платформенный аутентификатор с проверкой пользователя не обнаружен";return;}
status.textContent="Платформенный WebAuthn доступен. Создайте тестовый ключ, только если согласны.";reg.disabled=false;
}catch(e){status.textContent=e.message;}})();
reg.onclick=async()=>{reg.disabled=true;try{
let o=await call("/register/options");o.challenge=decode(o.challenge);o.user.id=decode(o.user.id);
let c=await navigator.credentials.create({publicKey:o});
let d={id:c.id,rawId:encode(c.rawId),type:c.type,response:{clientDataJSON:encode(c.response.clientDataJSON),attestationObject:encode(c.response.attestationObject)}};
await call("/register/finish",d);status.textContent="Регистрация проверена сервером. Теперь подтвердите вход.";auth.disabled=false;
}catch(e){status.textContent="Регистрация не завершена: "+e.name;reg.disabled=false;}};
auth.onclick=async()=>{auth.disabled=true;try{let o=await call("/auth/options");o.challenge=decode(o.challenge);o.allowCredentials.forEach(c=>c.id=decode(c.id));
let c=await navigator.credentials.get({publicKey:o});
let d={id:c.id,rawId:encode(c.rawId),type:c.type,response:{clientDataJSON:encode(c.response.clientDataJSON),authenticatorData:encode(c.response.authenticatorData),signature:encode(c.response.signature),userHandle:c.response.userHandle?encode(c.response.userHandle):null}};
await call("/auth/finish",d);status.textContent="PASS: регистрация и вход с проверкой пользователя подтверждены. Удалите тестовый Passkey после проверки.";
}catch(e){status.textContent="Вход не завершён: "+e.name;auth.disabled=false;}};"""

class Probe:
    def __init__(self,origin,result_path):
        self.origin=origin
        self.account="Arvectum TEST "+secrets.token_hex(5)
        self.user=secrets.token_bytes(32)
        self.pending=None
        self.credential=None
        self.result_path=result_path
        self.passed=False
    def challenge(self,kind,options):
        self.pending=(kind,options.challenge,time.monotonic()+120)
        return json.loads(options_to_json(options))
    def consume(self,kind,payload):
        old=self.pending
        self.pending=None
        if not old or old[0]!=kind or time.monotonic()>=old[2]:raise ValueError()
        # Explicit same-origin ceremony; not a cross-origin or embedded context.
        s=payload["response"]["clientDataJSON"]
        client=json.loads(base64.urlsafe_b64decode(s+"="*(-len(s)%4)))
        if client.get("crossOrigin",False) is not False or "topOrigin" in client:raise ValueError()
        return old[1]
    def handle(self,path,payload):
        if path=="/info":return {"account":self.account}
        if path=="/register/options" and self.credential is None:
            opts=generate_registration_options(rp_id="localhost",rp_name="Arvectum SYNTHETIC TEST",
                user_name=self.account,user_id=self.user,timeout=120000,
                authenticator_selection=AuthenticatorSelectionCriteria(authenticator_attachment=AuthenticatorAttachment.PLATFORM,
                    resident_key=ResidentKeyRequirement.REQUIRED,user_verification=UserVerificationRequirement.REQUIRED))
            return self.challenge("register",opts)
        if path=="/register/finish" and self.credential is None:
            raw=self.consume("register",payload)
            self.credential=verify_registration_response(credential=payload,expected_challenge=raw,expected_rp_id="localhost",
                 expected_origin=self.origin,require_user_verification=True)
            return {"registered":True}
        if path=="/auth/options" and self.credential and not self.passed:
            opts=generate_authentication_options(rp_id="localhost",timeout=120000,
                allow_credentials=[PublicKeyCredentialDescriptor(id=self.credential.credential_id)],
                user_verification=UserVerificationRequirement.REQUIRED)
            return self.challenge("auth",opts)
        if path=="/auth/finish" and self.credential and not self.passed:
            raw=self.consume("auth",payload)
            out=verify_authentication_response(credential=payload,expected_challenge=raw,expected_rp_id="localhost",
                 expected_origin=self.origin,credential_public_key=self.credential.credential_public_key,
                 credential_current_sign_count=self.credential.sign_count,require_user_verification=True)
            if out.credential_id!=self.credential.credential_id:raise ValueError()
            with self.result_path.open("x",encoding="utf-8") as f:
                json.dump({"status":"PASS","at":datetime.now(timezone.utc).isoformat(),
                    "registration_user_verified":self.credential.user_verified,"authentication_user_verified":out.user_verified,
                    "scope":"manual local browser test; no hardware attestation or company data",
                    "account":self.account},f)
            self.passed=True
            return {"authenticated":True}
        raise ValueError()

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)
    def log_message(self,*args):pass
    def send_data(self,status,body,mime):
        self.close_connection=True
        self.send_response(status)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers();self.wfile.write(body)
    def json(self,status,data):
        self.send_data(status,json.dumps(data).encode(),"application/json; charset=utf-8")
    def valid_host(self):
        return self.client_address[0]=="127.0.0.1" and self.headers.get_all("Host")==[self.server.host_value]
    def do_GET(self):
        if not self.valid_host():return self.json(403,{"code":"host"})
        if self.path=="/":return self.send_data(200,HTML.encode(),"text/html; charset=utf-8")
        if self.path=="/probe.js":return self.send_data(200,JS.encode(),"text/javascript; charset=utf-8")
        return self.json(404,{"code":"route"})
    def do_POST(self):
        if not self.valid_host() or self.headers.get_all("Origin")!=[self.server.probe.origin]:
            return self.json(403,{"code":"origin"})
        try:
            entries=self.headers.get_all("Content-Length")
            if self.headers.get("Transfer-Encoding") or not entries or len(entries)!=1:raise ValueError()
            n=int(entries[0])
            if not 0<n<=32768:raise ValueError()
            body=self.rfile.read(n)
            if len(body)!=n:raise ValueError()
            payload=json.loads(body)
            if not isinstance(payload,dict):raise ValueError()
            out=self.server.probe.handle(self.path,payload)
        except Exception:return self.json(400,{"code":"verification rejected"})
        return self.json(200,out)

def main():
    import os,subprocess,tempfile
    os.umask(0o077)
    # Local synthetic evidence only. No live credentials or raw assertions saved.
    root=Path.home()/"Library/Application Support/ArvectumCompany/manual-passkey-probe"
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="manual-",dir=root))
    with HTTPServer(("127.0.0.1",0),Handler) as server:
        server.host_value=f"localhost:{server.server_port}"
        origin="http://"+server.host_value
        server.probe=Probe(origin,run/"result.json")
        server.timeout=1
        print("Synthetic local probe:",origin,flush=True)
        print("Only click the registration button if you agree to create the test passkey.",flush=True)
        print("Temporary result directory:",run,flush=True)
        subprocess.run(["/usr/bin/open","-a","Safari",origin],check=True)
        deadline=time.monotonic()+300
        while time.monotonic()<deadline and not server.probe.passed:
            server.handle_request()
        print("PASS: user-verified registration and authentication" if server.probe.passed else "NOT VERIFIED: no completed ceremony",flush=True)

if __name__=="__main__":main()
