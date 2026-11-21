#!/usr/bin/env python3
"""Explicit selected-device compatible re-pin, no launchd or access mutation."""
import argparse
import json
from pathlib import Path
import re
import platform
import subprocess
import sys
import p7_06_governed_deploy as p706
from workspace_app.access import P704AccessResolver
from workspace_app.wsf_collector_runtime import PUBLICATION_PIN
from workspace_app.wsf_collector_repin import switch
from workspace_app.wsf_manual_context import ManualContextError
from workspace_app.wsf_manual_policy import _private_file
from workspace_app.wsf_manual_backup import PilotBackup,VOLUME
from workspace_app.wsf_inbox_routes import INBOX_PARTS
from wsf_collector_operator import maintenance,predecessor,REPO,CONTRACT
from workspace_app.wsf_collector_runner import LABEL

def compatible(paths):
    # No change to collection, policy, dependency lock, store or authorization code.
    allowed={"reference/python/workspace_app/release.json","reference/python/wsf_collector_repin_operator.py",
             "reference/python/workspace_app/wsf_collector_repin.py","reference/python/p7_06_macos_deploy.sh",
             # AC-401 read/cutover only; collector contracts, source reader,
             # policy, access store and dependencies remain excluded.
             "reference/python/workspace_app/wsf_company_control_reference.py",
             "reference/python/workspace_app/wsf_company_control_successor.py",
             "reference/python/workspace_app/wsf_company_control_cutover.py",
             "reference/python/workspace_app/wsf_company_control_admission.py",
             "reference/python/workspace_app/ac401-approved-publication.md",
             "reference/python/workspace_app/ac401-material-approved-publication.md",
             "reference/python/workspace_app/wsf_company_control_material.py",
             "reference/python/workspace_app/wsf_company_control_material_admission.py",
             "reference/python/wsf_company_control_material_operator.py",
             "reference/python/wsf_company_control_successor_operator.py",
             "reference/python/workspace_app/wsf_local_control.py",
             "reference/python/workspace_app/wsf_decision_reference.py",
             "reference/python/workspace_app/wsf_risk_reference.py",
             "reference/python/workspace_app/ac402-403-local-publication.md",
             "reference/python/wsf_local_control_operator.py"}
    return all(p in allowed or p.startswith(("docs/","reference/python/workspace_frontend/src/",
                "reference/python/workspace_frontend/dist/","reference/python/workspace_tests/","reference/python/tests/")) for p in paths)

# Exact, Owner-approved queue successor. Do not broaden the generic allowlist.
QUEUE_SOURCE = "83c0458fa108dd512ee0dbcd976238a3595a8f07"
QUEUE_ANCHOR = "58fad791a53769f8d87a7c2d60333388fbc8ff91"
QUEUE_DECISION = "OWNER-2026-11-20-WSF05-OWNER-PROJECT-QUEUE"
QUEUE_CONTRACT = "docs/contracts/WSF-05-OWNER-PROJECT-QUEUE-v0.5.8.md"
QUEUE_CONTRACT_BLOB = "0af2c545f0e68c4f0b8d684a11e3d9051a6d30a5"
QUEUE_SUCCESSOR_FILES = {
    "reference/python/wsf_collector_repin_operator.py",
    "reference/python/workspace_tests/test_wsf_owner_queue_collector_compatibility.py",
}

def exact_queue_successor(source, target, decision, *, git=None):
    if source != QUEUE_SOURCE or decision != QUEUE_DECISION:
        return False
    if not re.fullmatch("[0-9a-f]{40}", target):
        return False
    if git is None:
        def git(*args):
            return subprocess.check_output(["git", "-C", str(REPO), *args], timeout=10)
    try:
        git("merge-base", "--is-ancestor", QUEUE_ANCHOR, target)
        if git("rev-parse", target + ":" + QUEUE_CONTRACT).decode().strip() != QUEUE_CONTRACT_BLOB:
            return False
        paths = set(git("diff", "--name-only", "--no-renames", "-z", QUEUE_ANCHOR, target).decode().split("\0")) - {""}
        # A release containing this compatibility verification may differ
        # from the exact reviewed queue anchor only by this operator and its test.
        return paths == QUEUE_SUCCESSOR_FILES
    except (OSError, ValueError, subprocess.SubprocessError):
        return False

# Exact Git-first source change admitted only under the separate Owner decision.
# This does not broaden the existing compatible UI/operations envelope.
GIT_FIRST_SOURCE = "824cc89723495ee6bab7c38e7557821f369c934f"
GIT_FIRST_DECISION = "OWNER-2026-11-21-WSF07A-GIT-FIRST-FAILOVER"
GIT_FIRST_FILES = {
    "docs/engineering/WSF-07A-GIT-SOURCE-FAILOVER-PROPOSAL-2026-11-21.md",
    "docs/governance/decisions/DECISION-2026-11-21-WSF07A-GIT-FIRST-FAILOVER.md",
    "reference/python/workspace_app/f11_routes.py",
    "reference/python/workspace_app/wsf_collector_git_source.py",
    "reference/python/workspace_app/wsf_collector_source.py",
    "reference/python/workspace_tests/test_wsf_collector_git_source.py",
    "reference/python/workspace_tests/test_wsf_collector_git_repin.py",
    "reference/python/wsf_collector_repin_operator.py",
}

def exact_git_first_successor(source, target, decision, *, git=None):
    if source != GIT_FIRST_SOURCE or decision != GIT_FIRST_DECISION or not re.fullmatch("[0-9a-f]{40}",target):
        return False
    if git is None:
        def git(*args):
            return subprocess.check_output(["git", "-C", str(REPO), *args],timeout=10)
    try:
        git("merge-base", "--is-ancestor", GIT_FIRST_SOURCE, target)
        before = git("rev-parse", GIT_FIRST_SOURCE + ":" + CONTRACT).decode().strip()
        after = git("rev-parse", target + ":" + CONTRACT).decode().strip()
        if before != after or not re.fullmatch("[0-9a-f]{40}",after):
            return False
        actual = set(git("diff","--name-only","--no-renames","-z",GIT_FIRST_SOURCE,target).decode().split("\0"))-{""}
        return actual == GIT_FIRST_FILES
    except (OSError,ValueError,subprocess.SubprocessError):
        return False

# Bounded combined successor: source-watch read UI and Python 3.14/F11 repair only.
# The source is the exact Git-first release. Never accepts an arbitrary Workspace update.
SOURCE_SYNC_ANCHOR = "963ae125921cab23ebca5f826724395452126af4"
SOURCE_SYNC_DECISION = "OWNER-2026-11-21-MC-SOURCE-SYNC-REPIN"
SOURCE_SYNC_FILES = frozenset({
    "docs/engineering/WSF-07A-GIT-FIRST-LIVE-FOLLOWUP-2026-11-21.md",
    "docs/engineering/F11-COMPANY-SOURCE-WATCH-READ-ONLY-OWNER-VIEW-2026-11-21.md",
    "docs/governance/decisions/DECISION-2026-11-21-MC-SOURCE-SYNC-REPIN.md",
    "reference/python/p7_06_macos_deploy.sh",
    "reference/python/tests/test_p7_06_macos_deploy.py",
    "reference/python/workspace_app/f11_routes.py",
    "reference/python/workspace_app/company_source_watch_evidence.py",
    "reference/python/workspace_frontend/dist/.vite/manifest.json",
    "reference/python/workspace_frontend/dist/assets/index-CMmcmoc_.js",
    "reference/python/workspace_frontend/dist/assets/index-k_S1EF-z.js",
    "reference/python/workspace_frontend/dist/index.html",
    "reference/python/workspace_frontend/src/CompanySourceWatch.test.tsx",
    "reference/python/workspace_frontend/src/CompanySourceWatch.tsx",
    "reference/python/workspace_frontend/src/MissionControl.tsx",
    "reference/python/workspace_frontend/src/f11Api.ts",
    "reference/python/workspace_frontend/src/f11Types.ts",
    "reference/python/workspace_tests/test_company_source_watch_evidence.py",
    "reference/python/workspace_tests/test_wsf07a_f11_python_pin.py",
    "reference/python/workspace_tests/test_wsf_collector_source_sync_repin.py",
    "reference/python/wsf_collector_repin_operator.py",
})

def exact_source_sync_successor(source,target,decision,*,git=None):
    if source!=SOURCE_SYNC_ANCHOR or decision!=SOURCE_SYNC_DECISION or not re.fullmatch("[0-9a-f]{40}",target):
        return False
    if git is None:
        def git(*args):
            return subprocess.check_output(["git","-C",str(REPO),*args],timeout=10)
    try:
        git("merge-base","--is-ancestor",SOURCE_SYNC_ANCHOR,target)
        old_blob=git("rev-parse",SOURCE_SYNC_ANCHOR+":"+CONTRACT).decode().strip()
        new_blob=git("rev-parse",target+":"+CONTRACT).decode().strip()
        if old_blob!=new_blob or not re.fullmatch("[a-f0-9]{40}",new_blob):
            return False
        changed=set(git("diff","--name-only","--no-renames","-z",SOURCE_SYNC_ANCHOR,target).decode().split("\0"))-{""}
        return changed==SOURCE_SYNC_FILES
    except (OSError,ValueError,subprocess.SubprocessError):
        return False

def verify(root,source,target,decision):
    if platform.system()!="Darwin" or not root.is_absolute() or root.resolve()!=root:
        raise ManualContextError("selected Mac required")
    expected=root/"releases"/target/"source"/"reference"/"python"/Path(__file__).name
    if Path(__file__).resolve()!=expected or Path(sys.executable)!=root/"venvs"/target/"bin"/"python" or sys.version_info[:2]!=(3,14):
        raise ManualContextError("exact installed interpreter required")
    if p706.current_release(root)!=target:raise ManualContextError("target is not current")
    for sha in (source,target):
        p706.verify_release(root,sha)
        if subprocess.run(["git","-C",str(REPO),"merge-base","--is-ancestor",sha,"origin/main"],capture_output=True,timeout=5).returncode:
            raise ManualContextError("release is not canonical")
        if subprocess.check_output(["git","-C",str(REPO),"rev-parse",sha+":"+CONTRACT],text=True,timeout=5).strip()!=PUBLICATION_PIN:
            raise ManualContextError("contract changed")
    paths=subprocess.check_output(["git","-C",str(REPO),"diff","--name-only","--no-renames","-z",source,target],timeout=10).decode().split("\0")
    if not compatible([p for p in paths if p]) and not exact_queue_successor(source,target,decision) and not exact_git_first_successor(source,target,decision) and not exact_source_sync_successor(source,target,decision):
        raise ManualContextError("not a compatible bounded successor")
    pointer=json.loads(_private_file(root/"run"/"p7-06-last-success.json"))
    txid=pointer["transaction_id"];pid=pointer["plan_id"]
    if not all(re.fullmatch("[0-9a-f]{64}",v) for v in (txid,pid)):raise ManualContextError("invalid deployment evidence")
    tx=json.loads(_private_file(root/"evidence"/"p7-06"/"transactions"/(txid+".json")))
    plan=json.loads(_private_file(root/"evidence"/"p7-06"/"plans"/(pid+".json")))
    if (any(x.get("source_release")!=source or x.get("target_release")!=target for x in (pointer,tx,plan))
        or tx.get("transaction_id")!=txid or tx.get("plan_id")!=pid or plan.get("plan_id")!=pid
        or tx.get("result")!="PASS" or tx.get("runtime_release_verified") is not True or tx.get("observer_release_verified") is not True
        or plan.get("operator_decision_ref")!=decision):
        raise ManualContextError("exact successful governed deployment required")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True);p.add_argument("--source",required=True)
    p.add_argument("--target",required=True);p.add_argument("--decision",required=True)
    p.add_argument("--archive-name",required=True);p.add_argument("--confirm",action="store_true")
    a=p.parse_args()
    if not a.confirm or not all(re.fullmatch("[0-9a-f]{40}",s) for s in (a.source,a.target)) or not re.fullmatch("collector-repin-[A-Za-z0-9-]{8,80}",a.archive_name):
        raise ManualContextError("explicit re-pin decision required")
    check=lambda:verify(a.root,a.source,a.target,a.decision)
    check()
    with maintenance(a.root) as quiet:
        owner=P704AccessResolver(a.root).authorize()
        predecessor(a.root,owner,recovery=True)
        out=switch(a.root,owner,source=a.source,target=a.target,publication=PUBLICATION_PIN,
            decision=a.decision,archive=VOLUME.joinpath(*INBOX_PARTS)/a.archive_name,
            plist=Path.home()/"Library"/"LaunchAgents"/(LABEL+".plist"),
            backup_factory=lambda f:PilotBackup(f,parts=INBOX_PARTS),quiescent=quiet,verify_release=check,confirm=True)
    print(json.dumps(out,sort_keys=True))

if __name__=="__main__":
    try:main()
    except Exception:raise SystemExit("Collector re-pin denied or interrupted; inspect private evidence and resume exact approved operation") from None
