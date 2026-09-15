# P10 Sequencing / Concurrency Review — Waiting Evidence Must Not Freeze Useful Development

Status: `Complete / PASS`
Date: `2026-09-15`
Owner: `ООО «Арвектум»`
Task classification: `governance` with `platform` and `product_contract`
Constitution: `1.2.0` — `Ratified`, frozen
RFC basis: RFC-0001 through RFC-0008 `1.0.0` — `Accepted`
ADR basis: ADR-0001 and ADR-0002 — `Accepted`
Roadmap baseline reviewed: `ROADMAP 2.97.9`; `PHASE-10 1.0.9`
Trigger: owner review of current useful capability breadth after P10.06 and concern that P10.07 waiting state appeared to freeze all further Arvectum OS development.

## 1. Question

Does `P10.07 — First real governed operational action`, which truthfully waits for a naturally occurring genuine request, have to block all later useful Phase 10 development?

## 2. Finding

No.

P10.07 is a mandatory **real-world evidence gate for M10 closure**. It is not an architectural prerequisite for all asset-side usefulness, product-context composition, reliability work or bounded product-owned no-side-effect surfaces.

The prior Phase 10 concurrency map over-serialized the phase by placing `P10.09` and all later dogfooding after `R35`. That sequencing was a roadmap planning choice, not a requirement of the Constitution, an Accepted RFC or an Accepted ADR.

The corrected interpretation preserves the prohibition on synthetic real-action evidence while allowing independent useful work to continue.

## 3. Current evidence already sufficient for parallel work

The following are already canonical:

- `M10-alpha = Achieved / PASS` through a real Company-owned governed asset cycle;
- `R34 = Complete / PASS — 7/7`;
- Company Workspace Product Contract `Provisional 0.2.0` is effective for its exact declared scope;
- `P10.03`, `P10.04` and `P10.05` provide governed asset admission, owner-facing asset lifecycle and reviewed transient-output promotion boundaries;
- ADR-0002 plus R34-D1/D2 provide bounded restart-durable Company Workspace state;
- `P10.06 = Complete / PASS` provides a truthful Actionable Work projection but intentionally registers no synthetic/default request source;
- `P10.07` remains WAITING because no genuine request is currently available.

These facts justify continued work on making admitted assets and existing product context materially more useful without fabricating an operational action.

## 4. Corrected concurrency disposition

### 4.1 P10.07 — unchanged real evidence gate

Status remains:

`WAITING — genuine request required`.

It still requires:

- a naturally occurring real Company/product-owned request;
- the owning product's exact effective Product Contract for the consequential operation;
- current RFC-0005 gate revalidation;
- truthful completed/blocked/failed/uncertain outcome;
- reconstruction evidence;
- no synthetic request solely to satisfy M10.

P10.07 remains mandatory before `R35` can close and before `M10` can close.

### 4.2 P10.09 — may proceed now in bounded slices

`P10.09 — Source-grounded use of admitted assets in Workspace / AI / generation` does not depend semantically on a real product action.

It may proceed now as the primary active development stream, split into bounded slices:

- **P10.09-A — Asset discovery and ordinary retrieval:** human-friendly search/filter/open for admitted Company assets by name, role, project and current/superseded version, with exact provenance available on demand;
- **P10.09-B — Asset-aware generation:** select exact admitted templates/brand assets/source materials from ordinary Workspace UI and use them as explicit exact-version generation inputs without internal identifiers;
- **P10.09-C — Asset-grounded Copilot fit-check and bounded use:** determine whether current Product Contract `0.2.0` fully covers the intended AI grounding. If the intended reliance materially expands the contract, publish the minimum sufficient new Product Contract version before implementation. AI output remains transient/proposal-only and document contents do not become validated Knowledge merely through retrieval or summarization;
- **P10.09-D — Derived previews/indexes:** bounded previews/text extraction/search indexes may be added as non-authoritative projections with Organization/access/classification/purpose controls and exact source attribution.

P10.09 must not silently add CAP-002 Knowledge reliance, a public/stable search API, cross-Organization reuse or new authority semantics.

### 4.3 P10.08 — preparatory product-owned composition may proceed; reusable generalization still waits evidence

The original wording "After the first action works, determine what is genuinely reusable" remains correct for **platform generalization**.

However, bounded preparatory work may proceed now:

- inventory concrete product operational entry points already allowed by current Product Contracts;
- improve product-owned context/read-only surfaces;
- prepare no-side-effect `workspace.product-operation.enter` routing for explicitly supported products;
- identify missing Product Contract operations without implementing hidden coupling or consequential effects.

No common stable product-action abstraction is inferred before P10.07 provides real evidence.

### 4.4 P10.10 — dogfooding may start partially

Asset-side real daily-use dogfooding may begin as soon as P10.09 slices land.

Full `P10.10 = PASS` still requires the real P10.07 action journey and disposition of material friction across both asset and action work.

### 4.5 Continuous lanes

The following remain independently executable where bounded by current contracts/authority:

- product-owned Workspace usefulness improvements;
- reliability / DX / observability / recovery / dependency-security work;
- evidence-backed performance work from real owner use;
- external-integration design/implementation only when INT-B7's real endpoint prerequisites become available.

## 5. Product Contract fit rule for P10.09-C

Current Company Workspace Product Contract `Provisional 0.2.0` explicitly admits asset admission, reviewed generated-output promotion, Actionable Work projection and no-side-effect product-operation entry. It preserves the rule that admitted documents/extractions/summaries do not automatically become validated Knowledge.

Before adding admitted Company assets as material AI/Copilot context, the implementation MUST perform an explicit Product Contract fit review.

Result must be one of:

- `COVERED` — exact intended bounded use is already inside the effective contract and existing platform application boundary;
- `CONTRACT_EVOLUTION_REQUIRED` — publish a new immutable Product Contract version before governed reliance;
- `DEFER` — insufficient need/evidence or rights/security boundary unresolved.

No hidden AI-to-asset dependency is allowed.

## 6. Functional cross-review

Maximum: 7 iterations.

### Iteration 1 — architecture / evidence integrity

Finding: the old sequencing conflated an M10 evidence prerequisite with a global development prerequisite.

Revision: keep P10.07 mandatory for R35/M10 but remove it as a blocker for independent asset usefulness work.

Result: `PASS after revision`.

### Iteration 2 — Product Contract / Knowledge / AI boundary

Finding: moving P10.09 forward could accidentally treat existing Company asset admission as permission for arbitrary AI grounding or Knowledge promotion.

Revision: P10.09-C now begins with an explicit Product Contract fit decision and preserves RFC-0007 non-promotion semantics.

Result: `PASS after revision`.

### Iteration 3 — product/platform / closure integrity

Finding: product-entry preparation before P10.07 could tempt speculative platform generalization.

Revision: allow only product-owned/no-side-effect preparation now; reusable platform generalization and R35 remain evidence-dependent on P10.07.

Result: `PASS`.

No material objection remains after iteration 3.

## 7. Decision

> **PASS — correct Phase 10 sequencing so that P10.07 remains a mandatory waiting real-evidence gate, while P10.09 becomes immediately executable and bounded P10.08/P10.10 preparatory work may proceed in parallel.**

This review changes roadmap sequencing only. It does not amend Constitution/RFC/ADR, expand Product Contract scope, promote lifecycle states, create authority, claim Production/readiness, or waive P10.07/M10 evidence requirements.

## 8. Immediate next action

> **P10.09-A — admitted Company asset discovery and ordinary retrieval through Productive Workspace.**

The first implementation slice should make already-governed assets easier to find and use by human-readable name/role/project/version, while keeping technical identities/provenance inspectable rather than primary UX.
