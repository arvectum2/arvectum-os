from copy import deepcopy
import unittest

from test_wsf_manual_context import access
from workspace_app.wsf_manual_context import ManualContextError, _identity
from workspace_app.wsf_risk_finance_projection import risk_projection, finance_projection


class RiskFinanceTests(unittest.TestCase):
    def setUp(self):
        self.a=access()
        self.scope=_identity(self.a)
        self.now="2026-11-17T10:00:00+00:00"
        self.as_of="2026-11-17T09:30:00+00:00"
        self.until="2026-11-18T10:00:00+00:00"
        self.positions={"POS-005","POS-006"}
        self.risk={"id":"RSK-fixture","title":"Synthetic exposure","accountable_position":"POS-006",
                   "scope_refs":["fixture:project"],"source_refs":["fixture:risk"],"evidence_as_of":self.as_of,
                   "freshness":"current_for_declared_use","priority":"P0","owner_attention":"not_required",
                   "next_control_point":"Review fallback","closure_ref":None,
                   "risk_state":"active","risk_statement":"Synthetic exposure may disrupt a workstream",
                   "consequence_class":"workstream_critical","current_controls_refs":["fixture:backup"],
                   "likelihood_evidence":"unknown","response_intent":"tolerate","residual_exposure":"Residual fixture exposure",
                   "acceptance_ref":None,"review_trigger":"Next source review"}
        common={k:v for k,v in self.risk.items() if k in {"id","title","accountable_position","scope_refs",
                 "source_refs","evidence_as_of","freshness","priority","owner_attention","next_control_point","closure_ref"}}
        self.exc={**common,"id":"EXC-fixture","exception_state":"requested","control_rule_ref":"fixture:rule",
                  "requested_deviation":"Fixture proposal","authority_basis":"fixture:authority",
                  "approval_refs":[],"effective_scope":"Fixture only","effective_from":None,"effective_until":None,
                  "conditions":[],"compensating_controls":[],"residual_risk_refs":["RSK-fixture"],
                  "reversion_or_exit":"Return to normal control"}
        self.inc={**common,"id":"INC-fixture","incident_state":"contained","detected_at":self.as_of,
                  "consequence_class":"workstream_critical","observed_impact":"Synthetic disruption",
                  "incident_source_ref":"fixture:incident","containment_refs":["fixture:contain"],
                  "recovery_refs":["fixture:recovery"],"residual_risk_refs":["RSK-fixture"],
                  "closure_evidence_refs":[],"notification_obligation_refs":["OBL-fixture"],
                  "suspected_cause_summary":"unknown"}
        self.cash={"source_id":"fixture:cash","kind":"available_cash_fact","title":"Synthetic cash",
                   "source_ref":"fixture:bank","evidence_as_of":self.as_of,"freshness":"current_for_declared_use",
                   "control_refs":[],"scope_refs":["fixture:company"],"amount_minor":10000,"currency":"RUB",
                   "timing_condition":"Observed balance","confidence":"source_backed","accountable_position":"POS-005"}

    def project(self,fn,rows,now=None,**kw):
        source="fixture:source"
        packet=None if rows is None else {"scope":self.scope,"source_ref":source,"as_of":self.as_of,
                                         "review_until":self.until,"records":rows}
        return fn(self.a,packet,**{"scope":self.scope,"positions":self.positions,"source_ref":source,
                                  "now":now or self.now,**kw})

    def test_unknown_without_source(self):
        for fn in (risk_projection,finance_projection):
            result=self.project(fn,None)
            self.assertEqual(result["coverage"],"unknown")
            self.assertFalse(result["authority_provided"])
        self.assertEqual(self.project(finance_projection,None)["liquidity_status"],"unknown")

    def test_risk_tolerance_is_not_acceptance(self):
        d=self.project(risk_projection,[self.risk])
        self.assertEqual(d["risks"][0]["acceptance_status"],"not_established")
        self.assertEqual(len(d["protect_now"]),1)
        self.assertEqual(len(d["needs_review"]),1)
        linked={**self.risk,"acceptance_ref":"DEC-fixture"}
        self.assertEqual(self.project(risk_projection,[linked])["risks"][0]["acceptance_status"],"reference_requires_verification")

    def test_requested_exception_is_not_permission(self):
        e=self.project(risk_projection,[self.exc])["exceptions"][0]
        self.assertEqual(e["effective_status"],"requested")
        self.assertFalse(e["deviation_authorized_by_projection"])
        with self.assertRaises(ManualContextError):
            self.project(risk_projection,[{**self.exc,"exception_state":"approved"}])

    def test_approved_exception_timing_and_nonwaivable_boundary(self):
        e={**self.exc,"exception_state":"approved","approval_refs":["APR-fixture"],
           "effective_from":self.as_of,"effective_until":self.until}
        self.assertEqual(self.project(risk_projection,[e])["exceptions"][0]["effective_status"],"reference_requires_verification")
        self.assertEqual(self.project(risk_projection,[e],now=self.until)["exceptions"][0]["effective_status"],"expired")
        with self.assertRaises(ManualContextError):
            self.project(risk_projection,[{**e,"authority_basis":"none/not_permitted"}])

    def test_incident_recovery_never_closes_obligation_or_residual_risk(self):
        d=self.project(risk_projection,[self.risk,self.inc])
        self.assertFalse(d["incidents"][0]["recovery_implies_obligation_satisfaction"])
        self.assertEqual(d["risks"][0]["risk_state"],"active")
        with self.assertRaises(ManualContextError):
            self.project(risk_projection,[{**self.inc,"incident_state":"closed","closure_ref":"fixture:closure"}])

    def test_expiry_and_scope(self):
        d=self.project(risk_projection,[self.risk],now=self.until)
        self.assertEqual(d["risks"][0]["freshness"],"stale_for_declared_use")
        with self.assertRaises(ManualContextError):
            self.project(risk_projection,[self.risk],scope=_identity(access(org="other")))
        with self.assertRaises(ManualContextError):
            self.project(finance_projection,[self.cash],source_ref="other")

    def test_cash_only_from_current_cash_facts(self):
        rows=[self.cash]
        for kind in ("budget_limit","planned_spend","actual_payment","receivable","expected_inflow",
                     "approved_internal_commitment","incurred_obligation"):
            rows.append({**self.cash,"source_id":"fixture:"+kind,"kind":kind,
                        "control_refs":["OBL-fixture"] if kind=="incurred_obligation" else ["DEC-fixture"] if kind=="approved_internal_commitment" else [],
                        "confidence":"conditional" if kind=="expected_inflow" else "source_backed"})
        d=self.project(finance_projection,rows)
        self.assertTrue(d["cash_facts"][0]["counts_as_available_cash"])
        for key in ("budget_limits","planned_spend","payments","receivables","expected_inflows","approved_not_incurred","obligation_signals"):
            self.assertFalse(d[key][0]["counts_as_available_cash"])
        self.assertIsNone(d["company_cash_total"])
        self.assertEqual(d["liquidity_status"],"unknown")
        self.assertFalse(d["material_commitment_evidence_complete"])

    def test_stale_cash_is_not_available(self):
        for row,now in ((self.cash,self.until),({**self.cash,"freshness":"conflicted"},self.now)):
            c=self.project(finance_projection,[row],now=now)["cash_facts"][0]
            self.assertFalse(c["counts_as_available_cash"])
            self.assertFalse(c["current_source_fact"])

    def test_reject_forecast_as_cash_and_missing_control_refs(self):
        cases=[{**self.cash,"confidence":"conditional"},
               {**self.cash,"kind":"incurred_obligation"},
               {**self.cash,"kind":"approved_internal_commitment"},
               {**self.cash,"confidence":"unknown"},
               {**self.cash,"amount_minor":1.5},
               {**self.cash,"amount_minor":True}]
        for row in cases:
            with self.assertRaises(ManualContextError):self.project(finance_projection,[row])

    def test_unknown_amount_and_currency_separation(self):
        rows=[self.cash,{**self.cash,"source_id":"fixture:usd","currency":"USD"},
              {**self.cash,"source_id":"fixture:unknown","amount_minor":None,"currency":None,"confidence":"unknown"}]
        d=self.project(finance_projection,rows)
        self.assertEqual(len(d["cash_facts"]),3)
        self.assertIsNone(d["company_cash_total"])
        self.assertFalse(d["cash_facts"][-1]["counts_as_available_cash"])
        self.assertEqual(d["unknowns_and_gaps"][0]["source_id"],"fixture:unknown")

    def test_duplicates_and_unadmitted_position(self):
        for fn,row in ((risk_projection,self.risk),(finance_projection,self.cash)):
            with self.assertRaises(ManualContextError):self.project(fn,[row,row])
            with self.assertRaises(ManualContextError):self.project(fn,[{**row,"accountable_position":"POS-999"}])

    def test_no_source_mutation(self):
        rows=[self.risk,self.exc,self.inc]
        before=deepcopy(rows)
        self.project(risk_projection,rows,now=self.until)
        self.assertEqual(rows,before)
