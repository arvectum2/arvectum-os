"""Strict, read-only project-context adapter for a separately admitted Company packet."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re

import p7_04_persistent_access as p704
from .wsf_manual_context import ManualContextError, _identity
from .wsf_manual_policy import _private_file
from .wsf_manual_runtime import RuntimeManualPilot
from .wsf_company_control_reference import read_snapshot
from .wsf_control_projection import stamp

OPERATION = "workspace.owner_queue.read"
RESOURCE = "owner-project-queue"
QUEUES = {
    "delegated_candidate": "prepare_within_existing_envelope",
    "reconciliation_required": "read_only_reconciliation",
    "blocked_dependency": "blocked",
    "waiting_external": "watch",
    "deferred": "hold",
}
SECTIONS = ("protect_now", "owner_action_required", "delegated_work",
            "cash_commitments", "portfolio_review_triggers", "reference_implementation_evidence")


def need(value):
    if not value:
        raise ManualContextError("owner queue unavailable")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value, n):
    return isinstance(value, str) and re.fullmatch("[a-f0-9]{%d}" % n, value) is not None


def text(value, limit=4000):
    need(isinstance(value, str) and 0 < len(value.strip()) <= limit)
    return value


def strings(value, limit=30):
    need(isinstance(value, list) and len(value) <= limit)
    return [text(x) for x in value]


def unique_object(pairs):
    d = dict(pairs)
    need(len(d) == len(pairs))
    return d


def snapshot_projection(raw, source_commit, source_blob, source_sha256):
    """Input is already a derived Company packet, never a live business register."""
    need(len(raw) <= 512 * 1024 and digest(source_commit, 40) and
         digest(source_blob, 40) and digest(source_sha256, 64))
    need(sha(raw) == source_sha256)
    need(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == source_blob)
    d = json.loads(raw, object_pairs_hook=unique_object)
    need(d["schema"] == "arvectum.company.owner-work-queue-projection/1"
         and d["status"] == "restricted_candidate_projection" and d["derived"] is True
         and all(d[k] is False for k in ("canonical_authority", "organizational_authority_provided",
                                        "execution_authorized", "complete_company_coverage")))
    as_of = text(d["as_of"], 10)
    need(datetime.strptime(as_of, "%Y-%m-%d").strftime("%Y-%m-%d") == as_of)
    controls = set()
    for domain in ("control", "risk", "decision"):
        controls.update(strings(d["private_source_observation"][domain]["record_refs"], 100))
    need(all(re.fullmatch(r"(?:WORK|OBL|DEC|APR|ESC|RSK|EXC|INC)-[0-9]{3,8}", x) for x in controls))
    need(isinstance(d["items"], list) and 0 < len(d["items"]) <= 2000)
    need(isinstance(d["project_details"], dict) and 0 < len(d["project_details"]) <= 100)
    projects = []
    for label, p in d["project_details"].items():
        need(p["coverage"] == "partial")
        subviews = p["subviews"]
        need(isinstance(subviews, list) and len(subviews) <= 30)
        detail = []
        for v in subviews:
            need(v["actual_acceptance_verified"] is False)
            detail.append({k: text(v[k]) for k in ("label", "next", "state")})
        projects.append({"label": text(label, 200), "stage": text(p["stage"]),
                         "source_as_of": text(p["source_as_of"], 40), "subviews": detail})
    counts = dict.fromkeys(QUEUES.values(), 0)
    items, keys = [], set()
    for i in d["items"]:
        key = strings(i["source_key"], 2)
        need(len(key) == 2 and key[0] == i["project"] and key[0] in d["project_details"]
             and tuple(key) not in keys and QUEUES[i["source_queue"]] == i["queue"]
             and all(i[k] is False for k in ("execution_authorized", "actual_acceptance_verified", "owner_decision_ready")))
        keys.add(tuple(key))
        links = strings(i["related_control_refs"], 30)
        need(set(links) <= controls)
        counts[i["queue"]] += 1
        items.append({"project": key[0], "ref": key[1], "queue": i["queue"],
                      "action": text(i["action"]), "source_as_of": text(i["source_as_of"], 40),
                      "trigger": text(i["project_due_or_trigger"]), "unknowns": strings(i["unknowns"]),
                      "related_control_refs": links})
    need(set(x["project"] for x in items) == set(d["project_details"]))
    need(d["counts"] == {"projects": len(projects), "actions": len(items), "queues": counts,
                          "decision_ready_owner_items": 0})
    need([s["key"] for s in d["sections"]] == list(SECTIONS))
    sections = []
    for section in d["sections"]:
        need(isinstance(section["entries"], list) and len(section["entries"]) <= 100)
        rows = []
        for e in section["entries"]:
            need(e.get("execution_authorized", False) is False and e.get("decision_ready", False) is False)
            need(all(tuple(k) in keys for k in e.get("action_keys", [])))
            need(set(e.get("record_refs", [])) <= controls)
            # Compact control points only: the original registers retain authoritative facts.
            if "title" in e:
                rows.append({"title": text(e["title"]), "next": text(e["next_control_point"]),
                             "qualification": text(e["qualification"])})
            elif "claim" in e:
                rows.append({"title": text(e["claim"]), "next": text(e["next_validation"]),
                             "qualification": text(e["scope"])})
            else:
                rows.append({"title": text(e["project"]), "next": text(e.get("trigger", "See project details")),
                             "qualification": text(e["qualification"])})
        sections.append({"key": section["key"], "entries": rows})
    need(not sections[1]["entries"] and d["sections"][3]["financial_visibility"]["available_cash"] == "unknown"
         and d["sections"][3]["financial_visibility"]["payment_authority"] is False)
    return {"schema": "arvectum.workspace.owner-project-queue/1", "derived": True,
            "canonical_authority": False, "organizational_authority_provided": False,
            "execution_authorized": False, "coverage": "partial", "source_state": "dated_candidate_snapshot",
            "as_of": as_of, "source_commit": source_commit, "source_blob": source_blob,
            "projects": projects, "items": items, "sections": sections, "counts": d["counts"]}


class OwnerQueueReference:
    """Uncomposed by default. Requires an independently approved policy pin."""
    def __init__(self, root, *, approved_policy_sha256, approved_contract_blob,
                 clock=lambda: datetime.now(timezone.utc)):
        self.root = Path(root)
        need(self.root.is_absolute() and self.root.resolve() == self.root)
        need(digest(approved_policy_sha256, 64) and digest(approved_contract_blob, 40))
        self.policy_sha = approved_policy_sha256
        self.contract = approved_contract_blob
        self.clock = clock
        self.manual = RuntimeManualPilot(self.root)
        self.source = self.root / RESOURCE / "queue.json"

    def gate(self, a):
        raw = _private_file(self.root / "config/owner-project-queue-policy.json")
        need(sha(raw) == self.policy_sha)
        policy = json.loads(raw, object_pairs_hook=unique_object)
        receipt = json.loads(_private_file(self.root / "config/owner-project-queue-activation.json"),
                             object_pairs_hook=unique_object)
        need(receipt == {"schema": "arvectum.workspace.owner-project-queue-activation/1",
                         "contract_blob": self.contract, "policy_sha256": self.policy_sha})
        need(set(policy) == {"schema", "contract_blob", "scope", "credential_id", "grant_id",
                             "starts_at", "expires_at", "source_commit", "source_blob", "source_sha256"})
        need(policy["schema"] == "arvectum.workspace.owner-project-queue-policy/1"
             and policy["contract_blob"] == self.contract and policy["scope"] == _identity(a)
             and a.principal_kind == "human" and policy["credential_id"] == a.credential_id
             and digest(a.credential_id, 32) and digest(policy["grant_id"], 32))
        start, end = (stamp(policy[k]) for k in ("starts_at", "expires_at"))
        need(start <= self.clock() < end and end-start <= timedelta(days=30))
        review = self.manual.review_signal(a)
        need(end <= stamp(review["due_at"]))
        decision = p704.authorize_from_credential_file(
            self.root, organization=a.organization, principal=a.actor, credential_id=a.credential_id,
            credential_file=self.root/"secrets/p7-04"/(a.credential_id+".secret"),
            operation=OPERATION, resource=RESOURCE, access_path="local")
        need(decision.allowed and decision.principal_kind == "human" and decision.grant_id == policy["grant_id"])
        return policy, review

    def read(self, authorize):
        try:
            a = authorize()
            policy, review = self.gate(a)
            raw = read_snapshot(self.source)
            data = snapshot_projection(raw, policy["source_commit"], policy["source_blob"], policy["source_sha256"])
            need(stamp(data["as_of"]+"T00:00:00+00:00") <= self.clock())
            after = authorize()
            need(a == after and self.gate(after) == (policy, review) and read_snapshot(self.source) == raw)
            return data
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, p704.P704Error) as exc:
            raise ManualContextError("owner queue unavailable") from exc
