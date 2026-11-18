// URL is only a view filter, never a source of organizational authority.
// Accept opaque existing working-project IDs, not a portfolio ID or title.
export function initialProject(search = window.location.search): string | null {
  const values = new URLSearchParams(search).getAll("project_id");
  if (values.length === 0) return "";
  return values.length === 1 && /^PRJ-[0-9a-f]{32}$/.test(values[0]) ? values[0] : null;
}
export function projectHref(route: "/manual-context" | "/crm", project: string): string {
  return route + "?project_id=" + encodeURIComponent(project);
}
export function admittedProject(project: string | null, projects: {id:string}[]): boolean {
  return project === "" || (project !== null && projects.some(p => p.id === project));
}
