import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CompanyGeneratedOutputs } from "./CompanyGeneratedOutputs";
import { LanguageProvider } from "./i18n";
import type { CompanyGeneratedOutputsProjection } from "./p10_05Types";

const baseProjection: CompanyGeneratedOutputsProjection = {
  schema: "arvectum.workspace.company-generated-outputs/1",
  generated_at: "2026-08-29T08:00:00Z",
  product_contract: {
    id: "p9-11-f11-arvectum-company-workspace",
    version: "0.2.0",
    lifecycle: "Provisional",
  },
  items: [{
    output_id: "OUT-generated0001",
    state: "TransientOutput",
    canonical_authority: false,
    filename: "generated-company.docx",
    media_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    project_id: "PORT-003",
    created_at: "2026-08-29T07:50:00Z",
    created_by: "principal:owner@arvectum",
    output_sha256: "b".repeat(64),
    source_material_id: "MAT-template0001",
    source_version_id: "MV-template0001",
    source_sha256: "a".repeat(64),
    download_href: "/api/app/v1/company-materials/outputs/OUT-generated0001/download",
    review: {
      disposition: "PendingReview",
      reason: null,
      document_title: null,
      semantic_role: null,
      updated_at: null,
      actor: null,
      canonical_authority: false,
    },
    inherited_handling: {
      classification: "internal",
      purpose: "company governed document generation",
      rights: ["company-internal-use"],
      retention_rule: "retain-while-current-plus-governed-history",
      deletion_rule: "delete-only-through-governed-retention-process",
      permitted_reuse: ["company-internal-document-generation"],
    },
    exact_source_available: true,
    source_error: null,
    canonical_promotion: null,
    promotion_available: false,
    validated_knowledge: false,
  }],
  actions: { governed_promotion_available: false },
  governance: {
    output_source_state: "TransientOutput",
    review_is_canonical: false,
    promotion_requires_governed_execution: true,
    promotion_relabels_transient_source: false,
    validated_knowledge_created: false,
    external_send_sign_publish_available: false,
  },
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderOutputs(projection: CompanyGeneratedOutputsProjection) {
  const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === "POST") {
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(JSON.stringify(projection), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(
    <LanguageProvider initialLanguage="ru">
      <CompanyGeneratedOutputs csrfToken="csrf" />
    </LanguageProvider>,
  );
  return fetchMock;
}

describe("P10.05 reviewed generated-output owner journey", () => {
  it("keeps review visibly transient, shows inherited handling, and exposes no send/sign/publish action", async () => {
    renderOutputs(baseProjection);
    expect(await screen.findByRole("heading", { name: "Документы на проверке" })).toBeTruthy();
    fireEvent.click(document.querySelector(".exec-list > details > summary")!);
    expect(screen.getAllByText("TransientOutput").length).toBeGreaterThan(0);
    expect(screen.getByText("company governed document generation")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Оставить черновиком" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Отклонить" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Запросить принятие" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /отправ/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /подпис/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /публи/i })).toBeNull();
  });

  it("records KeepTransient separately from the consequential promotion command", async () => {
    const fetchMock = renderOutputs(baseProjection);
    await screen.findByRole("heading", { name: "Документы на проверке" });
    fireEvent.click(document.querySelector(".exec-list > details > summary")!);
    fireEvent.click(screen.getByRole("button", { name: "Оставить черновиком" }));
    await waitFor(() => {
      const post = fetchMock.mock.calls.find((call) => call[1]?.method === "POST");
      expect(post).toBeTruthy();
      expect(String(post?.[0])).toContain("/review");
      expect(JSON.parse(String(post?.[1]?.body))).toEqual({ disposition: "KeepTransient" });
    });
  });

  it("shows final Governed Execution action only after an exact promotion request is ready", async () => {
    const requested: CompanyGeneratedOutputsProjection = {
      ...baseProjection,
      actions: { governed_promotion_available: true },
      items: [{
        ...baseProjection.items[0],
        review: {
          ...baseProjection.items[0].review,
          disposition: "PromotionRequested",
          document_title: "Reviewed Company Document",
          semantic_role: "company-project-document",
          updated_at: "2026-08-29T08:01:00Z",
          actor: "principal:owner@arvectum",
        },
        promotion_available: true,
      }],
    };
    renderOutputs(requested);
    await screen.findByRole("heading",{name:"Документы на проверке"});
    fireEvent.click(document.querySelector(".exec-list > details > summary")!);
    expect(await screen.findByRole("button", { name: "Подтвердить принятие" })).toBeTruthy();
    expect(screen.getByText(/сервер заново проверяет credential/i)).toBeTruthy();
  });
});
