from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from test_workspace_app import FakeResolver,settings
from workspace_app.main import create_app,RELEASE_HEADER
from workspace_app.release import load_release
from workspace_app.wsf_crm import CRMStore
from workspace_app.wsf_crm_routes import FixtureCRMPilot


class CRMRoutesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.resolver=FakeResolver()
        self.a=self.resolver.authorize()
        self.p="PRJ-"+uuid4().hex
        self.store=CRMStore(self.root/"synthetic-crm",self.a,project_ids={self.p},evidence_refs={"fixture:meeting"})
        self.store.initialize(self.a)
        self.headers={RELEASE_HEADER:load_release().release_id,"Origin":"http://127.0.0.1:8769"}
        self.base="/api/app/v1/crm"
        self.now=datetime.now(timezone.utc)

    def client(self,pilot=None):
        c=TestClient(create_app(settings(self.root),access_resolver=self.resolver,crm_fixture=pilot),
                     base_url="http://127.0.0.1:8769",client=("127.0.0.1",50000))
        self.addCleanup(c.close);return c

    def pilot(self,**kw):
        return FixtureCRMPilot(**{"store":self.store,"credential_id":self.a.credential_id,"grant_id":self.a.grant_id,
                     "starts_at":self.now-timedelta(minutes=1),"expires_at":self.now+timedelta(days=1),
                     "allowed_operations":frozenset({"read","write","export"}),**kw})

    def boot(self,c):
        r=c.post("/api/app/v1/session/bootstrap",headers=self.headers)
        self.assertEqual(r.status_code,200)
        return {**self.headers,"X-Arvectum-CSRF":r.json()["session"]["csrf_token"]}

    def submit(self,c,h,kind,data,**kw):
        return c.post(self.base+"/submit",headers=h,json={"key":uuid4().hex,"entity":kind,
                     "data":data,"record_id":None,"expected_revision":0,**kw})

    def test_default_disabled_no_session(self):
        c=self.client()
        self.assertEqual(c.get(self.base,headers=self.headers).status_code,401)
        h=self.boot(c)
        self.assertEqual(c.get(self.base,headers=h).status_code,503)
        self.assertEqual(c.post(self.base+"/submit",headers=h,json={}).status_code,503)

    def test_full_fixture_journey(self):
        c=self.client(self.pilot());h=self.boot(c)
        p=self.submit(c,h,"party",{"name":"Synthetic","registry_ref":None,"description":"Fixture"})
        self.assertEqual(p.status_code,200);pid=p.json()["id"]
        person=self.submit(c,h,"contact",{"party_id":pid,"name":"Synthetic Person","role":"Fixture","channel_ref":None})
        self.assertEqual(person.status_code,200);cid=person.json()["id"]
        o=self.submit(c,h,"opportunity",{"party_id":pid,"contact_id":cid,"title":"Synthetic opportunity","stage":"qualified",
             "next_action":"Review","next_contact_at":None,"project_id":self.p,"evidence_refs":[],"outcome_ref":None})
        self.assertEqual(o.status_code,200)
        i=self.submit(c,h,"interaction",{"party_id":pid,"contact_id":cid,"opportunity_id":o.json()["id"],"project_id":self.p,
                     "kind":"meeting","occurred_at":"2026-01-01T00:00:00+00:00","summary":"Fixture","evidence_ref":"fixture:meeting"})
        self.assertEqual(i.status_code,200)
        d=c.get(self.base,params={"project_id":self.p},headers=h).json()
        self.assertEqual([len(v) for v in d.values()],[1,1,1,1])
        self.assertEqual(c.get(self.base+"/parties/"+pid+"/timeline",headers=h).json(),[i.json()])
        self.assertEqual(c.get(self.base+"/records/"+pid+"/history",headers=h).json(),[p.json()])
        ex=c.get(self.base+"/export",headers=h);self.assertEqual(ex.status_code,200)
        self.assertEqual(ex.content,self.store.export(self.a));self.assertEqual(ex.headers["cache-control"],"no-store")

    def test_operation_permission_and_expiry(self):
        c=self.client(self.pilot(allowed_operations=frozenset({"read"})));h=self.boot(c)
        self.assertEqual(c.get(self.base,headers=h).status_code,200)
        self.assertEqual(c.post(self.base+"/submit",headers=h,json={}).status_code,403)
        self.assertEqual(c.get(self.base+"/export",headers=h).status_code,403)
        c=self.client(self.pilot(expires_at=self.now-timedelta(seconds=1)));h=self.boot(c)
        self.assertEqual(c.get(self.base,headers=h).status_code,403)

    def test_csrf_bounded_body_and_session_revocation(self):
        c=self.client(self.pilot());h=self.boot(c)
        self.assertEqual(c.post(self.base+"/submit",headers=self.headers,json={}).status_code,403)
        self.assertEqual(c.post(self.base+"/submit",headers=h,json={"data":"x"*25000}).status_code,400)
        self.resolver.denied=True
        self.assertEqual(c.get(self.base,headers=h).status_code,403)
        self.assertEqual(c.get(self.base+"/export",headers=h).status_code,401)
