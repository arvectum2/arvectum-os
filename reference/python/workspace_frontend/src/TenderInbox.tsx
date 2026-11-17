import {useEffect,useRef,useState} from "react";
import {useWorkspaceLanguage} from "./i18n";

type Group={id:string;case_ref:string;run_ref:string;project_id:string;event_ids:string[];review_signal:boolean;revision:number;state:string;reviewed_at:string|null};
type Item={id:string;kind:string;occurred_at:string};
type View={coverage:string;pending_count:number;backup_status:string;groups:Group[];events:Item[];observation:{state:string;since:string;until:string;checked_at:string}|null};
const root="/api/app/v1/tender-inbox";
const requestKey=()=>Array.from(crypto.getRandomValues(new Uint8Array(16)),n=>n.toString(16).padStart(2,"0")).join("");
async function request(path="",init:RequestInit={}){
 const h=new Headers(init.headers);h.set("X-Arvectum-Workspace-Release",__ARVECTUM_WORKSPACE_RELEASE__);
 if(init.body)h.set("Content-Type","application/json");
 const r=await fetch(root+path,{...init,headers:h,credentials:"same-origin"});
 if(!r.ok)throw Error(String(r.status));return r;
}
export function TenderInbox({csrfToken}:{csrfToken:string}){
 const {text,language}=useWorkspaceLanguage();
 const [data,setData]=useState<View|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(""),[opened,setOpened]=useState(false),[all,setAll]=useState(false),[warning,setWarning]=useState(false);
 const generation=useRef(0),pending=useRef<{op:string;body:Record<string,unknown>}|null>(null);
 useEffect(()=>()=>{generation.current++;},[]);
 const date=(value:string)=>new Date(value).toLocaleString(language==="ru"?"ru-RU":"en-GB");
 async function load(){
  const n=++generation.current;setBusy(true);setData(null);setError("");
  try{const v=await (await request()).json();if(!Array.isArray(v.groups)||!Array.isArray(v.events))throw Error("invalid");
   if(n===generation.current)setData(v);
  }catch{if(n===generation.current){setData(null);setError("unavailable");}}
  finally{if(n===generation.current)setBusy(false);}
 }
 async function mutate(op:string,fields:Record<string,unknown>){
  if(busy)return;
  let p=pending.current;
  if(!p||p.op!==op||JSON.stringify({...p.body,key:""})!==JSON.stringify({key:"",...fields}))p={op,body:{key:requestKey(),...fields}};
  pending.current=p;const n=++generation.current;setBusy(true);setError("");
  try{
   const v=await (await request("/"+op,{method:"POST",headers:{"X-Arvectum-CSRF":csrfToken},body:JSON.stringify(p.body)})).json();
   if(n===generation.current){pending.current=null;setWarning(v.backup_status!=="verified");await load();}
  }catch(e){if(n===generation.current){setData(null);setError(e instanceof Error&&["401","403","503"].includes(e.message)?"unavailable":"retry");}}
  finally{if(n===generation.current)setBusy(false);}
 }
 async function exportData(){
  const n=++generation.current;setBusy(true);setError("");
  try{const b=await (await request("/export")).blob();if(n!==generation.current)return;const u=URL.createObjectURL(b);try{const a=document.createElement("a");a.href=u;a.download="tender-inbox-private.json";a.click();}finally{URL.revokeObjectURL(u);}}
  catch{if(n===generation.current){setData(null);setError("unavailable");}}
  finally{if(n===generation.current)setBusy(false);}
 }
 return <section className="company-card"><h2>{text("События закупок","Tender events")}</h2>
  {!opened?<button onClick={()=>{setOpened(true);void load();}}>{text("Открыть события закупок","Open tender events")}</button>:<>
   {error==="unavailable"&&<p role="alert">{text("Источник закупок недоступен или ещё не подключён. Данные скрыты.","Tender source unavailable or not connected. Data hidden.")}</p>}
   {error==="retry"&&<p role="alert">{text("Результат операции не подтверждён. Повторите тот же запрос.","Operation not confirmed. Retry the same request.")}</p>}
   <button disabled={busy} onClick={()=>void load()}>{text("Обновить события закупок","Refresh tender events")}</button>
   {error==="retry"&&pending.current&&<button disabled={busy} onClick={()=>{const p=pending.current;if(p){const {key:_,...fields}=p.body;void mutate(p.op,fields);}}}>{text("Повторить запрос закупок","Retry tender request")}</button>}
   {data&&<>
    {(warning||data.backup_status!=="verified")&&<p role="alert">{text("Резервная копия событий требует проверки.","Tender backup needs review.")}</p>}
    <p>{data.coverage==="unknown"?text("Первая проверка ещё не выполнена.","First scan not yet run."):text("Групп к просмотру: ","Groups to review: ")+data.pending_count}</p>
    {data.observation&&<p>{text("Последняя проверка","Last observation")}: {date(data.observation.checked_at)}. {text("Просмотренный период","Observed interval")}: {date(data.observation.since)} — {date(data.observation.until)}.</p>}
    {data.observation?.state==="overflow"&&<p role="alert">{text("Слишком много событий в периоде. Источник требует отдельной проверки; новые события не получены.","Observation overflow. Source needs review; no new rows received.")}</p>}
    <p>{text("Сводка неполная и не подтверждает текущий статус закупки или необходимость решения собственника.","Partial observation, not current procurement status or an Owner decision.")}</p>
    <button disabled={busy} onClick={()=>void mutate("poll",{})}>{text("Получить события за 24 часа","Get events from last 24 hours")}</button>
    <button disabled={busy} onClick={()=>void exportData()}>{text("Экспорт событий закупок","Export tender events")}</button>
    <label><input type="checkbox" checked={all} onChange={e=>setAll(e.target.checked)}/>{text("Показать обработанные закупки","Show reviewed tender groups")}</label>
    {data.groups.filter(g=>all||g.state==="pending").map(g=><article className="company-card" key={g.id}>
      <h3>{g.review_signal?text("Требуется просмотр анализа","Analysis review signal"):text("Анализ закупки завершён","Tender analysis completed")}</h3>
      <p>{text("Связанных событий","Related events")}: {g.event_ids.length}. {text("Актуальное решение по закупке не определено.","Current bid decision is unknown.")}</p>
      {data.events.filter(e=>g.event_ids.includes(e.id)).map(e=><p key={e.id}>{e.kind==="review_required"?text("Сигнал проверки","Review signal"):text("Анализ завершён","Analysis completed")} · {date(e.occurred_at)}</p>)}
      <details><summary>{text("Исходные идентификаторы","Source references")}</summary><p>{text("Закупка","Case")}: {g.case_ref}</p><p>{text("Анализ","Run")}: {g.run_ref}</p><p>{text("Проект","Project")}: {g.project_id}</p></details>
      <a href="/projects">{text("Открыть проекты","Open projects")}</a>
      {g.state==="pending"?<div><button disabled={busy} onClick={()=>void mutate("review",{item_id:g.id,expected_revision:g.revision,state:"reviewed"})}>{text("Просмотрено","Reviewed")}</button>
      <button disabled={busy} onClick={()=>void mutate("review",{item_id:g.id,expected_revision:g.revision,state:"dismissed"})}>{text("Пропустить","Dismiss")}</button></div>:<p>{g.state==="reviewed"?text("Просмотрено","Reviewed"):text("Пропущено","Dismissed")}</p>}
    </article>)}
   </>}
  </>}
 </section>;
}
