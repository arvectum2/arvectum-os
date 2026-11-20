"""Exact successor admission; dormant until a separately published approval.

No request, environment variable or writable policy can set these release pins.
"""
from contextlib import contextmanager
from hashlib import sha1
import json,os,stat,tempfile
from pathlib import Path
from types import SimpleNamespace
from .wsf_company_control_reference import sha,read_snapshot,BINDINGS
from .wsf_company_control_successor import first_successor
from .wsf_company_control_cutover import Plan,advance
from .wsf_manual_context import ManualContextError,_json,_identity
from .wsf_manual_policy import _private_file
from .wsf_manual_backup import PilotBackup,BACKUP_NAME
from .wsf_control_projection import project_controls

PUBLICATION='5c49b6079f113c06b26f197a6e0d805c9b5bb704'
APPROVED_PLAN_SHA='58969b2a2024ca3c06dfc5ee11311e5323e74b743ef278414f3acb9a1dda3056'
PUBLICATION_PATH="ac401-approved-publication.md"
PREFIX="company-control-successor"
JOURNAL="company-control-cutover.json"
PARTS=("Arvectum","backups","arvectum-company","control-register")

def exists(path):
    try:path.lstat();return True
    except FileNotFoundError:return False

def load_plan(root):
    if PUBLICATION is None or APPROVED_PLAN_SHA is None:
        raise ManualContextError("successor not published")
    raw=(Path(__file__).resolve().parent/PUBLICATION_PATH).read_bytes()
    blob=sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
    if blob!=PUBLICATION:raise ManualContextError("publication mismatch")
    raw=_private_file(root/"config"/(PREFIX+"-approved.json"))
    if sha(raw)!=APPROVED_PLAN_SHA:raise ManualContextError("approval mismatch")
    plan=Plan(**json.loads(raw))
    if plan.contract!=PUBLICATION:raise ManualContextError("contract mismatch")
    return plan

def write_atomic(path,raw):
    # Private trusted directory, caller holds shared transaction locks.
    parent=path.parent
    st=parent.lstat()
    if parent.resolve()!=parent or not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.getuid() or st.st_mode&0o077:
        raise ManualContextError("artifact directory unsafe")
    if exists(path):raise ManualContextError("new artifact already exists")
    fd,tmp=tempfile.mkstemp(prefix=".ac401-",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        # Exclusive link publication: no replace of an unexpected artifact.
        os.link(tmp,path,follow_symlinks=False)
        os.unlink(tmp)
        sync_dir(path.parent)
        if _private_file(path)!=raw:raise ManualContextError("artifact verify")
    finally:
        if exists(Path(tmp)):os.unlink(tmp)

def sync_dir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

def policy_bytes(p,plan):
    return _json({"schema":"arvectum.workspace.ac401-successor-policy/1",
      "scope":p["scope"],"credential_id":p["credential_id"],"grant_id":p["grant_id"],
      "records":BINDINGS,"starts_at":p["starts_at"],"expires_at":p["expires_at"],
      "predecessor":plan.predecessor,"source_sha256":plan.successor,
      "old_policy_sha256":plan.old_policy,"contract":plan.contract,"decision":plan.decision})

def receipt_bytes(plan):
    return _json({"schema":"arvectum.workspace.ac401-successor-receipt/1",
                  "policy_sha256":plan.policy,"contract":plan.contract,"decision":plan.decision})

class Admission:
    def __init__(self,runtime,authorize):
        self.runtime=runtime;self.authorize=authorize;self.root=runtime.root
        self.config=self.root/"config"
        self.source=runtime.source
        self.archive=self.source.parent/"successor-review"
        self.backup_access=PilotBackup(SimpleNamespace(directory=self.source.parent),parts=PARTS)
        self.backup=self.backup_access.volume.joinpath(*PARTS)/BACKUP_NAME
        self.policy=self.config/(PREFIX+"-policy.json")
        self.receipt=self.config/(PREFIX+"-activation.json")
        self.journal=self.config/JOURNAL

    def check(self,plan):
        if load_plan(self.root)!=plan:raise ManualContextError("approval changed")
        a=self.authorize();p,pin,review=self.runtime.gate(a)
        if (pin!=plan.old_policy or p["source_sha256"]!=plan.predecessor
            or sha(_private_file(self.config/"company-control-activation.json"))!=plan.old_receipt
            or sha(policy_bytes(p,plan))!=plan.policy or sha(receipt_bytes(plan))!=plan.receipt):
            raise ManualContextError("legacy or successor admission mismatch")
        old=read_snapshot(self.archive/"predecessor.private.json")
        new=read_snapshot(self.archive/"successor.private.json")
        rows=first_successor(old,new,review=review,now=self.runtime.clock().isoformat(),
            expected_old=plan.predecessor,expected_new=plan.successor,decision=plan.decision)
        return a,p,rows,old,new

    @staticmethod
    def optional(path):
        try:return _private_file(path)
        except FileNotFoundError:return None

    def observe(self):
        with self.backup_access._destination() as fd:
            raw=self.backup_access._read(fd)
        values={"source":sha(read_snapshot(self.source)),"backup":sha(raw)}
        for name,path in (("policy",self.policy),("receipt",self.receipt)):
            raw=self.optional(path);values[name]=None if raw is None else sha(raw)
        return values

    def read_journal(self):return self.optional(self.journal)
    def project(self,plan,*,internal=False):
        if not internal and exists(self.journal):raise ManualContextError("cutover incomplete")
        a,p,rows,_,_=self.check(plan)
        if plan.phase(self.observe())!=4:raise ManualContextError("successor unavailable")
        now=self.runtime.clock().isoformat()
        result=project_controls(a,{"scope":_identity(a),"source_ref":"Company AC-401",
             "as_of":now,"coverage":"partial","records":rows},admitted_scope=p["scope"],
             admitted_positions=set(BINDINGS.values()),now=now)
        self.check(plan)
        if plan.phase(self.observe())!=4 or (not internal and exists(self.journal)):
            raise ManualContextError("changed during read")
        return result

class DiskCutover(Admission):
    """Physical filesystem adapter. Company supplies the locked writer."""
    def __init__(self,runtime,authorize,company,maintenance):
        super().__init__(runtime,authorize)
        self.company=company;self.maintenance=maintenance
        self.quiet=None;self.writers={};self.backup_identity=None

    def check_destination(self):
        with self.backup_access._destination() as fd:
            st=os.fstat(fd);path=self.backup.parent.stat()
            identity=(st.st_dev,st.st_ino)
            if identity!=(path.st_dev,path.st_ino) or (self.backup_identity is not None and identity!=self.backup_identity):
                raise ManualContextError("backup destination changed")
            return identity

    @contextmanager
    def exclusive(self):
        with self.maintenance(self.root) as quiet:
            self.quiet=quiet
            try:
                self.backup_identity=self.check_destination()
                with self.company.locked_snapshot_writer(self.source) as source:
                    with self.company.locked_snapshot_writer(self.backup) as backup:
                        self.writers={"source":source,"backup":backup}
                        yield
            finally:
                self.writers={};self.quiet=None;self.backup_identity=None

    def preflight(self,plan):
        if self.quiet is None or len(self.writers)!=2:raise ManualContextError("maintenance required")
        self.quiet();self.check_destination()
        a,p,rows,old,new=self.check(plan)
        now=self.runtime.clock().isoformat()
        project_controls(a,{"scope":_identity(a),"source_ref":"Company AC-401",
             "as_of":now,"coverage":"partial","records":rows},admitted_scope=p["scope"],
             admitted_positions=set(BINDINGS.values()),now=now)
        for raw in (old,new):
            doc=json.loads(raw);self.company.replay(doc)
            if self.company.canonical(doc)!=raw:raise ManualContextError("Company canonical format")
        if self.company.replay(json.loads(old)).keys()!=self.company.replay(json.loads(new)).keys():
            raise ManualContextError("Company boundary changed")
    def observe(self):
        self.check_destination()
        return super().observe()
    def create_journal(self,raw):write_atomic(self.journal,raw)
    def remove_journal(self):
        self.journal.unlink();sync_dir(self.journal.parent)
    def write(self,step,plan):
        self.preflight(plan)
        a,p,_,old,new=self.check(plan)
        if step in self.writers:
            self.writers[step](json.loads(new),expected_digest=sha(old))
            self.check_destination()
        elif step=="policy":write_atomic(self.policy,policy_bytes(p,plan))
        elif step=="receipt":write_atomic(self.receipt,receipt_bytes(plan))
        else:raise ManualContextError("unknown write")
    def verify_final(self,plan):
        self.preflight(plan);self.project(plan,internal=True)
    def run(self,plan):
        return advance(plan,self)

def selected_successor(runtime,authorize):
    cfg=runtime.root/"config"
    if exists(cfg/JOURNAL):raise ManualContextError("cutover incomplete")
    if any(exists(cfg/(PREFIX+s)) for s in ("-policy.json","-activation.json")):
        plan=load_plan(runtime.root)
        return Admission(runtime,authorize).project(plan)
    return None
