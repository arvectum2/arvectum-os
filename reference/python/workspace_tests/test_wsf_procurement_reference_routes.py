from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile,unittest
from types import SimpleNamespace
from fastapi.testclient import TestClient
from test_workspace_app import FakeResolver,settings
from workspace_app.main import create_app,RELEASE_HEADER
from workspace_app.release import load_release
from workspace_app.wsf_procurement_reference import RuntimeProcurementReference

PATH="/api/app/v1/procurement-reference"

class ReferenceRouteTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name).resolve()
        self.resolver=FakeResolver();self.calls=0
        self.headers={RELEASE_HEADER:load_release().release_id,"Origin":"http://127.0.0.1:8769"}
    def client(self,enabled):
        def read(authorize):
            a=authorize();self.calls+=1
            assert a==authorize()
            return {"schema":"arvectum.workspace.internal-procurement-reference/1","items":[{"fixture":True}],"canonical_authority":False}
        c=TestClient(create_app(settings(self.root),access_resolver=self.resolver,
            procurement_reference=SimpleNamespace(read=read) if enabled else RuntimeProcurementReference(self.root)),
            base_url="http://127.0.0.1:8769",client=("127.0.0.1",50000))
        self.addCleanup(c.close);return c
    def boot(self,c):
        r=c.post("/api/app/v1/session/bootstrap",headers=self.headers)
        self.assertEqual(r.status_code,200)
        return {**self.headers,"X-Arvectum-CSRF":r.json()["session"]["csrf_token"]}
    def test_denied_by_default(self):
        c=self.client(False);self.assertEqual(c.post(PATH,headers=self.headers).status_code,401)
        h=self.boot(c);self.assertEqual(c.post(PATH,headers=h).status_code,503)
        self.assertEqual(self.calls,0)
    def test_read_requires_csrf_no_query_no_body(self):
        c=self.client(True);h=self.boot(c)
        self.assertEqual(c.post(PATH,headers=self.headers).status_code,403)
        self.assertEqual(c.post(PATH+"?deal_id=foreign",headers=h).status_code,400)
        self.assertEqual(c.post(PATH,headers=h,json={"url":"http://example.invalid"}).status_code,400)
        self.assertEqual(self.calls,0)
        r=c.post(PATH,headers=h);self.assertEqual(r.status_code,200)
        self.assertEqual(r.headers["cache-control"],"no-store")
        self.assertEqual(self.calls,1)
        self.resolver.denied=True
        self.assertEqual(c.post(PATH,headers=h).status_code,403)
        self.assertEqual(c.post(PATH,headers=h).status_code,401)
        self.assertEqual(self.calls,1)
