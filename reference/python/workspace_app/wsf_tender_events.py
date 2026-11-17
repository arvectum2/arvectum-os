"""WSF-07B Tender Agent metadata adapter candidate.

No transport, SQL, credentials, durable writes or authority. The producer must
first supply a separately admitted authenticated tenant-scoped bounded export.
Legacy optional tenant filters and unscoped events are not safe source bindings.
"""
import re
from datetime import datetime, timezone
from .wsf_manual_context import ManualContextError, _identity, _id, _keys, _digest, _json
from .wsf_control_projection import stamp

SCHEMA="arvectum.workspace.tender-event-candidates/1"
MAX_ROWS=100
KINDS={"analysis_completed":"analysis_run","review_required":"procurement_case"}
ROW_KEYS={"id","event_key","event_type","tenant_id","aggregate_type","aggregate_id","envelope","created_at"}
ENV_KEYS={"schema_version","event_key","event_type","tenant_id","aggregate_type","aggregate_id","occurred_at","data"}

def opaque(value):
    if not isinstance(value,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}",value):
        raise ManualContextError("invalid source reference")
    return value

def normalize(access,rows,*,scope,binding_id,tenant,project_map,now):
    """Caller supplies independently verified source, mapping and authorization.

    Reject the entire batch on any tenant or identity mismatch. No heuristic
    name match; do not persist source payload, external URL, or free text.
    """
    if _identity(access)!=scope:raise ManualContextError("tender scope unavailable")
    opaque(binding_id);opaque(tenant);current=stamp(now)
    if not isinstance(rows,list) or len(rows)>MAX_ROWS:raise ManualContextError("bounded batch required")
    if not isinstance(project_map,dict):raise ManualContextError("project mapping unavailable")
    for src,dst in project_map.items():opaque(src);_id(dst,"PRJ-")
    result={}
    for r in rows:
        _keys(r,ROW_KEYS)
        e=r["envelope"];_keys(e,ENV_KEYS)
        if r["tenant_id"]!=tenant or e["tenant_id"]!=tenant:
            raise ManualContextError("unscoped or foreign event")
        if e["schema_version"]!="integration-event-v1":raise ManualContextError("source schema unavailable")
        for k in ("event_key","event_type","tenant_id","aggregate_type","aggregate_id"):
            if r[k]!=e[k]:raise ManualContextError("source envelope conflict")
        event_key=r["event_key"]
        if not isinstance(event_key,str) or not re.fullmatch("[a-f0-9]{64}",event_key):
            raise ManualContextError("invalid event key")
        kind=r["event_type"]
        if not isinstance(kind,str) or kind not in KINDS or r["aggregate_type"]!=KINDS[kind]:
            raise ManualContextError("event not admitted")
        rid=opaque(r["id"]);aggregate=opaque(r["aggregate_id"])
        occurred,created=stamp(e["occurred_at"]),stamp(r["created_at"])
        if occurred>created or created>current:raise ManualContextError("source time conflict")
        d=e["data"]
        keys={"project_id","case_id","status"} if kind=="analysis_completed" else {"project_id","run_id","reason"}
        _keys(d,keys)
        project=opaque(d["project_id"])
        if project not in project_map:raise ManualContextError("exact project mapping unavailable")
        case=opaque(d["case_id"]) if kind=="analysis_completed" else aggregate
        run=aggregate if kind=="analysis_completed" else opaque(d["run_id"])
        if kind=="analysis_completed" and d["status"]!="completed":raise ManualContextError("analysis outcome conflict")
        if kind=="review_required" and d["reason"]!="analysis_completed_operator_review":raise ManualContextError("review reason not admitted")
        # Stable event key matches producer algorithm for these exact producers.
        if _digest(_json([kind,KINDS[kind],aggregate,run]))!=event_key:
            raise ManualContextError("event key mismatch")
        event_id="TENDEREVT-"+_digest(_json([binding_id,tenant,event_key]))[:32]
        normalized={"id":event_id,"binding_id":binding_id,"event_key":event_key,
            "source_record_id":rid,"source_project_id":project,"project_id":project_map[project],
            "case_ref":case,"run_ref":run,"kind":kind,"occurred_at":occurred.isoformat(),
            "created_at":created.isoformat(),"canonical_authority":False,
            "business_impact":"unknown","owner_action":"unknown",
            "suggested_action":"review-analysis-result" if kind=="review_required" else "inspect-completed-analysis"}
        if event_id in result and result[event_id]!=normalized:
            raise ManualContextError("immutable source event conflict")
        result[event_id]=normalized
    return sorted(result.values(),key=lambda r:(r["created_at"],r["source_record_id"]))

def review_groups(events):
    """Source-linked grouping for presentation, not closure or automatic tasks."""
    groups={}
    for e in events:
        k=(e["binding_id"],e["source_project_id"],e["case_ref"],e["run_ref"])
        g=groups.setdefault(k,{"project_id":e["project_id"],"case_ref":e["case_ref"],"run_ref":e["run_ref"],
            "events":[],"review_signal":False,"owner_action":"unknown","canonical_authority":False})
        if g["project_id"]!=e["project_id"]:raise ManualContextError("project mapping conflict")
        g["events"].append(e["id"])
        if e["kind"]=="review_required":g["review_signal"]=True
    return {"schema":SCHEMA,"coverage":"partial","derived":True,
            "canonical_authority":False,"organizational_authority_provided":False,
            "groups":list(groups.values())}
