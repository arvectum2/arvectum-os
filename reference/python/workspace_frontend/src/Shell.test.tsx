import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Shell } from "./Shell";
import type { MyWorkProjection, WorkspaceContext } from "./types";

const context: WorkspaceContext = {
  schema: "arvectum.workspace.shell-context/1",
  release: { id: "p9.04.1", app_api_contract: "2", classification: "bounded-internal-provisional", public_api: false },
  organization: { label: "ООО «Арвектум»", scope_resolved_server_side: true },
  actor: { label: "Owner operator", attributable: true, scope_resolved_server_side: true, authentication_source: "P7.04 owner-local credential" },
  session: { csrf_token: "test-only", bounded: true, revocable: true, authority_provided: false },
  navigation: [
    { id: "today", label: "Home", href: "/", availability: "available" },
    { id: "work", label: "Work", href: "/work", availability: "available" },
  ],
  data_governance: { protected_read_revalidated: true, response_minimized: "shell-context-only", canonical_state_in_browser: false }
};

const projection: MyWorkProjection = {
  schema: "arvectum.workspace.my-work/1",
  generated_at: "2026-08-21T10:00:00Z",
  projection: {
    derived: true,
    canonical_authority: false,
    organizational_authority_provided: false,
    consequential_action_available: false,
    visibility_implies_permission: false,
  },
  scope: {
    organization_resolved_server_side: true,
    actor_resolved_server_side: true,
    denied_item_counts_exposed: false,
  },
  health: {
    state: "fresh",
    code: "OK",
    message: "Attention sources are current.",
    observed_at: "2026-08-21T10:00:00Z",
    heartbeat_age_seconds: 1,
  },
  items: [{
    id: "11111111111111111111",
    kind: "waiting-input",
    group: "decision-required",
    urgency: "high",
    title: "Governed preflight is waiting",
    reason: "Decision evidence is missing.",
    source: "ЕИС / zakupki.gov.ru",
    next_step: "Inspect blockers through the governed flow.",
    evidence_mode: "live",
    observed_at: "2026-08-21T10:00:00Z",
    open_href: "/my-work?focus=11111111111111111111",
    interaction: "inspect-only",
    technical_evidence_available: true,
    authority_provided: false,
  }],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/");
});

describe("P9.04 shell", () => {
  it("presents explicit context and a useful Needs Attention projection on Home", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(projection), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })));
    window.history.replaceState({}, "", "/");
    render(<Shell context={context} onLogout={() => undefined} />);
    expect(screen.getByLabelText("Organization: ООО «Арвектум»")).toBeTruthy();
    expect(screen.getByLabelText("User: Owner operator")).toBeTruthy();
    expect(screen.getByRole("navigation", { name: "Workspace navigation" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Work" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Company overview" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button",{name:"Read summary"}));
    expect(await screen.findByRole("link",{name:"Governed preflight is waiting"})).toBeTruthy();
    expect(screen.getByText(/Partial coverage: missing records/)).toBeTruthy();
  });
});

it("focused changes entry reads only the saved inbox, never portfolio or procurement",async()=>{
 window.history.replaceState({},"","/information-hub?view=changes");
 const f=vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{
  expect(String(input)).toBe("/api/app/v1/roadmap-inbox");
  expect(init?.method??"GET").toBe("GET");
  expect(init?.cache).toBe("no-store");
  return new Response(JSON.stringify({coverage:"partial",pending_count:0,backup_status:"verified",items:[],sources:[]}),{status:200});
 });
 vi.stubGlobal("fetch",f);
 render(<Shell context={context} onLogout={()=>undefined}/>);
 expect(screen.getByRole("heading",{name:"Change inbox"})).toBeTruthy();
 await screen.findByText("No saved changes pending review.");
 expect(f).toHaveBeenCalledTimes(1);
 expect(screen.getByRole("link",{name:"All incoming information and sources"}).getAttribute("href")).toBe("/information-hub");
 expect(screen.queryByRole("button",{name:"Refresh sources"})).toBeNull();
 fireEvent.click(screen.getByRole("button",{name:"Refresh inbox"}));
 await screen.findByText("No saved changes pending review.");
 expect(f).toHaveBeenCalledTimes(2);
});
