import {useWorkspaceLanguage} from "./i18n";

/** Read-only operating-cadence guide. It is not a review history or scheduler. */
export function OperatingCadence(){
 const {text}=useWorkspaceLanguage();
 return <section className="exec-panel" aria-labelledby="operating-cadence">
 <header><h2 id="operating-cadence">{text("Операционный цикл","Operating cadence")}</h2></header>
 <p>{text("Сначала существенные события, затем периодический контроль. Обязательной ежедневной проверки нет.","Material events first, then periodic checks. No mandatory daily check.")}</p>
 <details className="exec-row"><summary><strong>{text("По событию","Event-driven")}</strong><small>{text("Немедленная адресная проверка при существенном изменении","Immediate scoped review on material change")}</small></summary>
 <p>{text("Обязательства, решения и полномочия, риски, деньги, портфель, критические зависимости или утратившие актуальность доказательства.","Obligations, decisions and authority, risks, finances, portfolio, critical dependencies or invalidated evidence.")}</p>
 <p>{text("Собственник подключается только при необходимом действии или полномочии. Обычные задачи, технические уведомления и ожидание без действия не являются основанием для эскалации.","Owner involvement requires actionable need or authority. Routine tasks, technical warnings and non-actionable waiting are not escalation grounds.")}</p>
 <a href="/control-details">{text("Работы, решения и риски","Work, decisions and risks")}</a></details>
 <details className="exec-row"><summary><strong>{text("Неделя","Week")}</strong><small>{text("Не более одной сводки при наличии существенного состояния","At most one summary if material state exists")}</small></summary>
 <p>{text("Приоритетная защита, действия собственника, исключения делегированной работы, финансовые и договорные сигналы, портфель и изменения доказательств.","Protect now, Owner action, delegated exceptions, finance and obligation signals, portfolio and evidence changes.")}</p>
 <p>{text("Активность недели и предыдущая проверка требуют подтверждения.","Active week and prior review require confirmation.")}</p></details>
 <details className="exec-row"><summary><strong>{text("Месяц","Month")}</strong><small>{text("Один объединённый контрольный обзор","One integrated management checkpoint")}</small></summary>
 <p>{text("Финансовая сводка, исключения портфеля, открытые существенные работы и риски, лишняя нагрузка контроля.","Finance summary, portfolio exceptions, open material controls and control burden.")}</p>
 <p><a href="/finance">{text("Финансы","Finances")}</a> · <a href="/projects">{text("Портфель","Portfolio")}</a> · <a href="/control-details">{text("Реестры","Registers")}</a></p></details>
 <details className="exec-row"><summary><strong>{text("Квартал","Quarter")}</strong><small>{text("Одна комплексная сверка","One integrated revalidation")}</small></summary>
 <p>{text("Портфель, непрерывность и зависимости, соответствие контролей масштабу бизнеса, нагрузка собственника.","Portfolio, continuity and dependencies, control fit and Owner burden.")}</p></details>
 <p className="exec-muted">{text("История завершённых контрольных обзоров не допущена. Чтение сводки не означает завершение проверки. Новые задачи и уведомления автоматически не создаются.","Completed review history is not admitted. Reading a summary does not complete a review. No tasks or notifications are automatically created.")}</p>
 </section>;
}
