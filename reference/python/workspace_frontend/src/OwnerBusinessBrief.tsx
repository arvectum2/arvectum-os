import {useState} from "react";
import {useWorkspaceLanguage} from "./i18n";
import {parseControl} from "./CompanyControlReference";
import {parseDecision} from "./DecisionReference";
import {parseRisk} from "./RiskReference";
import {parseFinance} from "./FinanceReference";
import {parseCRM} from "./ControlReferenceSummary";
import type {OwnerQueue} from "./OwnerProjectQueue";

type Props={work:ReturnType<typeof parseControl>|null;decisions:ReturnType<typeof parseDecision>|null;risks:ReturnType<typeof parseRisk>|null;finance:ReturnType<typeof parseFinance>|null;crm:ReturnType<typeof parseCRM>|null;projects:OwnerQueue|null;checked:Date|null};
// Company owns project meaning. The platform presents only approved source material,
// and leaves an explicit unknown when a business outcome was never supplied.
const human=(value:string)=>value.replaceAll("receipts","подтверждения").replaceAll("runtime","рабочую систему").replaceAll("evidence","доказательства").replaceAll("Read-only","Без изменений");
const technical=/\b(?:POS|WORK|OBL|RSK|DEC|APR|ESC|WSF|AC|MC|TZ|PORT|AS|LAB|DP|BR|AW)[-_]\d+[\w.-]*/;
const safe=(value:string)=>{const first=value.split(";")[0];return technical.test(value)?(!technical.test(first)?human(first)+".":"Следующий результат требует уточнения в исходных материалах."):human(value);};
function date(value:string|null|undefined,locale:string){
 if(!value)return null;const ms=Date.parse(value);
 return Number.isFinite(ms)?new Intl.DateTimeFormat(locale,{day:"numeric",month:"long",year:"numeric"}).format(ms):null;
}
export function contractDateFromCondition(value:string|null|undefined,locale:string){
 if(!value)return null;
 // Only the exact signed-calendar condition is promoted to a readable date.
 const match=value.match(/^По (\d{2})\.(\d{2})\.(\d{4}) включительно/);
 if(!match)return null;
 const [,day,month,year]=match;
 const dt=new Date(Date.UTC(Number(year),Number(month)-1,Number(day),12));
 if(dt.getUTCDate()!==Number(day)||dt.getUTCMonth()!==Number(month)-1||dt.getUTCFullYear()!==Number(year))return null;
 return new Intl.DateTimeFormat(locale,{day:"numeric",month:"long",year:"numeric"}).format(dt);
}
export function OwnerBusinessBrief({work,decisions,risks,finance,crm,projects,checked}:Props){
 const {language,text}=useWorkspaceLanguage(),ru=language==="ru";
 const [all,setAll]=useState(false);
 const review=!!projects; // Backend already enforces exact source hash/policy before returning.
 const client=work?.obligation_signals[0]?.title.split(" — ")[0];
 const museum=work?.obligation_signals.filter(x=>!!client&&x.title.startsWith(client+" — "))??[];
 const due=museum.find(x=>x.due_or_trigger.kind==="exact"&&x.due_or_trigger.value)?.due_or_trigger.value;
 const contractCondition=museum.find(x=>x.due_or_trigger.kind==="condition"&&contractDateFromCondition(x.due_or_trigger.value,ru?"ru-RU":"en-GB"))?.due_or_trigger.value;
 const dueLabel=date(due,ru?"ru-RU":"en-GB")??contractDateFromCondition(contractCondition,ru?"ru-RU":"en-GB");
 const acceptance=museum.find(x=>x.title.includes("приемке"));
 const days=acceptance?.due_or_trigger.value?.match(/Не более (\d+) рабочих дней/);
 const contacts=crm?.items.filter(x=>x.status!=="paused")??[];
 const preparing=decisions?.filter(x=>x.recorded_state==="preparing")??[];
 const names=projects?.projects.map(x=>x.label)??[];
 const priority=projects?.sections.filter(x=>x.key==="protect_now"||x.key==="delegated_work").flatMap(x=>x.entries)??[];
 const activeNames=priority.map(x=>names.find(name=>x.title.startsWith(name+" —"))).filter((x):x is string=>!!x);
 const ordered=[...new Set([...activeNames,...names])];
 const state=(name:string)=>{
  const actions=projects?.items.filter(x=>x.project===name)??[];
  return actions.every(x=>x.queue==="hold")?text("На паузе","On hold"):
   actions.some(x=>x.queue==="blocked")?text("Есть зависимость","Blocked"):
   actions.some(x=>x.queue==="prepare_within_existing_envelope")?text("Можно подготовить","Can prepare"):
   text("Нужна проверка","Needs review");
 };
 return <section className="owner-business" aria-label={text("Состояние бизнеса","Business situation")}>
 <div className="owner-business-heading"><div><h2>{text("Что происходит с компанией","What is happening in the company")}</h2>
 <p>{checked?text("Проверены подключённые сведения; исполнение и полнота данных не гарантированы.","Connected information was read; completion and coverage are not guaranteed."):text("Обнови сводку, чтобы увидеть данные компании.","Refresh to see company data.")}</p></div>
 {projects&&<small>{text("Проекты: сведения от ","Project snapshot dated ")}{date(projects.as_of,ru?"ru-RU":"en-GB")}</small>}</div>
 <div className="owner-business-top">
 <article><span>{text("Твоё решение сейчас","Your decision now")}</span><strong>{decisions?text("Готовых вопросов нет","Nothing ready"):text("Неизвестно","Unknown")}</strong><small>{decisions?(preparing.length?text("Готовится: ","Preparing: ")+preparing[0].title:text("В проверенном реестре","In checked register")):text("Источник не прочитан","Source unavailable")}</small></article>
 <article><span>{text("Ближайший договорный срок","Next contract checkpoint")}</span><strong>{work?dueLabel??text("Уточнить","Needs review"):text("Неизвестно","Unknown")}</strong><small>{museum.length?client+text(" · исполнение не подтверждено"," · completion unconfirmed"):text("Не подтверждён в этом источнике","Not established in this source")}</small></article>
 <article><span>{text("Коммерческие контакты","Sales follow-ups")}</span><strong>{crm?String(contacts.length):text("Неизвестно","Unknown")}</strong><small>{crm?text("Без даты следующего контакта: ","Without a follow-up date: ")+contacts.filter(x=>x.status==="unscheduled").length:text("Очередь недоступна","Source unavailable")}</small></article>
 <article><span>{text("Деньги на счетах","Available cash")}</span><strong>{text("Нет данных","Unknown")}</strong><small>{text("Банк и учёт не подключены","Bank/accounting not connected")}</small></article>
 </div>
 <div className="owner-business-stories">
 <article className="owner-business-story"><h3>{(client??text("Договор с заказчиком","Client contract"))+text(": сдать результат",": deliver the result")}</h3>
 {museum.length?<><p>{text("По договору нужно завершить работы и оформить приёмку; выполнения пока никто не подтвердил.","The contracted work and acceptance remain unverified.")}</p><ol>{museum.map((m,i)=><li key={m.id}>{i===0?text("Сверить готовность результата и согласования заказчика.","Check deliverables and client approvals."):(days?text("После окончания договорного срока в течение ","Within ")+days[1]+text(" рабочих дней подготовить комплект для оформления приёмки в ЕИС."," working days after the contractual service term, prepare documents for acceptance in the procurement system."):text("После выполнения подготовить документы приёмки.","Prepare acceptance documents after completion."))}</li>)}</ol></>:<p>{text("Договорные сведения не прочитаны.","Contract information unavailable.")}</p>}
 <p className="owner-business-note">{text("Следующий результат: подтверждённый комплект сдачи.","Next outcome: a verified handover package.")}</p></article>
 <article className="owner-business-story"><h3>{text("Продажи: следующий контакт","Sales: next contact")}</h3>
 {crm?contacts.length?contacts.slice(0,4).map(c=><div className="owner-business-contact" key={c.opportunity_id}><strong>{c.party_name}</strong><p>{c.next_action}</p><small>{c.status==="unscheduled"?text("Дата не назначена","Date not set"):date(c.next_contact_at,ru?"ru-RU":"en-GB")??text("Дата требует сверки","Date needs review")}</small></div>):<p>{text("Контактов в доступной очереди нет; полнота неизвестна.","No entries in available follow-ups; coverage unknown.")}</p>:<p>{text("Коммерческая очередь недоступна.","Sales data unavailable.")}</p>}
 <a href="/crm">{text("Открыть переговоры","Open follow-ups")}</a></article>
 <article className="owner-business-story"><h3>{text("Что можно готовить без нового решения","Preparation without a new decision")}</h3>
 {projects?.sections.find(x=>x.key==="delegated_work")?.entries.length?<ul>{projects.sections.find(x=>x.key==="delegated_work")!.entries.map((e,i)=><li key={i}><strong>{e.title}</strong> — {safe(e.next)}</li>)}</ul>:<p>{text("Сведения о подготовке требуют сверки.","Preparation status needs validation.")}</p>}
 <p className="owner-business-note">{text("Это возможная подготовка, не доказательство выполнения или делегирования.","Preparation candidates, not proof of execution or delegation.")}</p></article>
 <article className="owner-business-story"><h3>{text("Деньги: чего не хватает для решения","Money: missing evidence")}</h3>
 <p>{text("Остатки, расходы и реальные поступления не подтверждены. Пока нельзя оценить прибыль и денежный запас.","Balances, expenses and receipts are unverified. Profit and runway cannot be calculated.")}</p>
 {finance&&<p>{text("Цена действующего договора: ","Contract price: ")}<strong>{new Intl.NumberFormat(ru?"ru-RU":"en-GB",{style:"currency",currency:"RUB"}).format(Number(finance.conditional_inflow.contract_price_rub))}</strong>. {text("Это не полученные деньги.","This is not cash received.")}</p>}
 <p className="owner-business-note">{text("Следующий шаг: получить фактические остатки и обязательства.","Next: obtain bank balances and confirmed commitments.")}</p></article>
 </div>
 {projects?.sections.find(section=>section.key==="protect_now")?.entries.slice(1).map((entry,i)=><aside className="owner-delivery-check" key={i}><strong>{entry.title}</strong><p>{safe(entry.next)}</p><small>{text("Сигнал требует подтверждения. Не новый инцидент или поручение.","Signal requires confirmation; not a new incident or assignment.")}</small></aside>)}
 <section className="owner-project-business"><div className="owner-business-heading"><div><h3>{text("Результат по каждому направлению","Outcome for every area")}</h3><p>{text("Цель и ближайшая проверка, а не внутренние коды задач.","Business outcome and next check, not internal task codes.")}</p></div></div>
 {!projects?<p>{text("Список недоступен. Обнови сводку.","List unavailable. Refresh summary.")}</p>:<><div className="owner-project-business-list">{(all?ordered:ordered.slice(0,6)).map(name=>{const item=review?priority.find(x=>x.title.startsWith(name+" —")):undefined;return <details className="owner-business-project" key={name}><summary><span><strong>{name}</strong><small>{item?item.title.split(" — ").slice(1).join(" — "):text("Результат не указан в управленческой сводке","Business outcome not established in admitted source")}</small></span><em>{review?state(name):text("Не проверено","Unverified")}</em></summary><p><strong>{text("Следующий полезный результат: ","Next useful outcome: ")}</strong>{item?safe(item.next):text("Необходим содержательный результат и подтверждение текущего статуса.","A business outcome and verified current state are required.")}</p><small>{text("Цель не подтверждает факт исполнения. Исходные задания доступны в разделе проверки.","An intended outcome is not proof of completion. Source tasks are available in evidence.")}</small></details>})}</div>
 {ordered.length>6&&<button className="owner-business-expand" onClick={()=>setAll(x=>!x)}>{all?text("Свернуть остальные направления","Collapse areas"):text("Показать остальные направления","Show remaining areas")+" ("+(ordered.length-6)+")"}</button>}</>}</section>
 {risks&&risks.length>0&&<p className="owner-business-note">{text("Открытые риски есть; их актуальность проверяется. Технические основания хранятся отдельно.","Open risks exist and need current validation. Technical evidence is available separately.")}</p>}
 </section>;
}
