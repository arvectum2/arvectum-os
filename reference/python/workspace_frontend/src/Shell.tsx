import { Activity } from "./Activity";
import { CompanyGeneratedOutputs } from "./CompanyGeneratedOutputs";
import { CompanyMaterials } from "./CompanyMaterials";
import { CompanyProjects } from "./CompanyProjects";
import { InformationHub } from "./InformationHub";
import { FocusedRoadmapInbox } from "./RoadmapInbox";
import { ManualContext } from "./ManualContext";
import { CRM } from "./CRM";
import { MissionControl } from "./MissionControl";
import { ExecutiveOverview } from "./ExecutiveOverview";
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
import { useWorkspaceLanguage } from "./i18n";
import type { WorkspaceContext } from "./types";

function groupForPath(path: string): string {
  if (["/","/today","/mission-control","/control-details"].includes(path)) return "today";
  if (["/projects","/manual-context"].includes(path)) return "projects";
  if (path==="/crm") return "clients";
  if (path==="/finance") return "finance";
  if (["/library","/company-materials","/company-generated-outputs","/information","/search","/records","/documents","/knowledge"].includes(path)||path.startsWith("/objects/")) return "information";
  if (["/work","/my-work","/products","/operations","/information-hub"].includes(path)||path.startsWith("/products/")) return "work";
  if(path==="/copilot") return "copilot";
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
  const has=(id:string)=>context.navigation.some(x=>x.id===id&&x.availability==="available");
  const link=(id:string,href:string,ru:string,en:string,secondary=false)=><a className={secondary?"exec-secondary-link":undefined} href={href} onClick={event=>{event.preventDefault();navigateTo(href);}} aria-current={activeId===id?"page":undefined}>{text(ru,en)}</a>;
  const primaryNavigation=[
    ...(has("today")?[["today","/","Обзор","Overview"]]:[]),
    ...(has("work")?[["work","/work","Работа","Work"],["projects","/projects","Проекты","Projects"],["clients","/crm","Клиенты","Clients"],["finance","/finance","Финансы","Finances"]]:[]),
    ...(has("information")||has("work")?[["information",has("work")?"/library":"/information","Документы","Documents"]]:[]),
  ].map(([id,href,ru,en])=><li key={id}>{link(id,href,ru,en)}</li>);
  const libraryRoute=["/library","/company-materials","/company-generated-outputs","/information","/search","/documents","/records","/knowledge"].includes(currentPath);
  const documentTabs=libraryRoute&&has("work")?<div className="hub-filters exec-library-tabs" aria-label={text("Разделы документов","Document sections")}>{[
    ["/library","Библиотека","Library"],["/company-generated-outputs","На проверке","Under review"],["/information","Поиск","Search"]
  ].map(([href,ru,en])=><a key={href} className="quiet-link" href={href} aria-current={currentPath===href||href==="/library"&&currentPath==="/company-materials"?"page":undefined} onClick={event=>{event.preventDefault();navigateTo(href);}}>{text(ru,en)}</a>)}</div>:null;

  let content: React.ReactNode;
  if (objectId) content = <ObjectDetail objectId={objectId} />;
  else if (currentPath === "/products" || productId) content = <Products productId={productId} />;
  else if (currentPath === "/control-details") content = <MissionControl csrfToken={context.session.csrf_token} />;
  else if (currentPath === "/crm") content = <CRM csrfToken={context.session.csrf_token} />;
  else if (currentPath === "/manual-context") content = <ManualContext csrfToken={context.session.csrf_token} />;
  else if (currentPath === "/information-hub" && window.location.search === "?view=changes") content = <FocusedRoadmapInbox key={"focused-inbox-"+context.session.csrf_token} csrfToken={context.session.csrf_token} />;
  else if (currentPath === "/information-hub") content = <InformationHub csrfToken={context.session.csrf_token} />;
  else if (currentPath === "/projects") content = <CompanyProjects />;
  else if (currentPath === "/library" || currentPath === "/company-materials") content = <CompanyMaterials csrfToken={context.session.csrf_token} />;
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
  else if (activeId === "today") content = <ExecutiveOverview key={"overview-"+context.session.csrf_token} csrfToken={context.session.csrf_token}/>;
  else if (activeId === "finance") content = <ExecutiveOverview key={"finance-"+context.session.csrf_token} mode="finance" csrfToken={context.session.csrf_token}/>;
  else if (currentPath === "/operations") content = <Work/>;
  else if (activeId === "work") content = <ExecutiveOverview key={"work-"+context.session.csrf_token} mode="work" csrfToken={context.session.csrf_token}/>;
  else if (activeId === "information") content = <Discovery />;
  else if (activeId === "copilot") content = <Copilot csrfToken={context.session.csrf_token} />;
  else content = <System release={context.release.id} />;

  return <div className="app-shell">
    <a className="skip-link" href="#workspace-main">{text("К содержанию", "Skip to content")}</a>
    <aside className="sidebar" aria-label={text("Навигация Arvectum OS", "Workspace navigation")}>
      <div className="brand" aria-label="Arvectum OS"><img src={arvectumLogo} className="brand-logo" alt="Arvectum" /><span className="brand-product">OS</span></div>
      <nav aria-label={text("Навигация Arvectum OS", "Workspace navigation")}><ul>{primaryNavigation}</ul></nav>
      <div className="sidebar-controls">
        {has("work")&&link("work","/information-hub","Входящие","Inbox",true)}
        {has("copilot")&&link("copilot","/copilot","Arvectum AI","Arvectum AI",true)}
        {has("system")&&link("system","/system","Настройки","Settings",true)}
        <a href="/guide" onClick={(event) => { event.preventDefault(); navigateTo("/guide"); }}>{text("Руководство", "Guide")}</a>
        <div className="language-switch" role="group" aria-label={text("Язык интерфейса", "Interface language")}><button type="button" className={language === "ru" ? "active" : ""} aria-pressed={language === "ru"} onClick={() => setLanguage("ru")}>RU</button><button type="button" className={language === "en" ? "active" : ""} aria-pressed={language === "en"} onClick={() => setLanguage("en")}>EN</button></div><div className="sidebar-footnote">{text("Внутреннее рабочее пространство", "Internal workspace")}<details><summary>{text("Версия приложения", "Application version")}</summary><code>{context.release.id}</code></details></div></div>
    </aside>
    <div className="workspace-column">
      <header className="topbar">
        <div className="context-chip" aria-label={`${text("Организация", "Organization")}: ${context.organization.label}`}><span className="eyebrow">{text("Организация", "Organization")}</span><strong>{context.organization.label}</strong></div>
        <div className="context-chip" aria-label={`${text("Пользователь", "User")}: ${language==="ru"&&context.actor.label==="Owner operator"?"Собственник":context.actor.label}`}><span className="eyebrow">{text("Пользователь", "User")}</span><strong>{language==="ru"&&context.actor.label==="Owner operator"?"Собственник":context.actor.label}</strong></div>
        <form className="global-search" role="search" onSubmit={(event) => { event.preventDefault(); const query = String(new FormData(event.currentTarget).get("q") ?? "").trim(); navigateTo(query ? `/information?q=${encodeURIComponent(query)}` : "/information"); }}>
          <label className="visually-hidden" htmlFor="global-search-query">{text("Глобальный поиск", "Global search")}</label><input id="global-search-query" name="q" type="search" maxLength={160} placeholder={text("Найти документ, запись, знание…", "Find a document, record, knowledge…")} /><button type="submit">{text("Найти", "Search")}</button>
        </form>
        <button type="button" className="quiet-button" onClick={onLogout}>{text("Выйти", "Sign out")}</button>
      </header>
      <main id="workspace-main" tabIndex={-1}>{documentTabs}{content}</main>
    </div>
  </div>;
}
