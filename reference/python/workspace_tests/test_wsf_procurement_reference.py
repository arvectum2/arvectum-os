import json,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from arvectum_os_ref.identity import Identity
import p7_04_persistent_access as p704
from workspace_app.access import P704AccessResolver,provision_workspace_grant
from workspace_app.wsf_manual_context import ManualContextError,_identity,_json
from workspace_app.wsf_manual_backup import PilotBackup
from workspace_app.wsf_manual_runtime import RuntimeManualPilot,APPROVED_DRAFT as NOTES_DRAFT,APPROVAL_DECISION
from workspace_app.wsf_procurement_reference import RuntimeProcurementReference,DRAFT,OPERATION,RESOURCE,sha,validate_source
from wsf_manual_operator import activate as activate_notes,write_new

class ProcurementReferenceTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.base=Path(t.name).resolve();self.root=self.base/"runtime";self.root.mkdir(mode=0o700)
        (self.root/"config").mkdir(mode=0o700)
        vol=self.base/"volume";vol.mkdir(mode=0o700);(vol/"notes").mkdir(mode=0o700)
        org=Identity("organization","fixture-reference-org","platform")
        actor=Identity("principal","fixture-reference-owner","fixture-reference-org")
        p704.initialize_access_store(self.root,org);p704.register_principal(self.root,actor,kind="human")
        p704.issue_credential(self.root,actor);provision_workspace_grant(self.root)
        def backup(store):return PilotBackup(store,volume=vol,uuid="fixture",parts=("notes",),verifier=lambda v,u:None)
        with patch("wsf_manual_operator.prepare_destination"),patch("wsf_manual_operator.PilotBackup",side_effect=backup),patch("workspace_app.wsf_manual_runtime.PilotBackup",side_effect=backup):
            activate_notes(self.root,APPROVAL_DECISION,NOTES_DRAFT,True)
            self.resolve=P704AccessResolver(self.root).authorize
            self.a=self.resolve();self.notes=RuntimeManualPilot(self.root)
            self.project=self.notes.submit(self.a,uuid4().hex,"project",{"label":"Fixture","kind":"internal"})["id"]
        self.now=datetime.fromisoformat("2026-11-17T12:00:00+00:00")
        self.runtime=RuntimeProcurementReference(self.root,clock=lambda:self.now)
        self.token="a"*64
        self.grant=p704.grant_access(self.root,self.a.actor,operation=OPERATION,resource=RESOURCE,access_paths=("local",))
        self.policy={"schema":"arvectum.workspace.procurement-reference-policy/1","draft_blob":DRAFT,
                     "scope":_identity(self.a),"credential_id":self.a.credential_id,"grant_id":self.grant,
                     "purpose":"owner-triggered-internal-procurement-read",
                     "binding_id":"fixture-binding","source_release":"b"*40,"database_binding":"c"*64,
                     "deal_ids":["DL-fixture"],"project_id":self.project,
                     "starts_at":(self.now-timedelta(minutes=10)).isoformat(),"expires_at":(self.now+timedelta(hours=1)).isoformat(),
                     "source_credential_sha256":sha(self.token.encode())}
        self.result={"schema":"arvectum.tender.internal-procurement-reference/1","binding_id":self.policy["binding_id"],
                     "source_release":self.policy["source_release"],"database_binding":self.policy["database_binding"],
                     "observed_at":self.now.isoformat(),"coverage":"admitted-identity-set-only","canonical_authority":False,
                     "items":[{"deal_id":"DL-fixture","procurement_number":"0123456789012345678","workflow_status":"POST_SUBMISSION",
                               "updated_at":self.now.isoformat(),"recorded_decision":None,
                               "recommendation":{"ref":"SCR-fixture","source":"AGENT_SCREENING","value":"GO","at":self.now.isoformat()},
                               "submission":None,"outcome":None,"current_legal_status":"unknown"}]}
    def admit(self):
        raw=_json(self.policy)
        write_new(self.root/"config"/"procurement-reference-policy.json",raw)
        write_new(self.root/"secrets"/"procurement-reference.secret",self.token.encode())
        write_new(self.root/"config"/"procurement-reference-activation.json",
                  _json({"schema":"arvectum.workspace.procurement-reference-activation/1","draft_blob":DRAFT,"policy_sha256":sha(raw)}))
    def test_real_independent_permission_and_no_state_write(self):
        before=self.notes.authorize_operation(self.a,"export").export(self.a)
        with patch("workspace_app.wsf_procurement_reference.fetch_source",return_value=_json(self.result)) as fetch:
            with self.assertRaises(ManualContextError):self.runtime.read(self.resolve)
            fetch.assert_not_called();self.admit()
            d=self.runtime.read(self.resolve)
            fetch.assert_called_once_with(self.token)
            self.assertEqual(d["project_id"],self.project)
            self.assertEqual(d["items"][0]["recommendation"]["value"],"GO")
            self.assertIsNone(d["items"][0]["recorded_decision"])
            self.assertNotIn("database_binding",d)
            p704.revoke_grant(self.root,self.grant)
            with self.assertRaises(ManualContextError):self.runtime.read(self.resolve)
            self.assertEqual(fetch.call_count,1)
        self.assertEqual(self.notes.authorize_operation(self.a,"export").export(self.a),before)
    def test_revocation_during_fetch_denies_release(self):
        self.admit()
        def fetch(token):
            p704.revoke_grant(self.root,self.grant)
            return _json(self.result)
        with patch("workspace_app.wsf_procurement_reference.fetch_source",side_effect=fetch):
            with self.assertRaises(ManualContextError):self.runtime.read(self.resolve)
    def test_strict_shape_freshness_and_scope(self):
        for operation in ("foreign","missing","payload","stale","wrong-db","fake-approval","future"):
            r=json.loads(_json(self.result))
            if operation=="foreign":r["items"][0]["deal_id"]="DL-other"
            if operation=="missing":r["items"]=[]
            if operation=="payload":r["items"][0]["rationale"]="unadmitted"
            if operation=="stale":r["observed_at"]=(self.now-timedelta(hours=1)).isoformat()
            if operation=="wrong-db":r["database_binding"]="d"*64
            if operation=="fake-approval":
                r["items"][0]["recorded_decision"]={"ref":"DEC-fixture","code":"PORTFOLIO_BID_DECISION","value":"GO",
                    "actor_type":"HUMAN","actor_reference_present":True,"at":self.now.isoformat(),"owner_approval_verified":True}
            if operation=="future":r["items"][0]["updated_at"]=(self.now+timedelta(days=1)).isoformat()
            with self.assertRaises(ManualContextError):validate_source(_json(r),self.policy,self.now,self.now)
        self.assertEqual(len(validate_source(_json(self.result),self.policy,self.now,self.now)["items"]),1)
