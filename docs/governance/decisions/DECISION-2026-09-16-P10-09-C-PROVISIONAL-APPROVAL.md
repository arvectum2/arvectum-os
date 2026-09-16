# DECISION-2026-09-16-P10-09-C-PROVISIONAL-APPROVAL

Status: `Approved`
Date: `2026-09-16`
Owner / Decision Authority: `ООО «Арвектум»`
Task classification: `product_contract` + `governance` + `product_specific`
Authority: Constitution `1.2.0`; RFC-0001 through RFC-0008 `1.0.0`; ADR-0001 and ADR-0002 `Accepted`
Decision target: `P10.09-C — asset-grounded Copilot fit-check and bounded use`
Approved lifecycle transition: `Draft → Provisional`
Approved version: `0.3.0`

## 1. Independent owner decision

The owner explicitly approved the exact reviewed P10.09-C Product Contract with the instruction:

> `утверждаю P10.09-C Product Contract v0.3.0 в Provisional scope; exact Draft blob 0b21eb3f05a0cdae5c3765a10dfdd27f9d8c4292`

This approval applies only to the exact Draft content identified below. It is an explicit owner governance decision and does not derive authority from an AI recommendation, UI state, or implementation readiness.

## 2. Exact approved proposal identity

Approved Draft:

`docs/contracts/P10-09-C-ARVECTUM-COMPANY-WORKSPACE-PRODUCT-CONTRACT-DRAFT-v0.3.0.md`

Exact approved Draft content identity:

- blob SHA: `0b21eb3f05a0cdae5c3765a10dfdd27f9d8c4292`;
- Draft version: `0.3.0`;
- PR: `#5`;
- Product Contract subject: `product-contract-subject/p9-11-f11-arvectum-company-workspace@organization/arvectum-company`.

A material boundary change requires a new immutable Product Contract version and new applicable approval evidence.

## 3. Human-readable approved scope

The owner approves bounded internal `Provisional 0.3.0` for one additional read-only/transient operation:

`workspace.copilot.ground-company-assets`

The operation may use an exact current canonically admitted Company asset as Copilot evidence only when its exact canonical Organizational Asset designation explicitly contains permitted reuse `company-internal-ai-grounding`.

For the first implementation, raw model context is limited to bounded UTF-8 `text/plain` and `text/markdown`; other admitted media may be metadata evidence only and are not parsed or interpreted in this slice.

## 4. Authority and safety meaning

This approval does not make any existing admitted asset AI-eligible by itself. Asset-level handling remains exact and authoritative. Non-canonical review/UI state cannot grant AI reuse.

Copilot output remains transient synthesis. It creates no validated Knowledge, canonical mutation, Authorization, Organizational Authority, Consequential Approval, or external effect. Evidence content is treated as untrusted data rather than model instructions.

The approved boundary remains organization-scoped and server-authorized. Cross-Organization retrieval/reuse is not admitted.

## 5. What this approval does not approve or prove

This decision does not approve or prove:

- Product Contract `Stable` lifecycle;
- Platform Capability `Active` lifecycle;
- CAP-002 Knowledge reliance or automatic Memory/Knowledge promotion;
- cloud/external model-provider use;
- PDF, DOCX, PPTX, image or OCR content extraction for AI grounding;
- direct AI-to-action, approval, publication, signing, filing or other consequential execution;
- cross-Organization AI grounding;
- public/stable API or SDK compatibility;
- customer/external Production readiness, SLA, support or certification;
- retroactive mutation of existing asset handling policies;
- P10.09-C implementation closure merely by publication.

## 6. Required publication sequence

This Approval Record must be committed before lifecycle-current `Provisional 0.3.0` is published.

After this independent approval commit exists, the branch may:

1. publish `Provisional 0.3.0` by immutable reference to the exact approved Draft blob;
2. wire only the approved bounded Company Asset → Copilot source;
3. keep asset eligibility fail-closed on exact canonical designation handling;
4. run functional cross-review and full applicable tests/CI;
5. synchronize roadmap/closure only after implementation evidence is complete;
6. merge only after read-after-write and CI requirements pass.
