import {useState} from "react";
import {useWorkspaceLanguage} from "./i18n";

const queues=["prepare_within_existing_envelope","read_only_reconciliation","blocked","watch","hold"] as const;
type Queue=typeof queues[number];
type Item={project:string;ref:string;queue:Queue;action:string;source_as_of:string;trigger:string;unknowns:string[];related_control_refs:string[]};
type Subview={label:string;next:string;state:string};
type Project={label:string;stage:string;source_as_of:string;subviews:Subview[]};
type Section={key:string;entries:{title:string;next:string;qualification:string}[]};
export type OwnerQueue={schema:string;as_of:string;source_commit:string;source_blob:string;projects:Project[];items:Item[];sections:Section[];counts:{projects:number;actions:number;queues:Record<Queue,number>;decision_ready_owner_items:0}};
const record=(x:unknown):x is Record<string,unknown>=>!!x&&typeof x==="object"&&!Array.isArray(x);
const str=(x:unknown):x is string=>typeof x==="string"&&x.trim().length>0&&x.length<=4000;
const strings=(x:unknown):x is string[]=>Array.isArray(x)&&x.length<=100&&x.every(str);
const fields=(x:Record<string,unknown>,names:string[])=>names.every(k=>str(x[k]));
const sectionKeys=["protect_now","owner_action_required","delegated_work","cash_commitments","portfolio_review_triggers","reference_implementation_evidence"];
export function parseOwnerQueue(v:unknown):OwnerQueue{
 if(!record(v)||v.schema!=="arvectum.workspace.owner-project-queue/1"||v.derived!==true||
 v.canonical_authority!==false||v.organizational_authority_provided!==false||v.execution_authorized!==false||
 v.coverage!=="partial"||v.source_state!=="dated_candidate_snapshot"||!str(v.as_of)||!/^\d{4}-\d{2}-\d{2}$/.test(v.as_of)||
 !str(v.source_commit)||!/^[a-f0-9]{40}$/.test(v.source_commit)||!str(v.source_blob)||!/^[a-f0-9]{40}$/.test(v.source_blob)||
 !Array.isArray(v.projects)||!v.projects.length||v.projects.length>100||!Array.isArray(v.items)||!v.items.length||v.items.length>2000||
 !Array.isArray(v.sections)||v.sections.length!==6||!record(v.counts)||!record(v.counts.queues)||v.counts.decision_ready_owner_items!==0)throw Error("queue shape");
 const labels=new Set<string>();const itemProjects=new Set<string>();const keys=new Set<string>();const counts:Record<Queue,number>={prepare_within_existing_envelope:0,read_only_reconciliation:0,blocked:0,watch:0,hold:0};
 for(const p of v.projects){if(!record(p)||!str(p.label)||labels.has(p.label)||!fields(p,["stage","source_as_of"])||!Array.isArray(p.subviews)||p.subviews.length>30||!p.subviews.every(s=>record(s)&&fields(s,["label","next","state"])))throw Error("project");labels.add(p.label);}
 for(const i of v.items){if(!record(i)||!str(i.project)||!labels.has(i.project)||!str(i.ref)||!queues.includes(i.queue as Queue)||!fields(i,["action","source_as_of","trigger"])||!strings(i.unknowns)||!strings(i.related_control_refs))throw Error("action");
 const k=JSON.stringify([i.project,i.ref]);if(keys.has(k))throw Error("duplicate");keys.add(k);itemProjects.add(i.project);counts[i.queue as Queue]++;}
 for(const [n,s] of v.sections.entries()){if(!record(s)||s.key!==sectionKeys[n]||!Array.isArray(s.entries)||s.entries.length>100||!s.entries.every(e=>record(e)&&fields(e,["title","next","qualification"]))||(n===1&&s.entries.length))throw Error("section");}
 if(v.counts.projects!==labels.size||v.counts.actions!==keys.size||queues.some(q=>v.counts && record(v.counts)&&record(v.counts.queues)&&v.counts.queues[q]!==counts[q])||[...labels].some(p=>!itemProjects.has(p)))throw Error("counts");
 return v as unknown as OwnerQueue;
}
export function OwnerProjectQueue({data,state}:{data:OwnerQueue|null;state:string}){
 const {text}=useWorkspaceLanguage(),[filter,setFilter]=useState<Queue|"all">("all"),[project,setProject]=useState("");
 const names:Record<Queue,string>={prepare_within_existing_envelope:text("Подготовка","Preparation"),read_only_reconciliation:text("Сверка","Reconciliation"),blocked:text("Блокеры","Blocked"),watch:text("Ожидание","Waiting"),hold:text("Отложено","On hold")};
 return <section className="exec-panel"><header><h2>{text("Проекты и следующие действия","Projects and next steps")}</h2></header>
 {!data?<p role="status">{state==="unchecked"?text("Обновите сводку для чтения проектной очереди.","Read summary to check the project queue."):text("Проектная очередь не допущена или недоступна. Состояние неизвестно.","Project queue is not admitted or unavailable. Status unknown.")}</p>:<>
 <p className="exec-muted">{text("Снимок на","Snapshot dated")} {data.as_of} · {text("Частичное покрытие. Не реальное время, не поручения владельцу и не разрешение на исполнение.","Partial coverage. Not live status, Owner assignments or execution permission.")}</p>
 <div className="exec-facts"><span>{text("Проектные контуры","Project contours")}<strong>{data.counts.projects}</strong></span><span>{text("Следующие действия","Next-action references")}<strong>{data.counts.actions}</strong></span><span>{text("Требуют подготовки и сверки","Preparation and review")}<strong>{data.counts.queues.prepare_within_existing_envelope+data.counts.queues.read_only_reconciliation}</strong></span></div>
 <h3>{text("Ближайшие контрольные точки снимка","Snapshot control points")}</h3>
 {data.sections[0].entries.map((e,i)=><article className="project-state-message" key={i}><strong>{e.title}</strong><p>{e.next}</p><small>{e.qualification}</small></article>)}
 {data.sections[2].entries.map((e,i)=><details className="exec-row" key={i}><summary>{e.title}<span className="exec-next-point">{e.next}</span></summary><p>{e.qualification}</p></details>)}
 <p>{text("В этом снимке не установлено готовых к принятию решений. Действующий реестр решений проверяется отдельно.","No decision-ready items established in this snapshot. Live decision register is checked separately.")}</p>
 <div className="hub-filters" role="group" aria-label={text("Фильтр очереди","Queue filter")}><button aria-pressed={filter==="all"} onClick={()=>setFilter("all")}>{text("Все","All")} · {data.counts.actions}</button>{queues.map(q=><button key={q} aria-pressed={filter===q} onClick={()=>setFilter(q)}>{names[q]} · {data.counts.queues[q]}</button>)}</div>
 <label>{text("Контур проекта","Project contour")} <select value={project} onChange={e=>setProject(e.target.value)}><option value="">{text("Все проекты","All projects")}</option>{data.projects.map(p=><option key={p.label}>{p.label}</option>)}</select></label>
 {data.projects.filter(p=>!project||p.label===project).map(p=>{
 const all=data.items.filter(i=>i.project===p.label),items=all.filter(i=>filter==="all"||i.queue===filter);
 if(!items.length)return null;
 return <details className="exec-row" key={p.label} open={project===p.label||undefined}><summary><span><strong>{p.label}</strong><small>{p.stage}</small><span className="exec-next-point">{items[0].action}</span></span><span>{items.length}/{all.length}</span></summary>
 {items.map(i=><article key={i.ref}><p><strong>{i.ref} · {names[i.queue]}</strong></p><p>{i.action}</p><details><summary>{text("Условия и источники","Conditions and references")}</summary><p>{i.trigger}</p><p>{i.source_as_of}</p>{i.unknowns.map((u,n)=><p key={n}>{u}</p>)}<p>{i.related_control_refs.join(" · ")}</p></details></article>)}
 {p.subviews.length>0&&<details><summary>{text("Дорожные карты приложений","Application roadmaps")} · {p.subviews.length}</summary>{p.subviews.map((s,i)=><p key={i}>{s.label} · {s.state} — {s.next}</p>)}</details>}
 </details>;})}
 <details><summary>{text("Основание снимка","Snapshot provenance")}</summary><p><code>{data.source_commit}</code></p><p><code>{data.source_blob}</code></p></details>
 </>}
 </section>;
}
