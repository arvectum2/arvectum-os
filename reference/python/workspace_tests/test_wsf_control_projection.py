import copy
import unittest

from test_wsf_manual_context import access
from workspace_app.wsf_manual_context import ManualContextError, _identity
from workspace_app.wsf_control_projection import project_controls


class ControlProjectionTests(unittest.TestCase):
    def setUp(self):
        self.a=access()
        self.scope=_identity(self.a)
        self.now="2026-11-17T10:00:00+00:00"
        self.positions={"POS-001","POS-004"}
        self.card={"exact_question":"Choose option A or B","why_now":"Current material trigger",
                   "owner_capacity":"Owner","authority_basis":"fixture-owner-authority",
                   "current_recommendation":"Nonbinding option A from POS-004",
                   "options":["A","B"],"downside_reversibility":"Reversible fixture",
                   "evidence_refs":["fixture:evidence"],"known_unknowns":[],
                   "constraints_excluded_effects":"No external effect",
                   "requested_owner_act":"Choose exact option",
                   "effect_readiness":"Separate authorization required",
                   "execution_handoff":"POS-004 after separate gates",
                   "review_expiry":"2026-11-18T00:00:00+00:00"}

    def record(self,rid,**changes):
        return {"id":rid,"title":"Synthetic "+rid,"accountable_position":"POS-004",
                "scope_refs":["fixture:project"],"source_refs":["fixture:evidence"],
                "evidence_as_of":"2026-11-17T09:00:00+00:00",
                "freshness":"current_for_declared_use","review_condition":"Before material decision",
                "control_state":"open","priority":"P1","next_control_point":"Review progress",
                "due_or_trigger":{"kind":"none","value":None,"source_ref":None},
                "owner_action":"not_required","material_consequence":"Synthetic material impact",
                "substantive_unknowns":[],"decision_card":None,**changes}

    def projection(self,records=None,**kw):
        packet=None if records is None else {"scope":self.scope,"source_ref":"fixture:register",
                "as_of":"2026-11-17T09:30:00+00:00","coverage":"partial","records":records}
        return project_controls(self.a,packet,admitted_scope=self.scope,admitted_positions=self.positions,now=self.now,**kw)

    def test_unknown_is_not_empty_complete_register(self):
        self.assertEqual(self.projection()["coverage"],"unknown")
        self.assertEqual(self.projection([])["coverage"],"partial")

    def test_p0_protection_and_overdue_do_not_infer_owner_action(self):
        r=self.record("OBL-fixture",priority="P0",due_or_trigger={
            "kind":"exact","value":"2026-11-16T10:00:00+00:00","source_ref":"fixture:due"})
        d=self.projection([r])
        self.assertEqual(d["protect_now"][0]["id"],r["id"])
        self.assertEqual(d["obligation_signals"][0]["due_status"],"past_due")
        self.assertFalse(d["owner_action"])
        self.assertFalse(d["delegated_work"][0]["decision_ready"])

    def test_external_wait_separate_from_delegation_and_owner_queue(self):
        w=self.record("WORK-fixture",control_state="waiting",owner_action="waiting_external",
                      due_or_trigger={"kind":"condition","value":"External response","source_ref":"fixture:waiting"})
        d=self.projection([w,self.record("WORK-other")])
        self.assertEqual(len(d["waiting_external"]),1)
        self.assertEqual(len(d["delegated_work"]),1)
        self.assertFalse(d["owner_action"])

    def test_explicit_owner_decision_ready_without_approval(self):
        r=self.record("DEC-fixture",owner_action="required_now",decision_card=self.card)
        d=self.projection([r])
        self.assertTrue(d["owner_action"][0]["decision_ready"])
        self.assertFalse(d["organizational_authority_provided"])
        self.assertFalse(d["owner_action"][0]["canonical_authority"])

    def test_stale_conflicted_unknown_or_expired_never_ready(self):
        for state in ("stale_for_declared_use","unknown","conflicted"):
            r=self.record("DEC-fixture",freshness=state,owner_action="required_now",decision_card=self.card)
            d=self.projection([r])
            self.assertFalse(d["owner_action"][0]["decision_ready"])
            self.assertEqual(len(d["needs_reconciliation"]),1)
        card=copy.deepcopy(self.card);card["review_expiry"]=self.now
        self.assertFalse(self.projection([self.record("DEC-fixture",owner_action="required_now",decision_card=card)])["owner_action"][0]["decision_ready"])
        card=copy.deepcopy(self.card);card["known_unknowns"]=["Missing evidence"]
        self.assertFalse(self.projection([self.record("DEC-fixture",owner_action="required_now",decision_card=card)])["owner_action"][0]["decision_ready"])

    def test_window_and_unknown_deadline_not_fabricated(self):
        r=self.record("WORK-fixture",due_or_trigger={"kind":"window","value":["2026-11-16T10:00:00+00:00","2026-11-18T10:00:00+00:00"],"source_ref":"fixture:window"})
        u=self.record("OBL-fixture",due_or_trigger={"kind":"unknown","value":"Date unconfirmed","source_ref":None})
        d=self.projection([r,u])
        self.assertEqual(d["delegated_work"][0]["due_status"],"window")
        self.assertEqual(d["obligation_signals"][0]["due_status"],"unknown")
        self.assertEqual(len(d["needs_reconciliation"]),1)

    def test_distinct_position_and_source_refs_required(self):
        for r in (self.record("WORK-a",accountable_position="AI"),self.record("WORK-a",source_refs=[]),
                  self.record("WORK-a",accountable_position="POS-999")):
            with self.assertRaises(ManualContextError):self.projection([r])

    def test_duplicates_and_foreign_scope_fail_closed(self):
        r=self.record("WORK-a")
        with self.assertRaises(ManualContextError):self.projection([r,r])
        with self.assertRaises(ManualContextError):
            project_controls(access(org="foreign"),None,admitted_scope=self.scope,admitted_positions=self.positions,now=self.now)

    def test_closed_and_inconsistent_states(self):
        d=self.projection([self.record("WORK-a",control_state="closed")])
        self.assertEqual(len(d["closed"]),1)
        self.assertFalse(d["delegated_work"])
        for r in (self.record("WORK-a",control_state="closed",owner_action="required_now"),
                  self.record("WORK-a",owner_action="waiting_external"),
                  self.record("DEC-a",owner_action="required_by_trigger"),
                  self.record("WORK-a",decision_card=self.card)):
            with self.assertRaises(ManualContextError):self.projection([r])

    def test_actual_trigger_and_missing_packet_allow_not_ready(self):
        r=self.record("APR-a",owner_action="required_by_trigger",
                      due_or_trigger={"kind":"condition","value":"Customer evidence received","source_ref":"fixture:trigger"})
        d=self.projection([r])
        self.assertFalse(d["owner_action"][0]["decision_ready"])
        self.assertEqual(len(d["needs_reconciliation"]),1)

    def test_missing_or_incomplete_card_never_ready(self):
        card=copy.deepcopy(self.card);del card["authority_basis"]
        with self.assertRaises(ManualContextError):
            self.projection([self.record("DEC-a",owner_action="required_now",decision_card=card)])
