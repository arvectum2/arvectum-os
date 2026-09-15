import type {
  AdmittedCompanyAsset,
  CompanyAssetLibraryExport,
  CompanyAssetLibraryProjection,
  CompanyMaterialsProjection,
  CompanyPortfolioProjection,
  GeneratedCompanyOutput,
  StagedMaterialVersion,
} from "./f11Types";

const RELEASE_ID = __ARVECTUM_WORKSPACE_RELEASE__;
const RELEASE_HEADER = "X-Arvectum-Workspace-Release";

async function responseError(response: Response): Promise<Error> {
  let code = `HTTP_${response.status}`;
  try {
    const payload = await response.json() as { code?: string; detail?: string };
    code = payload.code ?? payload.detail ?? code;
  } catch {
    // Keep a minimized error when the server did not return JSON.
  }
  return new Error(code);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set(RELEASE_HEADER, RELEASE_ID);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...init, headers, credentials: "same-origin" });
  if (!response.ok) throw await responseError(response);
  return await response.json() as T;
}

function downloadFilename(disposition: string | null, fallback = "generated-arvectum-document.docx"): string {
  if (!disposition) return fallback;
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  if (encoded) {
    try {
      return decodeURIComponent(encoded);
    } catch {
      // Fall back to the ordinary filename parameter below.
    }
  }
  const quoted = disposition.match(/filename="([^"]+)"/i)?.[1];
  const plain = disposition.match(/filename=([^;]+)/i)?.[1]?.trim();
  return quoted ?? plain ?? fallback;
}

function assetPath(materialId: string, versionId: string, action: string): string {
  return `/api/app/v1/company-assets/${encodeURIComponent(materialId)}/versions/${encodeURIComponent(versionId)}/${action}`;
}

export function loadCompanyPortfolio(forceRefresh = false): Promise<CompanyPortfolioProjection> {
  return request<CompanyPortfolioProjection>(forceRefresh ? "/api/app/v1/company/portfolio?refresh=true" : "/api/app/v1/company/portfolio");
}

export function loadCompanyMaterials(): Promise<CompanyMaterialsProjection> {
  return request<CompanyMaterialsProjection>("/api/app/v1/company-materials");
}

export function loadCompanyAssetLibrary(): Promise<CompanyAssetLibraryProjection> {
  return request<CompanyAssetLibraryProjection>("/api/app/v1/company-assets");
}

export function exportCompanyAssetLibrary(limit = 100): Promise<CompanyAssetLibraryExport> {
  return request<CompanyAssetLibraryExport>(`/api/app/v1/company-assets/export?limit=${limit}`);
}

export async function fetchCompanyAssetContent(
  materialId: string,
  versionId: string,
  download = false,
): Promise<{ blob: Blob; filename: string; mediaType: string }> {
  const headers = new Headers();
  headers.set(RELEASE_HEADER, RELEASE_ID);
  const path = `${assetPath(materialId, versionId, "content")}?download=${download ? "true" : "false"}`;
  const response = await fetch(path, { headers, credentials: "same-origin" });
  if (!response.ok) throw await responseError(response);
  return {
    blob: await response.blob(),
    filename: downloadFilename(response.headers.get("Content-Disposition"), "company-asset"),
    mediaType: response.headers.get("Content-Type") ?? "application/octet-stream",
  };
}

export async function submitCompanyAssetReview(
  materialId: string,
  versionId: string,
  input: { deletion_rule: string; permitted_reuse: string[] },
  csrfToken: string,
): Promise<void> {
  await request(assetPath(materialId, versionId, "review"), {
    method: "POST",
    headers: { "X-Arvectum-CSRF": csrfToken },
    body: JSON.stringify(input),
  });
}

export async function rejectCompanyAssetVersion(
  materialId: string,
  versionId: string,
  reason: string,
  csrfToken: string,
): Promise<void> {
  await request(assetPath(materialId, versionId, "reject"), {
    method: "POST",
    headers: { "X-Arvectum-CSRF": csrfToken },
    body: JSON.stringify({ reason }),
  });
}

export async function admitCompanyAssetVersion(
  materialId: string,
  versionId: string,
  csrfToken: string,
): Promise<AdmittedCompanyAsset> {
  const response = await request<{ admitted: AdmittedCompanyAsset }>(assetPath(materialId, versionId, "admit"), {
    method: "POST",
    headers: { "X-Arvectum-CSRF": csrfToken },
  });
  return response.admitted;
}

export async function stageCompanyMaterial(
  input: {
    material_id?: string;
    project_id: string;
    filename: string;
    media_type: string;
    semantic_role: string;
    classification: string;
    purpose: string;
    rights: string;
    retention_rule: string;
    content_base64: string;
  },
  csrfToken: string,
): Promise<StagedMaterialVersion> {
  const response = await request<{ material: StagedMaterialVersion }>("/api/app/v1/company-materials", {
    method: "POST",
    headers: { "X-Arvectum-CSRF": csrfToken },
    body: JSON.stringify(input),
  });
  return response.material;
}

export function generateCompanyDocx(
  input: { material_id: string; version_id: string; title: string; body: string; date: string },
  csrfToken: string,
): Promise<GeneratedCompanyOutput> {
  return request<GeneratedCompanyOutput>("/api/app/v1/company-materials/generate", {
    method: "POST",
    headers: { "X-Arvectum-CSRF": csrfToken },
    body: JSON.stringify(input),
  });
}

export async function downloadCompanyOutput(path: string): Promise<{ blob: Blob; filename: string }> {
  if (!path.startsWith("/api/app/v1/company-materials/outputs/") || !path.endsWith("/download")) {
    throw new Error("COMPANY_OUTPUT_DOWNLOAD_PATH_INVALID");
  }
  const headers = new Headers();
  headers.set(RELEASE_HEADER, RELEASE_ID);
  const response = await fetch(path, { headers, credentials: "same-origin" });
  if (!response.ok) throw await responseError(response);
  return {
    blob: await response.blob(),
    filename: downloadFilename(response.headers.get("Content-Disposition")),
  };
}

export async function fileToBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  const chunk = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunk) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunk));
  }
  return btoa(binary);
}
