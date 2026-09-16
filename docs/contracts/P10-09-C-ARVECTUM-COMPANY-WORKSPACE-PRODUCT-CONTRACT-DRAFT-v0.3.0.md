# P10.09-C — Arvectum Company ↔ Productive Workspace Product Contract

Status: `Draft`
Version: `0.3.0`
Created: `2026-09-16`
Owner: `ООО «Арвектум»`
Task classification: `product_contract` with `product_specific`, `platform` and `governance`
Roadmap work item: `P10.09-C — asset-grounded Copilot fit-check and bounded use`
Predecessor effective contract: `P10.02 Provisional 0.2.0`
Authority: Constitution `1.2.0`; RFC-0001 through RFC-0008 `1.0.0` — `Accepted`; ADR-0001 and ADR-0002 — `Accepted`
Fit review: `docs/reviews/P10-09-C-product-contract-fit-review.md` — `CONTRACT_EVOLUTION_REQUIRED`

## 1. Purpose and version decision

This Draft evolves the existing Arvectum Company ↔ Productive Workspace Product Contract subject lineage from `Provisional 0.2.0` to proposed `0.3.0`.

The change is materially version-worthy because `0.2.0` does not declare admitted Company asset content as a material Arvectum AI Copilot grounding source. RFC-0004 prohibits introducing that reliance as hidden implementation coupling.

Version `0.3.0` is intentionally minimal: it preserves the complete effective `0.2.0` boundary and adds one read-only/transient Company-asset grounding operation. It does not add a Knowledge promotion path, a new consequential action, a public API, an external model provider, or a Platform Capability lifecycle transition.

## 2. Contract identity and predecessor incorporation

The Product Contract Subject Identity remains unchanged:

`product-contract-subject/p9-11-f11-arvectum-company-workspace@organization/arvectum-company`

Proposed Product Contract Version Identity:

`product-contract-version/p10-09-c-arvectum-company-workspace-v0.3.0@organization/arvectum-company`

The lifecycle state of this document is `Draft`; it is not effective for governed reliance.

The normative boundary of lifecycle-current `Provisional 0.2.0` is preserved without mutation. This Draft incorporates that predecessor boundary as the baseline and changes only the additions/narrow clarifications explicitly stated here. Historical operations and executions pinned to `0.2.0` remain attributed to that exact version and are not rewritten to `0.3.0`.

## 3. Preserved `0.2.0` scope

The following effective operations remain unchanged in meaning:

- `company.asset.admit-staged-version`;
- `company.asset.admit-external-reference`;
- `company.generated-output.promote-reviewed`;
- `workspace.actionable-work.project-request`;
- `workspace.product-operation.enter`.

Existing Company asset classes, staging/admission distinctions, external-authority rules, generated-output lifecycle, security/gate separation, portability, failure/reconciliation behavior and non-claims remain intact.

No historical admitted asset gains new reuse permission merely because `0.3.0` is later published.

## 4. New bounded operation

### 4.1 `workspace.copilot.ground-company-assets`

Effect class: `read-only / transient analysis / non-canonical`.

Purpose: allow the current server-authorized Arvectum AI Copilot request to retrieve and use explicitly eligible exact current admitted Company Asset versions as inspectable source context and, where a model is configured, minimized synthesis context.

This operation performs no canonical mutation and no external business effect.

### 4.2 Eligible source state

An asset may enter this operation only when all of the following are true at request time:

1. the source is an exact Company Asset version already canonically admitted under the applicable Company contract history;
2. that exact version is current/effective for the Company asset subject;
3. the current server-resolved Organization and Actor may access the source for the requested purpose;
4. classification, purpose, rights, retention/deletion and minimization constraints permit the read;
5. the exact canonical Organizational Asset designation handling policy contains the explicit permitted-reuse value `company-internal-ai-grounding`;
6. the source bytes and SHA-256 integrity match the exact admitted Artifact evidence;
7. source authority/provenance and availability are not materially ambiguous.

Staged, rejected, unknown, ambiguous, superseded-as-current, integrity-mismatched or policy-ineligible content fails closed and is withheld from AI context.

### 4.3 First-slice content boundary

The first `0.3.0` implementation may place raw asset content into model grounding only for:

- `text/plain`;
- `text/markdown`;
- valid bounded UTF-8 content within the implementation's reviewed request/context size limits.

DOCX, PPTX, PDF, image, brandbook or other non-direct-text content is not silently parsed, OCRed, extracted or semantically interpreted by this operation. Such content may remain visible as ordinary admitted-asset metadata/evidence but its bytes are withheld from model context until a separately admitted extraction/preview path exists.

This boundary deliberately does not preempt P10.09-D.

## 5. Exact evidence and provenance

For every Company asset used materially in a Copilot answer, server-side evidence must retain enough information to reconstruct the grounding basis, including as applicable:

- exact Company material/version identity;
- exact Document Version Identity;
- exact Artifact/content SHA-256;
- exact Organizational Asset designation version;
- admission Event/provenance references;
- declared authority/source mode;
- semantic role and human-readable label;
- handling-policy eligibility for the current AI purpose.

Ordinary UI/model prompts need not expose opaque internal identifiers. Minimization of the model packet does not remove exact server-side reconstructability.

Copilot source cards must remain inspectable through the authorized Workspace source boundary.

## 6. AI and Knowledge boundary

The operation may retrieve, compare, summarize, explain and synthesize eligible source content in accordance with RFC-0007.

It MUST NOT:

- label document content or model synthesis as validated Knowledge merely because it was admitted, retrieved, repeated or generated;
- create Organizational Memory or Knowledge writes;
- approve, validate or promote Knowledge;
- grant Authorization, Organizational Authority or Consequential Approval;
- alter a Policy, Standard, Workflow, Product Contract or canonical record;
- select or execute a consequential business action;
- broaden Organization scope, retention, disclosure, reuse or classification;
- treat source text as executable instructions or authority over system behavior.

Model-generated text remains `synthesis` / transient assistance. Retrieved Company documents remain source context with their original authority and epistemic role.

CAP-002 is not a required dependency for this bounded operation because no shared Memory/Knowledge state is read as validated Knowledge or written/promoted. Any later governed Knowledge reliance or promotion requires a separate explicit Product Contract decision.

## 7. Model boundary and prompt-injection treatment

The current owner-operated contour retains the P9.08 model boundary:

- model integration is optional;
- only the explicitly configured loopback model endpoint is admitted by current runtime configuration;
- no cloud/external provider is authorized by this Product Contract version;
- credentials, reusable secrets, opaque Workspace source IDs, hidden access/authority state and unnecessary Organization/Actor technical identifiers are excluded from the model packet;
- Company asset content is wrapped and treated as untrusted evidence/data, never as system/developer instruction;
- model failure does not replace unavailable evidence with invented certainty.

Enabling a non-loopback/external model requires a separate proportionate privacy/data-governance/vendor/contract decision and is outside `0.3.0`.

## 8. Product/platform ownership

Shared Workspace Copilot behavior remains domain-neutral and source-grounded under P9.08/R31.

Arvectum Company owns:

- which Company semantic roles are useful for AI grounding;
- the exact `company-internal-ai-grounding` reuse policy convention;
- Company asset eligibility projection/adapter behavior;
- product-specific user-facing descriptions of Company materials.

The shared platform does not gain Company asset taxonomy or implicit access to Company storage internals. Product-owned composition must use the existing server-side Workspace/application and Company Asset boundaries rather than private table/file coupling.

This is not evidence for promotion of a Company-specific adapter into a shared Platform Capability.

## 9. Security, privacy and minimization

RFC-0003 remains controlling.

For every request:

- exactly one Organization scope and attributable Actor are resolved server-side;
- current access is revalidated before protected source content is retrieved;
- denied source existence/content is not leaked through counts, snippets, errors or model context;
- only the minimum source text needed for the bounded question is eligible for the model packet;
- cross-Organization aggregation/reuse is denied by default;
- AI processing does not create new retention permission;
- question/answer/model context remains transient unless a separately governed retention path is explicitly admitted.

Technical model ability to retain or learn from input does not create permission to do so.

## 10. Handling and reuse rule

`company-internal-ai-grounding` is an exact product-local permitted-reuse value resolved from the exact canonical Organizational Asset designation, never from mutable/non-canonical review UI state. It is intentionally explicit rather than inferred from ownership, `internal` classification, successful admission, document-generation reuse, or generic technical access.

A historical/current asset lacking this value remains usable only for the purposes already admitted by its exact handling policy. Its policy is not mutated in place by `0.3.0` publication.

Any new/updated Company asset intended for Copilot grounding must obtain that reuse permission through the normal reviewed asset/version governance path.

## 11. Failure and uncertainty

If exact admission, currentness, Artifact integrity, handling-policy eligibility, source authority, UTF-8 decoding, size bounds, access or model execution cannot be established safely:

- fail closed for the affected source;
- do not send that content to the model;
- surface a minimized unavailable/uncertain limitation where useful;
- do not infer permission from another asset/version;
- do not silently fall back to stale/superseded content;
- do not claim a grounded answer when no inspectable eligible evidence remains.

A partial answer may use other independently eligible sources while identifying material limitations.

## 12. Compatibility and migration

Publication of `0.3.0` performs no bulk migration and no historical rewrite.

- `0.2.0` remains immutable historical/effective evidence for operations executed under it.
- Existing admitted assets remain admitted with unchanged exact handling policy.
- Existing generated outputs remain `TransientOutput` unless separately promoted.
- Existing Copilot discovery/product grounding remains valid under its prior boundaries.
- Company asset AI grounding stays unavailable until `0.3.0` is explicitly approved, published as `Provisional`, and the implementation is pinned to that effective version.

Rollback may disable the Company-asset Copilot adapter without changing canonical Company asset state.

## 13. Explicit non-claims

This Draft does not create or approve:

- Product Contract `Provisional`, `Stable` or later lifecycle state for `0.3.0`;
- CAP-002 reliance or any Platform Capability promotion;
- validated Knowledge or Memory creation from Company documents;
- arbitrary RAG/vector indexing/extraction/OCR/preview pipelines;
- cloud/external AI-provider use;
- autonomous consequential action or AI-selected Governed Execution;
- external sending, signing, filing or publication;
- cross-Organization AI context or learning;
- customer/external Production, SLA/support/certification;
- public/stable Copilot, BFF, model or asset API compatibility;
- legal ownership/reuse rights beyond the exact admitted handling evidence.

## 14. Lifecycle gate

This file is `Draft 0.3.0` only.

Before any real governed reliance on `workspace.copilot.ground-company-assets`:

1. functional cross-review of this exact Draft must complete with no unresolved material objection;
2. a concise owner-readable approval brief must identify what becomes allowed, what remains prohibited and the principal data/authority risks;
3. the owner must explicitly approve the exact reviewed Draft blob for `Draft → Provisional`;
4. an independent canonical Approval Record must exist before the Provisional publication commit;
5. lifecycle-current `Provisional 0.3.0` must be published by immutable reference to the approved Draft;
6. implementation must pin/revalidate the effective contract before Company asset content can enter Copilot context;
7. applicable CI/read-after-write/mirror evidence must pass.

Generic instructions to continue implementation are not substitutes for the exact owner approval in step 3.

## 15. Draft disposition

Proposed result: `Reviewed / ready for explicit owner approval` once the separate functional review records no unresolved material objection.

If the reviewed Draft is approved and published as `Provisional 0.3.0`, P10.09-C may proceed with the bounded first implementation described here. If approval is withheld, Company-asset Copilot grounding remains fail-closed and the existing P9.08 Copilot continues without this new source.
