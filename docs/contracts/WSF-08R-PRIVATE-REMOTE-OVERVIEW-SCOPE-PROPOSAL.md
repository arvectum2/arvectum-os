# WSF-08R — private remote overview scope proposal

Status: draft review input only; not a Product Contract approval, activation or remote grant. Predecessor scope stays intact (local Workspace pilot and independently published source policies, including 0.6.2 Collector). Proposed one-human, one-device, Organization-scoped read-only slice for owner work from MacBook Air; no public/customer access, no additional paid service. Company owns data admission and utility; OS owns identity, security and authorization semantics. Authority: RFC-0003, Accepted ADR-0001, current applicable Product Contracts; no new Organizational Authority.

## Proposed exact application boundary

Same Workspace product/BFF; dedicated private HTTPS origin and reviewed authenticated TLS peer binding. No generic HTTP proxy into the trusted local listener. Locally authorized explicit enrollment of one owner-bound passkey (public key and credential identifier, RP ID, expected origin, reliable credential lifecycle/counter/backup-state handling) and registered device. Challenge single-use, bounded and tied to exact admission; genuine WebAuthn user verification required. A device certificate is not proof of the human; device and human checks are independent. Retain server-side current grant, explicit access_path=remote, exact scope, per-request credential and device binding. No copying or reusing local owner secret, no fallback to local. Use Secure/HttpOnly/SameSite=Strict host-only cookie, bounded revocable sessions, exact Host/Origin, request size/rate limits, CSRF on mutations, no protected data in cache/logs. Session and credential revocation, expired admission, device/role/credential/grant change all fail closed; local fallback stays available.

Proposed route allowlist: necessary remote shell/static release assets, POST /api/app/v1/remote/challenge and /bootstrap, GET /api/app/v1/remote/overview and POST /api/app/v1/remote/logout only. Enrollment/revocation operator action only in local profile, separately authorized. Deny all ordinary local API paths, arbitrary search, detail/history/exports, notes/CRM writes, Inbox poll/review, communications, Copilot, finance/risk details and consequential actions. No client-controlled authority/scope override. No remote company write admitted by this proposal.

## Proposed minimum projection (not source admission)

A single overview read, no new source collection and no automatic data creation. Each existing source must first receive its own reviewed remote read permission and field/canonical-source binding; missing permissions yield a generic unavailable section without leaking data or counts. Do not simply call local-only providers using local grants.

| Section | Candidate allowed fields | Excluded |
| --- | --- | --- |
| Work/obligations (AC-401 admitted references) | title, control state, priority, the declared next control point, due/trigger display, source freshness | original contract bodies/signatures, full evidence paths, source IDs revealing prohibited data |
| Preparing decisions (AC-402 admitted reference) | title, preparation state, review date, next review trigger | raw decision evidence/approval controls or authority assertion |
| CRM coordination (restricted CRM) | admitted non-sensitive organization name, opportunity title/stage, next action, optional scheduled follow-up, explicit unscheduled status | contacts, personal data, note bodies, source bodies, financial terms, export |
| Roadmap Inbox | saved current/active count, pending count, last verified scan, backup/coverage state | source bodies, manual scan, review/dismiss/export, excluded-source discovery |

Fields remain candidates requiring exact Company source review and current per-section remote authorization. Display truthful partial coverage and source currency; zero, omitted and unavailable are distinct. Do not expose local detailed objects, notes, private evidence locations or confidential client facts. No replication database. Expiry bounded by existing pilot (2026-12-17T09:35:36.060836Z), no automatic renewal; if a later rollout is needed, approved successor required. No costs or new dependency approved here.

## Acceptance before live use

Separate exact contract publication and implementation review. Private route/ACL and trusted TLS verification on actual MacBook, genuine local enrollment and hardware-backed authentication where feasible, denial of unauthorized device, unregistered credentials and remote-grant absence, replay/expiry/counter/origin/RP ID/user verification, no local fallback, full source-specific policy denial, scope and revocation checks, no secrets in logs, bounded session/load, controlled recovery, existing local profile regression, exact CI and separately approved deploy/provisioning. No remote mode until those gates are met. Actual owner feedback required for pilot acceptance. Browser read-only usefulness reviewed before introducing any write.
