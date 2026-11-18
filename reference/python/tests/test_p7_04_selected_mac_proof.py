import json
import os
import tempfile
import unittest
from pathlib import Path

import p7_04_selected_mac_proof as proof


class P704SelectedMacProofTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "runtime"
        self.root.mkdir(mode=0o700)
        run = self.root / "run"
        run.mkdir(mode=0o700)
        self.health = run / "health.json"
        self.health.write_text(
            json.dumps({
                "release_sha": "a" * 40,
                "state": "healthy",
                "canonical_state_written": False,
                "product_effects_enabled": False,
            }),
            encoding="utf-8",
        )
        if os.name != "nt":
            self.health.chmod(0o600)

        p6_root = Path(self.tmp.name) / "p6"
        p6_root.mkdir(mode=0o700)
        self.context = p6_root / "organization-operator.json"
        self.context.write_text(
            json.dumps({
                "schema_version": "p6.05-l4-local-context-1",
                "organization": {
                    "identity": {"namespace": "organization", "value": "org", "scope": "platform"},
                    "context_label": "ООО «Арвектум»",
                },
                "operator": {
                    "identity": {"namespace": "principal", "value": "owner", "scope": "org"},
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
            }),
            encoding="utf-8",
        )
        if os.name != "nt":
            self.context.chmod(0o600)

    def tearDown(self):
        self.tmp.cleanup()

    def test_selected_mac_proof_is_repeatable_and_keeps_authority_boundary(self):
        first = proof.run_selected_mac_proof(self.root, self.context, "b" * 40)
        second = proof.run_selected_mac_proof(self.root, self.context, "b" * 40)
        self.assertEqual(first["status"], "PASS")
        self.assertEqual(second["status"], "PASS")
        self.assertTrue(first["p6_human_identity_reused"])
        self.assertTrue(first["persistent_human_attributable"])
        self.assertTrue(first["persistent_service_attributable"])
        self.assertTrue(first["deny_by_default"])
        self.assertTrue(first["remote_administration_path_explicit"])
        self.assertTrue(first["remote_lifecycle_admin_denied_without_grant"])
        self.assertTrue(first["service_ambient_admin_absent"])
        self.assertTrue(first["credential_rotation_fail_closed"])
        self.assertTrue(first["grant_revocation_fail_closed"])
        self.assertFalse(first["ambient_admin"])
        self.assertFalse(first["organizational_authority_provided"])
        self.assertFalse(first["consequential_approval_provided"])
        self.assertFalse(first["canonical_mutation"])
        self.assertFalse(first["external_effects"])

    def test_multi_service_proof_never_rotates_collector(self):
        from arvectum_os_ref.identity import Identity
        p=proof.p704
        proof.run_selected_mac_proof(self.root,self.context,"b"*40)
        before=p.load_access_store(self.root)
        observer=next(k for k,r in before["principals"].items() if r["kind"]=="service")
        collector=Identity("principal","fixture-collector","org")
        ck=p.register_principal(self.root,collector,kind="service")
        cid=p.issue_credential(self.root,collector)["credential_id"]
        gid=p.grant_access(self.root,collector,operation="workspace.inbox.collect",resource="roadmap-inbox")
        baseline=p.load_access_store(self.root)
        for kwargs in ({},{"service_principal_key":ck}):
            with self.assertRaises(p.IntegrityError):
                proof.run_selected_mac_proof(self.root,self.context,"b"*40,**kwargs)
            self.assertEqual(p.load_access_store(self.root),baseline)
        result=proof.run_selected_mac_proof(self.root,self.context,"b"*40,service_principal_key=observer)
        self.assertEqual(result["status"],"PASS")
        after=p.load_access_store(self.root)
        self.assertEqual(after["credentials"][cid],baseline["credentials"][cid])
        self.assertEqual(after["grants"][gid],baseline["grants"][gid])
        self.assertEqual([g for g in after["grants"].values() if g["principal_key"]==ck],[baseline["grants"][gid]])
        # Even if the observer is disabled, an unrelated single service must not be reused.
        p.disable_principal(self.root,p._id_load(after["principals"][observer]["identity"],"observer"))
        with self.assertRaises(p.IntegrityError):
            proof.run_selected_mac_proof(self.root,self.context,"b"*40)

    def test_selected_mac_proof_fails_closed_when_runtime_is_not_healthy(self):
        health = json.loads(self.health.read_text(encoding="utf-8"))
        health["state"] = "stopped"
        self.health.write_text(json.dumps(health), encoding="utf-8")
        if os.name != "nt":
            self.health.chmod(0o600)
        with self.assertRaises(Exception):
            proof.run_selected_mac_proof(self.root, self.context, "b" * 40)


if __name__ == "__main__":
    unittest.main()
