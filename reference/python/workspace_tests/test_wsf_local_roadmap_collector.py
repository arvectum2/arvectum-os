from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4
from test_wsf_manual_context import access
from workspace_app.wsf_manual_context import ManualContextError, _identity, _digest
from workspace_app.wsf_roadmap_inbox import RoadmapInbox
from workspace_app.wsf_manual_backup import PilotBackup
from workspace_app.company_portfolio_verified import VerifiedRuntimeCompanyPortfolioProvider
from workspace_app.wsf_local_roadmap_collector import (
    ACTIVE,EXCLUDED,EXPIRY,REGISTRY,ServicePolicy,CollectorInbox,exact_registry,
    rehearse_migration,collect_cycle,
)

class CollectorTests(TestCase):
    def setUp(self):
        tmp=TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name).resolve()
        self.h=access()
        self.s=replace(access(actor="collector",kind="service"),credential_id="1"*32,grant_id="2"*32)
        self.now=datetime(2026,11,18,15,10,tzinfo=timezone.utc)
        self.clock=patch("workspace_app.wsf_local_roadmap_collector._utc",side_effect=lambda:self.now)
        self.clock.start();self.addCleanup(self.clock.stop)
        self.policy=ServicePolicy(tuple(tuple(x) for x in _identity(self.h)),self.s.organization,
            self.s.actor,self.s.credential_id,self.s.grant_id,"a"*40,self.now-timedelta(days=1),EXPIRY)
        self.bindings=exact_registry()
        self.legacy=RoadmapInbox(self.root/"legacy",self.h,bindings=self.bindings)
        self.legacy.initialize(self.h)
        self.legacy.scan(self.h,uuid4().hex,self.projection(self.now-timedelta(hours=1),"1","a"),(self.now-timedelta(hours=1)).isoformat())
        self.inbox,self.old,self.new=rehearse_migration(self.legacy,self.h,self.legacy.export(self.h),self.root/"candidate")
        self.volume=self.root/"volume";self.volume.mkdir(mode=0o700)
        (self.volume/"inbox").mkdir(mode=0o700)
        self.hbackup=self.backup(self.inbox.file);self.hbackup.copy_latest(self.h)
        self.provider=VerifiedRuntimeCompanyPortfolioProvider(REGISTRY)

    def projection(self,at,commit="2",digest="a",failed=None):
        projects=[]
        for pid,b in self.bindings.items():
            state="current-source-backed" if pid in ACTIVE else "reconciliation-required"
            if pid==failed:state="unavailable"
            source={"repository":b["repository"],"path":b["path"],"adapter":b["adapter"],
                 "freshness":"fresh-fetch","commit_sha":commit*40,"content_sha256":digest*64,
                 "fetched_at":at.isoformat()} if state=="current-source-backed" else None
            projects.append({"id":pid,"repository":b["repository"],"roadmap_path":b["path"],
                             "state":state,"source":source,"roadmap":{"raw":"NOT STORED"}})
        return {"schema":"arvectum.workspace.company-portfolio/1","projection":{"read_only":True,"canonical_authority":False},
                "scope":{"organization_resolved_server_side":True,"actor_resolved_server_side":True,"cross_organization_aggregation":False},
                "projects":projects}

    def backup(self,f):
        return PilotBackup(f,volume=self.volume,uuid="fixture",parts=("inbox",),verifier=lambda v,u:None)
    def run_cycle(self,projection=None,resolve=None,backup_factory=None):
        with patch.object(self.provider,"project",return_value=projection or self.projection(self.now)) as pull:
            d=collect_cycle(self.inbox,self.policy,self.provider,resolve or (lambda:self.s),backup_factory=backup_factory or self.backup)
            return d,pull.call_count
    def state(self):
        return self.inbox.read(self.h,self.now.isoformat())

    def test_exact_active_registry_and_legacy_preservation(self):
        self.assertEqual(len(ACTIVE),8);self.assertEqual(len(EXCLUDED),2)
        self.assertEqual(self.legacy.export(self.h),self.old)
        self.assertEqual(self.inbox.file._decode(self.new),self.legacy.file._decode(self.old))
        self.assertEqual(len(self.state()["sources"]),8)
        self.assertEqual(len(self.state()["excluded_sources"]),2)
        self.assertNotIn(b"NOT STORED",self.new)

    def test_cycle_attributed_and_repeated_window_no_fetch(self):
        d,n=self.run_cycle();self.assertEqual((d["current"],d["backup_status"],n),(8,"verified",1))
        raw=self.inbox.export(self.h);event=self.inbox.file._decode(raw)[-1]
        self.assertEqual(event["operation"],"service-scan")
        self.assertEqual(event["data"]["executor"]["kind"],"service")
        self.assertEqual(event["data"]["executor"]["credential_id"],self.s.credential_id)
        self.assertEqual(self.run_cycle()[1],0)
        self.assertEqual(self.inbox.export(self.h),raw)

    def test_changed_digest_and_human_review(self):
        self.run_cycle(self.projection(self.now,digest="b"))
        self.assertEqual(self.state()["pending_count"],8)
        i=self.state()["items"][0]
        self.inbox.review(self.h,uuid4().hex,i["id"],1,"reviewed",(self.now+timedelta(seconds=1)).isoformat())
        self.assertEqual(self.state()["pending_count"],7)

    def test_unavailable_keeps_checkpoint(self):
        self.run_cycle(self.projection(self.now,failed="OS"))
        row=next(r for r in self.state()["sources"] if r["source_id"]=="OS")
        self.assertEqual(row["checkpoint"]["commit_sha"],"1"*40)
        self.assertEqual(row["state"],"unavailable")

    def test_service_cannot_use_human_apis(self):
        for fn in (self.inbox.read,self.inbox.export,self.inbox.capacity):
            with self.assertRaises(ManualContextError):fn(self.s)
        with self.assertRaises(ManualContextError):
            self.inbox.review(self.s,uuid4().hex,"INBOX-"+"1"*32,1,"reviewed",self.now.isoformat())
        with self.assertRaises(ManualContextError):
            self.inbox.scan(self.s,uuid4().hex,self.projection(self.now),self.now.isoformat())

    def test_wrong_identity_and_expiry_deny(self):
        for s in (self.h,replace(self.s,organization=access(org="other").organization),
                  replace(self.s,grant_id="3"*32),replace(self.s,actor=access(actor="other").actor)):
            with self.assertRaises(ManualContextError):self.run_cycle(resolve=lambda:s)
        self.now=EXPIRY
        with self.assertRaises(ManualContextError):self.run_cycle()
        self.assertEqual(self.inbox.export(self.h),self.new)

    def test_revoked_during_fetch_no_commit(self):
        enabled=True
        def resolve():
            if not enabled:raise ManualContextError("revoked")
            return self.s
        def fetch(*a,**kw):
            nonlocal enabled
            enabled=False
            return self.projection(self.now)
        with patch.object(self.provider,"project",side_effect=fetch):
            with self.assertRaises(ManualContextError):
                collect_cycle(self.inbox,self.policy,self.provider,resolve,backup_factory=self.backup)
        self.assertEqual(self.inbox.export(self.h),self.new)

    def test_registry_drift_and_overlap(self):
        with self.inbox.file.cycle_lock():
            with self.assertRaises(ManualContextError):self.run_cycle()
        self.provider._descriptors=self.provider._descriptors[:-1]
        with self.assertRaises(ManualContextError):self.run_cycle()
        self.assertEqual(self.inbox.export(self.h),self.new)

    def test_backup_failure_blocks_next_cycle(self):
        def bad(f):
            b=self.backup(f);original=b.copy_latest;count=0
            def copy(a):
                nonlocal count
                count+=1
                if count==2:raise ManualContextError("backup unavailable")
                return original(a)
            b.copy_latest=copy
            return b
        d,_=self.run_cycle(backup_factory=bad)
        self.assertEqual(d["backup_status"],"saved-primary-backup-unavailable")
        self.now+=timedelta(hours=3)
        with self.assertRaises(ManualContextError):self.run_cycle()
        self.hbackup.copy_latest(self.h)
        self.assertEqual(self.run_cycle()[0]["backup_status"],"verified")

    def test_restore_and_original_bytes(self):
        self.run_cycle()
        restored=CollectorInbox(self.root/"restore",_identity(self.h),_digest(self.old),len(self.legacy.file._decode(self.old)),create=True)
        restored.restore_empty(self.h,self.hbackup.verified_snapshot(self.h))
        self.assertEqual(restored.export(self.h),self.inbox.export(self.h))
        self.assertEqual(self.legacy.export(self.h),self.old)
        with self.assertRaises(ManualContextError):
            rehearse_migration(self.legacy,self.h,b"bad",self.root/"bad")

    def test_legacy_prefix_cannot_be_rewritten(self):
        events=self.inbox.file._decode(self.new)
        events[0]["key"]="9"*32
        with self.assertRaises(ManualContextError):
            self.inbox.file._decode(self.inbox.file._encode(events))

    def test_reader_fetches_only_eight_exact_paths(self):
        from base64 import b64encode
        from urllib.parse import quote
        from workspace_app.company_portfolio_verified import ContentHashingGitHubRoadmapReader
        reader=ContentHashingGitHubRoadmapReader(token="")
        provider=VerifiedRuntimeCompanyPortfolioProvider(REGISTRY,reader=reader)
        urls=[]
        def response(url):
            urls.append(url)
            if url.endswith("/commits/main"):return {"sha":"2"*40}
            return {"encoding":"base64","content":b64encode(b"# Synthetic roadmap\n").decode()}
        with patch.object(reader,"_json",side_effect=response),patch("workspace_app.company_portfolio._utc_now",return_value=self.now.isoformat()):
            r=collect_cycle(self.inbox,self.policy,provider,lambda:self.s,backup_factory=self.backup)
        self.assertEqual(r["current"],8)
        expected=set()
        for pid in ACTIVE:
            b=self.bindings[pid];base="https://api.github.com/repos/"+b["repository"]
            expected.add(base+"/commits/main")
            expected.add(base+"/contents/"+quote(b["path"],safe="/")+"?ref="+"2"*40)
        self.assertEqual(set(urls),expected)
        self.assertEqual(len(urls),16)
        self.assertNotIn(b"Synthetic roadmap",self.inbox.export(self.h))

    def test_real_p704_grant_resolution_and_revocation(self):
        from arvectum_os_ref.identity import Identity
        import p7_04_persistent_access as p704
        root=self.root/"fixture-runtime"
        org=Identity("organization","fixture-org","platform")
        owner=Identity("principal","fixture-owner",org.value)
        svc=Identity("principal","fixture-collector",org.value)
        p704.initialize_access_store(root,org)
        p704.register_principal(root,owner,kind="human")
        p704.register_principal(root,svc,kind="service")
        cid=p704.issue_credential(root,svc)["credential_id"]
        gid=p704.grant_access(root,svc,operation="workspace.inbox.collect",resource="roadmap-inbox",access_paths=("local",))
        release="a"*40
        target=root/"releases"/release;target.mkdir(parents=True)
        (root/"current").symlink_to(target)
        scope=tuple(tuple((i.namespace,i.value,i.scope)) for i in (org,owner))
        policy=ServicePolicy(scope,org,svc,cid,gid,release,self.now-timedelta(days=1),EXPIRY)
        self.assertEqual(policy.resolve(root,self.now).principal_kind,"service")
        for op in ("workspace.inbox.review","workspace.inbox.export","workspace.open"):
            decision=p704.authorize_from_credential_file(root,organization=org,principal=svc,credential_id=cid,
                 credential_file=root/"secrets"/"p7-04"/(cid+".secret"),operation=op,resource="roadmap-inbox",access_path="local")
            self.assertFalse(decision.allowed)
        p704.revoke_credential(root,cid)
        with self.assertRaises(ManualContextError):policy.resolve(root,self.now)

    def test_migration_preserves_reviewed_history_and_pending_ids(self):
        t=self.now-timedelta(minutes=20)
        self.legacy.scan(self.h,uuid4().hex,self.projection(t,"2","b"),t.isoformat())
        items=self.legacy.read(self.h,t.isoformat())["items"]
        self.legacy.review(self.h,uuid4().hex,items[0]["id"],1,"reviewed",(t+timedelta(seconds=1)).isoformat())
        raw=self.legacy.export(self.h)
        migrated,original,candidate=rehearse_migration(self.legacy,self.h,raw,self.root/"review-migration")
        old=self.legacy.read(self.h,self.now.isoformat())
        new=migrated.read(self.h,self.now.isoformat())
        self.assertEqual(new["items"],old["items"])
        self.assertEqual(new["pending_count"],old["pending_count"])
        self.assertEqual(original,raw)
        self.assertEqual(self.legacy.export(self.h),raw)

    def test_missing_prebackup_no_commit_or_fetch(self):
        (self.volume/"inbox"/"latest.private.json").unlink()
        with patch.object(self.provider,"project") as fetch:
            with self.assertRaises(OSError):
                collect_cycle(self.inbox,self.policy,self.provider,lambda:self.s,backup_factory=self.backup)
            fetch.assert_not_called()
        self.assertEqual(self.inbox.export(self.h),self.new)
