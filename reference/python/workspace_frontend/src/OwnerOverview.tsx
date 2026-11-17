import { useEffect, useState } from "react";
import { useWorkspaceLanguage } from "./i18n";
import "./CompanyWorkspace.css";
import "./OwnerOverview.css";

type Project = { id: string; label: string; kind: "customer" | "internal" };
type Note = { id: string; title: string; text: string; project_id: string | null; at: string };
type Snapshot = { projects: Project[]; notes: Note[]; backup_status?: string };
type State = { kind: "loading" } | { kind: "ready"; value: Snapshot } | { kind: "unavailable" };
const SEED_PREFIX = "Сводка подготовлена AI по прямому поручению собственника 17.11.2026; рабочая интерпретация, не новый канонический факт или решение. ";

function summary(note: Note) {
  const text = note.text.startsWith(SEED_PREFIX) ? note.text.slice(SEED_PREFIX.length) : note.text;
  // Only the explicitly marked initial AI summaries have a known source delimiter.
  // Other notes remain verbatim in project details; do not infer their structure.
  const body = note.text.startsWith(SEED_PREFIX) ? text.split(" Источник:")[0] : text;
  return body.length > 330 ? body.slice(0, 327) + "…" : body;
}

export function OwnerOverview() {
  const { text } = useWorkspaceLanguage();
  const [state,setState] = useState<State>({kind:"loading"});
  const [query,setQuery] = useState("");
  const [refresh,setRefresh] = useState(0);
  useEffect(() => {
    let active=true;
    setState({kind:"loading"});
    void fetch("/api/app/v1/manual-context", {credentials:"same-origin",headers:{"X-Arvectum-Workspace-Release":__ARVECTUM_WORKSPACE_RELEASE__}})
      .then(async r => {
        if (!r.ok) throw Error();
        const d = await r.json() as Snapshot;
        if (!Array.isArray(d.projects) || !Array.isArray(d.notes)) throw Error();
        if (active) setState({kind:"ready",value:d});
      }).catch(() => {if(active)setState({kind:"unavailable"});});
    return () => {active=false;};
  },[refresh]);

  return <section className="company-page owner-overview" aria-labelledby="owner-title">
    <header className="company-page-head">
      <div><p className="eyebrow">Arvectum Workspace</p>
      <h1 id="owner-title">{text("Компания сегодня","Company today")}</h1>
      <p>{text("Проекты и последние рабочие сводки в одном месте.","Projects and latest working summaries in one place.")}</p></div>
      <button type="button" disabled={state.kind==="loading"} onClick={()=>setRefresh(v=>v+1)}>{text("Обновить","Refresh")}</button>
    </header>
    <div className="owner-actions">
      <a href="/manual-context">{text("Все проекты и заметки","All projects and notes")}</a>
      <a href="/company-materials">{text("Документы компании","Company documents")}</a>
      <a href="/copilot">{text("Спросить Arvectum","Ask Arvectum")}</a>
    </div>
    {state.kind==="loading" && <p role="status">{text("Загружаем проекты…","Loading projects…")}</p>}
    {state.kind==="unavailable" && <p role="alert">{text("Рабочие сводки недоступны. Повторите загрузку. Это не означает, что проектов нет.","Working summaries unavailable. Retry. This does not mean there are no projects.")}</p>}
    {state.kind==="ready" && <>
      {state.value.backup_status && state.value.backup_status!=="verified" && <p role="alert">{text("Резервная копия требует внимания. Проверьте её в настройках перед новой записью.","Backup needs attention. Review before writing.")}</p>}
      <div className="owner-summary"><strong>{state.value.projects.length}</strong> {text("рабочих проектов и направлений","work projects and areas")} · {state.value.notes.length} {text("сводок и заметок","summaries and notes")}</div>
      <label className="owner-search">{text("Найти проект","Find project")}<input type="search" placeholder={text("Название проекта…","Project name…")} value={query} onChange={e=>setQuery(e.target.value)}/></label>
      {(["customer","internal"] as const).map(kind=>{
        const projects=state.value.projects.filter(p=>p.kind===kind&&p.label.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
        if(!projects.length)return null;
        return <section key={kind} className="owner-project-group">
          <h2>{kind==="customer"?text("Клиентские проекты","Customer projects"):text("Продукты и внутренние направления","Products and internal areas")}</h2>
          <div className="owner-project-grid">
          {projects.map(p=>{
            const notes=state.value.notes.filter(n=>n.project_id===p.id).sort((a,b)=>b.at.localeCompare(a.at));
            const n=notes[0];
            return <article key={p.id} className="company-card owner-project">
              <h3>{p.label}</h3>
              {n?<><p className="owner-note-title">{n.title}</p><p className="owner-note-summary">{summary(n)}</p>
              <p className="hub-meta">{text("Последняя рабочая запись","Latest working note")}: {n.at.slice(0,10)}</p></>:<p>{text("Сводка ещё не добавлена.","No summary yet.")}</p>}
              <a href={"/manual-context?project="+encodeURIComponent(p.id)}>{text("Открыть проект","Open project")}</a>
            </article>;
          })}
          </div>
        </section>;
      })}
      {!state.value.projects.some(p=>p.label.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))&&<p>{text("Нет проектов по этому запросу.","No matching projects.")}</p>}
      <p className="hub-meta">{text("Рабочие заметки не являются задачами, подтверждёнными обязательствами или автоматической лентой событий.","Working notes are not tasks, verified obligations or an automated event feed.")}</p>
    </>}
  </section>;
}
