from datetime import datetime,timedelta,timezone
from pathlib import Path
from copy import deepcopy
from uuid import uuid4
import tempfile,unittest
from test_wsf_tender_events import TenderEventTests
from workspace_app.wsf_manual_context import ManualContextError
from workspace_app.wsf_tender_inbox import TenderInbox,SOURCE_SCHEMA
from workspace_app.wsf_manual_backup import PilotBackup

class TenderInboxTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name).resolve()
        self.f=TenderEventTests();self.f.setUp()
        self.a=self.f.a;self.s=self.make("inbox");self.s.initialize(self.a)
        self.now=self.f.now
    def make(self,name,**kw):
        return TenderInbox(self.root/name,self.a,**{"binding_id":"fixture","tenant":self.f.tenant,
                      "project_map":self.f.mapping,**kw})
    def window(self,rows,**kw):
        return {"schema":SOURCE_SCHEMA,"state":"observed","coverage":"partial","since":"2026-11-17T09:00:00Z","until":self.now,"rows":rows,**kw}
    def admit(self,rows,**kw):
        self.s.admit_window(self.a,kw.pop("key",uuid4().hex),self.window(rows,**kw),self.now)
    def review(self,group):
        self.s.review(self.a,uuid4().hex,group["id"],group["revision"],"reviewed",self.now)
    def test_overlap_dedup_and_new_event_reopens_review(self):
        a,b=self.f.row(),self.f.row("review_required")
        self.admit([a]);r=self.s.read(self.a)["groups"][0];self.review(r)
        self.admit([a]);self.assertEqual(self.s.read(self.a)["pending_count"],0)
        self.admit([a,b]);d=self.s.read(self.a)
        self.assertEqual(len(d["events"]),2);self.assertEqual(len(d["groups"]),1)
        self.assertTrue(d["groups"][0]["review_signal"])
        self.assertEqual(d["groups"][0]["revision"],3);self.assertEqual(d["pending_count"],1)
        self.assertEqual(d["groups"][0]["owner_action"],"unknown")
        with self.assertRaises(ManualContextError):self.review(r)
    def test_request_replay_and_restart(self):
        k=uuid4().hex;self.admit([self.f.row()],key=k);raw=self.s.export(self.a)
        self.admit([self.f.row()],key=k);self.assertEqual(raw,self.s.export(self.a))
        self.s=self.make("inbox",require_initialized=True)
        self.assertEqual(self.s.read(self.a)["pending_count"],1)
        with self.assertRaises(ManualContextError):self.admit([],key=k)
    def test_overflow_and_absence_not_closure(self):
        self.assertEqual(self.s.read(self.a)["coverage"],"unknown")
        self.admit([self.f.row()])
        self.admit([],state="overflow");d=self.s.read(self.a)
        self.assertEqual(d["observation"]["state"],"overflow")
        self.assertEqual(d["pending_count"],1);self.assertEqual(d["coverage"],"partial")
        self.admit([]);self.assertEqual(self.s.read(self.a)["pending_count"],1)
    def test_reject_cross_tenant_conflict_and_interval_atomically(self):
        self.admit([self.f.row()]);raw=self.s.export(self.a)
        bad=self.f.row();bad["id"]="other"
        foreign=self.f.row();foreign["tenant_id"]=foreign["envelope"]["tenant_id"]="foreign"
        for rows,kw in [([bad],{}),([foreign],{}),([self.f.row()],{"since":"2026-11-17T09:30:00Z"}),([self.f.row()],{"state":"overflow"}),([],{"coverage":"complete"})]:
            with self.assertRaises(ManualContextError):self.admit(rows,**kw)
        self.assertEqual(self.s.export(self.a),raw)
    def test_restore_scope_and_private_backup(self):
        self.admit([self.f.row()]);self.review(self.s.read(self.a)["groups"][0])
        v=self.root/"volume";v.mkdir(mode=0o700);(v/"tender").mkdir(mode=0o700)
        b=PilotBackup(self.s.file,volume=v,uuid="fixture",parts=("tender",),verifier=lambda a,b:None)
        b.copy_latest(self.a);raw=b.verified_snapshot(self.a)
        t=self.make("restored");t.restore_empty(self.a,raw)
        self.assertEqual(t.read(self.a),self.s.read(self.a))
        with self.assertRaises(ManualContextError):t.restore_empty(self.a,raw)
        with self.assertRaises(ManualContextError):self.make("other",tenant="other").restore_empty(self.a,raw)
        self.s.file.path.write_bytes(b"corrupt")
        with self.assertRaises(ManualContextError):self.s.read(self.a)
        self.assertEqual(self.s.file.path.read_bytes(),b"corrupt")
