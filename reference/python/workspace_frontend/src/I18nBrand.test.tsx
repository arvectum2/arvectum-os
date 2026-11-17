import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import arvectumLogo from "./assets/arvectum-logo.svg?raw";
import { LanguageProvider } from "./i18n";
import { Shell } from "./Shell";
import type { MyWorkProjection, WorkspaceContext } from "./types";

const context: WorkspaceContext = {
  schema: "arvectum.workspace.shell-context/1",
  release: { id: "p9.11.5", app_api_contract: "11", classification: "bounded-internal-provisional", public_api: false },
  organization: { label: "ООО «Арвектум»", scope_resolved_server_side: true },
  actor: { label: "Owner operator", attributable: true, scope_resolved_server_side: true, authentication_source: "P7.04 owner-local credential" },
  session: { csrf_token: "test-only", bounded: true, revocable: true, authority_provided: false },
  navigation: [
    { id: "today", label: "Today", href: "/", availability: "available" },
    { id: "work", label: "Work", href: "/work", availability: "available" },
    { id: "information", label: "Information", href: "/information", availability: "available" },
    { id: "copilot", label: "Arvectum AI", href: "/copilot", availability: "available" },
    { id: "system", label: "System", href: "/system", availability: "available" },
  ],
  data_governance: { protected_read_revalidated: true, response_minimized: "shell-context-only", canonical_state_in_browser: false },
};
const projection: MyWorkProjection = { schema: "arvectum.workspace.my-work/1", generated_at: "2026-08-23T08:00:00Z", projection: { derived: true, canonical_authority: false, organizational_authority_provided: false, consequential_action_available: false, visibility_implies_permission: false }, scope: { organization_resolved_server_side: true, actor_resolved_server_side: true, denied_item_counts_exposed: false }, health: { state: "fresh", code: "OK", message: "Current.", observed_at: "2026-08-23T08:00:00Z", heartbeat_age_seconds: 1 }, items: [] };
const scenarioProjection: MyWorkProjection = { ...projection, items: [{ id: "11111111111111111111", kind: "waiting-approval", group: "decision-required", urgency: "high", title: "Fixture approval", reason: "Fixture approval is pending", source: "fixture/workspace/attention", next_step: "Inspect fixture evidence", evidence_mode: "scenario", observed_at: "2026-08-23T08:00:00Z", open_href: "/my-work?focus=11111111111111111111", interaction: "inspect-only", technical_evidence_available: false, authority_provided: false }] };

afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState({}, "", "/"); });

describe("P9.11 owner-first Workspace", () => {
  it("uses exactly the owner-oriented Russian primary navigation and today actions", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({projects:[],notes:[],backup_status:"verified"}), { status: 200, headers: { "Content-Type": "application/json" } })));
    render(<LanguageProvider><Shell context={context} onLogout={() => undefined} /></LanguageProvider>);
    expect(document.documentElement.lang).toBe("ru");
    expect(arvectumLogo).toContain('viewBox="0 0 425.2 72.06"');
    expect(arvectumLogo).toContain("BRAND__Ok----Block");
    expect(screen.getByRole("img", { name: "Arvectum" })).toBeTruthy();
    expect(screen.queryByText("AV")).toBeNull();
    expect(screen.getAllByRole("link").filter((link) => ["Главная", "Проекты", "Документы", "Arvectum AI", "Настройки"].includes(link.textContent ?? "")).map((link) => link.textContent)).toEqual(["Главная", "Проекты", "Документы", "Arvectum AI", "Настройки"]);
    expect(screen.queryByRole("link", { name: "Записи" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Знания" })).toBeNull();
    expect(screen.getByRole("heading", { name: "Компания сегодня" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Все проекты и заметки" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Документы компании" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Спросить Arvectum" })).toBeTruthy();
  });

  it("switches to English without browser storage", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({projects:[],notes:[],backup_status:"verified"}), { status: 200, headers: { "Content-Type": "application/json" } })));
    render(<LanguageProvider><Shell context={context} onLogout={() => undefined} /></LanguageProvider>);
    fireEvent.click(screen.getByRole("button", { name: "EN" }));
    expect(document.documentElement.lang).toBe("en");
    expect(screen.getByRole("link", { name: "Home" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Company today" })).toBeTruthy();
  });

  it("shows a compact action-first Home and withholds scenario evidence", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({projects:[],notes:[],backup_status:"verified"}), { status: 200, headers: { "Content-Type": "application/json" } })));
    render(<LanguageProvider><Shell context={context} onLogout={() => undefined} /></LanguageProvider>);
    expect(screen.getByText("Arvectum Workspace")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Компания сегодня" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Добро пожаловать" })).toBeNull();
    expect(screen.getByRole("link", { name: "Все проекты и заметки" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Документы компании" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Спросить Arvectum" })).toBeTruthy();
    expect(await screen.findByText("Нет проектов по этому запросу.")).toBeTruthy();
    expect(screen.getAllByRole("link", { name: "Все проекты и заметки" }).length).toBeGreaterThan(0);
    expect(screen.queryByText("Сейчас нет задач, требующих вашего решения.")).toBeNull();
  });

  it("does not present scenario fixtures as ordinary Home work", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(scenarioProjection), { status: 200, headers: { "Content-Type": "application/json" } })));
    render(<LanguageProvider><Shell context={context} onLogout={() => undefined} /></LanguageProvider>);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText("Fixture approval")).toBeNull();
    expect(screen.queryByText("fixture/workspace/attention")).toBeNull();
    expect(screen.queryByText(/тестовые сценарии/i)).toBeNull();
  });

  it("groups legacy product and technical deep routes under Work and System", () => {
    window.history.replaceState({}, "", "/products/tender-operator");
    const { unmount } = render(<LanguageProvider initialLanguage="en"><Shell context={context} onLogout={() => undefined} /></LanguageProvider>);
    expect(screen.getByRole("link", { name: "Settings" }).getAttribute("aria-current")).toBe("page");
    unmount();

    window.history.replaceState({}, "", "/governed?focus=11111111111111111111");
    render(<LanguageProvider initialLanguage="en"><Shell context={context} onLogout={() => undefined} /></LanguageProvider>);
    expect(screen.getByRole("link", { name: "Settings" }).getAttribute("aria-current")).toBe("page");
  });
});
