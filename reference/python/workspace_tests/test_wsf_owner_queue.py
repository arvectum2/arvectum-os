import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from test_workspace_app import FakeResolver, settings
from workspace_app.main import create_app, RELEASE_HEADER
from workspace_app.release import load_release
from workspace_app.wsf_owner_queue import snapshot_projection, SECTIONS, QUEUES
from workspace_app.wsf_manual_context import ManualContextError

PATH = "/api/app/v1/company-owner-project-queue"


def fixture():
    counts = dict.fromkeys(QUEUES.values(), 0)
    counts["hold"] = 1
    return {"schema":"arvectum.company.owner-work-queue-projection/1",
        "status":"restricted_candidate_projection", "as_of":"2026-11-20", "derived":True,
        "canonical_authority":False,"organizational_authority_provided":False,
        "execution_authorized":False,"complete_company_coverage":False,
        "private_source_observation":{k:{"record_refs":[]} for k in ("control","risk","decision")},
        "project_details":{"Fixture":{"coverage":"partial","stage":"stage","source_as_of":"2026-11-20","subviews":[]}},
        "items":[{"source_key":["Fixture","F1"],"project":"Fixture","source_queue":"deferred","queue":"hold",
                  "execution_authorized":False,"actual_acceptance_verified":False,"owner_decision_ready":False,
                  "related_control_refs":[],"action":"Keep paused","source_as_of":"2026-11-20",
                  "project_due_or_trigger":"Owner restart","unknowns":["outcome"]}],
        "sections":[{"key":k,"entries":[],**({"financial_visibility":{"available_cash":"unknown","payment_authority":False}} if k=="cash_commitments" else {})} for k in SECTIONS],
        "counts":{"projects":1,"actions":1,"queues":counts,"decision_ready_owner_items":0}}


def project(d):
    b=json.dumps(d).encode()
    return snapshot_projection(b,"a"*40,hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest(),hashlib.sha256(b).hexdigest())


class ProjectionTests(unittest.TestCase):
    def test_snapshot(self):
        v=project(fixture());self.assertEqual(v["items"][0]["queue"],"hold")
        self.assertNotIn("private_source_observation",v)
        self.assertFalse(v["execution_authorized"])
    def test_wrong_digest(self):
        with self.assertRaises(ManualContextError):
            snapshot_projection(b"{}","a"*40,"b"*40,"c"*64)
    def test_duplicate(self):
        d=fixture();d["items"]*=2
        with self.assertRaises(ManualContextError):project(d)
    def test_hold_not_reopened(self):
        d=fixture();d["items"][0]["queue"]="prepare_within_existing_envelope"
        with self.assertRaises(ManualContextError):project(d)
    def test_implicit_authority(self):
        d=fixture();d["items"][0]["execution_authorized"]=True
        with self.assertRaises(ManualContextError):project(d)
    def test_fake_owner_decision(self):
        d=fixture();d["sections"][1]["entries"]=[{"title":"Approval","next_control_point":"Approve","qualification":"unknown"}]
        with self.assertRaises(ManualContextError):project(d)


class RouteTests(unittest.TestCase):
    def client(self, enabled):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.resolver=FakeResolver()
        def read(authorize):
            a=authorize();assert a==authorize();return project(fixture())
        c=TestClient(create_app(settings(Path(t.name).resolve()),access_resolver=self.resolver,
            owner_queue_reference=SimpleNamespace(read=read) if enabled else None),
            base_url="http://127.0.0.1:8769",client=("127.0.0.1",50000))
        self.addCleanup(c.close)
        h={RELEASE_HEADER:load_release().release_id,"Origin":"http://127.0.0.1:8769"}
        self.assertEqual(c.post(PATH,headers=h).status_code,401)
        r=c.post("/api/app/v1/session/bootstrap",headers=h);self.assertEqual(r.status_code,200)
        return c,h,{**h,"X-Arvectum-CSRF":r.json()["session"]["csrf_token"]}
    def test_default_off(self):
        c,_,h=self.client(False);self.assertEqual(c.post(PATH,headers=h).status_code,503)
    def test_read_boundary(self):
        c,h,ok=self.client(True)
        self.assertEqual(c.post(PATH,headers=h).status_code,403)
        self.assertEqual(c.post(PATH+"?project=anything",headers=ok).status_code,400)
        self.assertEqual(c.post(PATH,headers=ok,json={"source":"foreign"}).status_code,400)
        r=c.post(PATH,headers=ok);self.assertEqual(r.status_code,200);self.assertEqual(r.headers["cache-control"],"no-store")
        self.resolver.denied=True;self.assertEqual(c.post(PATH,headers=ok).status_code,403)
