import copy,json,unittest
from unittest.mock import patch
import p7_04_persistent_access as p704
from workspace_app import wsf_local_control as local
from workspace_app.wsf_manual_context import ManualContextError,_json
from workspace_app.wsf_company_control_reference import sha
import test_wsf_decision_reference as d
import test_wsf_risk_reference as risk_fixture

def canonical(doc):return _json(doc)+b"\n"

def append(doc,row,key):
    result=copy.deepcopy(doc);events=result["events"]
    events.append({"sequence":len(events)+1,"prior_digest":sha(canonical(events[-1])),
         "at":events[-1]["at"],"operator_ref":"fixture","reason":"fixture","concern_key":key,"record":row})
    return result

class LocalTests(unittest.TestCase):
    def fixture(self,kind):
        f=(d.DecisionReferenceTests if kind=="decision" else risk_fixture.RiskReferenceTests)()
        f.setUp();self.addCleanup(f.doCleanups)
        for e in f.doc["events"]:
            r=e["record"]
            if kind=="risk":r["current_controls_refs"]=["fixture"]
            elif r["id"].startswith("DEC-"):
                r["evidence_refs"]=["fixture"];r["required_approval_refs"]=[]
        for i,e in enumerate(f.doc["events"]):
            if i:e["prior_digest"]=sha(canonical(f.doc["events"][i-1]))
        f.runtime.source.write_bytes(canonical(f.doc))
        f.p["source_sha256"]=sha(canonical(f.doc));f.admit()
        self.enterContext(patch.object(local,"enabled",return_value=True))
        return f
    def test_two_history_imports_and_no_new_effect(self):
        f=self.fixture("decision");doc=f.doc
        for rid in local.ACTS:
            ref="arvectum2/arvectum-company@"+local.COMPANY_COMMIT+":docs/governance/decisions/"+local.ACTS[rid]+".md"
            row={**f.doc["events"][2]["record"],"id":rid,"decision_state":"decided","decision_outcome":"approve_with_conditions",
                 "decision_act_ref":ref,"effective_at":"2026-11-20","evidence_refs":[ref]}
            doc=append(doc,row,"fixture-"+rid)
            raw=canonical(doc);f.runtime.source.write_bytes(raw)
            with patch.object(local,"backup_bytes",return_value=raw):
                result=f.runtime.read(f.resolve)
                self.assertEqual(result["items"][-1]["id"],rid);self.assertFalse(result["items"][-1]["decision_ready"])
        self.assertEqual(len(result["items"]),6)
    def test_risk_repeated_updates_and_scope_rejection(self):
        f=self.fixture("risk");doc=f.doc
        row=f.doc["events"][1]["record"]
        for text in ("first evidence","second evidence"):
            row={**row,"next_control_point":text}
            doc=append(doc,row,"fixture-RSK-002")
            raw=canonical(doc);f.runtime.source.write_bytes(raw)
            with patch.object(local,"backup_bytes",return_value=raw):
                self.assertEqual(f.runtime.read(f.resolve)["items"][1]["next_control_point"],text)
        for changed in ({"risk_acceptance_decision_ref":"DEC-001"},{"company_priority":{"level":"P0"}},{"source_refs":[]},{"closure_ref":"fake"}):
            raw=canonical(append(doc,{**row,**changed},"fixture-RSK-002"))
            f.runtime.source.write_bytes(raw)
            with patch.object(local,"backup_bytes",return_value=raw),self.assertRaises(ManualContextError):
                f.runtime.read(f.resolve)
    def test_backup_mismatch_baseline_tamper_revocation(self):
        f=self.fixture("risk");old=canonical(f.doc)
        with patch.object(local,"backup_bytes",return_value=b"wrong"),self.assertRaises(ManualContextError):f.runtime.read(f.resolve)
        doc=copy.deepcopy(f.doc);doc["events"][0]["record"]["title"]="changed"
        raw=canonical(doc);f.runtime.source.write_bytes(raw)
        with patch.object(local,"backup_bytes",return_value=raw),self.assertRaises(ManualContextError):f.runtime.read(f.resolve)
        f.runtime.source.write_bytes(old);p704.revoke_grant(f.root,f.g)
        with patch.object(local,"backup_bytes",return_value=old),self.assertRaises(ManualContextError):f.runtime.read(f.resolve)

class ReceiptTests(unittest.TestCase):
    def test_published_receipt_required(self):
        import tempfile
        from pathlib import Path
        from wsf_manual_operator import write_new
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();(root/"config").mkdir(mode=0o700)
            self.assertFalse(local.enabled(root))
            path=root/"config/ac402-403-local-activation.json"
            write_new(path,_json({"schema":"arvectum.workspace.local-control-activation/1","publication":local.PUBLICATION,"owner_act":"edc59e48b1788859e275907d3d6749b7a88e1da6"}))
            self.assertTrue(local.enabled(root))
            path.write_bytes(b"{}")
            with self.assertRaises(ManualContextError):local.enabled(root)
