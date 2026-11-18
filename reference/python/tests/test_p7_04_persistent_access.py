import json
import os
import tempfile
import unittest
from pathlib import Path

from arvectum_os_ref.identity import Identity
import p7_04_persistent_access as p704


class P704PersistentAccessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "runtime"
        self.org = Identity("organization", "org-arvectum", "platform")
        self.human = Identity("principal", "owner-operator", self.org.value)
        self.service = Identity("principal", "persistent-runtime", self.org.value)
        p704.initialize_access_store(self.root, self.org)
        p704.register_principal(self.root, self.human, kind="human")
        p704.register_principal(self.root, self.service, kind="service")

    def tearDown(self):
        self.tmp.cleanup()

    def issue(self, principal):
        issued = p704.issue_credential(self.root, principal)
        secret = p704.read_credential_secret(Path(issued["secret_path"]))
        return issued, secret

    def test_persistent_human_and_service_identity_roundtrip(self):
        state = p704.load_access_store(self.root)
        identities = {r["identity"]["value"]: r["kind"] for r in state["principals"].values()}
        self.assertEqual(identities["owner-operator"], "human")
        self.assertEqual(identities["persistent-runtime"], "service")
        summary = p704.verify_store(self.root)
        self.assertEqual(summary["human_principals"], 1)
        self.assertEqual(summary["service_principals"], 1)

    def test_p6_owner_identity_continuity_and_service_identity_persist(self):
        p6_root = Path(self.tmp.name) / "p6"
        p6_root.mkdir(mode=0o700)
        context = p6_root / "organization-operator.json"
        payload = {
            "schema_version": "p6.05-l4-local-context-1",
            "organization": {
                "identity": {"namespace": "organization", "value": "p6-org", "scope": "platform"},
                "context_label": "ООО «Арвектум»",
            },
            "operator": {
                "identity": {"namespace": "principal", "value": "p6-owner", "scope": "p6-org"},
                "principal_category": "human",
                "operating_mode": "owner-operated",
            },
            "authority": {
                "authorization_grants": [], "delegations": [], "organizational_authority_claimed": False,
            },
            "authentication": {"evidence_refs": []},
            "bootstrap": {"scope": "P6.05-L4", "owner_authorization_asserted": True},
        }
        context.write_text(json.dumps(payload), encoding="utf-8")
        if os.name != "nt":
            context.chmod(0o600)
        continuity_root = Path(self.tmp.name) / "continuity"
        first = p704.bootstrap_from_p6_owner_context(continuity_root, context)
        second = p704.bootstrap_from_p6_owner_context(continuity_root, context)
        self.assertEqual(first["human_operator"]["value"], "p6-owner")
        self.assertEqual(first["organization"]["value"], "p6-org")
        self.assertTrue(first["service_created"])
        self.assertFalse(second["service_created"])
        self.assertEqual(first["service_identity"], second["service_identity"])
        self.assertEqual(first["credentials_issued"], 0)
        self.assertEqual(first["grants_issued"], 0)

    def test_explicit_service_selection_preserves_other_principals(self):
        from unittest.mock import patch
        collector = Identity("principal", "collector", self.org.value)
        ck = p704.register_principal(self.root, collector, kind="service")
        sk = p704._principal_key(self.service)
        cid = p704.issue_credential(self.root, collector)["credential_id"]
        p704.grant_access(self.root, collector, operation="workspace.inbox.collect", resource="roadmap-inbox")
        before = p704.load_access_store(self.root)
        with patch.object(p704, "load_p6_owner_context", return_value=(self.org,self.human)):
            with self.assertRaises(p704.IntegrityError):
                p704.bootstrap_from_p6_owner_context(self.root, Path("unused"))
            for bad in (p704._principal_key(self.human),"0"*64,"invalid"):
                with self.assertRaises(p704.P704Error):
                    p704.bootstrap_from_p6_owner_context(self.root, Path("unused"),service_principal_key=bad)
            exact=p704.bootstrap_from_p6_owner_context(self.root, Path("unused"),service_principal_key=sk)
            self.assertEqual(exact["service_identity"]["value"],self.service.value)
            self.assertFalse(exact["service_created"])
            self.assertEqual(exact["credentials_issued"],0)
            self.assertEqual(exact["grants_issued"],0)
            self.assertEqual(p704.load_access_store(self.root),before)
            p704.disable_principal(self.root,collector)
            with self.assertRaises(p704.IntegrityError):
                p704.bootstrap_from_p6_owner_context(self.root, Path("unused"),service_principal_key=ck)

    def test_p6_context_with_authority_claim_is_rejected(self):
        p6_root = Path(self.tmp.name) / "bad-p6"
        p6_root.mkdir(mode=0o700)
        context = p6_root / "organization-operator.json"
        payload = {
            "schema_version": "p6.05-l4-local-context-1",
            "organization": {
                "identity": {"namespace": "organization", "value": "p6-org", "scope": "platform"},
                "context_label": "ООО «Арвектум»",
            },
            "operator": {
                "identity": {"namespace": "principal", "value": "p6-owner", "scope": "p6-org"},
                "principal_category": "human", "operating_mode": "owner-operated",
            },
            "authority": {
                "authorization_grants": ["bad"], "delegations": [], "organizational_authority_claimed": True,
            },
            "authentication": {"evidence_refs": []},
            "bootstrap": {"scope": "P6.05-L4", "owner_authorization_asserted": True},
        }
        context.write_text(json.dumps(payload), encoding="utf-8")
        if os.name != "nt":
            context.chmod(0o600)
        with self.assertRaises(p704.IntegrityError):
            p704.bootstrap_from_p6_owner_context(Path(self.tmp.name) / "bad-continuity", context)

    def test_default_deny_after_successful_authentication_without_grant(self):
        issued, secret = self.issue(self.human)
        decision = p704.authorize(
            self.root, organization=self.org, principal=self.human,
            credential_id=issued["credential_id"], credential_secret=secret,
            operation="runtime.inspect", resource="runtime:p7-02", access_path="local",
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "NO_EXPLICIT_GRANT")
        self.assertFalse(decision.organizational_authority_satisfied)

    def test_exact_operation_resource_organization_scope_allows_only_exact_match(self):
        issued, secret = self.issue(self.human)
        p704.grant_access(
            self.root, self.human, operation="runtime.inspect", resource="runtime:p7-02",
            access_paths=("local",),
        )
        allowed = p704.authorize(
            self.root, organization=self.org, principal=self.human,
            credential_id=issued["credential_id"], credential_secret=secret,
            operation="runtime.inspect", resource="runtime:p7-02", access_path="local",
        )
        self.assertTrue(allowed.allowed)
        self.assertEqual(allowed.principal_kind, "human")
        wrong_operation = p704.authorize(
            self.root, organization=self.org, principal=self.human,
            credential_id=issued["credential_id"], credential_secret=secret,
            operation="runtime.restart", resource="runtime:p7-02", access_path="local",
        )
        wrong_resource = p704.authorize(
            self.root, organization=self.org, principal=self.human,
            credential_id=issued["credential_id"], credential_secret=secret,
            operation="runtime.inspect", resource="runtime:p7-03", access_path="local",
        )
        other_org = Identity("organization", "other-org", "platform")
        wrong_org = p704.authorize(
            self.root, organization=other_org, principal=self.human,
            credential_id=issued["credential_id"], credential_secret=secret,
            operation="runtime.inspect", resource="runtime:p7-02", access_path="local",
        )
        self.assertEqual(
            (wrong_operation.reason, wrong_resource.reason, wrong_org.reason),
            ("NO_EXPLICIT_GRANT", "NO_EXPLICIT_GRANT", "ORGANIZATION_SCOPE_MISMATCH"),
        )

    def test_wildcard_ambient_admin_grants_are_impossible(self):
        with self.assertRaises(p704.BoundaryError):
            p704.grant_access(self.root, self.human, operation="*", resource="runtime:p7-02")
        with self.assertRaises(p704.BoundaryError):
            p704.grant_access(self.root, self.human, operation="runtime.inspect", resource="*")
        state = p704.load_access_store(self.root)
        self.assertFalse(state["ambient_admin"])
        self.assertNotIn("roles", state)

    def test_service_identity_is_attributable_and_has_no_admin_inheritance(self):
        issued, secret = self.issue(self.service)
        p704.grant_access(
            self.root, self.service, operation="runtime.heartbeat", resource="runtime:p7-02",
            access_paths=("local",),
        )
        allowed = p704.authorize(
            self.root, organization=self.org, principal=self.service,
            credential_id=issued["credential_id"], credential_secret=secret,
            operation="runtime.heartbeat", resource="runtime:p7-02", access_path="local",
        )
        denied = p704.authorize(
            self.root, organization=self.org, principal=self.service,
            credential_id=issued["credential_id"], credential_secret=secret,
            operation="runtime.restart", resource="runtime:p7-02", access_path="local",
        )
        self.assertTrue(allowed.allowed)
        self.assertEqual(allowed.principal_kind, "service")
        self.assertFalse(denied.allowed)

    def test_rotation_revokes_old_secret_and_new_credential_works(self):
        first, first_secret = self.issue(self.human)
        p704.grant_access(self.root, self.human, operation="runtime.inspect", resource="runtime:p7-02")
        rotated = p704.rotate_credential(self.root, self.human, first["credential_id"])
        second_secret = p704.read_credential_secret(Path(rotated["secret_path"]))
        self.assertFalse(Path(first["secret_path"]).exists())
        old = p704.authorize(
            self.root, organization=self.org, principal=self.human,
            credential_id=first["credential_id"], credential_secret=first_secret,
            operation="runtime.inspect", resource="runtime:p7-02", access_path="local",
        )
        new = p704.authorize(
            self.root, organization=self.org, principal=self.human,
            credential_id=rotated["credential_id"], credential_secret=second_secret,
            operation="runtime.inspect", resource="runtime:p7-02", access_path="local",
        )
        self.assertEqual(old.reason, "CREDENTIAL_REVOKED")
        self.assertTrue(new.allowed)
        self.assertEqual(rotated["generation"], 2)

    def test_credential_and_principal_revocation_fail_closed(self):
        issued, secret = self.issue(self.human)
        p704.grant_access(self.root, self.human, operation="runtime.inspect", resource="runtime:p7-02")
        p704.revoke_credential(self.root, issued["credential_id"])
        self.assertFalse(Path(issued["secret_path"]).exists())
        denied = p704.authorize(
            self.root, organization=self.org, principal=self.human,
            credential_id=issued["credential_id"], credential_secret=secret,
            operation="runtime.inspect", resource="runtime:p7-02", access_path="local",
        )
        self.assertEqual(denied.reason, "CREDENTIAL_REVOKED")
        replacement = p704.issue_credential(self.root, self.human)
        replacement_secret = p704.read_credential_secret(Path(replacement["secret_path"]))
        p704.disable_principal(self.root, self.human)
        disabled = p704.authorize(
            self.root, organization=self.org, principal=self.human,
            credential_id=replacement["credential_id"], credential_secret=replacement_secret,
            operation="runtime.inspect", resource="runtime:p7-02", access_path="local",
        )
        self.assertEqual(disabled.reason, "PRINCIPAL_DISABLED")
        self.assertFalse(Path(replacement["secret_path"]).exists())

    def test_grant_revocation_is_immediate(self):
        issued, secret = self.issue(self.human)
        grant = p704.grant_access(self.root, self.human, operation="runtime.inspect", resource="runtime:p7-02")
        p704.revoke_grant(self.root, grant)
        denied = p704.authorize(
            self.root, organization=self.org, principal=self.human,
            credential_id=issued["credential_id"], credential_secret=secret,
            operation="runtime.inspect", resource="runtime:p7-02", access_path="local",
        )
        self.assertEqual(denied.reason, "NO_EXPLICIT_GRANT")

    def test_remote_administration_requires_explicit_remote_path(self):
        issued, secret = self.issue(self.human)
        p704.grant_access(
            self.root, self.human, operation="runtime.restart", resource="runtime:p7-02",
            access_paths=("local",),
        )
        remote_denied = p704.authorize(
            self.root, organization=self.org, principal=self.human,
            credential_id=issued["credential_id"], credential_secret=secret,
            operation="runtime.restart", resource="runtime:p7-02", access_path="remote",
        )
        self.assertEqual(remote_denied.reason, "NO_EXPLICIT_GRANT")
        p704.grant_access(
            self.root, self.human, operation="runtime.restart", resource="runtime:p7-02",
            access_paths=("remote",),
        )
        remote_allowed = p704.authorize(
            self.root, organization=self.org, principal=self.human,
            credential_id=issued["credential_id"], credential_secret=secret,
            operation="runtime.restart", resource="runtime:p7-02", access_path="remote",
        )
        self.assertTrue(remote_allowed.allowed)
        self.assertFalse(remote_allowed.organizational_authority_satisfied)
        self.assertFalse(remote_allowed.consequential_approval_satisfied)

    def test_operational_access_never_satisfies_consequential_approval(self):
        issued, secret = self.issue(self.human)
        p704.grant_access(
            self.root, self.human, operation="governed-execution.submit", resource="execution:demo",
            access_paths=("local",),
        )
        decision = p704.authorize(
            self.root, organization=self.org, principal=self.human,
            credential_id=issued["credential_id"], credential_secret=secret,
            operation="governed-execution.submit", resource="execution:demo", access_path="local",
        )
        self.assertTrue(decision.allowed)
        self.assertTrue(decision.operational_access_only)
        self.assertFalse(decision.organizational_authority_satisfied)
        self.assertFalse(decision.consequential_approval_satisfied)

    def test_secret_is_separate_from_registry_and_owner_only(self):
        issued, secret = self.issue(self.human)
        registry = (self.root / "config" / "p7-04-access.json").read_text(encoding="utf-8")
        self.assertNotIn(secret, registry)
        self.assertIn('"verifier"', registry)
        if os.name != "nt":
            self.assertEqual(Path(issued["secret_path"]).stat().st_mode & 0o777, 0o600)
            self.assertEqual((self.root / "config" / "p7-04-access.json").stat().st_mode & 0o777, 0o600)

    def test_orphaned_secret_plaintext_is_detected_fail_closed(self):
        orphan = self.root / "secrets" / "p7-04" / "orphan.secret"
        orphan.write_text("unbound-reusable-secret\n", encoding="utf-8")
        if os.name != "nt":
            orphan.chmod(0o600)
        with self.assertRaises(p704.IntegrityError) as ctx:
            p704.verify_store(self.root)
        self.assertIn("orphan or unrecognized credential plaintext", str(ctx.exception))

    def test_tampered_policy_claiming_ambient_admin_fails_closed(self):
        path = self.root / "config" / "p7-04-access.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["ambient_admin"] = True
        path.write_text(json.dumps(state), encoding="utf-8")
        if os.name != "nt":
            path.chmod(0o600)
        with self.assertRaises(p704.IntegrityError):
            p704.load_access_store(self.root)


if __name__ == "__main__":
    unittest.main()
