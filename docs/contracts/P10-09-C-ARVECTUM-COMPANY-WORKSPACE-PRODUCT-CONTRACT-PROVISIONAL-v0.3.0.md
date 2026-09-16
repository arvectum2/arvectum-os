# P10.09-C — Arvectum Company ↔ Productive Workspace Product Contract

Status: `Provisional`
Version: `0.3.0`
Published: `2026-09-16`
Owner: `ООО «Арвектум»`
Task classification: `product_contract` with `product_specific`, `platform` and `governance`
Authority: Constitution `1.2.0`; RFC-0001 through RFC-0008 `1.0.0` — `Accepted`; ADR-0001 and ADR-0002 — `Accepted`
Owner approval: [`DECISION-2026-09-16-P10-09-C-PROVISIONAL-APPROVAL`](../governance/decisions/DECISION-2026-09-16-P10-09-C-PROVISIONAL-APPROVAL.md) — `Approved`
Approval commit: `500e2adb92384cbd5008aee21a0391864e5a8a1d`
Approved Draft: [`P10-09-C-ARVECTUM-COMPANY-WORKSPACE-PRODUCT-CONTRACT-DRAFT-v0.3.0`](P10-09-C-ARVECTUM-COMPANY-WORKSPACE-PRODUCT-CONTRACT-DRAFT-v0.3.0.md)
Approved Draft blob SHA: `0b21eb3f05a0cdae5c3765a10dfdd27f9d8c4292`
Predecessor effective contract: [`P10.02 Provisional 0.2.0`](P10-02-ARVECTUM-COMPANY-WORKSPACE-PRODUCT-CONTRACT-PROVISIONAL-v0.2.0.md)
Roadmap work item: `P10.09-C — asset-grounded Copilot fit-check and bounded use`

## 1. Provisional publication

This document is the lifecycle-current `Provisional 0.3.0` publication of the Arvectum Company ↔ Productive Workspace Product Contract.

The owner-approved normative substance is the exact reviewed Draft `0.3.0` identified by immutable Git blob SHA:

`0b21eb3f05a0cdae5c3765a10dfdd27f9d8c4292`

That exact blob is incorporated into this publication by immutable content reference. No material product/platform boundary semantics are changed by this publication.

The independent owner approval is recorded by `DECISION-2026-09-16-P10-09-C-PROVISIONAL-APPROVAL` in repository commit `500e2adb92384cbd5008aee21a0391864e5a8a1d`, which exists before this publication commit and explicitly authorizes `Draft 0.3.0 → Provisional 0.3.0`.

The Product Contract Subject lineage remains:

`product-contract-subject/p9-11-f11-arvectum-company-workspace@organization/arvectum-company`

The lifecycle-current Version Identity is:

`product-contract-version/p10-09-c-arvectum-company-workspace-v0.3.0@organization/arvectum-company`

Version `0.2.0` remains immutable historical contract evidence for operations executed or intentionally pinned under that exact boundary. Publication of `0.3.0` does not rewrite historical evidence.

## 2. Preserved predecessor boundary

`Provisional 0.3.0` preserves the complete admitted meaning of `0.2.0`, including:

- `company.asset.admit-staged-version`;
- `company.asset.admit-external-reference`;
- `company.generated-output.promote-reviewed`;
- `workspace.actionable-work.project-request`;
- `workspace.product-operation.enter`;
- Company asset classes and staging/admission distinctions;
- external-source authority preservation;
- generated-output `TransientOutput` default;
- security/gate separation, provenance, portability, failure/reconciliation and non-claims.

No historical or current admitted asset gains new reuse permission solely because this Product Contract version is published.

## 3. New admitted operation

### 3.1 `workspace.copilot.ground-company-assets`

Effect class: `read-only / transient analysis / non-canonical`.

The current server-authorized Arvectum AI Copilot may retrieve and use an exact current admitted Company Asset version as inspectable evidence and, where the configured model boundary permits, minimized synthesis context only when the exact source remains eligible at request time.

The operation performs no canonical mutation and no external business effect.

### 3.2 Exact eligibility

An asset is eligible only when all applicable conditions from the approved Draft are satisfied, including:

1. exact current canonical Company Asset admission;
2. current server-resolved Organization/Actor access;
3. exact source integrity and provenance;
4. handling constraints permitting the requested purpose;
5. exact canonical Organizational Asset designation containing permitted reuse `company-internal-ai-grounding`.

AI reuse is not inferred from ownership, `internal` classification, admission, document-generation reuse, technical readability, UI state or model ability.

Staged, rejected, unknown, ambiguous, superseded-as-current, integrity-mismatched or policy-ineligible content fails closed.

## 4. First implementation content boundary

Raw Company asset content may enter model grounding only for bounded valid UTF-8:

- `text/plain`;
- `text/markdown`.

DOCX, PPTX, PDF, image, brandbook and other non-direct-text bytes are not parsed, OCRed, extracted or semantically interpreted by this operation. They may be metadata evidence only until a separately admitted extraction/preview path exists.

This publication does not preempt P10.09-D.

## 5. AI, Knowledge and authority boundary

The new operation may retrieve, compare, summarize, explain and synthesize eligible source content. It does not:

- create or validate Knowledge or Organizational Memory;
- convert document/source content or AI synthesis into validated Knowledge;
- grant Authentication, Authorization, Organizational Authority or Consequential Approval;
- change a Policy, Standard, Workflow, Product Contract or canonical record;
- choose or execute a consequential business action;
- broaden Organization scope, classification, rights, retention, disclosure or reuse;
- treat source text as executable instruction or authority over system behavior.

Copilot model output remains transient synthesis. Retrieved Company materials retain their source authority and epistemic role.

CAP-002 is not a dependency of this bounded operation because no shared validated Knowledge/Memory state is read, written or promoted.

## 6. Model, privacy and minimization boundary

The current P9.08 model boundary remains controlling:

- model use is optional;
- only the explicitly configured loopback model endpoint is admitted by the current runtime contour;
- this Product Contract does not authorize a cloud/external provider;
- credentials, reusable secrets, hidden authority state and unnecessary technical identities are excluded from the model packet;
- source content is untrusted evidence/data, never system/developer instruction;
- question/answer/model context remains transient absent a separately governed retention path;
- cross-Organization retrieval/reuse remains denied by default.

A non-loopback/external model requires a separate proportionate privacy/data-governance/vendor/contract decision.

## 7. Product/platform ownership

Shared Workspace Copilot behavior remains domain-neutral and source-grounded.

Arvectum Company owns Company-specific asset eligibility, semantic-use choices and the `company-internal-ai-grounding` reuse convention. The platform does not gain Company taxonomy, private-store coupling or a new Platform Capability lifecycle state.

This Product Contract version is not evidence for promotion of the Company-specific adapter into a shared Platform Capability.

## 8. Migration and compatibility

Publication performs no bulk migration and no historical rewrite.

- `0.2.0` remains immutable historical evidence;
- existing admitted assets retain their exact handling policies;
- existing generated outputs remain `TransientOutput` unless separately governed promotion succeeds;
- existing Copilot discovery/product grounding remains valid under its prior boundaries;
- Company asset grounding is available only when implementation is pinned to this exact effective publication and asset-level eligibility is independently satisfied.

Rollback may disable the Company-asset Copilot adapter without changing canonical Company asset state.

## 9. Explicit non-claims

This `Provisional 0.3.0` publication does not establish or authorize:

- Product Contract `Stable` status;
- Platform Capability `Active` status;
- automatic Knowledge/Memory promotion or CAP-002 reliance;
- cloud/external AI-provider use;
- arbitrary RAG/vector indexing, OCR or extraction pipelines;
- direct AI-to-action or AI-selected Governed Execution;
- external sending, signing, filing or publication;
- cross-Organization AI context or learning;
- public/stable Copilot, BFF, model or asset API compatibility;
- customer/external Production readiness, SLA, support or certification;
- retroactive expansion of asset rights/reuse merely through this publication.

## 10. Effective-state rule

Real reliance on `workspace.copilot.ground-company-assets` is permitted only when runtime evidence pins this exact `Provisional 0.3.0` publication and continues to revalidate exact asset-level eligibility.

Implementation completion, release readiness and P10.09-C closure remain separate evidence gates. This publication alone does not close P10.09-C or advance any Platform Capability lifecycle.
