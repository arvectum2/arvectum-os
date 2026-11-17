from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from dataclasses import replace
from uuid import uuid4

from test_wsf_manual_context import access
from workspace_app.wsf_manual_context import ManualContextStore, ManualContextError, _identity
from workspace_app.wsf_manual_policy import ManualPolicyGate, OPERATIONS, POLICY_SCHEMA


class ManualPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.a = replace(access(), credential_id=uuid4().hex)
        self.store = ManualContextStore(self.root/"workspace-company-manual-context", self.a)
        self.store.restore_empty(self.a, self.store.export(self.a))
        self.policy = self.root/"config"/"manual-context-policy.json"
        self.policy.parent.mkdir(mode=0o700)
        now = datetime.now(timezone.utc)
        self.data = {"schema":POLICY_SCHEMA, "contract_draft_blob":"a"*40,
                     "scope":_identity(self.a),"credential_id":self.a.credential_id,
                     "starts_at":(now-timedelta(minutes=1)).isoformat(),
                     "expires_at":(now+timedelta(days=1)).isoformat(),
                     "grants":{op:uuid4().hex for op in OPERATIONS},
                     "purpose":"restricted-internal-project-coordination"}
        self.gate = self.pin()

    def pin(self):
        raw = json.dumps(self.data).encode()
        self.policy.write_bytes(raw)
        self.policy.chmod(0o600)
        return ManualPolicyGate(self.root, hashlib.sha256(raw).hexdigest(), "a"*40)

    def decision(self, *args, **kwargs):
        return SimpleNamespace(allowed=True, principal_kind="human", grant_id=self.data["grants"][kwargs["operation"]])

    def test_each_exact_operation_revalidates_distinct_grant(self):
        with patch("workspace_app.wsf_manual_policy.p704.authorize_from_credential_file", side_effect=self.decision) as auth:
            for op in OPERATIONS:
                self.assertEqual(self.gate.authorize(self.a,op).path,self.store.path)
                self.assertEqual(auth.call_args.kwargs["operation"],op)
                self.assertEqual(auth.call_args.kwargs["resource"],"manual-context")
            self.assertEqual(auth.call_count,5)
            with self.assertRaises(ManualContextError):
                self.gate.authorize(self.a,"workspace.open")

    def test_expiry_and_foreign_scope(self):
        self.data["expires_at"]=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
        gate=self.pin()
        with patch("workspace_app.wsf_manual_policy.p704.authorize_from_credential_file") as auth:
            for a in (self.a,replace(self.a,credential_id="b"*32)):
                with self.assertRaises(ManualContextError):
                    gate.authorize(a,"workspace.context.read")
            auth.assert_not_called()

    def test_unapproved_policy_tamper(self):
        self.data["purpose"]="changed"
        self.pin()
        with self.assertRaises(ManualContextError):
            self.gate.authorize(self.a,"workspace.context.read")

    def test_revoked_or_wrong_grant(self):
        for decision in (SimpleNamespace(allowed=False,principal_kind="human",grant_id=None),
                         SimpleNamespace(allowed=True,principal_kind="human",grant_id="wrong")):
            with patch("workspace_app.wsf_manual_policy.p704.authorize_from_credential_file",return_value=decision):
                with self.assertRaises(ManualContextError):
                    self.gate.authorize(self.a,"workspace.context.read")

    def test_missing_primary_never_recreated(self):
        self.store.path.unlink()
        with patch("workspace_app.wsf_manual_policy.p704.authorize_from_credential_file",side_effect=self.decision):
            with self.assertRaises(ManualContextError):
                self.gate.authorize(self.a,"workspace.context.read")
        self.assertFalse(self.store.path.exists())

    def test_missing_policy_denied(self):
        self.policy.unlink()
        with self.assertRaises(ManualContextError):
            self.gate.authorize(self.a,"workspace.context.read")
