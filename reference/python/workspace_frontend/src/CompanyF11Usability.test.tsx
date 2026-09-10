import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CompanyProjects } from "./CompanyProjects";
import { LanguageProvider } from "./i18n";
import { Shell } from "./Shell";
import type { CompanyAssetLibraryProjection, CompanyPortfolioProjection } from "./f11Types";
import type { WorkspaceContext } from "./types";

const portfolio: CompanyPortfolioProjection = {
  schema: "arvectum.workspace.company-portfolio/1",
  generated_at: "2026-08-26T15:00:00Z",
  product_contract: { id: "P9.11-F11", version: "0.1.0", lifecycle: "Provisional" },
  projection: {
    derived: true, canonical_authority: false, read_only: true,
    roadmap_write_available: false, remote_execution_available: false,
    chat_or_model_memory_used_as_authority: false, visibility_implies_permission: false,
  },
  scope: { organization_resolved_server_side: true, actor_resolved_server_side: true, cross_organization_aggregation: false },
  projects: [{
    id: "PORT-003", label: "Arvectum Proxy Launcher", kind: "product", disposition: "continue",
    repository: "arvectum2/proxy-launcher", roadmap_path: "docs/ROADMAP.md",
    execution_targets: ["web", "windows-test-laptop"], authority_mode: "External Reference",
    projection_authority: "non-authoritative", state: "current-source-backed", message: "Source backed",
    source: {
      repository: "arvectum2/proxy-launcher", path: "docs/ROADMAP.md", commit_sha: "a".repeat(40),
      content_sha256: "b".repeat(64), fetched_at: "2026-08-26T15:00:00Z", freshness: "fresh-fetch", adapter: "proxy-roadmap-v1",
    },
    roadmap: {
      status: "CURRENT / LOCAL REAL-HOST GATE", version: "0.2.3", source_updated: "2026-08-25",
      done: ["APL-IP-001 reconciliation — DONE"], current: ["APL-WIN-014 — enforced local gate"],
      branches: ["[Web] ChatGPT/GitHub", "[Win] ARVECTUM-DEMO"], unlocked: ["APL-WIN-014 — CURRENT"],
      blocked: ["Windows production enforcement STOP-GATE"],
    },
  }],
};

const stalePortfolio: CompanyPortfolioProjection = {
  ...portfolio,
  generated_at: "2026-08-26T15:05:00Z",
  projects: [{
    ...portfolio.projects[0], state: "stale-cache",
    message: "Канонический источник сейчас недоступен; показана последняя успешно полученная сводка.",
    source: portfolio.projects[0].source ? { ...portfolio.projects[0].source, freshness: "stale-cache" } : null,
  }],
};

const library: CompanyAssetLibraryProjection = {
  schema: "arvectum.workspace.company-asset-library/1",
  generated_at: "2026-08-28T12:00:00Z",
  product_contract: { id: "p9-11-f11-arvectum-company-workspace", version: "0.2.0", lifecycle: "Provisional" },
  views: { drafts: [], review: [], accepted: [], archive: [] },
  actions: { governed_admission_available: false },
  scope: { organization_resolved_server_side: true, actor_resolved_server_side: true, cross_organization_access: false },
  governance: {
    workspace_is_authority_source: false, staging_is_canonical: false, review_state_is_canonical: false,
    canonical_admission_requires_governed_execution: true, generated_output_default: "TransientOutput",
    validated_knowledge_created: false,
  },
};

const context: WorkspaceContext = {
  schema: "arvectum.workspace.shell-context/1",
  release: { id: "p9.11.9", app_api_contract: "11", classification: "bounded-internal-provisional", public_api: false },
  organization: { label: "ООО «Арвектум»", scope_resolved_server_side: true },
  actor: { label: "Owner operator", attributable: true, scope_resolved_server_side: true, authentication_source: "local-owner" },
  session: { csrf_token: "csrf", bounded: true, revocable: true, authority_provided: false },
  navigation: [
    { id: "today", label: "Home", href: "/today", availability: "available" },
    { id: "work", label: "Work", href: "/work", availability: "available" },
    { id: "information", label: "Information", href: "/information", availability: "available" },
    { id: "copilot", label: "Copilot", href: "/copilot", availability: "available" },
    { id: "system", label: "System", href: "/system", availability: "available" },
  ],
  data_governance: { protected_read_revalidated: true, response_minimized: "shell-context-only", canonical_state_in_browser: false },
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/");
});

describe("F11 owner usability remediation", () => {
  it("renders the same six owner questions before technical provenance", async () => {
    window.history.replaceState({}, "", "/projects");
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(portfolio), { status: 200, headers: { "Content-Type": "application/json" } })));
    render(<LanguageProvider initialLanguage="ru"><CompanyProjects /></LanguageProvider>);
    expect(await screen.findByRole("heading", { name: "Arvectum Proxy Launcher" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Где сейчас" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Что уже сделано" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Что можно делать сейчас" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Ветки развития" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Что заблокировано / ждёт" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Где выполнять" })).toBeTruthy();
    expect(screen.getByText("Стендовый ноутбук Windows")).toBeTruthy();
    const technical = screen.getByText("Источник и технические доказательства");
    const technicalDetails = technical.closest("details");
    expect(technicalDetails?.hasAttribute("open")).toBe(false);
    fireEvent.click(technical);
    expect(technicalDetails?.hasAttribute("open")).toBe(true);
    expect(screen.getByText("arvectum2/proxy-launcher")).toBeTruthy();
  });

  it("keeps Projects and Company materials in the primary navigation so the owner can return", async () => {
    window.history.replaceState({}, "", "/company-materials");
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const payload = String(input).includes("company/portfolio") ? portfolio : library;
      return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
    render(<LanguageProvider initialLanguage="ru"><Shell context={context} onLogout={() => undefined} /></LanguageProvider>);
    expect(await screen.findByRole("heading", { name: "Материалы компании" })).toBeTruthy();
    const projectsLink = screen.getByRole("link", { name: "Проекты" });
    const materialsLink = screen.getByRole("link", { name: "Материалы компании" });
    expect(projectsLink.closest("nav")).toBeTruthy();
    expect(materialsLink.closest("nav")).toBeTruthy();
    expect(materialsLink.getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Задачи" }).getAttribute("aria-current")).toBeNull();
  });

  it("keeps last-known-good project content visible when explicit source refresh degrades to stale cache", async () => {
    window.history.replaceState({}, "", "/projects");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const payload = String(input).includes("refresh=true") ? stalePortfolio : portfolio;
      return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<LanguageProvider initialLanguage="ru"><CompanyProjects /></LanguageProvider>);
    expect(await screen.findByText("APL-WIN-014 — enforced local gate")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Обновить из источников" }));
    expect(screen.getByText("APL-WIN-014 — enforced local gate")).toBeTruthy();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(String(fetchMock.mock.calls[1][0])).toContain("/api/app/v1/company/portfolio?refresh=true");
    expect(await screen.findByText(/последняя успешно полученная сводка/i)).toBeTruthy();
    expect(screen.getByText("APL-WIN-014 — enforced local gate")).toBeTruthy();
    expect(screen.queryByText("Портфель проектов недоступен")).toBeNull();
  });
});
