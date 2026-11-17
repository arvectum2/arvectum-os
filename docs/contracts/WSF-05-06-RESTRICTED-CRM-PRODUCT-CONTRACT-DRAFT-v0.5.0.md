# WSF-05/06 — Restricted operational CRM and control read slice

Status: Draft, not effective; exact Owner review required before activation.
Proposed successor: 0.5.0 (restricted combined slice, not the full proposed WSF-05 control input or WSF-06 CRM drafts).
Predecessor: Provisional 0.4.0, whose exact scope and expiry are preserved. The broader WSF-05 and WSF-06 drafts remain candidates, not effective versions.
Authority: Company Workspace First and the owner-approved 30-day manual pilot. No new authority is implied by API access, AI assistance, CI or publication.

## Exact proposed activation scope

- One existing human owner-local principal and organization, current Workspace session and independent P7.04 operations: workspace.crm.read, workspace.crm.party, workspace.crm.opportunity, workspace.crm.export, resource crm-lite, local only. No new organizational authority.
- Real organizational counterparty/business names and non-sensitive descriptions; opportunity title, stage, next action and optional next-contact time; links to already admitted PRJ/NOTE records. No named people, personal contact data, confidential contract terms, financial values, raw correspondence or credentials. Contact and interaction entities remain disabled, including contact references. Free-text handling restriction is an operator rule, not a claim that content classification detects every prohibited input. No automated import, email, external transmission or message sending.
- Party and opportunity changes use private immutable revision history and idempotency; closed outcomes require reviewed evidence reference. A won stage is not contract or revenue. Follow-ups are derived CRM coordination, not canonical obligations or owner action. Current unrelated risk, financial, WORK/OBL and decision sources remain unknown/not connected; no automatic creation.
- Private physical internal primary workspace-company-crm/crm.json; 2 MiB / 500 events, explicit initialization; dedicated encrypted external ArvectumSSD/Arvectum/backups/arvectum-os/crm-lite/latest.private.json, exact UUID and mount verification. No silent fallback. Separate copy before/after writes, daily and before release updates using existing exact-current backup operator; actual service access and restore must be verified. Missing primary never silently initialized. No old data relocation.
- Validity: from independently recorded actual activation until the existing pilot expiry 2026-12-17T09:35:36.060836Z, never longer than 30 days. No renewal or deletion by implication. At expiry deny normal access and review retention/authorized offline export/purge separately; separate irreversible purge authority. Additional cost 0 RUB.
- Existing 0.4.0 manual read supports derived project timeline and the actual existing pilot review signal; these reads create neither canonical work nor approval. Six AC-406 sections remain unknown unless their actual sources independently admitted.

## Implementation and activation gates

Integrated candidate merges exact PR #31, #32 and #29 evidence, excludes UI redesign #30. Runtime candidate CRM approval pin deliberately unset. No production CRM provider, grant, store, or policy enabled by this draft. Only after exact approval and publication: set immutable reviewed draft pin in runtime, wire productive provider, review exact CI/approval gates, perform governed deploy and separately explicit operator activation. Candidate operator requires exact version, publication, explicit decision and confirm; writes receipt last, distinct grants/backup, no reinitialize. Verify actual BFF read/write backup and launchd backup after activation, preserve existing 12 projects and 12 notes, record evidence. Do not infer success of actual user journey or expand to risk/finance, contact or communication data. Any broader source/handling requires its own admission.

User acceptance: use actual non-sensitive parties/opportunities, observe follow-up and revision, inspect backup health, retain prior project/notes. Comprehensive UI redesign remains WSF-08, not this scope.
