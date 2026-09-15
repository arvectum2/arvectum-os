from __future__ import annotations

import base64
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import p7_04_persistent_access as p704
from arvectum_os_ref.governed_execution import GovernedGateKind, GovernedGateOutcome
from arvectum_os_ref.identity import Identity
from p10_05_company_output_ref.contract import OP_PROMOTE_REVIEWED_OUTPUT
from workspace_app.access import P704AccessResolver, provision_workspace_grant
from workspace_app.company_asset_governed_provider import (
    P1004OwnerCompanyAssetAdmissionProvider,
    provision_company_asset_admission_grant,
)
from workspace_app.company_asset_library import (
    CompanyAssetAdmissionUnavailable,
    CompanyAssetLibrary,
    P1003CompanyAssetAdmissionExecutor,
)
from workspace_app.company_generated_output_governed_provider import (
    COMPANY_GENERATED_OUTPUT_PROMOTION_RESOURCE,
    P1005OwnerCompanyGeneratedOutputPromotionProvider,
    provision_company_generated_output_promotion_grant,
)
from workspace_app.company_generated_outputs import (
    CompanyGeneratedOutputs,
    P1005CompanyGeneratedOutputPromotionExecutor,
)
from workspace_app.company_materials import CompanyMaterialsStore


DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def docx_template() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>{{TITLE}} {{BODY}} {{DATE}}</w:t></w:r></w:p></w:body></w:document>",
        )
    return buffer.getvalue()


class CompanyGeneratedOutputPromotionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.organization = Identity("organization", "p10-05-org", "platform")
        self.owner = Identity("principal", "p10-05-owner", self.organization.value)
        p704.initialize_access_store(self.root, self.organization)
        p704.register_principal(self.root, self.owner, kind="human")
        p704.issue_credential(self.root, self.owner)
        provision_workspace_grant(self.root)
        self.access = P704AccessResolver(self.root).authorize()

        self.materials = CompanyMaterialsStore(self.root)
        self.asset_provider = P1004OwnerCompanyAssetAdmissionProvider(self.root)
        self.asset_executor = P1003CompanyAssetAdmissionExecutor(self.asset_provider)
        self.assets = CompanyAssetLibrary(self.materials, self.asset_executor)
        provision_company_asset_admission_grant(self.root)

        staged = self.materials.stage(
            self.access,
            {
                "project_id": "COMPANY",
                "filename": "company-template.docx",
                "media_type": DOCX_MEDIA_TYPE,
                "semantic_role": "document-template",
                "classification": "internal",
                "purpose": "company governed document generation",
                "rights": "company-internal-use",
                "retention_rule": "retain-while-current-plus-governed-history",
                "content_base64": base64.b64encode(docx_template()).decode("ascii"),
            },
        )["material"]
        self.material_id = str(staged["material_id"])
        self.version_id = str(staged["version_id"])
        self.assets.submit_review(
            self.access,
            self.material_id,
            self.version_id,
            {
                "deletion_rule": "delete-only-through-governed-retention-process",
                "permitted_reuse": ["company-internal-document-generation"],
            },
        )
        self.assets.admit(self.access, self.material_id, self.version_id)
        generated = self.assets.generate_docx(
            self.access,
            {
                "material_id": self.material_id,
                "version_id": self.version_id,
                "title": "Reviewed Company Document",
                "body": "Bounded real-work text",
                "date": "2026-08-29",
            },
        )
        self.output_id = str(generated["output"]["output_id"])

        self.promotion_provider = P1005OwnerCompanyGeneratedOutputPromotionProvider(self.root)
        self.promotion_executor = P1005CompanyGeneratedOutputPromotionExecutor(
            self.promotion_provider, self.asset_executor
        )
        self.outputs = CompanyGeneratedOutputs(
            self.root,
            self.materials,
            self.asset_executor,
            self.promotion_executor,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def request_promotion(self) -> dict[str, object]:
        return self.outputs.review(
            self.access,
            self.output_id,
            {
                "disposition": "PromotionRequested",
                "document_title": "Reviewed Company Document",
                "semantic_role": "company-project-document",
            },
        )

    def test_promotion_grant_is_distinct_never_ambient_and_revocable(self) -> None:
        self.assertFalse(self.promotion_provider.available(self.access))
        state = p704.load_access_store(self.root)
        self.assertEqual(
            [grant for grant in state["grants"].values() if grant["operation"] == OP_PROMOTE_REVIEWED_OUTPUT],
            [],
        )

        grant_id = provision_company_generated_output_promotion_grant(self.root)
        state = p704.load_access_store(self.root)
        grant = state["grants"][grant_id]
        self.assertEqual(grant["operation"], OP_PROMOTE_REVIEWED_OUTPUT)
        self.assertEqual(grant["resource"], COMPANY_GENERATED_OUTPUT_PROMOTION_RESOURCE)
        self.assertEqual(grant["access_paths"], ["local"])
        self.assertFalse(state["organizational_authority_provided"])
        self.assertTrue(self.promotion_provider.available(self.access))

        p704.revoke_grant(self.root, grant_id)
        self.assertFalse(self.promotion_provider.available(self.access))

    def test_reject_keep_and_request_review_never_relabel_transient_or_write_canonical(self) -> None:
        rejected = self.outputs.review(
            self.access,
            self.output_id,
            {"disposition": "Rejected", "reason": "needs revision"},
        )
        self.assertEqual(rejected["disposition"], "Rejected")
        self.assertFalse(rejected["canonical_authority"])
        self.assertEqual(len(self.promotion_executor.state.committed), 0)

        kept = self.outputs.review(self.access, self.output_id, {"disposition": "KeepTransient"})
        self.assertEqual(kept["disposition"], "KeepTransient")
        self.assertEqual(len(self.promotion_executor.state.committed), 0)

        requested = self.request_promotion()
        self.assertEqual(requested["disposition"], "PromotionRequested")
        self.assertEqual(requested["source_state"], "TransientOutput")
        path, manifest = self.materials.output_path(self.access, self.output_id)
        self.assertTrue(path.is_file())
        self.assertEqual(manifest["state"], "TransientOutput")
        self.assertFalse(manifest["canonical_authority"])
        self.assertEqual(len(self.promotion_executor.state.committed), 0)

    def test_prepare_has_six_independent_gates_and_exact_source_handling(self) -> None:
        review = self.request_promotion()
        provision_company_generated_output_promotion_grant(self.root)
        evidence = self.outputs._promotion_evidence(self.access, self.output_id)
        from workspace_app.company_generated_output_promotion import (
            build_generated_output_document_candidate,
            resolve_exact_generated_output,
        )

        output = resolve_exact_generated_output(
            store=self.materials,
            asset_admission=self.asset_executor,
            access=self.access,
            output_id=self.output_id,
        )
        actor = self.promotion_provider.actor_for(self.access)
        from datetime import datetime, timezone

        candidate = build_generated_output_document_candidate(
            output=output,
            access=self.access,
            actor=actor,
            candidate_created_at=datetime.now(timezone.utc),
            document_title=str(review["document_title"]),
            semantic_role=str(review["semantic_role"]),
        )
        prepared = self.promotion_provider.prepare(
            access=self.access,
            candidate=candidate,
            output=output,
            review=evidence,
        )
        decisions = {item.kind: item for item in prepared.execution.gate_decisions}
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
        self.assertNotEqual(
            decisions[GovernedGateKind.AUTHORIZATION].basis_ref,
            decisions[GovernedGateKind.ORGANIZATIONAL_AUTHORITY].basis_ref,
        )
        self.assertEqual(prepared.execution.product_contract.lifecycle_status, "Provisional")
        self.assertEqual(prepared.execution.operation_name, OP_PROMOTE_REVIEWED_OUTPUT)
        self.assertEqual(len(prepared.execution.material_inputs), 2)
        self.assertEqual(review["handling"], {
            "classification": "internal",
            "purpose": "company governed document generation",
            "rights": ["company-internal-use"],
            "retention_rule": "retain-while-current-plus-governed-history",
            "deletion_rule": "delete-only-through-governed-retention-process",
            "permitted_reuse": ["company-internal-document-generation"],
        })

    def test_governed_promotion_is_idempotent_and_source_remains_transient(self) -> None:
        self.request_promotion()
        provision_company_generated_output_promotion_grant(self.root)

        first = self.outputs.promote(self.access, self.output_id)
        second = self.outputs.promote(self.access, self.output_id)

        self.assertEqual(first, second)
        self.assertEqual(len(self.promotion_executor.state.committed), 1)
        self.assertEqual(len(self.promotion_executor.state.admitted_events), 1)
        self.assertEqual(len(self.promotion_executor.state.attempts), 1)
        committed = self.promotion_executor.state.committed[0]
        self.assertEqual(committed.admitted_document.artifacts[0].state.value, "Governed")
        self.assertIn(
            self.asset_executor.state.committed[0].admitted_document.version_id,
            committed.admitted_document.canonical_record.provenance_refs,
        )
        self.assertFalse(dict(committed.admitted_document.canonical_record.payload).get("validated_knowledge", False))

        _, manifest = self.materials.output_path(self.access, self.output_id)
        self.assertEqual(manifest["state"], "TransientOutput")
        self.assertFalse(manifest["canonical_authority"])
        projection = self.outputs.project(self.access)
        item = next(value for value in projection["items"] if value["output_id"] == self.output_id)
        self.assertIsNotNone(item["canonical_promotion"])
        self.assertEqual(item["state"], "TransientOutput")
        self.assertFalse(projection["governance"]["promotion_relabels_transient_source"])
        self.assertFalse(projection["governance"]["validated_knowledge_created"])
        self.assertFalse(projection["governance"]["external_send_sign_publish_available"])

    def test_asset_aware_promotion_preserves_every_exact_admitted_input(self) -> None:
        staged = self.materials.stage(
            self.access,
            {
                "project_id": "COMPANY",
                "filename": "approved-source.txt",
                "media_type": "text/plain",
                "semantic_role": "source",
                "classification": "internal",
                "purpose": "company governed document generation",
                "rights": "company-internal-use",
                "retention_rule": "retain-while-current-plus-governed-history",
                "content_base64": base64.b64encode(b"Approved exact source text").decode("ascii"),
            },
        )["material"]
        self.assets.submit_review(
            self.access,
            staged["material_id"],
            staged["version_id"],
            {
                "deletion_rule": "delete-only-through-governed-retention-process",
                "permitted_reuse": ["company-internal-document-generation"],
            },
        )
        self.assets.admit(self.access, staged["material_id"], staged["version_id"])
        input_admission = self.asset_executor.state.committed[-1]
        input_artifact = input_admission.admitted_document.artifacts[0]

        generated = self.assets.generate_docx(
            self.access,
            {
                "material_id": self.material_id,
                "version_id": self.version_id,
                "asset_inputs": [
                    {
                        "material_id": staged["material_id"],
                        "version_id": staged["version_id"],
                        "use_as": "source",
                    }
                ],
                "title": "Asset-aware reviewed document",
                "body": "Body",
                "date": "2026-09-15",
            },
        )
        output_id = str(generated["output"]["output_id"])
        self.outputs.review(
            self.access,
            output_id,
            {
                "disposition": "PromotionRequested",
                "document_title": "Asset-aware reviewed document",
                "semantic_role": "company-project-document",
            },
        )
        provision_company_generated_output_promotion_grant(self.root)
        self.outputs.promote(self.access, output_id)

        committed = self.promotion_executor.state.committed[0]
        record = committed.admitted_document.canonical_record
        artifact = committed.admitted_document.artifacts[0]
        self.assertIn(input_admission.admitted_document.version_id, record.provenance_refs)
        self.assertIn(input_admission.designation.version_id, record.provenance_refs)
        self.assertIn(input_artifact.artifact_id, artifact.source_artifact_ids)
        _, manifest = self.materials.output_path(self.access, output_id)
        self.assertEqual(manifest["state"], "TransientOutput")
        self.assertEqual(manifest["input_assets"][0]["application"], "text-included")
        self.assertEqual(len(manifest["generation_input_digest"]), 64)

    def test_asset_aware_review_rejects_tampered_input_application_evidence(self) -> None:
        staged = self.materials.stage(
            self.access,
            {
                "project_id": "COMPANY",
                "filename": "approved-source.txt",
                "media_type": "text/plain",
                "semantic_role": "source",
                "classification": "internal",
                "purpose": "company governed document generation",
                "rights": "company-internal-use",
                "retention_rule": "retain-while-current-plus-governed-history",
                "content_base64": base64.b64encode(b"Approved exact source text").decode("ascii"),
            },
        )["material"]
        self.assets.submit_review(
            self.access, staged["material_id"], staged["version_id"],
            {
                "deletion_rule": "delete-only-through-governed-retention-process",
                "permitted_reuse": ["company-internal-document-generation"],
            },
        )
        self.assets.admit(self.access, staged["material_id"], staged["version_id"])
        generated = self.assets.generate_docx(
            self.access,
            {
                "material_id": self.material_id,
                "version_id": self.version_id,
                "asset_inputs": [{"material_id": staged["material_id"], "version_id": staged["version_id"], "use_as": "source"}],
                "title": "Tamper check",
                "body": "Body",
                "date": "2026-09-15",
            },
        )
        output_id = str(generated["output"]["output_id"])
        manifest_path = self.materials.transient / f"{output_id}.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["input_assets"][0]["application"] = "pinned-reference"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

        with self.assertRaisesRegex(CompanyAssetAdmissionUnavailable, "application evidence"):
            self.outputs.review(
                self.access, output_id,
                {
                    "disposition": "PromotionRequested",
                    "document_title": "Tamper check",
                    "semantic_role": "company-project-document",
                },
            )
        self.assertEqual(len(self.promotion_executor.state.committed), 0)

    def test_promotion_fails_closed_without_exact_admitted_source(self) -> None:
        self.request_promotion()
        provision_company_generated_output_promotion_grant(self.root)
        self.asset_executor.state = type(self.asset_executor.state)()
        with self.assertRaises(CompanyAssetAdmissionUnavailable):
            self.outputs.promote(self.access, self.output_id)
        self.assertEqual(len(self.promotion_executor.state.committed), 0)


if __name__ == "__main__":
    unittest.main()
