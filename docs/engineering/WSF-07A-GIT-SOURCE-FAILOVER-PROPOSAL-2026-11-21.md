# WSF-07A: Git-first roadmap source access

Status: Draft / implementation candidate, not approved for release or deployment.
Scope: existing eight registered public GitHub `main` locators. Company controls source and decisions; OS Workspace implements the reader.

The scheduled collector and ordinary Mission Control portfolio view previously used 16 anonymous GitHub REST calls per complete 3-hour scan, sharing an IP rate budget. This change tries public Git smart HTTPS first, loading the exact remote `main` commit into a private shallow bare cache inside the runtime, then reading only the allowlisted roadmap file at that SHA. No worktree is changed; no browser session, user SSH key, Git credential helper, human token, GitHub API token, shell or new cost is required. The collector and the interactive portfolio use separate private caches to avoid Git fetch contention. The Git commit and file SHA remain the evidence; the cache is a disposable non-canonical projection.

On Git transport failure, use the existing strict allowlisted anonymous REST reader. If both paths fail, report the source unavailable without advancing its checkpoint or labelling old evidence fresh. Existing Inbox history and last successful snapshot are kept with their recorded timestamps. Do not silently substitute GitVerse or another repository as authority. Existing identity grants, 8-active/2-excluded scope, backups, audit, 3-hour schedule, 4-hour freshness threshold, capacity cap, and owner review gates remain unchanged.

Activation requires isolated tests, exact release review, operational verification of anonymous Git transport on the selected Mac, source-integrity and failure testing, separately approved repin/deployment, and a read-after-write check. This draft does not itself authorize production activation or source-contract extension.

### Isolated proof

On 2026-11-21, all eight allowed roadmap contents were fetched via Git only on Mac mini, with REST deliberately disabled. The existing collector integration suite (17 tests) and collector suite (15 tests) passed using the pinned runtime Python environment. Git-first unit tests also passed. The live pinned release and Inbox ledger have not been changed. The ordinary F11 Company portfolio API now uses a separate Git cache so that ordinary Mission Control refreshes do not spend REST calls in the normal path.

The independent Company source watcher is owned by the Company repository, not the OS collector; its separate candidate and admission gate are in Company Spec 002. The proposed integrated dashboard remains a read-only derived projection, not a new authority for 22 business project statuses.
