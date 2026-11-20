"""Candidate reusable private disk adapter, no installed operator or trust bootstrap.

Trusted composition must provide actual maintenance and encrypted-volume
verification; this adapter never treats local file presence as authorization.
"""
import base64,json,os,stat,tempfile
from pathlib import Path
from contextlib import contextmanager
from .wsf_review_ticket import Ticket,need,digest,hex64
from .wsf_manual_context import _json
from .wsf_company_control_reference import read_snapshot
from .wsf_company_control_admission import exists,sync_dir

def publish(path,raw):
    need(not exists(path) and len(raw)<=32768,"exclusive artifact publication")
    fd,tmp=tempfile.mkstemp(prefix=".review-",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.link(tmp,path,follow_symlinks=False);os.unlink(tmp)
        sync_dir(path.parent)
        need(read_snapshot(path)==raw,"artifact verification")
    finally:
        if exists(Path(tmp)):os.unlink(tmp)

class ReviewedDisk:
    def __init__(self,*,source,backup,archive,candidates,company,maintenance,verify_destination):
        self.source,self.backup,self.archive=map(Path,(source,backup,archive))
        need(len({self.source.parent,self.backup.parent,self.archive})==3,"distinct private directories")
        self.input=candidates;self.company=company;self.maintenance=maintenance
        self.verify_destination=verify_destination
        self.j=self.archive/"transition.json";self.writers={};self.quiet=None;self.identity=None
    def destination(self):
        # Trusted external volume check must cover identity and encryption.
        self.verify_destination(self.backup)
        st=self.backup.parent.lstat()
        need(stat.S_ISDIR(st.st_mode) and self.backup.parent.resolve()==self.backup.parent,"unsafe backup directory")
        identity=(st.st_dev,st.st_ino)
        need(self.identity is None or identity==self.identity,"backup identity changed")
        return identity
    @contextmanager
    def exclusive(self):
        with self.maintenance() as quiet:
            self.quiet=quiet
            try:
                self.identity=self.destination()
                with self.company.locked(self.archive):
                    with self.company.locked_snapshot_writer(self.source) as src:
                        with self.company.locked_snapshot_writer(self.backup) as bk:
                            self.writers={"source":src,"backup":bk}
                            yield
            finally:self.writers={};self.quiet=None;self.identity=None
    def check_write(self):
        need(self.quiet is not None and len(self.writers)==2,"maintenance and Company locks required")
        self.quiet();self.destination()
    def candidates(self,t):return self.input(t)
    def read_source(self):return read_snapshot(self.source)
    def read_backup(self):
        self.destination();return read_snapshot(self.backup)
    def journal(self):
        try:return read_snapshot(self.j)
        except FileNotFoundError:return None
    def begin(self,raw):
        self.check_write();publish(self.j,raw)
    def finish(self):
        self.check_write();self.j.unlink();sync_dir(self.archive)
    def append_source(self,raw,old):
        self.check_write();self.writers["source"](json.loads(raw),expected_digest=old)
    def append_backup(self,raw,old):
        self.check_write();self.writers["backup"](json.loads(raw),expected_digest=old);self.destination()
    def artifact(self,id):
        need(hex64(id),"invalid archive identity");return self.archive/(id+".json")
    def archive_ticket(self,t,sig):
        self.check_write()
        publish(self.artifact(t.id()),_json({"ticket":base64.b64encode(t.raw()).decode(),"signature":base64.b64encode(sig).decode()}))
    def read_ticket(self,id):
        raw=read_snapshot(self.artifact(id))
        need(len(raw)<=32768,"archive bound")
        obj=json.loads(raw);need(set(obj)=={"ticket","signature"} and _json(obj)==raw,"archive format")
        t=Ticket.decode(base64.b64decode(obj["ticket"],validate=True))
        sig=base64.b64decode(obj["signature"],validate=True)
        need(t.id()==id,"archive identity mismatch");return t,sig
    def observe(self,t,sig):
        p=self.artifact(t.id());archived=exists(p)
        if archived:
            tt,ss=self.read_ticket(t.id());need(tt==t and ss==sig,"archived ticket changed")
        return digest(self.read_source()),digest(self.read_backup()),archived
