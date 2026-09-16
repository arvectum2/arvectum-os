# P10.09-C — Product Contract Draft 0.3.0 Functional Cross-Review

Status: `Complete / PASS`
Date: `2026-09-16`
Task classification: `product_contract` with `product_specific` and `governance`
Reviewed Draft: `docs/contracts/P10-09-C-ARVECTUM-COMPANY-WORKSPACE-PRODUCT-CONTRACT-DRAFT-v0.3.0.md`
Exact reviewed Draft blob: `0b21eb3f05a0cdae5c3765a10dfdd27f9d8c4292`
Fit decision: `CONTRACT_EVOLUTION_REQUIRED`
Maximum iterations: `7`

## 1. Review functions

The Draft was reviewed from four functional perspectives:

- architecture / product-platform boundary;
- security, privacy, rights and AI-context minimization;
- RFC-0007 Knowledge / AI-authority semantics;
- lifecycle, migration, provenance and operational reversibility.

Functional review is engineering/governance evidence only. It is not owner approval and does not transition the Product Contract to `Provisional`.

## 2. Iteration 1 — exact boundary and dependency discipline

**Material finding:** merely wiring CompanyAssetLibrary into P9.08 Copilot would create an undeclared Company-asset → shared-Copilot reliance. Adding CAP-002 just because AI is involved would also overstate the dependency.

**Revision:** the Draft declares one exact new read-only operation, `workspace.copilot.ground-company-assets`, while preserving all `0.2.0` operations and explicitly retaining no CAP-002 dependency because no validated Knowledge/Memory state is relied upon or produced.

**Result:** `PASS after revision`.

## 3. Iteration 2 — rights, purpose and historical admission

**Material finding:** canonical asset admission alone cannot be treated as blanket consent for a new AI-processing purpose. Historical Company assets were admitted with exact immutable permitted-reuse evidence that may mention correspondence or document generation but not AI grounding.

**Revision:** the Draft requires the exact product-local reuse value `company-internal-ai-grounding` from the exact canonical Organizational Asset designation of the current admitted version. Non-canonical review/UI state cannot grant it. Ownership, `internal` classification, technical readability or another reuse purpose cannot substitute for it. Publication performs no policy mutation or retroactive migration.

**Result:** `PASS after revision`.

## 4. Iteration 3 — model packet, prompt injection and P10.09-D separation

**Material finding:** the existing P9.08 loopback model receives minimized evidence summaries. A Company source could tempt direct binary parsing, oversized raw context, hidden IDs, or instruction-following from document content, duplicating later P10.09-D extraction scope.

**Revision:** the Draft limits first-slice raw content grounding to bounded valid UTF-8 `text/plain` / `text/markdown`; non-text bytes are withheld. Model context excludes credentials/hidden authority/opaque Workspace IDs, and source content is explicitly untrusted data rather than model instruction. External/cloud model providers remain out of scope.

**Result:** `PASS after revision`.

## 5. Iteration 4 — lineage, rollback and action safety

**Material finding:** a new Product Contract version must not rewrite historical `0.2.0` execution attribution or turn a Copilot answer into an action shortcut.

**Revision:** the Draft keeps the same Product Contract Subject, creates a new version identity, preserves exact historical `0.2.0` pins, performs no bulk migration, keeps Company grounding removable/disableable, and inherits R31's inspect-evidence-first rule with no AI-selected Governed Execution.

**Result:** `PASS`.

## 6. Final review result

No unresolved material architecture, product-boundary, hidden-coupling, security, privacy, rights, Organization-isolation, Knowledge-lifecycle, AI-authority, action-routing, provenance, migration or lifecycle objection remains in the exact reviewed Draft.

The Draft is therefore ready for the separate owner approval gate. Until that approval and subsequent `Provisional 0.3.0` publication exist, real Company-asset Copilot grounding remains unavailable.
