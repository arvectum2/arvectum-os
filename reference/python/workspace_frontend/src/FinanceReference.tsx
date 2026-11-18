import {useEffect,useRef,useState} from "react";
import {useWorkspaceLanguage} from "./i18n";
const labels=[["available_cash_fact_ref","Доступные средства","Available cash"],["material_due_outflows","Срочные платежи","Due outflows"],["material_receivables","Дебиторская задолженность","Receivables"],["material_payables","Кредиторская задолженность","Payables"],["recurring_cost_signal","Регулярные расходы","Recurring costs"],["expected_outflows","Ожидаемые расходы","Expected outflows"],["approved_not_yet_incurred_exposure","Утверждённые будущие затраты","Approved exposure"],["procurement_cash_gap_cases","Кассовые разрывы","Procurement cash gaps"],["mandatory_payment_attention","Обязательные платежи","Mandatory payments"],["actual_receipts","Фактические поступления","Actual receipts"],["project_profitability","Прибыльность проектов","Project profitability"]];
type View={report_as_of:string;conditional_inflow:{contract_price_rub:string;timing_condition:string;source_refs:string[];linked_obligations:string[]};unknowns:string[];next_control_point:string};
export function parseFinance(raw:unknown):View{
 if(!raw||typeof raw!=="object")throw Error();
 const d=raw as Record<string,any>;
 if(d.schema!=="arvectum.workspace.company-finance-reference/1"||d.coverage!=="partial"||d.derived!==true||d.canonical_authority!==false||d.organizational_authority_provided!==false||d.payment_authority!==false||d.position!=="POS-005"||d.liquidity_status!=="unknown"||d.decision_readiness!=="blocked_by_missing_financial_evidence"||!Number.isFinite(Date.parse(d.report_as_of)))throw Error();
 if(!d.facts||Object.keys(d.facts).length!==labels.length||!labels.every(([k])=>d.facts[k]?.status==="unknown"&&d.facts[k]?.value===null))throw Error();
 const v=d.conditional_inflow;
 if(!v||v.basis!=="contractual_conditional"||typeof v.contract_price_rub!=="string"||!/^(0|[1-9][0-9]{0,11})\.[0-9]{2}$/.test(v.contract_price_rub)||v.contract_price_rub==="0.00"||v.expected_available_cash_rub!==null||v.receivable_confirmed!==false||v.actual_receipt_confirmed!==false||v.advance_provided!==false||typeof v.timing_condition!=="string"||JSON.stringify(v.linked_obligations)!=='["OBL-001","OBL-002"]')throw Error();
 const strings=(a:unknown)=>Array.isArray(a)&&a.length>0&&a.every(x=>typeof x==="string");
 if(!strings(v.source_refs)||!strings(d.unknowns)||typeof d.next_control_point!=="string")throw Error();
 return d as unknown as View;
}
export function FinanceReference({csrfToken}:{csrfToken:string}){
 const {text}=useWorkspaceLanguage();
 const [data,setData]=useState<View|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(false);
 const seq=useRef(0);useEffect(()=>()=>{seq.current++;},[csrfToken]);
 async function load(){
  const n=++seq.current;setData(null);setBusy(true);setError(false);
  try{
   const r=await fetch("/api/app/v1/company-finance-reference",{method:"POST",credentials:"same-origin",cache:"no-store",headers:{"X-Arvectum-Workspace-Release":__ARVECTUM_WORKSPACE_RELEASE__,"X-Arvectum-CSRF":csrfToken}});
   if(!r.ok)throw Error();const d=parseFinance(await r.json());if(n===seq.current)setData(d);
  }catch{if(n===seq.current)setError(true);}
  finally{if(n===seq.current)setBusy(false);}
 }
 return <section className="company-card"><h2>{text("Финансы компании","Company finances")}</h2>
 <p>{text("Частичное покрытие. Договорная цена не является остатком денег или прибылью.","Partial coverage. Contract price is not available cash or profit.")}</p>
 <button disabled={busy} onClick={()=>void load()}>{text("Прочитать финансовую сводку","Read financial report")}</button>
 {error&&<p role="alert">{text("Финансовый снимок недоступен, изменился или не допущен. Сведения скрыты.","Financial snapshot unavailable, changed or not admitted. Details hidden.")}</p>}
 {data&&<><p>{text("Снимок на","Report as of")}: {data.report_as_of} · POS-005</p>
 <h3>{text("Условное поступление по контракту","Conditional contractual inflow")}</h3>
 <p>{text("Цена контракта","Contract price")}: {new Intl.NumberFormat("ru-RU",{style:"currency",currency:"RUB"}).format(Number(data.conditional_inflow.contract_price_rub))}</p>
 <p>{data.conditional_inflow.timing_condition}</p>
 <p>{text("Приёмка, фактическое поступление и дебиторская задолженность не подтверждены.","Acceptance, actual receipt and receivable not confirmed.")}</p>
 <h3>{text("Денежные средства и обязательства","Cash and commitments")}</h3>
 <dl>{labels.map(([key,ru,en])=><div key={key}><dt>{text(ru,en)}</dt><dd>{text("Не установлено","Unknown")}</dd></div>)}</dl>
 <p>{text("Финансовые решения не готовы: недостаточно подтверждённых сведений.","Financial decisions blocked by insufficient evidence.")}</p>
 <p>{data.next_control_point}</p><details><summary>{text("Источники и ограничения","Sources and limitations")}</summary>{[...data.conditional_inflow.source_refs,...data.unknowns].map((x,i)=><p key={i}>{x}</p>)}</details></>}
 </section>;
}
