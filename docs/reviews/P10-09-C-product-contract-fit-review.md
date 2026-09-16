# P10.09-C — Company Asset → Copilot Product Contract Fit Review

Status: `Complete / CONTRACT_EVOLUTION_REQUIRED`
Date: `2026-09-16`
Owner: `ООО «Арвектум»`
Task classification: `product_contract` with `product_specific` and `governance`
Roadmap item: `P10.09-C — asset-grounded Copilot fit-check and bounded use`

## 1. Question

May lifecycle-current Arvectum Company ↔ Productive Workspace Product Contract `Provisional 0.2.0` be relied upon for making exact admitted Company asset content material grounding context for Arvectum AI Copilot?

Required result vocabulary is fixed by the P10 sequencing/concurrency review: `COVERED`, `CONTRACT_EVOLUTION_REQUIRED`, or `DEFER`.

## 2. Authority checked

- Constitution `1.2.0` — `Ratified`, frozen.
- RFC-0001 through RFC-0008 — `Accepted 1.0.0`, with direct focus on RFC-0003, RFC-0004, RFC-0007 and RFC-0008.
- ADR-0001 — `Accepted` Productive Workspace browser/BFF topology.
- ADR-0002 — `Accepted` Company Workspace durable governed state.
- Company ↔ Workspace Product Contract `Provisional 0.2.0` and its exact approved Draft blob `a92c1d1aac54d565d3d32ce746925620c9d1fd12`.
- P9.08 bounded source-grounded Copilot and R31 AI-safety remediation.
- P10 sequencing/concurrency review, Section 5 Product Contract fit rule.
- P10.09-B closure and canonical roadmap `3.00.0`.

No higher-authority conflict was found with bounded AI retrieval/summarization itself. The issue is whether this exact product/platform reliance is already declared.

## 3. Findings

### 3.1 AI analysis is architecturally admissible

RFC-0007 permits AI to retrieve, analyze, summarize, compare and propose while keeping output non-authoritative and preventing silent Knowledge promotion. RFC-0008 likewise permits bounded AI participation over Document/Artifact content and requires derivation/source attribution where material.

Therefore P10.09-C is not blocked merely because an AI model may receive authorized Company document content.

### 3.2 Product Contract `0.2.0` does not declare this integration surface

`0.2.0` explicitly admits Company asset admission, reviewed generated-output promotion, Actionable Work projection and no-side-effect product-operation entry. It also retains exact-version document generation.

It does **not** declare an operation or integration surface by which admitted Company assets become material Copilot/model grounding context. Its `workspace.actionable-work.project-request` summarization allowance applies to the distinct Actionable Work projection and cannot be silently generalized into arbitrary Company-asset AI grounding.

RFC-0004 requires the Product Contract to declare material product/platform reliance before that reliance occurs. Reusing admission state as an implicit blanket AI permission would create hidden coupling and broaden the approved boundary without a versioned contract decision.

### 3.3 CAP-002 is not required for the bounded slice

The intended first slice does not read or write validated Knowledge and creates no Memory/Knowledge promotion path. Source documents, extracts and model synthesis remain source context / transient output. Therefore the new contract need not add CAP-002 as a platform dependency merely to perform bounded retrieval and synthesis.

Any future validated Knowledge reliance/promotion remains a separate RFC-0007 + Product Contract decision.

### 3.4 Asset admission is not blanket permission for AI reuse

Every admitted asset already carries classification, purpose, rights, retention/deletion and `permitted_reuse`. The contract evolution must not reinterpret historical admission as consent for a new purpose.

The bounded AI path therefore requires an explicit product-local reuse token on the exact current admitted version:

`company-internal-ai-grounding`

Absence of that exact token fails closed. Generic ownership, technical readability, `internal` classification, or prior permission for document generation is insufficient.

### 3.5 First implementation slice must remain smaller than future extraction/search work

P10.09-D owns derived previews/extraction/search-index work. P10.09-C therefore may place raw content into model context only for directly bounded textual media (`text/plain`, `text/markdown`) whose exact retained bytes can be safely decoded within a size cap.

DOCX/PDF/image/brandbook content is not silently parsed, OCRed or semantically interpreted in P10.09-C. Such assets may remain discoverable metadata/evidence, but their bytes are withheld from model grounding until an applicable later extraction path exists.

## 4. Fit decision

**`CONTRACT_EVOLUTION_REQUIRED`.**

The minimum sufficient change is a new immutable version in the existing Product Contract subject lineage. The proposed `0.3.0` adds one bounded read-only/transient operation for exact admitted Company asset grounding in Copilot while preserving every `0.2.0` canonical mutation, action-entry and lifecycle boundary.

This result does not itself approve `0.3.0`, publish it as `Provisional`, or authorize runtime reliance.

## 5. Required boundary for the new version

The new Product Contract must at minimum declare:

1. one explicit read-only/transient Company-asset → Copilot operation;
2. exact current admitted source version and Artifact integrity resolution;
3. server-side Organization/Actor access revalidation;
4. exact canonical designation-level `company-internal-ai-grounding` permitted-reuse requirement;
5. purpose/classification/rights/minimization/retention enforcement;
6. raw model content limited initially to bounded UTF-8 TXT/Markdown;
7. minimized model packet with no credentials, opaque Workspace IDs, hidden authority state or cross-Organization context;
8. source content treated as untrusted data, never instructions/authority;
9. answer remains transient/source-context + synthesis, not validated Knowledge;
10. no automatic action routing, canonical mutation, external effect or Knowledge/Memory write;
11. loopback-only model boundary retained for the current owner-operated contour;
12. no CAP-002/Platform Capability lifecycle promotion implied.

## 6. Next gate

Prepare and functionally cross-review Product Contract Draft `0.3.0`, then present a concise owner-readable decision brief plus the exact Draft blob SHA.

Real Company-asset Copilot reliance MUST remain unavailable until the owner explicitly approves that exact Draft and a lifecycle-current `Provisional 0.3.0` publication exists canonically.
