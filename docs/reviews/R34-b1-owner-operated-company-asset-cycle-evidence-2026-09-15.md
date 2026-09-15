# R34-B1 — Real Owner-Operated Company Asset Cycle Evidence

**Version:** 1.0.0
**Status:** Executed / PASS
**Execution date:** 2026-09-15
**Owner:** ООО «Арвектум»
**Task classification:** `platform + product_specific + governance`
**Canonical repository baseline:** `arvectum2/arvectum-os@f015e271aa23b330162888e58c90a1c38febf75c`
**Workspace release:** `p9.11.10`, app API contract `11`
**Parent:** [`R34 — M10-alpha Asset Governance / Usability Review`](R34-m10-alpha-asset-governance-usability-review.md)
**Execution procedure:** [`R34-B1 runbook`](R34-b1-owner-operated-company-asset-cycle-runbook.md)

## 1. Scope and evidence handling

This record captures the first real bounded owner-operated Company asset cycle required by R34/M10-alpha. The qualifying source was the owner-provided Arvectum official-letter template, adapted only for the existing Workspace `{{DATE}}` / `{{TITLE}}` / `{{BODY}}` generation contract and corrected by owner instruction so the duplicate reply-details block was removed and the footer uses `info@arvectum.com` and `+7 916 594-35-07`.

The record contains system-derived identifiers, digests, timestamps and bounded owner observations; it does not commit reusable credentials, cookies, CSRF values or unnecessary raw Company document contents. Supporting owner-local evidence is retained under `r34-b1-final-cycle/evidence/r34-b1-final-20260915/`; its `MANIFEST.sha256` digest is `a1e3e036ab4f7f8338c9205f10db5fae6273a8663f3ea0d8a9f45bbc57fe03a1`.

## 2. Owner attestation and material eligibility

The owner explicitly confirmed in project chat on 2026-09-15: `Подтверждаю: это шаблон ООО „Арвектум“, handling верный.` This confirmation applies to the final corrected template SHA-256 `516c9c97c182e5585f86f60ddc80640f0d7203d839549ea1571a2472c86e16d4` and the following handling:

- classification: `internal`;
- purpose: official Company business correspondence and internal notices;
- rights: Company-owned owner-provided template for ООО «Арвектум» use;
- retention: retain until superseded or explicit owner-approved deletion;
- deletion: only by explicit owner decision after supersession or retention review;
- permitted reuse: Company business correspondence, internal Company notices and template-based transient document generation.

The selected asset is therefore owner-attested Company-owned material, not a synthetic fixture or AI substitute for Company evidence.

## 3. Execution identity and environment

- Organization: `ООО «Арвектум»`; server-resolved scope `aa4e760c379c8952aba6c6c335f3e233`.
- Attributable Actor: `Owner operator`; authentication source: P7.04 owner-local credential in an isolated owner-local runtime.
- Runtime: `r34-b1-final-cycle`, loopback same-origin Workspace at `127.0.0.1:8780`.
- Productive Workspace preflight: `PASS`; release `p9.11.10`; API contract `11`.
- `workspace.open` and exact `company.asset.admit-staged-version` grants were provisioned separately. Preflight retained `organizational_authority_provided=false`; authorization did not itself supply Consequential Approval or Organizational Authority.

## 4. Staging and explicit review

Final corrected material:

- filename: `Arvectum-official-letter-template-final.docx`;
- Material ID: `MAT-1eb31fed39c48daead518694a911ce1e`;
- staged Version ID: `MV-8b54d6ccd980c922e953cbd6b31f7c02`;
- SHA-256: `516c9c97c182e5585f86f60ddc80640f0d7203d839549ea1571a2472c86e16d4`;
- received: `2026-09-15T11:22:25.449044Z`;
- state on receipt: `StagedNonCanonical`;
- `canonical_authority=false`, `validated_knowledge=false`, `canonical_state_changed=false`.

Explicit review completed at `2026-09-15T11:22:52.720539Z` for that exact version and remained non-canonical. The review fixed the owner-confirmed deletion and permitted-reuse policy above.

## 5. Governed canonical admission

Admission completed at `2026-09-15T11:50:23.465587Z` with `canonical_state_changed=true` and `through_governed_execution=true`.

Exact canonical identities:

- Document subject: `document:aa4e760c379c8952aba6c6c335f3e233:organizational-asset-MAT-1eb31fed39c48daead518694a911ce1e`;
- Document version: `document-version:aa4e760c379c8952aba6c6c335f3e233:organizational-asset-MV-8b54d6ccd980c922e953cbd6b31f7c02`;
- Asset designation: `organizational-asset-version:aa4e760c379c8952aba6c6c335f3e233:company-asset-MV-8b54d6ccd980c922e953cbd6b31f7c02`;
- Admission Event: `event-version:aa4e760c379c8952aba6c6c335f3e233:company-asset-admitted-MV-8b54d6ccd980c922e953cbd6b31f7c02-d78e7c806a10e3a7d36e0306-v1`.

Provenance includes the attributable principal, exact staged material/version, owner-command approval, Product Contract/workflow pins, and independent Actor Assurance, Authorization, Organizational Authority, Data Governance, Validation and Consequential Approval gate-decision versions.

## 6. Restart / recovery / no replay

The same Workspace process/runtime root was gracefully stopped at `2026-09-15T11:51:13Z` and restarted at `2026-09-15T11:51:39Z`.

Pre/post restart comparison matched exactly for Material ID, staged Version ID, SHA-256, Document subject/version, Asset designation subject/version, Admission Event, admitted timestamp, full provenance and current status. Durable admission state remained exactly `1 committed / 1 attempt / 1 started effect / 1 resolved effect`; restart therefore reconstructed history without replaying the consequential admission.

The owner-facing Workspace retained Organization/Owner context and exposed the Accepted asset after restart.

## 7. Genuine later use and generated-output boundary

The exact admitted version `MV-8b54d6ccd980c922e953cbd6b31f7c02` was used to generate a bounded Company operational notice. Output:

- Output ID: `OUT-45aebec8a4fa3b223c8be29a70ce9630`;
- output SHA-256: `2974be86bfd6480215f10843be359e482c1c5e60d87eff0a7c99b56e4b67f174`;
- exact source SHA-256: `516c9c97c182e5585f86f60ddc80640f0d7203d839549ea1571a2472c86e16d4`;
- state: `TransientOutput`;
- `canonical_authority=false`, `validated_knowledge=false`, `canonical_state_changed=false`.

Downloaded bytes matched the manifest digest. The generated DOCX preserved the corrected footer `arvectum.com • E-mail: info@arvectum.com • Тел.: +7 916 594-35-07`. No promotion was fabricated because the real task did not require canonical promotion.

## 8. Safe live negative

A request using the real Material ID with nonexistent Version ID `MV-00000000000000000000000000000000` returned HTTP `404` / `COMPANY_MATERIAL_VERSION_UNAVAILABLE`. The final runtime still contained exactly one transient output and durable admission counts remained `1/1/1/1`; the failure therefore produced no canonical or transient mutation.

## 9. Usability findings

No unresolved P0/P1 was observed. Two bounded P3 findings remain:

1. a fresh isolated runtime requires an explicit P6.05-L4/P7.04 bootstrap before normal `provision-*` commands; the prepared runbook under-documents this prerequisite;
2. Company Materials defaults to the Draft tab after restart even when `Accepted = 1`, adding an unnecessary navigation step.

The source-template duplicate-contact issue was corrected before the qualifying final cycle and is not an unresolved milestone defect.

## 10. R34 evidence matrix

| Required dimension | Result |
| --- | --- |
| Owner/operator + Organization context | PASS |
| Company-owned material + explicit owner attestation | PASS |
| Staged receipt + exact digest/version | PASS |
| Explicit owner review | PASS |
| Governed canonical admission | PASS |
| Accepted owner-facing projection | PASS |
| Same-root restart/reconstruction | PASS |
| Exact post-restart identity/provenance comparison | PASS |
| Genuine later use of exact admitted version | PASS |
| Safe fail-closed live negative | PASS |
| Generated-output classification | PASS — remains `TransientOutput`; promotion not exercised |
| Owner usability / P0-P3 classification | PASS — no P0/P1; two P3 follow-ups |

## 11. Evidence conclusion

**B1:** `CLOSED / LIVE PASS`.
**B2:** `CLOSED / TECHNICAL PASS`.
**R34 evidence sufficiency:** `PASS` for final functional cross-review.
**Product Contract:** remains `Provisional 0.2.0`.
**Platform Capability promotion:** none.
**Production/SLA/RTO/RPO/multi-process claim:** none.
