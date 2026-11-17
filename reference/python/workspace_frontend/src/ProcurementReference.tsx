import {useEffect,useRef,useState} from "react";
import {useWorkspaceLanguage} from "./i18n";

type Evidence={ref:string;at:string;code?:string;value?:string;source?:string;actor_type?:string;actor_reference_present?:boolean;artifact_ref?:string|null};
type Deal={deal_id:string;procurement_number:string|null;workflow_status:string;updated_at:string;recorded_decision:Evidence|null;recommendation:Evidence|null;submission:Evidence|null;outcome:Evidence|null};
type View={observed_at:string;source_release:string;project_id:string;coverage:string;items:Deal[]};
export function ProcurementReference({csrfToken}:{csrfToken:string}){
 const {text,language}=useWorkspaceLanguage();
 const [data,setData]=useState<View|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(false),[filter,setFilter]=useState("all");
 const generation=useRef(0);
 useEffect(()=>()=>{generation.current++;},[]);
 const date=(v:string)=>new Date(v).toLocaleString(language==="ru"?"ru-RU":"en-GB");
 async function load(){
  const n=++generation.current;setData(null);setBusy(true);setError(false);
  try{
   const response=await fetch("/api/app/v1/procurement-reference",{method:"POST",credentials:"same-origin",headers:{"X-Arvectum-Workspace-Release":__ARVECTUM_WORKSPACE_RELEASE__,"X-Arvectum-CSRF":csrfToken}});
   if(!response.ok)throw Error("unavailable");
   const v=await response.json();
   if(v.schema!=="arvectum.workspace.internal-procurement-reference/1"||v.coverage!=="admitted-identity-set-only"||!Array.isArray(v.items)||v.canonical_authority!==false)throw Error("invalid");
   if(n===generation.current)setData(v);
  }catch{if(n===generation.current){setData(null);setError(true);}}
  finally{if(n===generation.current)setBusy(false);}
 }
 const visible=data?.items.filter(r=>filter==="all"||(filter==="submitted"?!!r.submission:!r.recorded_decision))??[];
 return <section className="company-card"><h2>{text("Закупки Арвектума","Arvectum procurements")}</h2>
 <p>{text("Реестр Tender Agent — отдельный источник. Здесь только чтение согласованных записей.","Tender Agent registry — a separate source. Only admitted records are read here.")}</p>
 <button disabled={busy} onClick={()=>void load()}>{busy?text("Получаем портфель…","Reading portfolio…"):text("Получить портфель закупок","Read procurement portfolio")}</button>
 {error&&<p role="alert">{text("Реестр недоступен или источник не допущен. Прежние сведения скрыты.","Registry unavailable or source not admitted. Previous information hidden.")}</p>}
 {data&&<>
  <p>{text("Получено","Observed")}: {date(data.observed_at)}. {text("Согласованный набор: ","Admitted set: ")}{data.items.length}</p>
  <p>{text("Есть запись подачи: ","Recorded submission: ")}{data.items.filter(r=>r.submission).length} · {text("Есть запись результата: ","Recorded outcome: ")}{data.items.filter(r=>r.outcome).length}</p>
  <p>{text("Записи не подтверждают текущий юридический статус, факт внешнего действия или одобрение собственника.","Records do not establish current legal status, external action or Owner approval.")}</p>
  <label>{text("Фильтр закупок","Procurement filter")} <select value={filter} onChange={e=>setFilter(e.target.value)}>
   <option value="all">{text("Все согласованные","All admitted")}</option>
   <option value="undecided">{text("Нет записи решения","No decision record")}</option>
   <option value="submitted">{text("Есть запись подачи","Submission recorded")}</option>
  </select></label>
  {!visible.length&&<p role="status">{text("Нет записей в выбранном представлении.","No records in this view.")}</p>}
  {visible.map(r=><article key={r.deal_id} className="company-card">
    <h3>{r.procurement_number??r.deal_id}</h3>
    <p>{text("Состояние процесса","Workflow state")}: {r.workflow_status} · {text("Обновлено","Updated")}: {date(r.updated_at)}</p>
    <p>{text("Зафиксированное решение","Recorded decision")}: {r.recorded_decision?<>
      {r.recorded_decision.value} · {r.recorded_decision.actor_type} · {date(r.recorded_decision.at)}
      {r.recorded_decision.actor_reference_present===false&&text(" (нет ссылки на автора)"," (actor reference missing)")}
    </>:text("Нет подтверждённой записи","No confirmed record")}</p>
    <p>{text("Рекомендация системы","System recommendation")}: {r.recommendation?.value??text("Неизвестно","Unknown")}</p>
    <p>{text("Запись подачи","Submission record")}: {r.submission?date(r.submission.at):text("Нет сведений","Unknown")}</p>
    <p>{text("Запись результата","Outcome record")}: {r.outcome?r.outcome.code+" · "+date(r.outcome.at):text("Нет сведений","Unknown")}</p>
    <details><summary>{text("Источники записи","Evidence references")}</summary><p>{r.deal_id}</p>
      {([r.recorded_decision,r.recommendation,r.submission,r.outcome]).filter((e):e is Evidence=>e!==null).map((e,i)=><p key={i}>{e.ref} · {date(e.at)}{e.artifact_ref?" · "+e.artifact_ref:""}</p>)}
    </details>
  </article>)}
  <details><summary>{text("Происхождение сводки","Snapshot provenance")}</summary><p>Release <code>{data.source_release}</code></p><p>{text("Проект","Project")}: {data.project_id}</p><a href="/projects">{text("Открыть проекты","Open projects")}</a></details>
 </>}
 </section>;
}
