import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CompanyAssetDiscovery } from "./CompanyAssetDiscovery";
import { fetchCompanyAssetContent } from "./f11Api";
import type { CompanyAssetLibraryItem, CompanyAssetLibraryProjection } from "./f11Types";
import { LanguageProvider } from "./i18n";

vi.mock("./f11Api", () => ({ fetchCompanyAssetContent: vi.fn() }));

function item(overrides: Partial<CompanyAssetLibraryItem> = {}): CompanyAssetLibraryItem {
  return {
    material_id: "material-current",
    version_id: "version-current",
    title: "Шаблон договора.docx",
    project_id: "PORT-002",
    semantic_role: "document-template",
    media_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    classification: "internal",
    purpose: "договоры компании",
    rights: "company-internal-use",
    retention_rule: "until-replaced",
    received_at: "2026-09-15T12:00:00Z",
    uploader: "principal:owner",
    content_sha256: "a".repeat(64),
    size_bytes: 128,
    predecessor_version_id: null,
    staging_state: "StagedNonCanonical",
    review: { state: "InReview", policy: { deletion_rule: "governed", permitted_reuse: ["company-internal"] }, reason: null, updated_at: "2026-09-15T12:01:00Z" },
    canonical: {
      material_id: "material-current", version_id: "version-current", document_subject: "document:current",
      document_version: "document-version:current", designation_subject: "asset:current", designation_version: "asset-version:current",
      event_version: "event-version:current", admitted_at: "2026-09-15T12:02:00Z", provenance_refs: ["source:current"], current: true,
    },
    lifecycle_view: "accepted",
    technical_identity_available: true,
    ...overrides,
  };
}

const superseded = item({
  material_id: "material-logo",
  version_id: "version-logo-v1",
  title: "Логотип 2025.png",
  project_id: "COMPANY",
  semantic_role: "logo",
  media_type: "image/png",
  purpose: "старый фирменный знак",
  canonical: {
    material_id: "material-logo", version_id: "version-logo-v1", document_subject: "document:logo",
    document_version: "document-version:logo-v1", designation_subject: "asset:logo", designation_version: "asset-version:logo-v1",
    event_version: "event-version:logo-v1", admitted_at: "2025-09-15T12:00:00Z", provenance_refs: ["source:logo-v1"], current: false,
  },
  lifecycle_view: "archive",
});

const rejected = item({
  material_id: "material-rejected",
  version_id: "version-rejected",
  title: "Не принятый файл.pdf",
  semantic_role: "source",
  media_type: "application/pdf",
  canonical: null,
  review: { state: "Rejected", policy: null, reason: "no", updated_at: "2026-09-15T12:00:00Z" },
  lifecycle_view: "archive",
});

const library: CompanyAssetLibraryProjection = {
  schema: "arvectum.workspace.company-asset-library/1",
  generated_at: "2026-09-15T13:00:00Z",
  product_contract: { id: "p9-11-f11-arvectum-company-workspace", version: "0.2.0", lifecycle: "Provisional" },
  views: { drafts: [], review: [], accepted: [item()], archive: [superseded, rejected] },
  actions: { governed_admission_available: true },
  scope: { organization_resolved_server_side: true, actor_resolved_server_side: true, cross_organization_access: false },
  governance: {
    workspace_is_authority_source: false, staging_is_canonical: false, review_state_is_canonical: false,
    canonical_admission_requires_governed_execution: true, generated_output_default: "TransientOutput", validated_knowledge_created: false,
  },
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("P10.09-A admitted asset discovery", () => {
  it("shows only admitted assets and filters by human-readable name, role, project, version, and lifecycle", () => {
    render(<LanguageProvider initialLanguage="ru"><CompanyAssetDiscovery data={library} projects={[{ id: "PORT-002", label: "Tender Agent" }]} onReuse={() => undefined} /></LanguageProvider>);
    expect(screen.getByRole("heading", { name: "Шаблон договора.docx" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Логотип 2025.png" })).toBeTruthy();
    expect(screen.queryByText("Не принятый файл.pdf")).toBeNull();
    expect(screen.getByText("Tender Agent")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Название или назначение"), { target: { value: "договор" } });
    expect(screen.getByRole("heading", { name: "Шаблон договора.docx" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Логотип 2025.png" })).toBeNull();

    fireEvent.change(screen.getByLabelText("Название или назначение"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Тип"), { target: { value: "logo" } });
    expect(screen.getByRole("heading", { name: "Логотип 2025.png" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Шаблон договора.docx" })).toBeNull();

    fireEvent.change(screen.getByLabelText("Тип"), { target: { value: "all" } });
    fireEvent.change(screen.getByLabelText("Версия"), { target: { value: "superseded" } });
    expect(screen.getByRole("heading", { name: "Логотип 2025.png" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Шаблон договора.docx" })).toBeNull();

    fireEvent.change(screen.getByLabelText("Версия"), { target: { value: "all" } });
    fireEvent.change(screen.getByLabelText("Состояние"), { target: { value: "accepted" } });
    expect(screen.getByRole("heading", { name: "Шаблон договора.docx" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Логотип 2025.png" })).toBeNull();
  });

  it("retrieves the exact admitted bytes with release-aware API and passes exact DOCX version to reuse", async () => {
    const reuse = vi.fn();
    const open = vi.fn(() => ({ location: { href: "" }, close: vi.fn() }));
    vi.stubGlobal("open", open);
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:p10-09") });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
    vi.mocked(fetchCompanyAssetContent).mockResolvedValue({ blob: new Blob(["asset"]), filename: "Шаблон договора.docx", mediaType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });

    render(<LanguageProvider initialLanguage="ru"><CompanyAssetDiscovery data={library} projects={[{ id: "PORT-002", label: "Tender Agent" }]} onReuse={reuse} /></LanguageProvider>);
    fireEvent.click(screen.getAllByRole("button", { name: "Открыть" })[0]);
    await waitFor(() => expect(fetchCompanyAssetContent).toHaveBeenCalledWith("material-current", "version-current", false));
    fireEvent.click(screen.getByRole("button", { name: "Использовать как шаблон" }));
    expect(reuse).toHaveBeenCalledWith(expect.objectContaining({ material_id: "material-current", version_id: "version-current" }));
  });
});
