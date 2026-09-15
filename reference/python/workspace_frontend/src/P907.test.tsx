import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { ActionableWorkProjection, MyWorkProjection, ProductCompositionProjection, WorkspaceContext } from "./types";

const context: WorkspaceContext = {
  schema: "arvectum.workspace.shell-context/1",
  release: { id: "p9.07.1", app_api_contract: "5", classification: "bounded-internal-provisional", public_api: false },
  organization: { label: "ООО «Арвектум»", scope_resolved_server_side: true },
  actor: { label: "Owner operator", attributable: true, scope_resolved_server_side: true, authentication_source: "P7.04 owner-local credential" },
  session: { csrf_token: "csrf", bounded: true, revocable: true, authority_provided: false },
  navigation: [
    { id: "today", label: "Home", href: "/", availability: "available" },
    { id: "work", label: "Work", href: "/work", availability: "available" },
    { id: "information", label: "Sources", href: "/information", availability: "available" },
    { id: "copilot", label: "Arvectum AI", href: "/copilot", availability: "available" },
    { id: "system", label: "System", href: "/system", availability: "available" },
  ],
  data_governance: { protected_read_revalidated: true, response_minimized: "shell-context-only", canonical_state_in_browser: false },
};

const myWork: MyWorkProjection = {
  schema: "arvectum.workspace.my-work/1",
  generated_at: "2026-08-21T15:00:00Z",
  projection: { derived: true, canonical_authority: false, organizational_authority_provided: false, consequential_action_available: false, visibility_implies_permission: false },
  scope: { organization_resolved_server_side: true, actor_resolved_server_side: true, denied_item_counts_exposed: false },
  health: { state: "fresh", code: "OK", message: "Current", observed_at: "2026-08-21T15:00:00Z", heartbeat_age_seconds: 1 },
  items: [],
};


const actionableWork: ActionableWorkProjection = {
  schema: "arvectum.workspace.actionable-work/1",
  generated_at: "2026-09-15T12:00:00Z",
  projection: {
    derived: true, canonical_authority: false, creates_requests: false, universal_task_primitive: false,
    product_semantics_owned_by_platform: false, organizational_authority_provided: false, urgency_inferred: false,
    owner_responsibility_inferred: false, approval_requirement_inferred: false, action_availability_inferred: false,
  },
  scope: { organization_resolved_server_side: true, actor_resolved_server_side: true, current_workspace_access_revalidated: true, denied_request_counts_exposed: false },
  items: [],
};

const products: ProductCompositionProjection = {
  schema: "arvectum.workspace.product-composition/1",
  generated_at: "2026-08-21T15:00:00Z",
  projection: { derived: true, canonical_authority: false, product_semantics_owned_by_platform: false, organizational_authority_provided: false, cross_product_business_relationship_inferred: false },
  scope: { organization_resolved_server_side: true, actor_resolved_server_side: true, current_access_revalidated: true, switching_products_broadens_authorization: false },
  products: [
    {
      id: "tender-operator", label: "Tender Operator", ownership: "product-owned", repository: "arvectum/tender-agent",
      product_contract: { id: "P6.02", version: "0.1.0", lifecycle: "Provisional" },
      contour: { id: "P7.07", operating_scope: "Persistent Internal / owner-operated", status: "verified-retained-context", summary: "Persistent Tender Operator context is available through its declared CAP-001 Product Contract reliance. EIS remains externally authoritative.", shared_dependencies: ["CAP-001"], source_authority: "ЕИС / zakupki.gov.ru — External Reference" },
      interaction: { kind: "inspect-product-context", product_specific_work_stays_product_owned: true, authority_provided: false, canonical_mutation_available: false, external_effect_available: false },
      technical: { product_release_sha: "a".repeat(40), evidence_refs: ["governed-item:abc"] },
    },
    {
      id: "discount-parser", label: "Discount Parser", ownership: "product-owned", repository: "arvectum/discount-parser",
      product_contract: { id: "P6.06", version: "0.1.0", lifecycle: "Provisional" },
      contour: { id: "P7.08", operating_scope: "Persistent Internal / owner-operated", status: "verified-retained-context", summary: "A verified Discount Parser CAP-004 reconstruction context is retained. Reconstruction is read-only and does not replay a historical external effect.", shared_dependencies: ["CAP-004"], source_authority: "Product-owned external-outcome evidence; platform reconstruction is read-only" },
      interaction: { kind: "inspect-product-context", product_specific_work_stays_product_owned: true, authority_provided: false, canonical_mutation_available: false, external_effect_available: false },
      technical: { product_release_sha: "b".repeat(40), evidence_refs: ["execution:dp-real"] },
    },
  ],
};

function json(value: object): Response {
  return new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/");
});

describe("P9.07 J5 product composition", () => {
  it("moves across two explicit product-owned contexts without widening authority or requiring internal ids", async () => {
    const paths: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      paths.push(path);
      if (path === "/api/app/v1/context") return json(context);
      if (path === "/api/app/v1/my-work") return json(myWork);
      if (path === "/api/app/v1/actionable-work") return json(actionableWork);
      if (path === "/api/app/v1/products") return json(products);
      throw new Error(`Unexpected P9.07 request: ${path}`);
    }));

    window.history.replaceState({}, "", "/");
    render(<App />);
    expect(await screen.findByText("ООО «Арвектум»")).toBeTruthy();

    fireEvent.click(screen.getByRole("link", { name: "Tasks" }));
    await waitFor(() => expect(document.activeElement?.id).toBe("workspace-main"));
    window.history.replaceState({}, "", "/products");
    window.dispatchEvent(new PopStateEvent("popstate"));
    expect(await screen.findByRole("heading", { name: "Product contexts" })).toBeTruthy();
    expect(screen.getByText(/composed, not merged/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("link", { name: "Open Tender Operator" }));
    expect(await screen.findByRole("heading", { name: "Tender Operator" })).toBeTruthy();
    expect(screen.getByText("Verified Tender Operator context")).toBeTruthy();
    expect(screen.queryByText("governed-item:abc")).toBeNull();
    fireEvent.click(screen.getByText("Technical details"));
    expect(screen.getByText(/P6\.02 · Provisional 0\.1\.0/)).toBeTruthy();
    expect(screen.getByText("CAP-001")).toBeTruthy();
    expect(screen.getByText(/ЕИС \/ zakupki\.gov\.ru/)).toBeTruthy();

    fireEvent.click(screen.getByRole("link", { name: "Home" }));
    await waitFor(() => expect(document.activeElement?.id).toBe("workspace-main"));
    expect(screen.getByText("ООО «Арвектум»")).toBeTruthy();
    expect(screen.getByText("Owner operator")).toBeTruthy();

    window.history.replaceState({}, "", "/products");
    window.dispatchEvent(new PopStateEvent("popstate"));
    await screen.findByRole("heading", { name: "Product contexts" });
    fireEvent.click(screen.getByRole("link", { name: "Open Discount Parser" }));
    expect(await screen.findByRole("heading", { name: "Discount Parser" })).toBeTruthy();
    expect(screen.getByText("Verified Discount Parser context")).toBeTruthy();
    expect(screen.queryByText("execution:dp-real")).toBeNull();
    fireEvent.click(screen.getByText("Technical details"));
    expect(screen.getByText(/P6\.06 · Provisional 0\.1\.0/)).toBeTruthy();
    expect(screen.getByText("CAP-004")).toBeTruthy();
    expect(screen.getByText(/never replays an external effect/)).toBeTruthy();

    expect(paths.every((path) => ["/api/app/v1/context", "/api/app/v1/my-work", "/api/app/v1/actionable-work", "/api/app/v1/products"].includes(path))).toBe(true);
  });
});
