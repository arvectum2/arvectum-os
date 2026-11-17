import copy
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

import test_wsf_control_projection as fixture_module
from test_wsf_manual_context import access
from workspace_app.wsf_manual_context import ManualContextError, _identity
from workspace_app.wsf_control_cache import ControlSourceCache


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.a=access()
        self.p="PRJ-"+uuid4().hex
        self.now="2026-11-17T10:00:00+00:00"
        self.expiry="2026-11-18T10:00:00+00:00"
        self.fixture=fixture_module.ControlProjectionTests()
        self.fixture.setUp()
        self.cache=self.make("original")
        self.cache.initialize(self.a)
        self.r=self.fixture.record("WORK-fixture")
        self.packet={"scope":_identity(self.a),"source_ref":"fixture:register",
                     "as_of":"2026-11-17T09:30:00+00:00","coverage":"partial","records":[self.r]}
        self.first={"source_version":"a"*64,"expected_predecessor":None,"review_until":self.expiry,
                   "packet":self.packet,"project_links":{self.r["id"]:self.p},"now":self.now}

    def make(self,name,**kw):
        return ControlSourceCache(self.root/name,self.a,**{"source_ref":"fixture:register",
                "positions":{"POS-001","POS-004"},"project_ids":{self.p},**kw})

    def admit(self,**kw):
        return self.cache.admit_revision(self.a,**{**self.first,**kw})

    def test_persistence_and_idempotent_source_replay(self):
        first=self.admit()
        self.cache=self.make("original")
        self.assertEqual(self.admit(),first)
        view=self.cache.read(self.a,self.now)
        self.assertEqual(view["project_links"],self.first["project_links"])
        self.assertEqual(len(view["delegated_work"]),1)
        self.assertEqual(len(self.cache.history(self.a,self.r["id"],self.now)),1)
        changed=copy.deepcopy(self.packet);changed["records"][0]["title"]="Different"
        with self.assertRaises(ManualContextError):self.admit(packet=changed)

    def test_revision_chain_and_missing_record_not_closed(self):
        a=self.admit()
        p={**self.packet,"records":[]}
        with self.assertRaises(ManualContextError):
            self.admit(source_version="b"*64,packet=p,project_links={})
        self.admit(source_version="b"*64,expected_predecessor=a["digest"],packet=p,project_links={})
        d=self.cache.read(self.a,self.now)
        self.assertEqual(d["missing_from_latest"],[self.r["id"]])
        self.assertFalse(d["closed"])
        self.assertEqual(len(self.cache.history(self.a,self.r["id"],self.now)),1)

    def test_expired_packet_cannot_be_decision_ready(self):
        r=self.fixture.record("DEC-fixture",owner_action="required_now",decision_card={**self.fixture.card,"review_expiry":None})
        self.admit(packet={**self.packet,"records":[r]},project_links={})
        self.assertTrue(self.cache.read(self.a,self.now)["owner_action"][0]["decision_ready"])
        out=self.cache.read(self.a,self.expiry)
        self.assertTrue(out["review_expired"])
        self.assertFalse(out["owner_action"][0]["decision_ready"])
        self.assertEqual(out["owner_action"][0]["freshness"],"stale_for_declared_use")

    def test_source_scope_project_and_record_binding(self):
        for p,links in (({**self.packet,"source_ref":"other"},{}),
                        ({**self.packet,"scope":_identity(access(org="other"))},{}),
                        (self.packet,{self.r["id"]:"PRJ-"+uuid4().hex}),
                        (self.packet,{"WORK-other":self.p})):
            with self.assertRaises(ManualContextError):self.admit(packet=p,project_links=links)
        with self.assertRaises(ManualContextError):self.cache.read(access(actor="other"),self.now)
        self.assertEqual(self.cache.read(self.a,self.now)["coverage"],"unknown")

    def test_export_restore_and_overwrite_denial(self):
        self.admit()
        raw=self.cache.export(self.a,self.now)
        restored=self.make("restore")
        restored.restore_empty(self.a,raw,self.now)
        self.assertEqual(restored.export(self.a,self.now),raw)
        self.assertEqual(restored.read(self.a,self.now),self.cache.read(self.a,self.now))
        with self.assertRaises(ManualContextError):restored.restore_empty(self.a,raw,self.now)
        other=self.make("other",source_ref="other")
        with self.assertRaises(ManualContextError):other.restore_empty(self.a,raw,self.now)

    def test_corrupt_or_missing_snapshot_not_reinitialized(self):
        self.admit()
        self.cache.path.write_bytes(b"corrupt")
        with self.assertRaises(ManualContextError):self.cache.read(self.a,self.now)
        with self.assertRaises(ManualContextError):self.admit()
        self.assertEqual(self.cache.path.read_bytes(),b"corrupt")
        self.cache.path.unlink()
        with self.assertRaises(ManualContextError):self.cache.read(self.a,self.now)
        self.assertFalse(self.cache.path.exists())

    def test_private_permissions_and_explicit_initialization(self):
        cache=self.make("empty")
        with self.assertRaises(ManualContextError):cache.read(self.a,self.now)
        cache.initialize(self.a)
        self.assertEqual(cache.path.stat().st_mode & 0o777,0o600)
        with self.assertRaises(ManualContextError):cache.initialize(self.a)
        cache.path.chmod(0o644)
        with self.assertRaises(ManualContextError):cache.read(self.a,self.now)

    def test_monotonic_source_time(self):
        first=self.admit()
        with self.assertRaises(ManualContextError):
            self.admit(source_version="b"*64,expected_predecessor=first["digest"],
                      packet={**self.packet,"as_of":"2026-11-17T09:10:00+00:00"})
