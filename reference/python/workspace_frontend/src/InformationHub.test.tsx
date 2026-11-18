import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InformationHub } from "./InformationHub";
import { LanguageProvider } from "./i18n";
import type { CompanyPortfolioProjection, CompanyProjectCard } from "./f11Types";

const base: CompanyProjectCard = {
  id: "COMPANY", label: "Company fixture", kind: "company", disposition: "continue",
  repository: "arvectum2/arvectum-company", roadmap_path: "docs/roadmap/ROADMAP.md",
  execution_targets: [], authority_mode: "External Reference", projection_authority: "non-authoritative",
  state: "current-source-backed", message: "",
  source: { repository: "arvectum2/arvectum-company", path: "docs/roadmap/ROADMAP.md",
    commit_sha: "a".repeat(40), content_sha256: "b".repeat(64), fetched_at: "2026-11-17T09:00:00Z",
    freshness: "fresh-fetch", adapter: "company-roadmap-v1" },
  roadmap: { status: "Verified fixture", version: null, source_updated: null, done: [], current: [], branches: [], unlocked: [], blocked: [] },
};
const unavailable: CompanyProjectCard = { ...base, id: "PORT-007", label: "Unavailable fixture", state: "unavailable", source: null };
const stale: CompanyProjectCard = { ...base, id: "OS", label: "Stale fixture", state: "stale-cache" };
const invalid: CompanyProjectCard = { ...base, id: "PORT-001", label: "Invalid fixture", source: { ...base.source!, commit_sha: "not-a-sha" } };
const projection: CompanyPortfolioProjection = {
  schema: "arvectum.workspace.company-portfolio/1", generated_at: "2026-11-17T09:00:00Z",
  product_contract: {id: "P9.11-F11", version: "0.1.0", lifecycle: "Provisional"},
  projection: {derived: true, canonical_authority: false, read_only: true, roadmap_write_available: false,
    remote_execution_available: false, chat_or_model_memory_used_as_authority: false, visibility_implies_permission: false},
  scope: {organization_resolved_server_side: true, actor_resolved_server_side: true, cross_organization_aggregation: false},
  projects: [base, unavailable, stale, invalid],
};
function show() { render(<LanguageProvider initialLanguage="ru"><InformationHub /></LanguageProvider>); }
const response = (value: unknown, status=200) => new Response(JSON.stringify(value), {status, headers: {"Content-Type": "application/json"}});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe("Information Hub read-only observations", () => {
  it("shows verified exact source links and marks stale/unverified observations", async () => {
    const fetchMock=vi.fn(async () => response(projection));
    vi.stubGlobal("fetch", fetchMock); show();
    await screen.findByText("Состояние источников и последние сводки");
    fireEvent.click(screen.getByText("Состояние источников и последние сводки"));
    await screen.findByRole("heading", {name:"Company fixture"});
    expect(screen.getByText("Устаревшая сводка")).toBeTruthy();
    expect(screen.getByText("Не проверена точная версия")).toBeTruthy();
    expect(screen.getAllByRole("link", {name:"Точный источник"})).toHaveLength(2);
    expect(screen.getAllByRole("link", {name:"Точный источник"})[0].getAttribute("href")).toBe("https://github.com/arvectum2/arvectum-company/blob/"+"a".repeat(40)+"/docs/roadmap/ROADMAP.md");
    expect(screen.getAllByText("Verified fixture")).toHaveLength(2);
    expect(screen.getByText(/Сводка и очередь изменений — разные представления/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", {name:"Устаревшие и недоступные"}));
    expect(screen.queryByRole("heading",{name:"Company fixture"})).toBeNull();
    expect(screen.getByRole("heading",{name:"Stale fixture"})).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it("clears prior source data when explicit refresh is denied", async () => {
    const fetchMock=vi.fn().mockImplementationOnce(async () => response(projection)).mockImplementationOnce(async () => response({code:"DENIED"},403));
    vi.stubGlobal("fetch",fetchMock); show();
    await screen.findByRole("heading",{name:"Company fixture"});
    fireEvent.click(screen.getByRole("button",{name:"Обновить источники"}));
    await screen.findByRole("alert");
    expect(screen.queryByRole("heading",{name:"Company fixture"})).toBeNull();
    expect(screen.queryAllByRole("link",{name:"Точный источник"})).toHaveLength(0);
    expect(String(fetchMock.mock.calls[1][0])).toContain("/api/app/v1/company/portfolio?refresh=true");
  });
  it("can recover from initial source failure without a stored browser snapshot", async () => {
    const fetchMock=vi.fn().mockImplementationOnce(async () => response({},503)).mockImplementationOnce(async () => response(projection));
    vi.stubGlobal("fetch",fetchMock); show();
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button",{name:"Обновить источники"}));
    await waitFor(() => expect(screen.getByRole("heading",{name:"Company fixture"})).toBeTruthy());
  });
});
