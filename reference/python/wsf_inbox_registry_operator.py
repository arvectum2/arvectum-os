#!/usr/bin/env python3
"""Selected Mac offline WSF-07A successor cutover; no automatic service actions."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

from p9_11_workspace_process import status, NOT_RUNNING
from workspace_app.access import P704AccessResolver
from workspace_app.wsf_inbox_registry_migration import cutover
from workspace_app.wsf_inbox_runtime import SUCCESSOR_DRAFT
from workspace_app.wsf_manual_context import ManualContextError
from workspace_app.wsf_manual_backup import VOLUME, VOLUME_UUID, verify_volume
from workspace_app.wsf_inbox_routes import INBOX_PARTS

DECISION = "DECISION-WSF-07A-REGISTRY-LOCATOR-SUCCESSOR-APPROVAL"
BACKUP_LABEL = "com.arvectum.os.wsf-manual-backup"
SELECTED_ROOT = Path.home() / "Library/Application Support/ArvectumOS/persistent-internal"


def assert_offline(root, release):
    state = status(root)
    if state.get("state") != NOT_RUNNING or state.get("current_release") != release:
        raise ManualContextError("Workspace must be stopped on the exact selected release")
    listing = subprocess.check_output(["/bin/launchctl", "list"], text=True, timeout=5)
    if any(line.split()[-1:] == [BACKUP_LABEL] for line in listing.splitlines()):
        raise ManualContextError("daily backup LaunchAgent must be unloaded during cutover")


def execute(root, release, decision, draft, confirm):
    if (sys.platform != "darwin" or root != SELECTED_ROOT or root.resolve() != root
        or not re.fullmatch(r"[0-9a-f]{40}", release)
        or decision != DECISION or draft != SUCCESSOR_DRAFT or not confirm):
        raise ManualContextError("exact selected-device, release and approval required")
    source = root / "releases" / release / "source"
    if (root / "current").resolve() != source.parent or Path(__file__).resolve() != source / "reference/python/wsf_inbox_registry_operator.py":
        raise ManualContextError("operator is not executed from selected installed release")
    publication = source / "docs/contracts/WSF-07A-REGISTRY-LOCATOR-SUCCESSOR-PROVISIONAL-v0.6.1.md"
    approval = source / "docs/governance/decisions" / (DECISION + ".md")
    if not all(p.is_file() and SUCCESSOR_DRAFT in p.read_text(encoding="utf-8") for p in (publication, approval)):
        raise ManualContextError("exact published successor required")
    # Share P7.06 deployment lock; never remove an existing or foreign lock.
    lock = root / "run/p7-06-deploy.lock"
    lock.mkdir(mode=0o700, exist_ok=False)
    pidfile = lock / "pid"
    try:
        fd = os.open(pidfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(str(os.getpid()) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        check = lambda: assert_offline(root, release)
        check()
        verify_volume(VOLUME, VOLUME_UUID)
        archive = VOLUME.joinpath(*INBOX_PARTS) / ("before-061-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:12])
        access = P704AccessResolver(root).authorize()
        result = cutover(root, access, archive, assert_quiescent=check, confirm=True)
        return {**result, "rollback_archive": archive.name}
    finally:
        # Only remove a lock acquired by this process. An unclean interruption
        # leaves a visible lock and requires operator reconciliation.
        if pidfile.is_file() and pidfile.read_text().strip()==str(os.getpid()):
            pidfile.unlink()
            lock.rmdir()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--draft", required=True)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    try:
        result = execute(SELECTED_ROOT, args.release, args.decision, args.draft, args.confirm)
    except (ManualContextError, OSError, ValueError, subprocess.SubprocessError):
        raise SystemExit("Locator cutover stopped; inspect private receipt, rollback archive and deployment lock. Do not start until exact state verified.") from None
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
