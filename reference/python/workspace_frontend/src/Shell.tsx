import { Activity } from "./Activity";
import { CompanyGeneratedOutputs } from "./CompanyGeneratedOutputs";
import { CompanyMaterials } from "./CompanyMaterials";
import { CompanyProjects } from "./CompanyProjects";
import { InformationHub } from "./InformationHub";
import { Copilot } from "./Copilot";
import { Discovery } from "./Discovery";
import { Dogfooding } from "./Dogfooding";
import { Governed } from "./Governed";
import { Guide } from "./Guide";
import { MyWork } from "./MyWork";
import { ObjectDetail } from "./ObjectDetail";
import { Organization } from "./Organization";
import { Products } from "./Products";
import { System } from "./System";
import { Work } from "./Work";
import arvectumLogo from "./assets/arvectum-logo.svg";
import { navigationLabels, useWorkspaceLanguage } from "./i18n";
import type { NavigationItem, WorkspaceContext } from "./types";

function groupForPath(path: string): string {
  if (path === "/" || path === "/today" || path === "/guide") return "today";
  if (
    path === "/work"
    || path === "/my-work"
    || path === "/products"
    || path.startsWith("/products/")
    || path === "/projects"
    || path === "/information-hub"
    || path === "/company-materials"
    || path === "/company-generated-outputs"
  ) return "work";
  if (path === "/information" || path === "/search" || path === "/records" || path === "/documents" || path === "/knowledge" || path.startsWith("/objects/")) return "information";
  if (path === "/copilot") return "copilot";
  return "system";
}

function navigateTo(href: string) {
  window.history.pushState({}, "", href);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function Today() {
  const { text } = useWorkspaceLanguage();
  return <>
    <section className="home-intro" aria-labelledby="today-title">
      <p className="eyebrow">{text("Arvectum OS · Рабочее пространство", "Arvectum OS · Workspace")}</p>
      <h1 id="today-title">{text("Что делать сейчас", "What to do now")}</h1>
      <p>{text(
        "Если текущих задач нет, откройте проекты компании, материалы и шаблоны, найдите документ, задайте вопрос Arvectum AI или откройте руководство по возможностям Workspace.",
        "If there are no current tasks, open Company projects, materials and templates, find a document, ask Arvectum AI, or open the Workspace capability guide.",
      )}</p>
    </section>
    <section className="home-actions" aria-label={text("Основные действия", "Primary actions")}>
      <a href="/work" onClick={(event) => { event.preventDefault(); navigateTo("/work"); }}>{text("Открыть задачи", "Open tasks")}</a>
      <a href="/information-hub" onClick={(event) => { event.preventDefault(); navigateTo("/information-hub"); }}>{text("Входящая информация", "Information Hub")}</a>
      <a href="/projects" onClick={(event) => { event.preventDefault(); navigateTo("/projects"); }}>{text("Проекты компании", "Company projects")}</a>
      <a href="/company-materials" onClick={(event) => { event.preventDefault(); navigateTo("/company-materials"); }}>{text("Материалы компании", "Company materials")}</a>
      <a href="/company-generated-outputs" onClick={(event) => { event.preventDefault(); navigateTo("/company-generated-outputs"); }}>{text("Созданные документы", "Generated documents")}</a>
      <a href="/information" onClick={(event) => { event.preventDefault(); navigateTo("/information"); }}>{text("Найти документ", "Find a document")}</a>
      <a href="/copilot" onClick={(event) => { event.preventDefault(); navigateTo("/copilot"); }}>{text("Спросить Arvectum", "Ask Arvectum")}</a>
      <a href="/guide" onClick={(event) => { event.preventDefault(); navigateTo("/guide"); }}>{text("Открыть руководство", "Open guide")}</a>
    </section>
    <MyWork embedded />
  </>;
}

export function Shell({ context, onLogout }: { context: WorkspaceContext; onLogout: () => void }) {
  const { language, setLanguage, text } = useWorkspaceLanguage();
  const currentPath = window.location.pathname;
  const activeId = groupForPath(currentPath);
  const active = context.navigation.find((item) => item.id === activeId) ?? context.navigation[0];
  const objectId = currentPath.startsWith("/objects/") ? decodeURIComponent(currentPath.slice("/objects/".length)) : null;
  const productId = currentPath.startsWith("/products/") ? decodeURIComponent(currentPath.slice("/products/".length)) : null;
  const navLabel = (item: NavigationItem) => navigationLabels[item.id]?.[language] ?? item.label;
  const navigate = (item: NavigationItem) => (event: React.MouseEvent<HTMLAnchorElement>) => { event.preventDefault(); navigateTo(item.href); };
  const specialWorkPath = currentPath === "/information-hub" || currentPath === "/projects" || currentPath === "/company-materials" || currentPath === "/company-generated-outputs";
  const primaryNavigation = context.navigation.flatMap((item) => {
    const items = [
      <li key={item.id}><a href={item.href} onClick={navigate(item)} aria-current={item.id === active.id && !specialWorkPath ? "page" : undefined}><span>{navLabel(item)}</span></a></li>,
    ];
    if (item.id === "work") {
      items.push(
        <li key="information-hub"><a href="/information-hub" aria-current={currentPath === "/information-hub" ? "page" : undefined} onClick={(event) => { event.preventDefault(); navigateTo("/information-hub"); }}><span>{text("Входящая информация", "Information Hub")}</span></a></li>,
        <li key="company-projects"><a href="/projects" aria-current={currentPath === "/projects" ? "page" : undefined} onClick={(event) => { event.preventDefault(); navigateTo("/projects"); }}><span>{text("Проекты", "Projects")}</span></a></li>,
        <li key="company-materials"><a href="/company-materials" aria-current={currentPath === "/company-materials" ? "page" : undefined} onClick={(event) => { event.preventDefault(); navigateTo("/company-materials"); }}><span>{text("Материалы компании", "Company materials")}</span></a></li>,
        <li key="company-generated-outputs"><a href="/company-generated-outputs" aria-current={currentPath === "/company-generated-outputs" ? "page" : undefined} onClick={(event) => { event.preventDefault(); navigateTo("/company-generated-outputs"); }}><span>{text("Созданные документы", "Generated documents")}</span></a></li>,
      );
    }
    return items;
  });

  let content: React.ReactNode;
  if (objectId) content = <ObjectDetail objectId={objectId} />;
  else if (currentPath === "/products" || productId) content = <Products productId={productId} />;
  else if (currentPath === "/information-hub") content = <InformationHub />;
  else if (currentPath === "/projects") content = <CompanyProjects />;
  else if (currentPath === "/company-materials") content = <CompanyMaterials csrfToken={context.session.csrf_token} />;
  else if (currentPath === "/company-generated-outputs") content = <CompanyGeneratedOutputs csrfToken={context.session.csrf_token} />;
  else if (currentPath === "/my-work") content = <MyWork />;
  else if (currentPath === "/search" || currentPath === "/information") content = <Discovery />;
  else if (currentPath === "/records") content = <Discovery kind="record" />;
  else if (currentPath === "/documents") content = <Discovery kind="document" />;
  else if (currentPath === "/knowledge") content = <Discovery kind="knowledge" />;
  else if (currentPath === "/organization") content = <Organization organizationLabel={context.organization.label} />;
  else if (currentPath === "/activity") content = <Activity />;
  else if (currentPath === "/governed") content = <Governed csrfToken={context.session.csrf_token} />;
  else if (currentPath === "/dogfooding") content = <Dogfooding csrfToken={context.session.csrf_token} />;
  else if (currentPath === "/guide") content = <Guide release={context.release.id} />;
  else if (activeId === "today") content = <Today />;
  else if (activeId === "work") content = <Work />;
  else if (activeId === "information") content = <Discovery />;
  else if (activeId === "copilot") content = <Copilot csrfToken={context.session.csrf_token} />;
  else content = <System release={context.release.id} />;

  return <div className="app-shell">
    <a className="skip-link" href="#workspace-main">{text("К содержанию", "Skip to content")}</a>
    <aside className="sidebar" aria-label={text("Навигация Arvectum OS", "Workspace navigation")}>
      <div className="brand" aria-label="Arvectum OS"><img src={arvectumLogo} className="brand-logo" alt="Arvectum" /><span className="brand-product">OS</span></div>
      <nav aria-label={text("Навигация Arvectum OS", "Workspace navigation")}><ul>{primaryNavigation}</ul></nav>
      <div className="sidebar-controls">
        <a href="/guide" onClick={(event) => { event.preventDefault(); navigateTo("/guide"); }}>{text("Руководство", "Guide")}</a>
        <div className="language-switch" role="group" aria-label={text("Язык интерфейса", "Interface language")}><button type="button" className={language === "ru" ? "active" : ""} aria-pressed={language === "ru"} onClick={() => setLanguage("ru")}>RU</button><button type="button" className={language === "en" ? "active" : ""} aria-pressed={language === "en"} onClick={() => setLanguage("en")}>EN</button></div><div className="sidebar-footnote">{text("Внутреннее рабочее пространство", "Internal workspace")} · {context.release.id}</div></div>
    </aside>
    <div className="workspace-column">
      <header className="topbar">
        <div className="context-chip" aria-label={`${text("Организация", "Organization")}: ${context.organization.label}`}><span className="eyebrow">{text("Организация", "Organization")}</span><strong>{context.organization.label}</strong></div>
        <div className="context-chip" aria-label={`${text("Пользователь", "User")}: ${context.actor.label}`}><span className="eyebrow">{text("Пользователь", "User")}</span><strong>{context.actor.label}</strong></div>
        <form className="global-search" role="search" onSubmit={(event) => { event.preventDefault(); const query = String(new FormData(event.currentTarget).get("q") ?? "").trim(); navigateTo(query ? `/information?q=${encodeURIComponent(query)}` : "/information"); }}>
          <label className="visually-hidden" htmlFor="global-search-query">{text("Глобальный поиск", "Global search")}</label><input id="global-search-query" name="q" type="search" maxLength={160} placeholder={text("Найти документ, запись, знание…", "Find a document, record, knowledge…")} /><button type="submit">{text("Найти", "Search")}</button>
        </form>
        <button type="button" className="quiet-button" onClick={onLogout}>{text("Выйти", "Sign out")}</button>
      </header>
      <main id="workspace-main" tabIndex={-1}>{content}</main>
    </div>
  </div>;
}
