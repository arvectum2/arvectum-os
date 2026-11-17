from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from test_wsf_manual_context import access
from workspace_app.wsf_crm import CRMStore
from workspace_app.wsf_crm_backup import crm_backup
from workspace_app.wsf_manual_context import ManualContextError
from workspace_app.wsf_manual_backup import BACKUP_NAME


class CRMBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.a=access();self.store=self.make("primary");self.store.initialize(self.a)
        self.volume=self.root/"volume";self.volume.mkdir(mode=0o700)
        self.dest=self.volume/"crm";self.dest.mkdir(mode=0o700)
        self.mounted=True
        def check(v,u):
            if not self.mounted:raise ManualContextError("volume missing")
        self.backup=crm_backup(self.store,volume=self.volume,uuid="fixture",parts=("crm",),verifier=check)

    def make(self,name):
        return CRMStore(self.root/name,self.a,project_ids=set(),evidence_refs=set())

    def party(self,name):
        return self.store.submit(self.a,uuid4().hex,"party",{"name":name,"registry_ref":None,"description":"Synthetic"})

    def test_latest_restore(self):
        self.party("Fixture");self.backup.copy_latest(self.a)
        self.party("Fixture two");self.backup.copy_latest(self.a)
        self.assertEqual(list(self.dest.iterdir()),[self.dest/BACKUP_NAME])
        r=self.make("restore");r.restore_empty(self.a,self.backup.verified_snapshot(self.a))
        self.assertEqual(r.export(self.a),self.store.export(self.a))

    def test_unavailable_and_corrupt_copy_preserved(self):
        self.party("Fixture");self.backup.copy_latest(self.a)
        old=(self.dest/BACKUP_NAME).read_bytes()
        self.party("Fixture two");self.mounted=False
        with self.assertRaises(ManualContextError):self.backup.copy_latest(self.a)
        self.assertEqual((self.dest/BACKUP_NAME).read_bytes(),old)
        self.mounted=True;(self.dest/BACKUP_NAME).write_bytes(b"corrupt")
        with self.assertRaises(ManualContextError):self.backup.copy_latest(self.a)
        self.assertEqual((self.dest/BACKUP_NAME).read_bytes(),b"corrupt")

    def test_scope_and_destination_separation(self):
        with self.assertRaises(ManualContextError):self.backup.copy_latest(access(actor="foreign"))
        with self.assertRaises(ValueError):crm_backup(self.store,parts=("Arvectum","backups","arvectum-os","manual-context"))
