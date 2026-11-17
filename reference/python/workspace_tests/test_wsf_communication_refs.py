from copy import deepcopy
from pathlib import Path
import tempfile,unittest
from uuid import uuid4
from test_wsf_manual_context import access
from workspace_app.wsf_manual_context import ManualContextError
from workspace_app.wsf_communication_refs import CommunicationReferences
from workspace_app.wsf_manual_backup import PilotBackup

class CommunicationTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name).resolve();self.a=access()
        self.bindings={"mail":{"kind":"mail","account_ref":"a"*64,"container_ref":"b"*64},
                       "calendar":{"kind":"calendar","account_ref":"c"*64,"container_ref":"d"*64}}
        self.allowed=set(self.bindings);self.project="PRJ-"+uuid4().hex
        self.now="2026-11-17T10:00:00Z"
        self.s=self.make("original");self.s.initialize(self.a)
    def make(self,name,**kw):
        return CommunicationReferences(self.root/name,self.a,bindings=kw.get("bindings",self.bindings),project_ids={self.project})
    def mail(self,**kw):
        return {"native_id":"e"*64,"revision":"1"*64,"state":"received","occurred_at":"2026-11-17T09:00:00Z","start":None,"end":None,**kw}
    def calendar(self,**kw):
        return {"native_id":"e"*64,"revision":"1"*64,"state":"confirmed","occurred_at":None,"start":"2026-11-18","end":"2026-11-19",**kw}
    def page(self,kind,rows,**kw):
        self.s.admit_page(self.a,kw.pop("key",uuid4().hex),**{"binding":kind,"expected_cursor":None,"next_cursor":"f"*64,"complete":True,"rows":rows,"checked_at":self.now,"authorized_bindings":self.allowed,**kw})
    def view(self,allowed=None):
        return self.s.read(self.a,authorized_bindings=self.allowed if allowed is None else allowed,now=self.now)
    def review(self,r,**kw):
        self.s.review(self.a,kw.pop("key",uuid4().hex),**{"item_id":r["id"],"expected_revision":r["review_revision"],"state":"reviewed","project_id":self.project,"at":self.now,"authorized_bindings":self.allowed,**kw})
    def test_account_scoped_native_identity_and_link(self):
        self.page("mail",[self.mail()]);self.page("calendar",[self.calendar()])
        d=self.view();self.assertEqual(d["pending"],2)
        self.assertNotEqual(d["items"][0]["id"],d["items"][1]["id"])
        self.review(d["items"][0])
        self.assertEqual(self.view()["items"][0]["project_id"],self.project)
        self.assertFalse(self.view()["canonical_authority"])
    def test_page_retry_and_revision_dedup(self):
        k=uuid4().hex;self.page("mail",[self.mail()],key=k)
        raw=self.s.export(self.a,authorized_bindings=self.allowed)
        self.page("mail",[self.mail()],key=k)
        self.assertEqual(self.s.export(self.a,authorized_bindings=self.allowed),raw)
        self.page("mail",[self.mail()],expected_cursor="f"*64,next_cursor="0"*64)
        self.assertEqual(self.view()["pending"],1)
        r=self.view()["items"][0];self.review(r)
        self.page("mail",[self.mail(revision="2"*64)],expected_cursor="0"*64,next_cursor="3"*64)
        r=self.view()["items"][0]
        self.assertIsNone(r["project_id"]);self.assertEqual(r["review_revision"],3)
        self.assertEqual(r["review_state"],"pending")
        with self.assertRaises(ManualContextError):self.page("mail",[self.mail()],expected_cursor="3"*64,next_cursor="4"*64)
    def test_cursor_conflict_no_partial_write(self):
        self.page("mail",[self.mail()],complete=False)
        self.assertEqual(self.view()["sources"][1]["state"],"incomplete")
        raw=self.s.export(self.a,authorized_bindings=self.allowed)
        with self.assertRaises(ManualContextError):self.page("mail",[self.mail(revision="2"*64)])
        with self.assertRaises(ManualContextError):self.page("mail",[self.mail(occurred_at="2026-11-17T08:00:00Z")],expected_cursor="f"*64,next_cursor="0"*64)
        self.assertEqual(self.s.export(self.a,authorized_bindings=self.allowed),raw)
    def test_cancelled_event_is_not_obligation_closure(self):
        self.page("calendar",[self.calendar()])
        self.review(self.view()["items"][0])
        self.page("calendar",[self.calendar(revision="2"*64,state="cancelled",start=None,end=None)],expected_cursor="f"*64,next_cursor="0"*64)
        r=self.view()["items"][0]
        self.assertEqual(r["source"]["state"],"cancelled")
        self.assertEqual(r["review_state"],"pending")
        self.assertIsNone(r["project_id"])
    def test_interval_and_shape_strict(self):
        for r in (self.calendar(end="2026-11-17"),self.calendar(end="2026-11-19T00:00:00Z"),self.calendar(description="raw"),self.calendar(native_id="someone@example.org")):
            with self.assertRaises(ManualContextError):self.page("calendar",[r])
        with self.assertRaises(ManualContextError):self.page("mail",[self.mail(occurred_at=None)])
        with self.assertRaises(ManualContextError):self.page("mail",[self.mail()],next_cursor="real-secret-token")
        self.assertFalse(self.view()["items"])
    def test_revoked_sources_suppress_rows_counts_and_deny_mutation_export(self):
        self.page("mail",[self.mail()]);self.page("calendar",[self.calendar()])
        r=self.view()["items"][0]
        self.assertEqual(self.view({"calendar"})["pending"],1)
        self.assertEqual(self.view(set())["pending"],0)
        self.assertEqual(self.view(set())["coverage"],"unknown")
        with self.assertRaises(ManualContextError):self.review(r,authorized_bindings={"calendar"})
        with self.assertRaises(ManualContextError):self.page("mail",[],authorized_bindings={"calendar"})
        with self.assertRaises(ManualContextError):self.s.export(self.a,authorized_bindings={"calendar"})
        with self.assertRaises(ManualContextError):self.s.read(access(org="other"),authorized_bindings=self.allowed,now=self.now)
    def test_project_review_cas(self):
        self.page("mail",[self.mail()]);r=self.view()["items"][0]
        with self.assertRaises(ManualContextError):self.review(r,project_id="PRJ-"+uuid4().hex)
        with self.assertRaises(ManualContextError):self.review(r,state="dismissed")
        self.review(r)
        with self.assertRaises(ManualContextError):self.review(r)
    def test_backup_restore_and_binding_pin(self):
        self.page("mail",[self.mail()])
        volume=self.root/"volume";volume.mkdir(mode=0o700);(volume/"refs").mkdir(mode=0o700)
        b=PilotBackup(self.s.file,volume=volume,uuid="fixture",parts=("refs",),verifier=lambda v,u:None)
        b.copy_latest(self.a)
        raw=b.verified_snapshot(self.a)
        restored=self.make("restored");restored.restore_empty(self.a,raw,authorized_bindings=self.allowed)
        self.assertEqual(restored.export(self.a,authorized_bindings=self.allowed),raw)
        bad=deepcopy(self.bindings);bad["mail"]["container_ref"]="0"*64
        with self.assertRaises(ManualContextError):self.make("other",bindings=bad).restore_empty(self.a,raw,authorized_bindings=self.allowed)
        self.s.file.path.write_bytes(b"corrupt")
        with self.assertRaises(ManualContextError):self.view()
        self.assertEqual(self.s.file.path.read_bytes(),b"corrupt")
