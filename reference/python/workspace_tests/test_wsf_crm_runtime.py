from datetime import datetime,timedelta,timezone
from dataclasses import replace
import hashlib,json,tempfile,unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from types import SimpleNamespace

from test_wsf_manual_context import access
from workspace_app.wsf_crm import CRMStore
from workspace_app.wsf_crm_runtime import RuntimeCRMPilot, OPERATIONS, SCHEMA, RECEIPT_SCHEMA
from workspace_app.wsf_manual_context import ManualContextError,_identity


class RestrictedCRMRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();(self.root/"config").mkdir(mode=0o700)
        self.a=replace(access(),credential_id=uuid4().hex)
        self.p="PRJ-"+uuid4().hex;self.ref="NOTE-"+uuid4().hex
        self.draft="a"*40;self.now=datetime.now(timezone.utc)
        self.expiry=self.now+timedelta(days=1)
        self.store=CRMStore(self.root/"workspace-company-crm",self.a,project_ids={self.p},
                           evidence_refs={self.ref},allowed_entities={"party","opportunity"})
        self.store.initialize(self.a)
        self.policy={"schema":SCHEMA,"draft_blob":self.draft,"scope":_identity(self.a),
                     "credential_id":self.a.credential_id,"starts_at":(self.now-timedelta(minutes=1)).isoformat(),
                     "expires_at":self.expiry.isoformat(),"grants":{v:uuid4().hex for v in OPERATIONS.values()},
                     "purpose":"non-sensitive-organization-coordination"}
        self.pilot=RuntimeCRMPilot(self.root,approved_draft=self.draft)
        self.pin()
        self.pilot.manual.authorize_operation=lambda a,op:SimpleNamespace(read=lambda _:{"projects":[{"id":self.p,"label":"Fixture"}],"notes":[{"id":self.ref}]})
        self.pilot.manual.review_signal=lambda a:{"due_at":(self.now+timedelta(days=2)).isoformat()}
        self.payload={"name":"Fixture company","registry_ref":None,"description":"Synthetic"}

    def pin(self):
        raw=json.dumps(self.policy).encode()
        path=self.root/"config"/"crm-policy.json";path.write_bytes(raw);path.chmod(0o600)
        path=self.root/"config"/"crm-activation.json"
        path.write_text(json.dumps({"schema":RECEIPT_SCHEMA,"draft_blob":self.draft,"policy_sha256":hashlib.sha256(raw).hexdigest()}))
        path.chmod(0o600)

    def decision(self,*a,**kw):
        return SimpleNamespace(allowed=True,principal_kind="human",grant_id=self.policy["grants"][kw["operation"]])

    def test_default_no_admitted_contract(self):
        with self.assertRaises(ManualContextError):RuntimeCRMPilot(self.root).authorize(self.a,"read")

    def test_exact_grant_and_no_contact(self):
        with patch("workspace_app.wsf_crm_runtime.p704.authorize_from_credential_file",side_effect=self.decision) as auth:
            self.assertEqual(self.pilot.authorize(self.a,"party").path,self.store.path)
            self.assertEqual(auth.call_args.kwargs["operation"],"workspace.crm.party")
            self.assertEqual(self.pilot.catalog(self.a)["allowed_entities"],["party","opportunity"])
            with self.assertRaises(ManualContextError):self.pilot.authorize(self.a,"contact")
            with self.assertRaises(ManualContextError):self.pilot.submit(self.a,uuid4().hex,"contact",{})
            with self.assertRaises(ManualContextError):self.store.submit(self.a,uuid4().hex,"contact",{})

    def test_expiry_and_predecessor_bound(self):
        for expiry in (self.now-timedelta(seconds=1),self.now+timedelta(days=3)):
            self.policy["expires_at"]=expiry.isoformat();self.pin()
            with patch("workspace_app.wsf_crm_runtime.p704.authorize_from_credential_file",side_effect=self.decision) as auth:
                with self.assertRaises(ManualContextError):self.pilot.authorize(self.a,"read")
                auth.assert_not_called()

    def test_pin_and_revoked_grant(self):
        with patch("workspace_app.wsf_crm_runtime.p704.authorize_from_credential_file",return_value=SimpleNamespace(allowed=False,principal_kind="human",grant_id=None)):
            with self.assertRaises(ManualContextError):self.pilot.authorize(self.a,"read")
        (self.root/"config"/"crm-policy.json").write_text("{}")
        with self.assertRaises(ManualContextError):self.pilot.authorize(self.a,"read")

    def test_backup_failure_before_write_and_postwrite_warning(self):
        with patch("workspace_app.wsf_crm_runtime.p704.authorize_from_credential_file",side_effect=self.decision),patch("workspace_app.wsf_crm_runtime.crm_backup") as backup:
            backup.return_value.copy_latest.side_effect=ManualContextError("unavailable")
            with self.assertRaises(ManualContextError):self.pilot.submit(self.a,uuid4().hex,"party",self.payload)
            self.assertFalse(self.store.read(self.a)["party"])
            backup.return_value.copy_latest.side_effect=[{},ManualContextError("unavailable"),{},{}]
            key=uuid4().hex
            row=self.pilot.submit(self.a,key,"party",self.payload)
            self.assertEqual(row["backup_status"],"saved-primary-backup-unavailable")
            again=self.pilot.submit(self.a,key,"party",self.payload)
            self.assertEqual(again["id"],row["id"])
            self.assertEqual(again["backup_status"],"verified")
            self.assertEqual(len(self.store.read(self.a)["party"]),1)

    def test_no_missing_primary_recreation(self):
        self.store.path.unlink()
        with patch("workspace_app.wsf_crm_runtime.p704.authorize_from_credential_file",side_effect=self.decision):
            with self.assertRaises(ManualContextError):self.pilot.authorize(self.a,"read")
        self.assertFalse(self.store.path.exists())
