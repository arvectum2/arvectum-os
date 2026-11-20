"""Experimental independent signed review ticket, no production key/entrypoint."""
from dataclasses import dataclass,asdict
from datetime import timedelta
import hashlib,json,re,subprocess,tempfile
from pathlib import Path
from .wsf_manual_context import ManualContextError,_json
from .wsf_control_projection import stamp

NAMESPACE="arvectum-control-review-v1"
def need(ok,message):
    if not ok:raise ManualContextError(message)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def hex64(v):return isinstance(v,str) and re.fullmatch(r"[0-9a-f]{64}",v) is not None

@dataclass(frozen=True)
class Ticket:
    register:str
    contract:str
    organization:str
    reviewer:str
    operator:str
    credential:str
    grant:str
    authority_ref:str
    record_id:str
    sequence:int
    previous_ticket:str
    predecessor:str
    successor:str
    issued_at:str
    expires_at:str
    def __post_init__(self):
        need(self.register in ("decision","risk"),"register outside scope")
        need(all(hex64(x) for x in (self.previous_ticket,self.predecessor,self.successor)) and self.predecessor!=self.successor,"invalid digest")
        need(isinstance(self.contract,str) and re.fullmatch(r"[a-f0-9]{40}",self.contract),"invalid contract")
        need(type(self.sequence) is int and 1<=self.sequence<=1000,"sequence bound")
        for v in (self.organization,self.reviewer,self.operator,self.credential,self.grant,self.authority_ref,self.record_id):
            need(isinstance(v,str) and 0<len(v)<=512 and v.strip()==v and not any(ord(c)<32 for c in v),"invalid identity")
        need(stamp(self.issued_at)<stamp(self.expires_at)<=stamp(self.issued_at)+timedelta(days=30),"ticket lifetime")
    def raw(self):return _json({"schema":"arvectum.control-review-ticket/1",**asdict(self)})
    def id(self):return digest(self.raw())
    @classmethod
    def decode(cls,raw):
        need(type(raw) is bytes and len(raw)<=8192,"ticket bound")
        try:
            v=json.loads(raw);need(v.pop("schema")=="arvectum.control-review-ticket/1","ticket schema")
            t=cls(**v);need(t.raw()==raw,"noncanonical ticket");return t
        except (ValueError,TypeError,KeyError,AttributeError,RecursionError) as e:
            raise ManualContextError("malformed ticket") from e

@dataclass(frozen=True)
class Trust:
    """Supplied from independently protected approved configuration, NOT source."""
    register:str
    contract:str
    organization:str
    reviewer:str
    operator:str
    credential:str
    grant:str
    authority_ref:str
    expires_at:str
    public_key:str
    def bind(self,t,now):
        need(all(getattr(self,k)==getattr(t,k) for k in ("register","contract","organization","reviewer","operator","credential","grant","authority_ref")),"ticket authority/scope mismatch")
        need(stamp(t.issued_at)<=stamp(now)<stamp(t.expires_at)<=stamp(self.expires_at),"ticket expired or future")
        need(self.reviewer!=self.operator,"reviewer and operator must be independently controlled")
    def verify(self,t,signature,now):
        self.bind(t,now)
        need(isinstance(self.public_key,str) and re.fullmatch(r"ssh-ed25519 [A-Za-z0-9+/=]{68}",self.public_key),"invalid pinned key")
        need(type(signature) is bytes and 0<len(signature)<=4096,"signature bound")
        with tempfile.TemporaryDirectory(prefix="review-verify-") as d:
            p=Path(d);(p/"allowed").write_text("reviewer "+self.public_key+"\n")
            (p/"signature").write_bytes(signature)
            try:
                out=subprocess.run(["/usr/bin/ssh-keygen","-Y","verify","-f",str(p/"allowed"),
                    "-I","reviewer","-n",NAMESPACE,"-s",str(p/"signature")],input=t.raw(),
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5,check=False)
            except (OSError,subprocess.TimeoutExpired) as e:raise ManualContextError("signature verifier unavailable") from e
            need(out.returncode==0,"independent review signature denied")
