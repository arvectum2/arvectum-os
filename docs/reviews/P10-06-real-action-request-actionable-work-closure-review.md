# P10.06 — Real Action Request / Actionable Work boundary — closure review

Status: `Complete / PASS`
Date: `2026-09-15`
Owner: `ООО «Арвектум»`
Task classification: `platform` with `product_contract`, `product_specific` and `governance`
Constitution: `1.2.0` — `Ratified`, frozen
RFC baseline: RFC-0001 through RFC-0008 `1.0.0` — `Accepted`
Accepted ADR: `ADR-0001 — Productive Workspace Browser Application Topology`
Product Contract: `P10.02 Arvectum Company ↔ Productive Workspace — Provisional 0.2.0`
Roadmap baseline at task start: `ROADMAP 2.97.8`; `PHASE-10 1.0.8`; `P10.06 — Current`
Implementation PR: `#2 — P10.06: implement Actionable Work boundary`
Reviewed implementation head: `f9c1580712124be5e10618f07cbeb54df519deef`
Workspace release: `p10.06.1`; internal application contract: `12`

## 1. Closure statement

P10.06 is `Complete / PASS` for the exact bounded `Local / Persistent Internal / owner-operated` Productive Workspace scope.

The implementation defines a domain-neutral, non-authoritative Actionable Work envelope over requests that already exist in an owning Company/product source. It does not create a universal Kernel `Task`, does not manufacture a request to satisfy the roadmap, and does not make a request real merely because Workspace renders it.

The runtime intentionally registers **no default request sources**. Therefore P10.06 can be closed as a truthful boundary implementation while P10.07 still waits for the first naturally occurring genuine request. No synthetic fixture is claimed as real operational evidence.

A projected request can expose human-readable context, source ownership, source-declared state/freshness, why attention is requested, bounded source-declared next-step descriptions, Product Contract reference, governed-preflight state and exact source/provenance on demand. The projection does not infer urgency, owner responsibility, approval requirement, permission, action availability or Organizational Authority.

Opening a request context is a `no-side-effect-context-entry`. It performs no product operation, canonical mutation or external effect. Any later consequential effect must cross the applicable owning-product Product Contract and a new current RFC-0005 Governed Execution gate evaluation.

P10.06 does not amend Constitution or Accepted RFC/ADR, does not change Product Contract `0.2.0`, does not promote that contract to `Stable`, does not promote a Platform Capability to `Active`, and does not establish P10.07/M10 operational-action evidence.

## 2. Canonical authority checked

The closure review re-checked canonical authority rather than relying on project chat or model memory:

1. Constitution `1.2.0` — `Ratified`, frozen;
2. RFC Index — RFC-0001 through RFC-0008 are `Accepted 1.0.0`;
3. RFC-0001 — domain-neutral platform boundary, non-authoritative projections and Governed Execution law;
4. RFC-0004 — Product Contract boundary, no hidden coupling, lifecycle separation and no authority from contract possession;
5. RFC-0005 — current gate revalidation, AI/authority separation and no consequential effect outside Governed Execution;
6. RFC-0006 — provenance/evidence/replay safety and non-canonical observability/projection state;
7. ADR-0001 — same-origin BFF, server-side Organization/Actor resolution, safe `GET`, non-authoritative read models and exact SPA+BFF release coupling;
8. P10.01 authority matrix — real action requests remain Company/product-owned and are not invented by Workspace;
9. lifecycle-current P10.02 Product Contract `Provisional 0.2.0` — `workspace.actionable-work.project-request` is read-only/non-canonical and `workspace.product-operation.enter` has no product side effect by itself;
10. canonical master and Phase 10 roadmaps.

Conflict check result: **no material conflict with higher authority**.

Decision Authority Policy remains `Proposed 0.2.1`; no delegation or authority is inferred from P10.06.

## 3. Implemented Actionable Work envelope

The bounded source contribution contains only generic projection semantics:

- exact current Organization key;
- exact current Actor key;
- source kind: `product` or `company`;
- bounded source identity/label and exact request reference;
- human-readable title/context;
- source-declared attention reason;
- source state and freshness: `fresh`, `stale` or `unknown`;
- timezone-aware observation time;
- bounded source-declared next-step descriptions;
- source authority statement;
- exact Product Contract id/version/lifecycle metadata supplied by the owning boundary;
- source-declared governed-preflight state;
- explicit bounded provenance references;
- optional same-origin no-side-effect Workspace entry path.

This envelope does not define Tender, Discount, Creative, Proxy or other product business fields, approval rules, urgency rules, domain workflow state or product side-effect semantics.

Projection identities are opaque deterministic hashes over normalized source kind/source identity/request reference. Duplicate projected identities fail closed rather than merging conflicting source requests.

## 4. Source, freshness and fail-closed behavior

Each source contribution is validated against the **current server-resolved Organization and Actor**. Cross-scope data fails closed.

The provider requires explicit bounded provenance. Missing provenance, invalid lifecycle, malformed source fields, duplicate identities, source exceptions or unsafe entry paths fail closed.

Only `Provisional` or `Stable` Product Contract lifecycle metadata is admitted by the generic envelope. This is not a claim that possession of a Product Contract grants permission or authority; the owning source/adapter remains responsible for its exact effective contract semantics, and any consequential action is revalidated later.

A stale or unknown request may remain visible as truthful source context, but its Workspace entry is withheld. The projection does not silently replace unavailable source evidence with cached, inferred or synthetic requests.

The default runtime provider has zero registered sources and therefore truthfully returns an empty Actionable Work set.

## 5. Authority and Governed Execution boundary

The projection explicitly states:

- `canonical_authority = false`;
- `creates_requests = false`;
- `universal_task_primitive = false`;
- `product_semantics_owned_by_platform = false`;
- `organizational_authority_provided = false`;
- `urgency_inferred = false`;
- `owner_responsibility_inferred = false`;
- `approval_requirement_inferred = false`;
- `action_availability_inferred = false`.

Per request, the envelope also states that current gate revalidation is required before any effect and that consequential action, Organizational Authority and Consequential Approval are not provided by the projection.

The entry envelope is explicitly non-consequential and requests neither canonical mutation nor external effect. It cannot target `/api/*` or the direct `/governed` surface.

No UI state, visible card, source freshness, Product Contract reference, preflight text or no-side-effect entry constitutes current Authorization, Organizational Authority, Data Governance permission, Validation or Consequential Approval.

## 6. Browser / BFF and release boundary

P10.06 adds one authenticated read-only same-origin BFF endpoint:

`GET /api/app/v1/actionable-work`

It reuses the existing current-session/current-access dependency and therefore resolves/revalidates server-side Organization/Actor context before the provider is called. Source/provider failure maps to truthful `503 ACTIONABLE_WORK_UNAVAILABLE`; the BFF does not substitute a synthetic list.

The `/work` page now presents a separate `Запросы на действие / Action requests` block between existing `My Work` attention state and product contexts.

The empty state explicitly says that no verified requests exist and that Workspace will not manufacture one merely to populate the list or advance a milestone.

Because P10.06 adds a new browser/BFF exchange, the exact internal release boundary advances from the M9 historical baseline `p9.11.10 / contract 11` to:

- Workspace release: `p10.06.1`;
- internal application contract: `12`;
- classification: `bounded-internal-provisional`;
- `public_api = false`.

ADR-0001 exact SPA+BFF co-deployment remains preserved. No public/stable API or third-party compatibility promise is created.

## 7. Functional cross-review

Maximum allowed iterations: 7.

### Iteration 1 — Task / product / authority boundary

Finding: risk that P10.06 could become an implicit universal Task service or infer owner work from governance diagnostics.

Resolution: implement only a generic projection envelope; concrete requests remain source-owned; register no default runtime sources; expose explicit non-authoritative/no-authority flags; no request is synthesized from `My Work`, AI, gates or roadmap state.

Result: `PASS after bounded design confirmation`.

### Iteration 2 — source identity / freshness / provenance integrity

Finding: opaque projection identity initially derived from raw source id/reference while payload fields normalized whitespace, allowing textually equivalent references to produce different projection identities.

Resolution: derive the opaque ID from the same normalized source id/reference used by the payload; require explicit bounded provenance; fail closed on scope mismatch, duplicate identity, invalid lifecycle, malformed/unsafe entry and source failure; withhold entry for non-fresh source state.

Result: `PASS after revision`.

### Iteration 3 — browser/BFF / exact-release compatibility

Finding: adding the new `/work` read caused the historical P9.07 route allowlist test to reject the page, and retaining application contract `11` would hide a new BFF→SPA exchange.

Resolution: update the P9.07 test allowlist by exactly one new read-only endpoint; keep it separate from command/effect routes; advance exact Workspace release to `p10.06.1` and internal application contract to `12`; rebuild checked-in hashed frontend assets reproducibly.

Result: `PASS after revision`.

### Iteration 4 — regression / selected-Mac environment discrepancy

Finding: local full Reference Python execution returned `1367/1369`, with two legacy P7.05 selected-Mac proof failures caused by the installed launchd observer not being pinned to that historical proof release.

Resolution: reproduce the same two failures on a clean detached `origin/main` worktree. This proves they are selected-Mac baseline/environment state rather than a P10.06 regression. The exact implementation head then passed the canonical GitHub Reference Python CI on Linux.

Result: `PASS with bounded environment attribution`.

### Iteration 5 — final functional closure

Review: re-check no product schema/business rule leakage, no request fabrication, no authority from visibility, source/provenance/freshness fail-closed behavior, no-side-effect entry, exact-release compatibility and explicit P10.07 non-claim.

Material objections after iteration 5: **none**.

This functional review is implementation evidence only. It is not Product Contract `Stable` approval, Platform Capability promotion, operational-readiness approval, P10.07 evidence, M10 achievement or Organizational Authority delegation.

## 8. Verification and CI evidence

Reviewed implementation head:

`f9c1580712124be5e10618f07cbeb54df519deef`

Local bounded evidence on that implementation:

- Productive Workspace backend: `115/115 PASS` with an owner-local non-symlink `TMPDIR`;
- P10.06 focused backend: `12/12 PASS`;
- frontend: `50/50 PASS` across 17 files;
- TypeScript typecheck: `PASS`;
- browser Web Storage guard: `PASS`;
- production Vite build: `PASS`;
- release-pinned asset verification: `PASS` for `p10.06.1 / contract 12`;
- frontend dist SHA-256 reported by verifier: `515982c3ebf73ff74270ae8cff5ebbb62df42675ab4e2aafa7b2e0277ec858e2`;
- local full reference execution: `1367/1369`, with the same two P7.05 selected-Mac launchd-pin failures reproduced unchanged on clean `origin/main` and therefore excluded as P10.06 regressions.

Exact-head GitHub evidence:

- Productive Workspace CI run `34976262198` — `success`; BFF security/context and SPA build/interaction/storage jobs both passed on exact head `f9c1580712124be5e10618f07cbeb54df519deef`;
- Reference Python CI run `34976262340` — `success` on the same exact head;
- repository mirror workflow run `34976253998` — `success`.

Tests cover, among other cases:

- empty default runtime/no synthetic request generation;
- exact current Organization/Actor binding;
- source/provenance/freshness validation;
- deterministic opaque projection identity and duplicate rejection;
- stale request withholding the entry path;
- source exception failing closed without fallback work;
- non-effective Product Contract lifecycle rejection;
- safe same-origin/no-side-effect entry only;
- BFF session requirement and truthful `503` failure behavior;
- frontend empty/error/source-backed states;
- no approve/execute/promote command surface in Actionable Work;
- existing P9.07 product-context journey accepting only the new read-only P10.06 request endpoint in addition to its historical reads.

## 9. Explicit non-claims

P10.06 closure does **not** establish or claim:

- that a naturally occurring genuine action request currently exists;
- P10.07 completion or PASS;
- a real owner decision or consequential product action;
- a product canonical mutation or external effect;
- a universal Kernel/platform `Task` primitive;
- automatic task registration from AI, telemetry, roadmap state or incomplete governance gates;
- Product Contract `Stable` status;
- Platform Capability `Active` status;
- customer/external `Production` readiness;
- public/stable API, SDK, browser compatibility or third-party action protocol;
- SLA, support, certification or broader conformance commitments;
- Organizational Authority, Authorization or final consequential approval from UI visibility or Product Contract possession;
- authority to execute a Tender Agent, Discount Parser or other product effect without that product's exact effective Product Contract and current Governed Execution gates.

## 10. Exit result and next gate

P10.06 exit outcome is satisfied for its declared scope:

> concrete Company/product-owned requests **can be projected truthfully** through a domain-neutral Workspace envelope without creating a universal Task primitive, inventing urgency/responsibility/approval/authority, or executing a product side effect.

The next critical-path item is:

`P10.07 — First real governed operational action`.

P10.07 remains **WAITING** until a naturally occurring genuine request exists and the applicable owning-product Product Contract/governed operation is exact and effective. No synthetic request may be created merely to advance Phase 10.
