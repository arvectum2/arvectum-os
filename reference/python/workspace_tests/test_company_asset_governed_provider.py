from __future__ import annotations

import base64
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import p7_04_persistent_access as p704
from arvectum_os_ref.governed_execution import GovernedGateKind, GovernedGateOutcome
from arvectum_os_ref.identity import Identity
from p10_03_company_asset_ref.contract import OP_ADMIT_STAGED_VERSION
from p9_03_workspace import build_workspace_app
from workspace_app.access import P704AccessResolver, provision_workspace_grant
from workspace_app.company_asset_admission import (
    build_staged_document_candidate,
    resolve_exact_staged_material,
)
from workspace_app.company_asset_copilot import AI_GROUNDING_REUSE, P1003CompanyAssetCopilotHandlingResolver
from workspace_app.company_asset_governed_provider import (
    COMPANY_ASSET_ADMISSION_RESOURCE,
    P1004OwnerCompanyAssetAdmissionProvider,
    provision_company_asset_admission_grant,
)
from workspace_app.company_asset_library import (
    CompanyAssetAdmissionUnavailable,
    CompanyAssetLibrary,
    CompanyAssetReviewPolicy,
    P1003CompanyAssetAdmissionExecutor,
)
from workspace_app.company_materials import CompanyMaterialsStore
from workspace_app.config import WorkspaceSettings


class CompanyAssetGovernedProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.organization = Identity("organization", "p10-04-org", "platform")
        self.owner = Identity("principal", "p10-04-owner", self.organization.value)
        p704.initialize_access_store(self.root, self.organization)
        p704.register_principal(self.root, self.owner, kind="human")
        p704.issue_credential(self.root, self.owner)
        provision_workspace_grant(self.root)
        self.access = P704AccessResolver(self.root).authorize()
        self.provider = P1004OwnerCompanyAssetAdmissionProvider(self.root)
        self.executor = P1003CompanyAssetAdmissionExecutor(self.provider)
        self.store = CompanyMaterialsStore(self.root)
        self.library = CompanyAssetLibrary(self.store, self.executor)

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def review_payload() -> dict[str, object]:
        return {
            "deletion_rule": "delete-only-through-governed-retention-process",
            "permitted_reuse": ["company-internal-reference-use"],
        }

    def _stage(self, *, material_id: str | None = None, label: str = "v1") -> dict[str, object]:
        payload: dict[str, object] = {
            "project_id": "COMPANY",
            "filename": "company-standard.txt",
            "media_type": "text/plain",
            "semantic_role": "company-standard-source",
            "classification": "internal",
            "purpose": "governed-company-operational-use",
            "rights": "company-internal-use",
            "retention_rule": "retain-while-current-plus-governed-history",
            "content_base64": base64.b64encode(f"Arvectum standard {label}\n".encode()).decode(),
        }
        if material_id is not None:
            payload["material_id"] = material_id
        return self.store.stage(self.access, payload)["material"]

    def _settings(self) -> WorkspaceSettings:
        return WorkspaceSettings(
            runtime_root=self.root,
            public_origin="http://127.0.0.1:8769",
            bind_host="127.0.0.1",
            bind_port=8769,
            allowed_hosts=("127.0.0.1:8769",),
            organization_label="ООО «Арвектум»",
            actor_label="Owner operator",
            session_idle_seconds=1800,
            session_absolute_seconds=28800,
            allow_loopback_http=True,
        )

    def test_productive_workspace_installs_governed_executor_without_auto_grant(self) -> None:
        app = build_workspace_app(self._settings())
        admission = app.state.company_asset_library.admission
        self.assertIsInstance(admission, P1003CompanyAssetAdmissionExecutor)
        self.assertIsInstance(admission.provider, P1004OwnerCompanyAssetAdmissionProvider)
        self.assertFalse(admission.available(self.access))

        provision_company_asset_admission_grant(self.root)
        self.assertTrue(admission.available(self.access))

    def test_admission_grant_is_not_ambient_or_auto_provisioned(self) -> None:
        self.assertFalse(self.provider.available(self.access))
        state = p704.load_access_store(self.root)
        matching = [
            grant
            for grant in state["grants"].values()
            if grant["operation"] == OP_ADMIT_STAGED_VERSION
        ]
        self.assertEqual(matching, [])

        grant_id = provision_company_asset_admission_grant(self.root)
        self.assertTrue(self.provider.available(self.access))
        state = p704.load_access_store(self.root)
        grant = state["grants"][grant_id]
        self.assertEqual(grant["operation"], OP_ADMIT_STAGED_VERSION)
        self.assertEqual(grant["resource"], COMPANY_ASSET_ADMISSION_RESOURCE)
        self.assertEqual(grant["access_paths"], ["local"])
        self.assertFalse(state["organizational_authority_provided"])

        p704.revoke_grant(self.root, grant_id)
        self.assertFalse(self.provider.available(self.access))

    def test_prepare_builds_six_independent_ready_gates_from_exact_review(self) -> None:
        provision_company_asset_admission_grant(self.root)
        version = self._stage()
        material_id = str(version["material_id"])
        version_id = str(version["version_id"])
        policy = CompanyAssetReviewPolicy.from_payload(self.review_payload())
        self.library.submit_review(self.access, material_id, version_id, self.review_payload())
        review = self.executor._require_review_evidence(
            access=self.access,
            store=self.store,
            material_id=material_id,
            version_id=version_id,
            policy=policy,
        )
        staged = resolve_exact_staged_material(
            store=self.store,
            access=self.access,
            material_id=material_id,
            version_id=version_id,
        )
        actor = self.provider.actor_for(self.access)
        candidate = build_staged_document_candidate(
            staged=staged,
            access=self.access,
            actor=actor,
            candidate_created_at=datetime.now(timezone.utc),
        )
        prepared = self.provider.prepare(
            access=self.access,
            candidate=candidate,
            staged=staged,
            policy=policy,
            review=review,
        )
        decisions = {decision.kind: decision for decision in prepared.execution.gate_decisions}
        self.assertEqual(set(decisions), set(GovernedGateKind))
        self.assertTrue(all(item.outcome is GovernedGateOutcome.ALLOW for item in decisions.values()))
        self.assertEqual(
            decisions[GovernedGateKind.AUTHORIZATION].basis_ref.namespace,
            "authorization-grant",
        )
        self.assertEqual(
            decisions[GovernedGateKind.ORGANIZATIONAL_AUTHORITY].basis_ref.value,
            "p10-01-current-residual-owner-authority",
        )
        self.assertEqual(
            prepared.authority.organizational_authority_basis_ref,
            decisions[GovernedGateKind.ORGANIZATIONAL_AUTHORITY].basis_ref,
        )
        self.assertEqual(
            prepared.authority.consequential_approval_basis_ref,
            decisions[GovernedGateKind.CONSEQUENTIAL_APPROVAL].basis_ref,
        )
        self.assertEqual(prepared.execution.product_contract.lifecycle_status, "Provisional")
        self.assertEqual(prepared.execution.operation_name, OP_ADMIT_STAGED_VERSION)
        self.assertTrue(prepared.execution.gates_satisfied)

    def test_executor_refuses_direct_admission_without_current_review_evidence(self) -> None:
        provision_company_asset_admission_grant(self.root)
        version = self._stage()
        with self.assertRaises(CompanyAssetAdmissionUnavailable):
            self.executor.admit(
                access=self.access,
                store=self.store,
                material_id=str(version["material_id"]),
                version_id=str(version["version_id"]),
                policy=CompanyAssetReviewPolicy.from_payload(self.review_payload()),
            )
        self.assertEqual(len(self.executor.state.committed), 0)

    def test_copilot_handling_resolver_reads_canonical_designation_not_review_projection(self) -> None:
        provision_company_asset_admission_grant(self.root)
        version = self._stage()
        material_id = str(version["material_id"])
        version_id = str(version["version_id"])
        payload = {
            "deletion_rule": "delete-only-through-governed-retention-process",
            "permitted_reuse": [AI_GROUNDING_REUSE],
        }
        self.library.submit_review(self.access, material_id, version_id, payload)
        self.library.admit(self.access, material_id, version_id)
        resolver = P1003CompanyAssetCopilotHandlingResolver(self.executor)
        self.assertEqual(resolver.permitted_reuse(self.access, material_id, version_id), (AI_GROUNDING_REUSE,))

    def test_owner_admission_is_idempotent_and_uses_p10_03_guarded_state(self) -> None:
        provision_company_asset_admission_grant(self.root)
        version = self._stage()
        material_id = str(version["material_id"])
        version_id = str(version["version_id"])
        self.library.submit_review(self.access, material_id, version_id, self.review_payload())

        first = self.library.admit(self.access, material_id, version_id)
        second = self.library.admit(self.access, material_id, version_id)

        self.assertEqual(first, second)
        self.assertEqual(len(self.executor.state.committed), 1)
        self.assertEqual(len(self.executor.state.admitted_events), 1)
        self.assertEqual(len(self.executor.state.attempts), 1)
        projection = self.library.project(self.access)
        self.assertEqual(
            [item["version_id"] for item in projection["views"]["accepted"]],
            [version_id],
        )
        self.assertEqual(
            projection["views"]["accepted"][0]["staging_state"], "StagedNonCanonical"
        )
        self.assertTrue(projection["views"]["accepted"][0]["canonical"]["current"])


if __name__ == "__main__":
    unittest.main()
