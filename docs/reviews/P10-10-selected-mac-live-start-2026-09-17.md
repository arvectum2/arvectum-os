# P10.10 — Selected-Mac live owner dogfooding start evidence

Status: `Live start PASS / P10.10 remains IN PROGRESS`
Date: `2026-09-17`
Owner: `ООО «Арвектум»`
Task classification: `platform` with `product_contract`, `product_specific` and `governance` boundary checks
Authorization: [`DECISION-2026-09-17-P10-10-OWNER-DOGFOODING-START`](../governance/decisions/DECISION-2026-09-17-P10-10-OWNER-DOGFOODING-START.md) — `Approved`

## Purpose

Start genuine P10.10 owner dogfooding against the lifecycle-current Productive Workspace on the selected Mac mini without fabricating P10.07 action evidence.

## Pre-start finding and remediation

The selected Mac mini was still running exact Arvectum OS release `470878b8778fbac009d1ae52092879cf50d8f3f1`, whose immutable release manifest records historical canonical provenance `arvectum1/arvectum-os`.

The lifecycle-current P7.06 verifier admitted only the older `arvectum/arvectum-os` provenance as legacy source and therefore failed closed when migrating the real installed `arvectum1/arvectum-os` release to current canonical `arvectum2/arvectum-os`.

PR #17 fixed only that migration boundary:

- historical installed `arvectum1/arvectum-os` is admitted as legacy source provenance;
- new target releases remain restricted to current canonical `arvectum2/arvectum-os`;
- regression coverage proves current-target admission and legacy-target rejection.

Focused local lifecycle tests: `87/87 PASS`.
Reference Python CI for PR #17: `success`.

## Governed selected-Mac update evidence

P7.06 preflight: `PASS`.

Source exact release:

`470878b8778fbac009d1ae52092879cf50d8f3f1`

Target exact release:

`281febf3c25b44af5f34ad940740a143a92aff74`

Verified pre-update backup SHA-256:

`1dd1675603e86c28f0b8418513ff0c0f43d693836a21d330cb7526f428e9d6e4`

P7.06 transaction:

`49f217b9bfcbc02271fd4199a03f33a8dd6513766ef28f32f5b4005629d9221b`

Post-update status:

- P7.02 persistent runtime exact-release health: `PASS`;
- P7.05 observer exact-release status: `PASS`;
- persistent runtime health: `HEALTHY`;
- durable store schema unchanged: `arvectum.p7_03.durable-store/1`;
- no product/external effect replay was authorized or executed.

## Productive Workspace live start

Productive Workspace was started from the exact target release through `p9_11_workspace_process.py`.

Managed listener state:

- `CURRENT_EXACT`;
- bind: `127.0.0.1:8769`;
- Workspace release: `p10.09.3`;
- internal application contract: `15`;
- classification: `bounded-internal-provisional`;
- public API: `false`.

Root page returned HTTP `200` with title `Arvectum OS — Рабочее пространство` and the expected private security headers.

Safari was opened on the selected Mac at:

`http://127.0.0.1:8769/company-materials`

The actual browser path then recorded:

- initial unauthenticated context request fail-closed as expected;
- browser `POST /api/app/v1/session/bootstrap` → `200`;
- `GET /api/app/v1/company-assets` → `200`;
- `GET /api/app/v1/company/portfolio` → `200`.

This proves the genuine browser/session path reaches the current Productive Workspace and real Company Asset/portfolio projections. It does not prove usability PASS for P10.10.

## Current disposition

`P10.10 = IN PROGRESS / HUMAN`.

The next evidence must come from genuine owner use: finding/opening Company Assets, content search, exact-version generation and/or asset-grounded Copilot. Material friction should be recorded and repaired. Synthetic owner-use evidence is prohibited.

`P10.07` remains separately waiting for a naturally occurring genuine governed operational action and is not satisfied by this session start.
