"""Single bounded cycle, crash-visible retry state and inactive launchd template."""
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import fcntl
import json
import os
from pathlib import Path
import plistlib
import time

from .wsf_collector_runtime import service_inbox
from .wsf_collector_source import provider_for
from .wsf_inbox_registry_migration import atomic
from .wsf_local_roadmap_collector import ACTIVE, INTERVAL, collect_cycle
from .wsf_manual_context import ManualContextError, _json
from .wsf_manual_policy import _private_file
from .wsf_manual_backup import PilotBackup
from .wsf_inbox_routes import INBOX_PARTS
from .company_portfolio import CompanyPortfolioError

LABEL="com.arvectum.os.roadmap-collector"
STATUS="roadmap-collector-status.json"

def _now():
    return datetime.now(timezone.utc)

def _window(now):
    return int(now.timestamp())//INTERVAL

@contextmanager
def runner_lock(inbox):
    f=inbox.file;fd=f._open(f.directory/".collector-runner.lock",os.O_CREAT|os.O_RDWR)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ManualContextError("collector runner busy") from None
        yield
    finally:os.close(fd)

def read_status(root):
    p=Path(root)/"run"/STATUS
    if not p.exists() and not p.is_symlink():return None
    d=json.loads(_private_file(p))
    if (set(d)!={"schema","release_sha","window","attempts","state","updated_at","last_verified_at"}
        or d["schema"]!="arvectum.workspace.collector-status/1"
        or type(d["window"]) is not int or d["window"]<0
        or type(d["attempts"]) is not int or not 1<=d["attempts"]<=2
        or d["state"] not in ("running","retry-pending","verified","degraded","blocked")
        or datetime.fromisoformat(d["updated_at"]).utcoffset()!=timedelta(0)
        or (d["last_verified_at"] is not None and datetime.fromisoformat(d["last_verified_at"]).utcoffset()!=timedelta(0))):
        raise ManualContextError("collector run status invalid")
    return d

def attempt_once(root,inbox,policy,resolve,provider,*,backup_factory):
    """At most two attempts per 3h window. No retry on denied or uncertain write."""
    root=Path(root);now=_now();window=_window(now)
    with runner_lock(inbox):
        policy.validate(resolve(),now)
        old=read_status(root)
        if old and old["window"]>window:raise ManualContextError("collector clock regressed")
        if old and old["release_sha"]!=policy.release_sha:
            raise ManualContextError("collector run state requires release reconciliation")
        same=old is not None and old["window"]==window
        if same and (old["state"] in ("verified","degraded","blocked") or old["attempts"]>=2):
            return {"status":"not-due","previous_state":old["state"]}
        # If a process died mid-attempt, the ledger/backup check in collect_cycle
        # reconciles same-key commit before a retry is permitted.
        status={"schema":"arvectum.workspace.collector-status/1","release_sha":policy.release_sha,
                "window":window,"attempts":old["attempts"]+1 if same else 1,
                "state":"running","updated_at":now.isoformat(),
                "last_verified_at":old["last_verified_at"] if old else None}
        path=root/"run"/STATUS
        atomic(path,_json(status))
        try:
            result=collect_cycle(inbox,policy,provider,resolve,backup_factory=backup_factory)
            status["state"]="verified" if result.get("backup_status")=="verified" else "degraded"
            if status["state"]=="verified":
                status["last_verified_at"]=_now().isoformat()
        except (OSError,CompanyPortfolioError):
            # Preserve running state for one same-window retry only. No auto retry
            # of policy denial, stale backup or ambiguous different-window request.
            status["state"]="retry-pending" if status["attempts"]<2 else "blocked"
            atomic(path,_json({**status,"updated_at":_now().isoformat()}))
            return {"status":"retry-possible" if status["attempts"]<2 else "retry-exhausted","attempts":status["attempts"]}
        except ManualContextError:
            status["state"]="blocked";status["updated_at"]=_now().isoformat()
            atomic(path,_json(status));raise
        status["updated_at"]=_now().isoformat()
        atomic(path,_json(status))
        return result

def run(root,*,publication=None):
    inbox,p,policy,resolve=service_inbox(root,publication=publication)
    resolve()
    provider=provider_for(root,p)
    window=_window(_now())
    factory=lambda store:PilotBackup(store,parts=INBOX_PARTS)
    result=attempt_once(root,inbox,policy,resolve,provider,backup_factory=factory)
    if result.get("status")=="retry-possible" and result["attempts"]<2:
        time.sleep(5)
        if _window(_now())==window:
            result=attempt_once(root,inbox,policy,resolve,provider,backup_factory=factory)
    return result

def launchd_template(root,release_sha):
    """Generate bytes only. No launchctl, writes, provisioning or activation."""
    root=Path(root)
    if not root.is_absolute() or root.resolve()!=root or len(release_sha)!=40 or any(c not in "0123456789abcdef" for c in release_sha):
        raise ManualContextError("invalid launchd release path")
    py=root/"venvs"/release_sha/"bin"/"python"
    script=root/"releases"/release_sha/"source"/"reference"/"python"/"wsf_roadmap_collector.py"
    return plistlib.dumps({"Label":LABEL,"ProgramArguments":[str(py),"-B",str(script),"collect","--root",str(root)],
            "StartInterval":INTERVAL,"RunAtLoad":True,"KeepAlive":False,"ProcessType":"Background",
            "Umask":63,"WorkingDirectory":str(root),"StandardOutPath":str(root/"logs"/"roadmap-collector.out.log"),
            "StandardErrorPath":str(root/"logs"/"roadmap-collector.err.log"),
            "EnvironmentVariables":{"PYTHONDONTWRITEBYTECODE":"1"}},sort_keys=True)
