export type CompanyRoadmapSource = {
  repository: string;
  path: string;
  commit_sha: string;
  content_sha256: string;
  fetched_at: string;
  freshness: string;
  adapter: string;
};

export type CompanyProjectCard = {
  id: string;
  label: string;
  kind: string;
  disposition: string;
  repository: string | null;
  roadmap_path: string | null;
  execution_targets: string[];
  authority_mode: "External Reference";
  projection_authority: "non-authoritative";
  state: "current-source-backed" | "cached-source-backed" | "stale-cache" | "reconciliation-required" | "unavailable";
  message: string;
  source: CompanyRoadmapSource | null;
  roadmap: {
    status: string | null;
    version: string | null;
    source_updated: string | null;
    done: string[];
    current: string[];
    branches: string[];
    unlocked: string[];
    blocked: string[];
  };
};

export type CompanyPortfolioProjection = {
  schema: "arvectum.workspace.company-portfolio/1";
  generated_at: string;
  product_contract: { id: "P9.11-F11"; version: "0.1.0"; lifecycle: "Provisional" };
  projection: {
    derived: true;
    canonical_authority: false;
    read_only: true;
    roadmap_write_available: false;
    remote_execution_available: false;
    chat_or_model_memory_used_as_authority: false;
    visibility_implies_permission: false;
  };
  scope: {
    organization_resolved_server_side: true;
    actor_resolved_server_side: true;
    cross_organization_aggregation: false;
  };
  projects: CompanyProjectCard[];
};

export type StagedMaterialVersion = {
  material_id: string;
  version_id: string;
  predecessor_version_id: string | null;
  organization: string;
  project_id: string;
  filename: string;
  media_type: string;
  semantic_role: string;
  classification: string;
  purpose: string;
  rights: string;
  retention_rule: string;
  uploader: string;
  received_at: string;
  content_sha256: string;
  size_bytes: number;
  state: "StagedNonCanonical";
  canonical_authority: false;
  validated_knowledge: false;
};

export type StagedMaterial = {
  material_id: string;
  latest_version_id: string;
  versions: StagedMaterialVersion[];
};

export type CompanyMaterialsProjection = {
  schema: "arvectum.workspace.company-materials/1";
  generated_at: string;
  product_contract: { id: "P9.11-F11"; version: "0.1.0"; lifecycle: "Provisional" };
  scope: {
    organization_resolved_server_side: true;
    actor_resolved_server_side: true;
    cross_organization_access: false;
  };
  materials: StagedMaterial[];
  governance: {
    state: "StagedNonCanonical";
    canonical_admission_available: false;
    canonical_state_changed: false;
    organizational_authority_provided_by_upload: false;
    validated_knowledge_created: false;
    reason: string;
  };
};

export type CompanyAssetReview = {
  state: "Draft" | "InReview" | "Rejected";
  policy: null | {
    deletion_rule: string;
    permitted_reuse: string[];
  };
  reason: string | null;
  updated_at: string | null;
  actor?: string;
  canonical_authority?: false;
};

export type AdmittedCompanyAsset = {
  material_id: string;
  version_id: string;
  document_subject: string;
  document_version: string;
  designation_subject: string;
  designation_version: string;
  event_version: string;
  admitted_at: string;
  provenance_refs: string[];
  current: boolean;
};

export type CompanyAssetLibraryItem = {
  material_id: string;
  version_id: string;
  title: string;
  project_id: string;
  semantic_role: string;
  media_type: string;
  classification: string;
  purpose: string;
  rights: string;
  retention_rule: string;
  received_at: string;
  uploader: string;
  content_sha256: string;
  size_bytes: number;
  predecessor_version_id: string | null;
  staging_state: "StagedNonCanonical";
  review: CompanyAssetReview;
  canonical: AdmittedCompanyAsset | null;
  lifecycle_view: "drafts" | "review" | "accepted" | "archive";
  technical_identity_available: true;
};

export type CompanyAssetLibraryProjection = {
  schema: "arvectum.workspace.company-asset-library/1";
  generated_at: string;
  product_contract: {
    id: "p9-11-f11-arvectum-company-workspace";
    version: "0.2.0";
    lifecycle: "Provisional";
  };
  views: {
    drafts: CompanyAssetLibraryItem[];
    review: CompanyAssetLibraryItem[];
    accepted: CompanyAssetLibraryItem[];
    archive: CompanyAssetLibraryItem[];
  };
  actions: {
    governed_admission_available: boolean;
  };
  scope: {
    organization_resolved_server_side: true;
    actor_resolved_server_side: true;
    cross_organization_access: false;
  };
  governance: {
    workspace_is_authority_source: false;
    staging_is_canonical: false;
    review_state_is_canonical: false;
    canonical_admission_requires_governed_execution: true;
    generated_output_default: "TransientOutput";
    validated_knowledge_created: false;
  };
};

export type CompanyAssetLibraryExport = {
  schema: "arvectum.workspace.company-asset-library-export/1";
  generated_at: string;
  organization: string;
  items: CompanyAssetLibraryItem[];
  bounded: true;
  limit: number;
  canonical_authority: false;
};

export type GeneratedCompanyOutput = {
  schema: "arvectum.workspace.company-generated-output/1";
  output: {
    output_id: string;
    state: "TransientOutput";
    organization: string;
    project_id: string;
    created_at: string;
    created_by: string;
    source_material_id: string;
    source_version_id: string;
    source_sha256: string;
    generation_profile?: string;
    generation_input_digest?: string;
    input_assets?: CompanyGenerationAssetInputEvidence[];
    output_sha256: string;
    media_type: string;
    filename: string;
    canonical_authority: false;
    validated_knowledge: false;
    download_href: string;
  };
  governance: {
    generated_artifact_state: "TransientOutput";
    canonical_state_changed: false;
    exact_source_version_pinned: true;
    source_admitted_company_asset?: true;
    source_document_version?: string;
    source_designation_version?: string;
    all_generation_inputs_exact_admitted?: true;
    generation_input_count?: number;
  };
};

export type CompanyGenerationAssetInput = {
  material_id: string;
  version_id: string;
  use_as: "brand" | "source" | "reference";
};

export type CompanyGenerationAssetInputEvidence = CompanyGenerationAssetInput & {
  application: "embedded-image" | "text-included" | "pinned-reference";
  content_sha256: string;
  title: string;
  media_type: string;
  semantic_role: string;
  document_version: string;
  designation_version: string;
  event_version: string;
  provenance_refs: string[];
};
