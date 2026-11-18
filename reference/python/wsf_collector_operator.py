#!/usr/bin/env python3
"""Selected-Mac offline operator, inactive until exact publication pin.

Does not unload jobs, stop processes, create owner approvals or install launchd.
Use reviewed separate owner decision and maintenance window.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

import p7_04_persistent_access as p704
import p7_06_governed_deploy as p706
import p9_11_workspace_process as p911
from workspace_app.access import P704AccessResolver
from workspace_app import wsf_collector_runtime as runtime
from workspace_app.wsf_collector_provision import approval_document,provision,recover,APPROVAL
from workspace_app.wsf_inbox_runtime import RuntimeInboxPilot,SUCCESSOR_DRAFT,OPERATIONS,RESOURCE,SCHEMA as OLD_SCHEMA,RECEIPT_SCHEMA as OLD_RECEIPT
from workspace_app.wsf_roadmap_inbox import RoadmapInbox
from workspace_app.wsf_local_roadmap_collector import ACTIVE,EXPIRY,REGISTRY,exact_registry
from workspace_app.wsf_manual_backup import PilotBackup,VOLUME
from workspace_app.wsf_inbox_routes import INBOX_PARTS
from workspace_app.wsf_manual_context import ManualContextError,_identity,_digest,_json
from workspace_app.wsf_manual_policy import _private_file
from workspace_app.wsf_collector_source import FixedSourceReader
from workspace_app.company_portfolio_verified import VerifiedRuntimeCompanyPortfolioProvider
from workspace_app.wsf_inbox_registry_migration import syncdir
from wsf_manual_operator import write_new

REPO=Path("/Volumes/ArvectumSSD/Arvectum/repos/arvectum-os")
CONTRACT="docs/contracts/WSF-07A-LOCAL-ROADMAP-COLLECTOR-PROVISIONAL-v0.6.2.md"
LABELS=("com.arvectum.os.wsf-manual-backup","com.arvectum.os.roadmap-collector")

def admit(root,release):
    publication=runtime.PUBLICATION_PIN
    if publication is None or platform.system()!="Darwin" or root.resolve()!=root or not root.is_absolute() or not re.fullmatch("[0-9a-f]{40}",release):
        raise ManualContextError("effective publication or selected device unavailable")
    # Path checks are exact, not inferred from cwd.
    expected=root/"releases"/release/"source"/"reference"/"python"/Path(__file__).name
    py=root/"venvs"/release/"bin"/"python"
    if Path(__file__).resolve()!=expected or Path(sys.executable)!=py or sys.version_info[:2]!=(3,14):
        raise ManualContextError("operator must run from admitted release")
    if not (root/"current").is_symlink() or (root/"current").resolve()!=root/"releases"/release:
        raise ManualContextError("active release mismatch")
    p706.verify_release(root,release)
    # Merely building a draft PR cannot admit the operator. Require the
    # deployed commit to be reachable from locally verified canonical main.
    if subprocess.run(["git","-C",str(REPO),"merge-base","--is-ancestor",release,"origin/main"],
                      stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5).returncode!=0:
        raise ManualContextError("release is not published on canonical main")
    raw=subprocess.check_output(["git","-C",str(REPO),"show",release+":"+CONTRACT],timeout=8)
    blob=hashlib.sha1(("blob "+str(len(raw))+"\0").encode()+raw).hexdigest()
    if blob!=publication or runtime.DRAFT_BLOB.encode() not in raw:
        raise ManualContextError("canonical publication pin mismatch")
    return publication

def _job_absent(domain,label):
    r=subprocess.run(["/bin/launchctl","print",domain+"/"+label],capture_output=True,text=True,timeout=5)
    return r.returncode!=0 and 'Could not find service "'+label+'" in domain' in r.stderr

def quiescent(root):
    if p911.status(root)["state"]!=p911.NOT_RUNNING:
        raise ManualContextError("Workspace must be stopped")
    domain="gui/"+str(os.getuid())
    if subprocess.run(["/bin/launchctl","print",domain],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5).returncode!=0:
        raise ManualContextError("launchd domain unavailable")
    if not all(_job_absent(domain,x) for x in LABELS):
        raise ManualContextError("backup and collector jobs must be unloaded")
    rows=subprocess.check_output(["/bin/ps","-axo","pid=,command="],text=True,timeout=5).splitlines()
    names=("wsf_manual_daily_backup.sh","wsf_manual_operator.py","wsf_inbox_operator.py","wsf_roadmap_collector.py","wsf_crm_operator.py")
    if any(any(n in row for n in names) for row in rows):
        raise ManualContextError("backup or collector process still present")

@contextmanager
def maintenance(root):
    lock=root/"run"/"p7-06-deploy.lock"
    lock.mkdir(mode=0o700,exist_ok=False)
    pid=lock/"pid"
    try:
        write_new(pid,(str(os.getpid())+"\n").encode())
        quiescent(root)
        yield lambda:quiescent(root)
    finally:
        # No recursive deletion and no takeover of a stale or foreign lock.
        if pid.is_file() and not pid.is_symlink() and pid.read_text().strip()==str(os.getpid()):
            pid.unlink();lock.rmdir();syncdir(lock.parent)

def check_sources():
    reader=FixedSourceReader()
    provider=VerifiedRuntimeCompanyPortfolioProvider(REGISTRY,reader=reader)
    for d in provider._descriptors:
        if d.project_id in ACTIVE:
            source=reader.read(d)
            if not reader.content_sha256_for(source.repository,source.path,source.commit_sha):
                raise ManualContextError("source evidence missing")
    return True

REVIEW="roadmap-collector-review.json"

def predecessor(root,owner,*,recovery=False):
    # Existing human grants remain independently checked, including recovery
    # while the new provision journal deliberately closes the runtime gate.
    if not recovery:
        pilot=RuntimeInboxPilot(root)
        for op in OPERATIONS:pilot.authorize(owner,op)
        legacy,start,end,_=pilot._gate(owner,"export")
        if legacy.file.binding_digest!=runtime.REGISTRY_SHA:
            raise ManualContextError("wrong predecessor registry")
        return legacy,min(end,EXPIRY)
    raw=_private_file(root/"config"/"roadmap-inbox-policy.json")
    p=json.loads(raw)
    receipt=json.loads(_private_file(root/"config"/"roadmap-inbox-activation.json"))
    if (receipt!={"schema":OLD_RECEIPT,"draft_blob":SUCCESSOR_DRAFT,"policy_sha256":_digest(raw)}
        or p["schema"]!=OLD_SCHEMA or p["draft_blob"]!=SUCCESSOR_DRAFT or p["registry_sha256"]!=runtime.REGISTRY_SHA
        or p["scope"]!=_identity(owner) or p["credential_id"]!=owner.credential_id or p["purpose"]!="owner-triggered-roadmap-metadata"):
        raise ManualContextError("recovery predecessor binding mismatch")
    for op in OPERATIONS.values():
        d=p704.authorize_from_credential_file(root,organization=owner.organization,principal=owner.actor,
          credential_id=owner.credential_id,credential_file=root/"secrets"/"p7-04"/(owner.credential_id+".secret"),
          operation=op,resource=RESOURCE,access_path="local")
        if not d.allowed or d.principal_kind!="human" or d.grant_id!=p["grants"][op]:
            raise ManualContextError("recovery human grant denied")
    end=min(datetime.fromisoformat(p["expires_at"]),EXPIRY)
    # Recovery restores previously admitted history; it does not extend expiry.
    return RoadmapInbox(root/"workspace-company-roadmap-inbox",owner,bindings=exact_registry(),require_initialized=True),end

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("operation",choices=("review","record-approval","provision","recover"))
    parser.add_argument("--root",required=True,type=Path)
    parser.add_argument("--release",required=True)
    parser.add_argument("--decision",required=True)
    parser.add_argument("--archive-name",required=True)
    parser.add_argument("--review-sha")
    parser.add_argument("--confirm",action="store_true")
    a=parser.parse_args()
    root=a.root;publication=admit(root,a.release)
    if not re.fullmatch("collector-062-[A-Za-z0-9-]{8,80}",a.archive_name):
        raise ManualContextError("archive name invalid")
    archive=VOLUME.joinpath(*INBOX_PARTS)/a.archive_name
    owner=P704AccessResolver(root).authorize()
    legacy,expires=predecessor(root,owner,recovery=a.operation=="recover")
    backup=PilotBackup(legacy.file,parts=INBOX_PARTS)
    if a.operation=="review":
        check_sources()
        doc=approval_document(root,owner,legacy,backup,a.release,publication,a.decision,archive,expires)
        raw=_json(doc);write_new(root/"config"/REVIEW,raw)
        print(json.dumps({"status":"review-only","review_sha256":_digest(raw),"release":a.release,"sources":8,"expires_at":expires.isoformat()}))
        return
    if not a.confirm:
        raise ManualContextError("explicit owner decision required")
    if a.operation=="record-approval":
        raw=_private_file(root/"config"/REVIEW)
        if a.review_sha!=_digest(raw) or json.loads(raw)!=approval_document(root,owner,legacy,backup,a.release,publication,a.decision,archive,expires):
            raise ManualContextError("review changed; no approval recorded")
        write_new(root/"config"/APPROVAL,raw)
        print('{"status":"approval-recorded","provisioned":false}')
        return
    verified=check_sources() if a.operation=="provision" else False
    with maintenance(root) as quiet:
        if a.operation=="provision":
            # Re-read bound human context after obtaining maintenance lock.
            owner=P704AccessResolver(root).authorize()
            legacy,expires=predecessor(root,owner)
            backup=PilotBackup(legacy.file,parts=INBOX_PARTS)
            out=provision(root,owner,legacy,backup,release=a.release,publication=publication,
              decision=a.decision,archive=archive,expires=expires,quiescent=quiet,confirm=True,source_verified=verified)
        else:
            j=json.loads(_private_file(root/"config"/runtime.PROVISION_JOURNAL))
            if j["approval"]["archive"]!=str(archive):
                raise ManualContextError("recovery archive mismatch")
            out=recover(root,owner,legacy,backup,release=a.release,publication=publication,
                decision=a.decision,quiescent=quiet,confirm=True)
    print(json.dumps(out,sort_keys=True))

if __name__=="__main__":
    try:main()
    except Exception:
        # Private IDs and source tokens must not appear in console output.
        raise SystemExit("Collector operator denied or interrupted; consult private journal and reviewed runbook") from None
