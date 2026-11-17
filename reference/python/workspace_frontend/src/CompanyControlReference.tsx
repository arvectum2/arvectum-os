import {useEffect,useRef,useState} from "react";
import {useWorkspaceLanguage} from "./i18n";
type Row={id:string;title:string;accountable_position:string;priority:string;control_state:string;evidence_as_of:string;next_control_point:string;source_refs:string[];due_or_trigger:{kind:string;value:string};decision_ready:boolean};
type View={owner_action:Row[];obligation_signals:Row[];coverage:string;canonical_authority:boolean};
export function CompanyControlReference({csrfToken}:{csrfToken:string}){
 const {text}=useWorkspaceLanguage();
 const [data,setData]=useState<View|null>(null),[error,setError]=useState(false),[busy,setBusy]=useState(false);
 const seq=useRef(0);useEffect(()=>()=>{seq.current++;},[csrfToken]);
 async function load(){
  const n=++seq.current;setData(null);setBusy(true);setError(false);
  try{
   const r=await fetch("/api/app/v1/company-control-reference",{method:"POST",credentials:"same-origin",cache:"no-store",headers:{"X-Arvectum-Workspace-Release":__ARVECTUM_WORKSPACE_RELEASE__,"X-Arvectum-CSRF":csrfToken}});
   if(!r.ok)throw Error();
   const v=await r.json();
   if(v.coverage!=="partial"||v.derived!==true||v.canonical_authority!==false||v.organizational_authority_provided!==false||!Array.isArray(v.owner_action)||v.owner_action.length!==1||!Array.isArray(v.obligation_signals)||v.obligation_signals.length!==2)throw Error();
   const x=v.owner_action[0];
   if(x.id!=="WORK-001"||x.accountable_position!=="POS-001"||x.decision_ready!==false||x.canonical_authority!==false||x.due_or_trigger?.kind!=="exact"||!Number.isFinite(Date.parse(x.due_or_trigger.value))||!Array.isArray(x.source_refs)||!x.source_refs.every((s:unknown)=>typeof s==="string")||!["title","priority","control_state","evidence_as_of","next_control_point"].every(k=>typeof x[k]==="string"))throw Error();
   const ids=new Set<string>();
   for(const o of v.obligation_signals){
    if(!["OBL-001","OBL-002"].includes(o.id)||ids.has(o.id)||o.accountable_position!=="POS-002"||o.decision_ready!==false||o.canonical_authority!==false||o.due_or_trigger?.kind!=="condition"||typeof o.due_or_trigger.value!=="string"||o.control_state!=="open"||o.priority!=="P0"||!Array.isArray(o.source_refs)||!o.source_refs.every((s:unknown)=>typeof s==="string")||!["title","evidence_as_of","next_control_point"].every(k=>typeof o[k]==="string"))throw Error();
    ids.add(o.id);
   }
   if(n===seq.current)setData(v);
  }catch{if(n===seq.current)setError(true);}
  finally{if(n===seq.current)setBusy(false);}
 }
 return <section className="company-card"><h2>{text("Реестр работ и обязательств","Company work and obligation register")}</h2>
 <p>{text("Частичное покрытие. Только чтение отдельно согласованных записей; обязательства и решения не выводятся из заметок.","Partial coverage. Read only the separately admitted records; obligations and decisions are not inferred from notes.")}</p>
 <button disabled={busy} onClick={()=>void load()}>{text("Прочитать реестр работ","Read work register")}</button>
 {error&&<p role="alert">{text("Реестр не допущен, изменился или недоступен. Сведения скрыты.","Register not admitted, changed or unavailable. Details hidden.")}</p>}
 {data?.owner_action.map(x=><article key={x.id}><h3>{x.id} · {x.title}</h3>
 <p>{x.accountable_position} · {x.priority} · {text("Открыта","Open")}</p>
 <p>{text("Контрольный срок","Review deadline")}: {x.due_or_trigger.value}</p>
 <p>{x.next_control_point}</p><p>{text("Решение ещё не подготовлено; полнота обязательств неизвестна.","Decision not ready; obligation coverage unknown.")}</p>
 <details><summary>{text("Свидетельства","Evidence")}</summary><p>{x.evidence_as_of}</p>{x.source_refs.map((s,i)=><p key={i}>{s}</p>)}</details></article>)}
 {data&&<><h3>{text("Договорные обязательства","Contractual obligations")}</h3>
 <p>{text("Сроки — из проверенного комплекта контракта. Фактическое исполнение и приёмка требуют отдельной проверки.","Terms from the reviewed contract package. Actual fulfillment and acceptance require separate verification.")}</p>
 {data.obligation_signals.map(o=><article key={o.id}><h4>{o.id} · {o.title}</h4>
 <p>{o.accountable_position} · {o.priority} · {text("Открытое обязательство","Open obligation")}</p>
 <p>{text("Срок / условие","Due / condition")}: {o.due_or_trigger.value}</p><p>{o.next_control_point}</p>
 <details><summary>{text("Свидетельства","Evidence")}</summary><p>{o.evidence_as_of}</p>{o.source_refs.map((r,i)=><p key={i}>{r}</p>)}</details>
 </article>)}</>}
 </section>;
}
