#!/usr/bin/env python3
"""Exact selected-Mac second admission; draft cannot perform writes."""
import json,platform,subprocess,sys
from pathlib import Path
from workspace_app.access import P704AccessResolver
from workspace_app.wsf_company_control_reference import CompanyControlReference
from workspace_app.wsf_company_control_material_admission import load_material_plan,MaterialAdmission,PUBLICATION
from workspace_app.wsf_manual_context import ManualContextError
from wsf_company_control_successor_operator import company_writer,ROOT,OS,COMPANY
from wsf_collector_operator import maintenance
import p7_06_governed_deploy as p706

DECISION_PATH="docs/governance/decisions/DECISION-2026-11-20-AC401-MATERIAL-WORK-002-003.md"
DECISION_BLOB="554e77a891dc0bd4f1ed6d6ba9d36b7da0b726a0"
CONTRACT_PATH="docs/contracts/WSF-05-COMPANY-CONTROL-MATERIAL-PROVISIONAL-v0.5.6.md"

def main():
    if sys.argv[1:]!=["--confirm-exact-approved-transition"] or platform.system()!="Darwin":
        raise ManualContextError("explicit selected Mac confirmation required")
    plan=load_material_plan(ROOT)
    if DECISION_BLOB is None:raise ManualContextError("Company decision unpublished")
    release=p706.current_release(ROOT)
    if (Path(__file__).resolve()!=ROOT/"releases"/release/"source/reference/python"/Path(__file__).name
        or Path(sys.executable)!=ROOT/"venvs"/release/"bin/python"):
        raise ManualContextError("exact installed release required")
    p706.verify_release(ROOT,release)
    def git(repo,*args):
        return subprocess.check_output(["git","-C",str(repo),*args],timeout=10).decode().strip()
    if git(OS,"ls-remote","origin","refs/heads/main").split()[0]!=release or git(OS,"rev-parse",release+":"+CONTRACT_PATH)!=PUBLICATION:
        raise ManualContextError("effective canonical release required")
    company=git(COMPANY,"ls-remote","origin","refs/heads/main").split()[0]
    if git(COMPANY,"rev-parse",company+":"+DECISION_PATH)!=DECISION_BLOB:
        raise ManualContextError("Company decision mismatch")
    writer=company_writer()
    status=MaterialAdmission(CompanyControlReference(ROOT),P704AccessResolver(ROOT).authorize,writer,maintenance).run(plan)
    print(json.dumps({"status":status,"scope":"exact-reviewed-WORK-002-003"}))

if __name__=="__main__":
    try:main()
    except Exception:raise SystemExit("Material work transition denied or interrupted; preserve private evidence") from None
