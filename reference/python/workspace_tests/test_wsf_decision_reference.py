import unittest,json
from datetime import timedelta
from unittest.mock import patch
import test_wsf_procurement_reference as fixture
import p7_04_persistent_access as p704
from workspace_app.wsf_manual_context import _identity,_json,ManualContextError
from workspace_app.wsf_decision_reference import DecisionReference,DRAFT,OPERATION,RESOURCE,IDS,sha,projection,read_snapshot
from wsf_manual_operator import write_new

class DecisionReferenceTests(unittest.TestCase):
    def setUp(self):
        f=fixture.ProcurementReferenceTests();f.setUp();self.addCleanup(f.doCleanups);self.f=f
        self.root=f.root;self.a=f.a;self.resolve=f.resolve
        self.runtime=DecisionReference(f.root,clock=lambda:f.now)
        base=f.base/"company";base.mkdir(mode=0o700);p=base/"decisions";p.mkdir(mode=0o700);self.runtime.source=p/"register.json"
        now=f.now.isoformat();due=f.notes.review_signal(f.a)["due_at"]
        rows=[]
        for i in range(1,4):
            rows.append({"id":f"DEC-{i:03d}","last_reviewed_at":now,"evidence_as_of":now,"decision_state":"preparing" if i==3 else "decided","decision_outcome":"none" if i==3 else "approve_with_conditions","accountable_position":"POS-001","decision_authority":"Owner","effect_readiness":"blocked" if i==3 else "not_applicable","decision_act_ref":None if i==3 else "fixture act","effective_at":None if i==3 else now,"scope_refs":["WORK-001"],"review_expiry_trigger":"До "+due,"title":"Fixture","decision_question":"Review","authority_basis":"fixture basis","constraints_excluded_effects":"No effect"})
        rows.append({"id":"APR-001","last_reviewed_at":now,"evidence_as_of":now,"approval_state":"approved","approval_domain":"arvectum_os","required_approver_capacity":"Owner","approval_act_ref":"fixture act","authoritative_source_ref":"fixture act","title":"Fixture","authority_basis":"fixture basis","approval_scope":"Fixture scope","conditions_excluded_effects":"No effect","effective_period":"Fixture term"})
        self.doc={"schema":"arvectum.company.decision-approval-escalation-register/1","coverage":"partial","events":[]}
        for r in rows:
            ev=self.doc["events"]
            ev.append({"sequence":len(ev)+1,"prior_digest":sha(_json(ev[-1])+b"\n") if ev else None,"at":now,"operator_ref":"fixture","reason":"fixture","concern_key":"fixture-"+r["id"],"record":r})
        raw=_json(self.doc);write_new(self.runtime.source,raw)
        self.g=p704.grant_access(f.root,f.a.actor,operation=OPERATION,resource=RESOURCE,access_paths=("local",))
        self.p={"schema":"arvectum.workspace.company-decision-policy/1","draft_blob":DRAFT,"scope":_identity(f.a),"credential_id":f.a.credential_id,"grant_id":self.g,"purpose":"owner-triggered-first-decision-reference-read","source_sha256":sha(raw),"record_ids":list(IDS),"starts_at":(f.now-timedelta(minutes=10)).isoformat(),"expires_at":(f.now+timedelta(minutes=10)).isoformat()}
    def admit(self):
        raw=_json(self.p);write_new(self.root/"config/company-decision-policy.json",raw)
        write_new(self.root/"config/company-decision-activation.json",_json({"schema":"arvectum.workspace.company-decision-activation/1","draft_blob":DRAFT,"policy_sha256":sha(raw)}))
    def test_exact_read_and_revoke(self):
        with self.assertRaises(ManualContextError):self.runtime.read(self.resolve)
        self.admit();before=read_snapshot(self.runtime.source);r=self.runtime.read(self.resolve)
        self.assertEqual([v["id"] for v in r["items"]],list(IDS))
        self.assertEqual(r["items"][2]["recorded_outcome"],"none")
        self.assertTrue(all(not v["decision_ready"] and v["current_applicability"]=="unknown" for v in r["items"]))
        self.assertEqual(before,read_snapshot(self.runtime.source))
        p704.revoke_grant(self.root,self.g)
        with self.assertRaises(ManualContextError):self.runtime.read(self.resolve)
    def test_changed_source(self):
        self.admit();self.runtime.source.write_bytes(read_snapshot(self.runtime.source)+b" ")
        with self.assertRaises(ManualContextError):self.runtime.read(self.resolve)
    def test_scope_and_expiry(self):
        self.p["scope"]={};self.admit()
        with self.assertRaises(ManualContextError):self.runtime.read(self.resolve)
    def test_expired(self):
        self.admit();self.f.now+=timedelta(hours=1)
        with self.assertRaises(ManualContextError):self.runtime.read(self.resolve)
    def test_revoke_during_read(self):
        self.admit()
        def revoked(path):
            raw=read_snapshot(path);p704.revoke_grant(self.root,self.g);return raw
        with patch("workspace_app.wsf_decision_reference.read_snapshot",side_effect=revoked):
            with self.assertRaises(ManualContextError):self.runtime.read(self.resolve)
    def test_wrong_pending_outcome(self):
        self.doc["events"][2]["record"]["decision_outcome"]="approve"
        with self.assertRaises(ManualContextError):projection(self.doc,self.f.notes.review_signal(self.a),self.f.now.isoformat())
