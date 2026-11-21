import {useEffect,useRef,useState} from "react";
import {useWorkspaceLanguage} from "./i18n";
import {parseControl,type ControlRow} from "./CompanyControlReference";
import {parseDecision} from "./DecisionReference";
import {parseRisk} from "./RiskReference";
import {parseFinance} from "./FinanceReference";
import {FinanceStructure} from "./FinanceStructure";
import {OperatingCadence} from "./OperatingCadence";
import {OwnerProjectQueue,parseOwnerQueue} from "./OwnerProjectQueue";
import {OwnerBusinessBrief} from "./OwnerBusinessBrief";
import {OwnerPortfolioTrafficLight} from "./OwnerPortfolioTrafficLight";
import {parseCRM,parseInbox} from "./ControlReferenceSummary";
import type {MyWorkProjection} from "./types";
import "./Executive.css";

type Result<T>={state:"unchecked"|"unavailable"|"denied"}|{state:"ready";value:T};
type Sources={work:Result<ReturnType<typeof parseControl>>;decisions:Result<ReturnType<typeof parseDecision>>;risks:Result<ReturnType<typeof parseRisk>>;finance:Result<ReturnType<typeof parseFinance>>;crm:Result<ReturnType<typeof parseCRM>>;inbox:Result<ReturnType<typeof parseInbox>>;tasks:Result<MyWorkProjection>;ownerQueue:Result<ReturnType<typeof parseOwnerQueue>>};
const empty=():Sources=>({work:{state:"unchecked"},decisions:{state:"unchecked"},risks:{state:"unchecked"},finance:{state:"unchecked"},crm:{state:"unchecked"},inbox:{state:"unchecked"},tasks:{state:"unchecked"},ownerQueue:{state:"unchecked"}});
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
 const [busy,setBusy]=useState(false),[checked,setChecked]=useState<Date|null>(null),[denied,setDenied]=useState(false),[showEvidence,setShowEvidence]=useState(false);
 const gen=useRef(0);
 useEffect(()=>{gen.current++;setSources(empty());setChecked(null);setDenied(false);setBusy(false);setShowEvidence(false);return()=>{gen.current++;};},[csrfToken,mode]);
 async function refresh(){
  if(!csrfToken)return;
  const n=++gen.current;setBusy(true);setSources(empty());setDenied(false);setChecked(null);
  let next=empty();
  if(mode==="finance")next.finance=await read("company-finance-reference",parseFinance,csrfToken);
  else{
   const [work,decisions,risks,finance,crm,inbox,taskView,ownerQueue]=await Promise.all([
    read("company-control-reference",parseControl,csrfToken),read("company-decision-reference",parseDecision,csrfToken),mode==="overview"?read("company-risk-reference",parseRisk,csrfToken):Promise.resolve(empty().risks),
    mode==="overview"?read("company-finance-reference",parseFinance,csrfToken):Promise.resolve(empty().finance),
    mode==="overview"?read("crm/followups",parseCRM):Promise.resolve(empty().crm),mode==="overview"?read("roadmap-inbox",parseInbox):Promise.resolve(empty().inbox),read("my-work",parseTasks),mode==="overview"?read("company-owner-project-queue",parseOwnerQueue,csrfToken):Promise.resolve(empty().ownerQueue),
   ]);
   next={work,decisions,risks,finance,crm,inbox,tasks:taskView,ownerQueue};
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
 const admittedControls=new Map([...(work?.owner_action??[]),...(work?.obligation_signals??[]),...(work?.position_work??[])].map(x=>[x.id,x]));
 const relatedRisks=(id:string)=>risks?.filter(r=>r.linked_work.includes(id));
 const historical=decisions?.filter(d=>d.recorded_state!=="preparing");
 const activeTasks=queue?.items.filter(x=>x.evidence_mode==="live"&&x.group!=="informational"&&x.group!=="recent-outcome")??[];
 const due=(x:ControlRow)=>x.due_or_trigger.kind==="exact"&&x.due_or_trigger.value?fmt(x.due_or_trigger.value):x.due_or_trigger.value;
 const pending=decisions?.filter(x=>x.recorded_state==="preparing")??[];
 const linked=new Set(work?.owner_action.map(x=>x.id)??[]);
 // A successful read is not a business status, and a missing source is not a zero.
 const readResults=mode==="finance"?[sources.finance]:mode==="work"?[sources.work,sources.decisions,sources.tasks]:Object.values(sources);
 const readyCount=readResults.filter(r=>r.state==="ready").length;
 const projects=value(sources.ownerQueue);
 const unknown=text("Не установлено","Unknown");
 const criticalCount=work?.obligation_signals.length;
 const readyDecisions=decisions?0:null; // admitted decision parser requires decision_ready=false
 const headline=(v:number|null|undefined)=>v==null?unknown:String(v);
 const dueStatus=(x:ControlRow)=>{
  if(x.due_or_trigger.kind!=="exact"||!x.due_or_trigger.value||!checked)return null;
  const timestamp=Date.parse(x.due_or_trigger.value);
  if(!Number.isFinite(timestamp))return null;
  return timestamp<=checked.getTime()?text("Контрольный срок наступил · состояние исполнения не подтверждено","Review deadline reached · completion unconfirmed"):text("Контрольный срок ещё не наступил","Review deadline not yet reached");
 };
 const followupStatus=(state:string)=>{
  switch(state){
   case "past_due":return text("Срок контакта прошёл","Contact date passed");
   case "due_now":return text("Контакт сейчас","Contact due now");
   case "scheduled":return text("Запланирован","Scheduled");
   case "unscheduled":return text("Дата не задана","Unscheduled");
   case "paused":return text("На паузе","Paused");
   default:return text("Не проверено","Not checked");
  }
 };
 const unscheduled=crm?.items.filter(x=>x.status==="unscheduled").length;
 const overdue=crm?.items.filter(x=>x.status==="past_due").length;
 const nextPoint=(x:ControlRow)=><span className="exec-next-point"><b>{text("Следующий контроль: ","Next check: ")}</b>{x.next_control_point}</span>;
 const financePanel=<section className="exec-panel" id="exec-finance"><header><h2>{mode==="finance"?text("Финансовый снимок","Financial snapshot"):text("Финансы","Finances")}</h2>{mode!=="finance"&&<a href="/finance">{text("Подробнее","Details")}</a>}</header>
 <p className="exec-muted">{text("Банк и бухгалтерия не подключены","Bank and accounting not connected")}</p>
 {finance?<><div className="exec-money">{money(finance.conditional_inflow.contract_price_rub)}</div><p>{text("Цена контракта · поступление условное","Contract price · conditional inflow")}</p><div className="exec-facts"><span>{text("Остаток","Cash balance")}<strong>—</strong></span><span>{text("Платежи","Payments")}<strong>—</strong></span><span>{text("Прибыль","Profit")}<strong>—</strong></span></div>
 <details><summary>{text("Условия и ограничения","Terms and limitations")}</summary><p>{finance.conditional_inflow.timing_condition}</p><p>{text("Фактические поступления и дебиторская задолженность не подтверждены.","Actual receipts and receivables not confirmed.")}</p><p>{text("11 финансовых показателей не установлены.","11 financial facts unknown.")}</p><p>{finance.next_control_point}</p><p>{fmt(finance.report_as_of)}</p><details><summary>{text("Источники","Sources")}</summary>{[...finance.conditional_inflow.source_refs,...finance.unknowns].map((s,i)=><p key={i}>{s}</p>)}</details></details>
 </>:<p role="status">{status(sources.finance)}</p>}</section>;
 function controlRow(x:ControlRow){
  const decision=pending.find(d=>d.linked_work===x.id);
  const decisionState=decision?text("Решение готовится · не готово к утверждению","Decision in preparation · not ready"):decisions?text("Связанное решение в допущенном реестре не найдено","Linked decision not found in admitted register"):text("Сведения о решении недоступны","Decision information unavailable");
  return <details className="exec-row" key={x.id}><summary><span><strong>{x.title}</strong><small>{decisionState}</small><small>{dueStatus(x)}</small>{nextPoint(x)}</span><span className="exec-date">{due(x)}</span></summary>
   {decision&&<><p>{text("Вопрос к решению: ","Decision question: ")}{decision.question}</p><p>{text("Условия: ","Constraints: ")}{decision.constraints}</p><p>{text("Основание для пересмотра: ","Review trigger: ")}{decision.review_trigger}</p>{decision.review_due_at&&<p>{text("Контроль решения: ","Decision review: ")}{fmt(decision.review_due_at)}</p>}<p>{text("Решение не принято. Здесь доступен только просмотр.","No decision has been made. This view is read-only.")}</p></>}
   <details><summary>{text("Основания","Evidence")}</summary><p>{x.id} · {x.accountable_position} · {fmt(x.evidence_as_of)}</p>{decision&&<p>{decision.id} · {decision.capacity} · {decision.authority_basis}</p>}{x.source_refs.map((s,i)=><p key={i}>{s}</p>)}</details></details>;
 }
 return <section className="executive">
 <header className="exec-head"><div><h1>{mode==="finance"?text("Финансы","Finances"):mode==="work"?text("Работа","Work"):text("Обзор компании","Company overview")}</h1><p>{checked?text("Запрос выполнен ","Requested ")+fmt(checked.toISOString()):text("Сведения из разрешённых источников по запросу.","Admitted sources on request.")}</p></div><button className="exec-primary" disabled={busy||!csrfToken} onClick={()=>void refresh()}>{busy?text("Проверяем…","Checking…"):text("Обновить сводку","Read summary")}</button></header>
 {mode==="overview"&&<OwnerPortfolioTrafficLight data={projects} state={sources.ownerQueue.state} checked={checked}/>}
 {mode==="overview"&&<details className="traffic-context"><summary>{text("Договоры, клиенты, деньги и контрольные сроки","Contracts, sales, cash and checkpoints")}</summary><OwnerBusinessBrief work={work} decisions={decisions} risks={risks} finance={finance} crm={crm} projects={projects} checked={checked}/></details>}
 {mode==="overview"&&<button className="owner-evidence-toggle" aria-expanded={showEvidence} onClick={()=>setShowEvidence(x=>!x)}>{showEvidence?text("Скрыть технические реестры","Hide technical registers"):text("Проверочные данные и источники (для аудита)","Technical records and evidence (audit)")}</button>}
 <div className={mode==="overview"&&!showEvidence?"owner-evidence-hidden":undefined} aria-hidden={mode==="overview"&&!showEvidence?true:undefined}>
 {checked&&<p className="exec-muted exec-read-coverage" role="status">{text("Прочитаны источники: ","Sources read: ")}{readyCount}/{readResults.length}. {text("Это состояние запроса, не полнота реестров компании.","Request status, not completeness of company registers.")}</p>}
 {denied&&<p className="exec-warning" role="alert">{text("Доступ не подтверждён. Сведения скрыты; повторите проверку.","Access not confirmed. Details hidden; try again.")}</p>}
 {mode==="overview"&&<nav className="exec-overview-grid" aria-label={text("Главные показатели","Key control signals")}>
 <a className="exec-overview-tile" href="#exec-obligations"><span>{text("Обязательства","Commitments")}</span><strong>{headline(criticalCount)}</strong><small>{text("Под контролем · не подтверждённое исполнение","Monitored · completion unconfirmed")}</small></a>
 <a className="exec-overview-tile" href="#exec-decisions"><span>{text("Решения собственника","Owner decisions")}</span><strong>{headline(readyDecisions)}</strong><small>{decisions?text("Готовых в допущенном реестре; готовятся: ","Ready in admitted register; preparing: ")+pending.length:text("Реестр не прочитан","Register not read")}</small></a>
 <a className="exec-overview-tile" href="#exec-risks"><span>{text("Риски","Risks")}</span><strong>{headline(risks?.length)}</strong><small>{text("В допущенном реестре · актуальность требует сверки","Admitted register · current applicability unverified")}</small></a>
 <a className="exec-overview-tile" href="#exec-finance"><span>{text("Доступные деньги","Available cash")}</span><strong className="exec-unknown">{unknown}</strong><small>{finance?text("Цена контракта не равна остатку","Contract price is not cash"):text("Финансовый источник не прочитан","Financial source not read")}</small></a>
 <a className="exec-overview-tile" href="#exec-projects"><span>{text("Проекты и действия","Projects and actions")}</span><strong>{projects?projects.counts.projects+" / "+projects.counts.actions:unknown}</strong><small>{projects?text("Подготовка и сверка: ","Preparation and review: ")+(projects.counts.queues.prepare_within_existing_envelope+projects.counts.queues.read_only_reconciliation)+text(" · Блокеры: "," · Blocked: ")+projects.counts.queues.blocked:text("Источник не прочитан","Source not read")}</small></a>
 </nav>}
 {mode!=="finance"&&<>
 <div className="exec-warning" role="status">{text("Покрытие частичное: отсутствие записей не означает отсутствие работ, рисков или обязательств компании.","Partial coverage: missing records do not mean there is no work, risk or obligation.")}</div>
 <section id="exec-obligations" className="exec-panel"><header><h2>{text("Обязательства под контролем","Commitments to monitor")}</h2><a href="/control-details">{text("Реестры","Registers")}</a></header>
 {work&&<p className="exec-muted">{text("Контроль исполнения. Ответственная Position указана в основаниях; это не список личных поручений собственнику.","Execution monitoring. Accountable Position is in evidence; these are not personal Owner assignments.")}</p>}
 {work?work.obligation_signals.map(x=><details className="exec-row" key={x.id}><summary><span><strong>{x.title}</strong><small>{text("Приоритетный контроль · исполнение не подтверждено","Priority monitoring · completion unconfirmed")}</small><small>{text("Срок / условие: ","Due / condition: ")}{due(x)}</small><small>{text("Ответственная Position: ","Accountable Position: ")}{x.accountable_position}</small>{nextPoint(x)}{mode==="overview"&&relatedRisks(x.id)?.length?<small>{text("Связанные риски: ","Linked risks: ")}{relatedRisks(x.id)?.map(r=>r.id).join(", ")}</small>:null}</span><span className="exec-priority">{text("Высший приоритет","Top priority")}</span></summary><details><summary>{text("Основания","Evidence")}</summary><p>{x.id} · {x.accountable_position} · {fmt(x.evidence_as_of)}</p>{x.source_refs.map((s,i)=><p key={i}>{s}</p>)}</details></details>):<p>{status(sources.work)}</p>}
 </section>
 <div className="exec-columns"><section id="exec-decisions" className="exec-panel"><header><h2>{text("Решения и следующие шаги","Decisions and next steps")}</h2><a href="/control-details">{text("Реестр решений","Decision register")}</a></header>
 {work&&<p className="exec-muted">{text("Работа собственника по допущенному реестру, не новые поручения.","Owner work from admitted register, not new assignments.")}</p>}
 {work?work.owner_action.map(controlRow):<p>{status(sources.work)}</p>}
 {historical&&<p className="exec-muted">{text("Исторические решения и согласования в допущенном реестре: ","Historical decisions and approvals in admitted register: ")}{historical.length}. {text("Не новое разрешение; применимость не подтверждена.","Not new authorization; applicability unconfirmed.")}</p>}
 {decisions&&<p className="exec-muted">{text("Эскалации: сведения не допущены; полнота неизвестна.","Escalations: not admitted; completeness unknown.")}</p>}
 {pending.filter(x=>!x.linked_work||!linked.has(x.linked_work)).map(x=><details className="exec-row" key={x.id}><summary>{x.title} · {text("Готовится · не готово к утверждению","Preparing · not ready for approval")}</summary>{x.linked_work&&<p>{text("Связанная работа недоступна в текущей сводке: ","Linked work unavailable in current summary: ")}{x.linked_work}</p>}<p>{x.question}</p><p>{x.constraints}</p>{x.review_due_at&&<p>{text("Контроль решения: ","Decision review: ")}{fmt(x.review_due_at)}</p>}</details>)}
 {!decisions&&<p className="exec-muted">{text("Решения: ","Decisions: ")}{status(sources.decisions)}</p>}
 <div className="exec-operational"><h3>{text("Операционные задачи","Operational tasks")}</h3><p className="exec-muted">{text("Отдельная очередь исполнения, не реестр решений собственника.","Separate execution queue, not the Owner decision register.")}</p>
 {queue?<><p className="exec-muted">{text("Операционная очередь: ","Operational queue: ")}{queue.health.state==="fresh"?activeTasks.length:text("требуется проверка","needs review")}</p>{queue.health.state==="fresh"&&(mode==="work"?activeTasks:activeTasks.slice(0,3)).map(x=><p key={x.id}><a href={x.open_href}>{x.title}</a></p>)}</>:<p className="exec-muted">{text("Операционная очередь: ","Operational queue: ")}{status(sources.tasks)}</p>}
 <a href="/my-work">{text("Открыть операционные задачи","Open operational tasks")}</a></div>
 </section>{mode==="overview"&&<section id="exec-risks" className="exec-panel"><header><h2>{text("Риски","Risks")}</h2><a href="/control-details">{text("Реестр","Register")}</a></header>
 {risks?[...risks].sort((a,b)=>a.priority.localeCompare(b.priority)).map(r=><details className="exec-row" key={r.id}><summary><span><strong>{r.title}</strong><small>{r.id} · {r.position}</small><small>{text("Снижение риска · принятие не подтверждено","Risk reduction · acceptance not established")}</small><span className="exec-risk-next">{text("Следующая проверка: ","Next review: ")}{r.next_control_point}</span></span><span className="exec-priority">{r.priority==="P0"?text("Высший","Top"):text("Высокий","High")}</span></summary><p>{r.risk_statement}</p><p>{r.residual_exposure}</p><p>{r.next_control_point}</p><details><summary>{text("Основания","Evidence")}</summary><p>{r.control_evidence}</p><p>{r.review_trigger}</p>{r.source_refs.map((s,i)=><p key={i}>{s}</p>)}<p>{text("Связанные работы и обязательства","Linked work and obligations")}</p>
 {r.linked_work.map(id=><p key={id}>{id} · {admittedControls.get(id)?.title??text("Связанная запись не допущена или недоступна","Linked record not admitted or unavailable")}</p>)}
 <p className="exec-muted">{text("Связь не подтверждает выполнение работы или закрытие риска.","A link does not establish completion or risk closure.")}</p></details></details>):<p>{status(sources.risks)}</p>}
 {risks&&<p className="exec-muted">{text("Открытые риски, не приняты. Актуальность требует проверки.","Open risks, not accepted. Current applicability unverified.")}</p>}
 {risks&&<p className="exec-muted">{text("Исключения и инциденты: сведения не допущены; полнота неизвестна.","Exceptions and incidents: not admitted; completeness unknown.")}</p>}
 </section>}</div>
 </>}
 {mode!=="finance"&&work?.position_work&&<section className="exec-panel"><header><h2>{text("Работы ответственных должностей","Accountable Position work")}</h2><a href="/control-details">{text("Реестр","Register")}</a></header>
 <p className="exec-muted">{text("Работы компании, не новые договорные обязательства, не доказательство делегирования и не решения собственника.","Company work, not new contractual obligations, proven delegation or Owner decisions.")}</p>
 {work.position_work.map(x=><details className="exec-row" key={x.id}><summary><span><strong>{x.title}</strong><small>{x.id} · {x.accountable_position} · {x.priority}</small><small>{text("Срок не задан · состояние требует сверки","No deadline set · status needs verification")}</small>{nextPoint(x)}</span></summary>
 <details><summary>{text("Основания","Evidence")}</summary><p>{fmt(x.evidence_as_of)}</p>{x.source_refs.map((s,i)=><p key={i}>{s}</p>)}</details></details>)}
 </section>}
 {mode==="overview"&&<section className="exec-panel"><header><h2>{text("Делегированная работа и наблюдение","Delegated work and watch")}</h2><a href="/my-work">{text("Операционные задачи","Operational tasks")}</a></header>
 <p className="exec-muted">{text("Назначение ответственной должности само по себе не подтверждает делегирование. Реестр действующих назначений и ожиданий внешнего ответа в эту сводку не допущен.","An accountable position alone does not establish delegation. Current assignments and external-wait states are not admitted to this summary.")}</p>
 <p>{text("Покрытие делегированной работы: не установлено.","Delegated-work coverage: unknown.")}</p>
 </section>}
 {mode!=="work"&&<div className="exec-columns">{financePanel}{mode==="overview"&&<section className="exec-panel"><header><h2>{text("Портфель, возможности и изменения","Portfolio, opportunities and changes")}</h2><a href="/information-hub">{text("Входящие","Inbox")}</a></header>
 <div className="exec-signal"><a href="/crm">{text("Следующие контакты","Follow-ups")}</a><strong>{crm?crm.items.length:status(sources.crm)}</strong></div>
 {crm&&<><p className="exec-muted">{text("Дата не задана: ","Unscheduled: ")}{unscheduled} · {text("Срок контакта прошёл: ","Contact date passed: ")}{overdue}</p>
 {crm.items.length===0&&<p>{text("В допущенной очереди нет следующих контактов.","No follow-ups in the admitted queue.")}</p>}
 {crm.items.slice(0,3).map(x=><article className="exec-followup" key={x.opportunity_id}><strong>{x.party_name}</strong><p>{x.title}</p><p>{x.next_action}</p><small>{followupStatus(x.status)}{x.next_contact_at?" · "+fmt(x.next_contact_at):""}</small></article>)}
 {crm.items.length>3&&<p><a href="/crm">{text("Открыть все контакты: ","Open all follow-ups: ")}{crm.items.length}</a></p>}
 <p className="exec-muted">{text("Состояние очереди на ","Queue as of ")}{fmt(crm.as_of)}. {text("Не новые обязательства или решения собственника.","Not new commitments or Owner decisions.")}</p></>}
 <p className="exec-muted">{text("Решения AC-405 о приоритетах и инвестициях не допущены в эту сводку; изменения дорожной карты не означают пересмотр портфеля.","AC-405 priority and investment decisions are not admitted here; roadmap changes do not imply portfolio re-ranking.")}</p>
 <div className="exec-signal"><a href="/information-hub?view=changes">{text("Изменения ожидают просмотра","Changes pending review")}</a><strong>{inbox?inbox.pending_count:status(sources.inbox)}</strong></div>
 {inbox&&<p className="exec-muted">{text("Актуальные сохранённые наблюдения: ","Current saved observations: ")}{inbox.sources.filter(s=>s.state==="current-source-backed"&&s.freshness==="current-observation").length}/{inbox.sources.length}. {text("Не новый сбор.","Not a new collection.")}</p>}
 {inbox&&inbox.backup_status!=="verified"&&<p className="exec-warning" role="status">{text("Резервная копия очереди требует проверки.","Inbox backup needs review.")}</p>}
 {inbox&&inbox.sources.some(s=>s.freshness!=="current-observation")&&<p className="exec-warning" role="status">{text("Есть источники, требующие проверки актуальности.","Some sources need a freshness check.")}</p>}
 {inbox&&inbox.excluded_sources.length>0&&<p className="exec-muted">{text("Исключено из мониторинга: ","Excluded from monitoring: ")}{inbox.excluded_sources.length}</p>}
 {inbox?.collector&&<details className="exec-row"><summary>{text("Локальный сборщик","Local collector")} · {text("состояние","state")}: {inbox.collector.run_state}</summary>
 <p>{text("Последний сервисный сбор: ","Last service scan: ")}{inbox.collector.last_service_scan_at?fmt(inbox.collector.last_service_scan_at):"—"}</p>
 <p>{text("Последняя проверенная запись: ","Last verified persistence: ")}{inbox.collector.last_verified_at?fmt(inbox.collector.last_verified_at):"—"}</p>
 <p>{text("Следующее допустимое окно (не гарантия запуска): ","Next eligible window (not a guaranteed run): ")}{inbox.collector.next_window_at?fmt(inbox.collector.next_window_at):"—"}</p>
 <p>{text("Резервная копия: ","Backup: ")}{inbox.backup_status}</p>
 {inbox.sources.filter(s=>s.freshness!=="current-observation").map(s=><p key={s.source_id}>{s.source_id} · {s.state} · {text("требуется проверка","needs review")}</p>)}
 <p>{text("События: ","Events: ")}{inbox.collector.event_count}/500 · {inbox.collector.bytes}/2097152 {text("байт","bytes")}</p>
 {inbox.collector.capacity_warning&&<p role="alert">{text("Хранилище близко к лимиту","Storage nearing capacity")}</p>}
 <p>{text("Полномочия до: ","Authority expires: ")}{inbox.collector.expires_at?fmt(inbox.collector.expires_at):"—"}</p></details>}
 <a href="/projects">{text("Портфель проектов","Project portfolio")}</a>
 </section>}</div>}
 {mode==="overview"&&<OwnerProjectQueue data={projects} state={sources.ownerQueue.state}/>}
 {mode==="finance"&&finance&&<FinanceStructure finance={finance}/>}
 {mode==="overview"&&<OperatingCadence/>}
 {mode==="overview"&&<section className="exec-panel"><header><h2>{text("Доказательства работы системы","Reference-implementation evidence")}</h2></header>
 <p className="exec-muted">{text("Только подтверждённые технические наблюдения в этой сводке. Не оценка зрелости, автономности или экономии времени.","Only verified technical observations in this summary. Not a maturity, autonomy or time-saving score.")}</p>
 {inbox?.collector?<><p>{text("Последний подтверждённый сбор: ","Last verified collection: ")}{inbox.collector.last_verified_at?fmt(inbox.collector.last_verified_at):text("Не установлен","Unknown")}</p><p>{text("Состояние сборщика: ","Collector state: ")}{inbox.collector.run_state} · {text("Резервная копия: ","Backup: ")}{inbox.backup_status}</p></>:<p>{text("Сведения о сервисном сборе: ","Service collection evidence: ")}{inbox?text("Не установлено","Unknown"):status(sources.inbox)}</p>}
 <p>{text("Фактическое использование собственником, экономия времени и результативность AI не измеряются этим экраном.","Actual Owner use, time savings and AI effectiveness are not measured by this screen.")}</p>
 </section>}
 </div>
 {mode==="work"&&<div className="exec-panel"><a href="/operations">{text("Операционные очереди и продукты","Operational queues and products")}</a> · <a href="/information-hub">{text("Входящие и закупки","Inbox and procurement")}</a></div>}
 </section>;
}
