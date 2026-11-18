import { useEffect, useRef, useState } from "react";
import { useWorkspaceLanguage } from "./i18n";
import "./CompanyWorkspace.css";
import { RiskReference } from "./RiskReference";
import { DecisionReference } from "./DecisionReference";
import { CompanyControlReference } from "./CompanyControlReference";
import { ControlReferenceSummary } from "./ControlReferenceSummary";

type Project={id:string;label:string;kind:string};
type Note={id:string;title:string;text:string;project_id:string|null};
type Baseline={manual_context:{projects:Project[];notes:Note[]};sections:{id:string;state:string;missing_source:string}[];pilot_review?:{due_at:string;decision_ready:boolean}};
type Timeline={project:Project;events:{kind:string;at:string;record_id:string;revision?:number;title?:string;text?:string;label?:string}[]};
const root="/api/app/v1/manual-context";
async function get(path:string){
 const r=await fetch(path,{credentials:"same-origin",headers:{"X-Arvectum-Workspace-Release":__ARVECTUM_WORKSPACE_RELEASE__}});
 if(!r.ok)throw Error("unavailable");return r.json();
}
const sectionNames:Record<string,[string,string]>={"protect-now":["Критические риски","Protect now"],"owner-action":["Решения собственника","Owner action required"],"delegated-work":["Делегированная работа","Delegated work"],"cash-commitments":["Деньги и обязательства","Cash and commitments"],"portfolio-review":["Портфель и контрольные точки","Portfolio and review triggers"],"reference-evidence":["Результаты и подтверждения","Evidence and results"]};
const events:Record<string,[string,string]>={"project-created":["Проект создан","Project created"],"note-captured":["Добавлена заметка","Note captured"],"note-revised":["Заметка изменена","Note revised"],"note-linked":["Заметка привязана","Note linked"],"note-unlinked":["Заметка отвязана","Note unlinked"]};

export function MissionControl({csrfToken=""}:{csrfToken?:string}){
 const {text}=useWorkspaceLanguage();
 const [data,setData]=useState<Baseline|null>(null),[timeline,setTimeline]=useState<Timeline|null>(null);
 const [selected,setSelected]=useState(""),[error,setError]=useState(false),[busy,setBusy]=useState(true);
 const seq=useRef(0);
 async function load(){
  const n=++seq.current;setBusy(true);setError(false);setData(null);setTimeline(null);setSelected("");
  try{const d=await get(root+"/mission-control");if(!Array.isArray(d.manual_context?.projects)||!Array.isArray(d.manual_context?.notes)||!Array.isArray(d.sections))throw Error();
   if(n===seq.current)setData(d);
  }catch{if(n===seq.current){setData(null);setTimeline(null);setError(true);}}
  finally{if(n===seq.current)setBusy(false);}
 }
 useEffect(()=>{void load();return()=>{seq.current++;};},[]);
 async function show(id:string){
  setSelected(id);setTimeline(null);const n=++seq.current;if(!id)return;
  setBusy(true);setError(false);
  try{const d=await get(root+"/projects/"+encodeURIComponent(id)+"/timeline");if(d.project?.id!==id||!Array.isArray(d.events))throw Error();if(n===seq.current)setTimeline(d);}
  catch{if(n===seq.current){setData(null);setTimeline(null);setSelected("");setError(true);}}
  finally{if(n===seq.current)setBusy(false);}
 }
 return <section className="company-page"><header className="company-page-head"><div><h1>{text("Управление компанией","Mission Control")}</h1>
 <p>{text("Рабочий контекст и контрольные точки. Неподключённые источники обозначены явно.","Work context and review triggers. Unconnected sources are explicit.")}</p></div>
 <button disabled={busy} onClick={()=>void load()}>{text("Обновить","Refresh")}</button></header>
 {error&&<p role="alert">{text("Управленческие данные недоступны. Это не означает, что нет задач или рисков.","Control data unavailable. This does not mean there are no tasks or risks.")}</p>}
 {data&&<><div className="company-card"><h2>{text("Контрольные точки","Review triggers")}</h2>
 {data.pilot_review?<p>{text("Пересмотр пилота Workspace","Review Workspace pilot")} · {new Date(data.pilot_review.due_at).toLocaleString()} · {text("Решение о продолжении ещё не принято","Continuation not yet decided")}</p>:<p>{text("Нет подтверждённой контрольной точки в этом источнике.","No verified review trigger from this source.")}</p>}
 <p>{data.manual_context.projects.length} {text("проектов","projects")} · {data.manual_context.notes.length} {text("рабочих заметок","working notes")}</p>
 <a href="/crm">{text("CRM и следующие контакты","CRM and follow-ups")}</a></div>
 {csrfToken&&<CompanyControlReference key={csrfToken} csrfToken={csrfToken}/>}
 {csrfToken&&<DecisionReference key={"decision-"+csrfToken} csrfToken={csrfToken}/>}
 {csrfToken&&<RiskReference key={"risk-"+csrfToken} csrfToken={csrfToken}/>}
 <ControlReferenceSummary onDenied={()=>{seq.current++;setBusy(false);setData(null);setTimeline(null);setSelected("");setError(true);}}/>
 <div className="company-card"><h2>{text("История проекта","Project timeline")}</h2>
 <label>{text("Проект","Project")}<select value={selected} disabled={busy} onChange={e=>void show(e.target.value)}><option value="">{text("Выберите проект","Choose project")}</option>{data.manual_context.projects.map(p=><option key={p.id} value={p.id}>{p.label}</option>)}</select></label>
 {timeline&&<div>{timeline.events.map((e,i)=><article className="company-card" key={e.record_id+":"+i}><h3>{e.title||e.label}</h3><p>{text(...(events[e.kind]||[e.kind,e.kind]))} · {e.at}</p>{e.text&&<p>{e.text}</p>}</article>)}</div>}
 </div>
 <div className="company-card"><h2>{text("Разделы контроля","Control sections")}</h2>{data.sections.map(s=><article key={s.id}><h3>{text(...(sectionNames[s.id]||[s.id,s.id]))}</h3><p>{text("Нет подключённого актуального источника. Состояние неизвестно.","No admitted current source. Status unknown.")}</p></article>)}</div>
 </>}
 </section>;
}
