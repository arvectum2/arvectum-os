"""WSF-05 functional projection candidate, using the existing manual read scope.

No new organizational records, authority, permissions, connectors or store.
AC-406 sections without admitted current evidence remain explicitly unknown.
"""
from .wsf_manual_context import ManualContextError, _id, _replay

SECTIONS = (
    ("protect-now", "Protect Now", "WORK/OBL, RSK/EXC/INC and current material-risk evidence"),
    ("owner-action", "Owner Action Required", "DEC/APR/ESC and exact current owner-action evidence"),
    ("delegated-work", "Delegated Work / No Owner Action", "WORK/OBL with accountable Position and current state"),
    ("cash-commitments", "Cash / Commitments / Obligation Signals", "AC-404 and authoritative finance/obligation evidence"),
    ("portfolio-review", "Portfolio / Opportunity / Review Triggers", "PORT/AC-405 and current review-trigger evidence"),
    ("reference-evidence", "Reference-Implementation Evidence", "Actual dated operational evidence and limitations"),
)


def project_timeline(store, access, project_id):
    """Consistent history of a single project, including notes moved out/in.

    Use the authoritative manual ledger order, not client timestamps; render a
    historical association as such. Notes are observations, never tasks.
    """
    store._authorize(access)
    _id(project_id, "PRJ-")
    with store._locked():
        events = store._load()
        projects, notes, _ = _replay(events)
        if project_id not in projects:
            raise ManualContextError("project unavailable")
        rows, previous, revision = [], {}, {}
        for event in events:
            op, rid, data = event["operation"], event["record_id"], event["payload"]
            if op == "project":
                if rid == project_id:
                    rows.append({"kind":"project-created","at":event["at"],"record_id":rid,
                                 "label":data["label"],"canonical_authority":False})
                continue
            old = previous.get(rid)
            new = data["project_id"]
            rev = revision.get(rid, 0) + 1
            previous[rid], revision[rid] = new, rev
            if old != project_id and new != project_id:
                continue
            kind = "note-captured" if op == "capture" else (
                "note-linked" if old != project_id else "note-unlinked" if new != project_id else "note-revised")
            # A moved-away note may contain material from its new project:
            # report only the last revision previously associated with this one.
            visible_rev = rev-1 if kind == "note-unlinked" else rev
            note = notes[rid][visible_rev-1]
            rows.append({"kind":kind,"at":event["at"],"record_id":rid,"revision":visible_rev,
                         "title":note["title"],"text":note["text"],"provenance":"manual-observation",
                         "canonical_authority":False})
        return {"schema":"arvectum.workspace.project-timeline/1","project":projects[project_id],
                "current_notes":[revs[-1] for revs in notes.values() if revs[-1]["project_id"] == project_id],
                "events":rows,"derived":True,"canonical_authority":False}


def mission_control_baseline(store, access):
    """Initial factual inventory; no inference from unstructured notes.

    A successful read only proves manual-context availability, not completeness
    of Company controls or absence of action/risk. Future independently admitted
    source adapters may populate sections; do not use this as a task register.
    """
    data = store.read(access)
    return {
        "schema":"arvectum.workspace.mission-control-baseline/1",
        "derived":True,"canonical_authority":False,"organizational_authority_provided":False,
        "manual_context":{"status":"available","projects":data["projects"],"notes":data["notes"],
                          "source":"manual-observation","complete_company_coverage":False},
        "sections":[{"id":id,"label":label,"state":"unknown","decision_ready":False,
                     "items":[],"missing_source":source} for id,label,source in SECTIONS],
    }
