"""AC-403/404 management reference projections; no live source or authority.

Inputs must be resolved by independently authorized adapters. These projections
do not create canonical records, infer acceptance, authorize payments or assert
complete company coverage. Exact confidential values need a separate admission.
"""
import re

from .wsf_manual_context import _identity, _keys
from .wsf_control_projection import text, strings, stamp, FRESHNESS, fail

RISK_COMMON = {"id","title","accountable_position","scope_refs","source_refs","evidence_as_of",
               "freshness","priority","owner_attention","next_control_point","closure_ref"}
RISK_FIELDS = {
    "RSK": {"risk_state","risk_statement","consequence_class","current_controls_refs",
            "likelihood_evidence","response_intent","residual_exposure","acceptance_ref","review_trigger"},
    "EXC": {"exception_state","control_rule_ref","requested_deviation","authority_basis",
            "approval_refs","effective_scope","effective_from","effective_until","conditions",
            "compensating_controls","residual_risk_refs","reversion_or_exit"},
    "INC": {"incident_state","detected_at","consequence_class","observed_impact",
            "incident_source_ref","containment_refs","recovery_refs","residual_risk_refs",
            "closure_evidence_refs","notification_obligation_refs","suspected_cause_summary"},
}
RISK_STATES = {
    "RSK": {"identified","assessing","active","monitoring","closed"},
    "EXC": {"requested","under_review","approved","rejected","expired","revoked","superseded","closed"},
    "INC": {"detected","triaged","contained","recovering","monitoring","closed"},
}
MONEY_KINDS = {"available_cash_fact","budget_limit","planned_spend","approved_internal_commitment",
               "incurred_obligation","actual_payment","receivable","expected_inflow","expected_outflow",
               "recurring_cost_signal","procurement_cash_gap","mandatory_payment_attention","project_economic_signal"}
MONEY_FIELDS = {"source_id","kind","title","source_ref","evidence_as_of","freshness","control_refs",
                "scope_refs","amount_minor","currency","timing_condition","confidence","accountable_position"}
CURRENT={"current_for_declared_use","not_time_sensitive"}
CONSEQUENCE={"company_critical","workstream_critical","degrading","not_currently_critical"}


def _packet(access, packet, scope, now, expected_source):
    if _identity(access)!=scope:
        fail("source scope unavailable")
    current=stamp(now)
    if packet is None:
        return current,None
    _keys(packet,{"scope","source_ref","as_of","review_until","records"})
    if packet["scope"]!=scope or packet["source_ref"]!=expected_source:
        fail("source binding mismatch")
    text(expected_source,500)
    as_of=stamp(packet["as_of"])
    until=stamp(packet["review_until"])
    if as_of>current or until<=as_of:
        fail("invalid source time")
    if not isinstance(packet["records"],list) or len(packet["records"])>500:
        fail("invalid source records")
    return current,as_of


def _fresh(value, expired):
    if value not in FRESHNESS:
        fail("invalid freshness")
    return "stale_for_declared_use" if expired and value in CURRENT else value


def _position(value, positions):
    if not isinstance(value,str) or not re.fullmatch(r"POS-[A-Za-z0-9_-]+",value) or value not in positions:
        fail("accountable position unavailable")


def _ref(value):
    if value is not None:
        text(value,500)


def risk_projection(access,packet,*,scope,positions,source_ref,now):
    current,as_of=_packet(access,packet,scope,now,source_ref)
    out={"coverage":"unknown","derived":True,"authority_provided":False,
         "risks":[],"exceptions":[],"incidents":[],"protect_now":[],"needs_review":[]}
    if packet is None:
        return out
    out.update(coverage="partial",source_ref=source_ref,source_as_of=packet["as_of"])
    expired=current>=stamp(packet["review_until"])
    seen=set()
    for raw in packet["records"]:
        if not isinstance(raw,dict):
            fail("invalid risk record")
        rid=text(raw.get("id"),160)
        prefix=rid.split("-",1)[0]
        if prefix not in RISK_FIELDS or not re.fullmatch(r"(RSK|EXC|INC)-[A-Za-z0-9][A-Za-z0-9._-]{0,100}",rid) or rid in seen:
            fail("invalid or duplicate risk identity")
        seen.add(rid)
        _keys(raw,RISK_COMMON|RISK_FIELDS[prefix])
        _position(raw["accountable_position"],positions)
        for k in ("title","next_control_point"):
            text(raw[k])
        strings(raw["scope_refs"],True);strings(raw["source_refs"],True)
        if stamp(raw["evidence_as_of"])>as_of:
            fail("evidence newer than packet")
        if raw["priority"] not in {"P0","P1","P2","P3"} or raw["owner_attention"] not in {"required","not_required","waiting_external"}:
            fail("invalid attention")
        state=raw[{"RSK":"risk_state","EXC":"exception_state","INC":"incident_state"}[prefix]]
        if state not in RISK_STATES[prefix]:
            fail("invalid risk lifecycle")
        _ref(raw["closure_ref"])
        if state=="closed" and not raw["closure_ref"]:
            fail("closure evidence missing")
        freshness=_fresh(raw["freshness"],expired)
        row={**raw,"freshness":freshness,"canonical_authority":False}
        review=freshness not in CURRENT
        if prefix=="RSK":
            for k in ("risk_statement","likelihood_evidence","residual_exposure","review_trigger"):
                text(raw[k])
            strings(raw["current_controls_refs"])
            if raw["consequence_class"] not in CONSEQUENCE or raw["response_intent"] not in {"avoid","reduce","monitor","transfer_or_share","tolerate","undecided"}:
                fail("invalid risk interpretation")
            _ref(raw["acceptance_ref"])
            # An adapter has supplied a reference, not validated acceptance here.
            row["acceptance_status"]="reference_requires_verification" if raw["acceptance_ref"] else "not_established"
            review=review or raw["response_intent"]=="tolerate"
            out["risks"].append(row)
        elif prefix=="EXC":
            for k in ("control_rule_ref","requested_deviation","authority_basis","effective_scope","reversion_or_exit"):
                text(raw[k])
            for k in ("approval_refs","conditions","compensating_controls","residual_risk_refs"):
                strings(raw[k])
            start=stamp(raw["effective_from"]) if raw["effective_from"] is not None else None
            end=stamp(raw["effective_until"]) if raw["effective_until"] is not None else None
            if start and end and start>=end:fail("invalid exception period")
            if state=="approved" and (not raw["approval_refs"] or raw["authority_basis"] in {"none","not_permitted","none/not_permitted"} or start is None or end is None):
                fail("approved exception evidence or period missing")
            row["effective_status"]=("expired" if end and current>=end else
                 "not_started" if start and current<start else "reference_requires_verification" if state=="approved" else state)
            row["deviation_authorized_by_projection"]=False
            review=review or state=="approved"
            out["exceptions"].append(row)
        else:
            if stamp(raw["detected_at"])>as_of or raw["consequence_class"] not in CONSEQUENCE-{"not_currently_critical"}:
                fail("invalid incident observation")
            for k in ("observed_impact","incident_source_ref","suspected_cause_summary"):
                text(raw[k])
            for k in ("containment_refs","recovery_refs","residual_risk_refs","closure_evidence_refs","notification_obligation_refs"):
                strings(raw[k])
            if state=="closed" and not raw["closure_evidence_refs"]:
                fail("incident closure evidence missing")
            row["recovery_implies_obligation_satisfaction"]=False
            out["incidents"].append(row)
        if review:out["needs_review"].append(row)
        if raw["priority"]=="P0" and state not in {"closed","rejected","revoked","superseded","expired"}:
            out["protect_now"].append(row)
    return out


def finance_projection(access,packet,*,scope,positions,source_ref,now):
    current,as_of=_packet(access,packet,scope,now,source_ref)
    out={"coverage":"unknown","derived":True,"authority_provided":False,
         "liquidity_status":"unknown","cash_facts":[],"budget_limits":[],"planned_spend":[],
         "approved_not_incurred":[],"obligation_signals":[],"payments":[],"receivables":[],
         "expected_inflows":[],"expected_outflows":[],"recurring_costs":[],"cash_gap_cases":[],
         "mandatory_payment_attention":[],"economic_signals":[],"unknowns_and_gaps":[],
         "company_cash_total":None,"material_commitment_evidence_complete":False}
    if packet is None:
        return out
    out.update(coverage="partial",source_ref=source_ref,source_as_of=packet["as_of"])
    expired=current>=stamp(packet["review_until"])
    groups=dict(zip(("available_cash_fact","budget_limit","planned_spend","approved_internal_commitment",
         "incurred_obligation","actual_payment","receivable","expected_inflow","expected_outflow",
         "recurring_cost_signal","procurement_cash_gap","mandatory_payment_attention","project_economic_signal"),
         ("cash_facts","budget_limits","planned_spend","approved_not_incurred","obligation_signals",
          "payments","receivables","expected_inflows","expected_outflows","recurring_costs","cash_gap_cases",
          "mandatory_payment_attention","economic_signals")))
    seen=set()
    for raw in packet["records"]:
        _keys(raw,MONEY_FIELDS)
        sid=text(raw["source_id"],160); kind=raw["kind"]
        if (sid,kind) in seen or kind not in MONEY_KINDS:
            fail("invalid or duplicate financial source reference")
        seen.add((sid,kind))
        _position(raw["accountable_position"],positions)
        for k in ("title","source_ref","timing_condition"):
            text(raw[k])
        strings(raw["scope_refs"],True); refs=strings(raw["control_refs"])
        if stamp(raw["evidence_as_of"])>as_of:
            fail("evidence newer than packet")
        if kind=="incurred_obligation" and not any(re.fullmatch(r"OBL-[A-Za-z0-9._-]+",r) for r in refs):
            fail("material obligation reference missing")
        if kind=="approved_internal_commitment" and not any(re.fullmatch(r"(DEC|APR)-[A-Za-z0-9._-]+",r) for r in refs):
            fail("internal commitment reference missing")
        amount,currency=raw["amount_minor"],raw["currency"]
        if amount is None:
            if currency is not None:fail("currency without amount")
        elif type(amount) is not int or not 0<=amount<=10**15 or not isinstance(currency,str) or not re.fullmatch("[A-Z]{3}",currency):
            fail("invalid exact monetary value")
        confidence=raw["confidence"]
        if confidence not in {"source_backed","reasonably_expected","conditional","speculative_unknown","unknown"}:
            fail("invalid financial confidence")
        if kind in {"available_cash_fact","actual_payment","receivable","incurred_obligation"} and confidence not in {"source_backed","unknown"}:
            fail("forecast cannot be a current fact")
        if confidence=="unknown" and amount is not None:fail("unknown confidence cannot carry amount")
        freshness=_fresh(raw["freshness"],expired)
        current_fact=confidence=="source_backed" and freshness in CURRENT and kind in {"available_cash_fact","actual_payment","receivable","incurred_obligation"}
        row={**raw,"freshness":freshness,"current_source_fact":current_fact,"canonical_authority":False,
             "counts_as_available_cash":bool(current_fact and kind=="available_cash_fact" and amount is not None)}
        out[groups[kind]].append(row)
        if freshness not in CURRENT or confidence in {"unknown","speculative_unknown"} or amount is None:
            out["unknowns_and_gaps"].append({"source_id":sid,"kind":kind,"freshness":freshness,"confidence":confidence})
    # Partial evidence cannot establish liquidity or a consolidated balance.
    # Never aggregate currencies, forecasts, receivables, or historic payments.
    return out
