"""Company-owned candidate report adapter for an owner-local, read-only F11 view.

The adapter never fetches, runs or updates Company source-watch. It is intentionally
isolated from OS identity/governance, the WSF-07A Inbox and WSF-05 status models.
"""
from collections import Counter
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import re
import stat

SCHEMA = "arvectum.company.project-source-watch-report/1"
BASELINE_SHA256 = "1911e34f4056d7201bae5524c366be698079da581219ff30aa244b87f1e1b126"
BASELINE_BLOB = "c4addaacf3381f789f2798d0b74cd2413a45d60e"
BASELINE_COMMIT = "84135f11bc115366fa5aac4ced9db0b86dc1ff0b"
SIGNALS = frozenset({"changed_source_review_required", "incomplete_source_evidence",
    "unscoped_repo_activity_review", "existing_os_collector_review_required",
    "observed_source_unchanged"})
STAMP = re.compile(r"company-source-watch-[0-9]{8}T[0-9]{6}[0-9]{0,6}Z\.json")
MAX_REPORT = 512_000
MAX_REPORTS = 4000


class CompanySourceWatchUnavailable(Exception):
    pass


def _private_dir(path):
    if path.is_symlink() or not path.is_dir():
        raise CompanySourceWatchUnavailable("private report directory unavailable")
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise CompanySourceWatchUnavailable("private report directory denied")


def _read_private(path):
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
            raise CompanySourceWatchUnavailable("report permissions denied")
        if not 1 <= info.st_size <= MAX_REPORT:
            raise CompanySourceWatchUnavailable("report size denied")
        with os.fdopen(fd, "rb") as stream:
            fd = None
            raw = stream.read(MAX_REPORT + 1)
        if len(raw) > MAX_REPORT:
            raise CompanySourceWatchUnavailable("report exceeds limit")
        return json.loads(raw)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise CompanySourceWatchUnavailable("report unavailable") from exc
    finally:
        if fd is not None:
            os.close(fd)


def read_company_source_watch(report_dir: Path, *, now: datetime | None = None):
    """Produce only candidate signal summary from the latest exact Company report."""
    report_dir = Path(report_dir)
    if not report_dir.is_absolute() or report_dir.resolve() != report_dir:
        raise CompanySourceWatchUnavailable("untrusted report directory")
    _private_dir(report_dir.parent)
    _private_dir(report_dir)
    try:
        names = [p for p in report_dir.iterdir() if STAMP.fullmatch(p.name)]
    except OSError as exc:
        raise CompanySourceWatchUnavailable("reports cannot be listed") from exc
    if not 1 <= len(names) <= MAX_REPORTS:
        raise CompanySourceWatchUnavailable("report inventory unavailable")
    latest = max(names, key=lambda p: p.name)
    data = _read_private(latest)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("status") != "derived_candidate_review_only":
        raise CompanySourceWatchUnavailable("unadmitted report")
    if any(data.get(k) is not False for k in ("automatic_approval", "automatic_source_repin",
            "canonical_status_modified", "organizational_authority_provided", "execution_authorized")):
        raise CompanySourceWatchUnavailable("report authority flags invalid")
    if (data.get("repository_owner") != "arvectum2" or data.get("source_sha256") != BASELINE_SHA256
            or data.get("source_blob") != BASELINE_BLOB or data.get("source_commit") != BASELINE_COMMIT
            or data.get("source_as_of") != "2026-11-20"):
        raise CompanySourceWatchUnavailable("report source pin invalid")
    coverage = data.get("coverage")
    if not isinstance(coverage, dict) or any(coverage.get(k) != n for k,n in
            (("projects",22),("source_refs",35),("os_collector_exact_refs_not_refetched",5))):
        raise CompanySourceWatchUnavailable("report coverage invalid")
    if coverage.get("os_collector_freshness_verified_here") is not False:
        raise CompanySourceWatchUnavailable("unadmitted collector health claim")
    projects = data.get("projects")
    if not isinstance(projects,list) or len(projects)!=22:
        raise CompanySourceWatchUnavailable("project count invalid")
    results=[];names_seen=set();counts=Counter()
    for row in projects:
        if not isinstance(row,dict) or not isinstance(row.get("project"),str) or not 1<=len(row["project"])<=150:
            raise CompanySourceWatchUnavailable("report project invalid")
        label=row["project"]
        if label in names_seen or row.get("review_signal") not in SIGNALS or row.get("business_stage_updated") is not False or row.get("proposed_business_status") is not None:
            raise CompanySourceWatchUnavailable("report cannot attest business state")
        names_seen.add(label); counts[row["review_signal"]]+=1
        results.append({"project":label,"review_signal":row["review_signal"]})
    summary=coverage.get("review_signals")
    if not isinstance(summary,dict) or summary!={k:v for k,v in counts.items()}:
        raise CompanySourceWatchUnavailable("report summary mismatch")
    try:
        observed=datetime.fromisoformat(data["scanned_at"].replace("Z","+00:00"))
    except (KeyError,TypeError,ValueError) as exc:
        raise CompanySourceWatchUnavailable("invalid report timestamp") from exc
    checked=now or datetime.now(timezone.utc)
    if observed.utcoffset()!=timedelta(0) or checked.utcoffset()!=timedelta(0) or observed>checked+timedelta(minutes=2):
        raise CompanySourceWatchUnavailable("report clock untrusted")
    stale=checked-observed>timedelta(hours=30)
    return {"schema":"arvectum.company.source-watch-view/1", "state":"stale" if stale else "current-observation",
            "derived":True,"canonical_authority":False,"business_status_updated":False,
            "organizational_authority_provided":False,"source_as_of":"2026-11-20",
            "scanned_at":observed.isoformat(),"report_name":latest.name,
            "coverage":{"projects":22,"source_refs":35,"os_exact_paths_delegated":5,
                "additional_repositories":coverage.get("additional_repos_scanned"),"review_signals":dict(counts)},
            "projects":results}
