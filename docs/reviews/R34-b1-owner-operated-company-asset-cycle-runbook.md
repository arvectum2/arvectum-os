# R34-B1 — Owner-Operated Company Asset Cycle Execution / Evidence Runbook

**Version:** 0.2.0
**Status:** Executed / PASS
**Date:** 2026-09-15
**Owner:** ООО «Арвектум»  
**Task classification:** `platform + product_specific + governance`  
**Parent review:** [`R34 — M10-alpha Asset Governance / Usability Review`](R34-m10-alpha-asset-governance-usability-review.md)  
**Target milestone:** `M10-alpha — First Governed Company Asset Cycle`

## 1. Purpose

This runbook defined the first real owner-operated Arvectum Company asset cycle required to resolve R34 blocker B1 and was executed on 2026-09-15.

The procedure alone is not milestone evidence. The resulting live evidence is recorded in [`R34-B1 — Real Owner-Operated Company Asset Cycle Evidence`](R34-b1-owner-operated-company-asset-cycle-evidence-2026-09-15.md); R34/M10-alpha status changes only through the reviewed closure and roadmap synchronization.

The qualifying cycle must use one real bounded Company-owned material and the actual Productive Workspace owner path. Synthetic fixtures, CI-only runs, generated test material and AI-created substitute evidence do not qualify.

## 2. Governing boundaries

Execution remains subordinate to:

- Constitution `1.2.0` — `Ratified`, frozen;
- RFC-0001 through RFC-0008 — `Accepted 1.0.0`;
- ADR-0001 — `Accepted`;
- ADR-0002 — `Company Workspace Durable Governed State`, `Accepted`;
- Company Workspace Product Contract `Provisional 0.2.0`;
- P10.03/P10.04/P10.05 accepted implementation boundaries;
- R34 review and canonical Phase 10 roadmap.

The runbook creates no new authority source. Authentication, Authorization, Organizational Authority, Data Governance, Validation and Consequential Approval remain distinct. AI may help record or explain evidence but may not decide Company ownership/rights, supply Organizational Authority, approve the consequential admission, or silently change canonical state.

## 3. Non-claims

Executing or publishing this runbook does not by itself:

- amend the Constitution or any Accepted RFC/ADR;
- promote the Product Contract from `Provisional` to `Stable`;
- promote any Platform Capability to `Active`;
- create a platform-wide database or stable persistence API;
- claim Production readiness, SLA, support, RTO/RPO or multi-process writer safety;
- make staged material canonical before Governed Execution;
- turn an admitted document into RFC-0007 validated Knowledge;
- turn generated output into canonical state without its separate governed promotion operation;
- authorize use of material beyond the owner-confirmed rights, classification, purpose and retention boundary.

## 4. Qualifying material

The owner must select one **real bounded material genuinely owned by ООО «Арвектум»**. This ownership requirement comes directly from the canonical M10-alpha milestone definition.

A third-party, licensed, externally owned or otherwise merely authorized-for-use material may be valid in another Product Contract/asset scenario, but it does **not** satisfy this M10-alpha cycle unless the canonical milestone definition is separately changed by proper governance.

For the first cycle, prefer a low-risk Company document with no reusable credentials and no unnecessary personal, customer or third-party confidential data. The material must be useful enough that later retrieval/use through Workspace is genuine rather than ceremonial.

Before staging, the owner records only the following attestation in the evidence packet:

- material title/description sufficient to identify the business purpose without copying unnecessary content;
- explicit confirmation that the material is owned by ООО «Арвектум» and a bounded ownership basis/reference where useful;
- intended classification;
- intended purpose;
- rights/use statement;
- retention rule;
- confirmation that the chosen handling is appropriate for the first owner-operated cycle.

The owner, not AI, is responsible for this ownership/handling attestation.

## 5. Evidence minimization

The repository evidence packet should contain identifiers, digests, timestamps, decisions and bounded screenshots/exports where useful. It should **not** duplicate the raw Company document unless a later explicit governance decision requires that.

Do not commit:

- passwords, API keys, cookies, session values or reusable credentials;
- unnecessary raw Company contents;
- unnecessary personal or third-party confidential information;
- local absolute paths where a bounded runtime/evidence reference is sufficient.

The retained material bytes remain in the existing owner-local content-addressed Company materials store under the Workspace runtime root. ADR-0002 governed-state metadata remains separate from the retained raw bytes.

## 6. Productive Workspace preconditions

Use the canonical repository and an owner-operated checkout containing the R34-D2 merge or later canonical `main`.

From `reference/python`, with the intended persistent owner-local runtime root configured consistently for the whole cycle:

```bash
python3 p9_03_workspace.py provision-local-grant --confirm
python3 p9_03_workspace.py provision-company-asset-admission-grant --confirm
python3 p9_03_workspace.py check
```

If the default owner-local profile is used, `WorkspaceSettings` resolves:

- runtime root: `~/Library/Application Support/ArvectumOS/persistent-internal`;
- origin: `http://127.0.0.1:8769`;
- bind host: `127.0.0.1`;
- bind port: `8769`.

A non-default runtime root may be selected with `ARVECTUM_P7_02_ROOT`, but the **same exact runtime root must be retained across the admission, process stop, restart and recovery/retrieval evidence steps**.

The `check` result must succeed and must report that Company asset admission is authorized for the exact current owner-operated access context. The grant is Authorization only; it supplies neither Organizational Authority nor Consequential Approval.

If `check` fails, stop. Do not create substitute evidence or bypass the failed gate.

Start the Productive Workspace with:

```bash
python3 p9_03_workspace.py serve
```

Use the configured owner-operated origin (default `http://127.0.0.1:8769`). The loopback Workspace creates the bounded browser session only after current access revalidation.

## 7. Real owner-operated execution sequence

### Step 1 — Record execution identity

Before changing Company asset state, record:

- UTC start timestamp;
- canonical repository commit SHA used by the running checkout;
- Workspace release/build identity shown by the running application/check output where available;
- Organization display/scope;
- attributable owner/operator identity label without credentials;
- runtime profile description sufficient to show that the same owner-local root is used before and after restart.

Do not record session cookies or secrets.

### Step 2 — Select and attest the real material

The owner selects the qualifying Company-owned material under section 4 and records the bounded ownership/rights/handling attestation.

If the owner cannot truthfully attest Company ownership, stop. The material is not eligible for this M10-alpha cycle.

### Step 3 — Stage the material through Workspace

Open **Материалы компании / Company materials** and use **Добавить материал / Add material**.

Enter the real values for:

- project (`COMPANY` is valid for Company-wide material);
- file;
- material type / semantic role;
- classification;
- purpose;
- rights;
- retention rule.

Save it with **Сохранить как черновик / Save as draft**.

Expected state:

- the exact version is immutable staged material;
- canonical state has not changed;
- the item is `StagedNonCanonical` / Draft;
- Workspace shows the staged version identity and SHA-256 digest.

Record the material/version identifiers, SHA-256, declared handling fields and staged timestamp/reference. Do not copy raw file contents into the evidence markdown.

### Step 4 — Owner review of the exact staged version

The owner inspects the exact staged version and its digest/handling metadata, then explicitly submits the review through the P10.04 Workspace lifecycle.

The review must include the actual deletion rule and permitted-reuse decision applicable to this material.

Expected state:

- review evidence exists for the exact staged version;
- canonical state has still not changed;
- the item is visible in the review lifecycle view;
- no authority is inferred from UI visibility.

Record the review decision/evidence identifiers exposed by Workspace/system evidence and the owner observation; do not invent an identifier that the actual projection does not expose.

### Step 5 — Consequential admission through Governed Execution

Only after the owner has made the required real-world authority/handling decision, invoke **Принять через Governed Execution / Admit through Governed Execution** for the exact reviewed version.

The Productive Workspace must re-evaluate the applicable server-side admission boundary. The successful path is the existing `company.asset.admit-staged-version` governed operation; the browser does not itself create authority.

If any required gate fails, record the truthful blocked/failed result and stop the positive cycle until it is legitimately remediated. Do not bypass or manually rewrite state.

On success, record from Workspace/system-derived evidence:

- admitted Company asset/material ID;
- exact admitted version ID;
- exact content SHA-256 / content reference;
- immutable Document version;
- Organizational Asset designation version;
- canonical Admission Event version/reference;
- provenance references;
- owner/operator and Organization context;
- successful UTC timestamp;
- confirmation that staged/review history remains distinct from the canonical admitted result.

### Step 6 — Owner-visible accepted state

Open the **Принятые / Accepted** lifecycle view and inspect the admitted item details.

Confirm that the exact admitted version, SHA-256, Document version, Asset designation, Admission Event and provenance are visible/retrievable and match the Step 5 result.

Record one bounded screenshot or exported projection if useful, with sensitive content minimized/redacted. Identifiers/digests are primary evidence; screenshots are supplemental.

### Step 7 — Process stop

Stop the Productive Workspace process normally.

Record the UTC stop timestamp. Do not delete or replace the runtime root, material store or governed-state directories.

The process stop itself must not trigger a new consequential effect.

### Step 8 — Restart from the same durable runtime root

Restart the same Productive Workspace profile using the same exact runtime root:

```bash
python3 p9_03_workspace.py check
python3 p9_03_workspace.py serve
```

A new browser session may be bootstrapped, but recovered history is not a source of current Authorization or Organizational Authority for any new operation.

If durable state is corrupt, partial, unknown-schema or otherwise unreconstructable, the system must fail closed. Do not repair evidence by hand.

### Step 9 — Post-restart exact reconstruction

Return to **Материалы компании / Company materials** → **Принятые / Accepted**.

Confirm that the same admitted result reconstructs after restart, including:

- same material ID;
- same exact admitted version ID;
- same SHA-256/content reference;
- same Document version;
- same Asset designation;
- same Admission Event;
- same provenance references.

Record UTC timestamp plus the exact identifier comparison. A different canonical version/Event for the same historical admission is a blocker requiring investigation.

### Step 10 — Genuine later retrieval/use through Workspace

Use the admitted material through an existing Workspace path that genuinely depends on that exact admitted version.

For a qualifying admitted DOCX template, the existing P10.04 Workspace generation form is one valid bounded use path: select the exact admitted template version and generate a document. The generated document remains `TransientOutput` by default and must not be represented as canonical or validated Knowledge.

If the selected material type has no existing truthful Workspace use path, do not invent one. Record the limitation as an R34 usability finding and leave B1 unresolved until a genuine supported retrieval/use is demonstrated.

For the use evidence record:

- exact admitted source version selected;
- source digest/version visible at point of use where exposed;
- UTC timestamp;
- resulting bounded action/result;
- confirmation that use did not mutate the admitted historical version;
- if output is generated, confirmation that it remains `TransientOutput` unless separately promoted through P10.05.

### Step 11 — Safe negative / recovery observation

R34 requires truthful owner-operated evidence for fail-closed behavior. Do **not** deliberately corrupt durable state or create a risky outage just to satisfy the milestone.

Use a naturally occurring or safely bounded negative path if one exists during the run (for example, an intentionally incomplete review input rejected before canonical mutation). Record only a path that does not endanger retained Company material or require bypassing security controls.

If no safe negative path occurs in this first real cycle, record `NOT EXERCISED IN REAL CYCLE` and rely on the already-qualified R34-D2 technical negative-path evidence for the engineering dimension. Do not fabricate live failure evidence.

### Step 12 — Owner usability observation

The owner records concise observations for:

- whether staging/review/admission state was understandable;
- whether exact version/digest/handling was visible before admission;
- whether the authority boundary was understandable at the consequential step;
- whether accepted history and provenance were discoverable;
- whether restart/recovery was transparent enough;
- whether later retrieval/use selected the intended exact version;
- any friction or defect.

Classify defects as `P0`, `P1`, `P2` or `P3`. Any unresolved `P0/P1` in M10-alpha scope blocks R34 PASS.

## 8. Evidence packet schema

After execution, create one bounded evidence record under `docs/reviews/` (or an R34 evidence subdirectory if one is introduced by the same reviewed change). The evidence record must be clearly marked **Executed** and must reference, not duplicate, sensitive payloads.

Minimum evidence matrix:

| Evidence | Required source / fields | Responsible actor |
| --- | --- | --- |
| Execution identity | UTC, repository commit, Workspace release/build, Organization, attributable operator, runtime profile | system + owner |
| Material eligibility | bounded title/description, explicit Company ownership attestation, classification, purpose, rights, retention | owner |
| Staged receipt | material ID, staged version ID, SHA-256, handling fields, timestamp | Workspace/system |
| Owner review | exact version, review decision/evidence exposed by actual projection, deletion rule, permitted reuse | owner + Workspace |
| Governed admission | operation, exact admitted version, Document version, designation, Event, provenance, timestamp | Governed Execution/system |
| Accepted UX | exact identifiers visible/retrievable in Accepted view | Workspace + owner |
| Restart | stop/start timestamps, same runtime profile, successful reconstruction | system + owner |
| Post-restart comparison | exact pre/post identifiers and digest match | system + owner |
| Later retrieval/use | exact admitted source version, use path/result, non-mutation observation | Workspace + owner |
| Negative/recovery observation | real safe path if exercised, otherwise explicit `NOT EXERCISED` with D2 technical evidence reference | owner/reviewer |
| Usability | owner observations + P0/P1/P2/P3 defect classification | owner |

## 9. Fail-closed / abort criteria

Stop the qualifying run and leave B1 open if any of the following occurs:

- Company ownership or required handling cannot be truthfully attested;
- owner access or Company asset admission authorization is unavailable;
- staged version/digest cannot be identified exactly;
- review is missing, ambiguous or applies to a different version;
- admission bypasses Governed Execution or any required gate;
- canonical result lacks exact immutable version/Event/provenance evidence;
- restart cannot reconstruct the exact admitted state from the same runtime root;
- recovery creates/replays a second consequential admission effect;
- post-restart identifiers/digest conflict with the admitted result;
- genuine Workspace retrieval/use of the admitted exact version cannot be demonstrated;
- raw sensitive contents/secrets would need to be committed merely to prove the milestone;
- unresolved `P0/P1` defect exists in M10-alpha scope.

A failed/blocked attempt is valuable evidence but is not permission to weaken the gate.

## 10. R34 re-review

After the real evidence packet is complete:

1. compare it against the R34 scope matrix and exit criteria;
2. verify B2 technical evidence still applies to the running canonical build;
3. review owner usability, exact-version/provenance, authority/data governance, retry/recovery and later retrieval/use;
4. record defects and remediation;
5. update R34 only after the evidence is reviewed.

R34 may become `Closed / PASS` only if all canonical exit criteria are satisfied. Only then may the roadmap claim M10-alpha and advance the critical path to P10.06.

## 11. Current disposition

**Runbook:** `Executed / PASS`
**Execution evidence:** [`R34-B1 live evidence`](R34-b1-owner-operated-company-asset-cycle-evidence-2026-09-15.md) `1.0.0 — Executed / PASS`
**B1:** `CLOSED / LIVE PASS`
**B2:** `CLOSED / TECHNICAL PASS`  
**R34:** `Closed / PASS — final functional cross-review 7/7`
**M10-alpha:** `Achieved / PASS`
**Next executable action:** `P10.06 — Real Action Request / Actionable Work boundary`
**Product Contract:** remains `Provisional 0.2.0`  
**Platform Capability promotion:** none

## 12. Execution record

The qualifying cycle used the owner-provided Arvectum official-letter DOCX after the owner-requested contact/footer correction, explicit owner ownership/handling attestation, exact staged/reviewed/admitted identity, Governed Execution admission, same-runtime-root restart/no-replay, genuine later document generation and a bounded fail-closed exact-version negative. Generated output remained `TransientOutput`; no promotion was exercised. Two P3 findings remain and no P0/P1 blocker was observed.
