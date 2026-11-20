"""Disposable filesystem and independent authority test double; never production."""
import json,os,subprocess
from pathlib import Path
from contextlib import contextmanager
from dataclasses import replace
from workspace_app.wsf_review_ticket import Ticket,Trust,need,digest,NAMESPACE
from workspace_app.wsf_manual_context import _json

NOW="2026-11-20T11:00:00Z"
EXP="2026-12-17T09:35:36Z"
def key(root):
    p=root/"test-review-key"
    subprocess.run(["/usr/bin/ssh-keygen","-q","-t","ed25519","-N","","-f",str(p)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return p
def sign(root,key,t,namespace=NAMESPACE):
    p=root/"sign-input"
    p.write_bytes(t.raw())
    s=Path(str(p)+".sig")
    if s.exists():s.unlink()
    subprocess.run(["/usr/bin/ssh-keygen","-Y","sign","-f",str(key),"-n",namespace,str(p)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return s.read_bytes()
def trust_for(key,register):
    return Trust(register,"a"*40,"fixture-org","fixture-reviewer","fixture-operator","fixture-credential","fixture-grant","fixture-authority",EXP," ".join(Path(str(key)+".pub").read_text().split()[:2]))
def ticket_for(trust,head,old,new,rid):
    return Ticket(trust.register,trust.contract,trust.organization,trust.reviewer,trust.operator,trust.credential,trust.grant,trust.authority_ref,rid,head[0]+1,head[1],digest(old),digest(new),NOW,EXP)
class Authority:
    """Test seam only. No local on-disk head is trusted for this model."""
    def __init__(self,old):self.value=(0,"0"*64,digest(old));self.live=True;self.interrupt=False
    def check_live(self,trust,t,sig,now):need(self.live,"revoked")
    def head(self,register):return self.value
    def read_head(self,register):return self.head(register)
    def reserve(self,trust,t,sig,now):self.check_live(trust,t,sig,now)
    def compare_and_set(self,register,old,new,trust,t,sig,now):
        trust.verify(t,sig,NOW);self.check_live(trust,t,sig,NOW)
        need(self.value==old,"head conflict");self.value=new
        if self.interrupt:raise OSError("synthetic interruption after head commit")
def atomic(p,b):
    tmp=p.with_name(p.name+".tmp")
    fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"wb") as f:f.write(b);f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)
    fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
class Disk:
    def __init__(self,root,old,company=None):
        self.root=root;self.root.mkdir(mode=0o700)
        self.source=root/"source";self.backup=root/"backup"
        self.source.mkdir(mode=0o700);self.backup.mkdir(mode=0o700)
        self.source=self.source/"register.json";self.backup=self.backup/"register.json"
        self.j=root/"journal";self.archive=root/"archive";self.archive.mkdir(mode=0o700)
        self.company=company;self.interrupt=None;self.locked=False
        for p in (self.source,self.backup):
            if company:company.write_snapshot(p,json.loads(old))
            else:atomic(p,old)
        self.old=old;self.new=None
    @contextmanager
    def exclusive(self):
        need(not self.locked,"test lock");self.locked=True
        try:yield
        finally:self.locked=False
    def check_write(self):need(self.locked,"test maintenance")
    def candidates(self,t):return self.old,self.new
    def read_source(self):return self.source.read_bytes()
    def read_backup(self):return self.backup.read_bytes()
    def journal(self):return self.j.read_bytes() if self.j.exists() else None
    def begin(self,data):need(not self.j.exists(),"journal exists");atomic(self.j,data)
    def finish(self):self.j.unlink()
    def write(self,p,new,old,step):
        need(self.locked and digest(p.read_bytes())==old,"predecessor changed")
        if self.company:self.company.write_snapshot(p,json.loads(new),expected_digest=old)
        else:atomic(p,new)
        if self.interrupt==step:raise OSError("synthetic interruption")
    def append_source(self,new,old):self.write(self.source,new,old,"source")
    def append_backup(self,new,old):self.write(self.backup,new,old,"backup")
    def archive_ticket(self,t,sig):
        # Single atomically committed ticket+signature record.
        p=self.archive/(t.id()+".json")
        need(not p.exists(),"archive exists")
        atomic(p,_json({"ticket":t.raw().hex(),"signature":sig.hex()}))
        if self.interrupt=="archive":raise OSError("synthetic interruption")
    def read_ticket(self,id):
        a=json.loads((self.archive/(id+".json")).read_bytes())
        return Ticket.decode(bytes.fromhex(a["ticket"])),bytes.fromhex(a["signature"])
    def observe(self,t,sig):
        p=self.archive/(t.id()+".json")
        if p.exists():
            tt,ss=self.read_ticket(t.id());need(tt==t and ss==sig,"archive mismatch")
        return digest(self.read_source()),digest(self.read_backup()),p.exists()
