import {useWorkspaceLanguage} from "./i18n";

type Row={id:string;label:string;repository:string;disposition:string;recorded_priority:string;role:string;accountable_position:string;execution_overlay:string;investment_boundary:string;dependency_boundary:string;continue_or_review_criteria:string;next_review_question:string;current_business_evidence:"unknown";financial_evidence:"unknown";review_outcome:"not_assessed";decision_ready:false};
type Packet={schema:string;status:string;derived:true;canonical_authority:false;organizational_authority_provided:false;coverage:"partial";review_completed:false;portfolio_updated:string;prepared_at:string;source_commit:string;previous_review_at:null;owner_attention:string;cadence:{event:string;monthly:string;quarterly:string;accountable_position:string;last_monthly_review:null;last_quarterly_review:null};source_refs:{path:string;blob:string}[];rows:Row[]};

const record=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==="object"&&!Array.isArray(v);
const str=(v:unknown):v is string=>typeof v==="string"&&v.trim().length>0&&v.length<=4000;
const date=(v:unknown)=>typeof v==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v;
export function parsePortfolioReview(value:unknown):Packet{
 if(!record(value)||value.schema!=="arvectum.company.portfolio-review-packet/1"||value.status!=="review_candidate"||
   value.derived!==true||value.canonical_authority!==false||value.organizational_authority_provided!==false||value.coverage!=="partial"||
   value.review_completed!==false||value.previous_review_at!==null||!date(value.portfolio_updated)||!date(value.prepared_at)||
   String(value.portfolio_updated)>String(value.prepared_at)||typeof value.source_commit!=="string"||!/^[a-f0-9]{40}$/.test(value.source_commit)||
   !str(value.owner_attention)||!record(value.cadence)||value.cadence.event!=="material_event"||
   value.cadence.monthly!=="monthly_async_exception_scan"||value.cadence.quarterly!=="quarterly_integrated_revalidation"||
   !str(value.cadence.accountable_position)||value.cadence.last_monthly_review!==null||value.cadence.last_quarterly_review!==null||
   !Array.isArray(value.source_refs)||value.source_refs.length<1||value.source_refs.length>20||
   !value.source_refs.every(x=>record(x)&&str(x.path)&&typeof x.blob==="string"&&/^[a-f0-9]{40}$/.test(x.blob))||
   !Array.isArray(value.rows)||value.rows.length<1||value.rows.length>100)throw Error("PORTFOLIO_REVIEW_INVALID");
 const ids=new Set<string>();
 for(const r of value.rows){
  if(!record(r)||typeof r.id!=="string"||!/^PORT-\d{3,8}$/.test(r.id)||ids.has(r.id)||
   !["label","repository","disposition","recorded_priority","role","accountable_position","execution_overlay","investment_boundary","dependency_boundary","continue_or_review_criteria","next_review_question"].every(k=>str(r[k]))||
   r.current_business_evidence!=="unknown"||r.financial_evidence!=="unknown"||r.review_outcome!=="not_assessed"||r.decision_ready!==false)throw Error("PORTFOLIO_REVIEW_INVALID");
  ids.add(r.id);
 }
 return value as unknown as Packet;
}

/** Read-only presentation of a separately admitted management packet.
 * The existing project provider does not supply it yet. No local fixture or
 * static Company treatment is used as a production fallback.
 */
export function PortfolioReview({candidate}:{candidate?:unknown}){
 const {text}=useWorkspaceLanguage();
 let packet:Packet|undefined;
 try{if(candidate!==undefined)packet=parsePortfolioReview(candidate);}catch{/* hide malformed packet */}
 return <section className="company-boundary-details portfolio-review">
 <h2>{text("Управление портфелем","Portfolio governance")}</h2>
 <p>{text("Управленческий статус продукта отличается от состояния разработки. Пересмотр не является утверждением инвестиций.","Portfolio treatment differs from implementation status. Review is not investment approval.")}</p>
 {!packet?<><p role="status">{text("Пакет управленческого пересмотра не допущен или недоступен.","Management review packet is not admitted or unavailable.")}</p><p>{text("Роль, ответственные должности, приоритеты, инвестиционные ограничения, зависимости, критерии продолжения и результаты пересмотра требуют отдельного подтверждённого источника.","Role, accountable positions, priorities, investment limits, dependencies, continuation criteria and review outcomes require a separately verified source.")}</p></>:
 <>
 <p>{text("Подготовленный пакет, не завершённый пересмотр","Prepared packet, not a completed review")} · {packet.prepared_at} · {text("Редакция портфеля","Portfolio revision")} {packet.portfolio_updated}</p>
 <p>{text("Ограничение внимания собственника","Owner attention boundary")}: {packet.owner_attention}</p>
 <div className="portfolio-cadence"><span>{text("Существенное событие → адресный пересмотр","Material event → scoped review")}</span><span>{text("Ежемесячная проверка исключений","Monthly exception scan")}</span><span>{text("Ежеквартальная сверка портфеля","Quarterly revalidation")}</span></div>
 <p>{text("Последние завершённые проверки не подтверждены.","Last completed reviews not established.")}</p>
 <div className="exec-list">{packet.rows.map(r=><details key={r.id}><summary><strong>{r.id} · {r.label}</strong><span>{r.disposition} · {r.recorded_priority}</span></summary>
 <dl className="company-facts">
 {[[text("Роль","Role"),r.role],[text("Ответственная должность","Accountable Position"),r.accountable_position],[text("Уточнение режима исполнения","Execution overlay"),r.execution_overlay],[text("Инвестиционная граница","Investment boundary"),r.investment_boundary],[text("Зависимости","Dependencies"),r.dependency_boundary],[text("Критерии продолжения / пересмотра","Continue / review criteria"),r.continue_or_review_criteria],[text("Следующий вопрос для проверки","Next review question"),r.next_review_question],[text("Бизнес-результат и экономика","Business outcomes and economics"),text("Не подтверждены","Unconfirmed")]].map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
 <p>{text("Решение к утверждению не подготовлено. Назначение исполнителя не подтверждено.","No decision ready for approval. Executor assignment not established.")}</p>
 </details>)}</div>
 <details><summary>{text("Исходные документы","Source documents")}</summary><p><code>{packet.source_commit}</code></p>{packet.source_refs.map(r=><p key={r.path}>{r.path} · <code>{r.blob}</code></p>)}</details>
 </>}
 </section>;
}
