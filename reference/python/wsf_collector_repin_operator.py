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
             "reference/python/wsf_company_control_successor_operator.py"}
    return all(p in allowed or p.startswith(("docs/","reference/python/workspace_frontend/src/",
                "reference/python/workspace_frontend/dist/","reference/python/workspace_tests/","reference/python/tests/")) for p in paths)

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
    if not compatible([p for p in paths if p]):raise ManualContextError("not a compatible bounded successor")
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
