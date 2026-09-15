# P10.09-A — Admitted Asset Discovery and Ordinary Retrieval Closure Review

Status: `Complete / PASS`
Date: `2026-09-15`
Task classification: `product_specific`
Owner: `ООО «Арвектум»`
Scope: Productive Workspace / Arvectum Company, bounded internal Provisional Product Contract scope

## Authority check

- Constitution `1.2.0` remains `Ratified` and unchanged.
- RFC-0001, RFC-0003, RFC-0004, RFC-0005, RFC-0006 and RFC-0008 remain satisfied.
- ADR-0001 permits Organization-scoped non-authoritative read/search projections.
- ADR-0002 keeps Company-specific projection and UX product-owned.
- Product Contract `p9-11-f11-arvectum-company-workspace 0.2.0` remains `Provisional`; no lifecycle transition is made.
- No Platform Capability lifecycle transition, public API, customer Production, SLA/support or broader conformance claim is created.

## Delivered slice

P10.09-A now provides an ordinary Workspace path over already admitted Company assets:

- human-readable search by name/purpose;
- filtering by semantic role/type, project, current/superseded version and accepted/archive state;
- ordinary open/download of the exact admitted version;
- exact admitted DOCX reuse into the existing generation flow;
- version, digest and provenance available on demand rather than as primary UX;
- rejected or staged-only versions excluded from ordinary admitted-asset discovery;
- session/access revalidation and exact-version SHA-256 integrity verification on retrieval.

The discovery view is non-authoritative and rebuildable. GET retrieval performs no canonical mutation. Staging, review, admission and generated-output promotion semantics are unchanged.

## Functional cross-review

Iteration 1 found no material authority, security, lifecycle or provenance objection. A deliberate usability fallback remains: when a product label is temporarily unavailable, the already-authorized project identifier may be displayed rather than hiding the asset.

CI initially exposed two release-closure defects rather than product-behavior defects: stale committed SPA production assets and historical master-roadmap rows that had lost stable M3/M8 closure wording. Both were repaired without changing Phase 10 sequencing.

## Evidence

- PR: `#3` — `P10.09-A: admitted asset discovery and ordinary retrieval`.
- Internal Workspace release: `p10.09.1`; application contract: `13`; still `bounded-internal-provisional` and `public_api=false`.
- Local frontend verification after release repair: TypeScript typecheck PASS; `18` test files / `52` tests PASS; Web Storage guard PASS; production build PASS.
- Historical roadmap closure regression verification: `26` targeted Phase 3/8 closure tests PASS.
- GitHub Actions `Productive Workspace CI` run `35000346004`: BFF security/context PASS; SPA build, interaction, storage, reproducibility and release-pinned asset boundary PASS.
- GitHub Actions `Reference Python CI` run `35000345989`: full reference architecture fitness suite PASS.

## Decision

`P10.09-A = Complete / PASS` for its exact bounded scope.

The next primary development slice is `P10.09-B — asset-aware generation`. P10.07 remains a separate mandatory genuine-request evidence gate for M10 closure and is not satisfied by this slice.
