# Decision — Start P10.10 genuine owner dogfooding on the selected Mac mini

Status: `Approved`
Date: `2026-09-17`
Owner: `ООО «Арвектум»`
Task classification: `governance` with `platform` and `product_contract` boundary checks
Authority: Constitution `1.2.0`; RFC-0001 through RFC-0008 `Accepted 1.0.0`; ADR-0001 and ADR-0002 `Accepted`

## Decision

The owner authorizes the start of `P10.10 — Real daily-operations dogfooding + friction closure` through genuine owner use of the Productive Workspace on the selected Mac mini.

The selected-Mac runtime may be updated from its currently installed exact historical `arvectum1/arvectum-os` release provenance to the exact lifecycle-current canonical `arvectum2/arvectum-os` `main` using the existing P7.06 governed update path.

The update must preserve:

- exact release identity;
- verified pre-update backup;
- compatibility/migration preflight;
- controlled stop/re-pin/start;
- post-update runtime/observer exact-release health;
- rollback evidence;
- no historical external-effect replay.

After exact-release health passes, Productive Workspace may be started for a genuine owner session. Real usability/operational friction observed during that session may be recorded and repaired under the existing Phase 10 governance and Product Contract boundaries.

## Non-authorizations

This decision does not authorize:

- synthetic `P10.07` action evidence;
- arbitrary Tender Operator, Discount Parser or other product side effects;
- Product Contract `Stable` promotion;
- Platform Capability `Active` promotion;
- customer/public Production;
- public/stable API/browser compatibility;
- SLA/support/certification expansion;
- AI authority, approval or automatic Knowledge promotion.

## Failure disposition

Any failed preflight, release-integrity check, backup verification, runtime/observer health check, Workspace exact-release check or authority boundary must fail closed. A failed update is not P10.10 evidence and must not be represented as successful owner dogfooding.
