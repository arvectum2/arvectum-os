# WSF-07A — Local Roadmap Collector

Status: Draft / for explicit Owner review; not approved, not deployed.
Proposed version: 0.6.2 (bounded successor to 0.6.1; other Product Contracts untouched).
Date: 2026-11-18
Baseline: arvectum2/arvectum-os main 11f62dddfe895b247331743b0a3ee5fd7b5e027d, Workspace p10.09.16 / API 15.
Company portfolio baseline: locally observed origin/main b7d92ab (no claim of independent current remote verification).

## 1. Business objective and scope

Owner direction: PORT-005 and PORT-006 are no longer relevant to this collector; continue without them. Prepare independent local collection, not ChatGPT-dependent execution.

Collect registered roadmap metadata every three hours on Mac mini. Keep one authoritative Inbox projection and its review history. The collector is deterministic Python, no AI model, no new paid dependency, no new department or Position solely for this job. Company controls scope and review; Workspace owns its implementation. The Owner remains the decision-maker. This contract does not retire products, alter Company portfolio dispositions, or authorize other product data access.

Active set: COMPANY, OS, PORT-001, PORT-002, PORT-003, PORT-004, PORT-007, PORT-008. Exact locators remain pinned to the approved 0.6.1 registry digest aa21ce050441c50f4b68c9dc7b16ebe43b1a5a29d4a98059a8616b35c2849016. PORT-005 and PORT-006 remain historical descriptors; no network request for them. Show active freshness as x/8, separate from two excluded descriptors. Never erase old observations or reviews. Preserve partial/unavailable status for any failed active source.

## 2. Execution and authority

Use a dedicated, explicitly registered P7.04 service Principal and separate local credential, exact operation/resource bindings, deny by default. Propose only `workspace.inbox.collect` on resource `roadmap-inbox` via local access; private backup verification/copy is an inseparable bounded operation of that path, not a general export grant. Human `read`, `poll`, `review`, `export` grants retain their original semantics. No administrator grant, human session bootstrap, human token reuse, arbitrary GitHub URL, write/push/PR creation, approval, review/dismiss, task creation, or canonical decision mutation by the service. GitHub source access must be demonstrably read-only and restricted to the admitted locators; verify source authentication and replacement path before provisioning; no broader credential by convenience. No new remote listener.

Do not coerce the service identity to human. Current `_identity` and Inbox storage scope bind the human Principal. Design an Inbox-specific resource scope, explicit service actor/credential/grant attribution, and an audited deterministic migration preserving legacy owner records and immutable prior bytes. Do not relax the identity helper used by manual notes, CRM or other stores. Retain independent authorization of the real human owner for reading/reviewing and of the service for collection. Revalidate service authorization, registry, expiry and release before fetching and just before committing. A revoked or expired grant must prevent commit. Changes to source allowlist require explicit governed update.

## 3. Runtime and durability

Use existing `VerifiedRuntimeCompanyPortfolioProvider`, existing metadata validation and change detection, and the existing Inbox where feasible. Adapt the Inbox boundary rather than create a competing store or a second business truth. Record only source identity, fixed locator reference, commit SHA, content SHA-256, timestamps, state, review lineage and proportionate service execution attribution. No raw roadmap bodies in the durable Inbox, no AI processing, no secrets in logs or repository.

One launchd job on internal disk; pinned current deployed release and Python 3.14-compatible environment. StartInterval 10800 seconds; one run on activation and wake behavior subject to due/retry gate, no continuous polling. No overlapping collector runs; coordinate manual and scheduled scans and migration/deploy with the existing lock/transaction semantics. Use deterministic per-window idempotency and bounded retry of the same logical request; reconcile uncertainty before another write. A failure does not erase the last successful observation or advance its checkpoint. No retry storm. Keep the four-hour freshness threshold; stale/failed sources visible in Mission Control. Explicitly separate successful process exit, current source evidence and pending changes. Do not treat a zero-change scan as evidence of no company work.

Pre/post mutation verify current backup on the separate encrypted ArvectumSSD volume and preserve existing daily backup behavior. Fail closed before mutation if pre-backup or scope invalid; post-backup failure is explicit degraded state, with further automatic writes blocked until reconciled. Preserve 2 MiB / 500 event limits; visible capacity warning at 80%, stop at cap, no automatic compaction or deletion. Pilot expires no later than 2026-12-17T09:35:36.060836Z or earlier revocation; no automatic renewal. Disable scheduling without erasing history. Plan for future retention review, not an implicit permanent extension.

## 4. Acceptance gates

1. Isolated fixture: exact eight active locators, two excluded, no arbitrary source; unchanged checkpoints do not produce duplicate pending changes; changed digest creates one pending item; unavailable source does not advance checkpoint. Verify expiry, revoked grant during fetch, wrong Principal/Organization/resource, service cannot review/export any other data, human cannot be substituted, duplicate cycle and overlap prevention, same-key retry, interrupted write and backup failure.
2. Migration rehearsal on isolated copies: legacy human read/review history and source hashes preserved; old bytes retained; migration rollback and backup restore verified; manual notes and CRM unaffected. Explicitly confirm exact data-handling and snapshot compatibility.
3. Technical exact-head review, CI, pinned immutable build. No live provisioning or deployment before separate approval of exact reviewed implementation and migration plan.
4. Selected Mac: approved service identity and narrow source access, verified backup, governed deployment, one explicit live scan, verify eight-source freshness in Mission Control (or truthful per-source failure), zero duplicate effects and actual service attribution. Enable 3-hour launchd schedule only after that scan and activation approval. Verify subsequent scheduled run from actual evidence; do not manufacture it. Reboot recovery as separately approved, no forced reboot in this work.
5. Operational handoff: last successful run, next planned run, failed source details, capacity, backup status, exact release and revocation/disable instructions. Owner usefulness remains separate from technical PASS.

## 5. Decision requested

Approve this exact draft as the scope for isolated implementation and review only: local scheduled deterministic collector; eight active sources; separate service Principal; preservation of original history; zero extra expenditure; no broader product authority or automatic review. Production credential provisioning, migration, contract publication, merge, deployment and schedule activation remain separately governed. No external product changes, Tender Agent changes, bank connection, or change in product lifecycle is included.
