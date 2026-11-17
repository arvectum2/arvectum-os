from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile,unittest
from uuid import uuid4
from fastapi.testclient import TestClient
from test_workspace_app import FakeResolver,settings
from test_wsf_tender_events import TenderEventTests
from workspace_app.main import create_app,RELEASE_HEADER
from workspace_app.release import load_release
from workspace_app.wsf_tender_inbox import TenderInbox,SOURCE_SCHEMA
from workspace_app.wsf_tender_inbox_routes import FixtureTenderInbox
from workspace_app.wsf_manual_backup import PilotBackup

BASE="/api/app/v1/tender-inbox"
class TenderInboxRoutesTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name).resolve()
        self.resolver=FakeResolver();self.a=self.resolver.authorize()
        self.f=TenderEventTests();self.f.setUp()
        self.inbox=TenderInbox(self.root/"inbox",self.a,binding_id="fixture",tenant=self.f.tenant,project_map=self.f.mapping)
        self.inbox.initialize(self.a)
        v=self.root/"volume";v.mkdir(mode=0o700);(v/"tender").mkdir(mode=0o700)
        self.backup=PilotBackup(self.inbox.file,volume=v,uuid="fixture",parts=("tender",),verifier=lambda v,u:None)
        self.backup.copy_latest(self.a);self.calls=0
        self.headers={RELEASE_HEADER:load_release().release_id,"Origin":"http://127.0.0.1:8769"}
    def fetch(self,since,until):
        self.calls+=1
        rows=[self.f.row(),self.f.row("review_required")]
        for r in rows:
            r["created_at"]=(until-timedelta(minutes=1)).isoformat()
            r["envelope"]["occurred_at"]=(until-timedelta(minutes=2)).isoformat()
        return {"schema":SOURCE_SCHEMA,"state":"observed","since":since.isoformat(),"until":until.isoformat(),"coverage":"partial","rows":rows}
    def client(self,enabled=True,ops=None):
        now=datetime.now(timezone.utc)
        fixture=FixtureTenderInbox(self.inbox,self.fetch,self.backup,self.a.credential_id,self.a.grant_id,
             now-timedelta(minutes=1),now+timedelta(days=1),ops if ops is not None else frozenset({"read","poll","review","export"}))
        c=TestClient(create_app(settings(self.root),access_resolver=self.resolver,tender_inbox_fixture=fixture if enabled else None),
                     base_url="http://127.0.0.1:8769",client=("127.0.0.1",50000))
        self.addCleanup(c.close);return c
    def boot(self,c):
        r=c.post("/api/app/v1/session/bootstrap",headers=self.headers);self.assertEqual(r.status_code,200)
        return {**self.headers,"X-Arvectum-CSRF":r.json()["session"]["csrf_token"]}
    def test_default_denied(self):
        c=self.client(False);self.assertEqual(c.get(BASE,headers=self.headers).status_code,401)
        h=self.boot(c);self.assertEqual(c.get(BASE,headers=h).status_code,503)
    def test_poll_review_replay_and_export(self):
        c=self.client();h=self.boot(c);k={"key":uuid4().hex}
        self.assertEqual(c.get(BASE,headers=h).json()["coverage"],"unknown")
        for _ in range(2):self.assertEqual(c.post(BASE+"/poll",headers=h,json=k).status_code,200)
        self.assertEqual(self.calls,1)
        d=c.get(BASE,headers=h).json();self.assertEqual(d["pending_count"],1)
        self.assertEqual(len(d["events"]),2);self.assertEqual(d["backup_status"],"verified")
        r=d["groups"][0];cmd={"key":uuid4().hex,"item_id":r["id"],"expected_revision":r["revision"],"state":"reviewed"}
        for _ in range(2):self.assertEqual(c.post(BASE+"/review",headers=h,json=cmd).status_code,200)
        self.assertEqual(c.get(BASE,headers=h).json()["pending_count"],0)
        self.assertEqual(c.get(BASE+"/export",headers=h).content,self.backup.verified_snapshot(self.a))
    def test_no_source_injection_and_grants(self):
        c=self.client();h=self.boot(c);k={"key":uuid4().hex}
        self.assertEqual(c.post(BASE+"/poll",headers=self.headers,json=k).status_code,403)
        self.assertEqual(c.post(BASE+"/poll",headers=h,json={**k,"rows":[]}).status_code,400)
        self.assertEqual(self.calls,0)
        self.resolver.denied=True
        self.assertEqual(c.get(BASE,headers=h).status_code,403)
        self.assertEqual(c.get(BASE,headers=h).status_code,401)
    def test_no_export_grant_denies_poll(self):
        c=self.client(ops=frozenset({"read","poll"}));h=self.boot(c)
        self.assertEqual(c.post(BASE+"/poll",headers=h,json={"key":uuid4().hex}).status_code,403)
        self.assertEqual(self.calls,0)
