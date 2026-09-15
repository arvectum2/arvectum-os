export type NavigationItem = {
  id: string;
  label: string;
  href: string;
  availability: "available" | `planned-${string}`;
};

export type WorkspaceContext = {
  schema: "arvectum.workspace.shell-context/1";
  release: {
    id: string;
    app_api_contract: string;
    classification: "bounded-internal-provisional";
    public_api: false;
  };
  organization: {
    label: string;
    scope_resolved_server_side: true;
  };
  actor: {
    label: string;
    attributable: true;
    scope_resolved_server_side: true;
    authentication_source: string;
  };
  session: {
    csrf_token: string;
    bounded: true;
    revocable: true;
    authority_provided: false;
  };
  navigation: NavigationItem[];
  data_governance: {
    protected_read_revalidated: true;
    response_minimized: "shell-context-only";
    canonical_state_in_browser: false;
  };
};

export type AttentionKind =
  | "waiting-approval"
  | "waiting-input"
  | "reconciliation-required"
  | "guarded-action-failed"
  | "recoverable-system-condition"
  | "recent-outcome"
  | "informational";

export type AttentionGroup =
  | "decision-required"
  | "blocked-failed"
  | "reconciliation-required"
  | "recent-outcome"
  | "informational";

export type AttentionUrgency = "high" | "medium" | "low";
export type ProjectionFreshness = "fresh" | "stale" | "degraded";

export type AttentionItem = {
  id: string;
  kind: AttentionKind;
  group: AttentionGroup;
  urgency: AttentionUrgency;
  title: string;
  reason: string;
  source: string;
  next_step: string;
  evidence_mode: "live" | "scenario";
  observed_at: string | null;
  open_href: string;
  interaction: "inspect-only";
  technical_evidence_available: boolean;
  authority_provided: false;
};

export type MyWorkProjection = {
  schema: "arvectum.workspace.my-work/1";
  generated_at: string;
  projection: {
    derived: true;
    canonical_authority: false;
    organizational_authority_provided: false;
    consequential_action_available: false;
    visibility_implies_permission: false;
  };
  scope: {
    organization_resolved_server_side: true;
    actor_resolved_server_side: true;
    denied_item_counts_exposed: false;
  };
  health: {
    state: ProjectionFreshness;
    code: string;
    message: string;
    observed_at: string;
    heartbeat_age_seconds: number | null;
  };
  items: AttentionItem[];
};

export type DiscoveryKind = "record" | "document" | "knowledge" | "execution";
export type DiscoveryFreshness = "fresh" | "degraded";

export type DiscoveryResult = {
  id: string;
  kind: DiscoveryKind;
  semantic_role: string;
  title: string;
  summary: string;
  source: string;
  authority_mode: string;
  state: string;
  knowledge_role: string | null;
  open_href: string;
  interaction: "inspect-only";
  authority_provided: false;
};

export type DiscoveryProjection = {
  schema: "arvectum.workspace.discovery/1";
  generated_at: string;
  query: string;
  kind_filter: DiscoveryKind | null;
  projection: {
    derived: true;
    canonical_authority: false;
    organizational_authority_provided: false;
    consequential_action_available: false;
    search_result_is_authority: false;
  };
  scope: {
    organization_resolved_server_side: true;
    actor_resolved_server_side: true;
    denied_result_counts_exposed: false;
    protected_snippets_minimized: true;
  };
  health: {
    state: DiscoveryFreshness;
    code: string;
    message: string;
    observed_at: string;
  };
  results: DiscoveryResult[];
};

export type ObjectContext = {
  schema: "arvectum.workspace.object-context/1";
  id: string;
  kind: DiscoveryKind;
  semantic_role: string;
  title: string;
  summary: string;
  source: string;
  knowledge_role: string | null;
  authority: {
    mode: string;
    scope: string;
    authoritative_source: string;
    organizational_authority_provided: false;
    visibility_implies_permission: false;
  };
  state: {
    lifecycle: string | null;
    validation: string | null;
    classification: string;
  };
  context: {
    meaning: string;
    process: string;
    next_step: string;
    interaction: "inspect-only";
    consequential_action_available: false;
  };
  technical: {
    subject_identity: string;
    version_identity: string;
    schema_version: string;
    source_release_sha: string;
    provenance_refs: string[];
    related_execution_subject: string | null;
    related_execution_version: string | null;
    related_event_version: string | null;
    related_checkpoint: string | null;
  };
  governed_preflight: {
    outcome: string | null;
    waiting_gates: string[];
    authority_provided: false;
  } | null;
  projection: {
    presentation_authority: "non-authoritative";
    current_source_revalidated: true;
    exact_version_exposed_on_demand: true;
  };
};

export type GovernedDecision = {
  name: "Authorization" | "Organizational Authority" | "Data Governance" | "Consequential Approval";
  state: string;
  basis: string;
};

export type GovernedExperienceProjection = {
  schema: "arvectum.workspace.governed-experience/1";
  generated_at: string;
  presentation: {
    title: string;
    summary: string;
    source: string;
    authority_mode: string;
    authority_scope: string;
    validation_status: string;
  };
  execution: {
    status: string;
    meaning: string;
    waiting_decisions: string[];
    technical_identity_available: true;
  };
  decisions: GovernedDecision[];
  action: {
    kind: "governed-preflight";
    label: string;
    available: boolean;
    consequential: false;
    canonical_mutation_requested: false;
    external_effect_requested: false;
    authority_provided: false;
    explanation: string;
  };
  technical: {
    release_sha: string;
    source_subject: string;
    source_version: string;
    execution_subject: string;
    execution_version: string;
    event_version: string;
    checkpoint_id: string;
    provenance_refs: string[];
  };
  scope: {
    organization_resolved_server_side: true;
    actor_resolved_server_side: true;
    current_access_revalidated: true;
    organizational_authority_provided: false;
    visibility_implies_permission: false;
  };
};

export type GovernedPreflightResult = {
  schema: "arvectum.workspace.governed-preflight-result/1";
  recorded_at: string;
  outcome: string;
  status_text: string;
  canonical_mutation_requested: false;
  canonical_mutation_performed: false;
  external_effect_requested: false;
  external_effect_performed: false;
  organizational_authority_provided: false;
  consequential_approval_provided: false;
  evidence: {
    classification: "owner-local non-canonical proof evidence";
    sha256: string;
  };
};

export type ProductSurfaceContext = {
  id: string;
  label: string;
  ownership: "product-owned";
  repository: string;
  product_contract: {
    id: string;
    version: string;
    lifecycle: "Provisional";
  };
  contour: {
    id: string;
    operating_scope: string;
    status: string;
    summary: string;
    shared_dependencies: string[];
    source_authority: string;
  };
  interaction: {
    kind: "inspect-product-context";
    product_specific_work_stays_product_owned: true;
    authority_provided: false;
    canonical_mutation_available: false;
    external_effect_available: false;
  };
  technical: {
    product_release_sha: string | null;
    evidence_refs: string[];
  };
};

export type ProductCompositionProjection = {
  schema: "arvectum.workspace.product-composition/1";
  generated_at: string;
  projection: {
    derived: true;
    canonical_authority: false;
    product_semantics_owned_by_platform: false;
    organizational_authority_provided: false;
    cross_product_business_relationship_inferred: false;
  };
  scope: {
    organization_resolved_server_side: true;
    actor_resolved_server_side: true;
    current_access_revalidated: true;
    switching_products_broadens_authorization: false;
  };
  products: ProductSurfaceContext[];
};

export type CopilotClaimKind = "source-context" | "synthesis" | "uncertainty" | "unavailable-evidence";

export type CopilotClaim = {
  kind: CopilotClaimKind;
  text: string;
  source_refs: string[];
};

export type CopilotSource = {
  id: string;
  label: string;
  summary: string;
  authority: string;
  freshness: string;
  semantic_role: string;
  knowledge_role: string | null;
  open_href: string;
  inspectable_in_workspace: true;
};

export type CopilotAnswer = {
  schema: "arvectum.workspace.copilot-answer/2";
  generated_at: string;
  claims: CopilotClaim[];
  sources: CopilotSource[];
  model: {
    provider: string;
    model: string;
    used: boolean;
    failure: string | null;
    output_role: "synthesis-only" | "not-used";
    raw_prompt_retained: false;
    chain_of_thought_retained: false;
  };
  scope: {
    organization_resolved_server_side: true;
    actor_resolved_server_side: true;
    current_access_revalidated: true;
    retrieval_authorization_reused_from_workspace: true;
    cross_organization_retrieval: false;
  };
  semantics: {
    source_context_distinct_from_synthesis: true;
    unvalidated_knowledge_not_presented_as_fact: true;
    uncertainty_explicit: true;
    unavailable_evidence_explicit: true;
    observation_memory_candidate_not_flattened_to_knowledge: true;
  };
  generation: {
    transient_output: true;
    validated_knowledge: false;
    canonical_state_changed: false;
    external_effect_performed: false;
    organizational_authority_provided: false;
    consequential_approval_provided: false;
    question_persisted: false;
  };
  follow_up: {
    kind: "inspect-evidence-first";
    label: string;
    href: string | null;
    direct_consequential_action: false;
    routes_to_governed_execution: false;
    context_bound_governed_continuation_required: true;
  };
};

export type OrganizationLaneState = "ready" | "degraded" | "unavailable";

export type OrganizationNavItem = {
  id: string;
  kind: "product" | "project-lens" | "knowledge" | "work";
  label: string;
  summary: string;
  href: string;
  source: string;
  authority: string;
  ownership: string;
  state: string;
  provenance_available: boolean;
  semantic_note: string | null;
  canonical_project_record: false;
  interaction: "navigate-and-inspect";
  authority_provided: false;
  consequential_action_available: false;
};

export type OrganizationLane = {
  id: "products" | "projects" | "knowledge" | "work";
  label: string;
  summary: string;
  state: OrganizationLaneState;
  source_boundary: string;
  items: OrganizationNavItem[];
};

export type OrganizationCompositionProjection = {
  schema: "arvectum.workspace.organization-composition/1";
  generated_at: string;
  health: { state: "ready" | "degraded" };
  projection: {
    derived: true;
    canonical_authority: false;
    organizational_authority_provided: false;
    company_semantics_promoted_to_kernel: false;
    project_lenses_are_canonical_records: false;
    source_projection_authority_preserved: true;
    canonical_mutation_available: false;
    external_effect_available: false;
  };
  scope: {
    organization_resolved_server_side: true;
    actor_resolved_server_side: true;
    current_access_revalidated: true;
    cross_organization_aggregation: false;
    denied_source_counts_exposed: false;
  };
  lanes: OrganizationLane[];
};

export type ActionableWorkFreshness = "fresh" | "stale" | "unknown";

export type ActionableWorkItem = {
  id: string;
  title: string;
  context: string;
  attention_reason: string;
  source: {
    kind: "product" | "company";
    id: string;
    label: string;
    request_ref: string;
    authority: string;
    state: string;
    freshness: ActionableWorkFreshness;
    observed_at: string;
    product_contract: {
      id: string;
      version: string;
      lifecycle: "Provisional" | "Stable";
    };
  };
  next_steps: string[];
  governed_execution: {
    preflight_state: string;
    current_gate_revalidation_required_for_effect: true;
    consequential_action_available: false;
    organizational_authority_provided: false;
    consequential_approval_provided: false;
  };
  entry: {
    kind: "no-side-effect-context-entry";
    available: boolean;
    href: string | null;
    consequential: false;
    canonical_mutation_requested: false;
    external_effect_requested: false;
    authority_provided: false;
    executes_product_operation: false;
  };
  technical: {
    provenance_refs: string[];
    exact_source_request_ref_available: true;
  };
};

export type ActionableWorkProjection = {
  schema: "arvectum.workspace.actionable-work/1";
  generated_at: string;
  projection: {
    derived: true;
    canonical_authority: false;
    creates_requests: false;
    universal_task_primitive: false;
    product_semantics_owned_by_platform: false;
    organizational_authority_provided: false;
    urgency_inferred: false;
    owner_responsibility_inferred: false;
    approval_requirement_inferred: false;
    action_availability_inferred: false;
  };
  scope: {
    organization_resolved_server_side: true;
    actor_resolved_server_side: true;
    current_workspace_access_revalidated: true;
    denied_request_counts_exposed: false;
  };
  items: ActionableWorkItem[];
};
