# R34 — M10-alpha Asset Governance / Usability Review

**Version:** 0.5.0
**Status:** Closed / PASS — B1 live owner cycle + B2 durability/recovery evidence satisfied; final functional cross-review 7/7 complete
**Date:** 2026-09-15
**Review target:** first real owner-operated Arvectum Company asset cycle  
**Gate verdict:** `PASS`
**Milestone:** `M10-alpha — Achieved / PASS`

## 1. Review objective

R34 is the mandatory M10-alpha governance/usability gate after P10.05. It determines whether the first real owner-operated Arvectum Company asset cycle is usable, governance-correct, durable and reconstructable under actual organizational evidence.

A PASS may not be inferred from implementation completeness, automated tests, synthetic fixtures, a prepared runbook or prior closure reviews alone.

## 2. Canonical authority checked

R34 remains subordinate to:

- Constitution `1.2.0` — `Ratified`;
- RFC-0001 through RFC-0008 — `Accepted 1.0.0`;
- ADR-0001 — `Accepted`;
- ADR-0002 — `Company Workspace Durable Governed State`, `Accepted 2026-08-29`;
- P10.02 Company Workspace Product Contract `0.2.0` — `Provisional`;
- canonical roadmap and Phase 10 roadmap;
- P10.03/P10.04/P10.05 implementation and closure evidence;
- R34-D1 durable-state implementation merged to `main` at `5f65061095094d9b58a4b293b2a5a8f01d88ad10`;
- R34-D2 Productive Workspace wiring/qualification merged in PR #34 at `152bacd55436ebc46b36bd61d4e43f89e6b45eb6`, with final pre-merge head `5e040f560f58fcdb90d21abfac1eb333ab3225a1`;
- [`R34-B1 — Owner-Operated Company Asset Cycle Execution / Evidence Runbook`](R34-b1-owner-operated-company-asset-cycle-runbook.md) `0.2.0` — `Executed / PASS`;
- [`R34-B1 — Real Owner-Operated Company Asset Cycle Evidence`](R34-b1-owner-operated-company-asset-cycle-evidence-2026-09-15.md) `1.0.0` — `Executed / PASS`.

No conflict with higher-authority canonical semantics is identified.

## 3. Current gate state

Both R34 blockers are closed.

### B1 — real owner-operated evidence — CLOSED / LIVE PASS

The final qualifying cycle used the owner-provided Arvectum official-letter template after the owner-requested footer/contact correction. The owner explicitly attested that the resulting exact template is a Company-owned ООО «Арвектум» asset and that the recorded handling is correct. The exact version then completed staged receipt → explicit review → Governed Execution admission → same-root restart/no-replay → Accepted projection → genuine later exact-version use.

Generated output remained `TransientOutput`; a safe nonexistent-version request failed closed without mutation. No P0/P1 was observed. Canonical evidence: [`R34-B1 live evidence`](R34-b1-owner-operated-company-asset-cycle-evidence-2026-09-15.md).

### B2 — restart-durable governed state — CLOSED / TECHNICAL PASS

ADR-0002 + R34-D1/D2 remain valid for the declared owner-local Productive Workspace scope. The live B1 cycle independently confirmed exact identity/Event/digest/provenance reconstruction after restart while durable admission remained one committed/attempt/effect history.

## 4. Current R34 scope matrix

| Review area | Final evidence | Final finding |
| --- | --- | --- |
| Owner usability | real owner-operated B1 cycle + live Workspace UI | `PASS`; two P3 follow-ups, no P0/P1 |
| Exact version / provenance | exact staged/admitted IDs, digest, Document/Asset/Event/provenance; restart exact-match | `PASS` |
| Authorization / Organizational Authority / Data Governance | separate P7.04 grant + six Governed Execution gates + explicit owner attestation/command | `PASS` |
| Data handling / logging | owner-local content-addressed bytes; minimized repository evidence; no reusable credential/session data committed | `PASS` |
| Partial failure / retry | D2 idempotency/uncertainty + live exact-version 404 with no mutation | `PASS` |
| Generated output | exact admitted source used; output stayed `TransientOutput`; no promotion forced | `PASS` |
| Recovery / update compatibility | ADR-0002/D1/D2 + live same-root restart/no-replay | `PASS for declared scope` |
| Product/platform coupling | existing Company-local path; no new shared semantic/business rule | `PASS` |

## 5. Findings

### F1 — live owner evidence is complete

The real Company-owned asset and explicit owner ownership/handling attestation satisfy the B1 milestone integrity requirement; no synthetic fixture or AI substitute is used as Company evidence.

### F2 — durable/reconstructable state remains valid

B2 remains `CLOSED / TECHNICAL PASS`, and the live final asset reconstructed exactly after restart without replay.

### F3 — authority boundaries remained distinct

Upload/review were non-canonical. Admission required current Authorization plus independent Actor Assurance, Organizational Authority, Data Governance, Validation and Consequential Approval evidence. Recovery did not become authority for a new operation.

### F4 — exact-version/provenance truthfulness passed live

The admitted SHA-256, Document version, Asset designation, Event and provenance were exact before/after restart and at point of later use.

### F5 — generated-output classification remained correct

The exact admitted template was used for genuine subsequent Company work. Output stayed `TransientOutput`, with `canonical_authority=false` and `validated_knowledge=false`; no artificial promotion was performed.

### F6 — safe negative failed closed

The real Material ID paired with a nonexistent Version ID returned `404 COMPANY_MATERIAL_VERSION_UNAVAILABLE` with no new output or canonical effect.

### F7 — no hidden product/platform coupling or lifecycle promotion

The cycle exercised existing Company Workspace paths and ADR-0002 product-local persistence. It creates no new Kernel primitive, public persistence API, Stable Product Contract, Active Platform Capability or Production/readiness claim.

### F8 — P3 fresh-runtime bootstrap documentation

A fresh isolated runtime requires explicit P6.05-L4/P7.04 bootstrap before `provision-*`; current runbook documentation should make this prerequisite clearer.

### F9 — P3 Accepted-tab navigation friction

After restart the Company Materials page defaults to Draft while `Accepted = 1`; the accepted asset remains present and usable but needs one extra navigation step.

## 6. R34-D2 qualification evidence

R34-D2 qualifies the exact existing Company admission/promotion owner path rather than introducing a new generic route or P10.08 entry point.

Productive composition evidence:

- `reference/python/p9_03_workspace.py` builds the existing P10.04/P10.05 path with `build_durable_company_governed_executors(settings.runtime_root)`;
- Company Asset Library and generated-output composition share the same durable admission dependency;
- generated-output promotion uses the paired durable promotion executor;
- existing P7.04 operation-specific grants and all RFC-0005 authority/gate semantics for **new** consequential effects remain unchanged.

Qualification evidence includes:

1. Productive Workspace actually uses the ADR-0002 durable pair;
2. committed admission survives restart with exact semantic state, Event, digest and provenance;
3. lost-response retry returns the durable committed result without repeating the effect/Event, including after the new-operation grant is revoked because this path reconstructs prior history rather than authorizing a new effect;
4. reviewed generated-output promotion survives restart while the source remains `TransientOutput` and `canonical_authority == False`;
5. coherent backup → restore of governed metadata, retained source/output bytes and generated-output review evidence reconstructs exact state and digests;
6. corrupt JSON, partial relational history and unknown schema fail closed;
7. unpublished stale temp files are not interpreted as committed state;
8. unsafe runtime/record symlinks fail closed and POSIX owner-local permissions remain restrictive;
9. governed metadata does not duplicate raw Company document bytes/content payloads;
10. exact typed uncertainty, retry token and fingerprint survive reconstruction;
11. unresolved pre-effect evidence survives restart and blocks blind retry/rebinding;
12. recovery reconstructs history and never treats historical replay as permission for a new effect.

At technical evidence head `434976f24c9767f0e6b79c12beb66afcd9e54975`, and again at final PR head `5e040f560f58fcdb90d21abfac1eb333ab3225a1` after canonical status synchronization:

- Productive Workspace CI — `PASS`;
- Reference Python CI — `PASS`;
- functional cross-review — no unresolved material technical objection.

PR #34 merged to canonical `main` at `152bacd55436ebc46b36bd61d4e43f89e6b45eb6`.

## 7. Functional cross-review state

This closure is the final allowed R34 functional cross-review iteration: **7/7**.

1. **Governance/authority:** PASS — explicit owner attestation plus independent current gates; no hidden authority.
2. **Architecture/product boundary:** PASS — Company-specific behavior remains product-local; no product business semantics moved into shared platform behavior.
3. **Events/idempotency/recovery:** PASS — one admission remained one committed/attempt/effect history across restart; no replay.
4. **Security/privacy/data governance:** PASS — repository evidence is minimized and contains no reusable session/credential secret or unnecessary raw Company payload.
5. **Exact-version/provenance:** PASS — exact source/version/digest/Event/provenance are reconstructable and pinned at use.
6. **Generated artifacts:** PASS — genuine later use occurred and output stayed `TransientOutput`; no false Knowledge/canonical promotion.
7. **Usability:** PASS for M10-alpha — no unresolved P0/P1; two bounded P3 follow-ups.

**Material objections after iteration 7:** none.

This functional review is not RFC/ADR acceptance, Product Contract lifecycle promotion, Platform Capability promotion or Production-readiness approval.

## 8. Completed remediation sequence

```text
ADR-0002 Accepted ✓
        ↓
R34-D1 durable implementation ✓
        ↓
R34-D2 Productive Workspace qualification ✓ / B2 CLOSED
        ↓
R34-B1 real owner-operated cycle + explicit owner attestation ✓ / B1 CLOSED
        ↓
R34 final cross-review 7/7 PASS ✓
        ↓
M10-alpha Achieved / PASS ✓
        ↓
P10.06 ← NEXT
```

## 9. Real owner evidence packet

The required packet is satisfied by [`R34-B1 — Real Owner-Operated Company Asset Cycle Evidence`](R34-b1-owner-operated-company-asset-cycle-evidence-2026-09-15.md) `1.0.0 — Executed / PASS`.

It covers owner/Organization context, explicit Company ownership/handling attestation, exact staged/admitted identity and digest, review, Governed Execution admission, Accepted projection, restart/no-replay, point-of-use provenance, genuine later use, generated-output classification, safe negative behavior and owner usability disposition. Supporting owner-local evidence manifest SHA-256: `a1e3e036ab4f7f8338c9205f10db5fae6273a8663f3ea0d8a9f45bbc57fe03a1`.

## 10. Exit criteria result

All R34 exit criteria are satisfied for the declared owner-local Productive Workspace scope:

- B2 durability/recovery evidence remains valid;
- real owner-operated B1 evidence is complete and reviewed;
- no unresolved P0/P1 exists;
- no structural objection remains around ownership, exact-version pinning, provenance, data handling, authority/gates, retry/reconciliation or recovery;
- genuine later use of the exact admitted version is demonstrated;
- generated output remained transient and promotion was not fabricated;
- the owner path is usable enough for M10-alpha without semantic inflation into shared platform behavior.

## 11. Current review decision

**R34:** `Closed / PASS`
**Gate verdict:** `PASS`
**Functional cross-review:** final iteration `7/7`; no unresolved material objection
**Blocker B1:** `CLOSED / LIVE PASS`
**Blocker B2:** `CLOSED / TECHNICAL PASS`
**R34-B1 runbook:** `0.2.0 Executed / PASS`
**R34-B1 evidence:** `1.0.0 Executed / PASS`
**M10-alpha:** `Achieved / PASS`
**Next executable action:** `P10.06 — Real Action Request / Actionable Work boundary`
**RFC amendment required:** none  
**Product Contract lifecycle transition:** none (`Provisional 0.2.0` remains current)
**Platform Capability promotion:** none
**Production/SLA/RTO/RPO/multi-process claim:** none
