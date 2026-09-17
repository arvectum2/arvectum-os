import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CompanyMaterials } from "./CompanyMaterials";
import { LanguageProvider } from "./i18n";
import type {
  CompanyAssetLibraryItem,
  CompanyAssetLibraryProjection,
  CompanyPortfolioProjection,
  GeneratedCompanyOutput,
} from "./f11Types";

const DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

const portfolio: CompanyPortfolioProjection = {
  schema: "arvectum.workspace.company-portfolio/1",
  generated_at: "2026-08-26T20:00:00Z",
  product_contract: { id: "P9.11-F11", version: "0.1.0", lifecycle: "Provisional" },
  projection: {
    derived: true, canonical_authority: false, read_only: true,
    roadmap_write_available: false, remote_execution_available: false,
    chat_or_model_memory_used_as_authority: false, visibility_implies_permission: false,
  },
  scope: { organization_resolved_server_side: true, actor_resolved_server_side: true, cross_organization_aggregation: false },
  projects: [],
};

const admittedTemplate: CompanyAssetLibraryItem = {
  material_id: "MAT-template0001",
  version_id: "MV-template00000001",
  predecessor_version_id: null,
  title: "Arvectum-template.docx",
  project_id: "PORT-003",
  media_type: DOCX,
  semantic_role: "document-template",
  classification: "internal",
  purpose: "standard document template",
  rights: "company-internal-use",
  retention_rule: "until-replaced-or-explicit-deletion",
  uploader: "principal:owner@arvectum",
  received_at: "2026-08-26T20:00:00Z",
  content_sha256: "a".repeat(64),
  size_bytes: 1024,
  staging_state: "StagedNonCanonical",
  review: {
    state: "InReview",
    policy: { deletion_rule: "governed-retention", permitted_reuse: ["company-document-generation"] },
    reason: null,
    updated_at: "2026-08-26T20:00:30Z",
    canonical_authority: false,
  },
  canonical: {
    material_id: "MAT-template0001",
    version_id: "MV-template00000001",
    document_subject: "document:org:template",
    document_version: "document-version:org:template-v1",
    designation_subject: "organizational-asset:org:template",
    designation_version: "organizational-asset-version:org:template-v1",
    event_version: "event-version:org:template-v1",
    admitted_at: "2026-08-26T20:00:40Z",
    provenance_refs: ["staged:MAT-template0001", "staged-version:MV-template00000001"],
    current: true,
  },
  lifecycle_view: "accepted",
  technical_identity_available: true,
};


const admittedLogo: CompanyAssetLibraryItem = {
  ...admittedTemplate,
  material_id: "MAT-logo000001",
  version_id: "MV-logo0000000001",
  title: "Arvectum-logo.png",
  project_id: "COMPANY",
  media_type: "image/png",
  semantic_role: "logo",
  purpose: "current Company logo",
  content_sha256: "c".repeat(64),
  canonical: {
    ...admittedTemplate.canonical!,
    material_id: "MAT-logo000001",
    version_id: "MV-logo0000000001",
    document_subject: "document:org:logo",
    document_version: "document-version:org:logo-v1",
    designation_subject: "organizational-asset:org:logo",
    designation_version: "organizational-asset-version:org:logo-v1",
    event_version: "event-version:org:logo-v1",
  },
};

const admittedSource: CompanyAssetLibraryItem = {
  ...admittedTemplate,
  material_id: "MAT-source0001",
  version_id: "MV-source00000001",
  title: "Approved-facts.md",
  project_id: "COMPANY",
  media_type: "text/markdown",
  semantic_role: "source",
  purpose: "approved source material",
  content_sha256: "d".repeat(64),
  canonical: {
    ...admittedTemplate.canonical!,
    material_id: "MAT-source0001",
    version_id: "MV-source00000001",
    document_subject: "document:org:source",
    document_version: "document-version:org:source-v1",
    designation_subject: "organizational-asset:org:source",
    designation_version: "organizational-asset-version:org:source-v1",
    event_version: "event-version:org:source-v1",
  },
};

const draftSource: CompanyAssetLibraryItem = {
  ...admittedSource,
  material_id: "MAT-draftsource01",
  version_id: "MV-draftsource0001",
  title: "Draft-company-source.md",
  canonical: null,
  lifecycle_view: "drafts",
  review: { state: "Draft", policy: { deletion_rule: "existing-retention", permitted_reuse: ["company-internal-document-generation"] }, reason: null, updated_at: null, canonical_authority: false },
};

const emptyLibrary: CompanyAssetLibraryProjection = {
  schema: "arvectum.workspace.company-asset-library/1",
  generated_at: "2026-08-26T20:00:00Z",
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

const libraryWithTemplate: CompanyAssetLibraryProjection = {
  ...emptyLibrary,
  views: { ...emptyLibrary.views, accepted: [admittedTemplate] },
};

const libraryWithGenerationAssets: CompanyAssetLibraryProjection = {
  ...emptyLibrary,
  views: { ...emptyLibrary.views, accepted: [admittedTemplate, admittedLogo, admittedSource] },
};

const generated: GeneratedCompanyOutput = {
  schema: "arvectum.workspace.company-generated-output/1",
  output: {
    output_id: "OUT-generated0001", state: "TransientOutput", organization: "organization:arvectum@platform",
    project_id: "PORT-003", created_at: "2026-08-26T20:01:00Z", created_by: "principal:owner@arvectum",
    source_material_id: admittedTemplate.material_id, source_version_id: admittedTemplate.version_id,
    source_sha256: admittedTemplate.content_sha256,
    generation_profile: "company-docx-asset-aware-v1",
    generation_input_digest: "e".repeat(64),
    input_assets: [
      { material_id: admittedLogo.material_id, version_id: admittedLogo.version_id, use_as: "brand", application: "embedded-image", content_sha256: admittedLogo.content_sha256, title: admittedLogo.title, media_type: admittedLogo.media_type, semantic_role: admittedLogo.semantic_role, document_version: admittedLogo.canonical!.document_version, designation_version: admittedLogo.canonical!.designation_version, event_version: admittedLogo.canonical!.event_version, provenance_refs: admittedLogo.canonical!.provenance_refs },
      { material_id: admittedSource.material_id, version_id: admittedSource.version_id, use_as: "source", application: "text-included", content_sha256: admittedSource.content_sha256, title: admittedSource.title, media_type: admittedSource.media_type, semantic_role: admittedSource.semantic_role, document_version: admittedSource.canonical!.document_version, designation_version: admittedSource.canonical!.designation_version, event_version: admittedSource.canonical!.event_version, provenance_refs: admittedSource.canonical!.provenance_refs },
    ],
    output_sha256: "b".repeat(64), media_type: DOCX,
    filename: "generated-OUT-generated0001.docx", canonical_authority: false, validated_knowledge: false,
    download_href: "/api/app/v1/company-materials/outputs/OUT-generated0001/download",
  },
  governance: {
    generated_artifact_state: "TransientOutput", canonical_state_changed: false, exact_source_version_pinned: true,
    source_admitted_company_asset: true,
    source_document_version: admittedTemplate.canonical!.document_version,
    source_designation_version: admittedTemplate.canonical!.designation_version,
    all_generation_inputs_exact_admitted: true, generation_input_count: 3,
  },
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderMaterials(library: CompanyAssetLibraryProjection) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("company/portfolio")) {
      return new Response(JSON.stringify(portfolio), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    if (url.endsWith("/company-materials/generate") && init?.method === "POST") {
      return new Response(JSON.stringify(generated), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    return new Response(JSON.stringify(library), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<LanguageProvider initialLanguage="ru"><CompanyMaterials csrfToken="csrf" /></LanguageProvider>);
  return fetchMock;
}

describe("P10.04 Company Asset owner journey", () => {
  it("uses a fixed material-type list with an explicit Other escape hatch", async () => {
    renderMaterials(emptyLibrary);
    expect(await screen.findByRole("heading", { name: "Материалы компании" })).toBeTruthy();
    const select = screen.getByLabelText("Тип материала") as HTMLSelectElement;
    expect(Array.from(select.options).map((option) => option.textContent)).toEqual([
      "Выберите тип", "Шаблон документа", "Брендбук", "Логотип", "Исходный материал", "Другое",
    ]);
    fireEvent.change(select, { target: { value: "other" } });
    expect(screen.getByLabelText("Другой тип")).toBeTruthy();
  });

  it("lets the owner explicitly enable exact-version Arvectum AI reuse without knowing the policy token", async () => {
    const library: CompanyAssetLibraryProjection = {
      ...emptyLibrary,
      views: { ...emptyLibrary.views, drafts: [draftSource] },
    };
    const fetchMock = renderMaterials(library);
    expect(await screen.findByRole("heading", { name: "Материалы компании" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Когда материал можно удалить"), { target: { value: "governed-retention" } });
    const aiReuse = screen.getByLabelText("Разрешить Arvectum AI использовать эту версию как источник");
    expect((aiReuse as HTMLInputElement).checked).toBe(false);
    const documentReuse = screen.getByLabelText("Разрешить использовать материал при создании документов") as HTMLInputElement;
    expect(documentReuse.checked).toBe(true);
    fireEvent.click(aiReuse);
    expect((aiReuse as HTMLInputElement).checked).toBe(true);
    fireEvent.click(aiReuse);
    expect((aiReuse as HTMLInputElement).checked).toBe(false);
    expect(documentReuse.checked).toBe(true);
    fireEvent.click(aiReuse);
    fireEvent.click(screen.getByRole("button", { name: "Проверить условия" }));

    await vi.waitFor(() => {
      const call = fetchMock.mock.calls.find(([input, init]) => String(input).endsWith("/review") && init?.method === "POST");
      expect(call).toBeTruthy();
      const body = JSON.parse(String(call?.[1]?.body));
      expect(body).toEqual({
        deletion_rule: "governed-retention",
        permitted_reuse: ["company-internal-document-generation", "company-internal-ai-grounding"],
      });
    });
  });

  it("keeps the ordinary draft view human-readable while preserving technical details on demand", async () => {
    const library: CompanyAssetLibraryProjection = {
      ...emptyLibrary,
      views: { ...emptyLibrary.views, drafts: [draftSource] },
    };
    renderMaterials(library);
    expect(await screen.findByRole("heading", { name: "Draft-company-source.md" })).toBeTruthy();
    expect(screen.getByText("Черновик")).toBeTruthy();
    expect(screen.getAllByText("Исходный материал").length).toBeGreaterThan(0);
    expect(screen.getByText("Для использования внутри компании")).toBeTruthy();
    expect(screen.getAllByText("До замены или явного удаления").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Подготовить к использованию" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Проверить условия" })).toBeTruthy();
    const details = screen.getAllByText("Технические сведения")[0].closest("details") as HTMLDetailsElement;
    expect(details.open).toBe(false);
    expect(screen.queryByText("Staged · черновик")).toBeNull();
    expect(screen.queryByText(/Product Contract/)).toBeNull();
    expect(screen.queryByText(/server-side revalidation/)).toBeNull();
  });

  it("selects exact current template, brand and source assets without requiring technical IDs", async () => {
    const fetchMock = renderMaterials(libraryWithGenerationAssets);
    expect(await screen.findByRole("heading", { name: "Материалы компании" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Шаблон"), {
      target: { value: `${admittedTemplate.material_id}::${admittedTemplate.version_id}` },
    });
    fireEvent.click(screen.getByLabelText(/Arvectum-logo\.png/));
    fireEvent.click(screen.getByLabelText(/Approved-facts\.md/));
    fireEvent.change(screen.getByLabelText("Заголовок"), { target: { value: "Тестовый документ" } });
    fireEvent.change(screen.getByLabelText("Текст"), { target: { value: "Проверка owner journey" } });
    fireEvent.change(screen.getByLabelText("Дата"), { target: { value: "26.08.2026" } });
    fireEvent.click(screen.getByRole("button", { name: "Создать документ" }));
    expect(await screen.findByText("Документ готов")).toBeTruthy();
    expect(screen.getByText("Arvectum-logo.png · встроен")).toBeTruthy();
    expect(screen.getByText("Approved-facts.md · текст включён")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Скачать DOCX" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Скачать DOCX" })).toBeNull();

    const call = fetchMock.mock.calls.find(([input, init]) => String(input).endsWith("/company-materials/generate") && init?.method === "POST");
    expect(call).toBeTruthy();
    const body = JSON.parse(String(call?.[1]?.body));
    expect(body.asset_inputs).toEqual([
      { material_id: admittedLogo.material_id, version_id: admittedLogo.version_id, use_as: "brand" },
      { material_id: admittedSource.material_id, version_id: admittedSource.version_id, use_as: "source" },
    ]);
  });
});
