# WSF-06 — Native CRM Lite proposed Product Contract extension

Status: Draft; implementation candidate only; no effective grant or data admission.
Proposed version: 0.6.0; requires reconciliation with exact approved predecessor after WSF-05 (draft 0.5.0 is not yet effective). No supersession by implication.
Date: 2026-11-17
Owner: Arvectum Company.
Canonical baseline: OS main 44c56045f02d40fdd6f72caf6c428f8b1c288b71; Company main 0930bb12b905926a10162e04b293e160808485a2. Workspace First, WSF-06, existing 0.4.0 manual pilot remain controlling.

## Purpose and minimal scope

Native product-local relationship coordination for one owner-operated organization, not a universal platform CRM schema and not an external CRM integration. Existing INT-B4 (blob a63121ed1c4392e3d61919fdbf326554955c2bf9) Bitrix24/amoCRM external-reference designs remain separate. No external API, send, synchronization, financial transaction or external effect. No new OS core primitives.

- PARTY: stable CRM company/counterparty reference, name, bounded description, optional independently admitted registry reference; not a legal identity authority.
- CONTACT: stable party-associated contact display name/role and optional protected channel reference. Contact is not an OS Principal, Assignment or Position. First candidate uses synthetic contact data only; actual personal-data intake and handling require separate explicit authority, applicable legal/data-governance review and exact permission. No raw address-book or mailbox import.
- OPP: stable party opportunity, optional associated contact, title, discovery/qualified/proposal/negotiation/paused/won/lost, next action and optional exact UTC contact time for open stages, optional existing PRJ and admitted evidence links. Closed outcome must reference admitted evidence; no silent reopening. Won/lost is a coordination outcome, not contractual fact, approval, legal act, obligation or cash.
- INT: party/contact/opportunity/project-related observed interaction, allowed meeting/call/email/message/other category, occurrence timestamp, brief summary, exact admitted evidence reference. Record an observation, never send a communication. Revision may correct metadata but cannot reassign party or source occurrence identity.

## Candidate lifecycle

Explicit initialization, optimistic expected revision, immutable revision history and exact idempotency-key replay. Duplicate normalized party name/registry ref, contact name within party, opportunity title within party, or interaction source ref requires manual reconciliation; never auto-merge. Name-based duplicate checks are conservative and do not establish legal identity. Only independently resolved existing project IDs and admitted reference IDs; no new canonical register identities. Per-project filter only directly associated contacts and parties; name/text search, party timeline and record history. Revoked evidence fails closed in candidate (future scoped handling/reconciliation required).

Private product-local JSON ledger, 2 MiB / 500 events independent proposed bound, internal SSD, private 0700 directory / 0600 files, lock, atomic fsync replacement, checksummed schema/scope, restore only to an empty private location; no silent replacement of missing/corrupt store. Proposed independently encrypted external ArvectumSSD backup and restore acceptance before live intake; existing manual-context backup job does not cover CRM. Numeric limits are proposed, not owner approval. No new directories on production, no real CRM data in Git. No online retention purge or claim of full data-subject rights implementation; explicit data lifecycle/retention/export/revocation/correction/erasure procedure required for real contacts. No automatic pilot extension or additional spend.

## API candidate

GET /api/app/v1/crm (query and optional exact project), GET records/{id}/history, GET parties/{id}/timeline, POST submit with exact write and client idempotency key + expected revision, GET export. Uses protected existing BFF session, release/origin checks and CSRF for write. Synthetic FixtureCRMPilot is injected only by tests; default is denied after authentication, no env toggle or production provider. Test fixture read/write/export separation and expiry do not establish real independent grants. Future activation must enforce exact operation/resource grants, current source rights, classification, server-bound scope, explicit policy pin, validity, backup, retention and consent/authority where applicable. No real contact records authorized by 0.4.0.

## Evidence and next gates

Store and tests at 12629479d62f67d345a3e895d8ed09cae1b23c30: 11/11 targeted tests PASS on Mac mini, including reload, stage/closure, relationships, dedup, rights revocation, recovery and no corruption overwrite. At 99c974eeab9388c2bce433493469eac92773bbd8 direct protected synthetic ASGI journey PASS: party/contact/opportunity/interaction creation, project filter, timeline, exact export, CSRF rejection, access revocation terminates session. Full TestClient integration cases committed; local runtime lacks httpx2, so direct ASGI used without changing production dependencies; CI must check full test suite. No real data accessed, no new production grant, policy, release, schedule or directory. Existing p10.09.5 HTTP 200. Before production: integrate WSF-05 and exact successor contract, real data/access/handling owner decision, backup and physical restore, minimal usable CRM form views, primary and reference integrity and real owner acceptance. UI simplification PR #30 remains deferred; essential functional UI is not a redesign.
