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
const DOCUMENT_GENERATION_REUSE = "company-internal-document-generation";
const LEGACY_DOCUMENT_GENERATION_REUSE = "company-document-generation";
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


function materialRoleLabel(value: string, text: (ru: string, en: string) => string): string {
  const option = MATERIAL_ROLE_OPTIONS.find((candidate) => candidate.value === value);
  return option ? text(option.ru, option.en) : value;
}

function classificationLabel(value: string, text: (ru: string, en: string) => string): string {
  return value === "internal" ? text("Внутренний", "Internal") : value;
}

function rightsLabel(value: string, text: (ru: string, en: string) => string): string {
  return value === "company-internal-use" ? text("Для использования внутри компании", "Company internal use") : value;
}

function retentionLabel(value: string, text: (ru: string, en: string) => string): string {
  return value === "until-replaced-or-explicit-deletion"
    ? text("До замены или явного удаления", "Until replaced or explicitly deleted")
    : value === "until-replaced"
      ? text("До замены новой версией", "Until replaced")
      : value;
}

function deletionLabel(value: string, text: (ru: string, en: string) => string): string {
  const known: Record<string, [string, string]> = {
    "governed-retention": ["По действующим правилам хранения", "Under the governed retention rules"],
    "existing-retention": ["По действующему сроку хранения", "Under the existing retention rule"],
    "delete-through-governed-retention": ["Только после проверки правил хранения", "Only after retention checks"],
    "delete-only-through-governed-retention-process": ["Только после проверки правил хранения", "Only after retention checks"],
  };
  const label = known[value];
  return label ? text(label[0], label[1]) : value;
}

function permittedReuseLabels(values: string[], text: (ru: string, en: string) => string): string[] {
  return values.map((value) => {
    if (value === DOCUMENT_GENERATION_REUSE || value === LEGACY_DOCUMENT_GENERATION_REUSE) {
      return text("Создание документов внутри компании", "Internal document generation");
    }
    if (value === AI_GROUNDING_REUSE) return text("Использование как источника для Arvectum AI", "Use as a source for Arvectum AI");
    return value;
  });
}

type MaterialRoleChoice = typeof MATERIAL_ROLE_OPTIONS[number]["value"] | "";
type ViewKey = keyof CompanyAssetLibraryProjection["views"];
type State =
  | { kind: "loading" }
  | { kind: "ready"; data: CompanyAssetLibraryProjection }
  | { kind: "error"; code: string };

const VIEW_OPTIONS: Array<{ key: ViewKey; ru: string; en: string }> = [
  { key: "drafts", ru: "Черновики", en: "Drafts" },
  { key: "review", ru: "Проверка", en: "Review" },
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
  return text("будет использован как ссылка на точную версию", "will be used as an exact-version reference");
}

function prettyDate(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("ru-RU");
}

function MaterialCard({
  item,
  busy,
  admissionAvailable,
  onReviewAndAdmit,
  onReject,
  onAdmit,
  onNewVersion,
}: {
  item: CompanyAssetLibraryItem;
  busy: boolean;
  admissionAvailable: boolean;
  onReviewAndAdmit: (item: CompanyAssetLibraryItem, deletionRule: string, permittedReuse: string[]) => Promise<void>;
  onReject: (item: CompanyAssetLibraryItem, reason: string) => Promise<void>;
  onAdmit: (item: CompanyAssetLibraryItem) => Promise<void>;
  onNewVersion: (item: CompanyAssetLibraryItem) => void;
}) {
  const { text } = useWorkspaceLanguage();
  const initialReuse = item.review.policy?.permitted_reuse ?? [];
  const [deletionRule, setDeletionRule] = useState(item.review.policy?.deletion_rule ?? "");
  const [reuse, setReuse] = useState<string[]>(initialReuse);
  const [rejectReason, setRejectReason] = useState("");
  const rejected = item.review.state === "Rejected";
  const canonical = item.canonical;
  const badge = canonical
    ? canonical.current ? text("Принят", "Accepted") : text("Заменён", "Superseded")
    : item.review.state === "InReview"
      ? text("Ждёт подтверждения", "Awaiting confirmation")
      : rejected ? text("Отклонён", "Rejected") : text("Черновик", "Draft");

  const generationReuseEnabled = reuse.some((value) => value === DOCUMENT_GENERATION_REUSE || value === LEGACY_DOCUMENT_GENERATION_REUSE);
  const aiGroundingEnabled = reuse.includes(AI_GROUNDING_REUSE);
  const setGenerationReuse = (enabled: boolean) => {
    const values = reuse.filter((value) => value !== DOCUMENT_GENERATION_REUSE && value !== LEGACY_DOCUMENT_GENERATION_REUSE);
    if (enabled) values.push(DOCUMENT_GENERATION_REUSE);
    setReuse(values);
  };
  const setAiGrounding = (enabled: boolean) => {
    const values = reuse.filter((value) => value !== AI_GROUNDING_REUSE);
    if (enabled) values.push(AI_GROUNDING_REUSE);
    setReuse(values);
  };

  const submitReview = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onReviewAndAdmit(item, deletionRule, Array.from(new Set(reuse)));
  };

  const submitReject = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onReject(item, rejectReason);
    setRejectReason("");
  };

  return <article className="company-card asset-library-card">
    <header className="company-card-head">
      <div>
        <p className="eyebrow">{materialRoleLabel(item.semantic_role, text)}</p>
        <h2>{item.title}</h2>
        <p className="project-source-updated">{text("Получено", "Received")}: {prettyDate(item.received_at)}</p>
      </div>
      <span className={`company-state ${canonical ? "company-state-canonical" : "company-state-staged"}`}>{badge}</span>
    </header>

    <dl className="company-facts asset-human-facts">
      <div><dt>{text("Проект", "Project")}</dt><dd>{item.project_id === "COMPANY" ? text("Компания в целом", "Company-wide") : item.project_id}</dd></div>
      <div><dt>{text("Тип", "Type")}</dt><dd>{materialRoleLabel(item.semantic_role, text)}</dd></div>
      <div><dt>{text("Доступ", "Access")}</dt><dd>{rightsLabel(item.rights, text)}</dd></div>
      <div><dt>{text("Назначение", "Purpose")}</dt><dd>{item.purpose}</dd></div>
      <div><dt>{text("Хранение", "Retention")}</dt><dd>{retentionLabel(item.retention_rule, text)}</dd></div>
      {item.review.policy ? <>
        <div><dt>{text("Удаление", "Deletion")}</dt><dd>{deletionLabel(item.review.policy.deletion_rule, text)}</dd></div>
        <div><dt>{text("Можно использовать для", "Permitted use")}</dt><dd>{permittedReuseLabels(item.review.policy.permitted_reuse, text).join(", ") || text("не указано", "not specified")}</dd></div>
      </> : null}
    </dl>

    {item.review.state === "InReview" ? <section className="asset-review-proof" aria-label={text("Версия для подтверждения", "Version for confirmation")}>
      <h3>{text("Готово к принятию", "Ready to accept")}</h3>
      <p>{text("Проверьте, что это нужный файл и условия использования указаны верно. Перед принятием сервер ещё раз проверит действующие права и ограничения.", "Verify the file and its use conditions. The server will re-check current access and restrictions before acceptance.")}</p>
      <dl className="company-facts">
        <div><dt>{text("Файл", "File")}</dt><dd>{item.title}</dd></div>
        <div><dt>{text("Тип", "Type")}</dt><dd>{materialRoleLabel(item.semantic_role, text)}</dd></div>
        <div><dt>{text("Доступ", "Access")}</dt><dd>{rightsLabel(item.rights, text)}</dd></div>
        <div><dt>{text("Хранение", "Retention")}</dt><dd>{retentionLabel(item.retention_rule, text)}</dd></div>
      </dl>
    </section> : null}

    {!canonical && item.review.state !== "InReview" ? <form className="asset-inline-form" onSubmit={(event) => void submitReview(event)}>
      <h3>{rejected ? text("Исправить условия", "Update conditions") : text("Подготовить к использованию", "Prepare for use")}</h3>
      <p>{text("Это одноразовая настройка для новой или изменённой версии. После принятия шаблон можно будет выбирать напрямую в библиотеке.", "This is a one-time setup for a new or changed version. Once accepted, the template can be selected directly from the library.")}</p>
      {rejected && item.review.reason ? <p className="boundary-note">{text("Причина отклонения", "Rejection reason")}: {item.review.reason}</p> : null}
      <label>{text("Когда материал можно удалить", "When the material may be deleted")}<input aria-label={text("Когда материал можно удалить", "When the material may be deleted")} value={deletionRule} onChange={(event) => setDeletionRule(event.target.value)} required maxLength={240} placeholder={text("Например: после замены новой версией", "For example: after it is replaced by a new version")} /><small>{text("Это условие задаётся один раз для новой версии. При обычном использовании принятого шаблона его повторно вводить не нужно.", "Set this once for a new version. You do not re-enter it when using an accepted template.")}</small></label>
      <label className="asset-generation-option">
        <input type="checkbox" aria-label={text("Разрешить использовать материал при создании документов", "Allow use in document generation")} checked={generationReuseEnabled} onChange={(event) => setGenerationReuse(event.target.checked)} />
        <span><strong>{text("Использовать при создании документов", "Use in document generation")}</strong><small>{text("Для шаблонов, логотипов и исходных материалов внутри компании.", "For templates, logos and source materials inside the company.")}</small></span>
      </label>
      <label className="asset-generation-option">
        <input type="checkbox" aria-label={text("Разрешить Arvectum AI использовать эту версию как источник", "Allow Arvectum AI to use this version as a source")} checked={aiGroundingEnabled} onChange={(event) => setAiGrounding(event.target.checked)} />
        <span><strong>{text("Разрешить Arvectum AI использовать эту версию как источник", "Allow Arvectum AI to use this version as a source")}</strong><small>{text("Отдельное разрешение только для этой версии. Само разрешение не даёт ИИ права менять документы или принимать решения.", "A separate permission for this version only. It does not let AI change documents or make decisions.")}</small></span>
      </label>
      <button type="submit" disabled={busy || !admissionAvailable}>{text("Принять материал", "Accept material")}</button>
      {!admissionAvailable ? <p className="boundary-note">{text("Принятие сейчас временно недоступно. Черновик сохранён; вернитесь к нему, когда серверная проверка восстановится.", "Acceptance is temporarily unavailable. The draft is saved; return when the server-side check is available again.")}</p> : null}
      <details className="project-technical-details">
        <summary>{text("Служебные разрешения", "Service permissions")}</summary>
        <p>{permittedReuseLabels(reuse, text).join(", ") || text("Дополнительные разрешения не выбраны.", "No additional permissions selected.")}</p>
      </details>
    </form> : null}

    {item.review.state === "InReview" && !canonical ? <div className="asset-review-actions">
      <button type="button" disabled={busy || !admissionAvailable} onClick={() => void onAdmit(item)}>{text("Принять материал", "Accept material")}</button>
      {!admissionAvailable ? <p className="boundary-note">{text("Сейчас материал нельзя безопасно принять: серверная проверка недоступна. Попробуйте позже.", "The material cannot be safely accepted now because the server-side check is unavailable. Try again later.")}</p> : null}
      <form className="asset-reject-form" onSubmit={(event) => void submitReject(event)}>
        <label>{text("Почему не принимаем", "Why reject it")}<input value={rejectReason} onChange={(event) => setRejectReason(event.target.value)} required maxLength={600} /></label>
        <button type="submit" disabled={busy}>{text("Отклонить", "Reject")}</button>
      </form>
    </div> : null}

    {canonical?.current ? <div className="asset-card-actions"><button type="button" disabled={busy} onClick={() => onNewVersion(item)}>{text("Добавить новую версию", "Add new version")}</button></div> : null}

    <details className="project-technical-details">
      <summary>{text("Технические сведения", "Technical details")}</summary>
      <dl className="company-facts">
        <div><dt>{text("Внутренний тип", "Internal role")}</dt><dd><code>{item.semantic_role}</code></dd></div>
        <div><dt>{text("Классификация", "Classification")}</dt><dd><code>{item.classification}</code></dd></div>
        <div><dt>{text("Права", "Rights")}</dt><dd><code>{item.rights}</code></dd></div>
        <div><dt>{text("Правило хранения", "Retention rule")}</dt><dd><code>{item.retention_rule}</code></dd></div>
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
      setMessage(text(`Черновик ${staged.filename} сохранён. Теперь проверьте условия использования и примите материал.`, `${staged.filename} was saved as a draft. Review its use conditions and accept it when ready.`));
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
        `Документ создан по выбранному шаблону и ${assetInputs.length} дополнительным материалам.`,
        `Document created from the selected template and ${assetInputs.length} additional materials.`,
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
  if (state.kind === "error") return <section className="company-page" role="alert"><h1>{text("Материалы компании недоступны", "Company materials unavailable")}</h1><p>{text("Не удалось безопасно загрузить библиотеку. Повторите попытку; технический код доступен ниже.", "The library could not be loaded safely. Try again; the technical code is available below.")}</p><details className="project-technical-details"><summary>{text("Технические сведения", "Technical details")}</summary><code>{state.code}</code></details><div><button type="button" onClick={() => void refresh()}>{text("Повторить", "Retry")}</button></div></section>;

  const currentItems = state.data.views[activeView];
  const admissionAvailable = state.data.actions.governed_admission_available;

  return <section className="company-page" aria-labelledby="company-materials-title">
    <header className="company-page-head asset-library-head">

      <h1 id="company-materials-title">{text("Материалы компании", "Company materials")}</h1>
      <p>{text("Здесь можно найти принятые материалы и сразу использовать текущий шаблон. Для нового или изменённого файла подтверждение выполняется один раз перед первым использованием.", "Find accepted materials here and use the current template directly. A new or changed file is confirmed once before first use.")}</p>
      <details className="company-boundary-details"><summary>{text("Почему новый материал нужно подтвердить", "Why a new material needs confirmation")}</summary><p>{text("До принятия файл считается подготовительным: можно проверить его назначение, срок хранения и разрешённые способы использования. При принятии сервер повторно проверяет текущие права. Это не требуется каждый раз, когда вы используете уже принятый шаблон.", "Before acceptance the file is preparatory: its purpose, retention and allowed uses can be checked. The server re-checks current access at acceptance. This is not repeated every time an accepted template is used.")}</p></details>
      <details className="company-boundary-details"><summary>{text("Служебные действия", "Service actions")}</summary><button type="button" disabled={busy} onClick={() => void downloadExport()}>{text("Экспортировать доступную историю", "Export accessible history")}</button></details>
    </header>

    <CompanyAssetDiscovery
      data={state.data}
      projects={projectOptions}
      onReuse={(item) => {
        setReuseSourceVersion(`${item.material_id}::${item.version_id}`);
        setMessage(text(`Шаблон «${item.title}» выбран. Заполните документ ниже.`, `Template “${item.title}” selected. Fill in the document below.`));
        window.setTimeout(() => document.getElementById("company-docx-generator")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
      }}
    />

    <section aria-labelledby="company-asset-governance-title">
      <div className="company-page-head"><h2 id="company-asset-governance-title">{text("Новые и изменённые материалы", "New and changed materials")}</h2><p>{text("Этот раздел нужен только для одноразовой подготовки нового файла или новой версии. Уже принятые материалы используйте через библиотеку выше.", "Use this section only for one-time setup of a new file or version. Use accepted materials from the library above.")}</p></div>
      <nav className="asset-library-tabs" aria-label={text("Состояния материалов", "Material lifecycle views")}>
        {VIEW_OPTIONS.map((view) => <button key={view.key} type="button" className={activeView === view.key ? "active" : ""} onClick={() => setActiveView(view.key)}>{text(view.ru, view.en)} <span>{state.data.views[view.key].length}</span></button>)}
      </nav>

      <section className="asset-library-view" aria-live="polite">
        {currentItems.length ? <div className="company-grid">{currentItems.map((item) => <MaterialCard
          key={item.version_id}
          item={item}
          busy={busy}
          admissionAvailable={admissionAvailable}
          onReviewAndAdmit={async (target, deletionRule, permittedReuse) => run(async () => {
            await submitCompanyAssetReview(target.material_id, target.version_id, { deletion_rule: deletionRule, permitted_reuse: permittedReuse }, csrfToken);
            setActiveView("review");
            try {
              await admitCompanyAssetVersion(target.material_id, target.version_id, csrfToken);
              setActiveView("accepted");
              setMessage(text("Материал принят и теперь доступен в рабочей библиотеке.", "Material accepted and now available in the working library."));
            } catch {
              setMessage(text("Условия сохранены, но принять материал сейчас не удалось. Он остался в разделе «Проверка» — можно повторить принятие позже.", "Conditions were saved, but acceptance could not complete. The material remains in Review and can be accepted later."));
            }
          })}
          onReject={async (target, reason) => run(async () => {
            await rejectCompanyAssetVersion(target.material_id, target.version_id, reason, csrfToken);
            setActiveView("archive");
            setMessage(text("Версия отклонена. Принятая библиотека не изменилась.", "Version rejected. The accepted library was not changed."));
          })}
          onAdmit={async (target) => run(async () => {
            await admitCompanyAssetVersion(target.material_id, target.version_id, csrfToken);
            setActiveView("accepted");
            setMessage(text("Материал принят и теперь доступен в рабочей библиотеке.", "Material accepted and now available in the working library."));
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
        <label>{text("Классификация", "Classification")}<select name="classification" defaultValue="internal"><option value="internal">{text("Внутренний", "Internal")}</option></select></label>
        <label>{text("Назначение", "Purpose")}<input name="purpose" required maxLength={240} /></label>
        <label>{text("Использование", "Use") }<select name="rights" defaultValue="company-internal-use"><option value="company-internal-use">{text("Внутри компании", "Inside the company")}</option></select></label>
        <label>{text("Хранение", "Retention")}<select name="retention_rule" defaultValue="until-replaced-or-explicit-deletion"><option value="until-replaced-or-explicit-deletion">{text("До замены или явного удаления", "Until replaced or explicitly deleted")}</option></select></label>
        <button type="submit" disabled={busy}>{busy ? text("Сохраняем…", "Saving…") : text("Сохранить как черновик", "Save as draft")}</button>
      </form>

      <form id="company-docx-generator" className="company-form" onSubmit={(event) => void submitGenerate(event)}>
        <h2>{text("Создать документ по шаблону", "Create a document from a template")}</h2>
        <p>{text("Выберите принятый шаблон. При необходимости добавьте логотип или исходные материалы. Созданный файл можно скачать сразу; в библиотеку он не добавляется автоматически.", "Choose an accepted template and optionally add a logo or source materials. The generated file can be downloaded immediately and is not automatically added to the library.")}</p>
        <label>{text("Шаблон", "Template")}<select name="source_version" required value={reuseSourceVersion} onChange={(event) => setReuseSourceVersion(event.target.value)}><option value="" disabled>{text("Выберите шаблон", "Choose template")}</option>{docxVersions.map((item) => <option key={item.version_id} value={`${item.material_id}::${item.version_id}`}>{item.title} · {prettyDate(item.received_at)}</option>)}</select></label>
        <section className="asset-generation-inputs" aria-labelledby="asset-generation-inputs-title">
          <h3 id="asset-generation-inputs-title">{text("Дополнительные материалы", "Additional assets")}</h3>
          <p>{text("Показываются только принятые текущие версии. Технические номера выбирать не нужно.", "Only accepted current versions are shown. Technical identifiers are not needed for selection.")}</p>
          {brandInputs.length ? <fieldset><legend>{text("Бренд", "Brand")}</legend>{brandInputs.map((item) => <label className="asset-generation-option" key={item.version_id}><input type="checkbox" name="asset_input" value={`brand::${item.material_id}::${item.version_id}`} /><span><strong>{item.title}</strong><small>{assetApplicationLabel(item, text)}</small></span></label>)}</fieldset> : null}
          {sourceInputs.length ? <fieldset><legend>{text("Исходные материалы", "Source materials")}</legend>{sourceInputs.map((item) => <label className="asset-generation-option" key={item.version_id}><input type="checkbox" name="asset_input" value={`source::${item.material_id}::${item.version_id}`} /><span><strong>{item.title}</strong><small>{assetApplicationLabel(item, text)}</small></span></label>)}</fieldset> : null}
          {referenceInputs.length ? <fieldset><legend>{text("Другие материалы", "Other materials")}</legend>{referenceInputs.map((item) => <label className="asset-generation-option" key={item.version_id}><input type="checkbox" name="asset_input" value={`reference::${item.material_id}::${item.version_id}`} /><span><strong>{item.title}</strong><small>{assetApplicationLabel(item, text)}</small></span></label>)}</fieldset> : null}
        </section>
        <label>{text("Заголовок", "Title")}<input name="title" required maxLength={320} /></label>
        <label>{text("Текст", "Body")}<textarea name="body" required maxLength={6000} rows={9} /></label>
        <label>{text("Дата", "Date")}<input name="date" required maxLength={80} defaultValue={new Date().toLocaleDateString("ru-RU")} /></label>
        <button type="submit" disabled={busy || docxVersions.length === 0}>{text("Создать документ", "Create document")}</button>
        {docxVersions.length === 0 ? <p className="boundary-note">{text("Принятых DOCX-шаблонов пока нет. Новый шаблон нужно один раз проверить и принять в разделе выше.", "There are no accepted DOCX templates yet. A new template must be reviewed and accepted once in the section above.")}</p> : null}
        {generated ? <div className="company-output"><strong>{text("Документ готов", "Document ready")}</strong><p>{text("Шаблон", "Template")}: {docxVersions.find((item) => item.version_id === generated.output.source_version_id)?.title ?? text("точная принятая версия", "exact admitted version")}</p>{generated.output.input_assets?.length ? <div><p><strong>{text("Использованные материалы", "Used assets")}</strong></p><ul>{generated.output.input_assets.map((item) => <li key={`${item.material_id}-${item.version_id}`}>{item.title} · {item.application === "embedded-image" ? text("встроен", "embedded") : item.application === "text-included" ? text("текст включён", "text included") : text("ссылка на точную версию", "exact-version reference")}</li>)}</ul></div> : null}<button type="button" disabled={busy} onClick={() => void downloadGenerated(generated)}>{text("Скачать DOCX", "Download DOCX")}</button><details><summary>{text("Технические сведения", "Technical details")}</summary><code>{generated.output.output_id}</code><br /><code>{generated.output.source_version_id}</code>{generated.output.generation_input_digest ? <><br /><code>{generated.output.generation_input_digest}</code></> : null}</details></div> : null}
      </form>
    </div>
  </section>;
}
