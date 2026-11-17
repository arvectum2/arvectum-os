from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient
from test_workspace_app import FakeResolver, settings
from workspace_app.main import create_app, RELEASE_HEADER
from workspace_app.release import load_release
from workspace_app.wsf_manual_context import ManualContextStore
from workspace_app.wsf_manual_routes import FixtureManualPilot
from uuid import uuid4


class ManualRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.resolver = FakeResolver()
        self.headers = {RELEASE_HEADER: load_release().release_id, "Origin": "http://127.0.0.1:8769"}
        self.store = ManualContextStore(self.root / "synthetic", self.resolver.authorize())
        self.now = datetime.now(timezone.utc)

    def client(self, pilot=None):
        app = create_app(settings(self.root), access_resolver=self.resolver, manual_context_fixture=pilot)
        c = TestClient(app, base_url="http://127.0.0.1:8769", client=("127.0.0.1", 50000))
        self.addCleanup(c.close)
        return c

    def fixture(self, **kw):
        a = self.resolver.authorize()
        args = dict(store=self.store, credential_id=a.credential_id, grant_id=a.grant_id,
                    starts_at=self.now-timedelta(minutes=1), expires_at=self.now+timedelta(days=1))
        return FixtureManualPilot(**{**args, **kw})

    def boot(self, c):
        r = c.post("/api/app/v1/session/bootstrap", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        return {**self.headers, "X-Arvectum-CSRF": r.json()["session"]["csrf_token"]}

    def test_default_denied_and_no_store_created(self):
        c = self.client()
        self.assertEqual(c.get("/api/app/v1/manual-context", headers=self.headers).status_code, 401)
        h = self.boot(c)
        self.assertEqual(c.get("/api/app/v1/manual-context", headers=h).status_code, 503)
        self.assertFalse(self.store.path.exists())

    def test_create_capture_revise_history_export(self):
        c = self.client(self.fixture())
        h = self.boot(c)
        root = "/api/app/v1/manual-context"
        def submit(op, data, key=None):
            return c.post(root+"/submit", headers=h, json={"key":key or uuid4().hex,"operation":op,"payload":data})
        p = submit("project", {"label":"Fixture project","kind":"customer"})
        self.assertEqual(p.status_code, 200)
        key = uuid4().hex
        data = {"title":"Observation","text":"Test details","project_id":p.json()["id"]}
        r = submit("capture", data, key)
        self.assertEqual(r.status_code, 200)
        n = r.json()
        self.assertEqual(submit("capture",data,key).json(),n)
        self.assertEqual(submit("revise",{**data,"note_id":n["id"],"expected_revision":1,"title":"Updated"}).status_code,200)
        self.assertEqual(c.get(root,headers=h).json()["notes"][0]["revision"],2)
        self.assertEqual(len(c.get(root+"/notes/"+n["id"]+"/history",headers=h).json()),2)
        self.assertEqual(c.get(root+"/export",headers=h).content,self.store.export(self.resolver.authorize()))

    def test_expired_wrong_grant_overlong_policy(self):
        for pilot in (self.fixture(starts_at=self.now-timedelta(days=2),expires_at=self.now-timedelta(days=1)),
                      self.fixture(grant_id="not-current"),self.fixture(expires_at=self.now+timedelta(days=31))):
            c = self.client(pilot)
            h = self.boot(c)
            self.assertEqual(c.get("/api/app/v1/manual-context",headers=h).status_code,403)
            self.assertEqual(c.post("/api/app/v1/manual-context/submit",headers=h,json={}).status_code,403)

    def test_csrf_revocation_and_payload_bounds(self):
        c = self.client(self.fixture())
        h=self.boot(c)
        root="/api/app/v1/manual-context"
        self.assertEqual(c.post(root+"/submit",headers=self.headers,json={}).status_code,403)
        self.assertEqual(c.post(root+"/submit",headers=h,json={"body":"x"*25000}).status_code,400)
        self.resolver.denied=True
        self.assertEqual(c.get(root,headers=h).status_code,403)

    def test_project_timeline_and_unknown_control_sources(self):
        c=self.client(self.fixture())
        h=self.boot(c)
        base="/api/app/v1/manual-context"
        p=c.post(base+"/submit",headers=h,json={"key":uuid4().hex,"operation":"project","payload":{"label":"Fixture","kind":"internal"}}).json()
        self.assertEqual(c.post(base+"/submit",headers=h,json={"key":uuid4().hex,"operation":"capture","payload":{"title":"Unverified approval claim","text":"Observation","project_id":p["id"]}}).status_code,200)
        timeline=c.get(base+"/projects/"+p["id"]+"/timeline",headers=h)
        self.assertEqual(timeline.status_code,200)
        self.assertEqual([v["kind"] for v in timeline.json()["events"]],["project-created","note-captured"])
        result=c.get(base+"/mission-control",headers=h)
        self.assertEqual(result.status_code,200)
        self.assertTrue(all(s["state"]=="unknown" and not s["items"] for s in result.json()["sections"]))
        self.resolver.denied=True
        self.assertEqual(c.get(base+"/mission-control",headers=h).status_code,403)
        self.assertEqual(c.get(base+"/projects/"+p["id"]+"/timeline",headers=h).status_code,403)
