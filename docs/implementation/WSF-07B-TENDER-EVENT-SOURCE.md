# WSF-07B — Tender Agent event source candidate

Status: implementation candidate; not admitted as a live source.
Date: 2026-11-17.
OS main 44adbec336c4cc1585afda5c834ea9839b756ad7; Company main 0930bb12b905926a10162e04b293e160808485a2. Deployed p10.09.7 unaffected.
WSF-07A PR #36 exact head 66e69ef8ba912178de89f584e2e9fd224547ed87 all four CI gates SUCCESS, still open; 0.6.0 owner-triggered contract remains draft, no implied approval.

## Exact source inventory

Tender Agent canonical GitHub main a1686d85baf139b7a01b0f29ae8283a266938482, inspected remotely by commit because local checkout is a dirty unrelated branch and does not contain this commit. No checkout modification or database access.
- src/modules/integration_outbox/README.md blob dd79658bfda68383a75f24093e65a471c35027ee: external delivery disabled; separate REVIEW/HUMAN gate.
- router.py bdb3a594d2986ba9d84f27703090822e7d3e4bd5 and service.py 521a1b752d14b622fc0c45f74dd29574211f8879: GET /integration-outbox/events optional tenant filter, no bounded cursor in this route; cannot establish source authorization/completeness from query filter. Do not call the productive endpoint or access DB directly.
- schemas.py bb034b17d3976012adfca7d50602448b0019b016: integration-event-v1 envelope. Key SHA-256 over compact JSON [event_type,aggregate_type,aggregate_id,source_key].
- customer_pilot/router.py lines 549–570: explicit tenant_id=customer_id for analysis_completed / analysis_run and review_required / procurement_case; exact linked project/case/run metadata and completed/operator-review reason. Monitoring and submission_readiness producers omit tenant_id in inspected code. These unscoped events, and unbound/wrong-tenant events, are excluded; do not guess Company ownership from a deal ID or null tenant.

## Minimal interoperable slice

Candidate module workspace_app/wsf_tender_events.py validates a maximum 100 rows, exact v1 envelope and producer key, explicit server-bound organization/actor/tenant/source binding and exact source-project → existing PRJ mapping supplied by a trusted future adapter. Reject whole malformed or mismatched batch; no free text, other event types, source URLs, raw reports, personal/confidential data. Duplicate immutable source event is collapsed within batch; conflicting same key rejected. Group analysis completion and associated operator-review signal by source project/case/run, not by title. No inference of bid decision, legal obligation, tender win, readiness, deadlines or Owner action. No change to source outbox state.

The normalized event IDs are deterministic and can support future persistent dedup across pages/restarts; this candidate does NOT yet implement the durable multi-source event queue, cursor, actual connector or review state. Source project map and source binding must be verified individually, not claimed from this pure function. Metadata references require the same private handling/retention review as other sources. Partial/empty batch is not completeness.

## Gates before live intake

Product-side owner review and exact authenticated read-only paged export contract with enforced tenant, allowlisted safe metadata, stable ordered cursor (created_at,id) and snapshot/continuation semantics, limit <=100, service rights and revocation. Do not reuse existing unbounded optional tenant-filter route as proof of isolation. Evidence and tenant mapping must be verified at actual deployment; current local source/production status not inspected. No direct DB access, no changes to Tender Agent, no webhook/ack or send. Then separately approve source-specific Workspace scope and protected normalized durable checkpoint/review queue with backup/restore, persistent dedup and negative tests. Periodic execution needs separate service identity; owner-triggered 0.6.0 approval alone would not admit this new source. WSF-04 automated intake and WSF-05 full control sources remain open. Mail and calendar require separate exact account/data-handling admission, no broad connector access. Preparation can continue independently.

Evidence: exact candidate 00596c4da6267f9baad2ed9783827f7684f4490b 8/8 focused tests PASS in isolated in-memory import using the Mac mini deployed Python environment, no dependency or live state change. Actual Workspace HTTP 200. No actual Tender Agent events retrieved or imported. Branch independent of PR #36 and deferred UI PR #30; integrate only after separate reviews. Full CI pending.
