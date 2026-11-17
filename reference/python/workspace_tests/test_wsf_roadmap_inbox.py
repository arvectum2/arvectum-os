from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from test_wsf_manual_context import access
from workspace_app.wsf_manual_context import ManualContextError
from workspace_app.wsf_roadmap_inbox import RoadmapInbox,metadata_snapshot,registry_bindings
from workspace_app.wsf_manual_backup import PilotBackup


class RoadmapInboxTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name).resolve();self.a=access()
        self.bindings={"COMPANY":{"repository":"arvectum2/arvectum-company","path":"docs/roadmap/ROADMAP.md","adapter":"company-roadmap-v1"},
                       "PORT-005":{"repository":None,"path":None,"adapter":"reconciliation-required"}}
        self.start=datetime(2026,11,17,10,tzinfo=timezone.utc)
        self.inbox=self.make("inbox");self.inbox.initialize(self.a)

    def make(self,name,**kw):
        return RoadmapInbox(self.root/name,self.a,bindings=kw.get("bindings",self.bindings))

    def projection(self,i=0,digest="a",commit="1",state="current-source-backed"):
        at=(self.start+timedelta(minutes=i)).isoformat()
        return {"schema":"arvectum.workspace.company-portfolio/1","projection":{"read_only":True,"canonical_authority":False},
                "scope":{"organization_resolved_server_side":True,"actor_resolved_server_side":True,"cross_organization_aggregation":False},
                "projects":[{"id":"COMPANY","repository":"arvectum2/arvectum-company","roadmap_path":"docs/roadmap/ROADMAP.md","state":state,
                   "source":{"repository":"arvectum2/arvectum-company","path":"docs/roadmap/ROADMAP.md","adapter":"company-roadmap-v1",
                   "freshness":"fresh-fetch","commit_sha":commit*40,"content_sha256":digest*64,"fetched_at":at},
                   "roadmap":{"status":"UNTRUSTED RAW CONTENT NEVER STORED"}},
                   {"id":"PORT-005","repository":None,"roadmap_path":None,"state":"reconciliation-required","source":None}]}

    def scan(self,i=0,digest="a",commit="1",state="current-source-backed",key=None,p=None):
        self.inbox.scan(self.a,key or uuid4().hex,p or self.projection(i,digest,commit,state),(self.start+timedelta(minutes=i)).isoformat())

    def view(self):return self.inbox.read(self.a)

    def test_baseline_and_same_content_commit_churn_no_noise(self):
        self.scan();self.scan(1,commit="2")
        d=self.view()
        self.assertEqual(d["pending_count"],0)
        self.assertEqual(d["sources"][0]["checkpoint"]["commit_sha"],"2"*40)
        self.assertEqual(d["sources"][1]["state"],"reconciliation-required")
        self.assertNotIn(b"UNTRUSTED RAW CONTENT",self.inbox.export(self.a))

    def test_changes_replay_and_review_history(self):
        self.scan();key=uuid4().hex;self.scan(1,digest="b",commit="2",key=key)
        self.scan(1,digest="b",commit="2",key=key)
        self.scan(2,digest="b",commit="3")
        self.assertEqual(self.view()["pending_count"],1)
        i=self.view()["items"][0]
        self.assertEqual(i["previous"]["content_sha256"],"a"*64)
        at=(self.start+timedelta(minutes=3)).isoformat();k=uuid4().hex
        self.inbox.review(self.a,k,i["id"],1,"reviewed",at)
        self.inbox.review(self.a,k,i["id"],1,"reviewed",at)
        self.assertEqual(self.view()["pending_count"],0)
        self.assertEqual(self.view()["items"][0]["revision"],2)
        with self.assertRaises(ManualContextError):self.inbox.review(self.a,uuid4().hex,i["id"],1,"dismissed",at)
        self.scan(4,digest="a",commit="4")
        self.assertEqual(self.view()["pending_count"],1)
        self.assertEqual(len(self.view()["items"]),2)

    def test_unavailable_or_cached_preserves_last_good_checkpoint(self):
        self.scan()
        for i,s in enumerate(("unavailable","stale-cache","cached-source-backed"),1):
            self.scan(i,digest="b",commit="2",state=s)
            r=self.view()["sources"][0]
            self.assertEqual(r["state"],s)
            self.assertEqual(r["checkpoint"]["content_sha256"],"a"*64)
            self.assertEqual(self.view()["pending_count"],0)
        self.scan(4,digest="b",commit="2")
        self.assertEqual(self.view()["pending_count"],1)

    def test_immutable_commit_conflict_and_out_of_order(self):
        self.scan()
        raw=self.inbox.export(self.a)
        with self.assertRaises(ManualContextError):self.scan(1,digest="b")
        self.assertEqual(self.inbox.export(self.a),raw)
        self.scan(2,digest="b",commit="2")
        with self.assertRaises(ManualContextError):self.scan(1,digest="c",commit="3")

    def test_exact_registry_and_scope(self):
        p=self.projection()
        for field,val in (("repository","other/repo"),("roadmap_path","other.md"),("id","PORT-999")):
            q=deepcopy(p);q["projects"][0][field]=val
            with self.assertRaises(ManualContextError):self.scan(p=q)
        q=deepcopy(p);q["projects"].pop()
        with self.assertRaises(ManualContextError):self.scan(p=q)
        q=deepcopy(p);q["scope"]["cross_organization_aggregation"]=True
        with self.assertRaises(ManualContextError):self.scan(p=q)
        with self.assertRaises(ManualContextError):self.inbox.read(access(actor="other"))

    def test_freshness_and_reference_validation(self):
        for field,val in (("content_sha256","not-sha"),("adapter","other"),("freshness","stale-cache"),
                          ("fetched_at","2026-11-17T09:00:00+00:00"),("fetched_at","2026-11-17T10:01:00+00:00")):
            p=self.projection();p["projects"][0]["source"][field]=val
            with self.assertRaises(ManualContextError):self.scan(p=p)

    def test_persistent_restore_and_registry_pin(self):
        self.scan();self.scan(1,digest="b",commit="2")
        raw=self.inbox.export(self.a)
        self.inbox=self.make("inbox")
        self.assertEqual(self.view()["pending_count"],1)
        restored=self.make("restore");restored.restore_empty(self.a,raw)
        self.assertEqual(restored.export(self.a),raw)
        with self.assertRaises(ManualContextError):restored.restore_empty(self.a,raw)
        b=deepcopy(self.bindings);b["COMPANY"]["adapter"]="other"
        with self.assertRaises(ManualContextError):self.make("other",bindings=b).restore_empty(self.a,raw)
        self.inbox.file.path.write_bytes(b"corrupt")
        with self.assertRaises(ManualContextError):self.view()
        self.assertEqual(self.inbox.file.path.read_bytes(),b"corrupt")

    def test_backup_compatible_and_recover(self):
        volume=self.root/"fixture-volume";volume.mkdir(mode=0o700)
        dest=volume/"inbox";dest.mkdir(mode=0o700)
        b=PilotBackup(self.inbox.file,volume=volume,uuid="fixture",parts=("inbox",),verifier=lambda v,u:None)
        self.scan();b.copy_latest(self.a);self.scan(1,digest="b",commit="2");b.copy_latest(self.a)
        r=self.make("restored");r.restore_empty(self.a,b.verified_snapshot(self.a))
        self.assertEqual(r.export(self.a),self.inbox.export(self.a))

    def test_packaged_registry_shape(self):
        b=registry_bindings()
        self.assertEqual(len(b),10)
        self.assertEqual(sum(p["path"] is not None for p in b.values()),7)
