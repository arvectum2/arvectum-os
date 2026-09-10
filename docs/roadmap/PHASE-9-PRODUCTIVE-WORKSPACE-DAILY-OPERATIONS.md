# Arvectum OS Phase 9 — Productive Workspace & Daily Operations

Status: `Complete / PASS`
Version: `1.14.0`
Created: `2026-08-21`
Updated: `2026-08-27`
Owner: `ООО «Арвектум»`
Task classification: `platform` with `product_contract` and `governance`
Parent roadmap: [`ROADMAP.md`](ROADMAP.md)

Current disposition: `P9.12 = Complete / PASS` and `M9 = Achieved / PASS` for the exact `Local / Persistent Internal / owner-operated` Productive Workspace scope. The authoritative Section 9 M9 exit set is satisfied by canonical P9.03–P9.11, R29–R32 and real-owner evidence; no Stable Product Contract, Active Platform Capability, public/stable interface, customer Production, broader conformance or authority promotion is implied. The deferred F08 real task-detail → governed-action journey remains a natural future recheck when a genuine actionable task appears and is not represented as completed natural evidence. Closure evidence: [`P9-12-phase-9-m9-closure-review.md`](../reviews/P9-12-phase-9-m9-closure-review.md).
Milestone: `M9 — Daily-use organizational workbench — Achieved / PASS`
Intermediate milestone: `M9-alpha — Usable Internal Workspace — Achieved / PASS`
Architecture baseline: Constitution `1.2.0`; RFC-0001 through RFC-0008 `Accepted 1.0.0`; ADR-0001 `Accepted`
Predecessor: `Phase 8 / M8 — Complete / PASS`
Activation decision: [`DECISION-2026-08-21-PHASE-9-PRODUCTIVE-WORKSPACE-ACTIVATION`](../governance/decisions/DECISION-2026-08-21-PHASE-9-PRODUCTIVE-WORKSPACE-ACTIVATION.md)

## 1. Purpose

Phase 9 converts the proven Arvectum OS runtime and semantic foundation into a genuinely useful daily work environment for the owner/operator of ООО «Арвектум».

The governing question is:

> Can the owner use Arvectum OS as the normal daily interface for understanding what needs attention, finding organizational information, inspecting context, making governed decisions and working across products without relying on GitHub, terminal commands or internal identifiers for ordinary work?

The legacy P4/P7 browser surfaces remain diagnostic/reference/recovery evidence. Productive Workspace is a separate long-lived internal application boundary governed by ADR-0001.

## 2. Productive Workspace principles

1. Human work first; platform internals second.
2. Derived presentation is not canonical authority.
3. UI state/buttons/session do not create Authorization, Organizational Authority, Data Governance permission or Consequential Approval.
4. Products own product semantics and enter Workspace only through explicit governed boundaries.
5. AI proposes; Governed Execution acts.
6. Real daily usability is evidence; synthetic owner sessions are not.
7. Phase 9 is internal-first and creates no speculative public surface.

## 3. Work breakdown

| ID | Work item | Status | Exit outcome |
|---|---|---:|---|
| P9.00 | Productive Workspace activation + outcome baseline | 🟩 Complete / PASS | Phase 9 activated |
| P9.01 | Real operator jobs-to-be-done + acceptance journeys | 🟩 Complete / PASS | six owner journeys fixed |
| P9.02 | Application architecture spike + frontend/BFF/session decision | 🟩 Complete / PASS | preferred topology selected |
| R29 | Productive Workspace Boundary Review | 🟩 Complete / PASS | ADR-0001 Accepted |
| P9.03 | Real application shell + navigation + Organization/user context | 🟩 Complete / PASS | ADR-0001 application shell |
| P9.04 | My Work / Needs Attention projection | 🟩 Complete / PASS | actionable owner queue |
| P9.05 | Human-friendly Records / Documents / Knowledge + global search | 🟩 Complete / PASS | understandable discovery/context |
| P9.06 | Executions / Decisions / governed actions UX | 🟩 Complete / PASS | authority-safe action UX |
| R30 | M9-alpha Usability / IA Review | 🟩 Complete / PASS | ordinary path usable |
| M9-alpha | Usable Internal Workspace | 🟩 Achieved / PASS | core browser work usable |
| P9.07 | Product-owned Workspace surfaces / composition | 🟩 Complete / PASS | two real product surfaces |
| P9.08 | Arvectum AI Copilot | 🟩 Complete / PASS | source-grounded bounded assistance |
| P9.09 | Activity / notifications / attention routing | 🟩 Complete / PASS | non-authoritative activity UX |
| P9.10 | ООО «Арвектум» organization composition | 🟩 Complete / PASS | company-level composition |
| R31 | Product Composition / AI Safety Review | 🟩 Complete / PASS | product/AI boundaries PASS |
| P9.11 | Real daily-use dogfooding + friction/backlog closure | 🟩 Complete / PASS — F11A/F11B bounded owner PASS | real owner sessions + material friction closure |
| R32 | M9 Productive Workspace Hardening + Milestone Code Health Gate | 🟩 Complete / PASS | pre-closure hardening PASS |
| P9.12 | Phase 9 / M9 closure review | 🟩 Complete / PASS | exact-scope M9 closure |

## 4. Accepted application architecture

ADR-0001 is binding for the current `Local / Persistent Internal / owner-operated` Productive Workspace scope:

- React + TypeScript SPA;
- same-origin co-deployed Python BFF;
- opaque revocable server-side session;
- explicit server-side Organization/Actor and current Authorization/Data Governance checks;
- CSRF/Origin/Host protection for unsafe requests;
- non-authoritative rebuildable read models/projections;
- product UI compile-time composition through explicit registered boundaries;
- exact-release SPA+BFF deployment through P7.06;
- no public/stable BFF/API/browser compatibility promise.

## 5. P9.11 dogfooding mechanism

Canonical baseline: [`P9-11-real-daily-use-dogfooding-friction-backlog-closure.md`](../reviews/P9-11-real-daily-use-dogfooding-friction-backlog-closure.md).

The local dogfooding store records bounded Observations, not canonical Events or validated Knowledge. Real owner friction is classified by journey, Workspace surface, severity and boundary. Material/blocker items remain closure-blocking until factually resolved/rechecked or otherwise dispositioned through the allowed governed path.

P9.11 cannot close from repository tests or simulated clicks alone. Real owner work primarily through Workspace is required.

## 6. Real P9.11 findings to date

### F03 — owner-first information architecture

Real owner use found that the Workspace did not make ordinary work obvious enough. `p9.11.2` repaired the navigation/presentation around Today, Work, Information, Arvectum AI and System. Later F07 work superseded the owner-facing labels without changing the stable route/backend identities.

### F04 — canonical repository identity migration

The first p9.11.2 governed deployment attempt failed closed because P7.06 still admitted only obsolete repository identity `arvectum/arvectum-os`.

The merged bounded migration now requires current checkout/new deployment targets from canonical `arvectum2/arvectum-os`, while old `arvectum/arvectum-os` identity may be recognized only as immutable historical installed-source provenance.

Focused F04 validation: `44 passed`; shell syntax and Python compilation PASS.

### F05 — exact-release live Workspace listener continuity

Canonical evidence: [`P9.11-F05 — Workspace listener live-state observation`](../reviews/P9-11-F05-workspace-listener-live-state.md).

The first governed p9.11.2 deployment successfully installed runtime `fdde2cde9b06722cff9716b9f580bb46692c7dcd`, but historical PID `30686` continued to serve `7dc7ceff986df41c1cd8be8668d51280c871e677` / Workspace `p9.11.1`. PR `#3` merged strict exact-process proof, managed spawn provenance, PID-reuse protection, P7.06 Workspace lifecycle reconciliation and launcher `CURRENT_EXACT` readiness.

The owner then approved one bounded graceful termination attempt for exact historical PID `30686`. All required identity/manifest/live-asset gates passed; exactly one `SIGTERM` was sent; PID `30686` exited; port `8769` became free; no `SIGKILL` or second signal was used. The authorization is consumed.

P7.06 transaction `215cb1390708bd4a0e72b567cf9060e4a84173147af618a064c464ca31640ff0` then updated the selected Mac successfully to exact runtime `6ed9dade96417251d3dd5fc8cb175c7136682b63`; P7.02/P7.05 were healthy, Workspace payload was `p9.11.2` / contract `11`, and no product/external effect replay occurred.

F05 is complete in its exact operational reconciliation scope.

### F06 — managed Workspace process identity on macOS paths

Canonical evidence: [`P9.11-F06 — Managed Workspace Start Failure After Selected-Mac Reconciliation`](../reviews/P9-11-F06-managed-workspace-start-failure.md).

The first managed Workspace start after F05 reconciliation created PID `52092`. Uvicorn completed application startup and listened on `127.0.0.1:8769`, but the helper never admitted `CURRENT_EXACT`; after the readiness window it gracefully cleaned up its own child. No application exception occurred.

Root cause was established: `_process_identity()` parsed raw macOS `ps command` display text using shell-oriented `shlex.split()`. Paths under `~/Library/Application Support/...` contain whitespace, so the healthy exact command was rejected before managed provenance could be evaluated.

PR `#4` merged the bounded repair through `3b4d2b2be4a095ff04e5703b36b3ef189c3d4057`:

- right-to-left exact entrypoint recognition preserves legitimate executable paths containing whitespace;
- extracted executable paths are validated as executable files rather than shell-tokenized strings;
- `DIRECT_OS_PROOF` requires genuine executable identity; framework-path divergence remains managed-proof-only;
- exact CWD, release manifest, live assets, PID and process-start identity remain required;
- failed-child matching metadata cleanup and bounded readiness diagnostics are hardened.

F06 is **operationally verified**: runtime `470d4e310973ed873eb71d1bec3cf0985288be6b` reached healthy P7.02/P7.05, Workspace `CURRENT_EXACT` with `MANAGED_SPAWN_PROOF`, exact live assets PASS, and refreshed/opened Desktop launcher.

### F07 — first-glance orientation and Russian-first UX repair

Canonical evidence: [`P9.11-F07 — Owner-first Workspace UX repair`](../reviews/P9-11-F07-owner-first-workspace-ux-repair.md).

The first F07 owner recheck on the pre-remediation UI failed because the next action was unclear, scenario fixtures looked live, raw technical evidence leaked on Home, actions were secondary, and branding was unacceptable.

PR `#6` merged the bounded remediation through `3e0b472a015bde7a44ac8202f364fbf5ea568ebb`, advancing Workspace to `p9.11.3` / app contract `11`. The merged behavior makes Home compact and action-first, keeps ordinary Home/Tasks live-only, isolates scenario evidence under `Настройки → Тестовые сценарии`, excludes scenario attention from ordinary Activity, preserves raw provenance in task detail under `Исходные данные`, uses explicit Russian urgency/navigation, and ships the owner-provided Block SVG as the local brand asset.

A real owner session on live `p9.11.3` now gives **PASS in the bounded F07 scope**: Home is understandable and visually acceptable, the primary actions are clear, the top-level navigation is understandable, and the Arvectum Block logo is accepted.

This does not close P9.11 because the same session exposed F08 downstream.

### F08 — task-to-governed action comprehension and actionability

Canonical evidence: [`P9.11-F08 — Task-to-Governed Action Comprehension and Actionability`](../reviews/P9-11-F08-task-to-governed-action-comprehension.md).

The real owner opened the single urgent task and then the governed execution surface. Result: **FAIL**.

Observed material friction:

- task-detail primary text remained raw English/internal wording rather than owner-facing Russian explanation;
- the focused detail and ordinary queue were rendered together, so the same task appeared again below; the list-level `Открыть` could navigate to the already-focused route and appear broken;
- `Открыть` and `Открыть выполнение` were visually crowded and their semantic difference was unclear;
- governed execution was dominated by `EIS document governed execution`, `Waiting`, `External Reference`, the four English gate names/bases and other internal evidence;
- the prominent `Run governed preflight` control looked consequential, while the interface did not clearly explain in Russian what it did or whether it was safe;
- the governed route unexpectedly highlighted `Настройки`, and long pages lost the primary navigation anchor while scrolling.

Repository inspection establishes the exact semantics that the repair preserves:

- current preflight action is `consequential=false`;
- `canonical_mutation_requested=false`;
- `external_effect_requested=false`;
- `authority_provided=false`;
- running it only re-evaluates retained evidence and records minimized owner-local non-canonical proof evidence;
- P7.06-UI4 deliberately supplies none of Authorization, Organizational Authority, Data Governance or Consequential Approval and exposes no consequential action request until independently governed evidence exists.

The p9.11.4 deployment passed P7.02/P7.05, exact manifest/assets, `CURRENT_EXACT`, `MANAGED_SPAWN_PROOF`, and launcher checks. The real owner recheck still failed: UI4 has no concrete action request or owner resolution path, so its Waiting gates cannot truthfully be owner work.

PR `#7` merged the bounded presentation repair as `2f1bf8f341c1a779805586e9f239c4442a65d96b`, advancing Workspace to `p9.11.4` / app contract `11` and making the mechanics clearer without inventing authority or a decision-supply workflow.

PR `#8` merged the owner-task eligibility repair as `037cd59d7917d52b3ff6aa2dea20dcad22ed484d`, advancing Workspace to `p9.11.5` / app contract `11`. It removes UI4 from ordinary attention and Activity alerts, retains it as `Настройки → Технические проверки`, states that no concrete action is requested, ignores stale task-focus query parameters, returns to Settings, and keeps the diagnostic result task-neutral. Exact reviewed head `dde1102d0892a6c71e7a47de9c3a93fba98c84de` passed Productive Workspace CI and Reference Python CI.

No product business action, authority, approval, canonical mutation or external effect was introduced. The p9.11.5 selected-Mac deployment passes exact runtime/readiness/assets/launcher checks and the structural UI4 owner-task guards.

The subsequent real p9.11.5 owner recheck gives a **bounded PASS for the exact false-task / owner-task eligibility defect**. Owner feedback: `сейчас все чисто, но задач нет, поэтому полноценно проверить не могу`. This confirms that no fabricated urgent task remains and that an empty real-work state is understandable. It does not provide evidence for the real task-detail → governed-action journey because no genuine actionable owner task exists. No synthetic task is admitted merely to complete acceptance. The first naturally occurring real task will be used to recheck that deferred journey without reopening the resolved false-task defect unless new material friction appears.

### F09 — Workspace stop-for-update graceful-shutdown race

Canonical evidence: [`P9.11-F09 — Workspace Stop-for-Update Graceful-Shutdown Race`](../reviews/P9-11-F09-workspace-stop-for-update-graceful-shutdown-race.md).

The first p9.11.5 governed update passed preflight and retained a verified backup, but failed before target activation when the post-SIGTERM stop poll reused HTTP/asset readiness while the known process was exiting. No pointer mutation, transaction, retry, SIGKILL, canonical mutation, product/external effect, or historical-effect replay occurred.

PR `#9` merged the bounded F09 repair as `8d10059c8b45abfd679891a0442bca3073a36dcc`, reviewed head `a451451037f8f77382264418039dac1ed5a9089f`. It keeps pre-signal full exact proof, replaces only the post-signal wait with original-process identity and loopback-listener proof, classifies asset HTTP failure instead of leaking it, and records future pre-activation stop failures as `FAIL` without falsely claiming rollback or whether a signal occurred. Exact-head Reference Python CI `32890992380` passed.

The selected Mac then successfully governed-deployed canonical target `03ba2c72fb9460e97b628c4b3dac36ac496cb942` from source runtime `dc0e0cff83a9031a3686191b5cf304ee03c2d1eb` with Workspace already `NOT_RUNNING`. P7.06 preflight/update passed with transaction `8d8893f5207cbd52eb67e99abad593f6ce069add3314c95373f081abdcd74ae0`; P7.02/P7.05 remained healthy; no Workspace stop or SIGTERM occurred during deployment; the target Workspace was started exactly once and reached `CURRENT_EXACT` with `MANAGED_SPAWN_PROOF`; loopback-only serving, exact index/assets and launcher all passed.

F09 remained **resolved in bounded scope / operationally restored**. The repaired live post-SIGTERM branch was later naturally re-exercised by the F11 running-Workspace update: owner-supplied local evidence reports clean stop/update/restart in one P7.06 pass with no rollback. This adds operational evidence without broadening F09's bounded lifecycle scope.

### F10 — Workspace guidance and organizational asset intake gap

The live `p9.11.6` guide passed bounded owner recheck for understandability. Owner feedback: `руководство есть, оно понятное. но пока система пустая, работать не с чем.` F10A therefore remains PASS only in guide-understandability scope; the missing organizational-material and practical-work surfaces became F11 rather than being silently treated as completed F10B/F10C.

### F11 — Company materials and project portfolio

Canonical evidence: [`P9.11-F11 — Материалы компании и единый портфель проектов`](../reviews/P9-11-F11-company-materials-and-project-portfolio.md).

The owner-approved Product Contract is `Provisional 0.1.0`. F11 owner validation attempt #2 is `FAIL`: the portfolio was initially visible, but every project card became unavailable after ordinary navigation return. F11D-03 is a bounded read-model stability defect, not a Product Contract expansion or Active Platform Capability:

- **F11A:** owner-local `StagedNonCanonical` Company material intake with Organization/Actor attribution, immutable version lineage, SHA-256/provenance/handling metadata, conservative actual-content allowlist, exact DOCX version selection and generated `TransientOutput`; canonical asset admission remains unavailable.
- **F11B:** explicit Company project registry plus read-only `External Reference` canonical-roadmap projection with exact repository/path/commit/content SHA-256/freshness and explicit `reconciliation-required` / `unavailable` states; no roadmap write or remote execution path.

F11D-03 root cause was a live GitHub fetch on every revisit with no last-known-good non-canonical cache. PR #17 merged the repair to canonical `main` at `ef46d23ffe0c724a86f7f49afd4c71345d42265c`, advancing Workspace to `p9.11.9` / app contract `11`. Final reviewed head `52ab60a332000fff70dc9c9d8d8dc43dccc9b4c5` passed Productive Workspace CI `33005196234` and Reference Python CI `33005196245`.

The selected Mac governed-deployed exact merged `p9.11.9` through P7.06 transaction `1bedb028b38c239f2bb2f3632277444d4e56e9a442efd996180e3b300370054e`. The pre-update backup is `p7-03-backup-20260826T194125Z-eac706c115c5180a.tar.gz` with SHA-256 `057d55c06290dbeb68b9cf2ac37bc6f15c71d1a6997919e19964760c6385ca45`. P7.02/P7.05 are healthy; Workspace is `CURRENT_EXACT` / `MANAGED_SPAWN_PROOF`; listener is loopback-only; exact frontend/BFF assets and launcher pass. First source load created a non-canonical Organization-scoped cache; three ordinary revisits returned `cached-within-window`, preserved identical exact commit/content-SHA/fetched-at evidence, and showed no unavailable cards. Explicit refresh succeeded. No outage was manufactured; CI covers stale-cache fallback. No roadmap write, remote execution, authority claim, canonical task creation, or canonical asset admission is available.

Subsequent real owner evidence closes both journeys in bounded scope. F11B owner recheck #3 accepts the stable project portfolio as usable with only minor layout polish. F11A owner attempt #2 on p9.11.10 confirms real generation, release-bound download, Word open, expected formatting and text replacement; the Word trust/provenance prompt is minor/non-blocking. F11A/F11B therefore have bounded owner PASS while Product Contract remains Provisional 0.1.0 and canonical asset admission remains unavailable.

## 7. Closure critical path

```text
R32 hardening + M9 Code Health Gate   PASS
        ↓
P9.12 / M9 closure                    PASS
```

P9.12 closes the numbered Phase 9 critical path. It does not activate a successor numbered phase.

## 8. Parallel work relationship

Parallel work does not change the Phase 9 closure result.

- Lane B integration design is internally complete through INT-B7 and waits for an exact real external endpoint/deployment/account.
- Lane C product↔Workspace work may continue only on evidence and Product Contract/product-local boundaries.
- Lane D reliability/DX/technical-debt work may continue when bounded and evidence-backed.
- Lane E remains discovery only for second-Organization/customer readiness.

See [`PARALLEL-WORKSTREAMS-POST-M9-ALPHA.md`](PARALLEL-WORKSTREAMS-POST-M9-ALPHA.md).

## 9. M9 exit criteria

M9 requires:

1. M9-alpha remains valid;
2. at least two real product-owned surfaces remain composed through explicit boundaries;
3. source-grounded, uncertainty-aware, authority-safe AI Copilot remains valid;
4. Activity/attention remains non-authoritative;
5. company-level composition remains useful without leaking organization/product semantics into Kernel behavior;
6. real owner working sessions are completed primarily through Workspace;
7. recurring material usability friction is dispositioned;
8. security/authority boundaries remain fail closed;
9. applicable ADR obligations remain satisfied;
10. R29–R32 material findings are closed or explicitly accepted by proper authority;
11. M9 Milestone Code Health Gate passes before closure.

P9.12 evaluates all eleven criteria as `PASS` in [`P9-12-phase-9-m9-closure-review.md`](../reviews/P9-12-phase-9-m9-closure-review.md). The result is scoped to the exact internal owner-operated contour and carries forward every limitation in that review.

## 10. Explicit non-goals

Phase 9 does not by itself establish public SaaS, customer Production, universal multi-tenancy, public/stable API or SDK, Stable Product Contracts, Active Platform Capabilities, external browser support matrix, SLA/support commitments, AI Organizational Authority or automatic promotion of Observations/generated outputs into validated Knowledge.

## 11. Post-M9 canonical sequencing

No successor numbered implementation phase is activated by P9.12. Canonical sequencing returns to [`ROADMAP.md`](ROADMAP.md), which remains the sole current-action source.

The deferred F08 real task-detail → governed-action journey remains a natural future recheck when a genuine actionable task appears. It must not be satisfied with synthetic owner work and does not become a retroactive claim of missing evidence.
