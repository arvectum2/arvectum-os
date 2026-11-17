"""Actual P7.04 activation in a temporary runtime; no network or production data."""
import json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from arvectum_os_ref.identity import Identity
import p7_04_persistent_access as p704
from workspace_app.access import P704AccessResolver,provision_workspace_grant
from workspace_app.wsf_manual_backup import PilotBackup
from workspace_app.wsf_manual_runtime import RuntimeManualPilot,APPROVED_DRAFT as NOTES_DRAFT,APPROVAL_DECISION
from workspace_app.wsf_manual_context import ManualContextError
from workspace_app.wsf_inbox_runtime import RuntimeInboxPilot,APPROVED_DRAFT,OPERATIONS
from workspace_app.wsf_roadmap_inbox import registry_bindings
from workspace_app.company_portfolio_verified import VerifiedRuntimeCompanyPortfolioProvider
from wsf_manual_operator import activate as activate_notes
from wsf_inbox_operator import activate,DECISION

class InboxOperatorTests(unittest.TestCase):
    def test_actual_grants_activation_scan_and_revoke(self):
        with tempfile.TemporaryDirectory(prefix="wsf07-operator-fixture-") as tmp:
            base=Path(tmp).resolve()
            root=base/"runtime";root.mkdir(mode=0o700);(root/"config").mkdir(mode=0o700)
            volume=base/"volume";volume.mkdir(mode=0o700)
            for name in ("notes","inbox"):(volume/name).mkdir(mode=0o700)
            org=Identity("organization","fixture-inbox-org","platform")
            actor=Identity("principal","fixture-inbox-owner","fixture-inbox-org")
            p704.initialize_access_store(root,org);p704.register_principal(root,actor,kind="human")
            p704.issue_credential(root,actor);provision_workspace_grant(root)
            def nb(store):return PilotBackup(store,volume=volume,uuid="fixture",parts=("notes",),verifier=lambda v,u:None)
            def ib(store,**kw):return PilotBackup(store,volume=volume,uuid="fixture",parts=("inbox",),verifier=lambda v,u:None)
            def snapshot(change=False):
                rows=[]
                for pid,b in registry_bindings().items():
                    ready=b["path"] is not None
                    row={"id":pid,"repository":b["repository"],"roadmap_path":b["path"],"state":"current-source-backed" if ready else "reconciliation-required","source":None}
                    if ready:row["source"]={"repository":b["repository"],"path":b["path"],"adapter":b["adapter"],"freshness":"fresh-fetch",
                        "commit_sha":("2" if change else "1")*40,"content_sha256":("b" if change and pid=="COMPANY" else "a")*64,"fetched_at":datetime.now(timezone.utc).isoformat()}
                    rows.append(row)
                return {"schema":"arvectum.workspace.company-portfolio/1","projection":{"read_only":True,"canonical_authority":False},
                        "scope":{"organization_resolved_server_side":True,"actor_resolved_server_side":True,"cross_organization_aggregation":False},"projects":rows}
            with patch("wsf_manual_operator.prepare_destination"),patch("wsf_manual_operator.PilotBackup",side_effect=nb),patch("workspace_app.wsf_manual_runtime.PilotBackup",side_effect=nb),patch("wsf_inbox_operator.prepare_destination"),patch("wsf_inbox_operator.PilotBackup",side_effect=ib),patch("workspace_app.wsf_inbox_runtime.PilotBackup",side_effect=ib):
                activate_notes(root,APPROVAL_DECISION,NOTES_DRAFT,True)
                resolve=P704AccessResolver(root).authorize;a=resolve()
                notes=RuntimeManualPilot(root)
                p=notes.submit(a,uuid4().hex,"project",{"label":"Synthetic project","kind":"internal"})
                notes.submit(a,uuid4().hex,"capture",{"title":"Fixture","text":"Synthetic only","project_id":p["id"]})
                before=notes.read(a)
                pilot=RuntimeInboxPilot(root)
                with self.assertRaises(ManualContextError):pilot.authorize(a,"read")
                outcome=activate(root,APPROVED_DRAFT,DECISION,True)
                self.assertEqual(outcome["operation_grants"],4)
                self.assertEqual(outcome["expires_at"],notes.review_signal(a)["due_at"])
                self.assertEqual(pilot.read(a)["coverage"],"unknown")
                k={"key":uuid4().hex}
                with patch.object(VerifiedRuntimeCompanyPortfolioProvider,"project",side_effect=[snapshot(),snapshot(True)]) as fetch:
                    self.assertEqual(pilot.mutate(resolve,"poll",k)["backup_status"],"verified")
                    self.assertEqual(pilot.mutate(resolve,"poll",k)["backup_status"],"verified")
                    self.assertEqual(fetch.call_count,1)
                    self.assertEqual(pilot.mutate(resolve,"poll",{"key":uuid4().hex})["backup_status"],"verified")
                    self.assertEqual(fetch.call_count,2)
                d=pilot.read(a);self.assertEqual(d["pending_count"],1)
                row=d["items"][0]
                self.assertEqual(pilot.mutate(resolve,"review",{"key":uuid4().hex,"item_id":row["id"],"expected_revision":1,"state":"reviewed"})["backup_status"],"verified")
                self.assertEqual(pilot.read(a)["pending_count"],0)
                self.assertEqual(pilot.read(a)["backup_status"],"verified")
                self.assertEqual(notes.read(a),before)
                with self.assertRaises(ManualContextError):activate(root,APPROVED_DRAFT,DECISION,True)
                policy=json.loads((root/"config"/"roadmap-inbox-policy.json").read_text())
                p704.revoke_grant(root,policy["grants"][OPERATIONS["poll"]])
                with self.assertRaises(ManualContextError):pilot.mutate(resolve,"poll",{"key":uuid4().hex})
                self.assertEqual(pilot.read(a)["pending_count"],0)
