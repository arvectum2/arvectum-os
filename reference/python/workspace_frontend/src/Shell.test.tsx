import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Shell } from "./Shell";
import type { WorkspaceContext } from "./types";

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

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/");
});

describe("P9.04 shell", () => {
  it("presents explicit context and a business overview on Home", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({projects:[],notes:[],backup_status:"verified"}), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })));
    window.history.replaceState({}, "", "/");
    render(<Shell context={context} onLogout={() => undefined} />);
    expect(screen.getByLabelText("Organization: ООО «Арвектум»")).toBeTruthy();
    expect(screen.getByLabelText("User: Owner operator")).toBeTruthy();
    expect(screen.getByRole("navigation", { name: "Workspace navigation" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Projects" }).getAttribute("href")).toBe("/manual-context");
    expect(await screen.findByRole("heading", { name: "Company today" })).toBeTruthy();
    expect(await screen.findByText("No matching projects.")).toBeTruthy();
    expect(screen.queryByText("Execution is stopped")).toBeNull();
  });
});
