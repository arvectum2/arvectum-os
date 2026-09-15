import { useMemo, useState } from "react";
import { fetchCompanyAssetContent } from "./f11Api";
import type { CompanyAssetLibraryItem, CompanyAssetLibraryProjection } from "./f11Types";
import { useWorkspaceLanguage } from "./i18n";
import "./CompanyAssetDiscovery.css";

const DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
type ProjectOption = { id: string; label: string };
type VersionFilter = "all" | "current" | "superseded";
type LifecycleFilter = "all" | "accepted" | "archive";

const ROLE_LABELS: Record<string, { ru: string; en: string }> = {
  "document-template": { ru: "Шаблон документа", en: "Document template" },
  brandbook: { ru: "Брендбук", en: "Brandbook" },
  logo: { ru: "Логотип", en: "Logo" },
  source: { ru: "Исходный материал", en: "Source material" },
};

function admittedItems(data: CompanyAssetLibraryProjection): CompanyAssetLibraryItem[] {
  return [...data.views.accepted, ...data.views.archive]
    .filter((item) => item.canonical !== null)
    .sort((left, right) => {
      const currentDelta = Number(Boolean(right.canonical?.current)) - Number(Boolean(left.canonical?.current));
      return currentDelta || left.title.localeCompare(right.title, "ru");
    });
}

function projectLabel(projectId: string, projects: ProjectOption[], companyWide: string): string {
  if (projectId === "COMPANY") return companyWide;
  return projects.find((project) => project.id === projectId)?.label ?? projectId;
}

function roleLabel(role: string, language: "ru" | "en"): string {
  return ROLE_LABELS[role]?.[language] ?? role;
}

export function CompanyAssetDiscovery({ data, projects, onReuse }: {
  data: CompanyAssetLibraryProjection;
  projects: ProjectOption[];
  onReuse: (item: CompanyAssetLibraryItem) => void;
}) {
  const { language, text } = useWorkspaceLanguage();
  const [query, setQuery] = useState("");
  const [role, setRole] = useState("all");
  const [project, setProject] = useState("all");
  const [version, setVersion] = useState<VersionFilter>("all");
  const [lifecycle, setLifecycle] = useState<LifecycleFilter>("all");
  const [retrieving, setRetrieving] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const companyWide = text("Компания в целом", "Company-wide");
  const all = useMemo(() => admittedItems(data), [data]);
  const roles = useMemo(() => [...new Set(all.map((item) => item.semantic_role))].sort(), [all]);
  const projectIds = useMemo(() => [...new Set(all.map((item) => item.project_id))].sort(), [all]);
  const normalizedQuery = query.trim().toLocaleLowerCase(language === "ru" ? "ru-RU" : "en-US");
  const filtered = useMemo(() => all.filter((item) => {
    const canonical = item.canonical;
    if (!canonical) return false;
    if (role !== "all" && item.semantic_role !== role) return false;
    if (project !== "all" && item.project_id !== project) return false;
    if (version === "current" && !canonical.current) return false;
    if (version === "superseded" && canonical.current) return false;
    if (lifecycle !== "all" && item.lifecycle_view !== lifecycle) return false;
    if (!normalizedQuery) return true;
    return [item.title, roleLabel(item.semantic_role, language), projectLabel(item.project_id, projects, companyWide), item.purpose]
      .join(" ").toLocaleLowerCase(language === "ru" ? "ru-RU" : "en-US").includes(normalizedQuery);
  }), [all, companyWide, language, lifecycle, normalizedQuery, project, projects, role, version]);

  const retrieve = async (item: CompanyAssetLibraryItem, download: boolean) => {
    setMessage(null);
    setRetrieving(item.version_id);
    const previewWindow = download ? null : window.open("", "_blank", "noopener,noreferrer");
    try {
      const result = await fetchCompanyAssetContent(item.material_id, item.version_id, download);
      const href = URL.createObjectURL(result.blob);
      if (download) {
        const anchor = document.createElement("a");
        anchor.href = href;
        anchor.download = result.filename;
        anchor.click();
      } else if (previewWindow) {
        previewWindow.location.href = href;
      } else {
        const anchor = document.createElement("a");
        anchor.href = href;
        anchor.target = "_blank";
        anchor.rel = "noopener noreferrer";
        anchor.click();
      }
      window.setTimeout(() => URL.revokeObjectURL(href), 60_000);
    } catch (error) {
      previewWindow?.close();
      setMessage(error instanceof Error ? error.message : "COMPANY_ASSET_CONTENT_UNAVAILABLE");
    } finally {
      setRetrieving(null);
    }
  };

  return <section className="asset-discovery" aria-labelledby="asset-discovery-title">
    <div className="asset-discovery-heading">
      <div><p className="eyebrow">P10.09-A</p><h2 id="asset-discovery-title">{text("Библиотека принятых материалов", "Admitted asset library")}</h2><p>{text("Ищите и открывайте материалы по обычным названиям, типам и проектам. Технические идентификаторы нужны только для проверки точной версии.", "Find and open assets by ordinary names, types, and projects. Technical identifiers are only needed when verifying an exact version.")}</p></div>
      <strong className="asset-discovery-count">{filtered.length} / {all.length}</strong>
    </div>
    <div className="asset-discovery-filters" role="search" aria-label={text("Поиск принятых материалов", "Search admitted assets")}>
      <label className="asset-discovery-query">{text("Название или назначение", "Name or purpose")}<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={text("Например: шаблон договора", "For example: contract template")} /></label>
      <label>{text("Тип", "Type")}<select value={role} onChange={(event) => setRole(event.target.value)}><option value="all">{text("Все типы", "All types")}</option>{roles.map((value) => <option key={value} value={value}>{roleLabel(value, language)}</option>)}</select></label>
      <label>{text("Проект", "Project")}<select value={project} onChange={(event) => setProject(event.target.value)}><option value="all">{text("Все проекты", "All projects")}</option>{projectIds.map((value) => <option key={value} value={value}>{projectLabel(value, projects, companyWide)}</option>)}</select></label>
      <label>{text("Версия", "Version")}<select value={version} onChange={(event) => setVersion(event.target.value as VersionFilter)}><option value="all">{text("Текущие и заменённые", "Current and superseded")}</option><option value="current">{text("Только текущие", "Current only")}</option><option value="superseded">{text("Только заменённые", "Superseded only")}</option></select></label>
      <label>{text("Состояние", "Lifecycle")}<select value={lifecycle} onChange={(event) => setLifecycle(event.target.value as LifecycleFilter)}><option value="all">{text("Принято и архив", "Accepted and archive")}</option><option value="accepted">{text("Принято", "Accepted")}</option><option value="archive">{text("Архив", "Archive")}</option></select></label>
    </div>
    {message ? <p className="company-message" role="status">{message}</p> : null}
    {filtered.length ? <div className="asset-discovery-results">{filtered.map((item) => {
      const canonical = item.canonical!;
      const busy = retrieving === item.version_id;
      return <article className="asset-discovery-card" key={item.version_id}>
        <header><div><p className="eyebrow">{roleLabel(item.semantic_role, language)}</p><h3>{item.title}</h3><p>{projectLabel(item.project_id, projects, companyWide)}</p></div><div className="asset-discovery-badges"><span>{canonical.current ? text("Текущая версия", "Current version") : text("Заменена", "Superseded")}</span><span>{item.lifecycle_view === "accepted" ? text("Принято", "Accepted") : text("Архив", "Archive")}</span></div></header>
        <dl className="asset-discovery-facts"><div><dt>{text("Классификация", "Classification")}</dt><dd>{item.classification}</dd></div><div><dt>{text("Назначение", "Purpose")}</dt><dd>{item.purpose}</dd></div><div><dt>{text("Права", "Rights")}</dt><dd>{item.rights}</dd></div></dl>
        <div className="asset-discovery-actions"><button type="button" disabled={busy} onClick={() => void retrieve(item, false)}>{busy ? text("Открываем…", "Opening…") : text("Открыть", "Open")}</button><button type="button" className="quiet-button" disabled={busy} onClick={() => void retrieve(item, true)}>{text("Скачать", "Download")}</button>{item.media_type === DOCX && item.semantic_role === "document-template" && canonical.current ? <button type="button" className="quiet-button" onClick={() => onReuse(item)}>{text("Использовать как шаблон", "Use as template")}</button> : null}</div>
        <details className="project-technical-details"><summary>{text("Точная версия и provenance", "Exact version and provenance")}</summary><dl className="company-facts"><div><dt>Material</dt><dd><code>{item.material_id}</code></dd></div><div><dt>Staged version</dt><dd><code>{item.version_id}</code></dd></div><div><dt>SHA-256</dt><dd><code>{item.content_sha256}</code></dd></div><div><dt>Document version</dt><dd><code>{canonical.document_version}</code></dd></div><div><dt>Asset designation</dt><dd><code>{canonical.designation_version}</code></dd></div><div><dt>Admission Event</dt><dd><code>{canonical.event_version}</code></dd></div><div><dt>Provenance</dt><dd>{canonical.provenance_refs.map((ref) => <div key={ref}><code>{ref}</code></div>)}</dd></div></dl></details>
      </article>;
    })}</div> : <p className="asset-empty-state">{all.length ? text("По выбранным фильтрам ничего не найдено.", "No admitted assets match these filters.") : text("Принятых материалов пока нет. Сначала материал должен пройти governed admission.", "There are no admitted assets yet. An asset must pass governed admission first.")}</p>}
  </section>;
}
