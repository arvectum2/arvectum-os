# WSF-03 — Unified Context / first implementation boundary
Status: Proposed / engineering inventory verified; product and contract review pending.
Date: 2026-11-17.
Baseline: OS main 2472bf7bacf59e41f0cfef3b29a3e40311edcf39; Company main 36c5dec27bfdece3cc02594e0400db118118f064.
Authority: Company [Workspace First decision](https://github.com/arvectum2/arvectum-company/blob/36c5dec27bfdece3cc02594e0400db118118f064/docs/governance/decisions/DECISION-2026-11-17-WORKSPACE-FIRST.md); [delivery lane](../roadmap/WORKSPACE-FIRST-DELIVERY.md). Not an RFC, Product Contract change, new authority or approval.

## Observed operational baseline

WSF-01: launchd stdout open failed with Operation not permitted after 2026-10-16 external SSD relocation. WSF-02: restored physical internal directory with external source retained; compared 72,867 entries / 64,930 file SHA-256 values, file modes and symlink targets, zero differences before activation. Governed P7.06 update PASS on 2026-11-17 from 5dd77a4db8393335be5fba6fa7756eb6880607c9 to 2472bf7bacf59e41f0cfef3b29a3e40311edcf39; transaction 02ea6a82cc8f0839f45dc6f2b78fa2377521170c312d4d8175eb44b0e52cd8dd; new backup verified SHA-256 34a7ecef483cb39caf4cc76d7fe5d6bfc6a9790d94c8d8f56433ef3f69b2402e. P7.02/P7.05/UI3 PASS, Workspace CURRENT_EXACT, loopback HTTP 200 on 8769, protected API without session 409. Material store had ten files; governed-state store zero files, not evidence of lost canonical records. Prior Operator Service pin corrected. No reboot/restore drill or real Owner browser-session/asset journey evidenced yet; WSF-02 technical recovery only. No P10.07/P10.10 closure.

## 1. Reuse inventory and reconciliation

| Existing implementation | Actual boundary / reuse |
|---|---|
| workspace_app/access.py, security.py | Server resolves exactly one Organization and attributable Actor; no client-supplied scope or permission |
| company_project_registry.json, company_portfolio.py, company_portfolio_verified.py | Explicit allowlisted product roadmap sources, stable Company PORT IDs, commit/path/hash/fetch time, bounded normalization, non-authoritative stale cache; do not make a new portfolio register |
| CompanyProjects.tsx | Read-only roadmap summaries; not customer projects, daily communications or canonical task manager |
| company_materials.py / company_asset_library.py / company_asset_retrieval.py / company_asset_search.py | Staged receipt versus governed admission, exact material/version IDs and handling metadata; bounded existing retrieval; do not bypass admission to populate inbox or treat staged bytes as knowledge |
| company_governed_state_store.py | Durable owner-local admission/promotion and effect evidence only; not a generic CRM DB; don't reuse internal private tables/storage shape |
| actionable_work.py | Real product/company-owned request plus exact Product Contract, provenance and fresh gates; not a generic task inbox |
| attention.py / MyWork / organization.py | Operational attention / navigation composition; not AC-406 business-control source |
| company_asset_copilot.py | Existing exact admitted text scope; no unreviewed mail or external model reuse |

Registry baseline: COMPANY, OS, PORT-001…007 (nine entries), whereas Company PORTFOLIO.md already includes PORT-008 Arvectum Work (discover). Exact canonical Work source fetched successfully: arvectum2/arvectum-work:docs/roadmap/ROADMAP.md (blob 5ad286e53e2fb45e4ee8fe6330beb9e1f6086580 at inspection). Reconcile that approved node via existing explicit registry, retain discover disposition and source-backed projection only. Do not infer project state from regex matches not supported by the source. PORT-005 has no reconciled repo or roadmap, PORT-006/007 lack reconciled roadmap locators; no guessed paths. Existing registry dispositions must be distinguished from current Company portfolio/roadmap overlay; later reconcile stale disposition/priority descriptions using Company decisions, not product status alone. Materials currently accept COMPANY or PORT-nnn only; customer project IDs must not be smuggled through fake PORT IDs or a silent schema relaxation.

## 2. Proposed product-local context model (not Kernel types)

| Concept | Identity and minimum data | Authority / relation |
|---|---|---|
| ScopeRef | organization key + typed kind + stable owning-source ID | COMPANY, OS, existing PORT-*, separately identified customer/internal workstream; never repo path as identity |
| Workstream (proposed PRJ-<opaque ID>, distinct from PORT) | stable ID, label, kind, accountable Position ref if confirmed, status, optional parent PORT, source refs | Company-owned customer engagement or internal work context; no inferred contract/obligation; separate from portfolio node |
| Party / Contact (future CRM Lite) | opaque scoped ID, type, minimal display/contact fields, source refs; optional verified legal identifiers | Company CRM directory for relationship metadata only; not OS Principal, legal identity proof, customer master or authority |
| Opportunity | opaque ID, party refs, workstream ref optional, stage, next step/trigger, evidence, unknowns | Company sales interpretation, not contract/revenue/receivable |
| SourceRef | org, registered source binding ID, native object ID, immutable revision/hash where available, locator, observed_at, source event time if known, rights/purpose/classification/retention and freshness | Original authoritative system retained; no credentials in refs |
| InboxItem | stable item ID, SourceRef, kind, minimal title, capture/observation time, review state and proposed links, optional safe preview if admitted | Product-local receipt/control state only; source facts remain source-owned; AI extraction is proposal |
| ContextLink | scoped endpoints of known compatible types, relation kind, evidence refs, review state, added/changed timestamps | Product-local navigational link by default; no implied canonical relationship, authority, approval or Knowledge; unresolved links visible |
| ControlRef | preexisting WORK/OBL/DEC/APR/ESC/RSK/EXC/INC/POS/PORT or authoritative external reference | link only, never recreate or silently mutate AC-401–406 records |
| Timeline / Mission Control | rebuildable read model from authorized linked sources and Company control inputs | no new authority or canonical facts; stale/conflicted/missing explicit |

No new public/global identity namespace or OS schema is introduced. Proposed PRJ/party/contact/opportunity IDs internal to product require design/contract review before durable real writes. Scope matching includes Organization, source binding and native ID; use stable assigned IDs for manual records, distinct from source dedup key. Do not include contact values/customer names in Git.

## 3. Source-of-truth matrix (Company AC-401–406 remain controlling)

- Portfolio disposition, capital and governance: Company PORTFOLIO/approved decisions; product current execution and roadmap: each exact product repository; Workspace is External Reference projection.
- Customer commitments / dates: actual contract, customer correspondence, acceptance acts and applicable legal evidence; AC-401 WORK/OBL are separate material Company control concerns with exactly one accountable POS. Receipt of email alone neither creates nor closes an obligation.
- Internal material decisions / approvals / escalation: AC-402 DEC/APR/ESC and attributable acts, separate from technical access; AI cannot approve. External approval remains external.
- Risk/exception/incident: AC-403 RSK/EXC/INC, underlying product/provider/customer source preserved; no fake fourth namespace or accepted risk without valid act.
- Finance: AC-404 bank/accounting/contract authoritative facts, separate forecasts, budgets, incurred obligation and actual payment. No bank connector or balance claim now.
- Prioritization: AC-405/PORT review; AC-406 six derived sections Protect Now, Owner Action Required, Delegated Work / No Owner Action, Cash / Commitments / Obligation Signals, Portfolio / Opportunity / Review Triggers, Reference-Implementation Evidence; waiting_external not an Owner task by default.
- Company materials: current admitted exact versions and source provenance, staged separate; external document rights remain external.
- Email/calendar/chat/Codex/ChatGPT: source system authoritative for messages/events/artifacts, not extracted action/approval/knowledge. No full transcript API assumed, no personal/cross-client ingestion. Specific connectors unbound today.
- Contact and CRM pipeline: proposed Company-owned product-local directory / interpretation; legal party identity, contracts, financial facts not inferred.

## 4. Intake, dedup and lifecycle (proposed)

Source key = (org, connector binding, source native object ID); revisions immutable and distinct; replay of same object+revision+digest no-op, changed source revision links predecessor, same revision with different digest = conflict, absent ID/permission = explicit quarantine/error. No title/date/fuzzy join as automatic merge. For Git metadata use repo identity + path/object ref + full commit SHA; for email use actual stable account/provider IDs (not globally trusting Message-ID); no broad source ingestion by default. Manual UUID plus client idempotency key scoped to org/session operation. UTC observed time, retain original source event time and distinction; unknown if unavailable.

Review: new → reviewed/linked or ignored; proposal → confirmed/rejected/superseded; pending/ambiguous link not silently applied. Correction/supersession and revocation visible; no rewriting source history or replaying effects. Access revoked/source deleted: deny retrieval, suppress previously derived content/counts, clear cache according to approved policy, retain only authorized minimum audit metadata. Explicit export and purge per data classification; no raw message log, no external model, no secrets in Git. Derived search/timeline must be rebuildable and source-linked. Versioned local persistence design must include atomic commit, integrity, backup/restore of own state separate from P7.03 scope, idempotency and isolation; no schema change or real writes until admitted.

## 5. Contract gap and next bounded slice

Existing Provisional 0.3.0 incorporates read-only registered roadmap projection and bounded admitted asset/Actionable Work/product entry. It does **not** establish a CRM/contact/workstream store, arbitrary email/calendar/chat access, durable inbox write, new lifecycle/promotions, or generalized reuse. Distinguish product-local experiments using synthetic fixtures from live data reliance. Before WSF-04 actual intake: exact Company-owned source binding, allowed purpose/fields/retention, least privilege, handling/ACL, operational costs, exact Product Contract fit or versioned draft/approval as applicable. No company-specific semantics in platform core; no new shared DB or external model. Candidate first stream: existing allowed GitHub roadmap metadata, then a narrowly authorized corporate mailbox only after scope/rights review. Existing Owner-selected real project pilot remains unassigned; select from actual confirmed Company work, not model memory; no actual client content in repository.

First engineering increment: reconcile approved PORT-008 in existing registry; prove original identities remain, source descriptor and authority are explicit, no source mutation and no invented status. Follow with an isolated context-model + inbox fixture prototype (new product-local tests, no production writes) then review exact live pilot boundary. Use source availability and real Owner journey, not mock adoption, to assess value.

Acceptance: source/authority map reviewed; identity isolation, dedup collision/replay, missing/stale evidence, unauthorized read, no canonical mutation, retention/export and backup/restore tests before live intake; owner feedback not synthesized.

## Source anchors

Company main pinned above: docs/portfolio/PORTFOLIO.md (d22a28d0a629478715d4f9c70f02b38e70d36c11), AC-401 original 0f4444fbd968e176a0a158771a7d0abe93549ecd, AC-402 a48081ba3599e6f3c91b8a6562435ad1f0c152f4, AC-403 857b601423f78fc3d4636dbf9754d5410d8a1c55, AC-404 80c7b620cf446ed28b76143a0325ce89b1939ac0, AC-406 f9e4d0f8e2e2a13f1147a8518461b35cd5264724; applicable approved publications and AC-405 remain controlling. OS contract 0.3.0 exact incorporated draft 0b21eb3f05a0cdae5c3765a10dfdd27f9d8c4292; 0.2.0 draft a92c1d1aac54d565d3d32ce746925620c9d1fd12; F11 0.1.0 incorporated explicit registry boundary. No old contract/version modified.

## 6. Isolated WSF-03 fixture increment — 2026-11-17

Implemented in `reference/python/workspace_app/wsf_context_fixture.py` with no import from the active application composition, no HTTP endpoint, file write, connector, AI use or production data. Scope is an explicitly supplied existing AccessContext (not a substitute for actual server auth); synthetic bindings only; separate PRJ identity and optional explicitly approved PORT parent. Inbox observations carry source binding/object/revision/digest/time, replay returns existing immutable item, same revision inconsistent title/digest/predecessor rejects, successors require exact current predecessor. Link review is separate from source truth and approval; only confirmed links to the latest visible revision contribute to timeline. Revoked binding suppresses items and links from projections; real retention/deletion/access-policy enforcement remains unimplemented. Historical observations retained only in memory; no persistence, durable idempotency, manual capture endpoint, CRM, broader ControlRef or account binding claimed. Prototype is single-session test code, not a usable product release.

Exact code/test commit 12e6f048cd94c9bc67c4e36d8ba78ea5a7eda632: 13/13 focused unit tests PASS executed from exact branch file bytes on Mac mini in isolated process; Workspace remained HTTP 200. The earlier 10/10 registry/portfolio test result remains separate. No live deployment or owner acceptance.

### WSF-04 first live slice proposal (not admitted)

Start from existing read-only portfolio source integration, specifically the already registered Company roadmap (COMPANY scope, arvectum2/arvectum-company:docs/roadmap/ROADMAP.md). Use exact Git commit SHA, path, content SHA-256 and fetch timestamp already exposed by VerifiedRuntimeCompanyPortfolioProvider. No additional GitHub token scope, arbitrary repo enumeration, mail ingestion, customer data or new write capability. Capture a minimal reviewed roadmap revision signal (source-backed title, source revision and freshness, no raw file content). Read-only derived display is the smallest candidate; distinguish a current observation from a true source change by having an earlier verified observation. Do not call first observation a new business event. If persistent intake or review is necessary, propose a versioned Product Contract and Company-owned handling spec: explicit bound SourceBinding, exact fields, scope, authorization, review actor, retention period, revocation, backup/restore and deletion/export, no authority expansion. Manual capture and real customer project ingestion await this gate. WSF-03 fixture does not satisfy these requirements. No email until specific account, rights, data scope and least-privilege binding approved. User should see a real verified signal in Workspace before broad connectors or CRM expansion.
