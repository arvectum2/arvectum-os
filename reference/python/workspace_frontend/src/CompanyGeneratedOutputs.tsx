import { useCallback, useEffect, useState } from "react";
import { downloadCompanyOutput } from "./f11Api";
import {
  loadCompanyGeneratedOutputs,
  promoteCompanyGeneratedOutput,
  reviewCompanyGeneratedOutput,
} from "./p10_05Api";
import type {
  CompanyGeneratedOutputHandling,
  CompanyGeneratedOutputItem,
  CompanyGeneratedOutputsProjection,
} from "./p10_05Types";
import { useWorkspaceLanguage } from "./i18n";
import "./CompanyWorkspace.css";


type State =
  | { kind: "loading" }
  | { kind: "ready"; data: CompanyGeneratedOutputsProjection }
  | { kind: "error"; code: string };

function prettyDate(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("ru-RU");
}

function Handling({ value }: { value: CompanyGeneratedOutputHandling }) {
  const { text } = useWorkspaceLanguage();
  return <dl className="company-facts">
    <div><dt>{text("Классификация", "Classification")}</dt><dd>{value.classification}</dd></div>
    <div><dt>{text("Назначение", "Purpose")}</dt><dd>{value.purpose}</dd></div>
    <div><dt>{text("Права использования", "Rights")}</dt><dd>{value.rights.join(", ")}</dd></div>
    <div><dt>Retention</dt><dd>{value.retention_rule}</dd></div>
    <div><dt>{text("Удаление", "Deletion")}</dt><dd>{value.deletion_rule}</dd></div>
    <div><dt>{text("Разрешённое повторное использование", "Permitted reuse")}</dt><dd>{value.permitted_reuse.join(", ")}</dd></div>
  </dl>;
}

function OutputCard({
  item,
  busy,
  onReview,
  onPromote,
  onDownload,
}: {
  item: CompanyGeneratedOutputItem;
  busy: boolean;
  onReview: (
    item: CompanyGeneratedOutputItem,
    input:
      | { disposition: "Rejected"; reason: string }
      | { disposition: "KeepTransient" }
      | { disposition: "PromotionRequested"; document_title: string; semantic_role: string },
  ) => Promise<void>;
  onPromote: (item: CompanyGeneratedOutputItem) => Promise<void>;
  onDownload: (item: CompanyGeneratedOutputItem) => Promise<void>;
}) {
  const { text } = useWorkspaceLanguage();
  const [reason, setReason] = useState("");
  const [documentTitle, setDocumentTitle] = useState(item.review.document_title ?? item.filename);
  const [semanticRole, setSemanticRole] = useState(item.review.semantic_role ?? "company-project-document");
  const promoted = item.canonical_promotion !== null;
  const disposition = item.review.disposition;
  const badge = promoted
    ? text("Промоутировано канонически", "Canonically promoted")
    : disposition === "PromotionRequested"
      ? text("Transient · запрошено продвижение", "Transient · promotion requested")
      : disposition === "Rejected"
        ? text("Transient · отклонено", "Transient · rejected")
        : disposition === "KeepTransient"
          ? text("Transient · оставить как есть", "Transient · keep as-is")
          : text("Transient · ожидает review", "Transient · awaiting review");

  return <article className="company-card asset-library-card">
    <header className="company-card-head">
      <div>
        <p className="eyebrow">TransientOutput</p>
        <h2>{item.filename}</h2>
        <p className="project-source-updated">{text("Создан", "Created")}: {prettyDate(item.created_at)}</p>
      </div>
      <span className={`company-state ${promoted ? "company-state-canonical" : "company-state-staged"}`}>{badge}</span>
    </header>

    <p>{text(
      "Этот generated output остаётся TransientOutput. Review не делает его каноническим; успешный Governed Execution создаёт отдельную immutable Document/Asset version.",
      "This generated output remains a TransientOutput. Review does not make it canonical; a successful Governed Execution creates a separate immutable Document/Asset version.",
    )}</p>

    <dl className="company-facts asset-human-facts">
      <div><dt>{text("Проект", "Project")}</dt><dd>{item.project_id}</dd></div>
      <div><dt>{text("Исходная версия шаблона", "Source template version")}</dt><dd>{item.source_version_id}</dd></div>
      <div><dt>{text("Точный источник подтверждён", "Exact source resolved")}</dt><dd>{item.exact_source_available ? text("Да", "Yes") : text("Нет", "No")}</dd></div>
      <div><dt>{text("Review disposition", "Review disposition")}</dt><dd>{disposition}</dd></div>
    </dl>

    {item.inherited_handling ? <section className="asset-review-proof">
      <h3>{text("Унаследованный handling", "Inherited handling")}</h3>
      <p>{text(
        "P10.05 не расширяет правила generated output относительно admitted source: эти значения наследуются и повторно проверяются перед canonical promotion.",
        "P10.05 does not broaden the generated output beyond its admitted source: these values are inherited and revalidated before canonical promotion.",
      )}</p>
      <Handling value={item.inherited_handling} />
    </section> : <p className="boundary-note" role="status">{text(
      "Exact admitted source сейчас недоступен; governed promotion заблокирован fail-closed.",
      "The exact admitted source is currently unavailable; governed promotion is fail-closed.",
    )}</p>}

    <div className="asset-card-actions">
      <button type="button" disabled={busy} onClick={() => void onDownload(item)}>{text("Скачать для review", "Download for review")}</button>
      {!promoted ? <button type="button" disabled={busy || !item.exact_source_available} onClick={() => void onReview(item, { disposition: "KeepTransient" })}>{text("Оставить transient", "Keep transient")}</button> : null}
    </div>

    {!promoted ? <form className="asset-reject-form" onSubmit={(event) => {
      event.preventDefault();
      void onReview(item, { disposition: "Rejected", reason });
    }}>
      <label>{text("Причина отклонения", "Rejection reason")}<input value={reason} onChange={(event) => setReason(event.target.value)} required maxLength={600} /></label>
      <button type="submit" disabled={busy}>{text("Отклонить", "Reject")}</button>
    </form> : null}

    {!promoted ? <form className="asset-inline-form" onSubmit={(event) => {
      event.preventDefault();
      void onReview(item, {
        disposition: "PromotionRequested",
        document_title: documentTitle,
        semantic_role: semanticRole,
      });
    }}>
      <h3>{text("Запросить governed promotion", "Request governed promotion")}</h3>
      <label>{text("Название документа", "Document title")}<input value={documentTitle} onChange={(event) => setDocumentTitle(event.target.value)} required maxLength={320} /></label>
      <label>{text("Роль документа", "Document role")}<input value={semanticRole} onChange={(event) => setSemanticRole(event.target.value)} required maxLength={96} /></label>
      <button type="submit" disabled={busy || !item.exact_source_available}>{text("Зафиксировать запрос на promotion", "Record promotion request")}</button>
    </form> : null}

    {disposition === "PromotionRequested" && !promoted ? <section className="asset-review-actions">
      <h3>{text("Последнее подтверждение", "Final confirmation")}</h3>
      <p>{text(
        "Команда ниже не получает authority из интерфейса. Сервер заново проверяет credential, exact Authorization grant, Organizational Authority, Data Governance, Validation и Consequential Approval.",
        "The command below gets no authority from the UI. The server revalidates credential, exact Authorization grant, Organizational Authority, Data Governance, Validation, and Consequential Approval.",
      )}</p>
      <button type="button" disabled={busy || !item.promotion_available} onClick={() => void onPromote(item)}>{text("Промоутировать через Governed Execution", "Promote through Governed Execution")}</button>
      {!item.promotion_available ? <p className="boundary-note">{text(
        "Governed promotion сейчас недоступен: отсутствует exact server-side evidence/grant или admitted source.",
        "Governed promotion is currently unavailable: exact server-side evidence/grant or admitted source is missing.",
      )}</p> : null}
    </section> : null}

    {promoted ? <section className="asset-review-proof">
      <h3>{text("Канонический результат", "Canonical result")}</h3>
      <p>{text(
        "Создана отдельная immutable governed Document/Asset version. Исходный файл выше по-прежнему классифицирован как TransientOutput.",
        "A separate immutable governed Document/Asset version was created. The source file above is still classified as a TransientOutput.",
      )}</p>
      <dl className="company-facts"><div><dt>{text("Промоутировано", "Promoted")}</dt><dd>{prettyDate(item.canonical_promotion?.promoted_at)}</dd></div></dl>
    </section> : null}

    <details className="project-technical-details">
      <summary>{text("Техническая идентичность и provenance", "Technical identity and provenance")}</summary>
      <dl className="company-facts">
        <div><dt>Output ID</dt><dd><code>{item.output_id}</code></dd></div>
        <div><dt>Output SHA-256</dt><dd><code>{item.output_sha256}</code></dd></div>
        <div><dt>Source material</dt><dd><code>{item.source_material_id}</code></dd></div>
        <div><dt>Source version</dt><dd><code>{item.source_version_id}</code></dd></div>
        <div><dt>Source SHA-256</dt><dd><code>{item.source_sha256}</code></dd></div>
        {item.canonical_promotion ? <>
          <div><dt>Document version</dt><dd><code>{item.canonical_promotion.document_version}</code></dd></div>
          <div><dt>Asset designation</dt><dd><code>{item.canonical_promotion.designation_version}</code></dd></div>
          <div><dt>Promotion Event</dt><dd><code>{item.canonical_promotion.event_version}</code></dd></div>
          <div><dt>Provenance</dt><dd>{item.canonical_promotion.provenance_refs.map((ref) => <div key={ref}><code>{ref}</code></div>)}</dd></div>
        </> : null}
      </dl>
    </details>
  </article>;
}

export function CompanyGeneratedOutputs({ csrfToken }: { csrfToken: string }) {
  const { text } = useWorkspaceLanguage();
  const [state, setState] = useState<State>({ kind: "loading" });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      setState({ kind: "ready", data: await loadCompanyGeneratedOutputs() });
    } catch (error) {
      setState({ kind: "error", code: error instanceof Error ? error.message : "COMPANY_GENERATED_OUTPUTS_UNAVAILABLE" });
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const run = async (action: () => Promise<void>, success: string) => {
    setMessage(null);
    setBusy(true);
    try {
      await action();
      setMessage(success);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "COMPANY_GENERATED_OUTPUT_ACTION_FAILED");
    } finally {
      setBusy(false);
    }
  };

  const download = async (item: CompanyGeneratedOutputItem) => {
    setBusy(true);
    try {
      const downloaded = await downloadCompanyOutput(item.download_href);
      const href = URL.createObjectURL(downloaded.blob);
      const anchor = document.createElement("a");
      anchor.href = href;
      anchor.download = downloaded.filename;
      anchor.click();
      URL.revokeObjectURL(href);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "COMPANY_OUTPUT_DOWNLOAD_FAILED");
    } finally {
      setBusy(false);
    }
  };

  if (state.kind === "loading") return <section className="company-page" aria-live="polite">{text("Открываем generated outputs…", "Opening generated outputs…")}</section>;
  if (state.kind === "error") return <section className="company-page" role="alert"><p className="eyebrow">P10.05 · operation boundary Provisional 0.2.0</p><h1>{text("Generated outputs недоступны", "Generated outputs unavailable")}</h1><code>{state.code}</code><div><button type="button" onClick={() => void refresh()}>{text("Повторить", "Retry")}</button></div></section>;

  return <section className="company-page" aria-labelledby="company-generated-outputs-title">
    <header className="company-page-head asset-library-head">
      <p className="eyebrow">P10.05 · operation boundary Provisional 0.2.0</p>
      <h1 id="company-generated-outputs-title">{text("Созданные документы · review", "Generated documents · review")}</h1>
      <p>{text(
        "Generated Artifact остаётся TransientOutput по умолчанию. Просмотр, скачивание, отклонение или повторное использование не делают его каноническим. Только отдельный успешно завершённый Governed Execution создаёт новую governed Document/Asset version.",
        "A Generated Artifact remains a TransientOutput by default. Viewing, downloading, rejecting, or reusing it does not make it canonical. Only a separate successful Governed Execution creates a new governed Document/Asset version.",
      )}</p>
      <details className="company-boundary-details"><summary>{text("Граница authority и scope", "Authority and scope boundary")}</summary><p>{text(
        "UI/BFF не являются authority. P10.05 не создаёт validated Knowledge и не предоставляет отправку, подпись или публикацию: такие действия потребуют отдельного governed scope.",
        "UI/BFF are not authority. P10.05 creates no validated Knowledge and provides no send, signature, or publication action; those require separate governed scope.",
      )}</p></details>
    </header>

    {message ? <p className="company-message" role="status">{message}</p> : null}
    {state.data.items.length ? <div className="company-grid">{state.data.items.map((item) => <OutputCard
      key={item.output_id}
      item={item}
      busy={busy}
      onDownload={download}
      onReview={async (target, input) => run(
        async () => { await reviewCompanyGeneratedOutput(target.output_id, input, csrfToken); },
        input.disposition === "Rejected"
          ? text("Output отклонён без canonical mutation.", "Output rejected without canonical mutation.")
          : input.disposition === "KeepTransient"
            ? text("Output оставлен TransientOutput.", "Output remains a TransientOutput.")
            : text("Запрос на governed promotion зафиксирован; canonical state пока не изменён.", "Governed promotion request recorded; canonical state has not changed yet."),
      )}
      onPromote={async (target) => run(
        async () => { await promoteCompanyGeneratedOutput(target.output_id, csrfToken); },
        text("Governed promotion завершён; создана отдельная каноническая Document/Asset version.", "Governed promotion completed; a separate canonical Document/Asset version was created."),
      )}
    />)}</div> : <p className="asset-empty-state">{text("Generated outputs пока нет. Создайте документ из принятого шаблона в «Материалах компании».", "There are no generated outputs yet. Generate a document from an admitted template in Company materials.")}</p>}
  </section>;
}
