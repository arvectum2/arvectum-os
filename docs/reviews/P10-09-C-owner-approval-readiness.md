# P10.09-C — Product Contract 0.3.0 Owner Approval Readiness

Status: `Ready for owner decision`
Date: `2026-09-16`
Task classification: `product_contract` + `governance`
Exact Draft blob: `0b21eb3f05a0cdae5c3765a10dfdd27f9d8c4292`
Draft: `docs/contracts/P10-09-C-ARVECTUM-COMPANY-WORKSPACE-PRODUCT-CONTRACT-DRAFT-v0.3.0.md`
Functional review: `Complete / PASS` after 4 iterations

## What you are deciding

Approve or decline transition of this exact Product Contract version from `Draft 0.3.0` to bounded internal `Provisional 0.3.0`.

## What approval would newly allow

Arvectum AI in the internal owner-operated Workspace may use an **exact current admitted Company asset** as source/model grounding only when that exact asset version explicitly allows the reuse value:

`company-internal-ai-grounding`

The first implementation may send only bounded UTF-8 TXT/Markdown content to the already-bounded loopback Copilot model. It must retain exact source/version/SHA/provenance evidence server-side and expose inspectable source context.

## What approval would NOT allow

Approval does **not**:

- make any existing asset automatically eligible for AI use;
- parse/OCR DOCX, PDF, PPTX, images or brandbooks into AI context;
- create validated Knowledge or Memory from documents or AI output;
- let AI approve, authorize or choose/execute consequential actions;
- permit cloud/external AI providers;
- permit cross-Organization context/reuse;
- create a public/stable API, Product Contract Stable status, Active Platform Capability, customer Production or SLA/support commitment.

## Main risk controls

1. Exact canonical designation-level AI reuse permission, not blanket admission-based consent or mutable review-state permission.
2. Current server-side Organization/Actor/access revalidation.
3. Exact Artifact SHA/provenance and current-version checks.
4. Text-only bounded first slice; later extraction remains separate P10.09-D work.
5. Source text treated as untrusted data for prompt-injection resistance.
6. Minimized loopback model packet; no credentials or hidden authority state.
7. Answer remains transient source-context/synthesis; no Knowledge promotion.
8. No direct AI → governed-action route.

## If you approve

The required exact approval statement is:

> `утверждаю P10.09-C Product Contract v0.3.0 в Provisional scope; exact Draft blob 0b21eb3f05a0cdae5c3765a10dfdd27f9d8c4292`

After that explicit decision, an independent Approval Record must be committed **before** the Provisional publication commit. Only then may the implementation be enabled for real Company-asset Copilot reliance.

## If you do not approve

Existing P9.08 Copilot continues unchanged without Company asset content as a new grounding source. P10.09-C remains open/deferred at the Product Contract gate; no canonical Company asset state is affected.
