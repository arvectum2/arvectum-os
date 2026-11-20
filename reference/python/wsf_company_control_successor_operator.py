#!/usr/bin/env python3
"""Selected-Mac exact, published AC-401 successor only. No approval generator."""
import json,platform,subprocess,sys,types
from pathlib import Path
from workspace_app.access import P704AccessResolver
from workspace_app.wsf_company_control_reference import CompanyControlReference
from workspace_app.wsf_company_control_admission import load_plan,DiskCutover,PUBLICATION
from workspace_app.wsf_manual_context import ManualContextError
from wsf_collector_operator import maintenance
import p7_06_governed_deploy as p706

COMPANY=Path("/Volumes/ArvectumSSD/Arvectum/repos/arvectum-company")
WRITER_BLOB="f21bdd430134b45013330693719d3bc33d542b0e"
DECISION_PATH="docs/governance/decisions/DECISION-2026-11-20-AC401-WORK001-SUCCESSOR.md"
DECISION_BLOB="e726a059bba8e1f2ad847fb1a5575e5ad49a75c7"
OS=Path("/Volumes/ArvectumSSD/Arvectum/repos/arvectum-os")
CONTRACT_PATH="docs/contracts/WSF-05-COMPANY-CONTROL-SUCCESSOR-PROVISIONAL-v0.5.5.md"
ROOT=Path.home()/"Library/Application Support/ArvectumOS/persistent-internal"

def company_writer():
    def git(*args):
        return subprocess.check_output(["git","-C",str(COMPANY),*args],timeout=10)
    remote=git("ls-remote","origin","refs/heads/main").decode().split()[0]
    if git("rev-parse","origin/main").decode().strip()!=remote:
        raise ManualContextError("Company canonical checkout stale")
    if git("rev-parse",remote+":tools/company_control_register.py").decode().strip()!=WRITER_BLOB:
        raise ManualContextError("Company writer not published")
    if git("rev-parse",remote+":"+DECISION_PATH).decode().strip()!=DECISION_BLOB:
        raise ManualContextError("Company approval not published")
    code=git("show",WRITER_BLOB)
    m=types.ModuleType("approved_company_control_register")
    exec(compile(code,"approved-company-control-register","exec"),m.__dict__)
    return m

def main():
    if sys.argv[1:]!=["--confirm-exact-approved-transition"] or platform.system()!="Darwin":
        raise ManualContextError("explicit selected Mac confirmation required")
    plan=load_plan(ROOT) # Fail before any maintenance or source write on draft.
    release=p706.current_release(ROOT)
    if (Path(__file__).resolve()!=ROOT/"releases"/release/"source/reference/python"/Path(__file__).name
        or Path(sys.executable)!=ROOT/"venvs"/release/"bin/python"):
        raise ManualContextError("exact installed release required")
    p706.verify_release(ROOT,release)
    def git(*args):
        return subprocess.check_output(["git","-C",str(OS),*args],timeout=10).decode().strip()
    if git("ls-remote","origin","refs/heads/main").split()[0]!=release or git("rev-parse",release+":"+CONTRACT_PATH)!=PUBLICATION:
        raise ManualContextError("effective canonical release required")
    writer=company_writer()
    out=DiskCutover(CompanyControlReference(ROOT),P704AccessResolver(ROOT).authorize,writer,maintenance).run(plan)
    print(json.dumps({"status":out,"scope":"exact-reviewed-WORK-001"}))

if __name__=="__main__":
    try:main()
    except Exception:raise SystemExit("AC-401 transition denied or interrupted; preserve private evidence") from None
