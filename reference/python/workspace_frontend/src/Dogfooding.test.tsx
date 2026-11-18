import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Dogfooding } from "./Dogfooding";
import type { DogfoodingBacklog, DogfoodingObservation } from "./dogfoodingTypes";

const recorded: DogfoodingObservation = {
  schema: "arvectum.workspace.dogfooding-observation/1",
  id: "observation-1",
  recorded_at: "2026-08-22T08:00:00Z",
  release_id: "p9.11.0",
  journey: "J1",
  surface: "my-work",
  severity: "material",
  classification: "workspace-usability",
  summary: "Needs one fewer navigation step",
  details: "The ordinary path requires an avoidable extra step.",
  status: "open",
  disposition: null,
  disposition_rationale: null,
  dispositioned_at: null,
};

function backlog(items: DogfoodingObservation[] = []): DogfoodingBacklog {
  const materialOpen = items.filter((item) => item.status === "open" && item.severity !== "minor").length;
  const deferredMaterial = items.filter(
    (item) => item.status === "dispositioned" && item.disposition === "deferred" && item.severity !== "minor",
  ).length;
  return {
    schema: "arvectum.workspace.dogfooding-backlog/1",
    generated_at: "2026-08-22T08:00:00Z",
    projection: {
      derived: true,
      canonical_authority: false,
      canonical_event: false,
      validated_knowledge: false,
      organizational_authority_provided: false,
      consequential_action_available: false,
    },
    scope: {
      organization_resolved_server_side: true,
      actor_resolved_server_side: true,
      current_access_revalidated: true,
      cross_organization_aggregation: false,
    },
    retention: { bounded: true, days: 90, max_items: 200, free_text_minimized: true, pruned_on_access: true },
    summary: {
      total: items.length,
      open: items.filter((item) => item.status === "open").length,
      material_open: materialOpen,
      closure_blocking: materialOpen + deferredMaterial,
    },
    items,
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("P9.11 dogfooding", () => {
  it("states the Observation boundary and captures minimized friction through the secured client", async () => {
    let current = backlog();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path === "/api/app/v1/dogfooding" && (!init?.method || init.method === "GET")) {
        return new Response(JSON.stringify(current), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (path === "/api/app/v1/dogfooding/observations" && init?.method === "POST") {
        expect(new Headers(init.headers).get("X-Arvectum-CSRF")).toBe("csrf-test");
        const body = JSON.parse(String(init.body));
        expect(body).toEqual({
          journey: "J1",
          surface: "my-work",
          severity: "material",
          classification: "workspace-usability",
          summary: "Needs one fewer navigation step",
          details: "The ordinary path requires an avoidable extra step.",
        });
        expect(body.organization).toBeUndefined();
        expect(body.actor).toBeUndefined();
        current = backlog([recorded]);
        return new Response(JSON.stringify(recorded), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      return new Response("{}", { status: 404, headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Dogfooding csrfToken="csrf-test" />);
    expect(await screen.findByText(/not canonical Events, validated Knowledge/)).toBeTruthy();
    expect(await screen.findByText(/Real owner sessions are still required/)).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Short observation"), { target: { value: recorded.summary } });
    fireEvent.change(screen.getByLabelText("Minimal supporting detail"), { target: { value: recorded.details } });
    fireEvent.click(screen.getByRole("button", { name: "Record observation" }));

    expect(await screen.findByText(recorded.summary)).toBeTruthy();
    expect(screen.getByText("Open")).toBeTruthy();
    expect(screen.getByText(/still block P9.11 friction-backlog closure/)).toBeTruthy();
    expect(fetchMock).toHaveBeenCalled();
  });

  it("exposes only factual closure choices for security-authority blockers", async () => {
    const securityFinding: DogfoodingObservation = {
      ...recorded,
      id: "security-1",
      severity: "blocker",
      classification: "security-authority",
      summary: "Authority boundary is ambiguous",
    };
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(backlog([securityFinding])), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })));
    render(<Dogfooding csrfToken="csrf-test" />);

    expect(await screen.findByText(securityFinding.summary)).toBeTruthy();
    expect(screen.queryByRole("option", { name: /accept risk/i })).toBeNull();
    expect(screen.queryByRole("option", { name: "Deferred with explicit rationale" })).toBeNull();
    expect(screen.queryByRole("option", { name: "Routed to product-owned backlog" })).toBeNull();
    expect(screen.queryByRole("option", { name: "Routed to governance work" })).toBeNull();
    expect(screen.getByRole("option", { name: "Resolved and rechecked" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "Not reproducible after recheck" })).toBeTruthy();
    await waitFor(() => expect(screen.getByRole("button", { name: "Disposition" })).toBeTruthy());
  });
});
