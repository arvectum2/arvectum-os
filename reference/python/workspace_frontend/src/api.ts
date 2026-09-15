import type {
  ActionableWorkProjection,
  CopilotAnswer,
  DiscoveryKind,
  DiscoveryProjection,
  GovernedExperienceProjection,
  GovernedPreflightResult,
  MyWorkProjection,
  ObjectContext,
  OrganizationCompositionProjection,
  ProductCompositionProjection,
  WorkspaceContext,
} from "./types";
import type {
  DogfoodingBacklog,
  DogfoodingDisposition,
  DogfoodingObservation,
  DogfoodingObservationInput,
} from "./dogfoodingTypes";

export class WorkspaceApiError extends Error {
  readonly code: string;
  readonly reloadRequired: boolean;

  constructor(code: string, reloadRequired = false) {
    super(code);
    this.name = "WorkspaceApiError";
    this.code = code;
    this.reloadRequired = reloadRequired;
  }
}

const RELEASE_ID = __ARVECTUM_WORKSPACE_RELEASE__;

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-Arvectum-Workspace-Release", RELEASE_ID);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...init, headers, credentials: "same-origin" });
  if (!response.ok) {
    let payload: { code?: string; detail?: string; reload_required?: boolean } = {};
    try {
      payload = await response.json();
    } catch {
      // Keep a minimized browser error when the response is not JSON.
    }
    throw new WorkspaceApiError(
      payload.code ?? payload.detail ?? `HTTP_${response.status}`,
      Boolean(payload.reload_required),
    );
  }
  return (await response.json()) as T;
}

export async function loadWorkspaceContext(): Promise<WorkspaceContext> {
  try {
    return await request<WorkspaceContext>("/api/app/v1/context");
  } catch (error) {
    if (error instanceof WorkspaceApiError && error.code === "SESSION_REQUIRED") {
      return request<WorkspaceContext>("/api/app/v1/session/bootstrap", { method: "POST" });
    }
    throw error;
  }
}

export async function loadMyWork(): Promise<MyWorkProjection> {
  return request<MyWorkProjection>("/api/app/v1/my-work");
}

export async function loadActionableWork(): Promise<ActionableWorkProjection> {
  return request<ActionableWorkProjection>("/api/app/v1/actionable-work");
}

export async function loadDiscovery(query = "", kind?: DiscoveryKind): Promise<DiscoveryProjection> {
  const params = new URLSearchParams();
  if (query.trim()) params.set("q", query.trim());
  if (kind) params.set("kind", kind);
  const suffix = params.size ? `?${params.toString()}` : "";
  return request<DiscoveryProjection>(`/api/app/v1/discovery${suffix}`);
}

export async function loadObjectContext(objectId: string): Promise<ObjectContext> {
  return request<ObjectContext>(`/api/app/v1/objects/${encodeURIComponent(objectId)}`);
}

export async function loadProductComposition(): Promise<ProductCompositionProjection> {
  return request<ProductCompositionProjection>("/api/app/v1/products");
}

export async function loadOrganizationComposition(): Promise<OrganizationCompositionProjection> {
  return request<OrganizationCompositionProjection>("/api/app/v1/organization");
}

export async function loadDogfoodingBacklog(): Promise<DogfoodingBacklog> {
  return request<DogfoodingBacklog>("/api/app/v1/dogfooding");
}

export async function recordDogfoodingObservation(
  input: DogfoodingObservationInput,
  csrfToken: string,
): Promise<DogfoodingObservation> {
  return request<DogfoodingObservation>("/api/app/v1/dogfooding/observations", {
    method: "POST",
    headers: { "X-Arvectum-CSRF": csrfToken },
    body: JSON.stringify(input),
  });
}

export async function dispositionDogfoodingObservation(
  observationId: string,
  disposition: DogfoodingDisposition,
  rationale: string,
  csrfToken: string,
): Promise<DogfoodingObservation> {
  return request<DogfoodingObservation>(
    `/api/app/v1/dogfooding/observations/${encodeURIComponent(observationId)}/disposition`,
    {
      method: "POST",
      headers: { "X-Arvectum-CSRF": csrfToken },
      body: JSON.stringify({ disposition, rationale }),
    },
  );
}

export async function askCopilot(question: string, csrfToken: string): Promise<CopilotAnswer> {
  return request<CopilotAnswer>("/api/app/v1/copilot/ask", {
    method: "POST",
    headers: { "X-Arvectum-CSRF": csrfToken },
    body: JSON.stringify({ question }),
  });
}

export async function loadGovernedExperience(): Promise<GovernedExperienceProjection> {
  return request<GovernedExperienceProjection>("/api/app/v1/governed");
}

export async function runGovernedPreflight(csrfToken: string): Promise<GovernedPreflightResult> {
  return request<GovernedPreflightResult>("/api/app/v1/governed/preflight", {
    method: "POST",
    headers: { "X-Arvectum-CSRF": csrfToken },
  });
}

export async function logoutWorkspace(csrfToken: string): Promise<void> {
  await request<{ status: string }>("/api/app/v1/session/logout", {
    method: "POST",
    headers: { "X-Arvectum-CSRF": csrfToken },
  });
}

export const workspaceReleaseId = RELEASE_ID;
