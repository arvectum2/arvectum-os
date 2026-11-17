from copy import deepcopy
from pathlib import Path
from uuid import uuid4
from datetime import timedelta
import unittest
from test_wsf_roadmap_inbox import RoadmapInboxTests
from workspace_app.wsf_manual_context import ManualContextError
from workspace_app.wsf_inbox_registry_preview import preview_resolved_bindings
from workspace_app.wsf_roadmap_inbox import RoadmapInbox,registry_bindings

class RegistryPreviewTests(unittest.TestCase):
    def setUp(self):
        f=RoadmapInboxTests();f.setUp();self.addCleanup(f.doCleanups);self.f=f
        f.bindings["PORT-005"]["repository"]="arvectum2/fixture"
        f.inbox=f.make("old");f.inbox.initialize(f.a)
    def projection(self,i=0,digest="a",commit="1"):
        p=self.f.projection(i,digest,commit)
        p["projects"][1]["repository"]="arvectum2/fixture"
        return p
    def scan(self,i=0,digest="a",commit="1"):
        self.f.scan(i,digest,commit,p=self.projection(i,digest,commit))
    def candidate(self):
        b=deepcopy(self.f.bindings);b["PORT-005"].update(path="docs/ROADMAP.md",adapter="generic-roadmap-v1");return b
    def test_history_and_first_new_baseline(self):
        f=self.f;self.scan();self.scan(1,"b","2")
        row=f.view()["items"][0]
        f.inbox.review(f.a,uuid4().hex,row["id"],1,"reviewed",(f.start+timedelta(minutes=2)).isoformat())
        old=f.inbox.export(f.a)
        target=f.make("new",bindings=self.candidate())
        raw,evidence=preview_resolved_bindings(f.a,f.inbox,target)
        self.assertEqual(evidence["changed"],["PORT-005"])
        self.assertEqual(evidence["event_count"],3)
        self.assertFalse(target.file.path.exists())
        self.assertEqual(f.inbox.export(f.a),old)
        target.restore_empty(f.a,raw)
        self.assertEqual(target.read(f.a),f.view())
        p=self.projection(3,"b","2")
        b=p["projects"][1];b.update(roadmap_path="docs/ROADMAP.md",state="current-source-backed",source={"repository":"arvectum2/fixture","path":"docs/ROADMAP.md","adapter":"generic-roadmap-v1","freshness":"fresh-fetch","commit_sha":"3"*40,"content_sha256":"c"*64,"fetched_at":(f.start+timedelta(minutes=3)).isoformat()})
        target.scan(f.a,uuid4().hex,p,(f.start+timedelta(minutes=3)).isoformat())
        self.assertEqual(target.read(f.a)["pending_count"],0)
        self.assertEqual(target.read(f.a)["items"],f.view()["items"])
    def test_refuses_existing_target_and_rebinding(self):
        f=self.f;self.scan()
        target=f.make("existing",bindings=self.candidate());target.initialize(f.a)
        with self.assertRaises(ManualContextError):preview_resolved_bindings(f.a,f.inbox,target)
        for i,mode in enumerate(("existing","repository","identity")):
            b=self.candidate()
            if mode=="existing":b["COMPANY"]["path"]="OTHER.md"
            elif mode=="repository":b["PORT-005"]["repository"]="arvectum2/other"
            else:del b["PORT-005"]
            with self.assertRaises(ManualContextError):preview_resolved_bindings(f.a,f.inbox,target=f.make("bad"+str(i),bindings=b))
    def test_packaged_candidate_exactly_one_change(self):
        root=Path(__file__).resolve().parents[3]
        old=registry_bindings()
        new=registry_bindings(root/"docs/implementation/wsf-07a-registry-candidate.json")
        self.assertEqual([k for k in old if old[k]!=new[k]],["PORT-007"])
        self.assertEqual(sum(bool(v["path"]) for v in new.values()),8)
        source=self.f.make("packaged-old",bindings=old);source.initialize(self.f.a)
        target=self.f.make("packaged-new",bindings=new)
        raw,d=preview_resolved_bindings(self.f.a,source,target)
        target.restore_empty(self.f.a,raw)
        self.assertTrue(d["history_preserved"])
