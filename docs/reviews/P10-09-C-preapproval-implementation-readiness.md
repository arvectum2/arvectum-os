# P10.09-C — Pre-Approval Implementation Readiness

Status: `Prepared / fail-closed / not enabled`
Date: `2026-09-16`
Task classification: `product_contract` with `product_specific` and `governance`
Fit decision: `CONTRACT_EVOLUTION_REQUIRED`
Reviewed Draft blob: `0b21eb3f05a0cdae5c3765a10dfdd27f9d8c4292`

## 1. Purpose

Prepare bounded implementation evidence without creating real Company-asset → Copilot reliance before the Product Contract owner gate.

This readiness work is subordinate to Draft `0.3.0`. It does not make the Draft effective and does not satisfy owner approval.

## 2. Prepared implementation

- internal release-scoped Copilot supplemental evidence seam; not a public/stable plugin API;
- product-owned `CompanyAssetCopilotEvidenceSource`;
- explicit runtime Product Contract gate requiring exact version `0.3.0`, lifecycle `Provisional` or `Stable`, and exact operation `workspace.copilot.ground-company-assets`;
- exact canonical Organizational Asset designation handling resolver over P10.03 committed admission state;
- required exact permitted-reuse value `company-internal-ai-grounding`;
- current admitted version + retained Artifact SHA integrity revalidation;
- TXT/Markdown raw model context only, bounded to 16 KiB per Company source and at most three selected Company evidence items;
- non-text assets metadata-only; binary bytes are not parsed or sent as model content;
- opaque browser source identity and `/company-materials` inspect path;
- model-only context excluded from the browser response payload;
- source content remains untrusted model data and the existing P9.08 system prompt continues to prohibit instruction following from evidence.

## 3. Deliberate non-enablement

`reference/python/workspace_app/main.py` still constructs `RuntimeCopilotProvider(discovery, products, model=model)` without any supplemental Company source.

Therefore the normal runtime has no Company-asset Copilot grounding behavior before approval/publication. The prepared adapter is exercised only by explicit tests.

No release/application-contract bump is made at this pre-approval stage because the deployable behavior is unchanged.

## 4. Cross-review findings closed

### Canonical handling source

Initial scaffold checked `permitted_reuse` from the non-canonical review projection. This was rejected as materially unsafe because review/UI state must not grant a new AI purpose.

Revision: production resolver now reads exact committed P10.03 Organizational Asset designation handling and verifies it against the admitted Artifact handling constraints. An adversarial test mutates non-canonical review metadata and proves that it still cannot grant AI reuse.

### Model-context relevance

Supplemental evidence relevance includes bounded `model_context`, allowing a content-only question to select a matching eligible text source without creating a derived search index. No persistent index/extraction is introduced; P10.09-D remains separate.

## 5. Verification

- existing + P10.09-C Copilot/governed-provider targeted suite: `19/19` PASS;
- full Workspace security/context suite after the final pre-approval revision: `129/129` PASS;
- existing CSRF/access-revalidation and loopback-model boundaries remain green;
- runtime composition inspection confirms Company asset grounding is not wired/enabled.

## 6. Remaining hard gate

Before real enablement:

1. owner explicitly approves exact Draft blob `0b21eb3f05a0cdae5c3765a10dfdd27f9d8c4292` for `Draft → Provisional`;
2. independent Approval Record is committed before publication;
3. lifecycle-current `Provisional 0.3.0` is published;
4. runtime composition is then wired to the exact effective contract and revalidated with CI/release evidence.

Until then, current P9.08 Copilot behavior remains unchanged.
