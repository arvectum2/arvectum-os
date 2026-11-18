import unittest,json
from datetime import timedelta
from unittest.mock import patch
import test_wsf_procurement_reference as fixture
import p7_04_persistent_access as p704
from workspace_app.wsf_manual_context import _identity,_json,ManualContextError
from workspace_app.wsf_finance_reference import FinanceReference,DRAFT,OPERATION,RESOURCE,IDS,UNKNOWN_FIELDS,sha,projection,read_snapshot
from wsf_manual_operator import write_new

class FinanceReferenceTests(unittest.TestCase):
    def setUp(self):
        f=fixture.ProcurementReferenceTests();f.setUp();self.addCleanup(f.doCleanups);self.f=f
        self.root=f.root;self.a=f.a;self.resolve=f.resolve
        self.runtime=FinanceReference(f.root,clock=lambda:f.now)
        base=f.base/"company";base.mkdir(mode=0o700);p=base/"finance";p.mkdir(mode=0o700);self.runtime.source=p/"initial.private.json"
        now=f.now.isoformat();due=f.notes.review_signal(f.a)["due_at"]
        v={"basis":"contractual_conditional","contract_price_rub":"123.45","expected_available_cash_rub":None,"receivable_confirmed":False,"actual_receipt_confirmed":False,"advance_provided":False,"timing_condition":"after fixture acceptance","source_refs":["fixture contract"],"linked_obligations":["OBL-001","OBL-002"],"as_of":now}
        self.doc={**{k:{"status":"unknown","value":None} for k in UNKNOWN_FIELDS},"schema":"arvectum.company.management-finance-report/1","report_as_of":now,"coverage":"partial","source_freshness":{"bank":"unknown","accounting":"unknown","contract_terms":"verified_archived_terms","performance_acceptance":"unknown"},"liquidity_status":"unknown","expected_inflows":[v],"portfolio_project_economic_signals":[{"source_refs":v["source_refs"],"linked_obligations":v["linked_obligations"],"costs":"unknown","margin":"unknown"}],"risk_exception_incident_refs":["RSK-003"],"decision_approval_escalation_refs":[],"unknowns_and_gaps":["fixture gaps"],"next_control_point":"Review sources","accountable_position":"POS-005","decision_readiness":"blocked_by_missing_financial_evidence","derived":True,"canonical_authority":False,"payment_authority":False}
        raw=_json(self.doc);write_new(self.runtime.source,raw)
        self.g=p704.grant_access(f.root,f.a.actor,operation=OPERATION,resource=RESOURCE,access_paths=("local",))
        self.p={"schema":"arvectum.workspace.company-finance-policy/1","draft_blob":DRAFT,"scope":_identity(f.a),"credential_id":f.a.credential_id,"grant_id":self.g,"purpose":"owner-triggered-first-finance-reference-read","source_sha256":sha(raw),"record_ids":list(IDS),"starts_at":(f.now-timedelta(minutes=10)).isoformat(),"expires_at":(f.now+timedelta(minutes=10)).isoformat()}
    def admit(self):
        raw=_json(self.p);write_new(self.root/"config/company-finance-policy.json",raw)
        write_new(self.root/"config/company-finance-activation.json",_json({"schema":"arvectum.workspace.company-finance-activation/1","draft_blob":DRAFT,"policy_sha256":sha(raw)}))
    def test_exact_read_and_revoke(self):
        with self.assertRaises(ManualContextError):self.runtime.read(self.resolve)
        self.admit();before=read_snapshot(self.runtime.source);r=self.runtime.read(self.resolve)
        self.assertEqual(r["conditional_inflow"]["contract_price_rub"],"123.45")
        self.assertIsNone(r["conditional_inflow"]["expected_available_cash_rub"])
        self.assertFalse(r["payment_authority"])
        self.assertTrue(all(v["value"] is None for v in r["facts"].values()))
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
        with patch("workspace_app.wsf_finance_reference.read_snapshot",side_effect=revoked):
            with self.assertRaises(ManualContextError):self.runtime.read(self.resolve)
    def test_no_false_financial_facts(self):
        import copy
        for key in UNKNOWN_FIELDS:
            doc=copy.deepcopy(self.doc);doc[key]={"status":"current","value":0}
            with self.assertRaises(ManualContextError):projection(doc,self.f.notes.review_signal(self.a),self.f.now.isoformat())
        for key,value in (("actual_receipt_confirmed",True),("receivable_confirmed",True),("expected_available_cash_rub","123.45")):
            doc=copy.deepcopy(self.doc);doc["expected_inflows"][0][key]=value
            with self.assertRaises(ManualContextError):projection(doc,self.f.notes.review_signal(self.a),self.f.now.isoformat())
        doc=copy.deepcopy(self.doc);doc["payment_authority"]=True
        with self.assertRaises(ManualContextError):projection(doc,self.f.notes.review_signal(self.a),self.f.now.isoformat())
