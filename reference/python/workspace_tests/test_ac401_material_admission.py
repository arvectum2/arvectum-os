"""Second exact admission, temporary private files and synthetic approval seams."""
import copy,json,unittest
from contextlib import contextmanager
from datetime import timedelta
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import p7_04_persistent_access as p704
import workspace_app.wsf_company_control_material_admission as material
from workspace_app.wsf_company_control_material import MaterialPlan,ADDITIONS,STEPS,material_rows
from workspace_app.wsf_company_control_material_admission import (MaterialAdmission,policy_bytes,
    receipt_bytes,load_material_plan,JOURNAL,PREFIX)
from workspace_app.wsf_company_control_admission import write_atomic,Admission
from workspace_app.wsf_company_control_reference import sha
from workspace_app.wsf_manual_context import ManualContextError,_json
from test_ac401_disk_admission import setup_disk
from ac401_cutover_fixture import atomic_replace

DECISION="OWNER-SYNTHETIC-MATERIAL-WORK"
class FixtureCompany:
    @staticmethod
    def canonical(doc):return _json(doc)+b"\n"
    @staticmethod
    def replay(doc):
        return {x["record"]["id"]:x["record"] for x in doc["events"]}
    @staticmethod
    @contextmanager
    def locked_snapshot_writer(path):
        def write(doc,*,expected_digest):
            old=path.read_bytes()
            if sha(old)!=expected_digest or doc["events"][:-1]!=json.loads(old)["events"]:
                raise ManualContextError("fixture predecessor")
            atomic_replace(path,FixtureCompany.canonical(doc))
        yield write

def case(test,company=FixtureCompany):
    c,prev,prevplan=setup_disk(test,company)
    test.enterContext(patch("workspace_app.wsf_company_control_admission.load_plan",return_value=prevplan))
    test.enterContext(patch("workspace_app.wsf_company_control_material_admission.load_plan",return_value=prevplan))
    prev.run(prevplan)
    prevraw=_json(prevplan.__dict__)
    write_atomic(c.base.root/"config/company-control-successor-approved.json",prevraw)
    a=MaterialAdmission(c.runtime,c.base.resolve,company,prev.maintenance)
    a.backup=prev.backup;a.backup_access=prev.backup_access
    old=a.source.read_bytes();d=json.loads(old);r=copy.deepcopy(d["events"][0]["record"])
    now=c.runtime.clock().isoformat()
    paths=("predecessor.private.json","intermediate.private.json","successor.private.json")
    raws=[old]
    for rid,(pos,key) in ADDITIONS.items():
        row={**r,"id":rid,"concern_key":key,"accountable_position":pos,
            "title":"Synthetic "+rid,"company_priority":{"level":"P1","why_now":"Fixture"},
            "attention_state":"needs_attention","control_state":"open",
            "due_or_trigger":{"kind":"none","value":None,"source_ref":None},
            "evidence_as_of":now,"last_reviewed_at":now,"next_control_point":"Check synthetic business evidence"}
        d["events"].append({"sequence":len(d["events"])+1,"prior_digest":sha(_json(d["events"][-1])+b"\n"),
            "at":now,"authority_ref":DECISION,"reason":"Synthetic exact candidate","record":row})
        raws.append(_json(d)+b"\n")
    a.archive.mkdir(mode=0o700)
    for name,raw in zip(paths,raws):atomic_replace(a.archive/name,raw)
    p,pin,review=c.runtime.gate(c.base.resolve())
    plan=MaterialPlan(*map(sha,raws),sha(prevraw),prevplan.policy,prevplan.receipt,"0"*64,"0"*64,DECISION,"f"*40)
    plan=replace(plan,policy=sha(policy_bytes(p,plan)));plan=replace(plan,receipt=sha(receipt_bytes(plan)))
    test.enterContext(patch("workspace_app.wsf_company_control_material_admission.load_material_plan",return_value=plan))
    return c,a,plan,raws

class MaterialTests(unittest.TestCase):
    def test_all_writes_resume_and_preserve_records(self):
        c,a,p,raws=case(self)
        self.assertEqual(p.phase(a.observe()),0)
        original=a.write;writes=[]
        for step in STEPS:
            def stop(s,plan):
                original(s,plan);writes.append(s)
                if s==step:raise OSError("post-write interruption")
            with patch.object(a,"write",side_effect=stop):
                with self.assertRaises(OSError):a.run(p)
            self.assertEqual(p.phase(a.observe()),len(writes))
            with self.assertRaises(ManualContextError):a.project(p)
            with self.assertRaises(ManualContextError):c.runtime.read(c.base.resolve)
        self.assertEqual(a.run(p),"completed")
        self.assertEqual(writes,list(STEPS))
        self.assertEqual(a.run(p),"already-completed")
        self.assertEqual(a.source.read_bytes(),raws[-1])
        self.assertEqual(a.backup.read_bytes(),raws[-1])
        result=a.project(p)
        self.assertEqual([x["id"] for x in result["position_work"]],list(ADDITIONS))
        self.assertFalse(any(x["id"] in ADDITIONS for x in result["delegated_work"]))
        self.assertEqual(len(result["owner_action"]),1)
        self.assertEqual(len(result["obligation_signals"]),2)
        self.assertFalse(result["organizational_authority_provided"])
    def test_wrong_state_and_missing_journal(self):
        c,a,p,raws=case(self)
        atomic_replace(a.backup,raws[1])
        with self.assertRaises(ManualContextError):a.run(p)
        self.assertEqual(a.source.read_bytes(),raws[0])
        atomic_replace(a.backup,raws[0]);atomic_replace(a.source,raws[1])
        with self.assertRaises(ManualContextError):a.run(p)
    def test_malformed_or_reclassified_addition_denied(self):
        c,a,p,raws=case(self)
        for field,value in (("accountable_position","POS-004"),("control_state","waiting"),("kind","obligation"),("closure_ref","fiction"),("due_or_trigger",{"kind":"exact","value":"2026-12-01T00:00:00Z","source_ref":"fiction"})):
            _,_,base,*_=a.previous.check(material.load_plan(a.root))
            d=json.loads(raws[-1]);d["events"][-1]["record"][field]=value
            mutated=_json(d)+b"\n"
            with self.subTest(field=field),self.assertRaises(ManualContextError):
                material_rows(base,raws[0],raws[1],mutated,plan=replace(p,successor=sha(mutated)),now=c.runtime.clock().isoformat())
    def test_revocation_after_first_append_stops_recovery(self):
        c,a,p,raws=case(self)
        original=a.write
        def stop(step,plan):
            original(step,plan);raise OSError()
        with patch.object(a,"write",side_effect=stop):
            with self.assertRaises(OSError):a.run(p)
        p704.revoke_grant(c.base.root,c.base.grant)
        with self.assertRaises(ManualContextError):a.run(p)
        self.assertEqual(a.source.read_bytes(),raws[1])
        self.assertEqual(a.backup.read_bytes(),raws[0])
    def test_unpublished_and_partial_read(self):
        from test_ac401_cutover import make_case
        c=make_case(self)
        with self.assertRaises(ManualContextError):load_material_plan(c.base.root)
        self.assertEqual(len(c.runtime.read(c.base.resolve)["obligation_signals"]),2)
        write_atomic(c.base.root/"config"/(PREFIX+"-activation.json"),b"invalid")
        with self.assertRaises(ManualContextError):c.runtime.read(c.base.resolve)
