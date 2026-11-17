"""AC-401/402/406 derived control routing candidate.

Only an independently admitted source adapter may supply packets. No live route,
register creation, inference from notes, or authority/approval provision here.
"""
from datetime import datetime, timezone
import re

from .wsf_manual_context import ManualContextError, _identity

KINDS = {"WORK": "work", "OBL": "obligation", "DEC": "decision", "APR": "approval", "ESC": "escalation"}
FRESHNESS = {"current_for_declared_use", "stale_for_declared_use", "unknown", "conflicted", "not_time_sensitive"}
ACTIONS = {"required_now", "required_by_trigger", "waiting_external", "not_required"}
CARD_FIELDS = {"exact_question", "why_now", "owner_capacity", "authority_basis",
               "current_recommendation", "options", "downside_reversibility",
               "evidence_refs", "known_unknowns", "constraints_excluded_effects",
               "requested_owner_act", "effect_readiness", "execution_handoff", "review_expiry"}
COMMON = {"id", "title", "accountable_position", "scope_refs", "source_refs", "evidence_as_of",
          "freshness", "review_condition", "control_state", "priority", "next_control_point",
          "due_or_trigger", "owner_action", "material_consequence", "substantive_unknowns", "decision_card"}


def fail(message):
    raise ManualContextError(message)


def text(value, limit=1000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        fail("invalid bounded control text")
    return value


def strings(value, nonempty=False):
    if not isinstance(value, list) or len(value) > 24 or (nonempty and not value):
        fail("invalid control references")
    return [text(x, 500) for x in value]


def stamp(value):
    try:
        d = datetime.fromisoformat(value)
        if d.utcoffset() != timezone.utc.utcoffset(d):
            raise ValueError()
        return d
    except (TypeError, ValueError):
        fail("invalid UTC evidence time")


def trigger(value):
    if not isinstance(value, dict) or set(value) != {"kind", "value", "source_ref"}:
        fail("invalid due/trigger")
    kind = value["kind"]
    if kind not in {"exact", "window", "condition", "periodic", "unknown", "none"}:
        fail("unknown due/trigger kind")
    if kind == "exact":
        stamp(value["value"])
    elif kind == "window":
        v = value["value"]
        if not isinstance(v, list) or len(v) != 2 or stamp(v[0]) > stamp(v[1]):
            fail("invalid due window")
    elif kind in {"condition", "periodic", "unknown"}:
        text(value["value"])
    elif value["value"] is not None:
        fail("none trigger has value")
    if kind in {"exact", "window", "condition", "periodic"}:
        text(value["source_ref"], 500)
    elif value["source_ref"] is not None:
        text(value["source_ref"], 500)
    return value


def _card(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != CARD_FIELDS:
        fail("incomplete owner decision packet")
    for name in CARD_FIELDS - {"options", "evidence_refs", "known_unknowns", "review_expiry"}:
        text(value[name])
    strings(value["options"])
    strings(value["evidence_refs"], True)
    strings(value["known_unknowns"])
    if value["review_expiry"] is not None:
        stamp(value["review_expiry"])
    return value


def project_controls(access, packet, *, admitted_scope, admitted_positions, now):
    """Pure read-only routing of a normalized, already-authorized source packet.

    Caller resolves authorization, binds sources/provenance and establishes
    completeness and freshness. This function does not certify source truth.
    A missing packet is unknown, not proof of zero tasks.
    """
    if admitted_scope != _identity(access):
        fail("control scope unavailable")
    current = stamp(now)
    result = {"derived":True, "canonical_authority":False, "organizational_authority_provided":False,
              "coverage":"unknown", "as_of":now, "protect_now":[], "owner_action":[],
              "waiting_external":[], "delegated_work":[], "obligation_signals":[], "closed":[],
              "needs_reconciliation":[]}
    if packet is None:
        return result
    if not isinstance(packet, dict) or set(packet) != {"scope","source_ref","as_of","coverage","records"}:
        fail("invalid source packet")
    if packet["scope"] != admitted_scope:
        fail("control scope unavailable")
    text(packet["source_ref"],500)
    observed = stamp(packet["as_of"])
    if observed > current or packet["coverage"] not in {"partial","unknown"}:
        fail("invalid source packet coverage or timestamp")
    records = packet["records"]
    if not isinstance(records, list) or len(records) > 500:
        fail("invalid source record count")
    result["coverage"] = packet["coverage"]
    result["source_ref"] = packet["source_ref"]
    result["source_as_of"] = packet["as_of"]
    seen=set()
    for raw in records:
        if not isinstance(raw, dict) or set(raw) != COMMON:
            fail("invalid normalized record")
        rid=text(raw["id"],160)
        match=re.fullmatch(r"(WORK|OBL|DEC|APR|ESC)-[A-Za-z0-9][A-Za-z0-9._-]{0,100}",rid)
        if not match or rid in seen:
            fail("duplicate or invalid control identity")
        seen.add(rid)
        kind=KINDS[match.group(1)]
        for k in ("title","next_control_point","review_condition","material_consequence"):
            text(raw[k])
        pos=raw["accountable_position"]
        if not isinstance(pos,str) or pos not in admitted_positions or not re.fullmatch(r"POS-[A-Za-z0-9_-]+",pos):
            fail("accountable position unavailable")
        strings(raw["scope_refs"], True)
        strings(raw["source_refs"], True)
        unknowns=strings(raw["substantive_unknowns"])
        if stamp(raw["evidence_as_of"]) > observed:
            fail("evidence newer than source packet")
        if raw["freshness"] not in FRESHNESS or raw["priority"] not in {"P0","P1","P2","P3"}:
            fail("invalid evidence or priority state")
        if raw["control_state"] not in {"open","waiting","blocked","closed"} or raw["owner_action"] not in ACTIONS:
            fail("invalid control handling")
        due=trigger(raw["due_or_trigger"])
        card=_card(raw["decision_card"])
        if raw["control_state"]=="closed" and raw["owner_action"]!="not_required":
            fail("closed control cannot require action")
        if raw["owner_action"]=="waiting_external" and raw["control_state"]!="waiting":
            fail("external watch requires waiting control state")
        if raw["owner_action"]=="required_by_trigger" and due["kind"] in {"none","unknown"}:
            fail("owner trigger missing")
        # Never infer the need for Owner action from P0, deadline or a technical failure.
        has_owner_need=raw["owner_action"] in {"required_now","required_by_trigger"}
        if card is not None and not has_owner_need:
            fail("owner card without actual owner action")
        needs_review=raw["freshness"] in {"stale_for_declared_use","unknown","conflicted"} or due["kind"]=="unknown" or bool(unknowns)
        safe_fresh=not needs_review
        expiry=stamp(card["review_expiry"]) if card and card["review_expiry"] else None
        ready=bool(has_owner_need and card and safe_fresh and not card["known_unknowns"]
                   and (expiry is None or current < expiry))
        due_status="not_dated"
        if due["kind"]=="exact":
            due_status="past_due" if current>stamp(due["value"]) else "dated"
        elif due["kind"]=="window":
            due_status="past_window" if current>stamp(due["value"][1]) else "window"
        elif due["kind"] in {"condition","periodic","unknown"}:
            due_status=due["kind"]
        row={**raw,"kind":kind,"due_status":due_status,"decision_ready":ready,
             "canonical_authority":False}
        if raw["control_state"]=="closed":
            result["closed"].append(row)
            continue
        if needs_review or (has_owner_need and not ready):
            result["needs_reconciliation"].append(row)
        if raw["priority"]=="P0":
            result["protect_now"].append(row)
        if kind=="obligation":
            result["obligation_signals"].append(row)
        if has_owner_need:
            result["owner_action"].append(row)
        elif raw["owner_action"]=="waiting_external":
            result["waiting_external"].append(row)
        else:
            result["delegated_work"].append(row)
    return result
