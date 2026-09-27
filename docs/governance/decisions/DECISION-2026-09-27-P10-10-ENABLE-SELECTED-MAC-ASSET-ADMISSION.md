# DECISION-2026-09-27 — Enable Company Asset Admission on Selected-Mac Workspace

Status: `Approved`
Decision date: `2026-09-27`
Owner: `ООО «Арвектум»`
Task classification: `governance` with `product_specific` and `product_contract` boundary checks
Related task: `P10.10 — Real daily-operations dogfooding + friction closure`
Runtime scope: selected Mac mini, persistent owner-local Workspace at `http://127.0.0.1:8769`
Operation: `company.asset.admit-staged-version`

## Decision

The Owner explicitly authorizes one-time provisioning of the existing least-privilege P7.04 Authorization grant for `company.asset.admit-staged-version` on the selected-Mac persistent owner-local Workspace runtime.

This decision is based on genuine P10.10 owner reuse that showed the Workspace runtime healthy while Company Asset admission remained unavailable because the exact operation grant was absent.

The provisioning must use the existing canonical command path:

`p9_03_workspace.py provision-company-asset-admission-grant --confirm`

against the same selected-Mac persistent runtime root used by the active Workspace.

## Boundary

This decision grants Authorization only for the exact existing operation and resource boundary implemented by the current Product Contract and P7.04 policy.

It does **not**:

- create or broaden Organizational Authority;
- approve any particular material/version for admission;
- bypass Data Governance, Validation or Consequential Approval;
- change the Product Contract or its lifecycle;
- change an Accepted RFC/ADR;
- authorize cross-Organization access;
- authorize generated-output promotion, product/external actions or P10.07 evidence;
- authorize AI to admit a material autonomously.

Each concrete admission remains an attributable owner command and must pass the existing server-side RFC-0005 Governed Execution gates for the exact staged version.

## Verification required

After provisioning, the executor must verify:

1. the provisioning command returns PASS;
2. Productive Workspace `check` reports `company_asset_admission_authorized=true`;
3. the live Company Asset projection reports `governed_admission_available=true`;
4. existing staged drafts remain staged and are not automatically admitted;
5. no unrelated grant, Organization scope or Product Contract boundary is changed.

## Owner approval evidence

Attributable Owner instruction in the Arvectum OS project conversation on `2026-09-27`:

> Да, включай принятие материалов на этом Workspace

## Result

`APPROVED — one-time least-privilege Company Asset admission Authorization provisioning on the selected-Mac persistent Workspace.`
