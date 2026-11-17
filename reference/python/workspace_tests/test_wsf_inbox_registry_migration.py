from datetime import datetime,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import json,unittest
from unittest.mock import patch
from arvectum_os_ref.identity import Identity
import p7_04_persistent_access as p704
from workspace_app.access import P704AccessResolver,provision_workspace_grant
from workspace_app.wsf_manual_backup import PilotBackup
from workspace_app.wsf_manual_runtime import RuntimeManualPilot,APPROVED_DRAFT as NOTES_DRAFT,APPROVAL_DECISION
from workspace_app.wsf_manual_context import ManualContextError
from workspace_app.wsf_inbox_runtime import RuntimeInboxPilot,APPROVED_DRAFT,SUCCESSOR_DRAFT,SUCCESSOR_PATH
from workspace_app.wsf_inbox_registry_migration import cutover,atomic
from workspace_app.wsf_roadmap_inbox import registry_bindings
from workspace_app.company_portfolio_verified import VerifiedRuntimeCompanyPortfolioProvider
from wsf_manual_operator import activate as activate_notes
from wsf_inbox_operator import activate,DECISION

class RegistryMigrationTests(unittest.TestCase):
    def setUp(self):
        t=TemporaryDirectory();self.addCleanup(t.cleanup);base=Path(t.name).resolve()
        self.root=base/"runtime";self.root.mkdir(mode=0o700);(self.root/"config").mkdir(mode=0o700)
        self.volume=base/"volume";self.volume.mkdir(mode=0o700)
        for n in ("notes","inbox"):(self.volume/n).mkdir(mode=0o700)
        org=Identity("organization","fixture-migrate-org","platform")
        actor=Identity("principal","fixture-migrate-owner","fixture-migrate-org")
        p704.initialize_access_store(self.root,org);p704.register_principal(self.root,actor,kind="human")
        p704.issue_credential(self.root,actor);provision_workspace_grant(self.root)
        def nb(s):return PilotBackup(s,volume=self.volume,uuid="fixture",parts=("notes",),verifier=lambda v,u:None)
        def ib(s,**kw):return PilotBackup(s,volume=self.volume,uuid="fixture",parts=("inbox",),verifier=lambda v,u:None)
        self.ib=ib
        for target,kw in (("wsf_manual_operator.prepare_destination",{}),("wsf_inbox_operator.prepare_destination",{}),
            ("wsf_manual_operator.PilotBackup",{"side_effect":nb}),("workspace_app.wsf_manual_runtime.PilotBackup",{"side_effect":nb}),
            ("wsf_inbox_operator.PilotBackup",{"side_effect":ib}),("workspace_app.wsf_inbox_runtime.PilotBackup",{"side_effect":ib})):
            p=patch(target,**kw);p.start();self.addCleanup(p.stop)
        activate_notes(self.root,APPROVAL_DECISION,NOTES_DRAFT,True)
        self.resolve=P704AccessResolver(self.root).authorize;self.a=self.resolve()
        activate(self.root,APPROVED_DRAFT,DECISION,True)
        self.pilot=RuntimeInboxPilot(self.root)
        with patch.object(VerifiedRuntimeCompanyPortfolioProvider,"project",return_value=self.snapshot()):
            self.pilot.mutate(self.resolve,"poll",{"key":uuid4().hex})
        self.archive=self.volume/"inbox"/"rollback"
        self.pred=self.pilot.authorize(self.a,"export").export(self.a)
        self.policy_path=self.root/"config"/"roadmap-inbox-policy.json"
        self.policy=self.policy_path.read_bytes()
    def snapshot(self,successor=False):
        rows=[]
        for pid,b in registry_bindings(SUCCESSOR_PATH if successor else None).items():
            ready=b["path"] is not None
            r={"id":pid,"repository":b["repository"],"roadmap_path":b["path"],"state":"current-source-backed" if ready else "reconciliation-required","source":None}
            if ready:r["source"]={"repository":b["repository"],"path":b["path"],"adapter":b["adapter"],
                "freshness":"fresh-fetch","commit_sha":"1"*40,"content_sha256":"a"*64,"fetched_at":datetime.now(timezone.utc).isoformat()}
            rows.append(r)
        return {"schema":"arvectum.workspace.company-portfolio/1","projection":{"read_only":True,"canonical_authority":False},
            "scope":{"organization_resolved_server_side":True,"actor_resolved_server_side":True,"cross_organization_aggregation":False},"projects":rows}
    def migrate(self,**kw):
        return cutover(self.root,self.a,self.archive,assert_quiescent=lambda:None,confirm=True,backup_factory=self.ib,**kw)
    def test_success_and_new_baseline(self):
        before=self.pilot.read(self.a);r=self.migrate()
        self.assertTrue(r["history_preserved"])
        self.assertEqual(r["changed"],["PORT-007"])
        self.assertEqual((self.archive/"inbox.json").read_bytes(),self.pred)
        self.assertEqual((self.archive/"policy.json").read_bytes(),self.policy)
        after=self.pilot.read(self.a)
        self.assertEqual(before,after)
        old,new=map(json.loads,(self.policy,self.policy_path.read_bytes()))
        self.assertEqual(new["draft_blob"],SUCCESSOR_DRAFT)
        self.assertEqual(new["grants"],old["grants"]);self.assertEqual(new["expires_at"],old["expires_at"])
        with patch.object(VerifiedRuntimeCompanyPortfolioProvider,"project",return_value=self.snapshot(True)):
            self.pilot.mutate(self.resolve,"poll",{"key":uuid4().hex})
        d=self.pilot.read(self.a)
        self.assertEqual(sum(x["state"]=="current-source-backed" for x in d["sources"]),8)
        self.assertEqual(d["pending_count"],0)
        self.assertEqual(d["backup_status"],"verified")
    def test_rollback_after_partial_write(self):
        def inject(path,raw):
            if path==self.policy_path:raise OSError("fixture injection")
            atomic(path,raw)
        with self.assertRaises(OSError):self.migrate(write=inject)
        self.assertEqual(self.pilot.authorize(self.a,"export").export(self.a),self.pred)
        self.assertEqual(self.policy_path.read_bytes(),self.policy)
        self.assertEqual(self.pilot.read(self.a)["backup_status"],"verified")
        self.assertEqual((self.archive/"backup.json").read_bytes(),self.pred)
    def test_no_implicit_approval_or_quiescence(self):
        with self.assertRaises(ManualContextError):
            cutover(self.root,self.a,self.archive,assert_quiescent=lambda:None,confirm=False,backup_factory=self.ib)
        def refuse():raise ManualContextError("not stopped")
        with self.assertRaises(ManualContextError):
            cutover(self.root,self.a,self.archive,assert_quiescent=refuse,confirm=True,backup_factory=self.ib)
        self.assertFalse(self.archive.exists())
        self.assertEqual(self.pilot.authorize(self.a,"export").export(self.a),self.pred)
