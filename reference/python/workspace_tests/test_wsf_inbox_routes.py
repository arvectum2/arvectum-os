from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile,unittest
from uuid import uuid4
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_workspace_app import FakeResolver,settings
from workspace_app.main import create_app,RELEASE_HEADER
from workspace_app.release import load_release
from workspace_app.wsf_inbox_routes import FixtureInboxPilot
from workspace_app.wsf_roadmap_inbox import RoadmapInbox,registry_bindings
from workspace_app.wsf_manual_backup import PilotBackup
from workspace_app.company_portfolio_verified import VerifiedRuntimeCompanyPortfolioProvider

BASE="/api/app/v1/roadmap-inbox"

class InboxRoutesTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name).resolve()
        self.resolver=FakeResolver();self.a=self.resolver.authorize()
        self.bindings=registry_bindings()
        self.inbox=RoadmapInbox(self.root/"inbox",self.a,bindings=self.bindings)
        self.inbox.initialize(self.a)
        volume=self.root/"volume";volume.mkdir(mode=0o700);(volume/"inbox").mkdir(mode=0o700)
        self.backup=PilotBackup(self.inbox.file,volume=volume,uuid="fixture",parts=("inbox",),verifier=lambda v,u:None)
        self.backup.copy_latest(self.a)
        self.provider=VerifiedRuntimeCompanyPortfolioProvider()
        self.now=datetime.now(timezone.utc)
        self.headers={RELEASE_HEADER:load_release().release_id,"Origin":"http://127.0.0.1:8769"}

    def projection(self,change=False):
        rows=[]
        for pid,b in self.bindings.items():
            ready=b["path"] is not None
            row={"id":pid,"repository":b["repository"],"roadmap_path":b["path"],"state":"current-source-backed" if ready else "reconciliation-required","source":None}
            if ready:
                row["source"]={"repository":b["repository"],"path":b["path"],"adapter":b["adapter"],"freshness":"fresh-fetch","commit_sha":("2" if change else "1")*40,"content_sha256":("b" if change and pid=="COMPANY" else "a")*64,"fetched_at":datetime.now(timezone.utc).isoformat()}
            rows.append(row)
        return {"schema":"arvectum.workspace.company-portfolio/1","projection":{"read_only":True,"canonical_authority":False},"scope":{"organization_resolved_server_side":True,"actor_resolved_server_side":True,"cross_organization_aggregation":False},"projects":rows}

    def pilot(self,**kw):
        return FixtureInboxPilot(**{"inbox":self.inbox,"provider":self.provider,"backup":self.backup,
            "credential_id":self.a.credential_id,"grant_id":self.a.grant_id,"starts_at":self.now-timedelta(minutes=1),
            "expires_at":self.now+timedelta(days=1),"operations":frozenset({"read","poll","review","export"}),**kw})

    def client(self,pilot=None):
        c=TestClient(create_app(settings(self.root),access_resolver=self.resolver,inbox_fixture=pilot),base_url="http://127.0.0.1:8769",client=("127.0.0.1",50000))
        self.addCleanup(c.close);return c

    def boot(self,c):
        r=c.post("/api/app/v1/session/bootstrap",headers=self.headers)
        self.assertEqual(r.status_code,200)
        return {**self.headers,"X-Arvectum-CSRF":r.json()["session"]["csrf_token"]}

    def test_default_disabled(self):
        c=self.client()
        self.assertEqual(c.get(BASE,headers=self.headers).status_code,401)
        h=self.boot(c)
        self.assertEqual(c.get(BASE,headers=h).status_code,503)
        self.assertEqual(c.post(BASE+"/poll",headers=h,json={"key":uuid4().hex}).status_code,503)

    def test_poll_review_export_and_replay(self):
        c=self.client(self.pilot());h=self.boot(c)
        with patch.object(self.provider,"project",side_effect=[self.projection(),self.projection(True)]) as fetch:
            first={"key":uuid4().hex}
            self.assertEqual(c.post(BASE+"/poll",headers=h,json=first).status_code,200)
            self.assertEqual(c.post(BASE+"/poll",headers=h,json=first).status_code,200)
            self.assertEqual(fetch.call_count,1)
            self.assertEqual(c.post(BASE+"/poll",headers=h,json={"key":uuid4().hex}).status_code,200)
            self.assertEqual(fetch.call_count,2)
        d=c.get(BASE,headers=h).json();self.assertEqual(d["backup_status"],"verified")
        self.assertEqual(d["pending_count"],1);row=d["items"][0]
        brief=c.get(BASE+"/brief",headers=h).json()
        self.assertEqual(brief["suggestions"][0]["business_impact"],"unknown")
        command={"key":uuid4().hex,"item_id":row["id"],"expected_revision":1,"state":"reviewed"}
        self.assertEqual(c.post(BASE+"/review",headers=h,json=command).status_code,200)
        self.assertEqual(c.post(BASE+"/review",headers=h,json=command).status_code,200)
        self.assertEqual(c.get(BASE,headers=h).json()["pending_count"],0)
        self.assertEqual(c.get(BASE+"/export",headers=h).content,self.inbox.export(self.a))
        self.assertEqual(self.inbox.export(self.a),self.backup.verified_snapshot(self.a))

    def test_scope_csrf_payload_and_revocation(self):
        c=self.client(self.pilot(operations=frozenset({"read"})));h=self.boot(c)
        self.assertEqual(c.post(BASE+"/poll",headers=h,json={"key":uuid4().hex}).status_code,403)
        self.assertEqual(c.get(BASE+"/export",headers=h).status_code,403)
        c=self.client(self.pilot());h=self.boot(c)
        self.assertEqual(c.post(BASE+"/poll",headers=self.headers,json={"key":uuid4().hex}).status_code,403)
        self.assertEqual(c.post(BASE+"/poll",headers=h,json={"key":uuid4().hex,"url":"https://example.invalid"}).status_code,400)
        self.resolver.denied=True
        self.assertEqual(c.get(BASE,headers=h).status_code,403)
        self.assertEqual(c.get(BASE,headers=h).status_code,401)
