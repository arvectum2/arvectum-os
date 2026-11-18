import { useEffect, useRef, useState } from "react";
import { useWorkspaceLanguage } from "./i18n";
import "./CompanyWorkspace.css";
import "./InformationHub.css";
import "./ManualContext.css";

type Project = { id: string; label: string; kind: "customer" | "internal" };
type Note = { id: string; revision: number; title: string; text: string; project_id: string | null; at: string };
type Snapshot = { projects: Project[]; notes: Note[]; backup_status?: "verified" | "stale" | "unavailable" };
type Pending = { key: string; operation: string; payload: Record<string, unknown> };
const root = "/api/app/v1/manual-context";

async function request(path = "", init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  headers.set("X-Arvectum-Workspace-Release", __ARVECTUM_WORKSPACE_RELEASE__);
  if (init.body) headers.set("Content-Type", "application/json");
  const response = await fetch(root + path, { ...init, headers, credentials: "same-origin" });
  if (!response.ok) throw new Error(String(response.status));
  return response;
}

function newKey() {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), n => n.toString(16).padStart(2, "0")).join("");
}

export function ManualContext({ csrfToken }: { csrfToken: string }) {
  const { text } = useWorkspaceLanguage();
  const [data, setData] = useState<Snapshot | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [label, setLabel] = useState("");
  const [kind, setKind] = useState<Project["kind"]>("customer");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [project, setProject] = useState("");
  const [filter, setFilter] = useState("");
  const [editing, setEditing] = useState<Note | null>(null);
  const [history, setHistory] = useState<Note[]>([]);
  const pending = useRef<Pending | null>(null);
  const generation = useRef(0);

  function clearPrivate() {
    setData(null); setLabel(""); setTitle(""); setBody(""); setProject(""); setFilter(""); setEditing(null); setHistory([]);
  }
  async function load() {
    const seq = ++generation.current;
    setBusy(true); setError("");
    try {
      const response = await request();
      const snapshot = await response.json() as Snapshot;
      if (seq === generation.current) { setData(snapshot); setHistory([]); }
    } catch {
      if (seq === generation.current) { pending.current = null; clearPrivate(); setError("unavailable"); }
    } finally { if (seq === generation.current) setBusy(false); }
  }
  useEffect(() => { void load(); return () => { generation.current++; }; }, []);

  async function submit(operation: string, payload: Record<string, unknown>) {
    if (busy || !data) return;
    const seq = ++generation.current;
    setBusy(true); setError("");
    const previous = pending.current;
    const record = previous && previous.operation === operation && JSON.stringify(previous.payload) === JSON.stringify(payload)
      ? previous : { key: newKey(), operation, payload };
    pending.current = record;
    try {
      await request("/submit", { method: "POST", headers: { "X-Arvectum-CSRF": csrfToken }, body: JSON.stringify(record) });
      if (seq !== generation.current) return;
      pending.current = null;
      if (operation === "project") setLabel("");
      else { setTitle(""); setBody(""); setEditing(null); }
      await load();
    } catch (err) {
      if (seq !== generation.current) return;
      if (err instanceof Error && ["401","403"].includes(err.message)) {
        pending.current = null; clearPrivate(); setError("unavailable");
      } else { setError("request"); }
    } finally { if (seq === generation.current) setBusy(false); }
  }

  async function showHistory(note: Note) {
    const seq = ++generation.current;
    setBusy(true); setError("");
    try {
      const response = await request("/notes/" + encodeURIComponent(note.id) + "/history");
      const revisions = await response.json() as Note[];
      if (seq === generation.current) setHistory(revisions);
    } catch {
      if (seq === generation.current) { pending.current = null; clearPrivate(); setError("unavailable"); }
    } finally { if (seq === generation.current) setBusy(false); }
  }

  async function download() {
    const seq = ++generation.current;
    setBusy(true); setError("");
    try {
      const response = await request("/export");
      const blob = await response.blob();
      if (seq !== generation.current) return;
      const url = URL.createObjectURL(blob);
      try {
        const a = document.createElement("a");
        a.href = url; a.download = "arvectum-manual-context-private.json"; a.click();
      } finally { URL.revokeObjectURL(url); }
    } catch {
      if (seq === generation.current) { pending.current = null; clearPrivate(); setError("unavailable"); }
    } finally { if (seq === generation.current) setBusy(false); }
  }

  return <section className="company-page manual-context" aria-labelledby="manual-title">
    <header className="company-page-head"><div>

      <h1 id="manual-title">{text("Заметки проектов", "Project notes")}</h1>
      <p>{text("Ручные рабочие наблюдения. Не договоры, обязательства или решения.", "Manual work observations. Not contracts, obligations or decisions.")}</p>
    </div><button disabled={busy} type="button" onClick={() => void load()}>{text("Обновить", "Refresh")}</button></header>
    {error === "unavailable" && <p role="alert">{text("Ручной контекст недоступен или пилот не активирован. Данные скрыты.", "Manual context unavailable or pilot not activated. Data hidden.")}</p>}
    {error === "request" && <p role="alert">{text("Запись не подтверждена. Проверьте доступность резервной копии, повторите ту же операцию либо обновите сводку.", "Save not confirmed. Check backup availability, retry the same operation or refresh.")}</p>}
    {!data && busy && <p role="status">{text("Проверяем доступ…", "Checking access…")}</p>}
    {data && <>
      {data.backup_status && <p role="status" className={data.backup_status === "verified" ? "hub-meta" : "hub-warning"}>{data.backup_status === "verified" ? text("Резервная копия проверена", "Backup verified") : text("Резервная копия устарела или недоступна. Перед новой записью потребуется восстановить резервирование.", "Backup stale or unavailable. Backup must be restored before new writes.")}</p>}
      <p className="hub-warning">{text("Закрытый пилот: не вводите персональные данные, секреты и конфиденциальные сведения заказчиков.", "Restricted pilot: do not enter personal data, secrets or confidential customer information.")}</p>
      <details className="exec-secondary" open={editing?true:undefined}><summary>{text("Добавить проект или заметку","Add project or note")}</summary><div className="manual-forms">
        <form className="company-card" onSubmit={e => { e.preventDefault(); void submit("project", { label, kind }); }}>
          <h2>{text("Создать проект", "Create project")}</h2>
          <label>{text("Название проекта", "Project name")}<input required maxLength={160} value={label} onChange={e => setLabel(e.target.value)} disabled={busy}/></label>
          <label>{text("Тип проекта", "Project kind")}<select value={kind} onChange={e => setKind(e.target.value as Project["kind"])} disabled={busy}>
            <option value="customer">{text("Клиентский", "Customer")}</option><option value="internal">{text("Внутренний", "Internal")}</option>
          </select></label>
          <button disabled={busy || !label.trim()} type="submit">{text("Создать проект", "Create project")}</button>
        </form>
        <form className="company-card" onSubmit={e => { e.preventDefault(); void submit(editing ? "revise" : "capture", { title, text: body, project_id: project || null, ...(editing ? { note_id: editing.id, expected_revision: editing.revision } : {}) }); }}>
          <h2>{editing ? text("Исправить заметку", "Revise note") : text("Добавить заметку", "Add note")}</h2>
          <label>{text("Заголовок", "Title")}<input required maxLength={160} value={title} onChange={e => setTitle(e.target.value)} disabled={busy}/></label>
          <label>{text("Заметка", "Note")}<textarea required maxLength={4000} rows={4} value={body} onChange={e => setBody(e.target.value)} disabled={busy}/></label>
          <label>{text("Привязка к проекту", "Project link")}<select value={project} onChange={e => setProject(e.target.value)} disabled={busy}>
            <option value="">{text("Без проекта", "No project")}</option>{data.projects.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select></label>
          <button disabled={busy || !title.trim() || !body.trim()} type="submit">{text("Сохранить заметку", "Save note")}</button>
          {editing && <button type="button" disabled={busy} onClick={() => {setEditing(null); setTitle(""); setBody("");}}>{text("Отмена", "Cancel")}</button>}
        </form>
      </div></details>
      <div className="hub-filters"><label>{text("История проекта", "Project history")}<select disabled={busy} value={filter} onChange={e => {setFilter(e.target.value);setHistory([]);}}>
        <option value="">{text("Все заметки", "All notes")}</option>{data.projects.map(p => <option value={p.id} key={p.id}>{p.label}</option>)}
      </select></label><button disabled={busy} type="button" onClick={() => void download()}>{text("Экспортировать данные", "Export data")}</button></div>
      {data.notes.filter(n => !filter || n.project_id === filter).slice().reverse().map(n => <details className="company-card" key={n.id}><summary><strong>{n.title}</strong></summary>
        <p className="manual-note">{n.text}</p>
        <p className="hub-meta">{data.projects.find(p => p.id === n.project_id)?.label ?? text("Без проекта", "No project")} · {text("Версия", "Revision")} {n.revision} · {new Date(n.at).toLocaleString()}</p>
        <div className="hub-filters"><button disabled={busy} type="button" onClick={() => {setEditing(n);setTitle(n.title);setBody(n.text);setProject(n.project_id ?? "");}}>{text("Редактировать", "Edit")}</button>
        <button disabled={busy} type="button" onClick={() => void showHistory(n)}>{text("Версии", "Versions")}</button></div>
      </details>)}
      {!!history.length && <section className="company-card"><h2>{text("История версий", "Revision history")}</h2>{history.map(n => <div key={n.revision}><h3>{n.revision} · {n.title}</h3><p className="manual-note">{n.text}</p><p className="hub-meta">{n.at}</p></div>)}</section>}
    </>}
  </section>;
}
