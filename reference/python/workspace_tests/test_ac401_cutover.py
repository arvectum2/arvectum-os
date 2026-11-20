import copy,json,unittest
from dataclasses import replace
from datetime import timedelta
import p7_04_persistent_access as p704
import test_wsf_company_control_reference as existing
from workspace_app.wsf_company_control_reference import sha
from workspace_app.wsf_company_control_successor import first_successor
from workspace_app.wsf_manual_context import ManualContextError,_json
from ac401_cutover_fixture import CutoverFixture,atomic_replace
from workspace_app.wsf_company_control_cutover import STEPS

DECISION="OWNER-SYNTHETIC-AC401-REVISION"
CONTRACT="f"*40

def make_case(test):
    b=existing.CompanyControlTests()
    b.setUp();test.addCleanup(b.doCleanups)
    d=copy.deepcopy(b.doc)
    for e in d["events"]:
        r=e["record"]
        r.update(control_summary="Synthetic",attention_state="normal",
          classification_handling="fixture-only",last_reviewed_at=r["evidence_as_of"],
          escalation_need=None,closure_ref=None)
        r["company_priority"]["why_now"]="Synthetic review"
        if r["kind"]=="work":
            r.update(bounded_outcome="Fixture review",completion_or_stop_condition="Fixture decision",execution_refs=["fixture"])
        else:
            r.update(authoritative_obligation_ref="fixture",satisfaction_condition="Fixture acceptance")
    for n,e in enumerate(d["events"]):
        e["prior_digest"]=sha(_json(d["events"][n-1])+b"\n") if n else None
    old=_json(d)+b"\n"
    atomic_replace(b.runtime.source,old);b.policy["source_sha256"]=sha(old);b.admit()
    cand=copy.deepcopy(d);r=copy.deepcopy(d["events"][0]["record"])
    r.update(attention_state="needs_attention",next_control_point="Verify actual use")
    r["source_refs"].append("synthetic new observation")
    cand["events"].append({"sequence":4,"prior_digest":sha(_json(d["events"][-1])+b"\n"),
        "at":b.fixture.now.isoformat(),"authority_ref":DECISION,"reason":"Synthetic revision","record":r})
    new=_json(cand)+b"\n"
    return CutoverFixture(b,old,new,DECISION,CONTRACT)

class CutoverTests(unittest.TestCase):
    def test_complete_idempotent_and_preserve_obligations(self):
        c=make_case(self)
        earlier=c.runtime.read(c.base.resolve)
        with self.assertRaises(ManualContextError):c.project(c.plan)
        self.assertEqual(c.run(),"completed")
        later=c.project(c.plan)
        self.assertEqual(earlier["obligation_signals"],later["obligation_signals"])
        self.assertEqual(later["owner_action"][0]["next_control_point"],"Verify actual use")
        self.assertFalse(later["owner_action"][0]["decision_ready"])
        self.assertEqual(c.source.read_bytes(),c.backup.read_bytes())
        self.assertEqual(c.writes,list(STEPS));self.assertEqual(c.run(),"already-completed")
        self.assertEqual(c.writes,list(STEPS))
        with self.assertRaises(ManualContextError):c.runtime.read(c.base.resolve)
    def test_interruption_before_and_after_every_write(self):
        for step in STEPS:
            for when in ("before","after"):
                with self.subTest(step=step,when=when):
                    c=make_case(self);c.failure=when+"-"+step
                    with self.assertRaises(OSError):c.run()
                    self.assertIsNotNone(c.read_journal())
                    with self.assertRaises(ManualContextError):c.project(c.plan)
                    before=c.source.read_bytes()
                    c.failure=None;self.assertEqual(c.run(),"completed")
                    self.assertEqual(c.source.read_bytes(),c.new)
                    self.assertIn(before,(c.old,c.new))
                    self.assertEqual(c.writes,list(STEPS))
                    self.assertIsNone(c.read_journal())
    def test_wrong_approval_backup_and_quiescence(self):
        c=make_case(self)
        for plan in (replace(c.plan,decision="OWNER-WRONG"),replace(c.plan,successor="b"*64)):
            with self.assertRaises(ManualContextError):c.run(plan)
        c.quiescent=False
        with self.assertRaises(ManualContextError):c.run()
        c.quiescent=True;atomic_replace(c.backup,b"bad")
        with self.assertRaises(ManualContextError):c.run()
        self.assertEqual(c.source.read_bytes(),c.old);self.assertEqual(c.writes,[])
        self.assertIsNone(c.read_journal())
    def test_backup_failure_revoked_grant_cannot_resume(self):
        c=make_case(self);c.failure="before-backup"
        with self.assertRaises(OSError):c.run()
        self.assertEqual(c.source.read_bytes(),c.new);self.assertEqual(c.backup.read_bytes(),c.old)
        p704.revoke_grant(c.base.root,c.base.grant)
        c.failure=None
        with self.assertRaises(ManualContextError):c.run()
        self.assertEqual(c.writes,["source"])
        self.assertIsNotNone(c.read_journal())
    def test_missing_or_changed_journal_denies_resume(self):
        for missing in (True,False):
            c=make_case(self);c.failure="after-source"
            with self.assertRaises(OSError):c.run()
            if missing:c.journal.unlink()
            else:atomic_replace(c.journal,b"{}")
            c.failure=None
            with self.assertRaises(ManualContextError):c.run()
            self.assertEqual(c.source.read_bytes(),c.new);self.assertEqual(c.writes,["source"])
    def test_out_of_order_partial_state_denied(self):
        c=make_case(self);atomic_replace(c.backup,c.new)
        with self.assertRaises(ManualContextError):c.run()
        self.assertEqual(c.source.read_bytes(),c.old)
    def test_completed_admission_denies_tamper_and_expiry(self):
        c=make_case(self);c.run()
        atomic_replace(c.receipt,b"{}")
        with self.assertRaises(ManualContextError):c.project(c.plan)
        atomic_replace(c.receipt,c.receipt_bytes)
        c.base.fixture.now+=timedelta(hours=1)
        with self.assertRaises(ManualContextError):c.project(c.plan)
    def test_candidate_shape_rejects_more_than_reviewed_checkpoint(self):
        c=make_case(self);_,_,review=c.runtime.gate(c.base.resolve())
        for key,value in (("control_state","waiting"),("accountable_position","POS-002"),
            ("due_or_trigger",{"kind":"none","value":None,"source_ref":None}),("source_refs",["unreviewed"]),
            ("attention_state","escalated")):
            d=json.loads(c.new);d["events"][-1]["record"][key]=value;raw=_json(d)+b"\n"
            with self.subTest(key=key),self.assertRaises(ManualContextError):
                first_successor(c.old,raw,review=review,now=c.runtime.clock().isoformat(),
                    expected_old=sha(c.old),expected_new=sha(raw),decision=DECISION)
    def test_invalid_plan_digests_and_identical_source_refused(self):
        c=make_case(self)
        for updates in ({"successor":c.plan.predecessor},{"contract":"invalid"},{"receipt":"x"*64},{"decision":"proposal"}):
            with self.subTest(updates=updates),self.assertRaises(ManualContextError):
                replace(c.plan,**updates)
        self.assertEqual(c.source.read_bytes(),c.old)
        self.assertIsNone(c.read_journal())
