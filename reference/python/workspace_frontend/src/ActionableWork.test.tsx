import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ActionableWork } from "./ActionableWork";
import { LanguageProvider } from "./i18n";
import type { ActionableWorkProjection } from "./types";

const base: ActionableWorkProjection = {
  schema: "arvectum.workspace.actionable-work/1",
  generated_at: "2026-09-15T12:00:00+00:00",
  projection: {
    derived: true,
    canonical_authority: false,
    creates_requests: false,
    universal_task_primitive: false,
    product_semantics_owned_by_platform: false,
    organizational_authority_provided: false,
    urgency_inferred: false,
    owner_responsibility_inferred: false,
    approval_requirement_inferred: false,
    action_availability_inferred: false,
  },
  scope: {
    organization_resolved_server_side: true,
    actor_resolved_server_side: true,
    current_workspace_access_revalidated: true,
    denied_request_counts_exposed: false,
  },
  items: [],
};

const realItem: ActionableWorkProjection["items"][number] = {
  id: "0123456789abcdef01234567",
  title: "Review a real product-owned request",
  context: "The owning product reports a current request.",
  attention_reason: "The source explicitly requests owner attention.",
  source: {
    kind: "product",
    id: "tender-agent",
    label: "Tender Agent",
    request_ref: "product-request:opaque-17",
    authority: "Product-owned request state; EIS remains external authority for procurement facts",
    state: "waiting-owner-disposition",
    freshness: "fresh",
    observed_at: "2026-09-15T12:00:00+00:00",
    product_contract: { id: "TA-PC", version: "0.1.0", lifecycle: "Provisional" },
  },
  next_steps: ["Open the product-owned request context.", "Inspect source evidence."],
  governed_execution: {
    preflight_state: "not-yet-evaluated-for-effect",
    current_gate_revalidation_required_for_effect: true,
    consequential_action_available: false,
    organizational_authority_provided: false,
    consequential_approval_provided: false,
  },
  entry: {
    kind: "no-side-effect-context-entry",
    available: true,
    href: "/products/tender-operator?request=opaque-17",
    consequential: false,
    canonical_mutation_requested: false,
    external_effect_requested: false,
    authority_provided: false,
    executes_product_operation: false,
  },
  technical: {
    provenance_refs: ["product-request:opaque-17", "product-release:abc"],
    exact_source_request_ref_available: true,
  },
};

function mockProjection(value: ActionableWorkProjection) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  })));
}

function renderEnglish() {
  render(<LanguageProvider initialLanguage="en"><ActionableWork /></LanguageProvider>);
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/work");
});

describe("P10.06 Actionable Work", () => {
  it("renders an empty live state without manufacturing a request", async () => {
    mockProjection(base);
    renderEnglish();

    expect(await screen.findByRole("heading", { name: "Action requests" })).toBeTruthy();
    expect(screen.getByText("There are no verified action requests now.")).toBeTruthy();
    expect(screen.getByText(/does not manufacture a request/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /approve|execute|retry effect/i })).toBeNull();
  });

  it("shows source-declared context without urgency or execution authority", async () => {
    mockProjection({ ...base, items: [realItem] });
    renderEnglish();

    expect(await screen.findByText("Review a real product-owned request")).toBeTruthy();
    expect(screen.getByText("The source explicitly requests owner attention.")).toBeTruthy();
    expect(screen.getByText("waiting-owner-disposition")).toBeTruthy();
    expect(screen.getByText("TA-PC · Provisional 0.1.0")).toBeTruthy();
    expect(screen.getByText(/Opening context does not execute a product operation/)).toBeTruthy();
    expect(screen.queryByText(/High urgency|Medium urgency|Low urgency/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /approve|execute|promote|retry/i })).toBeNull();
    expect(screen.getByRole("link", { name: "Open request context" }).getAttribute("href"))
      .toBe("/products/tender-operator?request=opaque-17");
  });

  it("navigates only to the backend-declared no-side-effect context entry", async () => {
    window.history.replaceState({}, "", "/work");
    mockProjection({ ...base, items: [realItem] });
    renderEnglish();

    fireEvent.click(await screen.findByRole("link", { name: "Open request context" }));
    expect(window.location.pathname).toBe("/products/tender-operator");
    expect(window.location.search).toBe("?request=opaque-17");
  });

  it("withholds entry when the source is not fresh", async () => {
    const stale = {
      ...realItem,
      source: { ...realItem.source, freshness: "stale" as const },
      entry: { ...realItem.entry, available: false, href: null },
    };
    mockProjection({ ...base, items: [stale] });
    renderEnglish();

    expect(await screen.findByText(/source is not confirmed fresh/i)).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Open request context" })).toBeNull();
  });

  it("fails visibly instead of substituting retained or inferred requests", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "ACTIONABLE_WORK_UNAVAILABLE" }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    })));
    renderEnglish();

    expect(await screen.findByRole("heading", { name: "Action requests are unavailable" })).toBeTruthy();
    expect(screen.getByText(/does not substitute retained or inferred requests/)).toBeTruthy();
    expect(screen.getByText("ACTIONABLE_WORK_UNAVAILABLE")).toBeTruthy();
  });
});
