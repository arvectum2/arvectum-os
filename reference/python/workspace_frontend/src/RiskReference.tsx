import {useEffect,useRef,useState} from "react";
import {useWorkspaceLanguage} from "./i18n";
type Row={id:string;title:string;position:string;priority:string;risk_statement:string;residual_exposure:string;control_evidence:string;next_control_point:string;review_trigger:string;source_refs:string[];linked_work:string[]};
const ids=["RSK-001","RSK-002","RSK-003"];
const positions=["POS-006","POS-004","POS-002"];
export function parseRisk(v:unknown):Row[]{
 if(!v||typeof v!=="object")throw Error();
 const d=v as Record<string,unknown>;
 if(d.schema!=="arvectum.workspace.company-risk-reference/1"||d.coverage!=="partial"||d.derived!==true||d.canonical_authority!==false||d.organizational_authority_provided!==false||!Array.isArray(d.items)||d.items.length!==3)throw Error();
 for(let i=0;i<3;i++){
  const r=d.items[i];
  if(!r||r.id!==ids[i]||r.position!==positions[i]||r.priority!==(i===2?"P0":"P1")||r.recorded_state!=="active"||r.risk_accepted!==false||r.response_intent!=="reduce"||r.owner_attention!=="not_required"||r.likelihood!=="unknown"||r.current_applicability!=="unknown"||!["title","risk_statement","residual_exposure","control_evidence","next_control_point","review_trigger"].every(k=>typeof r[k]==="string"&&r[k].length>0)||!["source_refs","linked_work"].every(k=>Array.isArray(r[k])&&r[k].length>0&&r[k].every((x:unknown)=>typeof x==="string")))throw Error();
 }
 return d.items as Row[];
}
export function RiskReference({csrfToken}:{csrfToken:string}){
 const {text}=useWorkspaceLanguage();
 const [rows,setRows]=useState<Row[]|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(false);
 const seq=useRef(0);useEffect(()=>()=>{seq.current++;},[csrfToken]);
 async function load(){
  const n=++seq.current;setRows(null);setBusy(true);setError(false);
  try{
   const r=await fetch("/api/app/v1/company-risk-reference",{method:"POST",credentials:"same-origin",cache:"no-store",headers:{"X-Arvectum-Workspace-Release":__ARVECTUM_WORKSPACE_RELEASE__,"X-Arvectum-CSRF":csrfToken}});
   if(!r.ok)throw Error();const d=parseRisk(await r.json());if(n===seq.current)setRows(d);
  }catch{if(n===seq.current)setError(true);}
  finally{if(n===seq.current)setBusy(false);}
 }
 return <section className="company-card"><h2>{text("Риски компании","Company risks")}</h2>
 <p>{text("Частичное покрытие. Риски не приняты; вероятность и текущая применимость требуют проверки.","Partial coverage. Risks are not accepted; likelihood and current applicability need verification.")}</p>
 <button disabled={busy} onClick={()=>void load()}>{text("Прочитать реестр рисков","Read risk register")}</button>
 {error&&<p role="alert">{text("Реестр изменился, недоступен или не допущен. Сведения скрыты.","Register changed, unavailable or not admitted. Details hidden.")}</p>}
 {rows&&<>{[...rows].sort((a,b)=>a.priority.localeCompare(b.priority)).map(r=><article key={r.id}><h3>{r.id} · {r.title}</h3><p>{r.position} · {r.priority} · {text("Открытый риск","Open risk")}</p><p>{r.risk_statement}</p><p>{text("Остаточный риск","Residual exposure")}: {r.residual_exposure}</p><p>{text("Следующий шаг","Next step")}: {r.next_control_point}</p><p>{r.review_trigger}</p><details><summary>{text("Свидетельства и связанные работы","Evidence and linked work")}</summary><p>{r.control_evidence}</p>{r.source_refs.map((x,i)=><p key={i}>{x}</p>)}<p>{r.linked_work.join(", ")}</p></details></article>)}
 <p>{text("Исключения и инциденты отдельно не допущены; полнота неизвестна.","Exceptions and incidents not admitted separately; completeness unknown.")}</p></>}
 </section>;
}
