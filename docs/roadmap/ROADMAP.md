# Arvectum OS Canonical Roadmap

Status: `Active`
Version: `2.98.1`
Created: `2026-08-07`
Updated: `2026-09-15`
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

## 2. Version 2.98.1 — Phase 10 concurrency correction

Phase 10 has progressed beyond the original serial plan:

- `R34 = Complete / PASS — 7/7`;
- `M10-alpha = Achieved / PASS` through a real owner-operated governed Company asset cycle;
- ADR-0002 durable Company Workspace state is accepted and qualified in the bounded owner-local scope;
- `P10.06 — Real Action Request / Actionable Work boundary = Complete / PASS`;
- Workspace internal release is `p10.06.1`, application contract `12`;
- `P10.07` truthfully waits for a naturally occurring genuine request and may not use synthetic evidence.

The prior sequencing incorrectly allowed the P10.07 waiting state to appear to freeze all later useful development.

[`P10 Sequencing / Concurrency Review — 2026-09-15`](../reviews/P10-SEQUENCING-CONCURRENCY-REVIEW-2026-09-15.md) is `Complete / PASS` and establishes the corrected rule:

> **P10.07 is a mandatory real-world evidence gate for R35/M10 closure, not a global development prerequisite. Independent asset usefulness, bounded product-owned preparation, dogfooding and reliability work may continue in parallel.**

Accordingly:

- **P10.09 is now the primary current development stream**;
- P10.08 may perform bounded product-owned/no-side-effect preparation, but evidence-based reusable platform generalization still waits for the first real P10.07 action;
- P10.10 may begin asset-side dogfooding, but full P10.10 PASS still requires the P10.07 action journey;
- R35 remains blocked until real action evidence exists;
- P10.07 remains mandatory for M10 closure.

This sequencing correction creates no Constitution/RFC/ADR amendment, Product Contract expansion, Stable/Active lifecycle promotion, public interface, customer Production or authority claim.

## 3. Architecture and governance baseline

- Constitution `1.2.0` — `Ratified`, frozen;
- RFC-0001 through RFC-0008 — `Accepted 1.0.0`;
- ADR-0001 — `Productive Workspace Browser Application Topology`, `Accepted`;
- ADR-0002 — `Company Workspace Durable Governed State`, `Accepted` for the exact bounded Company-local persistence scope;
- Decision Authority Policy — `Proposed 0.2.1`; residual authority remains with the owner under Accepted governance;
- Engineering Quality and Refactoring Gates remain binding;
- CAP-001 through CAP-004 remain `Incubating / Provisional`;
- Arvectum Company ↔ Productive Workspace Product Contract is lifecycle-current `Provisional 0.2.0` for its exact declared scope;
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

M10-alpha proves a real Company-owned material can complete staging → review → Governed Execution admission → immutable asset/version/provenance → restart/no-replay reconstruction → later exact-version use through Workspace while generated output remains `TransientOutput` by default.

## 6. Active Phase 10 work

| ID | Work item | Current status |
|---|---|---:|
| **P10.07** | First real governed operational action | **⏸ WAITING — genuine request required; mandatory M10 evidence** |
| **P10.08** | Product operational entry-point composition | **🟦 PARALLEL PREPARATION AVAILABLE**; final reusable generalization waits real P10.07 evidence |
| **P10.09** | Source-grounded use of admitted assets in Workspace / AI / generation | **🟨 CURRENT / PRIMARY DEVELOPMENT STREAM** |
| **P10.10** | Real daily-operations dogfooding + friction closure | **🟦 PARTIALLY OPEN** — asset-side sessions may start; full PASS waits P10.07 |
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

### P10.09-A — admitted-asset discovery and ordinary retrieval — CURRENT

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

### P10.09-B — asset-aware generation

Use exact admitted Company assets as explicit UI-selectable generation inputs:

- templates;
- logos/brand assets;
- source/reference materials;
- exact current/effective versions.

Generated outputs remain `TransientOutput` unless the already-governed reviewed promotion path succeeds.

### P10.09-C — asset-grounded Copilot fit-check and bounded use

Before admitted Company assets become material AI/Copilot context, record one explicit fit decision:

- `COVERED` — current effective Product Contract already covers the exact intended bounded use;
- `CONTRACT_EVOLUTION_REQUIRED` — publish the minimum sufficient new immutable Product Contract version before reliance;
- `DEFER` — unresolved need/rights/security boundary.

AI may retrieve, explain, compare, summarize and draft. It does not independently approve, admit assets, create authority or convert document content into RFC-0007 validated Knowledge.

### P10.09-D — derived previews/search indexes

Bounded preview, text extraction and search/index projections may be introduced when useful, provided they remain:

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

Do **not** infer a universal stable product-action API or platform abstraction before real reuse evidence exists.

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
                           │   P10.09-A CURRENT
                           │      ↓
                           │   P10.09-B
                           │      ↓
                           │   P10.09-C fit gate → bounded AI use if admitted
                           │      ↓
                           │   P10.09-D / asset-side P10.10 dogfooding
                           │
Phase 10 current main ─────┼─ REAL ACTION EVIDENCE
                           │   P10.07 WAITING [genuine request]
                           │      ↓
                           │   P10.08 evidence-informed completion → R35
                           │
                           ├─ PRODUCT PREPARATION
                           │   bounded P10.08 read-only/no-side-effect preparation
                           │
                           ├─ EXTERNAL INTEGRATIONS
                           │   INT-B7 WAITING [real endpoint/deployment/account]
                           │
                           └─ RELIABILITY / DX
                               continuous bounded engineering work

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

**Primary development action:**

> **P10.09-A — admitted Company asset discovery and ordinary retrieval through Productive Workspace.**

**Waiting evidence action:**

> **P10.07 — execute the first naturally occurring genuine governed operational action when a real request and applicable owning-product contract/operation exist. Do not synthesize it.**

**Available parallel work:**

> bounded P10.08 product-owned/no-side-effect preparation; asset-side P10.10 dogfooding as P10.09 slices land; reliability/DX work; INT-B7 only if a real external endpoint becomes available.
