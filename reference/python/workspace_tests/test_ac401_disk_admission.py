import json,os,unittest
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from workspace_app.wsf_company_control_admission import (Admission,DiskCutover,load_plan,policy_bytes,
    receipt_bytes,write_atomic,JOURNAL,PREFIX)
from workspace_app.wsf_company_control_cutover import Plan
from workspace_app.wsf_company_control_reference import sha
from workspace_app.wsf_manual_context import ManualContextError
from workspace_app.wsf_manual_backup import PilotBackup,BACKUP_NAME
from ac401_cutover_fixture import atomic_replace
from test_ac401_cutover import make_case

def setup_disk(test,company):
    c=make_case(test)
    @contextmanager
    def maintenance(root):
        yield lambda:None
    adapter=DiskCutover(c.runtime,c.base.resolve,company,maintenance)
    adapter.archive.mkdir(mode=0o700)
    write_atomic(adapter.archive/"predecessor.private.json",c.old)
    write_atomic(adapter.archive/"successor.private.json",c.new)
    adapter.backup=c.backup
    adapter.backup_access=PilotBackup(SimpleNamespace(directory=c.source.parent),
            volume=c.backup.parent.parent,uuid="fixture",parts=(c.backup.parent.name,),
            verifier=lambda v,u:None)
    p,_,_=c.runtime.gate(c.base.resolve())
    plan=replace(c.plan,policy=sha(policy_bytes(p,c.plan)))
    plan=replace(plan,receipt=sha(receipt_bytes(plan)))
    return c,adapter,plan

class DiskAdmissionTests(unittest.TestCase):
    def test_default_route_legacy_and_dormant_admission(self):
        c=make_case(self)
        self.assertEqual(len(c.runtime.read(c.base.resolve)["obligation_signals"]),2)
        cfg=c.base.root/"config"
        with self.assertRaises((ManualContextError,FileNotFoundError)):load_plan(c.base.root)
        write_atomic(cfg/JOURNAL,b"pending")
        with self.assertRaises(ManualContextError):c.runtime.read(c.base.resolve)
        (cfg/JOURNAL).unlink()
        write_atomic(cfg/(PREFIX+"-activation.json"),b"unpublished")
        with self.assertRaises(ManualContextError):c.runtime.read(c.base.resolve)
        self.assertEqual(c.source.read_bytes(),c.old)
    def test_atomic_artifact_no_overwrite_or_symlink(self):
        c=make_case(self);p=c.base.root/"config"/"test-new.json"
        write_atomic(p,b"one")
        self.assertEqual(p.read_bytes(),b"one")
        with self.assertRaises(ManualContextError):write_atomic(p,b"two")
        q=p.with_name("test-link.json");q.symlink_to(p)
        with self.assertRaises(ManualContextError):write_atomic(q,b"bad")
        self.assertEqual(p.read_bytes(),b"one")
    def test_volume_failure_is_denied(self):
        c=make_case(self)
        a=Admission(c.runtime,c.base.resolve)
        def fail(v,u):raise ManualContextError("wrong volume")
        a.backup_access.verifier=fail
        with self.assertRaises(ManualContextError):a.observe()
        self.assertEqual(c.source.read_bytes(),c.old)
    def test_independent_exact_publication_and_plan_pins(self):
        from hashlib import sha1
        from workspace_app.wsf_manual_context import _json
        c=make_case(self)
        pub=c.base.fixture.base/"synthetic-publication.md"
        publication=b"synthetic effective publication"
        pub.write_bytes(publication)
        blob=sha1(b"blob "+str(len(publication)).encode()+b"\0"+publication).hexdigest()
        plan=replace(c.plan,contract=blob)
        raw=_json(plan.__dict__)
        write_atomic(c.base.root/"config"/(PREFIX+"-approved.json"),raw)
        with patch("workspace_app.wsf_company_control_admission.PUBLICATION_PATH",str(pub)),patch("workspace_app.wsf_company_control_admission.PUBLICATION",blob),patch("workspace_app.wsf_company_control_admission.APPROVED_PLAN_SHA",sha(raw)):
            self.assertEqual(load_plan(c.base.root),plan)
            pub.write_bytes(b"changed")
            with self.assertRaises(ManualContextError):load_plan(c.base.root)
            pub.write_bytes(publication)
            atomic_replace(c.base.root/"config"/(PREFIX+"-approved.json"),b"{}")
            with self.assertRaises(ManualContextError):load_plan(c.base.root)
    def test_collector_compatible_paths_are_specific(self):
        from wsf_collector_repin_operator import compatible
        self.assertTrue(compatible(["reference/python/workspace_app/ac401-approved-publication.md",
                                    "reference/python/workspace_app/wsf_company_control_admission.py",
                                    "reference/python/wsf_company_control_successor_operator.py"]))
        for path in ("reference/python/workspace_app/wsf_collector_runtime.py",
                     "reference/python/workspace_app/wsf_manual_runtime.py",
                     "reference/python/workspace_app/wsf_crm_runtime.py",
                     "reference/python/p7_04_persistent_access.py",
                     "reference/python/workspace_app/requirements.lock"):
            self.assertFalse(compatible([path]),path)
