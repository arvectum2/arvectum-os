import { useEffect, useState } from "react";
import { loadCompanyPortfolio } from "./f11Api";
import type { CompanyPortfolioProjection, CompanyProjectCard } from "./f11Types";
import { useWorkspaceLanguage } from "./i18n";
import "./CompanyWorkspace.css";

type State =
  | { kind: "loading" }
  | { kind: "ready"; data: CompanyPortfolioProjection; refreshing: boolean }
  | { kind: "error"; code: string };

const TARGET_LABELS: Record<string, { ru: string; en: string }> = {
  web: { ru: "Веб / GitHub / ChatGPT", en: "Web / GitHub / ChatGPT" },
  "mac-mini": { ru: "Mac mini", en: "Mac mini" },
  macbook: { ru: "MacBook", en: "MacBook" },
  "windows-laptop": { ru: "Ноутбук Windows", en: "Windows laptop" },
  "windows-test-laptop": { ru: "Стендовый ноутбук Windows", en: "Windows test laptop" },
  "linux-test-laptop": { ru: "Стендовый ноутбук Linux", en: "Linux test laptop" },
  unspecified: { ru: "Не указано", en: "Not specified" },
};

function OwnerList({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return <section className="project-owner-section">
    <h3>{title}</h3>
    {items.length ? <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="project-empty-value">{empty}</p>}
  </section>;
}

function ProjectCard({ project }: { project: CompanyProjectCard }) {
  const { language, text } = useWorkspaceLanguage();
  const status = project.roadmap.status ?? (
    project.state === "reconciliation-required"
      ? text("Требуется сверка", "Reconciliation required")
      : project.state === "unavailable"
        ? text("Источник недоступен", "Source unavailable")
        : project.state === "stale-cache"
          ? text("Последняя известная сводка", "Last known snapshot")
          : text("Статус не указан", "Status not specified")
  );
  const targetItems = project.execution_targets
    .filter((target) => target !== "unspecified")
    .map((target) => TARGET_LABELS[target]?.[language] ?? target);
  const noSourceData = text("Нет данных в каноническом источнике", "No data in canonical source");

  return <article className="company-card company-project-card">
    <header className="company-card-head">
      <div>
        <p className="eyebrow">{project.id} · {project.kind}</p>
        <h2>{project.label}</h2>
        {project.roadmap.source_updated ? <p className="project-source-updated">{text("Источник обновлён", "Source updated")}: {project.roadmap.source_updated}</p> : null}
      </div>
      <span className={`company-state company-state-${project.state}`}>{status}</span>
    </header>

    {project.state !== "current-source-backed" ? <p className="project-state-message">{project.message}</p> : null}

    <div className="project-owner-grid">
      <OwnerList title={text("Где сейчас", "Current position")} items={project.roadmap.current} empty={noSourceData} />
      <OwnerList title={text("Что уже сделано", "Completed")} items={project.roadmap.done} empty={noSourceData} />
      <OwnerList title={text("Что можно делать сейчас", "Available now")} items={project.roadmap.unlocked} empty={noSourceData} />
      <OwnerList title={text("Ветки развития", "Development branches")} items={project.roadmap.branches} empty={noSourceData} />
      <OwnerList title={text("Что заблокировано / ждёт", "Blocked / pending")} items={project.roadmap.blocked} empty={text("Нет явно зафиксированных блокеров", "No explicit blockers recorded")} />
      <OwnerList title={text("Где выполнять", "Execution target")} items={targetItems} empty={text("Не указано в каноническом источнике", "Not specified in canonical source")} />
    </div>

    <details className="project-technical-details">
      <summary>{text("Источник и технические доказательства", "Source and technical evidence")}</summary>
      <dl className="company-facts">
        <div><dt>{text("Репозиторий", "Repository")}</dt><dd><code>{project.repository ?? "—"}</code></dd></div>
        <div><dt>{text("Roadmap / status source", "Roadmap / status source")}</dt><dd><code>{project.roadmap_path ?? "—"}</code></dd></div>
        <div><dt>{text("Authority mode", "Authority mode")}</dt><dd>{project.authority_mode}</dd></div>
        <div><dt>{text("Версия roadmap", "Roadmap version")}</dt><dd>{project.roadmap.version ?? "—"}</dd></div>
        <div><dt>{text("Точный commit", "Exact commit")}</dt><dd>{project.source ? <code>{project.source.commit_sha}</code> : "—"}</dd></div>
        <div><dt>{text("SHA-256 содержимого", "Content SHA-256")}</dt><dd>{project.source ? <code>{project.source.content_sha256}</code> : "—"}</dd></div>
        <div><dt>{text("Последнее успешное получение", "Last successful fetch")}</dt><dd>{project.source?.fetched_at ?? "—"}</dd></div>
        <div><dt>{text("Свежесть представления", "Projection freshness")}</dt><dd>{project.source?.freshness ?? text("не подтверждена", "not established")}</dd></div>
      </dl>
    </details>
  </article>;
}

export function CompanyProjects() {
  const { text } = useWorkspaceLanguage();
  const [state, setState] = useState<State>({ kind: "loading" });
  const refresh = (forceRefresh = false) => {
    setState((current) => current.kind === "ready" && forceRefresh
      ? { kind: "ready", data: current.data, refreshing: true }
      : { kind: "loading" });
    void loadCompanyPortfolio(forceRefresh)
      .then((data) => setState({ kind: "ready", data, refreshing: false }))
      .catch((error) => setState({ kind: "error", code: error instanceof Error ? error.message : "COMPANY_PORTFOLIO_UNAVAILABLE" }));
  };
  useEffect(() => { refresh(false); }, []);

  if (state.kind === "loading") return <section className="company-page" aria-live="polite">{text("Читаем сводку проектов…", "Reading project portfolio…")}</section>;
  if (state.kind === "error") return <section className="company-page" role="alert"><p className="eyebrow">F11B · Provisional 0.1.0</p><h1>{text("Портфель проектов недоступен", "Project portfolio unavailable")}</h1><p>{text("Нет ни доступного канонического источника, ни ранее успешно сохранённой локальной сводки. Workspace не подменяет их данными из чата или памяти модели.", "Neither the canonical source nor a previously successful local snapshot is available. Workspace does not replace them with chat or model memory.")}</p><code>{state.code}</code><div><button type="button" onClick={() => refresh(true)}>{text("Повторить", "Retry")}</button></div></section>;

  const sourceBacked = state.data.projects.filter((project) => project.state === "current-source-backed").length;
  const cached = state.data.projects.filter((project) => project.state === "cached-source-backed").length;
  const stale = state.data.projects.filter((project) => project.state === "stale-cache").length;
  const reconciliation = state.data.projects.filter((project) => project.state === "reconciliation-required").length;
  const unavailable = state.data.projects.filter((project) => project.state === "unavailable").length;

  return <section className="company-page" aria-labelledby="company-projects-title">
    <header className="company-page-head project-page-head">
      <div>

        <h1 id="company-projects-title">{text("Проекты компании", "Company projects")}</h1>
        <p>{text("Текущий статус проектов. Откройте проект для следующих шагов и истории.", "Project status. Open a project for next steps and history.")}</p>
      </div>
      <button type="button" disabled={state.refreshing} onClick={() => refresh(true)}>{state.refreshing ? text("Обновляем…", "Refreshing…") : text("Обновить из источников", "Refresh sources")}</button>
    </header>

    <div className="project-portfolio-summary" aria-label={text("Состояние источников", "Source status")}>
      <span><strong>{sourceBacked}</strong>{text("обновлены сейчас", "freshly fetched")}</span>
      <span><strong>{cached}</strong>{text("из свежего локального кэша", "from recent local cache")}</span>
      <span><strong>{stale}</strong>{text("последняя известная сводка", "last known snapshot")}</span>
      <span><strong>{reconciliation}</strong>{text("требуют сверки", "need reconciliation")}</span>
      <span><strong>{unavailable}</strong>{text("без данных", "without data")}</span>
    </div>

    <details className="company-boundary-details">
      <summary>{text("Как читать эту страницу", "How to read this page")}</summary>
      <p>{text("Обычная навигация использует последнюю успешно полученную non-canonical сводку и не зависит от нового GitHub-запроса при каждом возврате на страницу. Кнопка «Обновить из источников» делает явную попытку перечитать зарегистрированные canonical sources. Если внешний источник временно недоступен, прежняя сводка остаётся видимой и маркируется как последняя известная; она не становится canonical truth. Технический источник и exact SHA спрятаны в каждой карточке.", "Ordinary navigation uses the last successful non-canonical snapshot instead of depending on a new GitHub request every time the page is revisited. Refresh sources explicitly re-reads registered canonical sources. If an external source is temporarily unavailable, the previous snapshot remains visible and is marked as last known; it does not become canonical truth. Exact source and SHA remain available in each card.")}</p>
    </details>

    <div className="exec-list">{state.data.projects.map(project=><details key={project.id}><summary><strong>{project.label}</strong><span>{project.roadmap.status==="Active"?text("Активен","Active"):project.roadmap.status==="Paused"?text("На паузе","Paused"):""}{["Active","Paused"].includes(project.roadmap.status??"")?" · ":""}{project.state==="current-source-backed"?text("Получено сейчас","Fetched now"):project.state==="cached-source-backed"?text("Недавняя сводка","Recent snapshot"):project.state==="stale-cache"?text("Устарело","Stale"):text("Требуется проверка","Review needed")}</span></summary><ProjectCard project={project}/></details>)}</div>
    <a href="/manual-context">{text("Заметки и рабочие проекты","Notes and work projects")}</a>
  </section>;
}
