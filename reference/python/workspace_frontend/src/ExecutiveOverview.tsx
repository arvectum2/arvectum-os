import {useEffect,useRef,useState} from "react";
import {useWorkspaceLanguage} from "./i18n";
import {parseControl,type ControlRow} from "./CompanyControlReference";
import {parseDecision} from "./DecisionReference";
import {parseRisk} from "./RiskReference";
import {parseFinance} from "./FinanceReference";
import {parseCRM,parseInbox} from "./ControlReferenceSummary";
import type {MyWorkProjection} from "./types";
import "./Executive.css";

type Result<T>={state:"unchecked"|"unavailable"|"denied"}|{state:"ready";value:T};
type Sources={work:Result<ReturnType<typeof parseControl>>;decisions:Result<ReturnType<typeof parseDecision>>;risks:Result<ReturnType<typeof parseRisk>>;finance:Result<ReturnType<typeof parseFinance>>;crm:Result<ReturnType<typeof parseCRM>>;inbox:Result<ReturnType<typeof parseInbox>>;tasks:Result<MyWorkProjection>};
const empty=():Sources=>({work:{state:"unchecked"},decisions:{state:"unchecked"},risks:{state:"unchecked"},finance:{state:"unchecked"},crm:{state:"unchecked"},inbox:{state:"unchecked"},tasks:{state:"unchecked"}});
async function read<T>(path:string,parse:(raw:unknown)=>T,csrf?:string):Promise<Result<T>>{
 try{
  const r=await fetch("/api/app/v1/"+path,{method:csrf?"POST":"GET",credentials:"same-origin",cache:"no-store",headers:{"X-Arvectum-Workspace-Release":__ARVECTUM_WORKSPACE_RELEASE__,...(csrf?{"X-Arvectum-CSRF":csrf}:{})}});
  if(r.status===401||r.status===403)return {state:"denied"};
  if(!r.ok)return {state:"unavailable"};
  return {state:"ready",value:parse(await r.json())};
 }catch{return {state:"unavailable"};}
}
function parseTasks(v:unknown):MyWorkProjection{
 const d=v as MyWorkProjection;
 if(!d||d.schema!=="arvectum.workspace.my-work/1"||d.projection?.derived!==true||d.projection.canonical_authority!==false||d.projection.organizational_authority_provided!==false||d.projection.visibility_implies_permission!==false||d.projection.consequential_action_available!==false||d.scope?.organization_resolved_server_side!==true||d.scope.actor_resolved_server_side!==true||d.scope.denied_item_counts_exposed!==false||!["fresh","stale","degraded"].includes(d.health?.state)||!Array.isArray(d.items)||!d.items.every(x=>x&&typeof x.title==="string"&&typeof x.id==="string"&&typeof x.open_href==="string"&&x.open_href.startsWith("/my-work?focus=")&&x.authority_provided===false))throw Error("shape");
 return d;
}
function value<T>(r:Result<T>):T|null{return r.state==="ready"?r.value:null;}
export function ExecutiveOverview({csrfToken,mode="overview"}:{csrfToken:string;mode?:"overview"|"work"|"finance"}){
 const {language,text}=useWorkspaceLanguage();
 const [sources,setSources]=useState<Sources>(empty);
 const [busy,setBusy]=useState(false),[checked,setChecked]=useState<Date|null>(null),[denied,setDenied]=useState(false);
 const gen=useRef(0);
 useEffect(()=>{gen.current++;setSources(empty());setChecked(null);setDenied(false);setBusy(false);return()=>{gen.current++;};},[csrfToken,mode]);
 async function refresh(){
  if(!csrfToken)return;
  const n=++gen.current;setBusy(true);setSources(empty());setDenied(false);setChecked(null);
  let next=empty();
  if(mode==="finance")next.finance=await read("company-finance-reference",parseFinance,csrfToken);
  else{
   const [work,decisions,risks,finance,crm,inbox,taskView]=await Promise.all([
    read("company-control-reference",parseControl,csrfToken),read("company-decision-reference",parseDecision,csrfToken),mode==="overview"?read("company-risk-reference",parseRisk,csrfToken):Promise.resolve(empty().risks),
    mode==="overview"?read("company-finance-reference",parseFinance,csrfToken):Promise.resolve(empty().finance),
    mode==="overview"?read("crm/followups",parseCRM):Promise.resolve(empty().crm),mode==="overview"?read("roadmap-inbox",parseInbox):Promise.resolve(empty().inbox),read("my-work",parseTasks),
   ]);
   next={work,decisions,risks,finance,crm,inbox,tasks:taskView};
  }
  if(n!==gen.current)return;
  setBusy(false);
  if(Object.values(next).some(r=>r.state==="denied")){setDenied(true);return;}
  setSources(next);setChecked(new Date());
 }
 const fmt=(v:string)=>{const d=new Date(v);return Number.isFinite(d.getTime())?d.toLocaleString(language==="ru"?"ru-RU":"en-GB",{day:"numeric",month:"short",year:"numeric",hour:"2-digit",minute:"2-digit"}):v;};
 const money=(v:string)=>new Intl.NumberFormat(language==="ru"?"ru-RU":"en-GB",{style:"currency",currency:"RUB",maximumFractionDigits:2}).format(Number(v));
 const status=(r:Result<unknown>)=>busy?text("Проверяем…","Checking…"):r.state==="unavailable"?text("Недоступно","Unavailable"):denied?text("Доступ закрыт","Access denied"):text("Не проверено","Not checked");
 const work=value(sources.work),decisions=value(sources.decisions),risks=value(sources.risks),finance=value(sources.finance),crm=value(sources.crm),inbox=value(sources.inbox),queue=value(sources.tasks);
 const activeTasks=queue?.items.filter(x=>x.evidence_mode==="live"&&x.group!=="informational"&&x.group!=="recent-outcome")??[];
 const due=(x:ControlRow)=>x.due_or_trigger.kind==="exact"?fmt(x.due_or_trigger.value):x.due_or_trigger.value;
 const pending=decisions?.filter(x=>x.recorded_state==="preparing")??[];
 const linked=new Set(work?.owner_action.map(x=>x.id)??[]);
 const financePanel=<section className="exec-panel"><header><h2>{mode==="finance"?text("Финансовый снимок","Financial snapshot"):text("Финансы","Finances")}</h2>{mode!=="finance"&&<a href="/finance">{text("Подробнее","Details")}</a>}</header>
 <p className="exec-muted">{text("Банк и бухгалтерия не подключены","Bank and accounting not connected")}</p>
 {finance?<><div className="exec-money">{money(finance.conditional_inflow.contract_price_rub)}</div><p>{text("Цена контракта · поступление условное","Contract price · conditional inflow")}</p><div className="exec-facts"><span>{text("Остаток","Cash balance")}<strong>—</strong></span><span>{text("Платежи","Payments")}<strong>—</strong></span><span>{text("Прибыль","Profit")}<strong>—</strong></span></div>
 <details><summary>{text("Условия и ограничения","Terms and limitations")}</summary><p>{finance.conditional_inflow.timing_condition}</p><p>{text("Фактические поступления и дебиторская задолженность не подтверждены.","Actual receipts and receivables not confirmed.")}</p><p>{text("11 финансовых показателей не установлены.","11 financial facts unknown.")}</p><p>{finance.next_control_point}</p><p>{fmt(finance.report_as_of)}</p><details><summary>{text("Источники","Sources")}</summary>{[...finance.conditional_inflow.source_refs,...finance.unknowns].map((s,i)=><p key={i}>{s}</p>)}</details></details>
 </>:<p role="status">{status(sources.finance)}</p>}</section>;
 function controlRow(x:ControlRow){
  const decision=pending.find(d=>d.linked_work===x.id);
  return <details className="exec-row" key={x.id}><summary><span><strong>{x.title}</strong><small>{decision?text("Решение готовится · не готово к утверждению","Decision in preparation · not ready"):text("Открытая работа · решение не подготовлено","Open work · decision not ready")}</small></span><span className="exec-date">{due(x)}</span></summary><p>{x.next_control_point}</p>{decision&&<><p>{decision.question}</p><p>{decision.constraints}</p></>}<details><summary>{text("Основания","Evidence")}</summary><p>{x.id} · {x.accountable_position} · {fmt(x.evidence_as_of)}</p>{x.source_refs.map((s,i)=><p key={i}>{s}</p>)}</details></details>;
 }
 return <section className="executive">
 <header className="exec-head"><div><h1>{mode==="finance"?text("Финансы","Finances"):mode==="work"?text("Работа","Work"):text("Обзор компании","Company overview")}</h1><p>{checked?text("Запрос выполнен ","Requested ")+fmt(checked.toISOString()):text("Сведения из разрешённых источников по запросу.","Admitted sources on request.")}</p></div><button className="exec-primary" disabled={busy||!csrfToken} onClick={()=>void refresh()}>{busy?text("Проверяем…","Checking…"):text("Обновить сводку","Read summary")}</button></header>
 {denied&&<p className="exec-warning" role="alert">{text("Доступ не подтверждён. Сведения скрыты; повторите проверку.","Access not confirmed. Details hidden; try again.")}</p>}
 {mode!=="finance"&&<>
 <div className="exec-warning" role="status">{text("Покрытие частичное: отсутствие записей не означает отсутствие работ, рисков или обязательств компании.","Partial coverage: missing records do not mean there is no work, risk or obligation.")}</div>
 <section className="exec-panel"><header><h2>{text("Обязательства под контролем","Commitments to monitor")}</h2><a href="/control-details">{text("Реестры","Registers")}</a></header>
 {work?work.obligation_signals.map(x=><details className="exec-row" key={x.id}><summary><span><strong>{x.title}</strong><small>{text("Приоритетный контроль · исполнение не подтверждено","Priority monitoring · completion unconfirmed")}</small><small>{due(x)}</small></span><span className="exec-priority">{text("Высший приоритет","Top priority")}</span></summary><p>{due(x)}</p><p>{x.next_control_point}</p><details><summary>{text("Основания","Evidence")}</summary><p>{x.id} · {x.accountable_position} · {fmt(x.evidence_as_of)}</p>{x.source_refs.map((s,i)=><p key={i}>{s}</p>)}</details></details>):<p>{status(sources.work)}</p>}
 </section>
 <div className="exec-columns"><section className="exec-panel"><header><h2>{text("Решения и следующие шаги","Decisions and next steps")}</h2></header>
 {work?work.owner_action.map(controlRow):<p>{status(sources.work)}</p>}
 {pending.filter(x=>!x.linked_work||!linked.has(x.linked_work)).map(x=><details className="exec-row" key={x.id}><summary>{x.title} · {text("Готовится","Preparing")}</summary><p>{x.question}</p><p>{x.constraints}</p></details>)}
 {!decisions&&<p className="exec-muted">{text("Решения: ","Decisions: ")}{status(sources.decisions)}</p>}
 {queue?<><p className="exec-muted">{text("Операционная очередь: ","Operational queue: ")}{queue.health.state==="fresh"?activeTasks.length:text("требуется проверка","needs review")}</p>{queue.health.state==="fresh"&&(mode==="work"?activeTasks:activeTasks.slice(0,3)).map(x=><p key={x.id}><a href={x.open_href}>{x.title}</a></p>)}</>:<p className="exec-muted">{text("Операционная очередь: ","Operational queue: ")}{status(sources.tasks)}</p>}
 <a href="/my-work">{text("Операционные задачи","Operational tasks")}</a>
 </section>{mode==="overview"&&<section className="exec-panel"><header><h2>{text("Риски","Risks")}</h2><a href="/control-details">{text("Реестр","Register")}</a></header>
 {risks?[...risks].sort((a,b)=>a.priority.localeCompare(b.priority)).map(r=><details className="exec-row" key={r.id}><summary><strong>{r.title}</strong><span className="exec-priority">{r.priority==="P0"?text("Высший","Top"):text("Высокий","High")}</span></summary><p>{r.risk_statement}</p><p>{r.residual_exposure}</p><p>{r.next_control_point}</p><details><summary>{text("Основания","Evidence")}</summary><p>{r.control_evidence}</p><p>{r.review_trigger}</p>{r.source_refs.map((s,i)=><p key={i}>{s}</p>)}<p>{r.linked_work.join(", ")}</p></details></details>):<p>{status(sources.risks)}</p>}
 {risks&&<p className="exec-muted">{text("Открытые риски, не приняты. Актуальность требует проверки.","Open risks, not accepted. Current applicability unverified.")}</p>}
 </section>}</div>
 </>}
 {mode!=="work"&&<div className="exec-columns">{financePanel}{mode==="overview"&&<section className="exec-panel"><header><h2>{text("Изменения и клиенты","Changes and clients")}</h2><a href="/information-hub">{text("Входящие","Inbox")}</a></header>
 <div className="exec-signal"><a href="/crm">{text("Следующие контакты","Follow-ups")}</a><strong>{crm?crm.items.length:status(sources.crm)}</strong></div>
 {crm?.items.slice(0,3).map(x=><p key={x.opportunity_id}>{x.party_name} · {x.next_action}</p>)}
 <div className="exec-signal"><span>{text("Изменения ожидают просмотра","Changes pending review")}</span><strong>{inbox?inbox.pending_count:status(sources.inbox)}</strong></div>
 {inbox&&<p className="exec-muted">{text("Актуальные сохранённые наблюдения: ","Current saved observations: ")}{inbox.sources.filter(s=>s.state==="current-source-backed"&&s.freshness==="current-observation").length}/{inbox.sources.length}. {text("Не новый сбор.","Not a new collection.")}</p>}
 <a href="/projects">{text("Портфель проектов","Project portfolio")}</a>
 </section>}</div>}
 {mode==="work"&&<div className="exec-panel"><a href="/operations">{text("Операционные очереди и продукты","Operational queues and products")}</a> · <a href="/information-hub">{text("Входящие и закупки","Inbox and procurement")}</a></div>}
 </section>;
}
