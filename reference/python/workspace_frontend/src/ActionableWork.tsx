import { useCallback, useEffect, useState } from "react";
import { loadActionableWork, WorkspaceApiError } from "./api";
import { useWorkspaceLanguage } from "./i18n";
import type { ActionableWorkItem, ActionableWorkProjection } from "./types";

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; projection: ActionableWorkProjection }
  | { kind: "error"; code: string; reloadRequired: boolean };

function navigateTo(href: string): void {
  window.history.pushState({}, "", href);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function ActionableWork() {
  const { language, text } = useWorkspaceLanguage();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const refresh = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      setState({ kind: "ready", projection: await loadActionableWork() });
    } catch (error) {
      setState(error instanceof WorkspaceApiError
        ? { kind: "error", code: error.code, reloadRequired: error.reloadRequired }
        : { kind: "error", code: "ACTIONABLE_WORK_UNAVAILABLE", reloadRequired: false });
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  if (state.kind === "loading") {
    return <section className="actionable-work" aria-live="polite">
      <p>{text("Проверяем реальные запросы на действие…", "Checking real action requests…")}</p>
    </section>;
  }
  if (state.kind === "error") {
    return <section className="actionable-work" role="alert">
      <p className="eyebrow">P10.06 · Actionable Work</p>
      <h2>{text("Запросы на действие недоступны", "Action requests are unavailable")}</h2>
      <p>{state.reloadRequired
        ? text("Версия приложения изменилась. Перезагрузите страницу.", "The application release changed. Reload the page.")
        : text("Текущий source-backed контекст нельзя безопасно перепроверить. Workspace не показывает сохранённые или предполагаемые запросы вместо него.", "Current source-backed context could not be safely revalidated. Workspace does not substitute retained or inferred requests.")}</p>
      <code>{state.code}</code>
      <button type="button" onClick={() => state.reloadRequired ? window.location.reload() : void refresh()}>
        {state.reloadRequired ? text("Перезагрузить", "Reload") : text("Повторить", "Retry")}
      </button>
    </section>;
  }

  const projection = state.projection;
  return <section className="actionable-work" aria-labelledby="actionable-work-title">
    <div className="my-work-heading">
      <div>
        <p className="eyebrow">P10.06 · Actionable Work</p>
        <h2 id="actionable-work-title">{text("Запросы на действие", "Action requests")}</h2>
        <p>{text(
          "Здесь отображаются только запросы, которые уже существуют в продукте или компании и подтверждены текущим источником.",
          "Only requests that already exist in a product or Company source and are supported by current source evidence appear here.",
        )}</p>
      </div>
      <button type="button" className="quiet-button" onClick={() => void refresh()}>{text("Обновить", "Refresh")}</button>
    </div>
    <p className="boundary-note">{text(
      "Workspace не создаёт запросы, срочность, ответственность, согласование или полномочия. Открытие контекста не выполняет продуктовую операцию: перед любым эффектом действующие Authorization, Organizational Authority, Data Governance, Validation и Consequential Approval проверяются отдельно в Governed Execution.",
      "Workspace creates no request, urgency, responsibility, approval, or authority. Opening context does not execute a product operation: current Authorization, Organizational Authority, Data Governance, Validation, and Consequential Approval are revalidated separately in Governed Execution before any effect.",
    )}</p>
    {projection.items.length === 0
      ? <div className="empty-queue">
          <strong>{text("Подтверждённых запросов на действие сейчас нет.", "There are no verified action requests now.")}</strong>
          <p>{text(
            "Это нормальное состояние. Workspace не создаёт искусственный запрос ради заполнения списка или продвижения этапа.",
            "This is a normal state. Workspace does not manufacture a request to populate the list or advance a milestone.",
          )}</p>
        </div>
      : <div className="attention-list">{projection.items.map((item) => <ActionRequestCard key={item.id} item={item} language={language} />)}</div>}
  </section>;
}

function ActionRequestCard({ item, language }: { item: ActionableWorkItem; language: "ru" | "en" }) {
  const { text } = useWorkspaceLanguage();
  const observed = new Date(item.source.observed_at);
  const observedText = Number.isNaN(observed.getTime()) ? item.source.observed_at : observed.toLocaleString(language === "ru" ? "ru-RU" : "en-US");
  const current = item.source.freshness === "fresh";
  return <article className="attention-card actionable-work-card">
    <div className="attention-card-topline">
      <span>{item.source.kind === "product" ? text("Продукт", "Product") : text("Компания", "Company")}: {item.source.label}</span>
      <span>{text("Свежесть", "Freshness")}: {item.source.freshness}</span>
    </div>
    <h3>{item.title}</h3>
    <p>{item.context}</p>
    <dl>
      <div><dt>{text("Почему показано", "Why attention is requested")}</dt><dd>{item.attention_reason}</dd></div>
      <div><dt>{text("Состояние источника", "Source state")}</dt><dd>{item.source.state}</dd></div>
      <div><dt>{text("Наблюдалось", "Observed")}</dt><dd>{observedText}</dd></div>
      <div><dt>Product Contract</dt><dd>{item.source.product_contract.id} · {item.source.product_contract.lifecycle} {item.source.product_contract.version}</dd></div>
      <div><dt>{text("Governed preflight", "Governed preflight")}</dt><dd>{item.governed_execution.preflight_state}</dd></div>
    </dl>
    <section className="context-panel" aria-label={text("Описанные источником следующие шаги", "Source-declared next steps")}>
      <h4>{text("Что источник допускает рассмотреть дальше", "Source-declared next steps")}</h4>
      <ul>{item.next_steps.map((step) => <li key={step}>{step}</li>)}</ul>
    </section>
    {!current ? <p className="boundary-note">{text(
      "Источник не подтверждён как свежий. Переход к product/company entry point скрыт до повторной проверки.",
      "The source is not confirmed fresh. Product/company entry is withheld until revalidation.",
    )}</p> : null}
    {item.entry.available && item.entry.href
      ? <a className="task-list-action" href={item.entry.href} onClick={(event) => { event.preventDefault(); navigateTo(item.entry.href!); }}>
          {text("Открыть контекст запроса", "Open request context")}
        </a>
      : null}
    <details className="technical-details">
      <summary>{text("Точная ссылка и provenance", "Exact reference and provenance")}</summary>
      <dl>
        <div><dt>{text("Ссылка источника", "Source request reference")}</dt><dd><code>{item.source.request_ref}</code></dd></div>
        <div><dt>{text("Авторитет источника", "Source authority")}</dt><dd>{item.source.authority}</dd></div>
      </dl>
      <ul className="provenance-list">{item.technical.provenance_refs.map((ref) => <li key={ref}><code>{ref}</code></li>)}</ul>
      <p className="boundary-note">{text(
        "Эта карточка не является разрешением или согласием на эффект.",
        "This card is not authorization or approval for an effect.",
      )}</p>
    </details>
  </article>;
}
