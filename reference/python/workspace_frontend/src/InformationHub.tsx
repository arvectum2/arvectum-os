import { useEffect, useRef, useState } from "react";
import { loadCompanyPortfolio } from "./f11Api";
import type { CompanyPortfolioProjection, CompanyProjectCard } from "./f11Types";
import { useWorkspaceLanguage } from "./i18n";
import "./CompanyWorkspace.css";
import "./InformationHub.css";
import { RoadmapInbox } from "./RoadmapInbox";

type State =
  | { kind: "loading" }
  | { kind: "ready"; data: CompanyPortfolioProjection; refreshing: boolean }
  | { kind: "error" };

function exactSource(project: CompanyProjectCard) {
  const source = project.source;
  if (!source || !["current-source-backed", "cached-source-backed", "stale-cache"].includes(project.state)
    || project.repository !== source.repository || project.roadmap_path !== source.path
    || !/^arvectum2\/[A-Za-z0-9_.-]+$/.test(source.repository)
    || !/^[A-Za-z0-9_./ -]+\.md$/.test(source.path)
    || source.path.split("/").some((part) => !part || part === "." || part === "..")
    || !/^[a-f0-9]{40}$/.test(source.commit_sha)
    || !/^[a-f0-9]{64}$/.test(source.content_sha256)
    || !Number.isFinite(Date.parse(source.fetched_at))) return null;
  return source;
}

export function InformationHub({csrfToken=""}:{csrfToken?:string}={}) {
  const { language, text } = useWorkspaceLanguage();
  const [state, setState] = useState<State>({ kind: "loading" });
  const [filter, setFilter] = useState<"all" | "attention">("all");
  const generation = useRef(0);

  const refresh = (force = false) => {
    const request = ++generation.current;
    // Never retain prior content after a failed access/refresh response.
    setState((current) => current.kind === "ready" && force
      ? { ...current, refreshing: true } : { kind: "loading" });
    void loadCompanyPortfolio(force).then((data) => {
      if (request === generation.current) setState({ kind: "ready", data, refreshing: false });
    }).catch(() => {
      if (request === generation.current) setState({ kind: "error" });
    });
  };
  useEffect(() => { refresh(); return () => { generation.current += 1; }; }, []);

  const format = (value: string) => new Intl.DateTimeFormat(language === "ru" ? "ru-RU" : "en-GB",
    { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));

  const rows = state.kind === "ready" ? state.data.projects.map((project) => ({ project, source: exactSource(project) })) : [];
  const attention = rows.filter(({ project, source }) => !source || project.state === "stale-cache");
  const visible = filter === "attention" ? attention : rows;
  const healthy = rows.length - attention.length;
  const labels = {
    "current-source-backed": text("Получено сейчас", "Fetched now"),
    "cached-source-backed": text("Недавняя сводка", "Recent snapshot"),
    "stale-cache": text("Устаревшая сводка", "Stale snapshot"),
    "reconciliation-required": text("Источник не согласован", "Source not reconciled"),
    "unavailable": text("Источник недоступен", "Source unavailable"),
  };

  return <section className="company-page hub-page" aria-labelledby="hub-title">
    <header className="company-page-head">
      <div>
        <p className="eyebrow">Workspace First · Information Hub</p>
        <h1 id="hub-title">{text("Входящая информация", "Information Hub")}</h1>
        <p>{text("Последние доступные наблюдения из зарегистрированных дорожных карт GitHub. Это сводка источников, а не журнал новых событий или задач.", "Latest available observations from registered GitHub roadmaps. This is a source snapshot, not an event feed or task list.")}</p>
      </div>
      <button type="button" disabled={state.kind === "loading" || (state.kind === "ready" && state.refreshing)}
        onClick={() => refresh(true)}>{state.kind === "ready" && state.refreshing ? text("Обновляем…", "Refreshing…") : text("Обновить источники", "Refresh sources")}</button>
    </header>
    <RoadmapInbox csrfToken={csrfToken}/>
    {state.kind === "loading" && <p role="status">{text("Получаем разрешённые источники…", "Reading authorized sources…")}</p>}
    {state.kind === "error" && <p role="alert">{text("Сводка недоступна. Предыдущие сведения скрыты. Повторите запрос.", "Snapshot unavailable. Previous content hidden. Retry the request.")}</p>}
    {state.kind === "ready" && <>
      <div className="hub-summary" aria-label={text("Состояние источников", "Source status")}>
        <div><strong>{rows.length}</strong><span>{text("Зарегистрировано", "Registered")}</span></div>
        <div><strong>{healthy}</strong><span>{text("Доступные сводки", "Available snapshots")}</span></div>
        <div><strong>{attention.length}</strong><span>{text("Нужна проверка источника", "Source needs review")}</span></div>
      </div>
      <div className="hub-filters" role="group" aria-label={text("Фильтр источников", "Source filter")}>
        <button type="button" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>{text("Все источники", "All sources")}</button>
        <button type="button" aria-pressed={filter === "attention"} onClick={() => setFilter("attention")}>{text("Устаревшие и недоступные", "Stale and unavailable")}</button>
      </div>
      {!visible.length && <p role="status">{text("Нет источников в этом представлении.", "No sources in this view.")}</p>}
      <div className="hub-items">
        {visible.map(({ project, source }) => <article key={project.id} className="company-card hub-item">
          <header className="company-card-head">
            <div><p className="eyebrow">{project.id} · GitHub</p><h2>{project.label}</h2></div>
            <span className={`company-state company-state-${source ? project.state : "unavailable"}`}>
              {source ? labels[project.state] : project.source ? text("Не проверена точная версия", "Exact revision unverified") : project.state === "reconciliation-required" ? labels["reconciliation-required"] : labels.unavailable}
            </span>
          </header>
          {source ? <>
            <p>{project.roadmap.status ?? text("Статус не указан в источнике", "No status given by source")}</p>
            {project.state === "stale-cache" && <p className="hub-warning">{text("Последняя известная версия; актуальность не подтверждена.", "Last known revision; currency not confirmed.")}</p>}
            <p className="hub-meta">{text("Получено", "Fetched")}: {format(source.fetched_at)}</p>
            <div className="hub-links">
              <a href={`https://github.com/${source.repository}/blob/${source.commit_sha}/${source.path.split("/").map(encodeURIComponent).join("/")}`} target="_blank" rel="noopener noreferrer">{text("Точный источник", "Exact source")}</a>
              <a href="/projects">{text("Открыть проекты", "Open projects")}</a>
            </div>
            <details><summary>{text("Версия и происхождение", "Revision and provenance")}</summary>
              <dl className="company-facts"><div><dt>Commit</dt><dd><code>{source.commit_sha}</code></dd></div>
              <div><dt>SHA-256</dt><dd><code>{source.content_sha256}</code></dd></div><div><dt>{text("Путь", "Path")}</dt><dd><code>{source.path}</code></dd></div></dl>
            </details>
          </> : <p>{text("Подтверждённые данные источника отсутствуют.", "No verified source data available.")}</p>}
        </article>)}
      </div>
    </>}
    <p className="hub-boundary">{text("Сводка источников только для чтения. Очередь изменений требует отдельной активации; почта не подключена.", "Source snapshot is read-only. Change inbox requires independent activation; email is not connected.")}</p>
  </section>;
}
