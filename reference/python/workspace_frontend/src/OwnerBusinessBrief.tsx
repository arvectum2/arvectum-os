import {useState} from "react";
import {useWorkspaceLanguage} from "./i18n";
import {parseControl} from "./CompanyControlReference";
import {parseDecision} from "./DecisionReference";
import {parseRisk} from "./RiskReference";
import {parseFinance} from "./FinanceReference";
import {parseCRM} from "./ControlReferenceSummary";
import type {OwnerQueue} from "./OwnerProjectQueue";

type Props={work:ReturnType<typeof parseControl>|null;decisions:ReturnType<typeof parseDecision>|null;risks:ReturnType<typeof parseRisk>|null;finance:ReturnType<typeof parseFinance>|null;crm:ReturnType<typeof parseCRM>|null;projects:OwnerQueue|null;checked:Date|null};
type Description={goal:string;next:string;state:"prepare"|"check"|"wait"|"hold"};
// Human-readable presentation of the exact reviewed Company snapshot; not a new
// portfolio ranking, assignment, authority, approval, or claim of completion.
const REVIEWED="84135f11bc115366fa5aac4ced9db0b86dc1ff0b";
const BLOB="c4addaacf3381f789f2798d0b74cd2413a45d60e";
const meaning:Record<string,Description>={
 "Музей Хлеба":{goal:"Сдать работы заказчику по договору",next:"Сверить согласование фирменного стиля, комплект передачи и инфраструктуру.",state:"check"},
 "Балтика":{goal:"Согласовать условия пилота с заказчиком",next:"Проверить презентацию и демонстрацию; подтвердить встречу.",state:"prepare"},
 "Tender Agent":{goal:"Подтвердить пользу анализа закупок",next:"Сверить реальные кейсы и коммерческие показатели.",state:"check"},
 "MAX2TG":{goal:"Обеспечить доставку сообщений без потерь",next:"Проверить неотправленные и неопределённые сообщения.",state:"check"},
 "Proxy Launcher":{goal:"Подтвердить готовность iOS-приложения",next:"Завершить испытания на физических устройствах и сетях.",state:"check"},
 "Infrastructure":{goal:"Подготовить размещение сайта Музея Хлеба",next:"Сверить провайдера, договорные требования и стоимость.",state:"check"},
 "Arvectum Company":{goal:"Управлять обязательствами и результатами",next:"Проверить полноту и актуальность управленческих сведений.",state:"check"},
 "Arvectum OS":{goal:"Сделать рабочее пространство полезным собственнику",next:"Проверить ежедневное использование и восстановление.",state:"check"},
 "Arvectum Skills":{goal:"Не терять задачи и проверять результаты",next:"Проверить соответствие дорожных карт спецификациям.",state:"prepare"},
 "Arvectum Work":{goal:"Проверить спрос на автоматизацию закупок",next:"Подготовить проверку гипотезы до контактов с покупателями.",state:"prepare"},
 "Creative Test Agent":{goal:"Подготовить пилот анализа рекламы",next:"Проверить демонстрацию и данные, необходимые от заказчика.",state:"wait"},
 "1С Lab":{goal:"Проверить автономную работу с 1С",next:"Получить законный учебный дистрибутив.",state:"wait"},
 "Discount Parser":{goal:"Оценить перспективы продукта без клиента",next:"Сверить спрос и затраты, не возобновляя разработку.",state:"hold"},
 "Doors Parser":{goal:"Сохранить полезные наработки",next:"Оставить разработку в архиве до подтверждённого спроса.",state:"hold"},
 "Калькулятор закупок":{goal:"Сохранить архив разработки",next:"Не возобновлять без отдельного решения.",state:"hold"},
 "Data Platform":{goal:"Проверить полезность общего контура данных",next:"Провести испытания на реальных данных и проверить доступ.",state:"wait"},
 "Compliance":{goal:"Проверить безопасный запуск услуги",next:"Завершить проверку безопасности и условий публикации.",state:"check"},
 "Arvectum Tools":{goal:"Подтвердить пользу и качество приложений",next:"Собрать результаты испытаний, аналитики и отзывы.",state:"check"},
 "DealForge":{goal:"Оценить коммерческую гипотезу и права",next:"Проверить допустимость данных и экономический смысл.",state:"hold"},
 "Brand Identity":{goal:"Довести фирменный стиль Арвектума",next:"Завершить графические материалы и проверку.",state:"prepare"},
 "Корпоративный сайт":{goal:"Получать измеримые обращения с сайта",next:"Сверить реальные показатели поиска и содержание.",state:"check"},
 "ARC":{goal:"Обеспечить надёжный удалённый доступ",next:"Проверить работу и восстановление после перезапуска.",state:"check"}
};
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
 const review=!!projects&&projects.source_commit===REVIEWED&&projects.source_blob===BLOB;
 const museum=work?.obligation_signals.filter(x=>x.title.startsWith("Музей Хлеба"))??[];
 const due=museum.find(x=>x.due_or_trigger.kind==="exact"&&x.due_or_trigger.value)?.due_or_trigger.value;
 const contractCondition=museum.find(x=>x.due_or_trigger.kind==="condition"&&contractDateFromCondition(x.due_or_trigger.value,ru?"ru-RU":"en-GB"))?.due_or_trigger.value;
 const dueLabel=date(due,ru?"ru-RU":"en-GB")??contractDateFromCondition(contractCondition,ru?"ru-RU":"en-GB");
 const acceptance=museum.find(x=>x.title.includes("приемке"));
 const days=acceptance?.due_or_trigger.value?.match(/Не более (\d+) рабочих дней/);
 const contacts=crm?.items.filter(x=>x.status!=="paused")??[];
 const preparing=decisions?.filter(x=>x.recorded_state==="preparing")??[];
 const names=projects?.projects.map(x=>x.label)??[];
 const focus=["Музей Хлеба","Балтика","Tender Agent","MAX2TG","Proxy Launcher","Infrastructure"];
 const ordered=[...focus.filter(x=>names.includes(x)),...names.filter(x=>!focus.includes(x))];
 const state=(x:Description)=>x.state==="hold"?text("На паузе","On hold"):x.state==="wait"?text("Ждём условия","Waiting"):x.state==="prepare"?text("Можно подготовить","Can prepare"):text("Проверить результат","Verify outcome");
 return <section className="owner-business" aria-label={text("Состояние бизнеса","Business situation")}>
 <div className="owner-business-heading"><div><h2>{text("Что происходит с компанией","What is happening in the company")}</h2>
 <p>{checked?text("Проверены подключённые сведения; исполнение и полнота данных не гарантированы.","Connected information was read; completion and coverage are not guaranteed."):text("Обнови сводку, чтобы увидеть данные компании.","Refresh to see company data.")}</p></div>
 {projects&&<small>{text("Проекты: сведения от ","Project snapshot dated ")}{date(projects.as_of,ru?"ru-RU":"en-GB")}</small>}</div>
 <div className="owner-business-top">
 <article><span>{text("Твоё решение сейчас","Your decision now")}</span><strong>{decisions?text("Готовых вопросов нет","Nothing ready"):text("Неизвестно","Unknown")}</strong><small>{decisions?(preparing.length?text("Готовится: ","Preparing: ")+preparing[0].title:text("В проверенном реестре","In checked register")):text("Источник не прочитан","Source unavailable")}</small></article>
 <article><span>{text("Ближайший договорный срок","Next contract checkpoint")}</span><strong>{work?dueLabel??text("Уточнить","Needs review"):text("Неизвестно","Unknown")}</strong><small>{museum.length?text("Музей Хлеба · исполнение не подтверждено","Museum · completion unconfirmed"):text("Не подтверждён в этом источнике","Not established in this source")}</small></article>
 <article><span>{text("Коммерческие контакты","Sales follow-ups")}</span><strong>{crm?String(contacts.length):text("Неизвестно","Unknown")}</strong><small>{crm?text("Без даты следующего контакта: ","Without a follow-up date: ")+contacts.filter(x=>x.status==="unscheduled").length:text("Очередь недоступна","Source unavailable")}</small></article>
 <article><span>{text("Деньги на счетах","Available cash")}</span><strong>{text("Нет данных","Unknown")}</strong><small>{text("Банк и учёт не подключены","Bank/accounting not connected")}</small></article>
 </div>
 <div className="owner-business-stories">
 <article className="owner-business-story"><h3>{text("Музей Хлеба: сдать результат","Museum of Bread: deliver the result")}</h3>
 {museum.length?<><p>{text("По договору нужно завершить работы и оформить приёмку; выполнения пока никто не подтвердил.","The contracted work and acceptance remain unverified.")}</p><ol>{museum.map((m,i)=><li key={m.id}>{i===0?text("Сверить готовность результата и согласования заказчика.","Check deliverables and client approvals."):(days?text("После окончания договорного срока в течение ","Within ")+days[1]+text(" рабочих дней подготовить комплект для оформления приёмки в ЕИС."," working days after the contractual service term, prepare documents for acceptance in the procurement system."):text("После выполнения подготовить документы приёмки.","Prepare acceptance documents after completion."))}</li>)}</ol></>:<p>{text("Договорные сведения не прочитаны.","Contract information unavailable.")}</p>}
 <p className="owner-business-note">{text("Следующий результат: подтверждённый комплект сдачи.","Next outcome: a verified handover package.")}</p></article>
 <article className="owner-business-story"><h3>{text("Продажи: следующий контакт","Sales: next contact")}</h3>
 {crm?contacts.length?contacts.slice(0,4).map(c=><div className="owner-business-contact" key={c.opportunity_id}><strong>{c.party_name}</strong><p>{c.next_action}</p><small>{c.status==="unscheduled"?text("Дата не назначена","Date not set"):date(c.next_contact_at,ru?"ru-RU":"en-GB")??text("Дата требует сверки","Date needs review")}</small></div>):<p>{text("Контактов в доступной очереди нет; полнота неизвестна.","No entries in available follow-ups; coverage unknown.")}</p>:<p>{text("Коммерческая очередь недоступна.","Sales data unavailable.")}</p>}
 <a href="/crm">{text("Открыть переговоры","Open follow-ups")}</a></article>
 <article className="owner-business-story"><h3>{text("Что можно готовить без нового решения","Preparation without a new decision")}</h3>
 {review?<ul><li><strong>Балтика:</strong> {text("проверенные материалы к встрече и демонстрация.","checked meeting materials and demo.")}</li><li><strong>Tender Agent:</strong> {text("подтверждённые результаты анализа и экономика.","verified procurement results and economics.")}</li><li><strong>Workspace:</strong> {text("проверка полезности пилота в реальной работе.","validation of the pilot in actual work.")}</li></ul>:<p>{text("Актуальная очередь требует сверки.","Current work queue needs verification.")}</p>}
 <p className="owner-business-note">{text("Это возможная подготовка, не доказательство выполнения или делегирования.","Preparation candidates, not proof of execution or delegation.")}</p></article>
 <article className="owner-business-story"><h3>{text("Деньги: чего не хватает для решения","Money: missing evidence")}</h3>
 <p>{text("Остатки, расходы и реальные поступления не подтверждены. Пока нельзя оценить прибыль и денежный запас.","Balances, expenses and receipts are unverified. Profit and runway cannot be calculated.")}</p>
 {finance&&<p>{text("Цена действующего договора: ","Contract price: ")}<strong>{new Intl.NumberFormat(ru?"ru-RU":"en-GB",{style:"currency",currency:"RUB"}).format(Number(finance.conditional_inflow.contract_price_rub))}</strong>. {text("Это не полученные деньги.","This is not cash received.")}</p>}
 <p className="owner-business-note">{text("Следующий шаг: получить фактические остатки и обязательства.","Next: obtain bank balances and confirmed commitments.")}</p></article>
 </div>
 {projects?.sections.find(section=>section.key==="protect_now")?.entries.some(e=>e.title.startsWith("MAX2TG"))&&<aside className="owner-delivery-check"><strong>{text("Проверить доставку сообщений MAX2TG","Check MAX2TG message delivery")}</strong><p>{text("Есть сигнал о возможных потерях сообщений, но актуальный сбой не подтверждён. Следующий шаг — проверить очередь отправки и неопределённые сообщения без отправки тестовых сообщений.","A possible delivery loss signal needs confirmation. Review pending and uncertain messages without sending new test messages.")}</p></aside>}
 <section className="owner-project-business"><div className="owner-business-heading"><div><h3>{text("Результат по каждому направлению","Outcome for every area")}</h3><p>{text("Цель и ближайшая проверка, а не внутренние коды задач.","Business outcome and next check, not internal task codes.")}</p></div></div>
 {!projects?<p>{text("Список недоступен. Обнови сводку.","List unavailable. Refresh summary.")}</p>:<><div className="owner-project-business-list">{(all?ordered:ordered.slice(0,6)).map(name=>{const info=review?meaning[name]:undefined;return <details className="owner-business-project" key={name}><summary><span><strong>{name}</strong><small>{info?(ru?info.goal:"Business outcome needs validation"):text("Сверить актуальную цель","Verify current goal")}</small></span><em>{info?state(info):text("Не проверено","Unverified")}</em></summary><p><strong>{text("Следующий полезный результат: ","Next useful outcome: ")}</strong>{info?(ru?info.next:"Check the underlying project results and constraints."):text("Сверить статус проекта по текущим данным.","Reconcile the project state.")}</p><small>{text("Цель не подтверждает факт исполнения. Исходные задания доступны в разделе проверки.","An intended outcome is not proof of completion. Source tasks are available in evidence.")}</small></details>})}</div>
 {ordered.length>6&&<button className="owner-business-expand" onClick={()=>setAll(x=>!x)}>{all?text("Свернуть остальные направления","Collapse areas"):text("Показать остальные направления","Show remaining areas")+" ("+(ordered.length-6)+")"}</button>}</>}</section>
 {risks&&risks.length>0&&<p className="owner-business-note">{text("Открытые риски есть; их актуальность проверяется. Технические основания хранятся отдельно.","Open risks exist and need current validation. Technical evidence is available separately.")}</p>}
 </section>;
}
