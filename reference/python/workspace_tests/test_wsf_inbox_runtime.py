from datetime import datetime,timedelta,timezone
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import hashlib,json,tempfile,unittest
from test_wsf_manual_context import access
from workspace_app.wsf_manual_context import ManualContextError,_identity,_digest,_json
from workspace_app.wsf_roadmap_inbox import RoadmapInbox,registry_bindings
from workspace_app.wsf_inbox_runtime import RuntimeInboxPilot,OPERATIONS,SCHEMA,RECEIPT_SCHEMA

class InboxRuntimeTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name).resolve();(self.root/"config").mkdir(mode=0o700)
        self.a=replace(access(),credential_id=uuid4().hex)
        self.now=datetime.now(timezone.utc)
        self.bindings=registry_bindings();self.draft="a"*40
        self.primary=self.root/"workspace-company-roadmap-inbox"
        self.inbox=RoadmapInbox(self.primary,self.a,bindings=self.bindings)
        self.inbox.initialize(self.a)
        self.p={"schema":SCHEMA,"draft_blob":self.draft,"registry_sha256":_digest(_json(self.bindings)),
                "scope":_identity(self.a),"credential_id":self.a.credential_id,
                "starts_at":(self.now-timedelta(minutes=1)).isoformat(),"expires_at":(self.now+timedelta(days=1)).isoformat(),
                "grants":{v:uuid4().hex for v in OPERATIONS.values()},"purpose":"owner-triggered-roadmap-metadata"}
        self.pilot=RuntimeInboxPilot(self.root,approved_draft=self.draft)
        self.pilot.manual.review_signal=lambda a:{"due_at":(self.now+timedelta(days=2)).isoformat()}
        self.pin()
    def pin(self):
        raw=_json(self.p)
        p=self.root/"config"/"roadmap-inbox-policy.json";p.write_bytes(raw);p.chmod(0o600)
        p=self.root/"config"/"roadmap-inbox-activation.json"
        p.write_bytes(_json({"schema":RECEIPT_SCHEMA,"draft_blob":self.draft,"policy_sha256":hashlib.sha256(raw).hexdigest()}));p.chmod(0o600)
    def decision(self,*a,**kw):
        return SimpleNamespace(allowed=True,principal_kind="human",grant_id=self.p["grants"][kw["operation"]])
    def test_exact_independent_grants_and_inactive_default(self):
        with self.assertRaises(ManualContextError):RuntimeInboxPilot(self.root,approved_draft=None).authorize(self.a,"read")
        with patch("workspace_app.wsf_inbox_runtime.p704.authorize_from_credential_file",side_effect=self.decision) as auth:
            for op,exact in OPERATIONS.items():
                self.assertEqual(self.pilot.authorize(self.a,op).file.path,self.inbox.file.path)
                self.assertEqual(auth.call_args.kwargs["operation"],exact)
                self.assertEqual(auth.call_args.kwargs["resource"],"roadmap-inbox")
            with self.assertRaises(ManualContextError):self.pilot.authorize(self.a,"send")
    def test_no_reinit_and_revoked_grant(self):
        with patch("workspace_app.wsf_inbox_runtime.p704.authorize_from_credential_file",return_value=SimpleNamespace(allowed=False,principal_kind="human",grant_id=None)):
            with self.assertRaises(ManualContextError):self.pilot.authorize(self.a,"read")
        self.inbox.file.path.unlink()
        with patch("workspace_app.wsf_inbox_runtime.p704.authorize_from_credential_file",side_effect=self.decision):
            with self.assertRaises(ManualContextError):self.pilot.authorize(self.a,"read")
        self.assertFalse(self.inbox.file.path.exists())
    def test_registry_and_expiry_bindings(self):
        for k,v in (("registry_sha256","0"*64),("expires_at",(self.now+timedelta(days=3)).isoformat())):
            old=self.p[k];self.p[k]=v;self.pin()
            with patch("workspace_app.wsf_inbox_runtime.p704.authorize_from_credential_file") as auth:
                with self.assertRaises(ManualContextError):self.pilot.authorize(self.a,"poll")
                auth.assert_not_called()
            self.p[k]=old
        self.pin()
        (self.root/"config"/"roadmap-inbox-policy.json").write_text("{}")
        with self.assertRaises(ManualContextError):self.pilot.authorize(self.a,"read")
