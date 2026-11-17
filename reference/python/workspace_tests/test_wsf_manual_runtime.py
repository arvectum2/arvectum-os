from pathlib import Path
import json
from unittest.mock import patch
import tempfile
import unittest
from uuid import uuid4

from test_wsf_manual_context import access
from workspace_app.wsf_manual_context import ManualContextError, ManualContextStore
from workspace_app.wsf_manual_runtime import RuntimeManualPilot, APPROVED_DRAFT, APPROVAL_DECISION, ACTIVATION_SCHEMA, ACTIVATION_FILE


class RuntimePilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        (self.root/"config").mkdir(mode=0o700)
        self.a=access()
        self.store=ManualContextStore(self.root/"synthetic",self.a)
        self.store.restore_empty(self.a,self.store.export(self.a))
        self.pilot=RuntimeManualPilot(self.root)
        self.payload={"title":"Fixture","text":"Synthetic","project_id":None}

    def test_disabled_without_explicit_activation(self):
        with self.assertRaises(ManualContextError):
            self.pilot.authorize_operation(self.a,"read")
        self.assertFalse((self.root/"workspace-company-manual-context").exists())

    def test_exact_receipt_and_operation_mapping_each_time(self):
        p=self.root/"config"/ACTIVATION_FILE
        p.write_text(json.dumps({"schema":ACTIVATION_SCHEMA,"draft_blob":APPROVED_DRAFT,
                                  "decision":APPROVAL_DECISION,"policy_sha256":"a"*64}))
        p.chmod(0o600)
        with patch("workspace_app.wsf_manual_runtime.ManualPolicyGate") as gate:
            gate.return_value.authorize.return_value=self.store
            self.assertIs(self.pilot.authorize_operation(self.a,"capture"),self.store)
            gate.assert_called_once_with(self.root,"a"*64,APPROVED_DRAFT)
            gate.return_value.authorize.assert_called_once_with(self.a,"workspace.context.capture")
            p.unlink()
            with self.assertRaises(ManualContextError):
                self.pilot.authorize_operation(self.a,"read")

    def test_prewrite_backup_failure_does_not_mutate(self):
        with patch.object(self.pilot,"authorize_operation",return_value=self.store), patch("workspace_app.wsf_manual_runtime.PilotBackup") as backup:
            backup.return_value.copy_latest.side_effect=ManualContextError("unavailable")
            with self.assertRaises(ManualContextError):
                self.pilot.submit(self.a,uuid4().hex,"capture",self.payload)
        self.assertEqual(self.store.read(self.a)["notes"],[])

    def test_postwrite_failure_is_reported_and_retry_is_idempotent(self):
        key=uuid4().hex
        with patch.object(self.pilot,"authorize_operation",return_value=self.store), patch("workspace_app.wsf_manual_runtime.PilotBackup") as backup:
            backup.return_value.copy_latest.side_effect=[{},ManualContextError("unavailable"),{},{}]
            n=self.pilot.submit(self.a,key,"capture",self.payload)
            self.assertEqual(n["backup_status"],"saved-primary-backup-unavailable")
            retry=self.pilot.submit(self.a,key,"capture",self.payload)
            self.assertEqual(retry["id"],n["id"])
            self.assertEqual(retry["backup_status"],"verified")
        self.assertEqual(len(self.store.read(self.a)["notes"]),1)

    def test_read_backup_staleness(self):
        with patch.object(self.pilot,"authorize_operation",return_value=self.store), patch("workspace_app.wsf_manual_runtime.PilotBackup") as backup:
            backup.return_value.verified_snapshot.return_value=self.store.export(self.a)
            self.assertEqual(self.pilot.read(self.a)["backup_status"],"verified")
            self.store.submit(self.a,uuid4().hex,"capture",self.payload)
            self.assertEqual(self.pilot.read(self.a)["backup_status"],"stale")
            backup.return_value.verified_snapshot.side_effect=OSError("unavailable")
            self.assertEqual(self.pilot.read(self.a)["backup_status"],"unavailable")
