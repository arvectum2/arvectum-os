import {useEffect,useRef,useState} from "react";
import {useWorkspaceLanguage} from "./i18n";
type Row={id:string;kind:"decision"|"approval";title:string;question?:string;scope?:string;capacity:string;authority_basis:string;recorded_state:string;recorded_outcome?:string;act_ref:string|null;constraints:string;review_trigger?:string;review_due_at?:string|null;linked_work?:string|null;effective_period?:string;domain?:string;position?:string};
const names=["DEC-001","DEC-002","DEC-003","APR-001","DEC-004","DEC-005"];
export function parseDecision(v:unknown):Row[]{
 if(!v||typeof v!=="object")throw Error();
 const d=v as Record<string,unknown>;
 if(d.schema!=="arvectum.workspace.company-decision-reference/1"||d.coverage!=="partial"||d.derived!==true||d.canonical_authority!==false||d.organizational_authority_provided!==false||!Array.isArray(d.items)||(d.items.length<4||d.items.length>6))throw Error();
 for(let i=0;i<d.items.length;i++){
  const x=d.items[i];
  if(!x||x.id!==names[i]||x.decision_ready!==false||x.current_applicability!=="unknown"||x.capacity!=="Owner"||!["title","authority_basis","constraints"].every(k=>typeof x[k]==="string"))throw Error();
  if(i!==3){
   if(x.kind!=="decision"||x.position!=="POS-001"||typeof x.question!=="string"||typeof x.review_trigger!=="string")throw Error();
   if(i===2){if(x.recorded_state!=="preparing"||x.recorded_outcome!=="none"||x.act_ref!==null||x.linked_work!=="WORK-001"||!Number.isFinite(Date.parse(x.review_due_at)))throw Error();}
   else if(x.recorded_state!=="decided"||x.recorded_outcome!=="approve_with_conditions"||typeof x.act_ref!=="string")throw Error();
  }else if(x.kind!=="approval"||x.domain!=="arvectum_os"||x.recorded_state!=="approved"||!["scope","effective_period","act_ref"].every(k=>typeof x[k]==="string"))throw Error();
 }
 return d.items as Row[];
}
export function DecisionReference({csrfToken}:{csrfToken:string}){
 const {text}=useWorkspaceLanguage();
 const [rows,setRows]=useState<Row[]|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(false);
 const seq=useRef(0);useEffect(()=>()=>{seq.current++;},[csrfToken]);
 async function load(){
  const n=++seq.current;setRows(null);setBusy(true);setError(false);
  try{
   const r=await fetch("/api/app/v1/company-decision-reference",{method:"POST",credentials:"same-origin",cache:"no-store",headers:{"X-Arvectum-Workspace-Release":__ARVECTUM_WORKSPACE_RELEASE__,"X-Arvectum-CSRF":csrfToken}});
   if(!r.ok)throw Error();
   const d=parseDecision(await r.json());if(n===seq.current)setRows(d);
  }catch{if(n===seq.current)setError(true);}
  finally{if(n===seq.current)setBusy(false);}
 }
 return <section className="company-card"><h2>{text("Решения и согласования","Decisions and approvals")}</h2>
 <p>{text("Частичное покрытие. Исторические записи не являются новым разрешением. Полнота и текущая применимость согласований неизвестны.","Partial coverage. Historical records are not new permissions. Completeness and current applicability are unknown.")}</p>
 <button disabled={busy} onClick={()=>void load()}>{text("Прочитать реестр решений","Read decision register")}</button>
 {error&&<p role="alert">{text("Реестр решений изменён, недоступен или не допущен. Сведения скрыты.","Decision register changed, unavailable or not admitted. Details hidden.")}</p>}
 {rows&&<><h3>{text("Готовится решение","Decision in preparation")}</h3>
 {rows.filter(x=>x.id==="DEC-003").map(x=><article key={x.id}><h4>{x.id} · {x.title}</h4><p>{x.question}</p>
 <p>{text("Связанная работа (не новая задача)","Linked work (not a new task)")}: {x.linked_work} · {x.review_due_at}</p>
 <p>{text("Не готово к решению; результат не принят.","Not ready for decision; no outcome.")}</p><p>{x.constraints}</p></article>)}
 <h3>{text("Зафиксированные решения и согласования","Recorded decisions and approvals")}</h3>
 {rows.filter(x=>x.id!=="DEC-003").map(x=><article key={x.id}><h4>{x.id} · {x.title}</h4>
 <p>{x.kind==="approval"?text("Зафиксировано согласование","Approval recorded"):text("Решение принято с условиями","Decision recorded with conditions")}</p>
 <p>{x.question??x.scope}</p>{x.effective_period&&<p>{x.effective_period}</p>}<p>{x.constraints}</p>
 <details><summary>{text("Основание и источник","Authority basis and source")}</summary><p>{x.capacity} · {x.authority_basis}</p><p>{x.act_ref}</p>{x.review_trigger&&<p>{x.review_trigger}</p>}</details></article>)}
 <p>{text("Эскалации отдельно не допущены; полнота неизвестна.","No escalations admitted; coverage unknown.")}</p></>}
 </section>;
}
