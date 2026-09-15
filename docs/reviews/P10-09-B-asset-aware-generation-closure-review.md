# P10.09-B — Asset-Aware Generation Closure Review

Status: `Complete / PASS`
Date: `2026-09-15`
Task classification: `product_specific`
Owner: `ООО «Арвектум»`
Scope: Productive Workspace / Arvectum Company, bounded internal Provisional Product Contract scope

## Authority check

- Constitution `1.2.0` remains `Ratified` and unchanged.
- RFC-0001, RFC-0003, RFC-0004, RFC-0005, RFC-0006 and RFC-0008 remain satisfied; RFC-0007 remains relevant only as the non-Knowledge boundary and no AI/Knowledge reliance is introduced here.
- RFC-0005 exact material-input pinning and RFC-0008 derivation/transient-artifact requirements are preserved.
- ADR-0001 keeps browser state non-authoritative and requires server-side revalidation.
- ADR-0002 keeps this Company-specific bounded generation/persistence composition product-owned.
- Product Contract `p9-11-f11-arvectum-company-workspace 0.2.0` remains `Provisional`; no lifecycle transition is made.
- No Platform Capability lifecycle transition, public/stable API, customer Production, SLA/support or broader conformance claim is created.

## Delivered slice

P10.09-B makes current admitted Company assets explicit generation inputs without broadening authority:

- one exact current admitted DOCX `document-template` version is required;
- current admitted logo/brand, source and reference assets may be selected through ordinary human-readable Workspace UX;
- PNG/JPEG logo inputs are embedded into generated DOCX bytes;
- UTF-8 TXT/Markdown source/reference inputs are included as text;
- formats not deterministically interpreted by this slice remain truthful exact `pinned-reference` inputs rather than being presented as parsed or AI-understood;
- every auxiliary input retains exact SHA-256, Document Version, Organizational Asset designation, admission Event and provenance evidence;
- a reproducible `generation_input_digest` covers the exact material-input basis, while `output_sha256` independently protects final output bytes;
- superseded admitted versions remain historically retrievable but are not accepted as current/effective generation inputs;
- generated output remains `TransientOutput` by default.

The existing reviewed-promotion path was extended only enough to preserve the complete exact generation lineage. Promotion re-resolves every admitted input, validates application/provenance/digest evidence, rejects handling-policy incompatibility fail-closed, and carries all exact source Document/Artifact/designation provenance into the promoted candidate. The source output itself remains `TransientOutput`.

## Functional cross-review

Three execute/review/revise iterations were completed.

1. Multi-input promotion/provenance review exposed that auxiliary generation evidence needed complete downstream retention and independently verifiable exact-input digest semantics. The promotion bridge and generation manifest were tightened accordingly.
2. Tamper-negative and handling-policy review verified fail-closed behavior for modified input-application/provenance evidence and incompatible source handling; targeted generation/promotion tests passed.
3. Browser robustness review found a malformed client-side asset-selection value could throw before the normal UI error path. The handler was made fail-closed and the UI regression suite remained green.

No material architecture, authority, security, lifecycle or provenance objection remains within the exact bounded P10.09-B scope.

## Evidence

- PR: `#4` — `P10.09-B: exact admitted asset-aware generation`.
- Implementation commit: `4bcdaebeb68476b3ecaa0ba1cc6d34c61ae44214`.
- Internal Workspace release: `p10.09.2`; application contract: `14`; classification remains `bounded-internal-provisional`, `public_api=false`.
- Local Workspace suite: `123/123` PASS.
- Local frontend: `18` test files / `52` tests PASS; TypeScript typecheck PASS; Web Storage guard PASS; production build and release-pinned asset verification PASS.
- Targeted asset-aware generation + reviewed-promotion suite: `10/10` PASS, including tampered-manifest rejection and complete multi-input promotion lineage.
- Local P7.05 selected-Mac proof failures were reproduced unchanged on a clean canonical `main@4b682a4`, identifying host launchd proof state rather than P10.09-B regression.
- GitHub Actions `Productive Workspace CI` run `35023030317`: PASS.
- GitHub Actions `Reference Python CI` run `35023030327`: full reference architecture fitness suite PASS.

## Decision

`P10.09-B = Complete / PASS` for its exact bounded scope.

The next primary development slice is `P10.09-C — asset-grounded Copilot fit-check and bounded use`. Before admitted Company assets become material AI/Copilot context, P10.09-C must record the explicit Product Contract fit decision (`COVERED`, `CONTRACT_EVOLUTION_REQUIRED`, or `DEFER`). P10.07 remains a separate mandatory genuine-request evidence gate for M10 closure and is not satisfied by P10.09-B.
