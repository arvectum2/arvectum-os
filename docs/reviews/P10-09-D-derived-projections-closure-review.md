# P10.09-D Derived Projections Closure Review — 2026-09-16

Status: `Complete / PASS`
Review type: functional cross-review / roadmap evidence
Task: `P10.09-D — derived previews/search indexes`
Task classification: `product_specific`
Constitution: `1.2.0 Ratified`
Relevant Accepted RFC: `RFC-0001`, `RFC-0007`, `RFC-0008`

## Scope reviewed

P10.09-D introduced only bounded derived projections over exact current admitted Company asset versions:

1. exact UTF-8 TXT/Markdown text projection;
2. on-demand case-insensitive substring search rebuilt from the exact admitted source/version;
3. same-origin, session-protected Workspace BFF composition and ordinary-use search UI.

No persisted search index, OCR, embeddings, vector store, semantic ranking, canonical mutation, Knowledge promotion, Product Contract expansion, lifecycle promotion, external effect, or new authority surface was introduced.

## Acceptance evidence

- Projection output is explicitly non-authoritative and rebuildable from exact admitted source/version.
- Results retain exact material/version/SHA/document/designation attribution and use the existing server-side `AccessContext`, Company Asset Library and retrieval boundaries.
- Unsupported/opaque formats and invalid/oversized extraction fail explicitly rather than fabricating or silently partially succeeding.
- Derived output remains non-Knowledge by default under RFC-0007 and non-authoritative projection under RFC-0008.
- PR #8 exact-head Reference Python CI and Productive Workspace CI passed; merged as `4c616846331a6380dd72f3b428d8f33d24bac532`.
- PR #9 exact-head Reference Python CI and Productive Workspace CI passed; merged as `0eb7ee067f7239288a7ce75f0c5b7df18a6cbd8f`.
- PR #11 exact head `5396068c6f63bb40716e13c33b78fb7a50b46b64` passed Reference Python CI and Productive Workspace CI; no submitted reviews or unresolved review threads; merged after fresh Company AM-4 revalidation as `179a88d49b4ac783d57c2bf8fa7a7029527c4689`.
- Focused local BFF/projection/search tests passed `15/15`; frontend CompanyAssetDiscovery tests passed; later full frontend suite passed `54/54`, TypeScript/build and committed-production-assets reproducibility gate passed.

## Functional cross-review

### Architecture / product boundary

PASS. The implementation composes product-owned ordinary-use UX over existing Company asset boundaries and does not infer a reusable platform search API or hidden storage dependency.

### Security / data governance

PASS. Existing session and `AccessContext` enforcement remain server-side; derived content does not broaden Organization/access/classification/purpose scope.

### Knowledge / authority

PASS. Search/extraction is retrieval/projection only. It does not validate assertions, create Organizational Authority, promote Knowledge, approve assets, or execute consequential actions.

### Documents / provenance

PASS. Derived text/search remains attributable to exact source/version/content SHA and is explicitly non-authoritative/rebuildable. Unsupported extraction remains explicit.

### Delivery / reversibility

PASS. All changes are repository-revertible and create no release, deployment, production, legal, financial, procurement or external effect.

No material objection remains after the implementation/repair/reverification loop.

## Result

`P10.09-D = Complete / PASS` for its bounded roadmap scope.

This result does not claim OCR/vector/semantic-search capability, Platform Capability promotion, Product Contract lifecycle change, customer Production, operational-readiness approval, broader conformance, or completion of P10.07/P10.10/R35/M10.

The next canonical executable work is selected from the repository execution queue and roadmap; P10.07 remains a genuine-request evidence gate and must not be synthesized.
