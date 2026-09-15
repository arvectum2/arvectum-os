# R34-B1 — Real Owner-Operated Company Asset Cycle Evidence

**Version:** 1.0.0  
**Status:** Executed / BLOCKED — explicit owner ownership/handling attestation pending  
**Execution date:** 2026-09-15  
**Owner:** ООО «Арвектум»  
**Task classification:** `platform + product_specific + governance`  
**Canonical repository baseline:** `arvectum2/arvectum-os@f015e271aa23b330162888e58c90a1c38febf75c`  
**Workspace release:** `p9.11.10`, app API contract `11`  
**Parent:** [`R34 — M10-alpha Asset Governance / Usability Review`](R34-m10-alpha-asset-governance-usability-review.md)  
**Execution procedure:** [`R34-B1 runbook`](R34-b1-owner-operated-company-asset-cycle-runbook.md)

## 1. Scope and evidence handling

This record captures the first real bounded owner-operated Company asset cycle required by R34/M10-alpha. It records system-derived identifiers, digests, timestamps and bounded usability observations; it does not embed reusable credentials, cookies, CSRF values or unnecessary raw Company document contents.

The owner-local evidence bundle remains under the isolated runtime root at `evidence/r34-b1-20260915/`. Its `MANIFEST.sha256` digest is:

`bdd9cc9e981069358faf6d59621ad45359c76db7dbfe8458d1bc2fca128f49d2`

Repository markdown is the canonical review/evidence summary; the owner-local bundle is retained supporting operational evidence, not a new authority source.

## 2. Execution identity and environment

- Organization: `ООО «Арвектум»`; server-resolved Organization scope `aa4e760c379c8952aba6c6c335f3e233`.
- Attributable Actor: `Owner operator`; P6.05-L4 human identity continuity reused rather than replaced.
- Authentication source: P7.04 owner-local credential issued inside the isolated B1 runtime; no prior reusable credential was copied.
- Runtime: owner-local isolated `r34-b1-real-cycle`, loopback same-origin Workspace at `127.0.0.1:8779`.
- Operational `workspace.open` grant and exact `company.asset.admit-staged-version` authorization grant were provisioned separately.
- Preflight reported `organizational_authority_provided=false`; the admission authorization grant reported `consequential_approval_provided=false`. Organizational Authority and Consequential Approval remained separate gates evaluated by the governed admission provider.

## 3. Qualifying Company-owned material

The qualifying material is an original reusable Company business-letter DOCX template created for ООО «Арвектум» under direct owner instruction in the operating session, with no third-party content.

- Filename: `Arvectum-business-letter-template.docx`.
- Project: `COMPANY` / Company-wide use.
- Semantic role: `document-template`.
- Classification: `internal`.
- Purpose: reusable Company business correspondence and internal notices.
- Rights: Company-owned original work for ООО «Арвектум» business correspondence/internal documents.
- Retention: retain until superseded or explicit owner-approved deletion.
- SHA-256: `b0ae05b681d5475d6cd6bc999f301a776d8e983fb50584c7560ce78dc4735c94`.

This is not a synthetic fixture or the pre-existing `Arvectum_F11A_test_template.docx`.

## 4. Staging and owner review

Staging completed at `2026-09-15T09:35:34.681882Z`:

- Material ID: `MAT-738227b58e989828e6f7cf830fabf70d`.
- Staged Version ID: `MV-6ce8a7f9068db4798ad2d6e6803cee21`.
- State: `StagedNonCanonical`.
- `canonical_authority=false`; `validated_knowledge=false`; no canonical state changed on upload.

Owner review completed at `2026-09-15T09:35:57.747375Z` for the exact staged version. Review remained explicitly non-canonical. The review policy fixed:

- deletion only by explicit owner decision after supersession or retention review;
- permitted reuse for Company business correspondence, internal notices and template-based transient document generation.

## 5. Governed canonical admission

Admission completed at `2026-09-15T09:36:34.491309Z` with `canonical_state_changed=true` and `through_governed_execution=true`.

Exact canonical identities:

- Document subject: `document:aa4e760c379c8952aba6c6c335f3e233:organizational-asset-MAT-738227b58e989828e6f7cf830fabf70d`.
- Document version: `document-version:aa4e760c379c8952aba6c6c335f3e233:organizational-asset-MV-6ce8a7f9068db4798ad2d6e6803cee21`.
- Asset designation version: `organizational-asset-version:aa4e760c379c8952aba6c6c335f3e233:company-asset-MV-6ce8a7f9068db4798ad2d6e6803cee21`.
- Admission Event version: `event-version:aa4e760c379c8952aba6c6c335f3e233:company-asset-admitted-MV-6ce8a7f9068db4798ad2d6e6803cee21-d78e7c806a10e3a7d36e0306-v1`.

Provenance includes the attributable principal, execution subject/version, exact staged material/version, governance basis, owner-command approval record, Product Contract/workflow pins and six independent gate-decision versions for Actor Assurance, Authorization, Organizational Authority, Data Governance, Validation and Consequential Approval.

## 6. Restart / recovery / no replay

Before restart the Accepted projection contained exactly one qualifying accepted asset with the exact material/version/digest/canonical identities above.

The isolated Workspace was gracefully stopped at `2026-09-15T09:39:21Z` and restarted from the same repository build and the same runtime root at approximately `2026-09-15T09:39:44Z`.

Post-restart comparison was exact for:

- Material ID and staged Version ID;
- SHA-256;
- Document subject/version;
- Asset designation subject/version;
- Admission Event version;
- admission timestamp;
- complete provenance references;
- current-version status.

After restart the durable admission store still contained exactly `1 committed`, `1 attempt`, `1 started effect`, `1 resolved effect`. Recovery therefore reconstructed the historical result and did not replay the canonical admission or create a second Event/effect.

The owner-facing Workspace page after restart showed `Accepted = 1` and retained the Company/Owner operator context.

## 7. Genuine later use

The exact admitted version `MV-6ce8a7f9068db4798ad2d6e6803cee21` was subsequently selected as the source of a real bounded internal Company document: an operational notice identifying `arvectum2/arvectum-os` as the repository to use for new Arvectum OS checkout/deployment while explicitly stating that the notice is non-authoritative and does not replace canonical governance sources.

Generated output:

- Output ID: `OUT-67acda65356754bb96d67458bc77715e`.
- Output SHA-256: `c6c168436008babaa32b04707a76ec6e2bf7d3210b6f26554742b1fed1e01e12`.
- Exact source Version ID: `MV-6ce8a7f9068db4798ad2d6e6803cee21`.
- Exact source SHA-256: `b0ae05b681d5475d6cd6bc999f301a776d8e983fb50584c7560ce78dc4735c94`.
- State: `TransientOutput`.
- `canonical_authority=false`; `validated_knowledge=false`; `canonical_state_changed=false`.

Downloaded bytes matched the output manifest SHA-256. The rendered DOCX contained the intended title/body/date substitution. Generation left the admitted historical asset and Event unchanged. No generated-output promotion was exercised because the real task did not require canonical promotion.

## 8. Safe live negative path

A bounded exact-version negative was exercised without corrupting durable state: generation used the real Material ID with a nonexistent Version ID.

Result: HTTP `404`, `COMPANY_MATERIAL_VERSION_UNAVAILABLE`.

Before/after transient-output count remained `1 → 1`; durable admission counts remained `1 committed / 1 attempt / 1 started effect / 1 resolved effect`. The request failed closed before any canonical or transient mutation.

An earlier session bootstrap without the required release header also naturally returned `409 RELEASE_MISMATCH` before mutation; the exact-version negative above is the primary R34 live negative evidence.

## 9. Usability observations and defect classification

No `P0` or `P1` issue was observed in M10-alpha scope. Two non-blocking `P3` findings were recorded:

1. a fresh isolated runtime requires explicit P6.05-L4/P7.04 bootstrap before the `provision-*` commands become usable; the prepared B1 runbook did not make this prerequisite explicit enough;
2. after restart, the Company Materials page defaults to the Draft tab even when `Accepted = 1`, adding one unnecessary navigation step before inspecting accepted history.

Neither finding weakens ownership, exact-version pinning, authority/gates, provenance, data handling, recovery/no-replay or generated-output classification. They are follow-up usability/documentation improvements, not R34 blockers.

## 10. R34 evidence matrix result

| Required dimension | Result |
| --- | --- |
| Owner/operator + Organization context | PASS |
| Company-owned material eligibility | `BLOCKED` — explicit owner ownership/handling attestation not yet recorded |
| Staged receipt + exact digest/version | PASS |
| Explicit owner review | PASS |
| Governed canonical admission | PASS |
| Accepted owner-facing projection | PASS |
| Same-root restart/reconstruction | PASS |
| Exact post-restart identity/provenance comparison | PASS |
| Genuine later use of exact admitted version | PASS |
| Safe fail-closed live negative | PASS |
| Generated output classification | PASS — remained `TransientOutput`; promotion not exercised |
| Owner usability / P0-P3 classification | PASS — no P0/P1; two P3 follow-ups |

## 11. Final cross-review blocker

Functional cross-review iteration 7/7 identified one material milestone-integrity objection: the system evidence records an ownership basis for the newly created reusable Company template, but the owner has not yet explicitly attested the required ownership/handling facts in the conversation or another attributable owner record. The runbook explicitly assigns that attestation to the owner and prohibits AI from deciding Company ownership/rights.

No additional technical execution is required. Once the owner explicitly confirms that the template is Company-owned and that the recorded `internal` classification, stated business purpose/rights, retention rule and deletion/reuse handling are correct for ООО «Арвектум», this blocker can be closed and the already-collected live evidence can be subjected to the final R34 closure publication without replaying admission.

## 12. Non-claims

This evidence does not:

- promote the Company Workspace Product Contract beyond `Provisional 0.2.0`;
- promote any Platform Capability to `Active`;
- establish customer/public Production, SLA, RTO/RPO, multi-process writer safety or broad conformance;
- make the generated output canonical or validated Knowledge;
- turn the Company-local durable storage adapter into a platform-wide persistence requirement;
- make this evidence record itself an authority source for future operations.

## 13. Evidence conclusion

**B1:** `OPEN — owner attestation pending`; all technical/live-cycle dimensions otherwise pass.  
**B2:** `CLOSED / TECHNICAL PASS`.  
**R34 evidence sufficiency:** `BLOCKED` only on the mandatory explicit owner ownership/handling attestation.  
**M10-alpha:** remains unclaimed until that attestation is recorded, R34 re-review passes, and roadmap synchronization is merged.
