# WSF-05 — owner portfolio traffic light (presentation candidate)

Date: 2026-11-21. Status: candidate, not admitted for deployment. Parent deployed release `32de1f2cce179b6d1755eff9e324d70834aa69f0`. Candidate release `p10.09.29-owner-traffic-light-candidate`. Scope: local read-only UI, no API contract change (`16`), no source mutation, no Company authority transfer, no automatic approval or execution.

## Why

Owner compared a 22-project status/action chat table against Mission Control. The 22 project states were below large corporate cards and six-project collapsed list. A quick overview of all projects, status, next action and dependencies was missing.

## Delivered

- Traffic light is the first main content under Overview. All admitted project rows are visible by default, ordered for attention then remaining source order; filters do not change source records.
- A red indicator is **only** a Company protect-now entry or an explicit project-wide NO-GO/blocked prohibition. A blocked task alone shows yellow plus a blocker label, not a falsely claimed critical business incident.
- Yellow represents open work; gray represents all-hold; green requires independently verified acceptance that the current source does not convey, so the current admitted data yields zero green rather than inventing progress.
- Next step prefers Company `protect_now`/`delegated_work` reviewed summary, then the existing source action. All open references are accessible by expanding a row; existing technical audit and governance records remain unchanged.
- The Company snapshot date is prominent and separated from the on-screen re-read time. `Refresh` does **not** claim new repository data. Original source coverage is partial and source-derived status colors are not organizational decisions.
- Existing contractual/financial/sales details remain under a secondary disclosure, while the main portfolio table, filters and source age are accessible on 1440/1280/390-pixel screens.

## Verification and release gates

Typecheck, complete frontend and BFF regressions, no-web-storage guard, exact Vite build, and runtime CDP browser preview against all eight live admitted sources. The preview uses candidate static assets only; production remains on `32de1f2` until a separately approved P7.06 deployment and exact collector/queue launch re-pin. Retain original private status snapshot, ledger, access rights, expiry and schedules. Verify login session and security denials, absence of new grants, live asset hashes, visual status totals and rollback readiness after activation.

## Freshness is a separate Company-owned workflow

The admitted queue is pinned to the approved Company snapshot of 2026-11-20 (22 projects and 51 actions). No independent live project status source exists in this OS contract. A scheduled refresh of canonical Company/product repository evidence must produce a **reviewable candidate diff**, preserve raw source lineage, distinguish observed changes from status assessment, and obtain any required Owner/Position approval before publishing an updated Company canonical projection. Only then should OS consume a newly admitted, versioned snapshot through its governed source-pinning/expiry contract; no silent auto-overwrite and no direct OS scans of Company/product internals. This increment only detects and displays source age; it does NOT claim automation of source updating. The separately agreed Company owner/workflow, trigger cadence, replacement path, data exposure, acceptance checks and escalation must be decided before unattended activation.
