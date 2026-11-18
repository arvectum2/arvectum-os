import {useEffect,useRef,useState} from "react";
import {useWorkspaceLanguage} from "./i18n";

type Item={id:string;source_id:string;repository:string;path:string;observed:{commit_sha:string};previous:{commit_sha:string};detected_at:string;state:string;revision:number};
type Data={coverage:string;pending_count:number;backup_status:string;items:Item[];sources:{source_id:string;freshness:string}[];excluded_sources?:{source_id:string;freshness:string}[]};
const root="/api/app/v1/roadmap-inbox";
const key=()=>Array.from(crypto.getRandomValues(new Uint8Array(16)),n=>n.toString(16).padStart(2,"0")).join("");
function link(r:Item,sha:string){
 if(!/^arvectum2\/[A-Za-z0-9_.-]+$/.test(r.repository)||!/^[-a-zA-Z0-9_./ ]+\.md$/.test(r.path)||r.path.split("/").some(x=>!x||x==="."||x==="..")||!(/^[a-f0-9]{40}$/).test(sha))return null;
 return "https://github.com/"+r.repository+"/blob/"+sha+"/"+r.path.split("/").map(encodeURIComponent).join("/");
}
async function request(path="",init:RequestInit={}){
 const h=new Headers(init.headers);h.set("X-Arvectum-Workspace-Release",__ARVECTUM_WORKSPACE_RELEASE__);
 if(init.body)h.set("Content-Type","application/json");
 const r=await fetch(root+path,{...init,headers:h,credentials:"same-origin",cache:"no-store"});
 if(!r.ok)throw Error(String(r.status));return r;
}
export function RoadmapInbox({csrfToken,openOnEntry=false}:{csrfToken:string;openOnEntry?:boolean}){
 const {text}=useWorkspaceLanguage();
 const [data,setData]=useState<Data|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(""),[all,setAll]=useState(false);
 const [opened,setOpened]=useState(openOnEntry),[warning,setWarning]=useState(false);
 const gen=useRef(0),pending=useRef<{operation:string;body:Record<string,unknown>}|null>(null);
 useEffect(()=>{
  gen.current++;setData(null);setError("");setWarning(false);setAll(false);setBusy(false);pending.current=null;
  setOpened(openOnEntry);
  // StrictMode's setup/cleanup replay must not cause a duplicate GET.
  const entry=gen.current;
  if(openOnEntry&&csrfToken)queueMicrotask(()=>{if(gen.current===entry)void load();});
  return()=>{gen.current++;};
 },[csrfToken,openOnEntry]);
 async function load(){
  const n=++gen.current;setBusy(true);setData(null);setError("");
  try{const d=await (await request()).json();if(!Array.isArray(d.items)||!Array.isArray(d.sources))throw Error("invalid");if(n===gen.current)setData(d);}
  catch{if(n===gen.current){setData(null);setError("unavailable");}}
  finally{if(n===gen.current)setBusy(false);}
 }
 async function mutate(operation:string,fields:Record<string,unknown>){
  if(busy)return;
  let p=pending.current;
  if(!p||p.operation!==operation||JSON.stringify({...p.body,key:""})!==JSON.stringify({key:"",...fields}))p={operation,body:{key:key(),...fields}};
  pending.current=p;
  const n=++gen.current;setBusy(true);setError("");
  try{
   const d=await (await request("/"+operation,{method:"POST",headers:{"X-Arvectum-CSRF":csrfToken},body:JSON.stringify(p.body)})).json();
   if(n===gen.current){pending.current=null;setWarning(d.backup_status!=="verified");await load();}
  }catch(e){if(n===gen.current){if(e instanceof Error&&["401","403"].includes(e.message)){setData(null);setError("unavailable");}else {setData(null);setError("retry");}}}
  finally{if(n===gen.current)setBusy(false);}
 }
 async function exportData(){
  const n=++gen.current;setBusy(true);setError("");
  try{const b=await (await request("/export")).blob();if(n!==gen.current)return;const u=URL.createObjectURL(b);try{const a=document.createElement("a");a.href=u;a.download="roadmap-inbox-private.json";a.click();}finally{URL.revokeObjectURL(u);}}
  catch{if(n===gen.current){setData(null);setError("unavailable");}}
  finally{if(n===gen.current)setBusy(false);}
 }
 return <section className="company-card"><h2>{text("Изменения в проектах","Project changes")}</h2>
  {!opened?<button disabled={!csrfToken} onClick={()=>{setOpened(true);void load();}}>{text("Открыть очередь изменений","Open change inbox")}</button>:<>
   {error==="unavailable"&&<p role="alert">{text("Очередь недоступна или не активирована. Данные скрыты.","Inbox unavailable or not activated. Data hidden.")}</p>}
   {error==="retry"&&<p role="alert">{text("Результат операции не подтверждён. Повторите ту же операцию.","Operation not confirmed. Retry the same request.")}</p>}
   <button disabled={busy||!csrfToken} onClick={()=>void load()}>{text("Обновить очередь","Refresh inbox")}</button>
   {busy&&<p role="status">{text("Читаем сохранённую очередь…","Reading saved inbox…")}</p>}
   {error==="retry"&&pending.current&&<button disabled={busy} onClick={()=>{const p=pending.current;if(p){const {key:_,...fields}=p.body;void mutate(p.operation,fields);}}}>{text("Повторить операцию","Retry operation")}</button>}
   {data&&<>
    {(warning||data.backup_status!=="verified")&&<p role="alert">{text("Резервная копия требует проверки.","Backup needs review.")}</p>}
    <p>{data.coverage==="unknown"?text("Первая проверка ещё не выполнена.","First scan not yet run."):text("Ожидают просмотра: ","Pending review: ")+data.pending_count}</p>
    <p>{text("Источники, требующие проверки: ","Sources needing review: ")}{data.sources.filter(s=>s.freshness!=="current-observation").length}</p>
    {data.excluded_sources&&<p>{text("Исключено из активного мониторинга: ","Excluded from active monitoring: ")}{data.excluded_sources.length}</p>}
    <p>{text("Сохранённые наблюдения. Обновление очереди не запускает сбор GitHub.","Saved observations. Refreshing the inbox does not start a GitHub scan.")}</p>
    {data.pending_count===0&&!all&&<p role="status">{text("Нет сохранённых изменений, ожидающих просмотра.","No saved changes pending review.")}</p>}
    <details className="exec-secondary"><summary>{text("Ручной сбор и экспорт","Manual scan and export")}</summary>
    <p>{text("Ручной сбор обращается к источникам и может добавить новые наблюдения.","Manual scanning contacts sources and may add new observations.")}</p>
    <button disabled={busy||!csrfToken} onClick={()=>void mutate("poll",{})}>{text("Проверить изменения","Scan for changes")}</button>
    <button disabled={busy} onClick={()=>void exportData()}>{text("Экспорт очереди","Export inbox")}</button></details>
    <label><input type="checkbox" checked={all} onChange={e=>setAll(e.target.checked)}/>{text("Показать обработанные","Show reviewed")}</label>
    {data.items.filter(r=>all||r.state==="pending").map(r=><article key={r.id} className="company-card">
      <h3>{r.repository}</h3><p>{text("Изменение дорожной карты","Roadmap changed")} · {r.detected_at}</p>
      <p>{text("Влияние на бизнес ещё не оценено.","Business impact not yet assessed.")}</p>
      {link(r,r.observed.commit_sha)&&<a href={link(r,r.observed.commit_sha)!} target="_blank" rel="noopener noreferrer">{text("Новая версия","New version")}</a>}{" "}
      {link(r,r.previous.commit_sha)&&<a href={link(r,r.previous.commit_sha)!} target="_blank" rel="noopener noreferrer">{text("Предыдущая версия","Previous version")}</a>}
      {r.state==="pending"?<div><button disabled={busy} onClick={()=>void mutate("review",{item_id:r.id,expected_revision:r.revision,state:"reviewed"})}>{text("Просмотрено","Reviewed")}</button>
       <button disabled={busy} onClick={()=>void mutate("review",{item_id:r.id,expected_revision:r.revision,state:"dismissed"})}>{text("Пропустить","Dismiss")}</button></div>:<p>{r.state==="reviewed"?text("Просмотрено","Reviewed"):text("Пропущено","Dismissed")}</p>}
    </article>)}
   </>}
  </>}
 </section>;
}

// An explicit navigation to the focused view reads only the existing admitted
// Inbox. It never mounts portfolio or procurement providers, or starts a scan.
export function FocusedRoadmapInbox({csrfToken}:{csrfToken:string}){
 const {text}=useWorkspaceLanguage();
 return <section className="company-page hub-page" aria-labelledby="focused-inbox-title">
  <header className="company-page-head"><div><h1 id="focused-inbox-title">{text("Очередь изменений","Change inbox")}</h1>
  <p>{text("Просмотр сохранённых изменений проектов. Влияние на бизнес определяется отдельно.","Review saved project changes. Business impact is assessed separately.")}</p></div>
  <a href="/">{text("К обзору","Back to overview")}</a></header>
  <RoadmapInbox csrfToken={csrfToken} openOnEntry/>
  <p><a href="/information-hub">{text("Все входящие и источники","All incoming information and sources")}</a></p>
 </section>;
}
