"""Experimental durable reviewer-side head, reservation and revocation store.

Requires independently controlled host/account/config and authenticated caller.
No network listener, production enrollment, signing key or grant provisioning.
"""
from contextlib import contextmanager,closing
from dataclasses import asdict
from pathlib import Path
import os,sqlite3,stat
from .wsf_review_ticket import need,digest,hex64,Ticket
from .wsf_manual_context import _json
from .wsf_control_projection import stamp

class ReviewAuthority:
    def __init__(self,path,trust,*,authenticated_operator):
        self.path=Path(path);self.trust=trust;self.operator=authenticated_operator
        self.pin=digest(_json(asdict(trust)))
        need(self.operator==trust.operator,"authenticated operator mismatch")
    def private(self):
        p=self.path.parent;s=p.lstat()
        need(p.resolve()==p and stat.S_ISDIR(s.st_mode) and s.st_uid==os.getuid() and not s.st_mode&0o077,"unsafe authority directory")
        s=self.path.lstat()
        need(stat.S_ISREG(s.st_mode) and s.st_uid==os.getuid() and s.st_nlink==1 and not s.st_mode&0o077,"unsafe authority store")
    @classmethod
    def initialize(cls,path,trust,*,baseline,authenticated_operator):
        need(hex64(baseline),"invalid genesis")
        obj=cls(path,trust,authenticated_operator=authenticated_operator)
        p=obj.path.parent;s=p.lstat()
        need(p.resolve()==p and stat.S_ISDIR(s.st_mode) and s.st_uid==os.getuid() and not s.st_mode&0o077,"unsafe authority directory")
        fd=os.open(obj.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600);os.close(fd)
        with closing(sqlite3.connect(obj.path)) as db,db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("CREATE TABLE metadata (pin TEXT NOT NULL, genesis TEXT NOT NULL, revoked INTEGER NOT NULL CHECK(revoked IN (0,1)))")
            db.execute("CREATE TABLE history (seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, predecessor TEXT NOT NULL, successor TEXT NOT NULL, ticket BLOB NOT NULL, sig BLOB NOT NULL)")
            db.execute("CREATE TABLE reservation (slot INTEGER PRIMARY KEY CHECK(slot=1), id TEXT NOT NULL, ticket BLOB NOT NULL, sig BLOB NOT NULL)")
            db.execute("INSERT INTO metadata VALUES (?,?,0)",(obj.pin,baseline))
        fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
        return obj
    @contextmanager
    def tx(self):
        self.private()
        # mode=rw prevents silent recreation of a missing database.
        with closing(sqlite3.connect(self.path.as_uri()+"?mode=rw",uri=True,timeout=3)) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            try:
                meta=db.execute("SELECT pin,genesis,revoked FROM metadata").fetchall()
                need(len(meta)==1 and meta[0][0]==self.pin and hex64(meta[0][1]),"authority configuration mismatch")
                yield db,meta[0]
                db.commit()
            except BaseException:db.rollback();raise
    def current(self,db,meta):
        h=(0,"0"*64,meta[1])
        for seq,id,pred,succ,raw,sig in db.execute("SELECT seq,id,predecessor,successor,ticket,sig FROM history ORDER BY seq"):
            t=Ticket.decode(raw)
            need((seq,id,pred,succ)==(t.sequence,t.id(),t.predecessor,t.successor)
                 and (seq-1,t.previous_ticket,pred)==h,"authority history mismatch")
            # Historical signatures checked at issuance; live expiry is separate.
            self.trust.verify(t,sig,t.issued_at)
            h=(seq,id,succ)
        return h
    def pending(self,db):
        return db.execute("SELECT id,ticket,sig FROM reservation WHERE slot=1").fetchone()
    def check(self,db,meta,trust,t,now):
        need(trust==self.trust and not meta[2],"authority revoked or changed")
        trust.bind(t,now)
        h=self.current(db,meta);p=self.pending(db)
        old=(t.sequence-1,t.previous_ticket,t.predecessor);new=(t.sequence,t.id(),t.successor)
        need(h in (old,new),"old or conflicting ticket")
        need(p is None or p[0]==t.id(),"competing reservation")
        return h,p
    def check_live(self,trust,t,sig,now):
        trust.verify(t,sig,now)
        with self.tx() as (db,m):self.check(db,m,trust,t,now)
    def head(self,register):
        need(register==self.trust.register,"wrong authority resource")
        with self.tx() as (db,m):
            need(not m[2],"authority revoked")
            return self.current(db,m)
    def read_head(self,register):
        need(register==self.trust.register,"wrong authority resource")
        with self.tx() as (db,m):
            need(not m[2] and self.pending(db) is None,"revoked or pending update")
            return self.current(db,m)
    def reserve(self,trust,t,sig,now):
        trust.verify(t,sig,now)
        with self.tx() as (db,m):
            h,p=self.check(db,m,trust,t,now)
            if h==(t.sequence,t.id(),t.successor):
                need(p is None,"inconsistent committed reservation");return
            obj=(t.id(),t.raw(),sig)
            if p is not None:need(p==obj,"reservation signature mismatch")
            else:db.execute("INSERT INTO reservation VALUES (1,?,?,?)",obj)
    def compare_and_set(self,register,old,new,trust,t,sig,now):
        need(register==trust.register,"resource mismatch")
        trust.verify(t,sig,now)
        with self.tx() as (db,m):
            h,p=self.check(db,m,trust,t,now)
            need(old==(t.sequence-1,t.previous_ticket,t.predecessor) and new==(t.sequence,t.id(),t.successor),"CAS binding")
            need(h==old and p==(t.id(),t.raw(),sig),"reservation or head mismatch")
            db.execute("INSERT INTO history VALUES (?,?,?,?,?,?)",(t.sequence,t.id(),t.predecessor,t.successor,t.raw(),sig))
            db.execute("DELETE FROM reservation WHERE slot=1")
    def revoke(self):
        # Reviewer-side administrative operation, never exposed to operator RPC.
        with self.tx() as (db,m):db.execute("UPDATE metadata SET revoked=1")
