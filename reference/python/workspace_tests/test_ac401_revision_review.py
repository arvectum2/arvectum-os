import copy,json,unittest
from workspace_app.wsf_manual_context import ManualContextError,_json
from workspace_app.wsf_company_control_reference import sha,BINDINGS
from ac401_revision_review import review
NOW="2026-11-20T07:00:00+00:00"
def append(doc,r):
    events=doc["events"]
    events.append({"sequence":len(events)+1,"prior_digest":sha(_json(events[-1])+b"\n") if events else None,
        "at":NOW,"authority_ref":"synthetic","reason":"synthetic review","record":copy.deepcopy(r)})
def fixture():
    d={"schema":"arvectum.company.work-obligation-register/1","coverage":"partial","events":[]}
    for rid,pos in BINDINGS.items():
        append(d,{"id":rid,"kind":"work" if rid.startswith("WORK") else "obligation","concern_key":"fixture-"+rid,
            "accountable_position":pos,"title":"Fixture","control_state":"open","attention_state":"normal",
            "next_control_point":"Review source","last_reviewed_at":NOW,"evidence_as_of":NOW,
            "due_or_trigger":{"kind":"condition","value":"Fixture condition","source_ref":"fixture"},
            "source_refs":["fixture"],"escalation_need":None,"closure_ref":None})
    return d
class RevisionReviewTests(unittest.TestCase):
    def setUp(self):
        self.old=fixture();self.new=copy.deepcopy(self.old)
        self.r=copy.deepcopy(self.old["events"][1]["record"])
        self.r.update(control_state="waiting",attention_state="needs_attention",next_control_point="Check external response")
    def result(self):return review(_json(self.old),_json(self.new),now=NOW)
    def test_exact_append(self):
        append(self.new,self.r);v=self.result()
        self.assertEqual(v["candidate_events"],4)
        self.assertEqual(v["changes"][0]["id"],"OBL-001")
        self.assertFalse(v["activation_permitted"]);self.assertFalse(v["authority_provided"])
    def test_in_place_history_change(self):
        self.new["events"][0]["reason"]="rewritten";append(self.new,self.r)
        with self.assertRaises(ManualContextError):self.result()
    def test_duplicate_concern_new_identity(self):
        self.r["id"]="OBL-003";append(self.new,self.r)
        with self.assertRaises(ManualContextError):self.result()
    def test_changed_position_due_or_closure(self):
        for k,v in (("accountable_position","POS-003"),("due_or_trigger",{"kind":"none","value":None,"source_ref":None}),("control_state","closed"),("closure_ref","fiction")):
            self.new=copy.deepcopy(self.old);r={**self.r,k:v};append(self.new,r)
            with self.subTest(k=k),self.assertRaises(ManualContextError):self.result()
    def test_intermediate_unauthorized_change(self):
        append(self.new,{**self.r,"accountable_position":"POS-003"});append(self.new,self.r)
        with self.assertRaises(ManualContextError):self.result()
    def test_noop_and_escalation(self):
        append(self.new,self.old["events"][1]["record"])
        with self.assertRaises(ManualContextError):self.result()
        self.new=copy.deepcopy(self.old);append(self.new,{**self.r,"attention_state":"escalated"})
        with self.assertRaises(ManualContextError):self.result()
    def test_future_review_and_broken_chain(self):
        append(self.new,self.r);self.new["events"][-1]["prior_digest"]="0"*64
        with self.assertRaises(ManualContextError):self.result()
        self.new=copy.deepcopy(self.old);append(self.new,{**self.r,"evidence_as_of":"2026-12-01T00:00:00+00:00"})
        with self.assertRaises(ManualContextError):self.result()
