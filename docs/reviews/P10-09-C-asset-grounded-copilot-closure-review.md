# P10.09-C — Asset-Grounded Copilot Closure Review

Status: `Complete / PASS`
Date: `2026-09-16`
Task classification: `product_contract` with `product_specific` and `governance`
Owner: `ООО «Арвектум»`
Scope: Productive Workspace / Arvectum Company, bounded internal owner-operated Provisional Product Contract scope

## Authority check

- Constitution `1.2.0` remains `Ratified` and unchanged.
- RFC-0001 through RFC-0008 remain `Accepted 1.0.0`; RFC-0003, RFC-0004, RFC-0005, RFC-0007 and RFC-0008 are the principal P10.09-C constraints.
- ADR-0001 and ADR-0002 remain `Accepted` within their exact scopes.
- The P10.09-C fit result is `CONTRACT_EVOLUTION_REQUIRED`; Company asset → Copilot grounding was not introduced as hidden coupling under Product Contract `0.2.0`.
- Owner approval exists for exact reviewed Draft blob `0b21eb3f05a0cdae5c3765a10dfdd27f9d8c4292`.
- Lifecycle-current Arvectum Company ↔ Productive Workspace Product Contract is `Provisional 0.3.0`, published after the independent Approval Record.
- Historical and intentionally operation-pinned `0.2.0` executions remain attributed to their exact predecessor contract; no bulk migration or historical rewrite is performed.
- No Platform Capability promotion, CAP-002 reliance, validated Knowledge promotion, public/stable API, external AI provider, customer Production, SLA/support or broader conformance claim is created.

## Delivered slice

P10.09-C admits one bounded new read-only operation: `workspace.copilot.ground-company-assets`.

An admitted Company asset may materially ground Arvectum AI only when the exact current canonical version independently passes current Organization/Actor access, integrity, provenance, purpose/rights/minimization checks and its canonical Organizational Asset designation handling explicitly includes `company-internal-ai-grounding`.

The first implementation is deliberately narrow:

- model context is limited to bounded valid UTF-8 `text/plain` / `text/markdown` content;
- non-text DOCX/PDF/PPTX/image/brandbook bytes are not silently parsed, OCRed or semantically interpreted;
- source content is treated as untrusted evidence/data, never as system or developer instruction;
- only the existing explicitly configured loopback model boundary is admitted; no external/cloud model provider is authorized;
- browser-facing evidence remains minimized while exact source/version/SHA/designation/admission provenance stays reconstructable server-side;
- Company asset grounding remains retrieval/synthesis only and creates no Memory, Knowledge, approval, authorization, Organizational Authority or consequential action;
- generated model text remains transient synthesis.

The owner-facing Company Materials path now exposes an explicit human-readable AI-grounding control for the selected exact asset version. The control writes the already-governed product-local reuse value through the normal review/admission path, preserves unrelated permitted-reuse values, and cannot retroactively grant AI reuse to historical assets.

Existing P10.03 admission and P10.05 generated-output promotion executable projections remain intentionally pinned to their immutable P10.02 `0.2.0` boundary. The new AI-grounding path is separately contract-gated to exact `Provisional 0.3.0`; the UI distinguishes these boundaries rather than falsely relabelling historical/consequential executions.

## Functional cross-review

Four Product Contract Draft review iterations and subsequent implementation/UX review were completed.

1. Product/platform boundary review rejected direct Company Asset → shared Copilot coupling under `0.2.0` and rejected unnecessary CAP-002 promotion; the minimum new read-only Product Contract operation was defined instead.
2. Rights/purpose review rejected admission, ownership, `internal` classification or generic technical access as implicit AI consent; exact canonical `company-internal-ai-grounding` permission became mandatory.
3. Model-context review bounded raw context to direct UTF-8 text, excluded secrets/opaque authority state, treated source text as untrusted data and kept extraction/OCR for P10.09-D.
4. Lineage/action review preserved exact `0.2.0` historical attribution, no bulk migration and no AI → Governed Execution shortcut.

Implementation cross-review then closed two material presentation/governance risks: non-canonical review projection cannot grant AI reuse, and the owner-facing checkbox preserves other reuse permissions rather than replacing the handling policy. No unresolved material architecture, authority, security, privacy, rights, Knowledge-lifecycle, provenance, migration or usability objection remains in the exact bounded P10.09-C scope.

## Evidence

- PR: `#5` — `P10.09-C: contract-gated Company asset Copilot grounding`.
- Owner Approval Record commit: `500e2adb92384cbd5008aee21a0391864e5a8a1d`; Product Contract publication commit: `32d94f99c5cf24df91050e43220c4897aea9352a`.
- Approved Draft blob: `0b21eb3f05a0cdae5c3765a10dfdd27f9d8c4292`.
- Provisional publication blob: `58252df4079a84ff2e526124f7a1f54cee919b91`.
- Implementation/UX head: `57f3c8175a721f8d7601b77d587d4bd17cc0e585`.
- Internal Workspace release: `p10.09.3`; application contract: `15`; classification remains `bounded-internal-provisional`, `public_api=false`.
- Local Workspace suite: `134/134` PASS.
- Local frontend: `18` test files / `53` tests PASS; TypeScript typecheck PASS; Web Storage guard PASS; production build and release-pinned asset verification PASS.
- GitHub Actions `Productive Workspace CI` run `35061005469`: PASS on exact implementation/UX head.
- GitHub Actions `Reference Python CI` run `35061003751`: `1369/1369` PASS on exact implementation/UX head.
- GitVerse branch mirror run `35060935163`: PASS on exact implementation/UX head.
- Closure-state local full-reference run executed `1369` tests: `1367` passed and the same two selected-Mac P7.05 tests failed on current host launchd observer state; clean GitHub reference CI passes `1369/1369`. A previously observed transient P7.06 live-workspace `503` was separately reproduced on clean canonical `main@fe5bd18`, so it is not attributed to P10.09-C.

## Decision

`P10.09-C = Complete / PASS` for its exact bounded scope.

The next primary development slice is `P10.09-D — derived previews/search indexes`. It may introduce bounded preview, extraction and derived search/index projections only when they remain non-authoritative, rebuildable, exact-source/version attributable, Organization/access/purpose scoped, explicit about unsupported or failed extraction, and non-Knowledge by default.

`P10.07` remains a separate mandatory genuine-request evidence gate for R35/M10 closure and is not satisfied by P10.09-C.