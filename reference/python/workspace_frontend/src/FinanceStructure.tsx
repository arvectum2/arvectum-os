import {useWorkspaceLanguage} from "./i18n";
import type {parseFinance} from "./FinanceReference";

/** Structure only: 0.5.4 is the sole admitted source. No input or effect. */
export function FinanceStructure({finance}:{finance:ReturnType<typeof parseFinance>}){
 const {text}=useWorkspaceLanguage();
 const fields=(items:[string,string][])=> <dl className="finance-fields">{items.map(([ru,en])=>
  <div key={en}><dt>{text(ru,en)}</dt><dd>{text("Не установлено","Unknown")}</dd></div>)}</dl>;
 const v=finance.conditional_inflow;
 return <div className="finance-structure">
 <section className="exec-panel"><h2>{text("Деньги и движения","Cash and movements")}</h2>
 {fields([["Доступные средства","Available funds"],["Остаток по выписке","Booked balance"],["Фактические поступления","Actual receipts"],["Фактические списания","Actual debits"]])}
 <p className="exec-muted">{text("Обороты банка не равны выручке и расходам.","Bank turnover is not revenue and expense.")}</p></section>
 <section className="exec-panel"><h2>{text("Платёжный календарь","Payment calendar")}</h2>
 <p>{text("Покрытие частичное. Суммы и сроки обязательных выплат не подтверждены; это не пустой календарь.","Partial coverage. Required disbursements and dates are unconfirmed; this is not an empty calendar.")}</p>
 <div className="finance-table-wrap"><table className="finance-table"><thead><tr><th>{text("Основание","Basis")}</th><th>{text("Сумма","Amount")}</th><th>{text("Срок / условие","Date / condition")}</th></tr></thead>
 <tbody><tr><td>{text("Условное поступление по контракту","Conditional contractual inflow")}<small>{v.linked_obligations.join(" · ")}</small></td>
 <td>{new Intl.NumberFormat("ru-RU",{style:"currency",currency:"RUB"}).format(Number(v.contract_price_rub))}</td>
 <td>{text("Дата не подтверждена","Date not confirmed")}<small>{v.timing_condition}</small></td></tr></tbody></table></div>
 {fields([["Подтверждённые платежи к исполнению","Confirmed due payments"],["Дебиторская задолженность","Receivables"],["Кредиторская задолженность","Payables"],["Налоги и обязательные платежи","Tax and mandatory payments"]])}</section>
 <section className="exec-panel"><h2>{text("Расходы и лимиты","Costs and limits")}</h2>
 {fields([["Регулярные обязательства","Recurring commitments"],["Утверждённые лимиты","Approved limits"],["Утверждённые, ещё не возникшие обязательства","Approved, not yet incurred"],["Плановые расходы","Planned spending"]])}
 <p className="exec-muted">{text("Лимит и согласование не являются оплатой или возникшим обязательством.","A limit or approval is not a payment or incurred obligation.")}</p></section>
 <section className="exec-panel"><h2>{text("Прогноз ликвидности","Liquidity forecast")}</h2>
 <p className="finance-blocked">{text("Расчёт недоступен — недостаточно подтверждённых данных","Calculation unavailable — insufficient verified evidence")}</p>
 {fields([["Начальный доступный остаток","Opening available cash"],["Горизонт прогноза","Forecast horizon"],["Подтверждённые выплаты в горизонте","Confirmed outflows over horizon"],["Остаток после подтверждённых выплат","Cash after confirmed outflows"],["Закупочные кассовые разрывы","Procurement cash gaps"]])}
 <p className="exec-muted">{text("Условные поступления не включаются в консервативный расчёт.","Conditional inflows are excluded from the conservative calculation.")}</p></section>
 <section className="exec-panel"><h2>{text("Экономика проектов","Project economics")}</h2>
 {fields([["Подтверждённая выручка за период","Verified revenue for period"],["Прямые затраты за тот же период","Direct costs for same period"],["Маржинальный результат по прямым затратам","Direct contribution"],["Чистая прибыль","Net profit"]])}
 <p className="exec-muted">{text("Цена договора не подтверждает выручку. Разница выручки и прямых затрат не равна чистой прибыли.","Contract price does not establish revenue. Direct contribution is not net profit.")}</p></section>
 <section className="exec-panel"><h2>{text("Источники и контроль","Sources and control")}</h2>
 <p>POS-005 · {text("Снимок на","Report as of")}: {finance.report_as_of}</p>
 {fields([["Банковские данные","Bank evidence"],["Бухгалтерские данные","Accounting evidence"]])}
 <p>{text("Договорные условия проверены в архивном источнике.","Contract terms verified in archived source.")}</p>
 <p>{finance.next_control_point}</p><p className="exec-muted">{text("Только просмотр допущенных данных. Финансовые действия недоступны.","Admitted read only. Financial actions unavailable.")}</p></section>
 </div>;
}
