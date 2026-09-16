import { useEffect, useMemo, useState } from "react";
import { CompanyAssetDiscovery } from "./CompanyAssetDiscovery";
import {
  admitCompanyAssetVersion,
  downloadCompanyOutput,
  exportCompanyAssetLibrary,
  fileToBase64,
  generateCompanyDocx,
  loadCompanyAssetLibrary,
  loadCompanyPortfolio,
  rejectCompanyAssetVersion,
  stageCompanyMaterial,
  submitCompanyAssetReview,
} from "./f11Api";
import type {
  CompanyAssetLibraryItem,
  CompanyAssetLibraryProjection,
  GeneratedCompanyOutput,
} from "./f11Types";
import { useWorkspaceLanguage } from "./i18n";
import "./CompanyWorkspace.css";
import "./CompanyAssetLibrary.css";

const DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
const PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation";
const MAX_FILE_BYTES = 8 * 1024 * 1024;
const AI_GROUNDING_REUSE = "company-internal-ai-grounding";
const ACCEPTED_FILE_TYPES = ".docx,.pptx,.pdf,.png,.jpg,.jpeg,.webp,.txt,.md";
const ALLOWED_MEDIA_TYPES = new Set([
  DOCX,
  PPTX,
  "application/pdf",
  "image/png",
  "image/jpeg",
  "image/webp",
  "text/plain",
  "text/markdown",
]);

const MATERIAL_ROLE_OPTIONS = [
  { value: "document-template", ru: "Шаблон документа", en: "Document template" },
  { value: "brandbook", ru: "Брендбук", en: "Brandbook" },
  { value: "logo", ru: "Логотип", en: "Logo" },
  { value: "source", ru: "Исходный материал", en: "Source material" },
  { value: "other", ru: "Другое", en: "Other" },
] as const;

type MaterialRoleChoice = typeof MATERIAL_ROLE_OPTIONS[number]["value"] | "";
type ViewKey = keyof CompanyAssetLibraryProjection["views"];
type State =
  | { kind: "loading" }
  | { kind: "ready"; data: CompanyAssetLibraryProjection }
  | { kind: "error"; code: string };

const VIEW_OPTIONS: Array<{ key: ViewKey; ru: string; en: string }> = [
  { key: "drafts", ru: "Черновики", en: "Drafts" },
  { key: "review", ru: "На рассмотрении", en: "In review" },
  { key: "accepted", ru: "Принято", en: "Accepted" },
  { key: "archive", ru: "Архив / заменено", en: "Archive / superseded" },
];

function declaredMediaType(file: File): string | null {
  if (ALLOWED_MEDIA_TYPES.has(file.type)) return file.type;
  const extension = file.name.toLowerCase().split(".").pop() ?? "";
  const byExtension: Record<string, string> = {
    docx: DOCX,
    pptx: PPTX,
    pdf: "application/pdf",
    png: "image/png",
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    webp: "image/webp",
    txt: "text/plain",
    md: "text/markdown",
  };
  return byExtension[extension] ?? null;
}

function allItems(data: CompanyAssetLibraryProjection): CompanyAssetLibraryItem[] {
  return [...data.views.drafts, ...data.views.review, ...data.views.accepted, ...data.views.archive];
}

function latestStagedItems(data: CompanyAssetLibraryProjection): CompanyAssetLibraryItem[] {
  const byMaterial = new Map<string, CompanyAssetLibraryItem>();
  for (const item of allItems(data)) {
    const current = byMaterial.get(item.material_id);
    if (!current || item.received_at > current.received_at) byMaterial.set(item.material_id, item);
  }
  return [...byMaterial.values()].sort((a, b) => a.title.localeCompare(b.title));
}

function currentAdmittedItems(data: CompanyAssetLibraryProjection): CompanyAssetLibraryItem[] {
  return [...data.views.accepted, ...data.views.archive]
    .filter((item) => item.canonical?.current === true)
    .sort((a, b) => a.title.localeCompare(b.title, "ru"));
}

function admittedDocxItems(data: CompanyAssetLibraryProjection): CompanyAssetLibraryItem[] {
  return currentAdmittedItems(data)
    .filter((item) => item.semantic_role === "document-template" && item.media_type === DOCX)
    .sort((a, b) => b.received_at.localeCompare(a.received_at));
}

function assetApplicationLabel(item: CompanyAssetLibraryItem, text: (ru: string, en: string) => string): string {
  if (item.semantic_role === "logo" && ["image/png", "image/jpeg"].includes(item.media_type)) {
    return text("будет встроен в DOCX", "will be embedded in the DOCX");
  }
  if (["text/plain", "text/markdown"].includes(item.media_type)) {
    return text("текст будет включён", "text will be included");
  }
  return text("будет закреплён как точный reference", "will be pinned as an exact reference");
}

function prettyDate(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("ru-RU");
}

function MaterialCard({
  item,
  busy,
  admissionAvailable,
  onReview,
  onReject,
  onAdmit,
  onNewVersion,
}: {
  item: CompanyAssetLibraryItem;
  busy: boolean;
  admissionAvailable: boolean;
  onReview: (item: CompanyAssetLibraryItem, deletionRule: string, permittedReuse: string[]) => Promise<void>;
  onReject: (item: CompanyAssetLibraryItem, reason: string) => Promise<void>;
  onAdmit: (item: CompanyAssetLibraryItem) => Promise<void>;
  onNewVersion: (item: CompanyAssetLibraryItem) => void;
}) {
  const { text } = useWorkspaceLanguage();
  const [deletionRule, setDeletionRule] = useState(item.review.policy?.deletion_rule ?? "");
  const [reuse, setReuse] = useState(item.review.policy?.permitted_reuse.join(", ") ?? "");
  const [rejectReason, setRejectReason] = useState("");
  const rejected = item.review.state === "Rejected";
  const canonical = item.canonical;
  const badge = canonical
    ? canonical.current ? text("Канонически принято", "Canonically accepted") : text("Заменено", "Superseded")
    : item.review.state === "InReview"
      ? text("Staged · на рассмотрении", "Staged · in review")
      : rejected ? text("Staged · отклонено", "Staged · rejected") : text("Staged · черновик", "Staged · draft");

  const reuseValues = () => Array.from(new Set(reuse.split(",").map((value) => value.trim()).filter(Boolean)));
  const aiGroundingEnabled = reuseValues().includes(AI_GROUNDING_REUSE);
  const setAiGrounding = (enabled: boolean) => {
    const values = reuseValues().filter((value) => value !== AI_GROUNDING_REUSE);
    if (enabled) values.push(AI_GROUNDING_REUSE);
    setReuse(values.join(", "));
  };

  const submitReview = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onReview(item, deletionRule, reuseValues());
  };

  const submitReject = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onReject(item, rejectReason);
    setRejectReason("");
  };

  return <article className="company-card asset-library-card">
    <header className="company-card-head">
      <div>
        <p className="eyebrow">{item.semantic_role}</p>
        <h2>{item.title}</h2>
        <p className="project-source-updated">{text("Получено", "Received")}: {prettyDate(item.received_at)}</p>
      </div>
      <span className={`company-state ${canonical ? "company-state-canonical" : "company-state-staged"}`}>{badge}</span>
    </header>

    <dl className="company-facts asset-human-facts">
      <div><dt>{text("Проект", "Project")}</dt><dd>{item.project_id === "COMPANY" ? text("Компания в целом", "Company-wide") : item.project_id}</dd></div>
      <div><dt>{text("Тип материала", "Material type")}</dt><dd>{item.semantic_role}</dd></div>
      <div><dt>{text("Классификация", "Classification")}</dt><dd>{item.classification}</dd></div>
      <div><dt>{text("Назначение", "Purpose")}</dt><dd>{item.purpose}</dd></div>
      <div><dt>{text("Права использования", "Rights")}</dt><dd>{item.rights}</dd></div>
      <div><dt>Retention</dt><dd>{item.retention_rule}</dd></div>
      {item.review.policy ? <><div><dt>{text("Удаление", "Deletion")}</dt><dd>{item.review.policy.deletion_rule}</dd></div><div><dt>{text("Разрешённое повторное использование", "Permitted reuse")}</dt><dd>{item.review.policy.permitted_reuse.join(", ")}</dd></div></> : null}
    </dl>

    {item.review.state === "InReview" ? <section className="asset-review-proof" aria-label={text("Точная версия для подтверждения", "Exact version for confirmation")}>
      <h3>{text("Перед подтверждением", "Before confirmation")}</h3>
      <p>{text("Проверьте точный источник и правила этой версии. Кнопка не создаёт authority: сервер заново проверяет Governed Execution и независимые gates.", "Verify the exact source and handling rules for this version. The button does not create authority: the server revalidates Governed Execution and independent gates.")}</p>
      <dl className="company-facts">
        <div><dt>{text("Источник", "Source")}</dt><dd>{item.title}</dd></div>
        <div><dt>{text("Роль", "Role")}</dt><dd>{item.semantic_role}</dd></div>
        <div><dt>{text("Классификация", "Classification")}</dt><dd>{item.classification}</dd></div>
        <div><dt>Retention</dt><dd>{item.retention_rule}</dd></div>
        <div><dt>SHA-256</dt><dd><code>{item.content_sha256}</code></dd></div>
      </dl>
    </section> : null}

    {!canonical && item.review.state !== "InReview" ? <form className="asset-inline-form" onSubmit={(event) => void submitReview(event)}>
      <h3>{rejected ? text("Вернуть на рассмотрение", "Return to review") : text("Передать на рассмотрение", "Submit for review")}</h3>
      {rejected && item.review.reason ? <p className="boundary-note">{text("Причина отклонения", "Rejection reason")}: {item.review.reason}</p> : null}
      <label>{text("Правило удаления", "Deletion rule")}<input value={deletionRule} onChange={(event) => setDeletionRule(event.target.value)} required maxLength={240} placeholder={text("Укажите явно", "State explicitly")} /></label>
      <label>{text("Разрешённое повторное использование", "Permitted reuse")}<input value={reuse} onChange={(event) => setReuse(event.target.value)} required maxLength={400} placeholder={text("Через запятую", "Comma separated")} /></label>
      <label className="asset-generation-option">
        <input type="checkbox" aria-label={text("Разрешить Arvectum AI использовать эту версию как источник", "Allow Arvectum AI to use this version as a source")} checked={aiGroundingEnabled} onChange={(event) => setAiGrounding(event.target.checked)} />
        <span><strong>{text("Разрешить Arvectum AI использовать эту версию как источник", "Allow Arvectum AI to use this version as a source")}</strong><small>{text("Только для этой exact версии. Фактическое использование всё равно требует текущего доступа, действующего Product Contract и server-side revalidation.", "This applies only to this exact version. Actual use still requires current access, the effective Product Contract, and server-side revalidation.")}</small></span>
      </label>
      <button type="submit" disabled={busy}>{text("Передать на рассмотрение", "Submit for review")}</button>
    </form> : null}

    {item.review.state === "InReview" && !canonical ? <div className="asset-review-actions">
      <button type="button" disabled={busy || !admissionAvailable} onClick={() => void onAdmit(item)}>{text("Принять через Governed Execution", "Admit through Governed Execution")}</button>
      {!admissionAvailable ? <p className="boundary-note">{text("Текущий server-side admission provider недоступен: каноническое изменение заблокировано.", "The current server-side admission provider is unavailable: canonical change is blocked.")}</p> : null}
      <form className="asset-reject-form" onSubmit={(event) => void submitReject(event)}>
        <label>{text("Причина отклонения", "Rejection reason")}<input value={rejectReason} onChange={(event) => setRejectReason(event.target.value)} required maxLength={600} /></label>
        <button type="submit" disabled={busy}>{text("Отклонить", "Reject")}</button>
      </form>
    </div> : null}

    {canonical?.current ? <div className="asset-card-actions"><button type="button" disabled={busy} onClick={() => onNewVersion(item)}>{text("Добавить новую версию", "Add new version")}</button></div> : null}

    <details className="project-technical-details">
      <summary>{text("Техническая идентичность и provenance", "Technical identity and provenance")}</summary>
      <dl className="company-facts">
        <div><dt>Material</dt><dd><code>{item.material_id}</code></dd></div>
        <div><dt>Staged version</dt><dd><code>{item.version_id}</code></dd></div>
        <div><dt>{text("Предшественник", "Predecessor")}</dt><dd><code>{item.predecessor_version_id ?? "—"}</code></dd></div>
        <div><dt>{text("Загрузил", "Uploader")}</dt><dd><code>{item.uploader}</code></dd></div>
        <div><dt>SHA-256</dt><dd><code>{item.content_sha256}</code></dd></div>
        {canonical ? <><div><dt>Document version</dt><dd><code>{canonical.document_version}</code></dd></div><div><dt>Asset designation</dt><dd><code>{canonical.designation_version}</code></dd></div><div><dt>Admission Event</dt><dd><code>{canonical.event_version}</code></dd></div><div><dt>Provenance</dt><dd>{canonical.provenance_refs.map((ref) => <div key={ref}><code>{ref}</code></div>)}</dd></div></> : null}
      </dl>
    </details>
  </article>;
}

export function CompanyMaterials({ csrfToken }: { csrfToken: string }) {
  const { text } = useWorkspaceLanguage();
  const [state, setState] = useState<State>({ kind: "loading" });
  const [activeView, setActiveView] = useState<ViewKey>("drafts");
  const [projectOptions, setProjectOptions] = useState<Array<{ id: string; label: string }>>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [generated, setGenerated] = useState<GeneratedCompanyOutput | null>(null);
  const [semanticRoleChoice, setSemanticRoleChoice] = useState<MaterialRoleChoice>("");
  const [selectedMaterialId, setSelectedMaterialId] = useState("");
  const [reuseSourceVersion, setReuseSourceVersion] = useState("");

  const refresh = async () => {
    setState({ kind: "loading" });
    try {
      setState({ kind: "ready", data: await loadCompanyAssetLibrary() });
    } catch (error) {
      setState({ kind: "error", code: error instanceof Error ? error.message : "COMPANY_ASSET_LIBRARY_UNAVAILABLE" });
    }
  };

  useEffect(() => {
    void refresh();
    void loadCompanyPortfolio()
      .then((portfolio) => setProjectOptions(
        portfolio.projects.filter((project) => project.id.startsWith("PORT-")).map((project) => ({ id: project.id, label: project.label })),
      ))
      .catch(() => setProjectOptions([]));
  }, []);

  const latest = useMemo(() => state.kind === "ready" ? latestStagedItems(state.data) : [], [state]);
  const currentAdmitted = useMemo(() => state.kind === "ready" ? currentAdmittedItems(state.data) : [], [state]);
  const docxVersions = useMemo(() => state.kind === "ready" ? admittedDocxItems(state.data) : [], [state]);
  const brandInputs = useMemo(() => currentAdmitted.filter((item) => ["logo", "brandbook"].includes(item.semantic_role)), [currentAdmitted]);
  const sourceInputs = useMemo(() => currentAdmitted.filter((item) => item.semantic_role === "source"), [currentAdmitted]);
  const referenceInputs = useMemo(() => currentAdmitted.filter((item) => !["document-template", "logo", "brandbook", "source"].includes(item.semantic_role)), [currentAdmitted]);

  const run = async (action: () => Promise<void>) => {
    setMessage(null);
    setBusy(true);
    try {
      await action();
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "COMPANY_ASSET_ACTION_FAILED");
    } finally {
      setBusy(false);
    }
  };

  const submitStage = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    setGenerated(null);
    const form = event.currentTarget;
    const data = new FormData(form);
    const file = data.get("file");
    if (!(file instanceof File) || file.size === 0 || file.size > MAX_FILE_BYTES) {
      setMessage(text("Выберите файл до 8 MiB.", "Choose a file up to 8 MiB."));
      return;
    }
    const mediaType = declaredMediaType(file);
    if (!mediaType) {
      setMessage(text("Этот тип файла не входит в безопасный allowlist.", "This file type is outside the safe allowlist."));
      return;
    }
    const roleChoice = String(data.get("semantic_role_choice") ?? "");
    const semanticRole = roleChoice === "other" ? String(data.get("semantic_role_other") ?? "").trim() : roleChoice;
    if (!semanticRole) {
      setMessage(text("Выберите тип материала или укажите свой вариант.", "Choose a material type or enter a custom one."));
      return;
    }
    setBusy(true);
    try {
      const staged = await stageCompanyMaterial({
        ...(selectedMaterialId ? { material_id: selectedMaterialId } : {}),
        project_id: String(data.get("project_id") ?? "COMPANY"),
        filename: file.name,
        media_type: mediaType,
        semantic_role: semanticRole,
        classification: String(data.get("classification") ?? ""),
        purpose: String(data.get("purpose") ?? ""),
        rights: String(data.get("rights") ?? ""),
        retention_rule: String(data.get("retention_rule") ?? ""),
        content_base64: await fileToBase64(file),
      }, csrfToken);
      setMessage(text(`Черновик ${staged.filename} сохранён как новая immutable staged-версия. Канонический state не изменён.`, `${staged.filename} was saved as a new immutable staged draft. Canonical state did not change.`));
      form.reset();
      setSemanticRoleChoice("");
      setSelectedMaterialId("");
      setActiveView("drafts");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "COMPANY_MATERIAL_STAGE_FAILED");
    } finally {
      setBusy(false);
    }
  };

  const submitGenerate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    setGenerated(null);
    const data = new FormData(event.currentTarget);
    const composite = String(data.get("source_version") ?? "");
    const [materialId, versionId] = composite.split("::", 2);
    if (!materialId || !versionId) return;
    const assetInputs: Array<{ use_as: "brand" | "source" | "reference"; material_id: string; version_id: string }> = [];
    for (const value of data.getAll("asset_input")) {
      const [useAs, inputMaterialId, inputVersionId] = String(value).split("::", 3);
      if (!inputMaterialId || !inputVersionId || !["brand", "source", "reference"].includes(useAs)) {
        setMessage(text("Выбор дополнительного материала устарел или повреждён. Обновите страницу и выберите материалы заново.", "The auxiliary asset selection is stale or invalid. Refresh and select the assets again."));
        return;
      }
      assetInputs.push({
        use_as: useAs as "brand" | "source" | "reference",
        material_id: inputMaterialId,
        version_id: inputVersionId,
      });
    }
    if (assetInputs.length > 8) {
      setMessage(text("Можно выбрать не более 8 дополнительных материалов.", "Choose no more than 8 auxiliary assets."));
      return;
    }
    setBusy(true);
    try {
      const output = await generateCompanyDocx({
        material_id: materialId,
        version_id: versionId,
        asset_inputs: assetInputs,
        title: String(data.get("title") ?? ""),
        body: String(data.get("body") ?? ""),
        date: String(data.get("date") ?? ""),
      }, csrfToken);
      setGenerated(output);
      setMessage(text(
        `Документ создан как Transient Output из точного шаблона и ${assetInputs.length} дополнительных принятых материалов.`,
        `Document created as a Transient Output from the exact template and ${assetInputs.length} additional admitted assets.`,
      ));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "COMPANY_GENERATION_FAILED");
    } finally {
      setBusy(false);
    }
  };

  const downloadGenerated = async (output: GeneratedCompanyOutput) => {
    setBusy(true);
    try {
      const downloaded = await downloadCompanyOutput(output.output.download_href);
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

  const downloadExport = async () => {
    setBusy(true);
    try {
      const exported = await exportCompanyAssetLibrary(100);
      const href = URL.createObjectURL(new Blob([JSON.stringify(exported, null, 2)], { type: "application/json" }));
      const anchor = document.createElement("a");
      anchor.href = href;
      anchor.download = "arvectum-company-assets.json";
      anchor.click();
      URL.revokeObjectURL(href);
      setMessage(text("Выгружена bounded owner-scoped проекция библиотеки.", "Downloaded the bounded owner-scoped library projection."));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "COMPANY_ASSET_EXPORT_FAILED");
    } finally {
      setBusy(false);
    }
  };

  if (state.kind === "loading") return <section className="company-page" aria-live="polite">{text("Открываем библиотеку материалов…", "Opening the asset library…")}</section>;
  if (state.kind === "error") return <section className="company-page" role="alert"><p className="eyebrow">P10.04 · admission boundary Provisional 0.2.0 · AI grounding Provisional 0.3.0</p><h1>{text("Материалы компании недоступны", "Company materials unavailable")}</h1><code>{state.code}</code><div><button type="button" onClick={() => void refresh()}>{text("Повторить", "Retry")}</button></div></section>;

  const currentItems = state.data.views[activeView];
  const admissionAvailable = state.data.actions.governed_admission_available;

  return <section className="company-page" aria-labelledby="company-materials-title">
    <header className="company-page-head asset-library-head">
      <p className="eyebrow">P10.04 / P10.09-A / P10.09-B · admission boundary Provisional 0.2.0 · P10.09-C AI grounding Provisional 0.3.0</p>
      <h1 id="company-materials-title">{text("Материалы компании", "Company materials")}</h1>
      <p>{text("Принятые материалы доступны как обычная рабочая библиотека. Черновики и review остаются staged/non-canonical; только успешно завершённый Governed Execution создаёт принятую каноническую версию.", "Admitted assets are available as an ordinary working library. Drafts and review remain staged/non-canonical; only a successful Governed Execution creates an admitted canonical version.")}</p>
      <details className="company-boundary-details"><summary>{text("Граница authority", "Authority boundary")}</summary><p>{text("Workspace показывает состояние и инициирует команду, но не является источником authority. Authentication, Authorization, Organizational Authority, Data Governance, Validation и Consequential Approval не выводятся из видимости кнопки. Generated output остаётся Transient Output и не становится validated Knowledge.", "Workspace presents state and initiates a command but is not an authority source. Authentication, Authorization, Organizational Authority, Data Governance, Validation, and Consequential Approval are not inferred from button visibility. Generated output remains a Transient Output and does not become validated Knowledge.")}</p></details>
      <button type="button" disabled={busy} onClick={() => void downloadExport()}>{text("Экспортировать доступную историю", "Export accessible history")}</button>
    </header>

    <CompanyAssetDiscovery
      data={state.data}
      projects={projectOptions}
      onReuse={(item) => {
        setReuseSourceVersion(`${item.material_id}::${item.version_id}`);
        setMessage(text(`Для генерации выбрана точная принятая версия «${item.title}».`, `The exact admitted version “${item.title}” is selected for generation.`));
      }}
    />

    <section aria-labelledby="company-asset-governance-title">
      <div className="company-page-head"><p className="eyebrow">P10.04</p><h2 id="company-asset-governance-title">{text("Управление поступлением и версиями", "Admission and version management")}</h2><p>{text("Этот раздел нужен для загрузки, review и governed admission. Для обычного поиска и открытия используйте библиотеку выше.", "Use this section for upload, review, and governed admission. For ordinary discovery and opening, use the library above.")}</p></div>
      <nav className="asset-library-tabs" aria-label={text("Состояния материалов", "Material lifecycle views")}>
        {VIEW_OPTIONS.map((view) => <button key={view.key} type="button" className={activeView === view.key ? "active" : ""} onClick={() => setActiveView(view.key)}>{text(view.ru, view.en)} <span>{state.data.views[view.key].length}</span></button>)}
      </nav>

      <section className="asset-library-view" aria-live="polite">
        {currentItems.length ? <div className="company-grid">{currentItems.map((item) => <MaterialCard
          key={item.version_id}
          item={item}
          busy={busy}
          admissionAvailable={admissionAvailable}
          onReview={async (target, deletionRule, permittedReuse) => run(async () => {
            await submitCompanyAssetReview(target.material_id, target.version_id, { deletion_rule: deletionRule, permitted_reuse: permittedReuse }, csrfToken);
            setActiveView("review");
            setMessage(text("Точная staged-версия передана на рассмотрение; canonical state не изменён.", "The exact staged version entered review; canonical state did not change."));
          })}
          onReject={async (target, reason) => run(async () => {
            await rejectCompanyAssetVersion(target.material_id, target.version_id, reason, csrfToken);
            setActiveView("archive");
            setMessage(text("Версия отклонена без canonical mutation.", "Version rejected without canonical mutation."));
          })}
          onAdmit={async (target) => run(async () => {
            await admitCompanyAssetVersion(target.material_id, target.version_id, csrfToken);
            setActiveView("accepted");
            setMessage(text("Governed admission завершён; точная версия отображается как канонически принятая.", "Governed admission completed; the exact version is now shown as canonically accepted."));
          })}
          onNewVersion={(target) => {
            setSelectedMaterialId(target.material_id);
            setMessage(text(`Форма добавления переключена на новую версию «${target.title}».`, `The add form is now creating a new version of “${target.title}”.`));
          }}
        />)}</div> : <p className="asset-empty-state">{text("В этом состоянии материалов пока нет.", "There are no materials in this lifecycle view yet.")}</p>}
      </section>
    </section>

    {message ? <p className="company-message" role="status">{message}</p> : null}

    <div className="company-two-column">
      <form className="company-form" onSubmit={(event) => void submitStage(event)}>
        <h2>{selectedMaterialId ? text("Добавить новую версию", "Add new version") : text("Добавить материал", "Add material")}</h2>
        <label>{text("Материал", "Material")}<select value={selectedMaterialId} onChange={(event) => setSelectedMaterialId(event.target.value)}><option value="">{text("Новый материал", "New material")}</option>{latest.map((item) => <option key={item.material_id} value={item.material_id}>{item.title}</option>)}</select></label>
        <label>{text("Проект", "Project")}<select name="project_id" defaultValue="COMPANY"><option value="COMPANY">{text("Компания в целом", "Company-wide")}</option>{projectOptions.map((project) => <option key={project.id} value={project.id}>{project.label}</option>)}</select></label>
        <label>{text("Файл", "File")}<input name="file" type="file" accept={ACCEPTED_FILE_TYPES} required /></label>
        <label>{text("Тип материала", "Material type")}<select name="semantic_role_choice" value={semanticRoleChoice} onChange={(event) => setSemanticRoleChoice(event.target.value as MaterialRoleChoice)} required><option value="" disabled>{text("Выберите тип", "Choose type")}</option>{MATERIAL_ROLE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{text(option.ru, option.en)}</option>)}</select></label>
        {semanticRoleChoice === "other" ? <label>{text("Другой тип", "Other type")}<input name="semantic_role_other" required maxLength={96} /></label> : null}
        <label>{text("Классификация", "Classification")}<input name="classification" required maxLength={96} defaultValue="internal" /></label>
        <label>{text("Назначение", "Purpose")}<input name="purpose" required maxLength={240} /></label>
        <label>{text("Права использования", "Rights")}<input name="rights" required maxLength={240} defaultValue="company-internal-use" /></label>
        <label>Retention rule<input name="retention_rule" required maxLength={240} defaultValue="until-replaced-or-explicit-deletion" /></label>
        <button type="submit" disabled={busy}>{busy ? text("Сохраняем…", "Saving…") : text("Сохранить как черновик", "Save as draft")}</button>
      </form>

      <form id="company-docx-generator" className="company-form" onSubmit={(event) => void submitGenerate(event)}>
        <h2>{text("Создать DOCX из принятых материалов", "Generate DOCX from admitted assets")}</h2>
        <p>{text("Выберите текущую принятую версию шаблона и, при необходимости, дополнительные принятые assets. Логотип PNG/JPEG встраивается в DOCX, TXT/MD включается как текст, остальные материалы закрепляются как точные references. Результат остаётся Transient Output.", "Choose the current admitted template version and optional admitted assets. PNG/JPEG logos are embedded in the DOCX, TXT/MD content is included as text, and other assets are pinned as exact references. The result remains a Transient Output.")}</p>
        <label>{text("Текущий принятый шаблон", "Current admitted template")}<select name="source_version" required value={reuseSourceVersion} onChange={(event) => setReuseSourceVersion(event.target.value)}><option value="" disabled>{text("Выберите шаблон", "Choose template")}</option>{docxVersions.map((item) => <option key={item.version_id} value={`${item.material_id}::${item.version_id}`}>{item.title} · {prettyDate(item.received_at)}</option>)}</select></label>
        <section className="asset-generation-inputs" aria-labelledby="asset-generation-inputs-title">
          <h3 id="asset-generation-inputs-title">{text("Дополнительные материалы", "Additional assets")}</h3>
          <p>{text("Используются только текущие канонически принятые версии. Технические идентификаторы подставляются сервером и не требуются для выбора.", "Only current canonically admitted versions are eligible. The server resolves exact technical identities; they are not required for selection.")}</p>
          {brandInputs.length ? <fieldset><legend>{text("Бренд", "Brand")}</legend>{brandInputs.map((item) => <label className="asset-generation-option" key={item.version_id}><input type="checkbox" name="asset_input" value={`brand::${item.material_id}::${item.version_id}`} /><span><strong>{item.title}</strong><small>{assetApplicationLabel(item, text)}</small></span></label>)}</fieldset> : null}
          {sourceInputs.length ? <fieldset><legend>{text("Исходные материалы", "Source materials")}</legend>{sourceInputs.map((item) => <label className="asset-generation-option" key={item.version_id}><input type="checkbox" name="asset_input" value={`source::${item.material_id}::${item.version_id}`} /><span><strong>{item.title}</strong><small>{assetApplicationLabel(item, text)}</small></span></label>)}</fieldset> : null}
          {referenceInputs.length ? <fieldset><legend>{text("References", "References")}</legend>{referenceInputs.map((item) => <label className="asset-generation-option" key={item.version_id}><input type="checkbox" name="asset_input" value={`reference::${item.material_id}::${item.version_id}`} /><span><strong>{item.title}</strong><small>{assetApplicationLabel(item, text)}</small></span></label>)}</fieldset> : null}
        </section>
        <label>{text("Заголовок", "Title")}<input name="title" required maxLength={320} /></label>
        <label>{text("Текст", "Body")}<textarea name="body" required maxLength={6000} rows={9} /></label>
        <label>{text("Дата", "Date")}<input name="date" required maxLength={80} defaultValue={new Date().toLocaleDateString("ru-RU")} /></label>
        <button type="submit" disabled={busy || docxVersions.length === 0}>{text("Создать transient DOCX", "Generate transient DOCX")}</button>
        {docxVersions.length === 0 ? <p className="boundary-note">{text("Сначала примите DOCX-шаблон через governed admission.", "First admit a DOCX template through governed admission.")}</p> : null}
        {generated ? <div className="company-output"><strong>Transient Output</strong><p>{text("Шаблон", "Template")}: {docxVersions.find((item) => item.version_id === generated.output.source_version_id)?.title ?? text("точная принятая версия", "exact admitted version")}</p>{generated.output.input_assets?.length ? <div><p><strong>{text("Использованные материалы", "Used assets")}</strong></p><ul>{generated.output.input_assets.map((item) => <li key={`${item.material_id}-${item.version_id}`}>{item.title} · {item.application === "embedded-image" ? text("встроен", "embedded") : item.application === "text-included" ? text("текст включён", "text included") : text("точный reference", "exact reference")}</li>)}</ul></div> : null}<button type="button" disabled={busy} onClick={() => void downloadGenerated(generated)}>{text("Скачать DOCX", "Download DOCX")}</button><details><summary>{text("Технические сведения", "Technical details")}</summary><code>{generated.output.output_id}</code><br /><code>{generated.output.source_version_id}</code>{generated.output.generation_input_digest ? <><br /><code>{generated.output.generation_input_digest}</code></> : null}</details></div> : null}
      </form>
    </div>
  </section>;
}
