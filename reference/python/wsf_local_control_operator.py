#!/usr/bin/env python3
"""One Owner-directed local activation; no standing write authority."""
import json,sys,platform,subprocess,tempfile,os
from pathlib import Path
from workspace_app import wsf_local_control as local
from workspace_app.wsf_company_control_reference import read_snapshot,sha
from workspace_app.wsf_manual_context import _json
from workspace_app.wsf_decision_reference import DecisionReference
from workspace_app.wsf_risk_reference import RiskReference
from workspace_app.access import P704AccessResolver
from workspace_app.wsf_manual_backup import PilotBackup
from types import SimpleNamespace
from wsf_manual_operator import write_new
from wsf_collector_operator import maintenance
import p7_06_governed_deploy as deploy

ROOT=Path.home()/"Library/Application Support/ArvectumOS/persistent-internal"
COMPANY=Path("/Volumes/ArvectumSSD/Arvectum/repos/arvectum-company")
OS=COMPANY.parent/"arvectum-os"
ACT="edc59e48b1788859e275907d3d6749b7a88e1da6"
ACT_PATH="docs/governance/decisions/DECISION-2026-11-20-AC402-403-LOCAL-ADMISSION.md"
CONTRACT="docs/contracts/WSF-05-LOCAL-CONTROL-ADMISSION-v0.5.7.md"
WRITERS={"company_control_pair":"6cfa85b39f2d74d6279d4c7acd76ecf75d546143",
"company_decision_register":"da53c12ef47efd6f105d7aec2c94251a69f9f629",
"company_risk_register":"66a838420208fe2d2711d5237daab27c71d6e449",
"company_control_register":"f21bdd430134b45013330693719d3bc33d542b0e"}
PLANS={
"decision":("f81de7faa474f25ce78cf9a2585ceb61833e2636c21fe4dc693746b69e633278",(("DEC-004","e4c08565e285b45469953ee320252ea812bc7cb679c9147ea0f1e672ada97d54"),("DEC-005","bdd8691f6d28fa09b9f2c229ffeff79ffc34c75dbffad49ec303458091695bcc"))),
"risk":("33df0cbe647f781174d8d77783173917c1afbf40d6cb9929e9c649ca94e17b22",(("RSK-002","86183ff2d33495e4f52ac5a304db733b121331e10395acb6585c652b9a24d515"),))}
def git(repo,*args):
    return subprocess.check_output(["git","-C",str(repo),*args],timeout=10).decode().strip()
def main():
    local.need(sys.argv[1:]==["--confirm-initial-owner-approved-appends"] and platform.system()=="Darwin","confirmation")
    release=deploy.current_release(ROOT)
    local.need(Path(__file__).resolve()==ROOT/"releases"/release/"source/reference/python"/Path(__file__).name and Path(sys.executable)==ROOT/"venvs"/release/"bin/python","installed release")
    deploy.verify_release(ROOT,release)
    local.need(git(OS,"ls-remote","origin","refs/heads/main").split()[0]==release and git(OS,"rev-parse",release+":"+CONTRACT)==local.PUBLICATION,"canonical release")
    commit=git(COMPANY,"ls-remote","origin","refs/heads/main").split()[0]
    local.need(git(COMPANY,"rev-parse",commit+":"+ACT_PATH)==ACT,"published act")
    for name,pin in WRITERS.items():local.need(git(COMPANY,"rev-parse",commit+":tools/"+name+".py")==pin,"writer pin")
    auth=P704AccessResolver(ROOT).authorize
    review=Path.home()/"Library/Application Support/ArvectumCompany/control-review/2026-11-20-ac402-403"
    receipt=ROOT/"config/ac402-403-local-activation.json"
    rawreceipt=_json({"schema":"arvectum.workspace.local-control-activation/1","publication":local.PUBLICATION,"owner_act":ACT})
    with tempfile.TemporaryDirectory(prefix="local-approved-writer-") as tmp:
        pkg=Path(tmp)/"tools";pkg.mkdir(mode=0o700);(pkg/"__init__.py").touch()
        for name,pin in WRITERS.items():
            (pkg/(name+".py")).write_bytes(subprocess.check_output(["git","-C",str(COMPANY),"show",pin],timeout=10))
        sys.path.insert(0,tmp)
        from tools import company_decision_register as d,company_risk_register as r
        from tools.company_control_pair import append_pair
        with maintenance(ROOT) as quiet:
            prepared=[]
            for kind,ref,mod in (("decision",DecisionReference(ROOT),d),("risk",RiskReference(ROOT),r)):
                p,_,signal=ref.gate(auth());pin,steps=PLANS[kind]
                successors=[]
                for name,digest in steps:
                    raw=read_snapshot(review/(name+".candidate.private.json"))
                    local.need(sha(raw)==digest,"approved candidate changed")
                    mod.replay(json.loads(raw));local.project(raw,p["source_sha256"],kind,signal,ref.clock().isoformat())
                    successors.append(raw)
                base,_=local.validate(successors[0],pin,kind,ref.clock().isoformat())
                old=mod.canonical(base)
                local.need(sha(old)==pin==p["source_sha256"],"baseline pin")
                backup=PilotBackup(SimpleNamespace(directory=ref.source.parent),parts=("Arvectum","backups","arvectum-company",kind+"-register"))
                target=backup.volume.joinpath(*backup.parts,"latest.private.json")
                states=[old]+successors
                pair=(read_snapshot(ref.source),local.backup_bytes(ref,kind))
                local.need(pair in [(x,x) for x in states]+list(zip(states[1:],states[:-1])),"unexpected source pair")
                prepared.append((kind,ref,mod,backup,target,states))
            if receipt.exists():local.need(local.enabled(ROOT),"receipt mismatch")
            else:write_new(receipt,rawreceipt)
            local.need(local.enabled(ROOT),"activation missing")
            for kind,ref,mod,backup,target,states in prepared:
                with backup._destination() as fd:
                    st=os.fstat(fd)
                    def destination():
                        with backup._destination() as other:
                            now=os.fstat(other);local.need((now.st_dev,now.st_ino)==(st.st_dev,st.st_ino),"backup changed")
                    def authority():
                        quiet();ref.gate(auth());local.need(local.enabled(ROOT),"activation lost")
                    for i,(old,new) in enumerate(zip(states,states[1:])):
                        if read_snapshot(ref.source) in states[i+2:] and local.backup_bytes(ref,kind) in states[i+1:]:continue
                        append_pair(company=mod,source=ref.source,backup=target,predecessor=old,successor=new,check_authority=authority,check_destination=destination)
                    local.need(read_snapshot(ref.source)==local.backup_bytes(ref,kind)==states[-1],"final pair")
                    result=ref.read(auth);print(kind,len(result["items"]),"PASS")
if __name__=="__main__":
    try:main()
    except Exception:raise SystemExit("Local admission interrupted or denied; preserve reviewed candidates, inspect actual pair") from None
