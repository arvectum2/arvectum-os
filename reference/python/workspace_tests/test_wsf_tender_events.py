import copy,hashlib,json,unittest
from test_wsf_manual_context import access
from workspace_app.wsf_manual_context import ManualContextError,_identity
from workspace_app.wsf_tender_events import normalize,review_groups

class TenderEventTests(unittest.TestCase):
    def setUp(self):
        self.a=access();self.scope=_identity(self.a);self.tenant="synthetic-company"
        self.mapping={"source-project":"PRJ-"+"a"*32}
        self.now="2026-11-17T10:00:00Z"
    def row(self,kind="analysis_completed"):
        aggregate_type,aggregate=("analysis_run","run-1") if kind=="analysis_completed" else ("procurement_case","case-1")
        key=hashlib.sha256(json.dumps([kind,aggregate_type,aggregate,"run-1"],ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
        common={"event_key":key,"event_type":kind,"tenant_id":self.tenant,"aggregate_type":aggregate_type,"aggregate_id":aggregate}
        data={"project_id":"source-project","case_id":"case-1","status":"completed"} if kind=="analysis_completed" else {"project_id":"source-project","run_id":"run-1","reason":"analysis_completed_operator_review"}
        return {"id":kind+"-1",**common,"created_at":"2026-11-17T09:01:00Z","envelope":{"schema_version":"integration-event-v1",**common,"occurred_at":"2026-11-17T09:00:00Z","data":data}}
    def norm(self,rows,**kw):
        return normalize(self.a,rows,**{"scope":self.scope,"tenant":self.tenant,"binding_id":"fixture","project_map":self.mapping,"now":self.now,**kw})
    def test_pair_and_duplicates(self):
        a,b=self.row(),self.row("review_required")
        rows=self.norm([a,b,a])
        self.assertEqual(len(rows),2)
        grouped=review_groups(rows)
        self.assertEqual(len(grouped["groups"]),1)
        self.assertTrue(grouped["groups"][0]["review_signal"])
        self.assertEqual(grouped["groups"][0]["owner_action"],"unknown")
        self.assertFalse(grouped["organizational_authority_provided"])
    def test_empty_is_partial(self):
        self.assertEqual(review_groups(self.norm([]))["coverage"],"partial")
    def test_unscoped_and_cross_tenant_fail_entire_batch(self):
        a=self.row()
        for t in (None,"other"):
            b=copy.deepcopy(a);b["tenant_id"]=t;b["envelope"]["tenant_id"]=t
            with self.assertRaises(ManualContextError):self.norm([a,b])
        with self.assertRaises(ManualContextError):self.norm([a],scope=_identity(access(org="other")))
    def test_mismatch_or_unknown_mapping(self):
        a=self.row()
        with self.assertRaises(ManualContextError):self.norm([a],project_map={})
        b=copy.deepcopy(a);b["envelope"]["aggregate_id"]="different"
        with self.assertRaises(ManualContextError):self.norm([b])
    def test_other_event_types_and_payload_fields_denied(self):
        a=self.row();a["event_type"]="monitoring_alert";a["envelope"]["event_type"]="monitoring_alert"
        with self.assertRaises(ManualContextError):self.norm([a])
        a=self.row();a["envelope"]["data"]["message"]="Sensitive data"
        with self.assertRaises(ManualContextError):self.norm([a])
    def test_event_conflict_and_producer_key(self):
        a=self.row();b=copy.deepcopy(a);b["id"]="other"
        with self.assertRaises(ManualContextError):self.norm([a,b])
        a["event_key"]=a["envelope"]["event_key"]="0"*64
        with self.assertRaises(ManualContextError):self.norm([a])
    def test_outcome_not_inferred_and_time_bound(self):
        a=self.row();a["envelope"]["data"]["status"]="failed"
        with self.assertRaises(ManualContextError):self.norm([a])
        a=self.row();a["created_at"]="2026-11-18T10:00:00Z"
        with self.assertRaises(ManualContextError):self.norm([a])
    def test_no_mutation_and_bounded_batch(self):
        a=self.row();before=copy.deepcopy(a);self.norm([a]);self.assertEqual(a,before)
        with self.assertRaises(ManualContextError):self.norm([a]*101)
