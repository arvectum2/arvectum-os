# Arvectum OS Canonical Roadmap

Status: `Active`
Version: `3.03.1`
Created: `2026-08-07`
Updated: `2026-09-17`
Owner: `ООО «Арвектум»`
Task classification: `governance`

## 1. Purpose and authority

This document is the **single canonical roadmap** for Arvectum OS sequencing, current status and concurrency.

Authority order remains:

1. Constitution;
2. Accepted RFC;
3. Accepted ADR;
4. approved governance/policies/standards/catalogs;
5. Product Contracts and approved product decisions;
6. code/tests/evidence;
7. this roadmap;
8. task materials/chat/model memory.

Roadmap status does not itself change Platform Capability lifecycle, Product Contract lifecycle, operational environment/readiness, conformance maturity, SLA/support or commercial commitments.

Detailed phase plans, reviews and repository history retain implementation/evidence detail; this file defines current canonical sequencing when subordinate phase text is older or more restrictive.

## 2. Version 3.03.1 — P10.10 genuine owner-session start

Phase 10 has progressed beyond the original serial plan:

- owner decision [`DECISION-2026-09-17-P10-10-OWNER-DOGFOODING-START`](../governance/decisions/DECISION-2026-09-17-P10-10-OWNER-DOGFOODING-START.md) is `Approved`;
- `P10.10` genuine owner dogfooding is now `IN PROGRESS / HUMAN`, beginning with exact-release selected-Mac deployment and real owner use;
- deployment migration remediation PR #17 permits the already-installed `arvectum1/arvectum-os` release only as historical source provenance while keeping new targets restricted to canonical `arvectum2/arvectum-os`;

- `R34 = Complete / PASS — 7/7`;
- `M10-alpha = Achieved / PASS` through a real owner-operated governed Company asset cycle;
- ADR-0002 durable Company Workspace state is accepted and qualified in the bounded owner-local scope;
- `P10.06 — Real Action Request / Actionable Work boundary = Complete / PASS`;
- Workspace internal release is `p10.09.3`, application contract `15`;
- `P10.09-A — admitted-asset discovery and ordinary retrieval = Complete / PASS`;
- `P10.09-B — asset-aware generation = Complete / PASS`;
- `P10.09-C — asset-grounded Copilot fit-check and bounded use = Complete / PASS`;
- `P10.09-D — bounded derived text projection, on-demand substring search and ordinary Workspace search composition = Complete / PASS`;
- bounded pre-P10.07 `P10.08` product-owned/read-only/no-side-effect preparation is `Complete / PASS — preparation scope only`;
- lifecycle-current Arvectum Company ↔ Productive Workspace Product Contract is `Provisional 0.3.0` for the exact declared scope;
- `P10.07` truthfully waits for a naturally occurring genuine request and may not use synthetic evidence.

The prior sequencing incorrectly allowed the P10.07 waiting state to appear to freeze all later useful development.

[`P10 Sequencing / Concurrency Review — 2026-09-15`](../reviews/P10-SEQUENCING-CONCURRENCY-REVIEW-2026-09-15.md) is `Complete / PASS` and establishes the corrected rule:

> **P10.07 is a mandatory real-world evidence gate for R35/M10 closure, not a global development prerequisite. Independent asset usefulness, bounded product-owned preparation, dogfooding and reliability work may continue in parallel.**

Accordingly:

- **P10.09-D is Complete / PASS for its bounded roadmap scope**;
- **the bounded pre-P10.07 P10.08 preparation slice is Complete / PASS; no further independent AUTO preparation item is currently admitted by the execution queue**;
- evidence-based reusable P10.08 generalization/completion still waits for the first real P10.07 action;
- P10.10 may begin asset-side dogfooding only from genuine owner sessions, and full P10.10 PASS still requires the P10.07 action journey;
- R35 remains blocked until real action evidence exists;
- P10.07 remains mandatory for M10 closure.

This status synchronization creates no Constitution/RFC/ADR amendment, Product Contract expansion, Stable/Active lifecycle promotion, public interface, customer Production or authority claim.

## 3. Architecture and governance baseline

- Constitution `1.2.0` — `Ratified`, frozen;
- RFC-0001 through RFC-0008 — `Accepted 1.0.0`;
- ADR-0001 — `Productive Workspace Browser Application Topology`, `Accepted`;
- ADR-0002 — `Company Workspace Durable Governed State`, `Accepted` for the exact bounded Company-local persistence scope;
- Decision Authority Policy — `Proposed 0.2.1`; residual authority remains with the owner under Accepted governance;
- Engineering Quality and Refactoring Gates remain binding;
- CAP-001 through CAP-004 remain `Incubating / Provisional`;
- Arvectum Company ↔ Productive Workspace Product Contract is lifecycle-current `Provisional 0.3.0` for its exact declared scope; predecessor `0.2.0` remains immutable historical/operation-pinned evidence where applicable;
- operating environment remains `Local / Persistent Internal / owner-operated` with scoped conformance;
- canonical repository for current work is `arvectum2/arvectum-os`;
- no public/stable SDK/API/wire/browser/connector surface, external/customer Production, SLA/support/certification or broader conformance claim exists.

## 4. Strategic roadmap

| Phase | Strategic scope | Status | Milestone |
|---|---|---:|---|
| Phase 0 | Foundation / Architecture Bootstrap | 🟩 Complete | M0 |
| Phase 1 | Reference Implementation | 🟩 Complete | M1 |
| Phase 2 | Core Runtime | 🟩 Complete | M2 |
| `Phase 3` | Shared Platform Capabilities | 🟩 Complete | `M3` Validated shared capability baseline |
| `Phase 4` | Workspace / Operator Experience | 🟩 Complete | M4 |
| Phase 5 | SDK, Contracts and Extension Experience | 🟩 Complete | M5 |
| Phase 6 | Product-driven Platform Validation | 🟩 Complete / PASS | M6 |
| Phase 7 | Operational / Enterprise Readiness | 🟩 Complete / PASS | M7 |
| `Phase 8` | Ecosystem and External Integration | 🟩 Complete / PASS | M8 — exact activated one-Organization scope |
| Phase 9 | Productive Workspace & Daily Operations | 🟩 Complete / PASS | M9 |
| **Phase 10** | **Operational Work & Organizational Assets** | **🟨 Active** | **M10 — Governed Daily Operations Baseline** |

## 5. Phase 10 completed baseline

Detailed phase plan: [`PHASE-10-OPERATIONAL-WORK-ORGANIZATIONAL-ASSETS.md`](PHASE-10-OPERATIONAL-WORK-ORGANIZATIONAL-ASSETS.md).

Completed:

| ID | Work item | Status |
|---|---|---:|
| P10.00 | Phase 10 activation | 🟩 Complete / PASS |
| P10.01 | Asset/admission + real-work authority matrix | 🟩 Complete / PASS |
| P10.02 | Company Workspace Product Contract evolution | 🟩 Complete / PASS — `Provisional 0.2.0` |
| R33 | Asset / Product Contract / Authority Boundary Review | 🟩 Complete / PASS |
| P10.03 | Organizational-asset admission execution path | 🟩 Complete / PASS |
| P10.04 | Company Asset Library UX + version/handling | 🟩 Complete / PASS |
| P10.05 | Reviewed generated-output promotion | 🟩 Complete / PASS |
| R34 | M10-alpha Asset Governance / Usability Review | 🟩 Complete / PASS — 7/7 |
| M10-alpha | First Governed Company Asset Cycle | 🟩 Achieved / PASS |
| P10.06 | Real Action Request / Actionable Work boundary | 🟩 Complete / PASS |
| P10.09-A | Admitted-asset discovery and ordinary retrieval | 🟩 Complete / PASS |
| P10.09-B | Asset-aware generation from exact admitted Company asset versions | 🟩 Complete / PASS |
| P10.09-C | Asset-grounded Copilot fit-check and bounded use | 🟩 Complete / PASS — `Provisional 0.3.0` |
| P10.09-D | Bounded derived text projection + rebuildable substring search + ordinary Workspace composition | 🟩 Complete / PASS |

M10-alpha proves a real Company-owned material can complete staging → review → Governed Execution admission → immutable asset/version/provenance → restart/no-replay reconstruction → later exact-version use through Workspace while generated output remains `TransientOutput` by default.

## 6. Active Phase 10 work

| ID | Work item | Current status |
|---|---|---:|
| **P10.07** | First real governed operational action | **⏸ WAITING — genuine request required; mandatory M10 evidence** |
| **P10.08** | Product operational entry-point composition | **🟦 PREPARATION COMPLETE / WAITING** — bounded pre-P10.07 preparation passed; evidence-informed completion/generalization waits genuine P10.07 evidence |
| **P10.09** | Source-grounded use of admitted assets in Workspace / AI / generation | **🟩 COMPLETE / PASS through P10.09-D bounded scope** |
| **P10.10** | Real daily-operations dogfooding + friction closure | **🟨 IN PROGRESS / HUMAN** — selected-Mac exact-release deployment + genuine owner asset-side sessions; full PASS still waits P10.07 |
| P10.11 | Lifecycle / platform-reuse / capability disposition | ⬜ waits sufficient Phase 10 evidence |
| **R35** | Operational Work / Product Boundary / AI Authority Review | **🔒 blocked on real P10.07 action + applicable P10.08 evidence** |
| R36 | M10 Hardening + Milestone Code Health Gate | ⬜ later gate |
| P10.12 | Phase 10 / M10 closure review | ⬜ later |

## 7. P10.07 — real-action evidence gate

P10.07 remains deliberately non-synthetic.

Required evidence:

`real source request → Workspace context → owner decision → fresh server-side gates → Governed Execution → completed/blocked/failed/uncertain result → reconstruction evidence`.

Prerequisites for the concrete action include:

- naturally occurring real Company/product-owned request;
- owning product's exact effective Product Contract covering the consequential operation;
- exact current workflow/operation and RFC-0005 gates;
- no replay of an historical external effect without new authorization.

If no genuine request exists, P10.07 waits. This waiting state does **not** freeze unrelated work.

## 8. P10.09 — current value-delivery stream

P10.09 starts immediately from the already-achieved governed Company asset foundation.

[`P10.09-A Admitted Asset Discovery Closure Review — 2026-09-15`](../reviews/P10-09-A-admitted-asset-discovery-closure-review.md) is `Complete / PASS`.

[`P10.09-B Asset-Aware Generation Closure Review — 2026-09-15`](../reviews/P10-09-B-asset-aware-generation-closure-review.md) is `Complete / PASS`.

[`P10.09-C Asset-Grounded Copilot Closure Review — 2026-09-16`](../reviews/P10-09-C-asset-grounded-copilot-closure-review.md) is `Complete / PASS`.

### P10.09-A — admitted-asset discovery and ordinary retrieval — COMPLETE / PASS

Make governed Company assets easy to find and use through normal Workspace UX:

- search/filter by human-readable name;
- semantic Company role/type;
- project association where product-owned evidence exists;
- current versus superseded version;
- accepted/archive lifecycle state;
- ordinary open/preview/download/reuse path;
- exact version/digest/provenance available on demand rather than as primary UX;
- Organization/access/classification/purpose controls preserved.

No terminal, GitHub or internal UUID knowledge on the ordinary path.

### P10.09-B — asset-aware generation — COMPLETE / PASS

Use exact admitted Company assets as explicit UI-selectable generation inputs:

- templates;
- logos/brand assets;
- source/reference materials;
- exact current/effective versions.

Generated outputs remain `TransientOutput` unless the already-governed reviewed promotion path succeeds.

### P10.09-C — asset-grounded Copilot fit-check and bounded use — COMPLETE / PASS

The explicit fit decision was `CONTRACT_EVOLUTION_REQUIRED`. Product Contract `0.3.0` was independently owner-approved and published as `Provisional` before real Company-asset Copilot grounding was enabled.

The bounded runtime uses only exact current admitted asset versions whose canonical Organizational Asset designation explicitly permits `company-internal-ai-grounding`; publication does not retroactively grant AI reuse to older assets. Direct model context is limited to bounded valid UTF-8 TXT/Markdown under the existing loopback model boundary.

AI may retrieve, explain, compare, summarize and draft. It does not independently approve, admit assets, create authority, execute consequential actions or convert document/model content into RFC-0007 validated Knowledge.

### P10.09-D — derived previews/search indexes — COMPLETE / PASS

Closure review: [`P10.09-D Derived Projections Closure Review — 2026-09-16`](../reviews/P10-09-D-derived-projections-closure-review-2026-09-16.md) is `Complete / PASS`.

The delivered bounded projection/search slice remains:

- non-authoritative;
- rebuildable;
- source/version attributable;
- Organization/access/purpose scoped;
- explicit about unsupported/failed extraction;
- non-Knowledge by default.

## 9. P10.08 — product operational preparation in parallel

Before P10.07 occurs, permitted preparatory work is limited to bounded, product-owned/no-side-effect scope:

- inventory explicit operational entry points already admitted by current product contracts;
- improve read-only/product context surfaces;
- prepare `workspace.product-operation.enter` routing where the applicable contract already permits it;
- identify missing owning-product Product Contract operations;
- prepare fail-closed unavailable/blocked states.

The admitted pre-P10.07 preparation slice is `Complete / PASS — preparation scope only` based on the bounded inventory/cross-review merged through PR #14 and durable checkpoint closure merged through PR #15. Existing Workspace Actionable Work/product composition already provides the permitted read-only/no-side-effect entry boundary; no concrete consequential product operation was invented or admitted.

No further independent AUTO P10.08 preparation item is currently admitted. Do **not** infer a universal stable product-action API or platform abstraction before real reuse evidence exists.

After P10.07, evaluate what is genuinely reusable and finish P10.08/R35 from actual evidence.

## 10. P10.10 — progressive dogfooding

Asset-side real owner dogfooding may start as P10.09 slices become available.

Useful sessions include:

- find an admitted Company asset without knowing internal identifiers;
- compare current and prior versions;
- use an exact admitted template/brand/source version in real generation;
- review/promote/reject generated output where naturally useful;
- use asset-grounded AI only after the P10.09-C fit gate;
- record and close material usability friction.

Full P10.10 closure still requires the genuine P10.07 action journey.

## 11. Parallel lanes

```text
                           ┌─ VALUE / ASSETS
                           │   P10.09-A COMPLETE / PASS
                           │      ↓
                           │   P10.09-B COMPLETE / PASS
                           │      ↓
                           │   P10.09-C COMPLETE / PASS — Product Contract 0.3.0 + bounded AI grounding
                           │      ↓
                           │   P10.09-D COMPLETE / PASS — bounded derived projections/search
                           │      ↓
                           │   asset-side P10.10 dogfooding [HUMAN genuine-session evidence]
                           │
Phase 10 current main ─────┼─ REAL ACTION EVIDENCE
                           │   P10.07 WAITING [genuine request]
                           │      ↓
                           │   P10.08 evidence-informed completion → R35
                           │
                           ├─ PRODUCT PREPARATION
                           │   bounded pre-P10.07 P10.08 preparation COMPLETE / PASS
                           │   further completion waits real P10.07 evidence
                           │
                           ├─ EXTERNAL INTEGRATIONS
                           │   INT-B7 WAITING [real endpoint/deployment/account]
                           │
                           └─ RELIABILITY / DX
                               continuous bounded engineering work only when separately admitted by canonical task source/queue

(asset evidence + real-action evidence + R35 + full dogfooding)
                           ↓
                         P10.11
                           ↓
                          R36
                           ↓
                      P10.12 / M10
```

## 12. External integration lane

INT-B1 through INT-B6 are complete/scoped PASS. INT-B7 is prepared but remains `NOT ADMITTED` until a real exact endpoint/deployment/account and least-privilege credential binding exist.

Preferred prepared candidate remains bounded read-only `1С:ERP 2.5` procurement projection.

Do not invent endpoint/credential evidence or an INT-B8 merely to create activity.

## 13. Closure invariants

M10 still requires all applicable evidence, including:

1. M10-alpha remains valid;
2. receipt/staging, canonical admission and generated-output promotion remain distinct;
3. asset state remains durable/reconstructable in declared scope;
4. ordinary asset work is usable without terminal/GitHub/internal identifiers;
5. **one naturally occurring genuine action completes P10.07 or reaches a truthful blocked/failed/uncertain state with complete evidence**;
6. Actionable Work does not manufacture work/urgency/authority;
7. Product Contracts cover actual reliance;
8. product business semantics remain product-owned;
9. AI remains source-grounded/proposal-only and does not create authority/Knowledge promotion;
10. external authority remains external where declared;
11. full P10.10 dogfooding has no unresolved material blockers;
12. R33–R36 findings are closed/dispositioned;
13. R36 Milestone Code Health Gate passes before P10.12.

## 14. Current canonical actions

**Current autonomous execution state:**

> **No independent AUTO item is currently admitted in the repository execution queue after bounded P10.08 preparation closure. Do not invent a new priority merely to create activity.**

**Waiting evidence action:**

> **P10.07 — execute the first naturally occurring genuine governed operational action when a real request and applicable owning-product contract/operation exist. Do not synthesize it.**

**Human evidence lane:**

> **P10.10 — genuine owner dogfooding is active. Deploy the exact canonical selected-Mac release through P7.06, then use Company Assets/search/generation/Copilot in a real owner session; automation may record and repair observed friction but must not manufacture usability evidence.**

**Available conditional parallel work:**

> reliability/DX work only when separately admitted by an approved canonical task source/queue; INT-B7 only if a real external endpoint/deployment/account and least-privilege credential binding become available; no synthetic P10.07/P10.10 evidence and no inferred reusable platform abstraction.