from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4
from base64 import b64encode
import plistlib
import p7_04_persistent_access as p704
from arvectum_os_ref.identity import Identity
from workspace_app.access import AccessContext
from workspace_app.wsf_manual_context import ManualContextError,_identity,_digest,_json
from workspace_app.wsf_roadmap_inbox import RoadmapInbox
from workspace_app.wsf_manual_backup import PilotBackup
from workspace_app.wsf_inbox_runtime import RuntimeInboxPilot,OPERATIONS,SCHEMA,RECEIPT_SCHEMA,SUCCESSOR_DRAFT
from workspace_app.wsf_local_roadmap_collector import ACTIVE,EXPIRY,REGISTRY_SHA,REGISTRY,exact_registry
from workspace_app.wsf_collector_runtime import DRAFT_BLOB,CONFIG,JOURNAL,service_inbox,load_config
from workspace_app.wsf_collector_cutover import prepare,cutover,rollback_interrupted
from workspace_app.wsf_inbox_registry_migration import atomic
from workspace_app.wsf_collector_runner import attempt_once,launchd_template
from workspace_app.wsf_collector_source import FixedSourceReader,provider_for
from workspace_app.company_portfolio_verified import VerifiedRuntimeCompanyPortfolioProvider
from workspace_app.company_portfolio import CompanyPortfolioError

class CollectorIntegrationTests(TestCase):
    def setUp(self):
        t=TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name).resolve()/"runtime"
        self.now=datetime(2026,11,18,15,20,tzinfo=timezone.utc)
        fixed_now=self.now
        class FixedDateTime(datetime):
            @classmethod
            def now(cls,tz=None):
                return fixed_now.astimezone(tz) if tz else fixed_now.replace(tzinfo=None)
        for target,replacement in (
            ("workspace_app.wsf_inbox_runtime.datetime",FixedDateTime),
            ("workspace_app.wsf_inbox_routes.datetime",FixedDateTime),
            ("workspace_app.wsf_roadmap_inbox.datetime",FixedDateTime),
            ("workspace_app.wsf_local_roadmap_collector._utc",lambda:fixed_now),
            ("workspace_app.wsf_collector_runner._now",lambda:fixed_now)):
            guard=patch(target,replacement);guard.start();self.addCleanup(guard.stop)
        self.end=min(self.now+timedelta(days=1),EXPIRY)
        self.org=Identity("organization","test-org","platform")
        self.owner=Identity("principal","owner",self.org.value)
        self.svc=Identity("principal","collector",self.org.value)
        p704.initialize_access_store(self.root,self.org)
        for principal,kind in ((self.owner,"human"),(self.svc,"service")):
            p704.register_principal(self.root,principal,kind=kind)
        hc=p704.issue_credential(self.root,self.owner)["credential_id"]
        sc=p704.issue_credential(self.root,self.svc)["credential_id"]
        hg=p704.grant_access(self.root,self.owner,operation="workspace.open",resource="productive-workspace",access_paths=("local",))
        sg=p704.grant_access(self.root,self.svc,operation="workspace.inbox.collect",resource="roadmap-inbox",access_paths=("local",))
        self.h=AccessContext(self.org,self.owner,"human",hc,hg)
        self.s=AccessContext(self.org,self.svc,"service",sc,sg)
        self.grants={v:p704.grant_access(self.root,self.owner,operation=v,resource="roadmap-inbox",access_paths=("local",)) for v in OPERATIONS.values()}
        self.publication="c"*40;self.release="a"*40
        target=self.root/"releases"/self.release;target.mkdir(parents=True)
        (self.root/"current").symlink_to(target)
        (self.root/"run").mkdir(mode=0o700,exist_ok=True)
        (self.root/"config").mkdir(mode=0o700,exist_ok=True)
        self.legacy=RoadmapInbox(self.root/"workspace-company-roadmap-inbox",self.h,bindings=exact_registry())
        self.legacy.initialize(self.h)
        at=self.now-timedelta(minutes=1)
        self.legacy.scan(self.h,uuid4().hex,self.projection(at,"1"),at.isoformat())
        self.volume=self.root/"volume";self.volume.mkdir(mode=0o700)
        (self.volume/"inbox").mkdir(mode=0o700)
        self.backup=self.factory(self.legacy.file);self.backup.copy_latest(self.h)
        self.archive=self.volume/"inbox"/"cutover-archive"
        p={"schema":SCHEMA,"draft_blob":SUCCESSOR_DRAFT,"registry_sha256":REGISTRY_SHA,
           "scope":_identity(self.h),"credential_id":hc,"starts_at":(self.now-timedelta(hours=1)).isoformat(),
           "expires_at":self.end.isoformat(),"grants":self.grants,"purpose":"owner-triggered-roadmap-metadata"}
        raw=_json(p)
        atomic(self.root/"config"/"roadmap-inbox-policy.json",raw)
        atomic(self.root/"config"/"roadmap-inbox-activation.json",_json({"schema":RECEIPT_SCHEMA,"draft_blob":SUCCESSOR_DRAFT,"policy_sha256":_digest(raw)}))
        review={"schema":"arvectum.workspace.collector-source-review/1","mode":"anonymous-public",
           "repositories":sorted(exact_registry()[k]["repository"] for k in ACTIVE),
           "contents":"read-only","metadata":"read-only","credential":"none","external_verification_required":True}
        reviewraw=_json(review)
        atomic(self.root/"config"/"roadmap-collector-source-review.json",reviewraw)
        self.doc={"schema":"arvectum.workspace.collector-policy/1","draft_blob":DRAFT_BLOB,
           "publication":self.publication,"registry_sha256":REGISTRY_SHA,"owner_scope":_identity(self.h),
           "organization":_identity(self.h)[0],"principal":[self.svc.namespace,self.svc.value,self.svc.scope],
           "credential_id":sc,"grant_id":sg,"release_sha":self.release,
           "starts_at":(self.now-timedelta(hours=1)).isoformat(),"expires_at":self.end.isoformat(),
           "source_mode":"anonymous-public","source_review_sha256":_digest(reviewraw)}
        self.docs=prepare(self.root,self.legacy,self.h,self.backup,self.doc,self.publication)
        self.hpilot=RuntimeInboxPilot(self.root,collector_publication=self.publication)
        self.hpilot.manual.review_signal=lambda a:{"due_at":self.end.isoformat()}

    def factory(self,f):
        return PilotBackup(f,volume=self.volume,uuid="fixture",parts=("inbox",),verifier=lambda v,u:None)

    def projection(self,at,sha="2",digest="a"):
        rows=[]
        for k,b in exact_registry().items():
            src={"repository":b["repository"],"path":b["path"],"adapter":b["adapter"],"freshness":"fresh-fetch",
                 "commit_sha":sha*40,"content_sha256":digest*64,"fetched_at":at.isoformat()} if k in ACTIVE else None
            rows.append({"id":k,"repository":b["repository"],"roadmap_path":b["path"],
                         "state":"current-source-backed" if src else "reconciliation-required","source":src})
        return {"schema":"arvectum.workspace.company-portfolio/1","projection":{"read_only":True,"canonical_authority":False},
                "scope":{"organization_resolved_server_side":True,"actor_resolved_server_side":True,"cross_organization_aggregation":False},"projects":rows}

    def migrate(self,**kw):
        return cutover(self.root,self.legacy,self.h,self.backup,self.archive,self.docs,self.publication,quiescent=lambda:None,confirm=True,**kw)
    def test_runtime_human_service_integration(self):
        self.assertEqual(len(self.hpilot.authorize(self.h,"read").read(self.h)["sources"]),10)
        self.migrate()
        self.assertEqual(len(self.hpilot.authorize(self.h,"read").read(self.h)["sources"]),8)
        with self.assertRaises(ManualContextError):RuntimeInboxPilot(self.root).authorize(self.h,"read")
        with self.assertRaises(ManualContextError):self.hpilot.authorize(self.s,"read")
        inbox,p,policy,resolve=service_inbox(self.root,publication=self.publication)
        provider=provider_for(self.root,p)
        with patch.object(provider,"project",side_effect=lambda *a,**k:self.projection(self.now,digest="b")):
            result=attempt_once(self.root,inbox,policy,resolve,provider,backup_factory=self.factory)
        self.assertEqual(result["backup_status"],"verified")
        with patch("workspace_app.wsf_inbox_runtime.PilotBackup",side_effect=lambda store,**kw:self.factory(store)):
            d=self.hpilot.read(self.h)
            self.assertEqual(d["pending_count"],8)
            self.assertEqual(d["collector"]["run_state"],"verified")
            self.assertEqual(d["backup_status"],"verified")
            item=d["items"][0]
            self.hpilot.mutate(lambda:self.h,"review",{"key":uuid4().hex,"item_id":item["id"],"expected_revision":1,"state":"reviewed"})
            self.assertEqual(self.hpilot.read(self.h)["pending_count"],7)
        p704.revoke_credential(self.root,self.s.credential_id)
        with self.assertRaises(ManualContextError):resolve()
        self.assertEqual(len(self.hpilot.authorize(self.h,"read").read(self.h)["sources"]),8)

    def test_interruption_fails_closed_and_rollback(self):
        def interrupt(path,raw):
            if path.name==CONFIG:raise OSError("simulated interruption")
            atomic(path,raw)
        with self.assertRaises(OSError):self.migrate(write=interrupt)
        self.assertTrue((self.root/"config"/JOURNAL).is_file())
        with self.assertRaises(ManualContextError):self.hpilot.authorize(self.h,"read")
        with self.assertRaises(ManualContextError):service_inbox(self.root,publication=self.publication)
        rollback_interrupted(self.root,self.legacy,self.h,self.backup,self.archive,quiescent=lambda:None,confirm=True)
        self.assertEqual(self.legacy.export(self.h),self.docs["legacy.json"])
        self.assertEqual(self.backup.verified_snapshot(self.h),self.docs["legacy.json"])
        self.assertEqual(len(self.hpilot.authorize(self.h,"read").read(self.h)["sources"]),10)

    def test_source_no_auth_and_exact_get_paths(self):
        reader=FixedSourceReader()
        provider=VerifiedRuntimeCompanyPortfolioProvider(REGISTRY,reader=reader)
        calls=[]
        class Resp:
            def __init__(self,data):self.data=data
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,*a):return _json(self.data)
        def fetch(req,**kw):
            calls.append(req)
            return Resp({"sha":"2"*40} if req.full_url.endswith("/commits/main") else
                        {"encoding":"base64","content":b64encode(b"# Roadmap").decode()})
        with patch.dict("os.environ",{"ARVECTUM_WORKSPACE_GITHUB_TOKEN":"must-not-be-used"}):
            with patch.object(reader.opener,"open",side_effect=fetch):
                for d in provider._descriptors:
                    if d.project_id in ACTIVE:reader.read(d)
                    else:
                        with self.assertRaises(CompanyPortfolioError):reader.read(d)
        self.assertEqual(len(calls),16)
        self.assertTrue(all(r.get_method()=="GET" and not r.has_header("Authorization") and r.full_url.startswith("https://api.github.com/") for r in calls))
        with self.assertRaises(CompanyPortfolioError):reader._json("https://example.invalid/")

    def test_launcher_and_default_denial(self):
        with self.assertRaises(ManualContextError):load_config(self.root)
        d=plistlib.loads(launchd_template(self.root,self.release))
        self.assertEqual(d["StartInterval"],10800);self.assertTrue(d["RunAtLoad"])
        self.assertFalse(d["KeepAlive"])
        self.assertIn(self.release,d["ProgramArguments"][0])
        self.assertNotIn("ARVECTUM_WORKSPACE_GITHUB_TOKEN",d["EnvironmentVariables"])

    def test_runner_retry_bounded_and_duplicate_window(self):
        from workspace_app.wsf_collector_runner import read_status
        self.migrate()
        inbox,p,policy,resolve=service_inbox(self.root,publication=self.publication)
        provider=provider_for(self.root,p)
        with patch("workspace_app.wsf_collector_runner._now",return_value=self.now):
            with patch("workspace_app.wsf_collector_runner.collect_cycle",side_effect=OSError("fixture")) as f:
                self.assertEqual(attempt_once(self.root,inbox,policy,resolve,provider,backup_factory=self.factory)["status"],"retry-possible")
                self.assertEqual(read_status(self.root)["state"],"retry-pending")
                self.assertEqual(attempt_once(self.root,inbox,policy,resolve,provider,backup_factory=self.factory)["status"],"retry-exhausted")
                self.assertEqual(read_status(self.root)["state"],"blocked")
                self.assertEqual(attempt_once(self.root,inbox,policy,resolve,provider,backup_factory=self.factory),{"status":"not-due","previous_state":"blocked"})
                self.assertEqual(f.call_count,2)

    def test_runner_duplicate_success_is_read_only(self):
        self.migrate()
        inbox,p,policy,resolve=service_inbox(self.root,publication=self.publication)
        provider=provider_for(self.root,p)
        with patch("workspace_app.wsf_collector_runner._now",return_value=self.now):
            with patch.object(provider,"project",side_effect=lambda *a,**k:self.projection(self.now)) as fetch:
                first=attempt_once(self.root,inbox,policy,resolve,provider,backup_factory=self.factory)
                self.assertEqual(first["backup_status"],"verified")
                before=inbox.export(self.h)
                second=attempt_once(self.root,inbox,policy,resolve,provider,backup_factory=self.factory)
                self.assertEqual(second,{"status":"not-due","previous_state":"verified"})
                self.assertEqual(inbox.export(self.h),before)
                self.assertEqual(fetch.call_count,1)

    def test_active_collector_cycle_denies_governed_deploy_lock(self):
        import os,subprocess
        self.migrate()
        inbox,_,_,_=service_inbox(self.root,publication=self.publication)
        source=(Path(__file__).resolve().parents[1]/"p7_06_macos_deploy.sh").read_text()
        helper=source[source.index("acquire_lock() {"):source.index("wait_loaded() {")]
        env={**os.environ,"RUNTIME_ROOT":str(self.root),"LOCK_DIR":str(self.root/"run"/"p7-06-deploy.lock")}
        command='fail() { printf "%s\\n" "$1" >&2; exit 1; }\n'+helper+'\nacquire_lock; release_lock'
        with inbox.file.cycle_lock():
            attempt=subprocess.run(["/bin/sh","-c",command],env=env,capture_output=True,text=True,timeout=10)
            self.assertNotEqual(attempt.returncode,0)
            self.assertIn("roadmap collector cycle active or unsafe",attempt.stderr)
            self.assertFalse((self.root/"run"/"p7-06-deploy.lock").exists())
        self.assertEqual(subprocess.run(["/bin/sh","-c",command],env=env,capture_output=True,timeout=10).returncode,0)
