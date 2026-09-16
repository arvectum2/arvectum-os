from __future__ import annotations

import base64
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from arvectum_os_ref.identity import Identity
from workspace_app.access import AccessContext
from workspace_app.company_asset_copilot import (
    AI_GROUNDING_REUSE,
    CompanyAssetCopilotContractGate,
    CompanyAssetCopilotEvidenceSource,
    P10_09_C_OPERATION,
)
from workspace_app.company_asset_library import AdmittedCompanyAssetVersion, CompanyAssetLibrary, CompanyAssetReviewPolicy
from workspace_app.company_asset_retrieval import CompanyAssetRetrieval
from workspace_app.company_materials import CompanyMaterialsStore
from workspace_app.copilot import CopilotEvidence, ModelDescriptor, RuntimeCopilotProvider
from workspace_app.discovery import DiscoveryFreshness, DiscoveryHealth, DiscoveryProjection
from workspace_app.products import ProductCompositionProjection


class RecordingAdmission:
    def __init__(self) -> None:
        self.items: list[AdmittedCompanyAssetVersion] = []
        self.reuse_by_version: dict[str, tuple[str, ...]] = {}

    def available(self, access: AccessContext) -> bool:
        return True

    def admitted_versions(self, access: AccessContext) -> tuple[AdmittedCompanyAssetVersion, ...]:
        return tuple(self.items)

    def admit(self, *, access, store, material_id, version_id, policy: CompanyAssetReviewPolicy):
        self.items = [replace(item, current=False) if item.material_id == material_id and item.current else item for item in self.items]
        admitted = AdmittedCompanyAssetVersion(
            material_id=material_id,
            version_id=version_id,
            document_subject=f"document:{material_id}",
            document_version=f"document-version:{version_id}",
            designation_subject=f"asset:{material_id}",
            designation_version=f"asset-version:{version_id}",
            event_version=f"event-version:{version_id}",
            admitted_at=datetime.now(timezone.utc).isoformat(),
            provenance_refs=(f"source:{material_id}", f"version:{version_id}"),
            current=True,
        )
        self.items.append(admitted)
        self.reuse_by_version[version_id] = policy.permitted_reuse
        return admitted


class FakeCanonicalHandling:
    def __init__(self, admission: RecordingAdmission) -> None:
        self.admission = admission

    def permitted_reuse(self, access, material_id: str, version_id: str) -> tuple[str, ...]:
        return self.admission.reuse_by_version.get(version_id, ())


class EmptyDiscovery:
    def search(self, access, *, query="", kind=None):
        return DiscoveryProjection(
            generated_at="2026-09-16T00:00:00Z",
            query=query,
            kind_filter=kind,
            health=DiscoveryHealth(DiscoveryFreshness.FRESH, "OK", "Current.", "2026-09-16T00:00:00Z"),
            results=(),
        )


class EmptyProducts:
    def project(self, access):
        return ProductCompositionProjection(())


class RecordingModel:
    descriptor = ModelDescriptor("test-loopback", "test")

    def synthesize(self, question: str, evidence: tuple[CopilotEvidence, ...]) -> str:
        self.evidence = evidence
        return "Bounded synthesis."


class P1009CCompanyAssetCopilotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = CompanyMaterialsStore(self.root)
        self.admission = RecordingAdmission()
        self.library = CompanyAssetLibrary(self.store, self.admission)
        self.retrieval = CompanyAssetRetrieval(self.library, self.store)
        self.access = AccessContext(
            organization=Identity("organization", "org-p1009c", "platform"),
            actor=Identity("principal", "owner-p1009c", "org-p1009c"),
            principal_kind="human",
            credential_id="credential-p1009c",
            grant_id="grant-p1009c",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def stage(self, name: str, content: bytes, *, role="source", media_type="text/markdown", material_id=None):
        payload = {
            "project_id": "COMPANY",
            "filename": name,
            "media_type": media_type,
            "semantic_role": role,
            "classification": "internal",
            "purpose": "bounded company research and assistance",
            "rights": "company-internal-use",
            "retention_rule": "retain-while-current-plus-history",
            "content_base64": base64.b64encode(content).decode("ascii"),
        }
        if material_id:
            payload["material_id"] = material_id
        return self.store.stage(self.access, payload)["material"]

    def admit(self, item, *, ai=True):
        reuse = [AI_GROUNDING_REUSE] if ai else ["company-internal-document-generation"]
        self.library.submit_review(
            self.access, item["material_id"], item["version_id"],
            {"deletion_rule": "governed-deletion", "permitted_reuse": reuse},
        )
        self.library.admit(self.access, item["material_id"], item["version_id"])
        return item

    @staticmethod
    def gate(lifecycle="Provisional"):
        return CompanyAssetCopilotContractGate("0.3.0", lifecycle, P10_09_C_OPERATION)

    def source(self, gate=None):
        return CompanyAssetCopilotEvidenceSource(
            self.library, self.retrieval, FakeCanonicalHandling(self.admission), gate or self.gate()
        )

    def test_contract_gate_fails_closed_before_provisional_publication(self) -> None:
        item = self.admit(self.stage("research.md", b"Approved company market research."))
        evidence, limitations = self.source(self.gate("Draft")).evidence(self.access, "market research")
        self.assertEqual(evidence, ())
        self.assertTrue(any("Product Contract 0.3.0" in value for value in limitations))
        self.assertTrue(item["material_id"].startswith("MAT-"))

    def test_exact_current_permitted_text_reaches_model_context_without_browser_raw_leak(self) -> None:
        secret_text = "Approved company research: Project Aurora budget assumption is bounded."
        item = self.admit(self.stage("aurora-research.md", secret_text.encode()))
        model = RecordingModel()
        answer = RuntimeCopilotProvider(
            EmptyDiscovery(), EmptyProducts(), model=model, supplemental_sources=(self.source(),)
        ).answer(self.access, "What is the Aurora budget assumption?")
        payload = answer.to_payload()
        company = [source for source in answer.sources if source.source_id.startswith("company-asset:")]
        self.assertEqual(len(company), 1)
        self.assertEqual(company[0].model_context, secret_text)
        self.assertEqual(model.evidence[0].model_context, secret_text)
        rendered = str(payload)
        self.assertNotIn(secret_text, rendered)
        self.assertNotIn(item["material_id"], rendered)
        self.assertNotIn(item["version_id"], rendered)
        self.assertEqual(payload["follow_up"]["href"], "/company-materials")
        self.assertFalse(payload["generation"]["validated_knowledge"])
        self.assertFalse(payload["generation"]["canonical_state_changed"])

    def test_noncanonical_review_change_cannot_grant_ai_reuse(self) -> None:
        denied = self.admit(self.stage("review-only.md", b"Review state must not grant AI rights."), ai=False)
        manifest_path = self.store._manifest_path(denied["material_id"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["p10_04_review_states"][denied["version_id"]]["policy"]["permitted_reuse"] = [AI_GROUNDING_REUSE]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        projected = self.library.project(self.access)
        current = next(item for item in projected["views"]["accepted"] if item["version_id"] == denied["version_id"])
        self.assertIn(AI_GROUNDING_REUSE, current["review"]["policy"]["permitted_reuse"])
        evidence, _ = self.source().evidence(self.access, "review state AI rights")
        self.assertEqual(evidence, ())

    def test_missing_ai_reuse_and_superseded_versions_are_not_grounding_sources(self) -> None:
        denied = self.admit(self.stage("denied.md", b"Denied AI reuse content."), ai=False)
        first = self.admit(self.stage("history.md", b"Old approved grounding content."))
        self.admit(self.stage("history-v2.md", b"Current approved grounding content.", material_id=first["material_id"]))
        evidence, _ = self.source().evidence(self.access, "denied history approved grounding content")
        contexts = [item.model_context for item in evidence]
        self.assertNotIn("Denied AI reuse content.", contexts)
        self.assertNotIn("Old approved grounding content.", contexts)
        self.assertIn("Current approved grounding content.", contexts)
        self.assertTrue(denied["material_id"].startswith("MAT-"))

    def test_non_text_asset_is_metadata_only_and_not_binary_model_context(self) -> None:
        logo = self.admit(self.stage("company-logo.png", b"\x89PNG\r\n\x1a\nlogo", role="logo", media_type="image/png"))
        evidence, limitations = self.source().evidence(self.access, "company logo")
        self.assertEqual(limitations, ())
        self.assertEqual(len(evidence), 1)
        self.assertIsNone(evidence[0].model_context)
        self.assertIn("not interpreted", evidence[0].summary)
        self.assertNotIn(logo["material_id"], evidence[0].source_id)


if __name__ == "__main__":
    unittest.main()
