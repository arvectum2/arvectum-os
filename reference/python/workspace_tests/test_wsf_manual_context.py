from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

from arvectum_os_ref.identity import Identity
from workspace_app.access import AccessContext
from workspace_app.wsf_manual_context import ManualContextStore, ManualContextError


def access(org="synthetic-org", actor="synthetic-owner", kind="human"):
    return AccessContext(Identity("org", org, "local"), Identity("actor", actor, org), kind, "fixture", "fixture")


class ManualContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.a = access()
        self.store = ManualContextStore(self.root / "original", self.a)

    def project(self):
        return self.store.submit(self.a, uuid4().hex, "project", {"label": "Synthetic project", "kind": "customer"})

    def note(self, project=None):
        return self.store.submit(self.a, uuid4().hex, "capture", {"title": "Fixture", "text": "Synthetic note", "project_id": project})

    def test_reopen_and_independent_ids(self):
        p = self.project()
        n = self.note(p["id"])
        again = ManualContextStore(self.root / "original", self.a)
        self.assertEqual(again.read(self.a), {"projects": [p], "notes": [n]})
        self.assertNotEqual(self.project()["id"], p["id"])
        self.assertFalse(n["canonical_authority"])

    def test_replay_persisted_across_restart(self):
        key = uuid4().hex
        data = {"title": "Fixture", "text": "Observation", "project_id": None}
        item = self.store.submit(self.a, key, "capture", data)
        again = ManualContextStore(self.root / "original", self.a)
        self.assertEqual(again.submit(self.a, key, "capture", data), item)
        with self.assertRaises(ManualContextError):
            again.submit(self.a, key, "capture", {**data, "title": "Changed"})
        self.assertEqual(len(again.read(self.a)["notes"]), 1)

    def test_history_and_optimistic_revision(self):
        n = self.note()
        p = self.project()
        data = {"note_id": n["id"], "expected_revision": 1, "title": "Corrected", "text": "New observation", "project_id": p["id"]}
        key = uuid4().hex
        revised = self.store.submit(self.a, key, "revise", data)
        self.assertEqual(revised["revision"], 2)
        self.assertEqual(self.store.history(self.a, n["id"]), [n, revised])
        self.assertEqual(self.store.submit(self.a, key, "revise", data), revised)
        with self.assertRaises(ManualContextError):
            self.store.submit(self.a, uuid4().hex, "revise", data)
        self.assertEqual(self.store.read(self.a)["notes"], [revised])

    def test_scope_isolation_on_every_read(self):
        n = self.note()
        for other in (access(org="another"), access(actor="other"), access(kind="ai")):
            for action in (lambda: self.store.read(other), lambda: self.store.history(other, n["id"]),
                           lambda: self.store.export(other),
                           lambda: self.store.submit(other, uuid4().hex, "project", {"label":"No","kind":"internal"})):
                with self.assertRaises(ManualContextError):
                    action()
        foreign = ManualContextStore(self.root / "original", access(org="another"))
        with self.assertRaises(ManualContextError):
            foreign.read(access(org="another"))

    def test_unknown_project_and_extra_fields_fail_closed(self):
        for data in ({"title":"A","text":"B","project_id":"PRJ-"+uuid4().hex},
                     {"title":"A","text":"B","project_id":None,"approved":True},
                     {"title":"A","text":"B"*4001,"project_id":None}):
            with self.assertRaises(ManualContextError):
                self.store.submit(self.a, uuid4().hex, "capture", data)
        self.assertEqual(self.store.read(self.a)["notes"], [])

    def test_recovery_and_no_overwrite(self):
        n = self.note(self.project()["id"])
        raw = self.store.export(self.a)
        dest = ManualContextStore(self.root / "restored", self.a)
        dest.restore_empty(self.a, raw)
        self.assertEqual(dest.export(self.a), raw)
        self.assertEqual(dest.history(self.a, n["id"]), [n])
        with self.assertRaises(ManualContextError):
            dest.restore_empty(self.a, raw)
        foreign = ManualContextStore(self.root / "foreign", access(org="another"))
        with self.assertRaises(ManualContextError):
            foreign.restore_empty(access(org="another"), raw)

    def test_corruption_not_treated_as_empty(self):
        self.note()
        path = self.root / "original" / "context.json"
        raw = path.read_bytes()
        path.write_bytes(raw.replace(b"Synthetic note", b"Tampered note"))
        with self.assertRaises(ManualContextError):
            self.store.read(self.a)
        with self.assertRaises(ManualContextError):
            self.note()
        self.assertNotEqual(path.read_bytes(), raw)

    def test_private_permissions(self):
        self.note()
        path = self.root / "original" / "context.json"
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        path.chmod(0o644)
        with self.assertRaises(ManualContextError):
            self.store.read(self.a)

    def test_concurrent_duplicate_serialized(self):
        key = uuid4().hex
        data = {"title":"Fixture","text":"Concurrent","project_id":None}
        def receive(_):
            instance = ManualContextStore(self.root / "original", self.a)
            return instance.submit(self.a, key, "capture", data)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(receive, range(8)))
        self.assertEqual(len({r["id"] for r in results}), 1)
        self.assertEqual(len(self.store.read(self.a)["notes"]), 1)
