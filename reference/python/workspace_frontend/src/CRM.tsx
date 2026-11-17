import { useEffect, useRef, useState } from "react";
import { useWorkspaceLanguage } from "./i18n";
import "./CompanyWorkspace.css";
import "./ManualContext.css";

type Kind = "party"|"contact"|"opportunity"|"interaction";
type RecordRow = {id:string;revision:number;recorded_at:string;authority_provided:boolean;[key:string]:unknown};
type Snapshot = Record<Kind,RecordRow[]>;
type Catalog = {projects:{id:string;label:string}[];evidence_refs:string[]};
type Command = {key:string;entity:Kind;data:Record<string,unknown>;record_id:string|null;expected_revision:number};
const root="/api/app/v1/crm";
const kinds:Kind[]=["party","contact","opportunity","interaction"];
const initial:Record<Kind,Record<string,string>>={
 party:{name:"",description:"",registry_ref:""},
 contact:{party_id:"",name:"",role:"",channel_ref:""},
 opportunity:{party_id:"",contact_id:"",title:"",stage:"discovery",next_action:"",next_contact_at:"",project_id:"",evidence_refs:"[]",outcome_ref:""},
 interaction:{party_id:"",contact_id:"",opportunity_id:"",project_id:"",kind:"meeting",occurred_at:"",summary:"",evidence_ref:""}
};
const stages=[["discovery","Первичный интерес","Discovery"],["qualified","Квалификация","Qualified"],["proposal","Предложение","Proposal"],["negotiation","Переговоры","Negotiation"],["paused","Приостановлена","Paused"],["won","Выиграна","Won"],["lost","Проиграна","Lost"]];
const channels=[["meeting","Встреча","Meeting"],["call","Звонок","Call"],["email","Письмо","Email"],["message","Сообщение","Message"],["other","Другое","Other"]];
const titleOf=(r:RecordRow)=>String(r.name??r.title??r.summary??r.id);
const nullable=["registry_ref","channel_ref","contact_id","opportunity_id","project_id","next_action","next_contact_at","outcome_ref"];
function key(){return Array.from(crypto.getRandomValues(new Uint8Array(16)),n=>n.toString(16).padStart(2,"0")).join("");}
async function request(path="",init:RequestInit={}){
 const h=new Headers(init.headers);h.set("X-Arvectum-Workspace-Release",__ARVECTUM_WORKSPACE_RELEASE__);
 if(init.body)h.set("Content-Type","application/json");
 const r=await fetch(root+path,{...init,headers:h,credentials:"same-origin"});
 if(!r.ok)throw Error(String(r.status));return r;
}

export function CRM({csrfToken}:{csrfToken:string}){
 const {text}=useWorkspaceLanguage();
 const [snapshot,setSnapshot]=useState<Snapshot|null>(null);
 const [catalog,setCatalog]=useState<Catalog|null>(null);
 const [kind,setKind]=useState<Kind>("party");
 const [draft,setDraft]=useState({...initial.party});
 const [edit,setEdit]=useState<RecordRow|null>(null);
 const [query,setQuery]=useState("");
 const [project,setProject]=useState("");
 const [detail,setDetail]=useState<{title:string;rows:RecordRow[]}|null>(null);
 const [error,setError]=useState("");
 const [busy,setBusy]=useState(true);
 const gen=useRef(0),pending=useRef<Command|null>(null);
 function clear(){setSnapshot(null);setCatalog(null);setDraft({...initial[kind]});setEdit(null);setDetail(null);setQuery("");setProject("");pending.current=null;}
 async function load(){
  const seq=++gen.current;setBusy(true);setError("");setDetail(null);
  try{
   const [s,c]=await Promise.all([request(),request("/catalog")]);
   const data=await s.json(), cat=await c.json();
   if(!kinds.every(k=>Array.isArray(data[k]))||!Array.isArray(cat.projects)||!Array.isArray(cat.evidence_refs))throw Error("invalid");
   if(seq===gen.current){setSnapshot(data);setCatalog(cat);}
  }catch{if(seq===gen.current){clear();setError("unavailable");}}
  finally{if(seq===gen.current)setBusy(false);}
 }
 useEffect(()=>{void load();return()=>{gen.current++;};},[]);
 function selectKind(k:Kind){setKind(k);setDraft({...initial[k]});setEdit(null);setDetail(null);pending.current=null;}
 function change(field:string,value:string){
  setDraft(old=>{
   const next={...old,[field]:value};
   if(field==="party_id"){if("contact_id"in next)next.contact_id="";if("opportunity_id"in next)next.opportunity_id="";}
   if(field==="stage"){if(value==="won"||value==="lost"){next.next_action="";next.next_contact_at="";}else next.outcome_ref="";}
   return next;
  });
 }
 async function submit(){
  if(!snapshot||!catalog||busy)return;
  const data:Record<string,unknown>={};
  for(const [f,v] of Object.entries(draft))data[f]=f==="evidence_refs"?JSON.parse(v):nullable.includes(f)?v||null:v;
  const value={entity:kind,data,record_id:edit?.id??null,expected_revision:edit?.revision??0};
  let cmd=pending.current;
  if(!cmd||JSON.stringify({...cmd,key:""})!==JSON.stringify({key:"",...value}))cmd={key:key(),...value};
  pending.current=cmd;
  const seq=++gen.current;setBusy(true);setError("");
  try{await request("/submit",{method:"POST",headers:{"X-Arvectum-CSRF":csrfToken},body:JSON.stringify(cmd)});
   if(seq===gen.current){pending.current=null;setEdit(null);setDraft({...initial[kind]});await load();}
  }catch(e){if(seq===gen.current){if(e instanceof Error&&["401","403"].includes(e.message)){clear();setError("unavailable");}else setError("rejected");}}
  finally{if(seq===gen.current)setBusy(false);}
 }
 async function showDetail(path:string,title:string){
  const seq=++gen.current;setBusy(true);setError("");setDetail(null);
  try{const r=await request(path);const rows=await r.json();if(!Array.isArray(rows))throw Error();if(seq===gen.current)setDetail({title,rows});}
  catch{if(seq===gen.current){clear();setError("unavailable");}}
  finally{if(seq===gen.current)setBusy(false);}
 }
 async function download(){
  const seq=++gen.current;setBusy(true);setError("");
  try{const r=await request("/export");const b=await r.blob();if(seq!==gen.current)return;
   const u=URL.createObjectURL(b);try{const a=document.createElement("a");a.href=u;a.download="arvectum-crm-private.json";a.click();}finally{URL.revokeObjectURL(u);}
  }catch{if(seq===gen.current){clear();setError("unavailable");}}
  finally{if(seq===gen.current)setBusy(false);}
 }
 function editRow(row:RecordRow){
  const next:Record<string,string>={};
  for(const f of Object.keys(initial[kind]))next[f]=f==="evidence_refs"?JSON.stringify(Array.isArray(row[f])?row[f]:[]):String(row[f]??"");
  setDraft(next);setEdit(row);pending.current=null;setDetail(null);
 }
 const labels={party:text("Контрагенты","Counterparties"),contact:text("Контакты","Contacts"),opportunity:text("Сделки","Opportunities"),interaction:text("Взаимодействия","Interactions")};
 function field(f:string,ru:string,en:string,required=true,limit=160){return <label>{text(ru,en)}<input value={draft[f]??""} disabled={busy} required={required} maxLength={limit} onChange={e=>change(f,e.target.value)}/></label>;}
 function select(f:string,ru:string,en:string,opts:[string,string][],required=false,locked=false){
  return <label>{text(ru,en)}<select value={draft[f]??""} required={required} disabled={busy||locked} onChange={e=>change(f,e.target.value)}><option value="">{text("Не выбрано","Not selected")}</option>{opts.map(([v,label])=><option key={v} value={v}>{label}</option>)}</select></label>;
 }
 const rowOpts=(rows:RecordRow[]):[string,string][]=>rows.map(r=>[r.id,titleOf(r)]);
 const refs:[string,string][]=(catalog?.evidence_refs??[]).map(r=>[r,r]);
 const projects:[string,string][]=(catalog?.projects??[]).map(p=>[p.id,p.label]);
 const finished=draft.stage==="won"||draft.stage==="lost";
 const stageLabel=(v:unknown)=>{const s=stages.find(x=>x[0]===v);return s?text(s[1],s[2]):String(v??"");};
 const matches=(r:RecordRow)=>!query.trim()||[r.name,r.title,r.summary,r.role,r.description,r.next_action].some(v=>String(v??"").toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
 const matchesProject=(r:RecordRow)=>{
  if(!project||!snapshot)return true;
  if(kind==="opportunity"||kind==="interaction")return r.project_id===project;
  return [...snapshot.opportunity,...snapshot.interaction].some(o=>o.project_id===project&&(kind==="party"?o.party_id===r.id:o.contact_id===r.id));
 };
 function rowBody(r:RecordRow){
  return <><h3>{titleOf(r)}</h3>{r.stage!==undefined&&<p>{stageLabel(r.stage)}</p>}
   {typeof r.next_action==="string"&&<p>{text("Следующее действие","Next action")}: {r.next_action}</p>}
   {typeof r.next_contact_at==="string"&&<p>{text("Следующий контакт (UTC)","Next contact (UTC)")}: {r.next_contact_at}</p>}
   {typeof r.role==="string"&&<p>{r.role}</p>}{typeof r.description==="string"&&<p>{r.description}</p>}
   {typeof r.occurred_at==="string"&&<p>{r.occurred_at}</p>}
   {typeof r.party_id==="string"&&<p>{snapshot?.party.find(p=>p.id===r.party_id)?.name as string??""}</p>}
   <p className="hub-meta">{text("Версия","Revision")} {r.revision}</p></>;
 }
 return <section className="company-page manual-context"><header className="company-page-head"><div><h1>CRM Lite</h1><p>{text("Контрагенты, сделки и история взаимодействий","Counterparties, opportunities and interactions")}</p></div><button disabled={busy} onClick={()=>void load()}>{text("Обновить","Refresh")}</button></header>
  {error==="unavailable"&&<p role="alert">{text("CRM недоступна или не активирована. Данные скрыты.","CRM unavailable or not activated. Data hidden.")}</p>}
  {error==="rejected"&&<p role="alert">{text("Запись не подтверждена. Проверьте данные и повторите ту же операцию.","Save not confirmed. Review input and retry the same operation.")}</p>}
  {!snapshot&&busy&&<p role="status">{text("Проверяем доступ…","Checking access…")}</p>}
  {snapshot&&catalog&&<>
   <p className="hub-warning">{text("Тестовый контур. Не вводите реальные персональные или конфиденциальные данные.","Test contour. Do not enter real personal or confidential data.")}</p>
   <div className="hub-filters">{kinds.map(k=><button key={k} disabled={busy} aria-pressed={kind===k} onClick={()=>selectKind(k)}>{labels[k]}</button>)}<button disabled={busy} onClick={()=>void download()}>{text("Экспорт","Export")}</button></div>
   <div className="manual-forms"><form className="company-card" onSubmit={e=>{e.preventDefault();void submit();}}>
    <h2>{edit?text("Редактировать запись","Edit record"):text("Новая запись","New record")}</h2>
    {kind==="party"?<>{field("name","Название компании","Company name")}{field("description","Описание","Description",true,1000)}{select("registry_ref","Источник реквизитов","Registry source",refs,false,!!edit?.registry_ref)}</>:<>
      {select("party_id","Контрагент","Counterparty",rowOpts(snapshot.party),true,!!edit)}
      {kind==="contact"?<>{field("name","Имя контакта","Contact name")}{field("role","Роль","Role")}{select("channel_ref","Источник контакта","Contact source",refs)}</>:<>
       {select("contact_id","Контакт","Contact",rowOpts(snapshot.contact.filter(r=>r.party_id===draft.party_id)))}
       {select("project_id","Связанный проект","Linked project",projects)}
       {kind==="opportunity"?<>{field("title","Название сделки","Opportunity title")}{select("stage","Стадия","Stage",stages.map(s=>[s[0],text(s[1],s[2])]),true)}
        {finished?select("outcome_ref","Подтверждение результата","Outcome evidence",refs,true):<>{field("next_action","Следующее действие","Next action",true,500)}{field("next_contact_at","Следующий контакт (UTC, ISO)","Next contact (UTC, ISO)",false,50)}</>}
        {<label>{text("Источники сделки","Opportunity evidence")}<select multiple disabled={busy} value={JSON.parse(draft.evidence_refs||"[]") as string[]} onChange={e=>change("evidence_refs",JSON.stringify(Array.from(e.target.selectedOptions,x=>x.value)))}>{refs.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>}</>:<>
        {select("opportunity_id","Сделка","Opportunity",rowOpts(snapshot.opportunity.filter(r=>r.party_id===draft.party_id)))}
        {select("kind","Тип взаимодействия","Interaction type",channels.map(s=>[s[0],text(s[1],s[2])]),true)}
        {field("occurred_at","Время события (UTC, ISO)","Occurrence (UTC, ISO)",true,50)}
        {field("summary","Краткое содержание","Summary",true,1500)}
        {select("evidence_ref","Источник события","Interaction evidence",refs,true,!!edit)}
       </>}
      </>}
    </>}
    <button type="submit" disabled={busy}>{text("Сохранить","Save")}</button>
    {edit&&<button type="button" disabled={busy} onClick={()=>selectKind(kind)}>{text("Отмена","Cancel")}</button>}
   </form><div className="company-card"><h2>{labels[kind]}</h2>
    <label>{text("Поиск","Search")}<input type="search" value={query} onChange={e=>setQuery(e.target.value)} maxLength={160}/></label>
    <label>{text("Проект","Project")}<select value={project} onChange={e=>setProject(e.target.value)}><option value="">{text("Все проекты","All projects")}</option>{projects.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
    {snapshot[kind].filter(r=>matches(r)&&matchesProject(r)).map(r=><article key={r.id} className="company-card">{rowBody(r)}
     <button disabled={busy} onClick={()=>editRow(r)}>{text("Редактировать","Edit")}</button>
     <button disabled={busy} onClick={()=>void showDetail("/records/"+encodeURIComponent(r.id)+"/history",text("История версий","Revision history"))}>{text("Версии","Versions")}</button>
     {kind==="party"&&<button disabled={busy} onClick={()=>void showDetail("/parties/"+encodeURIComponent(r.id)+"/timeline",text("История взаимодействия","Interaction timeline"))}>{text("История","Timeline")}</button>}
    </article>)}
   </div></div>
   {detail&&<section className="company-card"><h2>{detail.title}</h2>{detail.rows.map(r=><article key={r.id+":"+r.revision}>{rowBody(r)}</article>)}</section>}
  </>}
 </section>;
}
