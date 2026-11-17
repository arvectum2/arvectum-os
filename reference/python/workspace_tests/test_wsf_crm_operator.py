"""Exercise the actual P7.04 backend solely in an isolated temporary runtime."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from arvectum_os_ref.identity import Identity
import p7_04_persistent_access as p704
from workspace_app.access import P704AccessResolver, provision_workspace_grant
from workspace_app.wsf_manual_backup import PilotBackup
from workspace_app.wsf_manual_runtime import RuntimeManualPilot, APPROVED_DRAFT as NOTES_DRAFT, APPROVAL_DECISION
from workspace_app.wsf_manual_context import ManualContextError
from workspace_app.wsf_crm_backup import crm_backup
from workspace_app.wsf_crm_runtime import RuntimeCRMPilot, APPROVED_DRAFT, OPERATIONS
from wsf_manual_operator import activate as activate_notes
from wsf_crm_operator import activate, DECISION


class CRMOperatorTests(unittest.TestCase):
    def test_actual_scoped_grants_activation_and_backup(self):
        with tempfile.TemporaryDirectory(prefix="wsf-integrated-fixture-") as tmp:
            base=Path(tmp).resolve()
            root=base/"runtime";root.mkdir(mode=0o700);(root/"config").mkdir(mode=0o700)
            volume=base/"fixture-volume";volume.mkdir(mode=0o700)
            for name in ("notes","crm"):(volume/name).mkdir(mode=0o700)
            org=Identity("organization","fixture-crm-org","platform")
            actor=Identity("principal","fixture-crm-owner","fixture-crm-org")
            p704.initialize_access_store(root,org)
            p704.register_principal(root,actor,kind="human")
            p704.issue_credential(root,actor)
            provision_workspace_grant(root)
            def nb(store):return PilotBackup(store,volume=volume,uuid="fixture",parts=("notes",),verifier=lambda v,u:None)
            def cb(store):return crm_backup(store,volume=volume,uuid="fixture",parts=("crm",),verifier=lambda v,u:None)
            with patch("wsf_manual_operator.prepare_destination"),patch("wsf_manual_operator.PilotBackup",side_effect=nb),patch("workspace_app.wsf_manual_runtime.PilotBackup",side_effect=nb),patch("wsf_crm_operator.prepare_destination"),patch("wsf_crm_operator.crm_backup",side_effect=cb),patch("workspace_app.wsf_crm_runtime.crm_backup",side_effect=cb):
                activate_notes(root,APPROVAL_DECISION,NOTES_DRAFT,True)
                a=P704AccessResolver(root).authorize()
                p=RuntimeManualPilot(root).submit(a,uuid4().hex,"project",{"label":"Synthetic project","kind":"customer"})
                n=RuntimeManualPilot(root).submit(a,uuid4().hex,"capture",{"title":"Fixture","text":"Synthetic only","project_id":p["id"]})
                with self.assertRaises(ManualContextError):RuntimeCRMPilot(root).authorize(a,"read")
                outcome=activate(root,APPROVED_DRAFT,DECISION,True)
                self.assertEqual(outcome["operation_grants"],4)
                self.assertEqual(outcome["expires_at"],RuntimeManualPilot(root).review_signal(a)["due_at"])
                pilot=RuntimeCRMPilot(root)
                party=pilot.submit(a,uuid4().hex,"party",{"name":"Synthetic organization","description":"Fixture","registry_ref":None})
                opp=pilot.submit(a,uuid4().hex,"opportunity",{"party_id":party["id"],"contact_id":None,
                   "title":"Synthetic opportunity","stage":"discovery","next_action":"Review",
                   "next_contact_at":None,"project_id":p["id"],"evidence_refs":[n["id"]],"outcome_ref":None})
                self.assertEqual(opp["backup_status"],"verified")
                self.assertEqual(len(pilot.read(a)["opportunity"]),1)
                self.assertEqual(pilot.read(a)["backup_status"],"verified")
                self.assertEqual(len(RuntimeManualPilot(root).read(a)["notes"]),1)
                self.assertEqual(pilot.catalog(a)["projects"],[{"id":p["id"],"label":"Synthetic project"}])
                with self.assertRaises(ManualContextError):pilot.submit(a,uuid4().hex,"contact",{})
                with self.assertRaises(ManualContextError):activate(root,APPROVED_DRAFT,DECISION,True)
                import json
                policy=json.loads((root/"config"/"crm-policy.json").read_text())
                p704.revoke_grant(root,policy["grants"][OPERATIONS["party"]])
                with self.assertRaises(ManualContextError):
                    pilot.submit(a,uuid4().hex,"party",{"name":"Denied","description":"Fixture","registry_ref":None})
                self.assertEqual(len(pilot.read(a)["party"]),1)
