import json
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import p7_05_selected_mac_proof as proof


SHA = "b" * 40
OTHER_SHA = "c" * 40


class P705SelectedMacProofContractTests(unittest.TestCase):
    def setUp(self):
        # Synthetic runtime fixture must not inspect the host's real launchd job.
        observer = patch.object(proof, "_macos_observer_state", return_value={"loaded":True,"exact_release_pinned":True})
        observer.start(); self.addCleanup(observer.stop)
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "runtime"
        (self.root / "run").mkdir(parents=True, mode=0o700)
        health = {
            "schema": "arvectum.p7_02.runtime-health/1",
            "classification": "non-canonical operational telemetry",
            "release_sha": SHA,
            "instance_id": "test-instance",
            "previous_instance_id": None,
            "generation": 1,
            "pid": os.getpid(),
            "started_at": "2026-08-18T00:00:00Z",
            "heartbeat_at": proof.p705._utc_now(),
            "state": "healthy",
            "network_listener_mode": "none",
            "product_effects_enabled": False,
            "canonical_state_written": False,
        }
        self.health_path = self.root / "run" / "health.json"
        self.health_path.write_text(json.dumps(health), encoding="utf-8")
        if os.name != "nt":
            self.health_path.chmod(0o600)

        self.context = base / "p6-context.json"
        context = {
            "schema_version": "p6.05-l4-local-context-1",
            "organization": {
                "identity": {"namespace": "organization", "value": "org-arvectum", "scope": "platform"},
                "context_label": "ООО «Арвектум»",
            },
            "operator": {
                "identity": {"namespace": "principal", "value": "owner-operator", "scope": "org-arvectum"},
                "principal_category": "human",
                "operating_mode": "owner-operated",
            },
            "authority": {
                "authorization_grants": [],
                "delegations": [],
                "organizational_authority_claimed": False,
            },
            "authentication": {"evidence_refs": []},
            "bootstrap": {"scope": "P6.05-L4", "owner_authorization_asserted": True},
        }
        self.context.write_text(json.dumps(context), encoding="utf-8")
        if os.name != "nt":
            self.context.chmod(0o600)

    def tearDown(self):
        self.tmp.cleanup()

    def test_bounded_selected_mac_contract_passes_without_canonical_mutation(self):
        result = proof.run_selected_mac_proof(self.root, self.context, SHA)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["tool_release_sha"], SHA)
        self.assertEqual(result["persistent_runtime_release_sha"], SHA)
        self.assertEqual(result["final_runtime_state"], "healthy")
        self.assertTrue(result["actionable_alert_path_verified"])
        self.assertTrue(result["governed_tree_hash_unchanged_by_cleanup"])
        self.assertFalse(result["canonical_state_deleted_by_cleanup"])
        self.assertFalse(result["evidence_deleted_by_cleanup"])
        self.assertFalse(result["payload_logging"])
        self.assertFalse(result["reusable_secret_logging"])
        self.assertFalse(result["canonical_mutation"])
        self.assertFalse(result["external_effects"])
        self.assertTrue((self.root / "evidence" / result["attestation_basename"]).exists())
        self.assertFalse((self.root / "run" / "p7-05-alert.json").exists())

    def test_explicit_selection_in_multi_service_registry(self):
        from arvectum_os_ref.identity import Identity
        p=proof.p704
        first=p.bootstrap_from_p6_owner_context(self.root,self.context)
        observer=p._principal_key(proof._identity(first["service_identity"]))
        collector=Identity("principal","collector","org-arvectum")
        key=p.register_principal(self.root,collector,kind="service")
        cid=p.issue_credential(self.root,collector)["credential_id"]
        gid=p.grant_access(self.root,collector,operation="workspace.inbox.collect",resource="roadmap-inbox")
        before=p.load_access_store(self.root)
        with self.assertRaises(p.IntegrityError):
            proof.run_selected_mac_proof(self.root,self.context,SHA)
        result=proof.run_selected_mac_proof(self.root,self.context,SHA,service_principal_key=observer)
        self.assertEqual(result["status"],"PASS")
        after=p.load_access_store(self.root)
        self.assertEqual(after["principals"][key],before["principals"][key])
        self.assertEqual(after["credentials"][cid],before["credentials"][cid])
        self.assertEqual(after["grants"][gid],before["grants"][gid])

    def test_selected_mac_contract_fails_on_runtime_release_mismatch(self):
        health = json.loads(self.health_path.read_text(encoding="utf-8"))
        health["release_sha"] = OTHER_SHA
        health["heartbeat_at"] = proof.p705._utc_now()
        self.health_path.write_text(json.dumps(health), encoding="utf-8")
        if os.name != "nt":
            self.health_path.chmod(0o600)

        with self.assertRaises(proof.p705.IntegrityError) as ctx:
            proof.run_selected_mac_proof(self.root, self.context, SHA)
        self.assertIn("runtime release mismatch", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
