from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from test_wsf_manual_context import access
from workspace_app.wsf_manual_context import ManualContextError
from workspace_app.wsf_crm import CRMStore


class CRMTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.a=access();self.p="PRJ-"+uuid4().hex;self.q="PRJ-"+uuid4().hex
        self.refs={"fixture:registry","fixture:channel","fixture:contract","fixture:meeting","fixture:email","fixture:other"}
        self.crm=self.make("crm");self.crm.initialize(self.a)

    def make(self,name):
        return CRMStore(self.root/name,self.a,project_ids={self.p,self.q},evidence_refs=self.refs)

    def submit(self,kind,data,**kw):
        return self.crm.submit(self.a,kw.pop("key",uuid4().hex),kind,data,**kw)

    def party(self,name="Synthetic Company",ref="fixture:registry"):
        return self.submit("party",{"name":name,"registry_ref":ref,"description":"Synthetic counterparty"})

    def contact(self,p,name="Synthetic Person"):
        return self.submit("contact",{"party_id":p["id"],"name":name,"role":"Synthetic role","channel_ref":"fixture:channel"})

    def opportunity(self,p,c=None,**kw):
        return self.submit("opportunity",{"party_id":p["id"],"contact_id":c["id"] if c else None,
                    "title":"Fixture opportunity","stage":"discovery","next_action":"Review proposal",
                    "next_contact_at":"2026-12-01T10:00:00+00:00","project_id":self.p,
                    "evidence_refs":["fixture:contract"],"outcome_ref":None,**kw})

    def interaction(self,p,c,o,**kw):
        return self.submit("interaction",{"party_id":p["id"],"contact_id":c["id"],"opportunity_id":o["id"],
                   "project_id":self.p,"kind":"meeting","occurred_at":"2026-01-01T10:00:00+00:00",
                   "summary":"Synthetic meeting","evidence_ref":"fixture:meeting",**kw})

    def fields(self,row):
        return {k:v for k,v in row.items() if k not in {"id","revision","recorded_at","authority_provided"}}

    def test_full_workflow_persistence_search_and_timeline(self):
        p=self.party();c=self.contact(p);o=self.opportunity(p,c);i=self.interaction(p,c,o)
        self.crm=self.make("crm")
        d=self.crm.read(self.a,project_id=self.p)
        self.assertEqual([len(v) for v in d.values()],[1,1,1,1])
        self.assertEqual(self.crm.read(self.a,query="synthetic company")["party"],[p])
        self.assertEqual(self.crm.timeline(self.a,p["id"]),[i])
        self.assertFalse(o["authority_provided"])

    def test_edit_cas_and_idempotency(self):
        data={"name":"Fixture","registry_ref":None,"description":"Observation"}
        k=uuid4().hex;p=self.submit("party",data,key=k)
        self.assertEqual(self.submit("party",data,key=k),p)
        with self.assertRaises(ManualContextError):self.submit("party",{**data,"name":"Other"},key=k)
        r=self.submit("party",{**data,"description":"Updated"},record_id=p["id"],expected_revision=1)
        self.assertEqual(r["revision"],2)
        self.assertEqual(self.crm.history(self.a,p["id"]),[p,r])
        with self.assertRaises(ManualContextError):self.submit("party",data,record_id=p["id"],expected_revision=1)

    def test_duplicate_names_and_registry_references(self):
        self.party()
        for name,ref in (("  SYNTHETIC  COMPANY ",None),("Other","fixture:registry")):
            with self.assertRaises(ManualContextError):self.party(name,ref)
        p=self.crm.read(self.a)["party"][0]
        with self.assertRaises(ManualContextError):self.submit("party",{**self.fields(p),"registry_ref":None},record_id=p["id"],expected_revision=1)
        self.contact(p)
        with self.assertRaises(ManualContextError):self.contact(p,"SYNTHETIC PERSON")

    def test_project_evidence_and_party_contact_integrity(self):
        p=self.party();q=self.party("Other",None);c=self.contact(p)
        for kw in ({"project_id":"PRJ-"+uuid4().hex},{"evidence_refs":["unadmitted"]}):
            with self.assertRaises(ManualContextError):self.opportunity(p,c,**kw)
        with self.assertRaises(ManualContextError):self.opportunity(q,c)
        o=self.opportunity(p,c)
        with self.assertRaises(ManualContextError):self.interaction(p,c,o,project_id=self.q)

    def test_stage_outcome_and_followup_separation(self):
        p=self.party();c=self.contact(p);o=self.opportunity(p,c)
        for patch in ({"stage":"won"},{"stage":"lost","outcome_ref":"fixture:contract"}):
            with self.assertRaises(ManualContextError):
                self.submit("opportunity",{**self.fields(o),**patch},record_id=o["id"],expected_revision=1)
        won=self.submit("opportunity",{**self.fields(o),"stage":"won","outcome_ref":"fixture:contract",
                       "next_action":None,"next_contact_at":None},record_id=o["id"],expected_revision=1)
        self.assertFalse(won["authority_provided"])
        with self.assertRaises(ManualContextError):
            self.submit("opportunity",self.fields(o),record_id=o["id"],expected_revision=2)

    def test_interaction_dedup_and_immutable_source(self):
        p=self.party();c=self.contact(p);o=self.opportunity(p,c);i=self.interaction(p,c,o)
        with self.assertRaises(ManualContextError):self.interaction(p,c,o)
        with self.assertRaises(ManualContextError):
            self.submit("interaction",{**self.fields(i),"evidence_ref":"fixture:email"},record_id=i["id"],expected_revision=1)

    def test_project_filter_excludes_unrelated_contacts(self):
        p=self.party();c=self.contact(p);self.contact(p,"Unrelated");self.opportunity(p,c)
        self.assertEqual(self.crm.read(self.a,project_id=self.p)["contact"],[c])
        self.assertEqual(self.crm.read(self.a,project_id=self.q)["party"],[])

    def test_export_restore_and_wrong_scope(self):
        self.party();raw=self.crm.export(self.a);r=self.make("restore");r.restore_empty(self.a,raw)
        self.assertEqual(r.export(self.a),raw)
        with self.assertRaises(ManualContextError):r.restore_empty(self.a,raw)
        for a in (access(actor="foreign"),access(org="foreign"),access(kind="ai")):
            with self.assertRaises(ManualContextError):r.read(a)
            with self.assertRaises(ManualContextError):r.export(a)

    def test_corruption_and_missing_store_fail_closed(self):
        self.party();self.crm.path.write_bytes(b"broken")
        with self.assertRaises(ManualContextError):self.crm.read(self.a)
        self.assertEqual(self.crm.path.read_bytes(),b"broken")
        self.crm.path.unlink()
        with self.assertRaises(ManualContextError):self.crm.read(self.a)
        self.assertFalse(self.crm.path.exists())

    def test_rights_removed_and_private_file_mode(self):
        self.party();self.assertEqual(self.crm.path.stat().st_mode&0o777,0o600)
        self.refs.remove("fixture:registry");self.crm=self.make("crm")
        with self.assertRaises(ManualContextError):self.crm.read(self.a)

    def test_invalid_input_future_interaction_and_no_mutation(self):
        p=self.party();c=self.contact(p);o=self.opportunity(p,c)
        raw=self.crm.export(self.a)
        for kw in ({"occurred_at":"2099-01-01T00:00:00+00:00"},{"kind":[]},{"summary":""}):
            with self.assertRaises(ManualContextError):self.interaction(p,c,o,**kw)
        self.assertEqual(self.crm.export(self.a),raw)
