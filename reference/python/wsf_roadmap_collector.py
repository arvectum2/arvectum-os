#!/usr/bin/env python3
"""Explicit local CLI; inactive until exact publication and separate provisioning."""
import argparse
import json
from pathlib import Path
import sys
from workspace_app import wsf_collector_runtime as runtime
from workspace_app.wsf_collector_runner import run,launchd_template
from workspace_app.wsf_manual_context import ManualContextError

def main():
    p=argparse.ArgumentParser()
    p.add_argument("operation",choices=("collect","print-plist"))
    p.add_argument("--root",required=True,type=Path)
    p.add_argument("--release")
    a=p.parse_args()
    if a.operation=="print-plist":
        if not a.release:p.error("--release required")
        sys.stdout.buffer.write(launchd_template(a.root,a.release));return 0
    if a.release:p.error("--release not accepted for collection")
    cfg,_=runtime.load_config(a.root,publication=runtime.PUBLICATION_PIN)
    release=cfg["release_sha"]
    expected=a.root/"releases"/release/"source"/"reference"/"python"/Path(__file__).name
    python=a.root/"venvs"/release/"bin"/"python"
    if (Path(__file__).resolve()!=expected or Path(sys.executable)!=python or sys.version_info[:2]!=(3,14)):
        raise ManualContextError("collector exact interpreter/release required")
    result=run(a.root,publication=runtime.PUBLICATION_PIN)
    print(json.dumps(result,sort_keys=True))
    return 0 if result.get("backup_status")=="verified" or (result.get("status")=="not-due" and result.get("previous_state")=="verified") else 1

if __name__=="__main__":
    try:raise SystemExit(main())
    except (ManualContextError,OSError,ValueError,TypeError):
        raise SystemExit("Collector unavailable; review policy, release and backup") from None
