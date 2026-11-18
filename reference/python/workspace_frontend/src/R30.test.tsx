import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type {
  DiscoveryProjection,
  GovernedExperienceProjection,
  GovernedPreflightResult,
  MyWorkProjection,
  ObjectContext,
  WorkspaceContext,
} from "./types";

const context: WorkspaceContext = {
  schema: "arvectum.workspace.shell-context/1",
  release: { id: "p9.06.2", app_api_contract: "4", classification: "bounded-internal-provisional", public_api: false },
  organization: { label: "ООО «Арвектум»", scope_resolved_server_side: true },
  actor: { label: "Owner operator", attributable: true, scope_resolved_server_side: true, authentication_source: "P7.04 owner-local credential" },
  session: { csrf_token: "r30-csrf", bounded: true, revocable: true, authority_provided: false },
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
  generated_at: "2026-08-21T13:00:00Z",
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
    message: "Attention sources were evaluated against the current healthy persistent runtime.",
    observed_at: "2026-08-21T13:00:00Z",
    heartbeat_age_seconds: 1,
  },
  items: [],
};

const discovery: DiscoveryProjection = {
  schema: "arvectum.workspace.discovery/1",
  generated_at: "2026-08-21T13:00:00Z",
  query: "0344100006426000005",
  kind_filter: "document",
  projection: {
    derived: true,
    canonical_authority: false,
    organizational_authority_provided: false,
    consequential_action_available: false,
    search_result_is_authority: false,
  },
  scope: {
    organization_resolved_server_side: true,
    actor_resolved_server_side: true,
    denied_result_counts_exposed: false,
    protected_snippets_minimized: true,
  },
  health: {
    state: "fresh",
    code: "OK",
    message: "Search was rebuilt from the current authorized governed source snapshot.",
    observed_at: "2026-08-21T13:00:00Z",
  },
  results: [{
    id: "0123456789abcdef0123",
    kind: "document",
    semantic_role: "Document",
    title: "Document — EIS exact notice attachment evidence",
    summary: "Governed Document available from ЕИС / zakupki.gov.ru.",
    source: "ЕИС / zakupki.gov.ru",
    authority_mode: "External Reference",
    state: "admitted · CAP-004 reconstruction complete",
    knowledge_role: null,
    open_href: "/objects/0123456789abcdef0123",
    interaction: "inspect-only",
    authority_provided: false,
  }],
};

const objectContext: ObjectContext = {
  schema: "arvectum.workspace.object-context/1",
  id: "0123456789abcdef0123",
  kind: "document",
  semantic_role: "Document",
  title: "Document — EIS exact notice attachment evidence",
  summary: "Governed Document available from ЕИС / zakupki.gov.ru.",
  source: "ЕИС / zakupki.gov.ru",
  knowledge_role: null,
  authority: {
    mode: "External Reference",
    scope: "EIS exact notice attachment evidence",
    authoritative_source: "ЕИС / zakupki.gov.ru",
    organizational_authority_provided: false,
    visibility_implies_permission: false,
  },
  state: { lifecycle: "admitted", validation: "CAP-004 reconstruction complete", classification: "internal" },
  context: {
    meaning: "Governed Document available from ЕИС / zakupki.gov.ru.",
    process: "This object is connected to retained governed execution/provenance evidence. Any consequential continuation must use the governed-action path and revalidate current gates.",
    next_step: "Inspect the waiting governance gates before any consequential action.",
    interaction: "inspect-only",
    consequential_action_available: false,
  },
  technical: {
    subject_identity: "document-subject/eis-0344100006426000005-exact",
    version_identity: "document-version/eis-0344100006426000005-exact-v1",
    schema_version: "1",
    source_release_sha: "release-sha",
    provenance_refs: ["event-version/eis-admitted-v1"],
    related_execution_subject: "execution-subject/eis-real",
    related_execution_version: "execution-version/eis-real-v5",
    related_event_version: "event-version/eis-admitted-v1",
    related_checkpoint: "checkpoint-eis-real",
  },
  governed_preflight: {
    outcome: "Waiting",
    waiting_gates: ["Authorization", "Organizational Authority", "Data Governance", "Consequential Approval"],
    authority_provided: false,
  },
  projection: {
    presentation_authority: "non-authoritative",
    current_source_revalidated: true,
    exact_version_exposed_on_demand: true,
  },
};

const governed: GovernedExperienceProjection = {
  schema: "arvectum.workspace.governed-experience/1",
  generated_at: "2026-08-21T13:00:00Z",
  presentation: {
    title: "EIS document governed execution",
    summary: "A real retained execution/provenance chain for an EIS-backed governed document. The authoritative external source remains ЕИС / zakupki.gov.ru.",
    source: "ЕИС / zakupki.gov.ru",
    authority_mode: "External Reference",
    authority_scope: "EIS exact notice attachment evidence",
    validation_status: "CAP-004 reconstruction complete",
  },
  execution: {
    status: "Waiting",
    meaning: "Required action decisions are still unresolved, so the execution remains fail-closed.",
    waiting_decisions: ["Authorization", "Organizational Authority", "Data Governance", "Consequential Approval"],
    technical_identity_available: true,
  },
  decisions: [
    { name: "Authorization", state: "Waiting", basis: "No action-specific authorization decision supplied." },
    { name: "Organizational Authority", state: "Waiting", basis: "Technical access supplies no Organizational Authority." },
    { name: "Data Governance", state: "Waiting", basis: "No purpose-specific data-governance decision supplied." },
    { name: "Consequential Approval", state: "Waiting", basis: "The browser/session/button is not approval." },
  ],
  action: {
    kind: "governed-preflight",
    label: "Run governed preflight",
    available: true,
    consequential: false,
    canonical_mutation_requested: false,
    external_effect_requested: false,
    authority_provided: false,
    explanation: "Re-check the real retained execution and all four governance gates now.",
  },
  technical: {
    release_sha: "a".repeat(40),
    source_subject: "document-subject/eis-real",
    source_version: "document-version/eis-real-v1",
    execution_subject: "execution-subject/eis-real",
    execution_version: "execution-version/eis-real-v5",
    event_version: "event-version/eis-real-v1",
    checkpoint_id: "checkpoint-real",
    provenance_refs: ["event-version/eis-real-v1"],
  },
  scope: {
    organization_resolved_server_side: true,
    actor_resolved_server_side: true,
    current_access_revalidated: true,
    organizational_authority_provided: false,
    visibility_implies_permission: false,
  },
};

const preflightResult: GovernedPreflightResult = {
  schema: "arvectum.workspace.governed-preflight-result/1",
  recorded_at: "2026-08-21T13:01:00Z",
  outcome: "Waiting",
  status_text: "Preflight executed: WAITING / fail-closed. Missing governance decisions were not manufactured.",
  canonical_mutation_requested: false,
  canonical_mutation_performed: false,
  external_effect_requested: false,
  external_effect_performed: false,
  organizational_authority_provided: false,
  consequential_approval_provided: false,
  evidence: { classification: "owner-local non-canonical proof evidence", sha256: "b".repeat(64) },
};

function json(value: object): Response {
  return new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/");
});

describe("R30 M9-alpha integrated J1-J4 ordinary path", () => {
  it("keeps non-actionable preflight out of Home while preserving diagnostic inspection", async () => {
    const requests: Array<{ path: string; method: string; body: BodyInit | null | undefined }> = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const method = init?.method ?? "GET";
      requests.push({ path, method, body: init?.body });
      if (path === "/api/app/v1/context") return json(context);
      if (path === "/api/app/v1/my-work") return json(myWork);
      if (path.startsWith("/api/app/v1/discovery")) return json(discovery);
      if (path.startsWith("/api/app/v1/objects/")) return json(objectContext);
      if (path === "/api/app/v1/governed" && method === "GET") return json(governed);
      if (path === "/api/app/v1/governed/preflight" && method === "POST") return json(preflightResult);
      throw new Error(`Unexpected R30 request: ${method} ${path}`);
    }));

    window.history.replaceState({}, "", "/");
    render(<App />);

    // J1: a preflight-only proof does not manufacture ordinary owner work.
    expect(await screen.findByRole("heading", { name: "Company overview" })).toBeTruthy();
    expect(screen.getByText(/Partial coverage: missing records/)).toBeTruthy();
    expect(requests.every(r=>!r.path.includes("governed/preflight"))).toBeTruthy();
    expect(screen.queryByText("Execution is stopped")).toBeNull();
    expect(screen.queryByText("ЕИС / zakupki.gov.ru")).toBeNull();

    // J2: use only the human EIS notice number and narrow by human-readable result type.
    const globalSearch = screen.getByLabelText("Global search");
    fireEvent.change(globalSearch, { target: { value: "0344100006426000005" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Search" })[0]);
    expect(await screen.findByRole("heading", { name: "Search information" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Result type"), { target: { value: "document" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Search" }).at(-1)!);
    expect(await screen.findByRole("heading", { name: "Document — EIS exact notice attachment evidence" })).toBeTruthy();
    expect(new URLSearchParams(window.location.search).get("kind")).toBe("document");

    // J3: object meaning and external authority are primary; exact ids remain hidden until drill-down.
    expect(screen.getByText("External Reference")).toBeTruthy();
    expect(screen.queryByText("document-subject/eis-0344100006426000005-exact")).toBeNull();
    fireEvent.click(screen.getByRole("link", { name: "Open context" }));
    expect(await screen.findByRole("heading", { name: "What this is" })).toBeTruthy();
    expect(screen.getByText("Outcome: Waiting.")).toBeTruthy();
    expect(screen.queryByText("document-subject/eis-0344100006426000005-exact")).toBeNull();

    // J4: diagnostics retain the gates without presenting them as owner work.
    fireEvent.click(screen.getByRole("link", { name: "Open related execution and governed action" }));
    expect(await screen.findByRole("heading", { name: "Governed execution readiness check" })).toBeTruthy();
    expect(screen.getByText("No concrete action is currently requested.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Settings" }).getAttribute("aria-current")).toBe("page");
    expect(screen.queryByText("Execution is stopped")).toBeNull();
    for (const gate of ["Action access", "Organization authority", "Data-use permission", "Final action approval"]) {
      expect(screen.getByText(gate)).toBeTruthy();
    }
    fireEvent.click(screen.getByRole("button", { name: "Re-check status" }));
    expect(await screen.findByText(/Nothing changed\. Readiness conditions remain unconfirmed/)).toBeTruthy();

    const post = requests.find((request) => request.path === "/api/app/v1/governed/preflight" && request.method === "POST");
    expect(post).toBeTruthy();
    expect(post?.body).toBeUndefined();
    expect(screen.queryByText(/canonical mutation performed/i)).toBeNull();
    expect(screen.queryByText(/external effect performed/i)).toBeNull();
  });
});
