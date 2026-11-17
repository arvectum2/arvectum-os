# WSF-04C — Arvectum Company ↔ Productive Workspace Product Contract
Status: Draft — NOT effective; approval and exact implementation review required.
Version: 0.4.0 (proposed)
Date: 2026-11-17
Owner: ООО «Арвектум»
Predecessor: [Provisional 0.3.0](P10-09-C-ARVECTUM-COMPANY-WORKSPACE-PRODUCT-CONTRACT-PROVISIONAL-v0.3.0.md), approved normative blob 0b21eb3f05a0cdae5a10dfdd27f9d8c4292.
Baseline: Constitution 1.2.0, RFC-0001…0008 Accepted, ADR-0001/0002 Accepted; Company Workspace First, AC-401…406.
This draft preserves the complete predecessor contract. No new platform capability, authority or lifecycle promotion. Company-specific semantics stay product-local.

## 1. First durable manual slice
Enable one owner-local workspace to name customer/internal workstreams, capture short manually entered work notes, associate them with an existing workstream, see latest version and history, and export/recover its own data. This is local Company working information, not a governed Document admission, validated Knowledge, task assignment, obligation, legal party register, contract, approval, financial fact or authorization. A note is an attributed observation/interpretation; its contents are not automatically authoritative. No CRM contacts, mail, calendar, messages, embeddings, AI reuse or external effect in this version.

## 2. Proposed operation boundary
All operations require server-resolved exactly one Organization and attributable enabled human Actor, revalidated P7.04 access and a separately admitted manual-context policy/grant. Do not infer permission from workspace.open alone. Enforce exact operation/resource, browser release/session/CSRF for writes, bounded body and server-generated IDs/timestamps. Fail closed for missing policy, stale session, mismatched scope, corrupt data, unsupported schema, unknown resource and conflict. No browser Web Storage or ambient repository access.
- workspace.context.project: create local PRJ identity and label, kind customer/internal; optional existing Company PORT association deferred.
- workspace.context.capture: new note (title/text, optional existing project link); server-generated stable ID, manual provenance, actor and UTC observation, client-generated UUID idempotency key. No source or actor identity supplied by browser.
- workspace.context.revise: append explicit correction to exact current note revision; preserve previous revision; duplicate requests return prior result, mismatched replay or predecessor rejected. Linking/unlinking is explicit human local metadata, not canonical relationship.
- workspace.context.read: latest notes/projects and explicit revision history within same admitted scope.
- workspace.context.export: owner-local private versioned snapshot, checksum; no data transfer to Git, cloud or external app.
- workspace.context.purge: explicit irreversible deletion of the whole pilot store and its approved backup copies, requires separate exact local owner approval; individual deletion/retention policy not yet implemented. No automatic live intake until deletion/retention path reviewed and exercised.

## 3. Handling proposal
Restricted internal notes only: purpose daily project coordination; manually entered minimal title and work summary; no credentials, personal data/contact details, customer confidential content, raw emails, attachments, regulated records or secrets in first pilot. Scope and rights separately confirmed before activation. Proposed retention: pilot maximum 30 days, then owner review/export/purge; no silent indefinite retention or automatic deletion of required evidence. Real data admission requires Company-approved handling policy, including lawful basis where applicable, access revocation, backup retention and deletion procedure; no legal compliance claim. Proposed pilot implementation must refuse normal use after policy expiry before real deployment.
 
## 4. Product-local storage
Use an owner-only directory distinct from P7.03 and existing governed asset/material stores. Single-writer atomic replace with fsync, lock, schema/version, scope and integrity validation; exact revision and idempotency record retained together. No arbitrary filesystem paths from browsers. Export checksum detects accidental corruption, not authentication against an attacker with filesystem write access. Restore only to a new/empty separately authorized store, exact scope/schema validation, no effect replay, never overwrite a working store; independent recovery drill. Backups of this store must be independently inventoried, protected and tested; P7.03 backup alone is insufficient. Consider bounded volume and storage evolution by measured workload.

## 5. Gates
Draft code may be tested only with synthetic data in isolated temporary directories. Prior to actual writes: exact draft approval and Provisional publication under applicable governance, review handling/purge/expiry, explicit activation/grant binding, secure BFF endpoints, negative access tests, idempotency and recovery, frontend integration and real owner acceptance. No auto-deploy authority. Effective predecessor remains 0.3.0. Current WSF-04A live read-only source observations remain unchanged.

## 6. Evidence
PR #26 merged at 77a5ce0343bf1e677726788c649045e3596fa20b; release p10.09.4 deployed via P7.06 transaction 2bd2501f1ad775f636853c7318a76c6c0384e7e31e8402a3f5cd10b25247b9a7, pre-update backup SHA-256 4054f7ba278b118d08f52450c60e6a101bf89fb4270a745234f4e8ad6ec28c89 verified. P7.02/P7.05/UI3 PASS, Workspace CURRENT_EXACT, Information Hub HTTP 200. Technical authenticated portfolio GET returned 10 sources: seven exact source-backed, PORT-005/006/007 reconciliation-required; test session revoked. No real owner session evidence, reboot test or full backup restore.
