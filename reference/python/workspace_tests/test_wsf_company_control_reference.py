import json, unittest
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
import test_wsf_procurement_reference as existing
import p7_04_persistent_access as p704
from workspace_app.wsf_manual_context import _identity,_json,ManualContextError
from workspace_app.wsf_company_control_reference import CompanyControlReference,DRAFT,OPERATION,RESOURCE,BINDINGS,sha
from wsf_manual_operator import write_new

class CompanyControlTests(unittest.TestCase):
    def setUp(self):
        self.fixture=existing.ProcurementReferenceTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f=self.fixture
        self.root=f.root;self.a=f.a;self.resolve=f.resolve
        self.runtime=CompanyControlReference(self.root,clock=lambda:f.now)
        base=f.base/"company";base.mkdir(mode=0o700)
        directory=base/"register";directory.mkdir(mode=0o700)
        self.runtime.source=directory/"register.json"
        self.grant=p704.grant_access(self.root,self.a.actor,operation=OPERATION,resource=RESOURCE,access_paths=("local",))
        due=f.notes.review_signal(self.a)["due_at"]
        self.row={"id":"WORK-001","kind":"work","concern_key":"workspace-pilot-continuation-review-2026-12","accountable_position":"POS-001","title":"Fixture review","control_state":"open","due_or_trigger":{"kind":"exact","value":due,"source_ref":"fixture"},"scope_refs":["fixture"],"source_refs":["fixture"],"evidence_as_of":f.now.isoformat(),"company_priority":{"level":"P1"},"next_control_point":"review"}
        self.doc={"schema":"arvectum.company.work-obligation-register/1","coverage":"partial","events":[{"sequence":1,"prior_digest":None,"at":f.now.isoformat(),"authority_ref":"fixture","reason":"fixture","record":self.row}]}
        for idx in (1,2):
            r={**self.row,"id":"OBL-%03d"%idx,"kind":"obligation","accountable_position":"POS-002","concern_key":"fixture-contract-"+str(idx),"due_or_trigger":{"kind":"condition","value":"Fixture contractual condition","source_ref":"fixture"},"obligation_class":"customer","satisfaction_evidence_ref":None,"closure_ref":None,"company_priority":{"level":"P0"}}
            events=self.doc["events"]
            events.append({"sequence":len(events)+1,"prior_digest":sha(_json(events[-1])+b"\n"),"at":f.now.isoformat(),"authority_ref":"fixture","reason":"fixture","record":r})
        raw=_json(self.doc);write_new(self.runtime.source,raw)
        self.policy={"schema":"arvectum.workspace.company-control-policy/1","draft_blob":DRAFT,"scope":_identity(self.a),"credential_id":self.a.credential_id,"grant_id":self.grant,"purpose":"owner-triggered-first-company-control-read","source_sha256":sha(raw),"records":BINDINGS,"starts_at":(f.now-timedelta(minutes=10)).isoformat(),"expires_at":(f.now+timedelta(minutes=10)).isoformat()}
    def admit(self):
        raw=_json(self.policy)
        write_new(self.root/"config/company-control-policy.json",raw)
        write_new(self.root/"config/company-control-activation.json",_json({"schema":"arvectum.workspace.company-control-activation/1","draft_blob":DRAFT,"policy_sha256":sha(raw)}))
    def test_default_denied_then_exact_read_and_revocation(self):
        with self.assertRaises(ManualContextError):self.runtime.read(self.resolve)
        self.admit()
        before=self.runtime.source.read_bytes()
        out=self.runtime.read(self.resolve)
        self.assertEqual(out["owner_action"][0]["id"],"WORK-001")
        self.assertFalse(out["owner_action"][0]["decision_ready"])
        self.assertEqual({x["id"] for x in out["obligation_signals"]},{"OBL-001","OBL-002"})
        self.assertEqual(len(out["owner_action"]),1)
        self.assertTrue(all(not x["decision_ready"] and x["freshness"]=="unknown" for x in out["obligation_signals"]))
        self.assertEqual(out["coverage"],"partial")
        self.assertEqual(self.runtime.source.read_bytes(),before)
        p704.revoke_grant(self.root,self.grant)
        with self.assertRaises(ManualContextError):self.runtime.read(self.resolve)
    def test_source_changed(self):
        self.admit()
        self.runtime.source.write_bytes(self.runtime.source.read_bytes()+b" ")
        with self.assertRaises(ManualContextError):self.runtime.read(self.resolve)
    def test_wrong_scope(self):
        self.policy["scope"]={}
        self.admit()
        with self.assertRaises(ManualContextError):self.runtime.read(self.resolve)
    def test_expired(self):
        self.admit()
        self.fixture.now+=timedelta(hours=1)
        with self.assertRaises(ManualContextError):self.runtime.read(self.resolve)
    def test_revoked_during_read(self):
        self.admit()
        from workspace_app.wsf_company_control_reference import read_snapshot
        def read(path):
            raw=read_snapshot(path)
            p704.revoke_grant(self.root,self.grant)
            return raw
        with patch("workspace_app.wsf_company_control_reference.read_snapshot",side_effect=read):
            with self.assertRaises(ManualContextError):self.runtime.read(self.resolve)
