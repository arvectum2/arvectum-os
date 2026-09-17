import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import p7_06_governed_deploy as m

SHA1 = "1" * 40
SHA2 = "2" * 40

class P706Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "releases").mkdir()
        (self.root / "venvs").mkdir()
        (self.root / "config").mkdir()
        (self.root / "evidence").mkdir()
        (self.root / "run").mkdir()
        self._release(SHA1, "arvectum.p7_03.durable-store/1")
        self._release(SHA2, "arvectum.p7_03.durable-store/1")
        os.symlink(self.root / "releases" / SHA1, self.root / "current")
        (self.root / "config/p7-03-recovery.json").write_text(json.dumps({"store_schema":"arvectum.p7_03.durable-store/1"}))
    def tearDown(self): self.tmp.cleanup()

    def _release(self, sha, schema, repository=m.CURRENT_CANONICAL_REPOSITORY):
        r = self.root / "releases" / sha
        src = r / "source/reference/python"
        src.mkdir(parents=True, exist_ok=True)
        for rel in m.REQUIRED_RELEASE_FILES:
            p = r / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if p.name == "p7_03_durable_state.py":
                p.write_text(f'STORE_SCHEMA = {schema!r}\n')
            else:
                p.write_text("# fixture\n")
        archive = r / "reference-python.tar"
        archive.write_bytes(f"archive-{sha}".encode())
        manifest = {"canonical_repository":repository,"release_sha":sha,"reference_python_archive_sha256":hashlib.sha256(archive.read_bytes()).hexdigest()}
        (r / "release-manifest.json").write_text(json.dumps(manifest))
        py = self.root / "venvs" / sha / "bin/python"
        py.parent.mkdir(parents=True, exist_ok=True); py.write_text("")

    def test_build_plan_pins_versions_and_no_replay(self):
        plan = m.build_plan(self.root, SHA2, "owner:P7.06-test")
        self.assertEqual(plan["source_release"], SHA1)
        self.assertEqual(plan["target_release"], SHA2)
        self.assertEqual(plan["migration"]["mode"], "none")
        self.assertTrue(plan["migration"]["rollback_safe"])
        self.assertFalse(plan["external_effect_replay_authorized"])
        self.assertIn("classify-workspace-listener", plan["required_sequence"])
        self.assertIn("conditionally-stop-known-workspace-listener", plan["required_sequence"])
        self.assertIn("conditionally-start-and-verify-exact-target-workspace-listener", plan["required_sequence"])
        self.assertTrue((self.root / "evidence/p7-06/plans" / f"{plan['plan_id']}.json").is_file())

    def test_same_release_rejected(self):
        with self.assertRaises(m.BoundaryError):
            m.build_plan(self.root, SHA1, "owner:test")

    def test_legacy_source_and_current_target_are_admitted(self):
        self._release(SHA1, "arvectum.p7_03.durable-store/1", "arvectum/arvectum-os")
        plan = m.build_plan(self.root, SHA2, "owner:test")
        self.assertEqual(plan["source_release"], SHA1)
        self.assertEqual(plan["target_release"], SHA2)

    def test_arvectum1_legacy_source_and_current_target_are_admitted(self):
        self._release(SHA1, "arvectum.p7_03.durable-store/1", "arvectum1/arvectum-os")
        plan = m.build_plan(self.root, SHA2, "owner:test")
        self.assertEqual(plan["source_release"], SHA1)
        self.assertEqual(plan["target_release"], SHA2)

    def test_current_source_and_arvectum1_legacy_target_are_rejected(self):
        self._release(SHA2, "arvectum.p7_03.durable-store/1", "arvectum1/arvectum-os")
        with self.assertRaises(m.IntegrityError):
            m.build_plan(self.root, SHA2, "owner:test")

    def test_current_source_and_legacy_target_are_rejected(self):
        self._release(SHA2, "arvectum.p7_03.durable-store/1", "arvectum/arvectum-os")
        with self.assertRaises(m.IntegrityError):
            m.build_plan(self.root, SHA2, "owner:test")

    def test_legacy_source_and_legacy_target_are_rejected(self):
        self._release(SHA1, "arvectum.p7_03.durable-store/1", "arvectum/arvectum-os")
        self._release(SHA2, "arvectum.p7_03.durable-store/1", "arvectum/arvectum-os")
        with self.assertRaises(m.IntegrityError):
            m.build_plan(self.root, SHA2, "owner:test")

    def test_arbitrary_source_repository_is_rejected(self):
        self._release(SHA1, "arvectum.p7_03.durable-store/1", "someone/example")
        with self.assertRaises(m.IntegrityError):
            m.build_plan(self.root, SHA2, "owner:test")

    def test_arbitrary_target_repository_is_rejected(self):
        self._release(SHA2, "arvectum.p7_03.durable-store/1", "someone/example")
        with self.assertRaises(m.IntegrityError):
            m.build_plan(self.root, SHA2, "owner:test")

    def test_status_admits_a_legacy_active_source_for_inspection(self):
        self._release(SHA1, "arvectum.p7_03.durable-store/1", "arvectum/arvectum-os")
        self.assertEqual(m.status(self.root)["current_release"], SHA1)

    def test_schema_change_without_plan_rejected(self):
        self._release(SHA2, "arvectum.p7_03.durable-store/2")
        with self.assertRaisesRegex(m.BoundaryError, "requires an explicit"):
            m.build_plan(self.root, SHA2, "owner:test")

    def test_schema_change_even_reversible_plan_is_fail_closed_until_executor_exists(self):
        self._release(SHA2, "arvectum.p7_03.durable-store/2")
        mp = self.root / "migration.json"
        mp.write_text(json.dumps({
            "schema":m.MIGRATION_SCHEMA,"source_release":SHA1,"target_release":SHA2,
            "source_store_schema":"arvectum.p7_03.durable-store/1","target_store_schema":"arvectum.p7_03.durable-store/2",
            "external_effects":False,"historical_effect_replay":False,"reversible":True
        }))
        with self.assertRaisesRegex(m.BoundaryError, "no governed migration executor"):
            m.build_plan(self.root, SHA2, "owner:test", mp)

    def test_tampered_release_archive_rejected(self):
        (self.root / "releases" / SHA2 / "reference-python.tar").write_bytes(b"tampered")
        with self.assertRaises(m.IntegrityError):
            m.verify_release(self.root, SHA2)

    def test_record_transaction_must_match_plan_and_backup(self):
        plan = m.build_plan(self.root, SHA2, "owner:test")
        backups = self.root / "backups"
        backups.mkdir(exist_ok=True)
        backup = backups / "p7-03-backup-fixture.tar.gz"
        backup.write_bytes(b"backup-fixture")
        backup_sha = hashlib.sha256(backup.read_bytes()).hexdigest()
        payload = self.root / "payload.json"
        payload.write_text(json.dumps({
            "plan_id":plan["plan_id"],"source_release":SHA1,"target_release":SHA2,"result":"PASS",
            "backup_path":str(backup),"backup_sha256":backup_sha,
            "runtime_release_verified":True,"observer_release_verified":True,"workspace_listener_disposition":"not-running","rollback_disposition":"safe"
        }))
        tx = m.record_transaction(self.root, payload)
        self.assertEqual(tx["schema"], m.TX_SCHEMA)
        self.assertFalse(tx["canonical_authority"])
        self.assertFalse(tx["external_effect_replay_authorized"])

if __name__ == "__main__": unittest.main()
