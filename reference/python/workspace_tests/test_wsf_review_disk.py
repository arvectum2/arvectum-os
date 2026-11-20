"""Private filesystem adapter exercise; trust/maintenance/volume are test seams."""
import json,unittest,tempfile
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch
from workspace_app.wsf_review_disk import ReviewedDisk
from workspace_app.wsf_review_transition import transition,admitted_bytes
from workspace_app.wsf_review_ticket import digest,need
from workspace_app.wsf_manual_context import ManualContextError
from review_ticket_fixture import Authority,atomic,key,sign,trust_for,ticket_for,NOW
from test_wsf_review_transition import Company,raw,baseline,decision

class LockedCompany(Company):
    @staticmethod
    @contextmanager
    def locked(directory):yield
    @classmethod
    @contextmanager
    def locked_snapshot_writer(cls,path):
        def write(doc,*,expected_digest):
            need(digest(path.read_bytes())==expected_digest,"predecessor")
            atomic(path,cls.canonical(doc))
        yield write
@unittest.skipUnless(Path("/usr/bin/ssh-keygen").is_file(),"system verifier unavailable")
class DiskTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        d=Path(t.name).resolve();k=key(d)
        for name in ("source","backup","archive"):(d/name).mkdir(mode=0o700)
        self.old=raw(baseline());self.new=raw(baseline()+[decision("DEC-004")])
        self.src=d/"source/register.json";self.bk=d/"backup/register.json"
        for p in (self.src,self.bk):atomic(p,self.old)
        self.a=Authority(self.old);self.trust=trust_for(k,"decision")
        self.t=ticket_for(self.trust,self.a.value,self.old,self.new,"DEC-004");self.sig=sign(d,k,self.t)
        self.volume=True;self.quiet=True
        @contextmanager
        def maintenance():yield lambda:need(self.quiet,"maintenance lost")
        self.io=ReviewedDisk(source=self.src,backup=self.bk,archive=d/"archive",candidates=lambda t:(self.old,self.new),
            company=LockedCompany,maintenance=maintenance,verify_destination=lambda path:need(self.volume,"volume denied"))
    def run_t(self):
        return transition(self.t,self.sig,trust=self.trust,authority=self.a,io=self.io,company=LockedCompany,
            verify_historical_act=lambda r:True,clock=lambda:NOW)
    def read(self):return admitted_bytes(trust=self.trust,authority=self.a,io=self.io,clock=lambda:NOW)
    def test_disk_resume_and_private_archive(self):
        original=self.io.append_source
        def stop(*args):original(*args);raise OSError("after source")
        with patch.object(self.io,"append_source",side_effect=stop):
            with self.assertRaises(OSError):self.run_t()
        self.assertTrue(self.io.j.is_file());self.assertEqual(self.bk.read_bytes(),self.old)
        with self.assertRaises(ManualContextError):self.read()
        self.assertEqual(self.run_t(),"completed")
        self.assertEqual(self.run_t(),"already-completed")
        self.assertEqual(self.read(),self.new)
        p=self.io.artifact(self.t.id())
        self.assertEqual(p.stat().st_mode&0o777,0o600)
        p.chmod(0o644)
        with self.assertRaises(ManualContextError):self.read()
    def test_volume_and_maintenance_denial(self):
        self.volume=False
        with self.assertRaises(ManualContextError):self.run_t()
        self.volume=True;self.quiet=False
        with self.assertRaises(ManualContextError):self.run_t()
        self.assertEqual(self.src.read_bytes(),self.old);self.assertIsNone(self.io.journal())
