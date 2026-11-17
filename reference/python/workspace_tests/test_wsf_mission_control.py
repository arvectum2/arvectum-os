from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from test_wsf_manual_context import access
from workspace_app.wsf_manual_context import ManualContextError, ManualContextStore
from workspace_app.wsf_mission_control import mission_control_baseline, project_timeline


class MissionControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.a=access()
        self.store=ManualContextStore(Path(self.tmp.name).resolve()/"fixture",self.a)

    def submit(self,op,payload):
        return self.store.submit(self.a,uuid4().hex,op,payload)

    def project(self,name):
        return self.submit("project",{"label":name,"kind":"customer"})["id"]

    def capture(self,pid,title="Fixture"):
        return self.submit("capture",{"title":title,"text":"Observation","project_id":pid})

    def revise(self,n,pid,title):
        return self.submit("revise",{"note_id":n["id"],"expected_revision":n["revision"],
                                    "title":title,"text":"New working note","project_id":pid})

    def test_timeline_includes_creation_capture_revision(self):
        p=self.project("Synthetic")
        n=self.capture(p)
        r=self.revise(n,p,"Corrected")
        result=project_timeline(self.store,self.a,p)
        self.assertEqual([e["kind"] for e in result["events"]],["project-created","note-captured","note-revised"])
        self.assertEqual(result["current_notes"],[r])
        self.assertEqual(result["events"][1]["revision"],1)
        self.assertEqual(result["events"][2]["revision"],2)
        self.assertFalse(result["canonical_authority"])

    def test_moves_and_unlink_preserve_history_without_new_project_content(self):
        p,q=self.project("One"),self.project("Two")
        n=self.capture(p,"Old association")
        r=self.revise(n,q,"Other project note")
        one=project_timeline(self.store,self.a,p)
        two=project_timeline(self.store,self.a,q)
        self.assertEqual(one["current_notes"],[])
        self.assertEqual(one["events"][-1]["kind"],"note-unlinked")
        self.assertEqual(one["events"][-1]["title"],"Old association")
        self.assertEqual(two["current_notes"],[r])
        self.assertEqual(two["events"][-1]["kind"],"note-linked")
        self.revise(r,None,"Unassigned")
        self.assertEqual(project_timeline(self.store,self.a,q)["current_notes"],[])

    def test_unrelated_notes_never_added(self):
        p,q=self.project("One"),self.project("Two")
        self.capture(q)
        self.capture(None)
        self.assertEqual(len(project_timeline(self.store,self.a,p)["events"]),1)

    def test_foreign_actor_organization_and_unknown_id_fail(self):
        p=self.project("Synthetic")
        for a in (access(actor="foreign"),access(org="foreign"),access(kind="ai")):
            with self.assertRaises(ManualContextError):
                project_timeline(self.store,a,p)
            with self.assertRaises(ManualContextError):
                mission_control_baseline(self.store,a)
        with self.assertRaises(ManualContextError):
            project_timeline(self.store,self.a,"PRJ-"+uuid4().hex)

    def test_notes_cannot_be_promoted_to_decisions_or_obligations(self):
        p=self.project("Synthetic")
        self.capture(p,"Urgent approval and payment requested")
        result=mission_control_baseline(self.store,self.a)
        self.assertEqual(len(result["manual_context"]["projects"]),1)
        self.assertEqual(len(result["manual_context"]["notes"]),1)
        self.assertFalse(result["manual_context"]["complete_company_coverage"])
        self.assertEqual(len(result["sections"]),6)
        self.assertTrue(all(s["state"]=="unknown" and not s["items"] and not s["decision_ready"] for s in result["sections"]))
        self.assertFalse(result["organizational_authority_provided"])

    def test_projection_never_mutates_ledger(self):
        p=self.project("Synthetic")
        self.capture(p)
        before=self.store.export(self.a)
        project_timeline(self.store,self.a,p)
        mission_control_baseline(self.store,self.a)
        self.assertEqual(self.store.export(self.a),before)
