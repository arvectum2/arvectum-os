import {useMemo,useState} from "react";
import {useWorkspaceLanguage} from "./i18n";
import type {OwnerQueue} from "./OwnerProjectQueue";

export type TrafficColor="critical"|"working"|"verified"|"paused";
type TrafficRow={label:string;color:TrafficColor;sourceAsOf:string;reason:string;next:string;hasBlocker:boolean;steps:{queue:string;action:string;ref:string}[];stage:string;protective:boolean};
const technical=/\b(?:POS|WORK|OBL|RSK|DEC|APR|ESC|WSF|AC|MC|TZ|PORT|AS|LAB|DP|BR|AW)[-_–]?\d+[A-Za-z0-9._-]*/gi;
const technicalCheck=new RegExp(technical.source,"i");
const queueOrder=["read_only_reconciliation","prepare_within_existing_envelope","blocked","watch","hold"];
function safeText(raw:string){const useful=raw.split(";").filter(part=>!technicalCheck.test(part));const source=useful.length?useful.join(";"):raw;const s=source.replaceAll("Read-only", "Без изменения данных").replaceAll("receipts", "подтверждения").replaceAll("runtime", "рабочую среду").replaceAll("evidence", "доказательства").replaceAll("roadmap", "дорожную карту").replaceAll("QA", "проверку качества").replace(technical, "упомянутый пункт").replace(/\s+/g," ").trim();return s||"Уточнить следующий шаг по исходным материалам.";}
function projectName(title:string,name:string){return title===name||title.startsWith(name+" — ")||title.startsWith(name+":");}
export function buildTrafficRows(data:OwnerQueue):TrafficRow[]{
 const protection=data.sections.find(x=>x.key==="protect_now")?.entries??[];
 const delegated=data.sections.find(x=>x.key==="delegated_work")?.entries??[];
 const rows=data.projects.map((project,sourceIndex)=>{
  const steps=data.items.filter(x=>x.project===project.label);
  const protectedSignal=protection.find(x=>projectName(x.title,project.label));
  const hasBlocker=steps.some(x=>x.queue==="blocked");
  const hardStop=/\bNO-GO\b|\bblocked\b|заблокирован|запрещ[её]н/i.test(project.stage);
  const allPaused=steps.length>0&&steps.every(x=>x.queue==="hold");
  // A task-level blocker does not prove an overall company-critical state.
  const color:TrafficColor=protectedSignal||hardStop?"critical":allPaused?"paused":"working";
  const ordered=[...steps].sort((a,b)=>queueOrder.indexOf(a.queue)-queueOrder.indexOf(b.queue));
  const reviewedNext=protectedSignal?.next??delegated.find(x=>projectName(x.title,project.label))?.next;
  const next=safeText(reviewedNext??ordered[0]?.action??"Уточнить следующий результат в источнике.");
  const reason=protectedSignal?safeText(protectedSignal.title.slice(project.label.length).replace(/^\s*[—:-]\s*/,"")):hardStop?"Зафиксирован запрет или блокирующее условие":allPaused?"Работа приостановлена":hasBlocker?"Есть отдельный блокирующий шаг":"Есть открытые действия";
  return {label:project.label,color,sourceAsOf:project.source_as_of,reason,next,hasBlocker,steps:ordered.map(x=>({queue:x.queue,action:x.action,ref:x.ref})),stage:project.stage,protective:!!protectedSignal,sourceIndex};
 });
 const rank:Record<TrafficColor,number>={critical:0,working:1,verified:2,paused:3};
 return rows.sort((a,b)=>rank[a.color]-rank[b.color]||Number(b.protective)-Number(a.protective)||a.sourceIndex-b.sourceIndex).map(({sourceIndex,...row})=>row);
}
export function trafficAge(asOf:string,now:Date){const date=/^\d{4}-\d{2}-\d{2}$/.test(asOf)?new Date(asOf+"T00:00:00Z"):new Date(NaN);if(!Number.isFinite(date.getTime())||date.toISOString().slice(0,10)!==asOf)return null;const current=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate());return current<date.getTime()?null:Math.floor((current-date.getTime())/86400000);}
const ru:Record<TrafficColor,string>={critical:"Требует внимания",working:"В работе",verified:"Подтверждено",paused:"На паузе"};
const en:Record<TrafficColor,string>={critical:"Needs attention",working:"In progress",verified:"Verified",paused:"On hold"};
export function OwnerPortfolioTrafficLight({data,state,checked}:{data:OwnerQueue|null;state:string;checked:Date|null}){
 const {language,text}=useWorkspaceLanguage();const [filter,setFilter]=useState<TrafficColor|"all">("all");const [open,setOpen]=useState<string[]>([]);
 const rows=useMemo(()=>data?buildTrafficRows(data):[],[data]);
 const count=(color:TrafficColor)=>rows.filter(r=>r.color===color).length;
 const selected=rows.filter(x=>filter==="all"||x.color===filter);
 const age=data?trafficAge(data.as_of,new Date()):null;
 const title=(x:TrafficColor)=>language==="ru"?ru[x]:en[x];
 const asOf=data?new Intl.DateTimeFormat(language==="ru"?"ru-RU":"en-GB",{day:"numeric",month:"long",year:"numeric",timeZone:"UTC"}).format(new Date(data.as_of+"T12:00:00Z")):null;
 return <section className="traffic-panel" aria-label={text("Светофор всех проектов компании","Company project traffic light")}>
 <header className="traffic-header"><div><h2>{text("Светофор проектов","Project traffic light")}</h2><p>{text("Состояние каждого проекта и следующий шаг — на одном экране.","Every project status and next step, in one view.")}</p></div><a href="/projects">{text("Проекты и история","Projects and history")}</a></header>
 {data?<>
 <div className="traffic-freshness" role="status"><strong>{text("Данные на ","Data dated ")}{asOf}</strong><span>{age==null?text("Возраст данных неизвестен","Age unknown"):age===0?text("Снимок сегодняшней даты","Snapshot dated today"):text("Снимок за прошлую дату · ","Older snapshot · ")+age+text(" дн."," days")}</span><small>{text("«Обновить сводку» повторно читает утверждённый снимок, а не новые изменения репозиториев. Цвет не означает приёмку работы.","Refresh rereads the approved snapshot, not new repository commits. Colors do not imply acceptance.")}</small></div>
 <div className="traffic-stats" aria-label={text("Сводка по состояниям","Status totals")}>
 {(["all","critical","working","verified","paused"] as const).map(value=><button key={value} type="button" aria-pressed={filter===value} className={"traffic-stat traffic-stat-"+value} onClick={()=>setFilter(value)}><strong>{value==="all"?rows.length:count(value)}</strong><span>{value==="all"?text("Все проекты","All projects"):title(value)}</span></button>)}
 </div>
 <p className="traffic-explainer">{text("Красный — срочный контроль или общий запрет. Жёлтый — работа не закрыта (в том числе с отдельным блокером). Серый — пауза. Зелёный требует подтверждённой приёмки; её в этом источнике нет.","Red means urgent attention or a project-level stop. Yellow is open work, including individual blockers. Gray is a hold. Green requires verified acceptance, unavailable in this source.")}</p>
 <div className="traffic-table" role="table" aria-label={text("Проекты и открытые действия","Projects and open actions")}>
 <div role="row" className="traffic-head-row"><span role="columnheader">{text("Проект","Project")}</span><span role="columnheader">{text("Состояние","Status")}</span><span role="columnheader">{text("Следующий шаг","Next step")}</span><span role="columnheader">{text("Подробнее","Details")}</span></div>
 {selected.map(item=>{const expanded=open.includes(item.label);return <div role="rowgroup" key={item.label} className="traffic-group">
 <div role="row" className="traffic-data-row"><div role="cell" className="traffic-project"><strong>{item.label}</strong>{item.hasBlocker&&item.color!=="critical"&&<small>{text("Есть отдельный блокер","One task is blocked")}</small>}</div><div role="cell"><span className={"traffic-status traffic-status-"+item.color}><i aria-hidden="true"/>{title(item.color)}</span><small className="traffic-reason">{item.reason}</small></div><div role="cell" className="traffic-next"><p>{item.next}</p></div><div role="cell" className="traffic-actions"><button type="button" aria-expanded={expanded} onClick={()=>setOpen(existing=>expanded?existing.filter(x=>x!==item.label):[...existing,item.label])}>{expanded?text("Свернуть","Close"):text("Все шаги","All steps")} · {item.steps.length}</button></div></div>
 {expanded&&<div role="row" className="traffic-expanded"><div role="cell"><p><strong>{text("Открытые действия по снимку","Actions in the source snapshot")}</strong></p><ol>{item.steps.map(s=><li key={s.ref}>{safeText(s.action)}</li>)}</ol><p>{text("Первоначальный статус: ","Original stage: ")}{item.stage}</p><p>{text("Сведения на ","Dated ")}{item.sourceAsOf}. {text("Не является подтверждением исполнения или решением собственника.","Not completion evidence or Owner approval.")}</p></div></div>}
 </div>})}</div>
 {selected.length===0&&<p className="traffic-empty">{text("В этом снимке нет проектов данной категории. Это не подтверждает отсутствие рисков или завершение работы.","No such projects in this snapshot. This does not establish absence of risk or completion.")}</p>}
 <footer className="traffic-footer"><span>{text("Показано ","Showing ")}{selected.length}{text(" из "," of ")}{rows.length}{text(" проектов · сохранено открытых действий: "," projects · open references preserved: ")}{data.counts.actions}</span><span>{text("Подтверждённых готовых решений собственника: ","Decision-ready Owner items: ")}{data.counts.decision_ready_owner_items}. {text("Решения принимаются отдельно.","Approvals are separate.")}</span></footer>
 </>:<p role="status" className="traffic-unavailable">{state==="unchecked"?text("Нажми «Обновить сводку», чтобы получить статусы.","Refresh to read project statuses."):text("Утверждённый источник недоступен. Статусы неизвестны.","Approved source unavailable. Status unknown.")}</p>}
 </section>;
}
