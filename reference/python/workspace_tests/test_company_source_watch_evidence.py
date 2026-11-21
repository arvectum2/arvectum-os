"""Source-watch read view cannot turn derived Company signals into authority."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from datetime import datetime,timezone,timedelta
from workspace_app.company_source_watch_evidence import read_company_source_watch, CompanySourceWatchUnavailable

SHA = "1911e34f4056d7201bae5524c366be698079da581219ff30aa244b87f1e1b126"


class CompanySourceWatchReadTests(TestCase):
    def setUp(self):
        tmp=TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name).resolve()/"company-service"
        self.root.mkdir(mode=0o700)
        self.dir=self.root/"reports"
        self.dir.mkdir(mode=0o700)
        self.now=datetime(2026,11,21,13,tzinfo=timezone.utc)
        self.data={"schema":"arvectum.company.project-source-watch-report/1",
            "status":"derived_candidate_review_only","repository_owner":"arvectum2",
            "source_sha256":SHA,"source_blob":"c4addaacf3381f789f2798d0b74cd2413a45d60e",
            "source_commit":"84135f11bc115366fa5aac4ced9db0b86dc1ff0b",
            "source_as_of":"2026-11-20","scanned_at":"2026-11-21T12:17:55+00:00",
            "automatic_approval":False,"automatic_source_repin":False,"canonical_status_modified":False,
            "organizational_authority_provided":False,"execution_authorized":False,
            "coverage":{"projects":22,"source_refs":35,"os_collector_exact_refs_not_refetched":5,
              "os_collector_freshness_verified_here":False,"additional_repos_scanned":14,
              "review_signals":{"observed_source_unchanged":22}},
            "projects":[{"project":f"Synthetic {n}","review_signal":"observed_source_unchanged",
                "business_stage_updated":False,"proposed_business_status":None} for n in range(22)]}
        self.file=self.dir/"company-source-watch-20261121T121755123456Z.json"
        self.save()

    def save(self):
        self.file.write_text(json.dumps(self.data,ensure_ascii=False))
        self.file.chmod(0o600)

    def test_current_candidate_is_read_only_and_not_business_status(self):
        snapshot=read_company_source_watch(self.dir,now=self.now)
        self.assertEqual(snapshot["state"],"current-observation")
        self.assertEqual(snapshot["coverage"]["projects"],22)
        self.assertIs(snapshot["business_status_updated"],False)
        self.assertNotIn("previous_business_stage",snapshot["projects"][0])
        self.assertEqual(snapshot["projects"][0]["project"],"Synthetic 0")

    def test_old_report_is_explicitly_stale(self):
        snapshot=read_company_source_watch(self.dir,now=self.now+timedelta(hours=31))
        self.assertEqual(snapshot["state"],"stale")

    def test_missing_file_or_symlink_is_denied(self):
        self.file.unlink()
        with self.assertRaises(CompanySourceWatchUnavailable):read_company_source_watch(self.dir,now=self.now)
        self.save()
        self.file.unlink();self.file.symlink_to(self.root/"other")
        with self.assertRaises(CompanySourceWatchUnavailable):read_company_source_watch(self.dir,now=self.now)

    def test_world_readable_or_symlink_directory_denied(self):
        self.file.chmod(0o644)
        with self.assertRaises(CompanySourceWatchUnavailable):read_company_source_watch(self.dir,now=self.now)
        self.file.chmod(0o600);self.dir.chmod(0o755)
        with self.assertRaises(CompanySourceWatchUnavailable):read_company_source_watch(self.dir,now=self.now)

    def test_authority_and_baseline_drift_denied(self):
        for key,bad in (("automatic_approval",True),("source_sha256","0"*64),
                        ("repository_owner","other"),("source_as_of","2026-11-21")):
            old=self.data[key];self.data[key]=bad;self.save()
            with self.assertRaises(CompanySourceWatchUnavailable):read_company_source_watch(self.dir,now=self.now)
            self.data[key]=old

    def test_project_tamper_or_fake_collector_health_denied(self):
        for action in (lambda: self.data["projects"][0].update({"business_stage_updated":True}),
                       lambda: self.data["projects"][0].update({"proposed_business_status":"DONE"}),
                       lambda: self.data["coverage"].update({"os_collector_freshness_verified_here":True}),
                       lambda: self.data["coverage"].update({"review_signals":{"observed_source_unchanged":21}})):
            original=json.loads(json.dumps(self.data))
            action();self.save()
            with self.assertRaises(CompanySourceWatchUnavailable):read_company_source_watch(self.dir,now=self.now)
            self.data=original

    def test_report_never_imports_runtime_or_has_network_operations(self):
        import inspect
        import workspace_app.company_source_watch_evidence as mod
        code=inspect.getsource(mod)
        for token in ("urllib", "subprocess", "requests", "os.system", "launchctl", "git fetch"):
            self.assertNotIn(token,code)
