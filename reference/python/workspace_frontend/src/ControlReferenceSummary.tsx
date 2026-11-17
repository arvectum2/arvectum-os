import {useEffect,useRef,useState} from "react";
import {useWorkspaceLanguage} from "./i18n";

type Followup={opportunity_id:string;title:string;party_name:string;next_action:string;next_contact_at:string|null;status:string};
type RoadmapItem={id:string;source_id:string;repository:string;detected_at:string;state:string};
type Source={source_id:string;state:string;freshness:string};
type CRM={items:Followup[];as_of:string};
type Inbox={items:RoadmapItem[];sources:Source[];coverage:string;pending_count:number;backup_status:string};
type Result<T>={state:"unknown"|"unavailable"|"denied"}|{state:"ready";value:T};

function record(v:unknown):Record<string,unknown>{
 if(!v||typeof v!=="object"||Array.isArray(v))throw Error("shape");
 return v as Record<string,unknown>;
}
function str(v:unknown):v is string{return typeof v==="string"&&v.length>0&&v.length<=1000;}
function stamp(v:unknown):v is string{return str(v)&&Number.isFinite(Date.parse(v));}
function base(v:unknown){const d=record(v);if(d.derived!==true||d.canonical_authority!==false||d.organizational_authority_provided!==false)throw Error("scope");return d;}
function crm(v:unknown):CRM{
 const d=base(v);
 if(d.company_control_coverage!=="unknown"||!stamp(d.as_of)||!Array.isArray(d.items)||d.items.length>500)throw Error("shape");
 const seen=new Set<string>();
 const items=d.items.map((v:unknown)=>{
  const r=record(v);
  if(!str(r.opportunity_id)||seen.has(r.opportunity_id)||!str(r.title)||!str(r.party_name)||!str(r.next_action)||
   (r.next_contact_at!==null&&!stamp(r.next_contact_at))||!str(r.status)||!["past_due","due_now","scheduled","unscheduled","paused"].includes(r.status)||r.authority_provided!==false)throw Error("shape");
  seen.add(r.opportunity_id);
  return {opportunity_id:r.opportunity_id,title:r.title,party_name:r.party_name,next_action:r.next_action,next_contact_at:r.next_contact_at,status:r.status};
 });
 return {as_of:d.as_of,items};
}
function inbox(v:unknown):Inbox{
 const d=base(v);
 if(!str(d.coverage)||!["partial","unknown"].includes(d.coverage)||!Array.isArray(d.items)||d.items.length>500||
  !Array.isArray(d.sources)||d.sources.length>10||!Number.isInteger(d.pending_count)||!str(d.backup_status))throw Error("shape");
 const ids=new Set<string>();
 const sources=d.sources.map((v:unknown)=>{
  const s=record(v);
  if(!str(s.source_id)||ids.has(s.source_id)||!str(s.state)||!str(s.freshness)||
    !["current-source-backed","cached-source-backed","stale-cache","unavailable","reconciliation-required"].includes(s.state)||
    !["current-observation","requires-refresh"].includes(s.freshness))throw Error("shape");
  ids.add(s.source_id);
  return {source_id:s.source_id,state:s.state,freshness:s.freshness};
 });
 const seen=new Set<string>();
 const items=d.items.map((v:unknown)=>{
  const r=record(v);
  if(!str(r.id)||seen.has(r.id)||!str(r.source_id)||!ids.has(r.source_id)||!str(r.repository)||!stamp(r.detected_at)||!str(r.state)||
   !["pending","reviewed","dismissed"].includes(r.state)||r.canonical_authority!==false)throw Error("shape");
  seen.add(r.id);
  return {id:r.id,source_id:r.source_id,repository:r.repository,detected_at:r.detected_at,state:r.state};
 });
 if(d.pending_count!==items.filter(r=>r.state==="pending").length)throw Error("count");
 return {items,sources,coverage:d.coverage,pending_count:d.pending_count as number,backup_status:d.backup_status};
}
async function read<T>(path:string,parse:(v:unknown)=>T):Promise<Result<T>>{
 try{
  const r=await fetch(path,{credentials:"same-origin",cache:"no-store",headers:{"X-Arvectum-Workspace-Release":__ARVECTUM_WORKSPACE_RELEASE__}});
  if(r.status===401||r.status===403)return {state:"denied"};
  if(!r.ok)return {state:"unavailable"};
  return {state:"ready",value:parse(await r.json())};
 }catch{return {state:"unavailable"};}
}
export function ControlReferenceSummary({onDenied}:{onDenied:()=>void}){
 const {text}=useWorkspaceLanguage();
 const [followups,setCRM]=useState<Result<CRM>>({state:"unknown"});
 const [changes,setInbox]=useState<Result<Inbox>>({state:"unknown"});
 const [busy,setBusy]=useState(false);
 const gen=useRef(0);
 useEffect(()=>()=>{gen.current++;},[]);
 async function load(){
  const n=++gen.current;setBusy(true);setCRM({state:"unknown"});setInbox({state:"unknown"});
  const [a,b]=await Promise.all([read("/api/app/v1/crm/followups",crm),read("/api/app/v1/roadmap-inbox",inbox)]);
  if(n!==gen.current)return;
  setBusy(false);
  if(a.state==="denied"||b.state==="denied"){onDenied();return;}
  setCRM(a);setInbox(b);
 }
 const status:Record<string,[string,string]>={past_due:["Срок контакта прошёл","Contact date passed"],due_now:["Контакт сейчас","Contact due now"],scheduled:["Запланирован","Scheduled"],unscheduled:["Дата не задана","Unscheduled"],paused:["На паузе","Paused"]};
 return <section className="company-card"><h2>{text("Рабочие сигналы","Work signals")}</h2>
 <p>{text("Справочный просмотр допущенных источников. Не реестр обязательств, не поручение и не решение собственника.","Reference-only view of admitted sources. Not an obligation register, assignment or owner decision.")}</p>
 <button disabled={busy} onClick={()=>void load()}>{text("Проверить рабочие сигналы","Check work signals")}</button>
 <p>{text("Проверка читает последние сохранённые наблюдения; не запускает сбор данных.","Reads last stored observations; does not start collection.")}</p>
 <h3>{text("CRM — следующие контакты","CRM — follow-ups")}</h3>
 {followups.state==="ready"?<>
 <p>{text("Время проверки","Checked at")}: {followups.value.as_of}</p>
 {followups.value.items.length===0&&<p>{text("В допущенной CRM нет открытых сделок. Полнота компании неизвестна.","No open opportunities in admitted CRM. Company-wide coverage unknown.")}</p>}
 {followups.value.items.map(r=><article key={r.opportunity_id}><h4>{r.title} · {r.party_name}</h4><p>{text(...status[r.status])} {r.next_contact_at??""}</p><p>{r.next_action}</p></article>)}
 </>:<p>{followups.state==="unavailable"?text("Источник недоступен; состояние неизвестно.","Source unavailable; status unknown."):text("Ещё не проверено.","Not checked yet.")}</p>}
 <a href="/crm">{text("Открыть CRM","Open CRM")}</a>
 <h3>{text("Изменения дорожных карт","Roadmap changes")}</h3>
 {changes.state==="ready"?<>
 <p>{changes.value.coverage==="unknown"?text("Первое наблюдение ещё не выполнено.","First observation not run."):text("Ожидают просмотра: ","Pending review: ")+changes.value.pending_count}</p>
 <p>{text("Свежие наблюдения: ","Fresh observations: ")}{changes.value.sources.filter(s=>s.state==="current-source-backed"&&s.freshness==="current-observation").length}/{changes.value.sources.length}</p>
 {changes.value.sources.filter(s=>s.state!=="current-source-backed"||s.freshness!=="current-observation").map(s=><p key={s.source_id}>{s.source_id} · {text("требует проверки источника","source requires review")}</p>)}
 {changes.value.backup_status!=="verified"&&<p role="alert">{text("Резервная копия очереди требует проверки.","Inbox backup needs review.")}</p>}
 {changes.value.items.filter(r=>r.state==="pending").map(r=><article key={r.id}><h4>{r.repository}</h4><p>{r.detected_at} · {text("Влияние на бизнес ещё не оценено.","Business impact not assessed.")}</p></article>)}
 </>:<p>{changes.state==="unavailable"?text("Источник недоступен; состояние неизвестно.","Source unavailable; status unknown."):text("Ещё не проверено.","Not checked yet.")}</p>}
 <a href="/information-hub">{text("Открыть очередь и реестр закупок","Open inbox and procurement reference")}</a>
 </section>;
}
