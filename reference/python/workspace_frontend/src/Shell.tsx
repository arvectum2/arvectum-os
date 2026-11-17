import { Activity } from "./Activity";
import { CompanyGeneratedOutputs } from "./CompanyGeneratedOutputs";
import { CompanyMaterials } from "./CompanyMaterials";
import { CompanyProjects } from "./CompanyProjects";
import { InformationHub } from "./InformationHub";
import { ManualContext } from "./ManualContext";
import { Copilot } from "./Copilot";
import { Discovery } from "./Discovery";
import { Dogfooding } from "./Dogfooding";
import { Governed } from "./Governed";
import { Guide } from "./Guide";
import { MyWork } from "./MyWork";
import { OwnerOverview } from "./OwnerOverview";
import { ObjectDetail } from "./ObjectDetail";
import { Organization } from "./Organization";
import { Products } from "./Products";
import { System } from "./System";
import { Work } from "./Work";
import arvectumLogo from "./assets/arvectum-logo.svg";
import { navigationLabels, useWorkspaceLanguage } from "./i18n";
import type { WorkspaceContext } from "./types";

function groupForPath(path: string): string {
  if (path === "/" || path === "/today" || path === "/guide") return "today";
  if (
    path === "/work"
    || path === "/my-work"
    || path === "/products"
    || path.startsWith("/products/")
    || path === "/projects"
    || path === "/information-hub"
    || path === "/manual-context"
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

export function Shell({ context, onLogout }: { context: WorkspaceContext; onLogout: () => void }) {
  const { language, setLanguage, text } = useWorkspaceLanguage();
  const currentPath = window.location.pathname;
  const activeId = groupForPath(currentPath);
  const objectId = currentPath.startsWith("/objects/") ? decodeURIComponent(currentPath.slice("/objects/".length)) : null;
  const productId = currentPath.startsWith("/products/") ? decodeURIComponent(currentPath.slice("/products/".length)) : null;
  const businessNavigationId = currentPath === "/manual-context" ? "work"
    : currentPath === "/company-materials" || currentPath === "/company-generated-outputs" ? "information"
    : activeId === "work" ? "system" : activeId;
  const primaryNavigation = context.navigation.map((item) => {
    const href = item.id === "work" ? "/manual-context" : item.id === "information" ? "/company-materials" : item.href;
    const label = item.id === "work" ? text("Проекты", "Projects")
      : item.id === "system" ? text("Настройки", "Settings")
      : navigationLabels[item.id]?.[language] ?? item.label;
    return <li key={item.id}><a href={href} aria-current={item.id === businessNavigationId ? "page" : undefined} onClick={(event) => { event.preventDefault(); navigateTo(href); }}><span>{label}</span></a></li>;
  });

  let content: React.ReactNode;
  if (objectId) content = <ObjectDetail objectId={objectId} />;
  else if (currentPath === "/products" || productId) content = <Products productId={productId} />;
  else if (currentPath === "/manual-context") content = <ManualContext csrfToken={context.session.csrf_token} />;
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
  else if (activeId === "today") content = <OwnerOverview />;
  else if (activeId === "work") content = <Work />;
  else if (activeId === "information") content = <Discovery />;
  else if (activeId === "copilot") content = <Copilot csrfToken={context.session.csrf_token} />;
  else content = <System release={context.release.id} />;

  return <div className="app-shell">
    <a className="skip-link" href="#workspace-main">{text("К содержанию", "Skip to content")}</a>
    <aside className="sidebar" aria-label={text("Навигация Arvectum OS", "Workspace navigation")}>
      <div className="brand" aria-label="Arvectum Workspace"><img src={arvectumLogo} className="brand-logo" alt="Arvectum" /><span className="brand-product">Workspace</span></div>
      <nav aria-label={text("Навигация Arvectum OS", "Workspace navigation")}><ul>{primaryNavigation}</ul></nav>
      <div className="sidebar-controls">
        <a href="/guide" onClick={(event) => { event.preventDefault(); navigateTo("/guide"); }}>{text("Руководство", "Guide")}</a>
        <div className="language-switch" role="group" aria-label={text("Язык интерфейса", "Interface language")}><button type="button" className={language === "ru" ? "active" : ""} aria-pressed={language === "ru"} onClick={() => setLanguage("ru")}>RU</button><button type="button" className={language === "en" ? "active" : ""} aria-pressed={language === "en"} onClick={() => setLanguage("en")}>EN</button></div><div className="sidebar-footnote">{text("Внутреннее рабочее пространство", "Internal workspace")}</div></div>
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
