"""Private temporary-directory cutover adapter only; no live operator."""
import os,tempfile
from contextlib import contextmanager
from workspace_app.wsf_company_control_reference import read_snapshot,sha,BINDINGS
from workspace_app.wsf_company_control_successor import first_successor
from workspace_app.wsf_control_projection import project_controls
from workspace_app.wsf_company_control_cutover import Plan,advance
from workspace_app.wsf_manual_context import ManualContextError,_json,_identity
from workspace_app.wsf_manual_policy import _private_file
from wsf_manual_operator import write_new

def fsync_dir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

def atomic_replace(path,raw):
    fd,tmp=tempfile.mkstemp(prefix=".fixture-",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path);fsync_dir(path.parent)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

class CutoverFixture:
    def __init__(self,base,old,new,decision,contract):
        self.base=base;self.runtime=base.runtime
        self.old=old;self.new=new
        self.source=self.runtime.source
        directory=self.source.parent.parent/"backup"
        directory.mkdir(mode=0o700)
        self.backup=directory/"latest.private.json"
        write_new(self.backup,old)
        cfg=base.root/"config"
        self.policy=cfg/"company-control-successor-policy.fixture.json"
        self.receipt=cfg/"company-control-successor-activation.fixture.json"
        self.journal=cfg/"company-control-cutover.fixture.json"
        self.legacy_receipt=cfg/"company-control-activation.json"
        p,pin,review=self.runtime.gate(base.resolve())
        self.policy_bytes=_json({"schema":"ac401-successor-fixture/1","scope":p["scope"],
           "credential_id":p["credential_id"],"grant_id":p["grant_id"],
           "starts_at":p["starts_at"],"expires_at":p["expires_at"],"records":BINDINGS,
           "predecessor":sha(old),"source_sha256":sha(new),
           "legacy_policy_sha256":pin,"decision":decision,"contract":contract})
        self.receipt_bytes=_json({"schema":"ac401-successor-receipt-fixture/1",
           "policy_sha256":sha(self.policy_bytes),"decision":decision,"contract":contract})
        self.plan=Plan(sha(old),sha(new),sha(self.policy_bytes),sha(self.receipt_bytes),pin,
                       sha(_private_file(self.legacy_receipt)),decision,contract)
        self.approved_plan=self.plan # synthetic independent approval seam
        self.quiescent=True;self.locked=False;self.failure=None
        self.writes=[];self.company_write=None

    @contextmanager
    def exclusive(self):
        if self.locked or not self.quiescent:raise ManualContextError("not quiescent")
        self.locked=True
        try:yield
        finally:self.locked=False

    def preflight(self,plan):
        if not self.locked or not self.quiescent or plan!=self.approved_plan:
            raise ManualContextError("exact fixture approval required")
        self.check(plan)

    def check(self,plan):
        a=self.base.resolve()
        p,pin,review=self.runtime.gate(a)
        if pin!=plan.old_policy or sha(_private_file(self.legacy_receipt))!=plan.old_receipt:
            raise ManualContextError("legacy admission changed")
        if p["source_sha256"]!=plan.predecessor:
            raise ManualContextError("legacy source pin changed")
        return a,p,first_successor(self.old,self.new,review=review,now=self.runtime.clock().isoformat(),
                  expected_old=plan.predecessor,expected_new=plan.successor,decision=plan.decision)

    @staticmethod
    def optional(path):
        try:return _private_file(path)
        except FileNotFoundError:return None
    def observe(self):
        out={"source":sha(read_snapshot(self.source)),"backup":sha(read_snapshot(self.backup))}
        for name,path in (("policy",self.policy),("receipt",self.receipt)):
            raw=self.optional(path);out[name]=None if raw is None else sha(raw)
        return out
    def read_journal(self):return self.optional(self.journal)
    def create_journal(self,raw):write_new(self.journal,raw)
    def remove_journal(self):
        self.journal.unlink();fsync_dir(self.journal.parent)
    def write(self,step,plan):
        if self.failure=="before-"+step:raise OSError("injected interruption")
        if step in ("source","backup"):
            path=getattr(self,step)
            if self.company_write:self.company_write(path,self.new)
            else:atomic_replace(path,self.new)
        elif step=="policy":write_new(self.policy,self.policy_bytes)
        elif step=="receipt":write_new(self.receipt,self.receipt_bytes)
        self.writes.append(step)
        if self.failure=="after-"+step:raise OSError("injected interruption")
    def verify_final(self,plan):
        self.preflight(plan)
        if plan.phase(self.observe())!=4:raise ManualContextError("not complete")
        self.project(plan,internal=True)
    def project(self,plan,internal=False):
        if plan!=self.approved_plan or (not internal and self.read_journal() is not None):
            raise ManualContextError("successor not available")
        if plan.phase(self.observe())!=4:raise ManualContextError("not admitted")
        a,p,rows=self.check(plan)
        now=self.runtime.clock().isoformat()
        result=project_controls(a,{"scope":_identity(a),"source_ref":"Company AC-401 fixture",
             "as_of":now,"coverage":"partial","records":rows},admitted_scope=p["scope"],
             admitted_positions=set(BINDINGS.values()),now=now)
        self.check(plan)
        if plan.phase(self.observe())!=4 or (not internal and self.read_journal() is not None):
            raise ManualContextError("changed during read")
        return result
    def run(self,plan=None):return advance(plan or self.plan,self)
