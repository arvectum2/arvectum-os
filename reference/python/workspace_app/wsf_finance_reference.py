"""AC-404 bounded, read-only normalized reference. No authority or effect grants."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json,re
import p7_04_persistent_access as p704
from .wsf_manual_context import ManualContextError,_identity,_id,_keys,_json
from .wsf_manual_policy import _private_file
from .wsf_manual_runtime import RuntimeManualPilot
from .wsf_company_control_reference import read_snapshot,sha
from .wsf_control_projection import stamp

DRAFT="5e54a460059fc2ade1c0b50389282319fc84b1a2"
OPERATION="workspace.company_finance.read"
RESOURCE="company-finance-reference"
IDS=("AC404-INITIAL-REPORT",)

EXPIRY=stamp("2026-12-17T09:35:36.060836+00:00")
def bounded(v):
    if not isinstance(v,str) or not v.strip() or len(v)>4000:raise ManualContextError("invalid reference text")
    return v

UNKNOWN_FIELDS=tuple("available_cash_fact_ref material_due_outflows material_receivables material_payables recurring_cost_signal expected_outflows approved_not_yet_incurred_exposure procurement_cash_gap_cases mandatory_payment_attention actual_receipts project_profitability".split())
def projection(doc,review,now):
    _keys(doc,set(UNKNOWN_FIELDS)|set("schema report_as_of coverage source_freshness liquidity_status expected_inflows portfolio_project_economic_signals risk_exception_incident_refs decision_approval_escalation_refs unknowns_and_gaps next_control_point accountable_position decision_readiness derived canonical_authority payment_authority".split()))
    if doc["schema"]!="arvectum.company.management-finance-report/1" or doc["coverage"]!="partial" or stamp(doc["report_as_of"])>stamp(now) or doc["accountable_position"]!="POS-005" or doc["derived"] is not True or doc["canonical_authority"] is not False or doc["payment_authority"] is not False or doc["liquidity_status"]!="unknown" or doc["decision_readiness"]!="blocked_by_missing_financial_evidence":raise ManualContextError("financial semantics mismatch")
    if doc["source_freshness"]!={"bank":"unknown","accounting":"unknown","contract_terms":"verified_archived_terms","performance_acceptance":"unknown"} or not all(doc[k]=={"status":"unknown","value":None} for k in UNKNOWN_FIELDS):raise ManualContextError("unreviewed financial fact")
    if not isinstance(doc["expected_inflows"],list) or len(doc["expected_inflows"])!=1:raise ManualContextError("unexpected inflow scope")
    v=doc["expected_inflows"][0]
    _keys(v,set("basis contract_price_rub expected_available_cash_rub receivable_confirmed actual_receipt_confirmed advance_provided timing_condition source_refs linked_obligations as_of".split()))
    if not isinstance(v["contract_price_rub"],str) or not re.fullmatch(r"(0|[1-9][0-9]{0,11})\.[0-9]{2}",v["contract_price_rub"]) or v["contract_price_rub"]=="0.00":raise ManualContextError("invalid decimal amount")
    if v["basis"]!="contractual_conditional" or v["expected_available_cash_rub"] is not None or v["receivable_confirmed"] is not False or v["actual_receipt_confirmed"] is not False or v["advance_provided"] is not False or v["as_of"]!=doc["report_as_of"] or v["linked_obligations"]!=["OBL-001","OBL-002"]:raise ManualContextError("unsupported cash claim")
    for x in (v["source_refs"],doc["unknowns_and_gaps"]):
        if not isinstance(x,list) or not 0<len(x)<=24:raise ManualContextError("invalid references")
        for item in x:bounded(item)
    if doc["portfolio_project_economic_signals"]!=[{"source_refs":v["source_refs"],"linked_obligations":v["linked_obligations"],"costs":"unknown","margin":"unknown"}] or doc["risk_exception_incident_refs"]!=["RSK-003"] or doc["decision_approval_escalation_refs"]!=[]:raise ManualContextError("unreviewed linkage")
    return {"schema":"arvectum.workspace.company-finance-reference/1","coverage":"partial","derived":True,"canonical_authority":False,"organizational_authority_provided":False,"payment_authority":False,"report_as_of":doc["report_as_of"],"as_of":now,"position":"POS-005","liquidity_status":"unknown","decision_readiness":doc["decision_readiness"],"facts":{k:doc[k] for k in UNKNOWN_FIELDS},"conditional_inflow":{"basis":v["basis"],"contract_price_rub":v["contract_price_rub"],"expected_available_cash_rub":None,"receivable_confirmed":False,"actual_receipt_confirmed":False,"advance_provided":False,"timing_condition":bounded(v["timing_condition"]),"source_refs":v["source_refs"],"linked_obligations":v["linked_obligations"]},"source_freshness":doc["source_freshness"],"unknowns":doc["unknowns_and_gaps"],"next_control_point":bounded(doc["next_control_point"]),"linked_risks":["RSK-003"]}

class FinanceReference:
    def __init__(self,root,*,clock=lambda:datetime.now(timezone.utc)):
        self.root=Path(root);self.clock=clock;self.manual=RuntimeManualPilot(self.root)
        self.source=Path.home()/"Library/Application Support/ArvectumCompany/finance-report/initial.private.json"
    def gate(self,a):
        raw=_private_file(self.root/"config/company-finance-policy.json")
        receipt=json.loads(_private_file(self.root/"config/company-finance-activation.json"))
        if receipt!={"schema":"arvectum.workspace.company-finance-activation/1","draft_blob":DRAFT,"policy_sha256":sha(raw)}:raise ManualContextError("receipt mismatch")
        p=json.loads(raw)
        _keys(p,{"schema","draft_blob","scope","credential_id","grant_id","purpose","source_sha256","record_ids","starts_at","expires_at"})
        if p["schema"]!="arvectum.workspace.company-finance-policy/1" or p["draft_blob"]!=DRAFT or p["scope"]!=_identity(a) or p["credential_id"]!=a.credential_id or p["purpose"]!="owner-triggered-first-finance-reference-read" or p["record_ids"]!=list(IDS) or not re.fullmatch("[a-f0-9]{64}",p["source_sha256"]):raise ManualContextError("policy mismatch")
        _id(p["credential_id"]);_id(p["grant_id"])
        start,end=stamp(p["starts_at"]),stamp(p["expires_at"])
        if not start<=self.clock()<end<=EXPIRY or end-start>timedelta(days=30):raise ManualContextError("expired")
        review=self.manual.review_signal(a)
        if end>stamp(review["due_at"]):raise ManualContextError("pilot expired")
        d=p704.authorize_from_credential_file(self.root,organization=a.organization,principal=a.actor,credential_id=a.credential_id,credential_file=self.root/"secrets/p7-04"/(a.credential_id+".secret"),operation=OPERATION,resource=RESOURCE,access_path="local")
        if not d.allowed or d.principal_kind!="human" or d.grant_id!=p["grant_id"]:raise ManualContextError("grant denied")
        return p,sha(raw),review
    def read(self,authorize):
        try:
            a=authorize();p,pin,review=self.gate(a)
            raw=read_snapshot(self.source)
            if sha(raw)!=p["source_sha256"]:raise ManualContextError("source changed")
            result=projection(json.loads(raw),review,self.clock().isoformat())
            _,after,review2=self.gate(authorize())
            if after!=pin or review2!=review or read_snapshot(self.source)!=raw:raise ManualContextError("source or access changed")
            return result
        except (OSError,ValueError,TypeError,KeyError,AttributeError,RecursionError,p704.P704Error) as exc:raise ManualContextError("financial reference unavailable") from exc
