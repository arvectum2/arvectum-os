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
// Exact translations of known source stages; original wording is preserved in evidence.
const stageRu:Record<string,string>={
 "Reliability first, multi-user acceptance separately":"Надёжность доставки; многопользовательская приёмка отдельно",
 "LAB-02 blocked":"LAB-02 — заблокировано",
 "Офлайн-репетиция CMS PASS reported; cloud gates open":"Офлайн-репетиция CMS пройдена по отчёту; облачные проверки открыты",
 "AS-043 first next action at pinned main":"AS-043 — следующее действие по зафиксированной версии",
 "Workspace First; AC-505 external wait":"Рабочее пространство — приоритет; AC-505 ожидает внешнего результата",
 "WSF-02–05 recovery and evidence":"WSF-02–05 — восстановление и подтверждения",
 "AW-020-C2 internal preparation; C1 historical pointer":"AW-020-C2 — внутренняя подготовка; C1 — предыдущий этап",
 "Waiting-for-client-data, lane 4/7 reported":"Ожидание данных заказчика; этап 4 из 7 по отчёту",
 "Technical hardening complete reported; lost client, reassessment":"Техническая доработка завершена по отчёту; потеря клиента, переоценка",
 "Contained reference, no new roadmap":"Сохранение наработок; новой дорожной карты нет",
 "KEEP_IN_PLACE":"Архив: сохранить без возобновления",
 "DP-INT-002 open":"DP-INT-002 — открыто",
 "AC-01 partial; EG-004b2 open; PUBLIC NO-GO":"AC-01 — частично; EG-004b2 — открыт; публичный запуск запрещён",
 "Four released apps reported; physical QA, analytics and localization open":"По отчёту выпущено четыре приложения; физические проверки, аналитика и локализация открыты",
 "S0 baseline; distinct from local customer pilot":"S0 — исходная гипотеза; отдельно от клиентского пилота",
 "BR-05 in progress v0.38":"BR-05 — в работе, версия 0.38",
 "Static QA accepted; actual SEO and deployment separate":"Статические проверки пройдены; SEO и развёртывание — отдельно",
 "Physical and tool acceptance open":"Физическая приёмка и проверка инструментов открыты",
};
const actionRu:readonly (readonly [string,string])[]=[["Read-only сверка","Сверка без изменения данных"],["фактических receipts","фактических подтверждений"],["реальные evidence cases","реальные подтверждённые случаи"],["не закрывать по CI","не закрывать только по результатам CI"],["по roadmap","по дорожной карте"],["не менять runtime","не менять рабочую среду"],["физические receipts","подтверждения физических испытаний"],["Read-only проверить актуальный runtime и очереди/UNKNOWN","Проверить без изменений рабочую среду и очереди (в том числе неопределённые отправки)"],["existing field acceptance","существующей приёмкой в реальных условиях"],["destructive tests","разрушающих испытаний"],["factual/legal verification separately","фактическая и правовая проверка отдельно"],["pilot Project Roadmap","пилот управления дорожными картами"],["reopen и evidence-grounded proposals","повторное открытие задач и предложения на основе доказательств"],["Company Projects/My Work","«Проекты» и «Моя работа»"],["governed action","действия по установленным правилам"],["без GO","без разрешения на запуск"],["синтетические evidence","синтетические доказательства"],["waiting lane","очередь ожидания"],["provenance","происхождение материалов"],["контракт и evidence","контракт и подтверждения"],["unmet SLO","недостижения целевого уровня обслуживания (SLO)"],["модельные, credential и бюджетные gates","ограничения по моделям, учётным данным и бюджету"],["законный scope доменов","законный перечень доменов"],["DNS/tenant proof","подтверждения DNS и принадлежности доменов"],["security QA","проверку безопасности"],["rule/evidence schema","схемы правил и доказательств"],["feedback IDs","идентификаторов отзывов"],["onboarding/manual fallback","первоначальную настройку и ручной резервный сценарий"],["фиктивного paywall","фиктивной платной блокировки"],["actual analytics","фактические показатели аналитики"],["storefront-ready","готовыми для магазина приложений"],["гипотезы и scope","гипотезы и границ работ"],["80%/60% claims","заявления о 80%/60%"],["контент и CTA","контент и призыв к действию"],["read-only диагностику","диагностику без изменений"],["нативную QA","проверку в исходных приложениях"],["физическую QA","проверку на физических устройствах"],["Read-only диагностика","Диагностика без изменений"]];
function readableAction(v:string,ru:boolean){return ru?actionRu.reduce((s,[a,b])=>s.replaceAll(a,b),v):v;}
export function OwnerProjectQueue({data,state}:{data:OwnerQueue|null;state:string}){
 const {text,language}=useWorkspaceLanguage();
 const [filter,setFilter]=useState<Queue|"all">("all"),[project,setProject]=useState(""),[expanded,setExpanded]=useState(false);
 const names:Record<Queue,string>={prepare_within_existing_envelope:text("Подготовка","Preparation"),read_only_reconciliation:text("Сверка","Reconciliation"),blocked:text("Блокеры","Blocked"),watch:text("Ожидание","Waiting"),hold:text("Отложено","On hold")};
 const matches=data?.projects.filter(p=>(!project||p.label===project)&&data.items.some(i=>i.project===p.label&&(filter==="all"||i.queue===filter)))??[];
 const shown=expanded||project?matches:matches.slice(0,6);
 const visibleActions=matches.reduce((n,p)=>n+(data?.items.filter(i=>i.project===p.label&&(filter==="all"||i.queue===filter)).length??0),0);
 const stage=(v:string)=>language==="ru"?(stageRu[v]??v):v;
 const action=(v:string)=>readableAction(v,language==="ru");
 return <section className="exec-panel owner-queue" id="exec-projects"><header><h2>{text("Проекты и следующие действия","Projects and next steps")}</h2>{data&&<span className="oq-date">{text("Снимок от","Snapshot dated")} {data.as_of}</span>}</header>
 {!data?<p role="status">{state==="unchecked"?text("Обновите сводку для чтения проектной очереди.","Read summary to check the project queue."):text("Проектная очередь не допущена или недоступна. Состояние неизвестно.","Project queue is not admitted or unavailable. Status unknown.")}</p>:<>
 <p className="exec-muted">{text("Частичное покрытие. Снимок не отражает состояние в реальном времени и не разрешает исполнение.","Partial coverage. Snapshot is not live status or permission to execute.")}</p>
 <div className="oq-summary"><div><strong>{data.counts.projects}</strong><span>{text("проектных контуров","project contours")}</span></div><div><strong>{data.counts.actions}</strong><span>{text("действий","next-action references")}</span></div><div><strong>{data.counts.queues.prepare_within_existing_envelope+data.counts.queues.read_only_reconciliation}</strong><span>{text("подготовка и сверка","preparation and review")}</span></div></div>
 <details className="oq-control"><summary>{text("Ближайшие контрольные точки снимка","Snapshot control points")}</summary>
 {[...data.sections[0].entries,...data.sections[2].entries].map((e,i)=><article key={i}><strong>{e.title}</strong><p>{action(e.next)}</p><details><summary>{text("Основание","Basis")}</summary><p>{e.qualification}</p><p>{e.next}</p></details></article>)}
 <p className="exec-muted">{text("В снимке не установлено готовых к принятию решений. Действующий реестр проверяется отдельно.","No decision-ready items established in this snapshot. Live register checked separately.")}</p></details>
 <div className="oq-toolbar"><div className="oq-filters" role="group" aria-label={text("Фильтр очереди","Queue filter")}><button aria-pressed={filter==="all"} onClick={()=>{setFilter("all");setExpanded(false)}}>{text("Все","All")} · {data.counts.actions}</button>{queues.map(k=><button key={k} aria-pressed={filter===k} onClick={()=>{setFilter(k);setExpanded(false)}}>{names[k]} · {data.counts.queues[k]}</button>)}</div>
 <label className="oq-select">{text("Проект","Project")} <select value={project} onChange={e=>{setProject(e.target.value);setExpanded(false)}}><option value="">{text("Все проекты","All projects")}</option>{data.projects.map(p=><option key={p.label}>{p.label}</option>)}</select></label></div>
 <p className="oq-result" role="status">{text("Показано проектов","Projects shown")}: {shown.length} {text("из","of")} {matches.length} · {text("Действий по фильтру","Matching action references")}: {visibleActions}</p>
 {matches.length===0&&<p>{text("По выбранным условиям действий нет в этом снимке.","No matching actions in this snapshot.")}</p>}
 <div className="oq-list">{shown.map(p=>{
 const all=data.items.filter(i=>i.project===p.label),items=all.filter(i=>filter==="all"||i.queue===filter);
 return <details className="oq-project" key={p.label} open={project===p.label||undefined}><summary><div className="oq-project-copy"><strong>{p.label}</strong><span className="oq-stage">{stage(p.stage)}</span><span className="oq-next"><b>{text("Следующее по списку: ","First matching action: ")}</b>{action(items[0].action)}</span></div><span className="oq-count">{text("Показано действий","Actions shown")}: {items.length} {text("из","of")} {all.length}</span></summary>
 <div className="oq-details">{items.map(i=><article className="oq-action" key={i.ref}><h3>{names[i.queue]}</h3><p>{action(i.action)}</p><details><summary>{text("Условия и источники","Conditions and references")}</summary><p>{i.ref}</p>{action(i.action)!==i.action&&<p>{i.action}</p>}<p>{i.trigger}</p><p>{i.source_as_of}</p>{i.unknowns.map((u,n)=><p key={n}>{u}</p>)}<p>{i.related_control_refs.join(" · ")}</p></details></article>)}
 {p.subviews.length>0&&<details className="oq-evidence"><summary>{text("Дорожные карты приложений","Application roadmaps")} · {p.subviews.length}</summary>{p.subviews.map((s,i)=><p key={i}>{s.label} · {s.state} — {s.next}</p>)}</details>}
 <details className="oq-evidence"><summary>{text("Исходный статус проекта","Original project status")}</summary><p>{p.stage}</p><p>{p.source_as_of}</p></details></div>
 </details>;})}</div>
 {!project&&matches.length>6&&<button className="oq-more" onClick={()=>setExpanded(x=>!x)}>{expanded?text("Свернуть список","Collapse list"):text("Показать все проекты по фильтру","Show all matching projects")+" · "+matches.length}</button>}
 <details className="oq-evidence"><summary>{text("Основание снимка","Snapshot provenance")}</summary><p><code>{data.source_commit}</code></p><p><code>{data.source_blob}</code></p></details>
 </>}
 </section>;
}
