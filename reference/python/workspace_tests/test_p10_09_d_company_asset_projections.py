from __future__ import annotations

import base64
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from arvectum_os_ref.identity import Identity
from workspace_app.access import AccessContext
from workspace_app.company_asset_library import (
    AdmittedCompanyAssetVersion,
    CompanyAssetLibrary,
    CompanyAssetReviewPolicy,
)
from workspace_app.company_asset_projections import (
    MAX_DERIVED_TEXT_BYTES,
    CompanyAssetDerivedProjectionService,
    CompanyAssetProjectionError,
)
from workspace_app.company_asset_retrieval import CompanyAssetContentUnavailable, CompanyAssetRetrieval
from workspace_app.company_materials import CompanyMaterialsStore


class RecordingAdmission:
    def __init__(self) -> None:
        self.items: list[AdmittedCompanyAssetVersion] = []

    def available(self, access: AccessContext) -> bool:
        return True

    def admitted_versions(self, access: AccessContext) -> tuple[AdmittedCompanyAssetVersion, ...]:
        return tuple(self.items)

    def admit(self, *, access, store, material_id, version_id, policy: CompanyAssetReviewPolicy):
        version = store._version(access, material_id, version_id)
        self.items = [
            replace(item, current=False) if item.material_id == material_id and item.current else item
            for item in self.items
        ]
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
        return admitted


class P1009DCompanyAssetProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = CompanyMaterialsStore(Path(self.temp.name))
        self.admission = RecordingAdmission()
        self.library = CompanyAssetLibrary(self.store, self.admission)
        self.retrieval = CompanyAssetRetrieval(self.library, self.store)
        self.service = CompanyAssetDerivedProjectionService(self.library, self.retrieval)
        self.access = AccessContext(
            organization=Identity("organization", "org-p1009d", "platform"),
            actor=Identity("principal", "owner-p1009d", "org-p1009d"),
            principal_kind="human",
            credential_id="credential-p1009d",
            grant_id="grant-p1009d",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def stage(self, name: str, content: bytes, *, media_type="text/markdown", material_id=None):
        payload = {
            "project_id": "COMPANY",
            "filename": name,
            "media_type": media_type,
            "semantic_role": "source",
            "classification": "internal",
            "purpose": "bounded company operations",
            "rights": "company-internal-use",
            "retention_rule": "retain-while-current-plus-history",
            "content_base64": base64.b64encode(content).decode("ascii"),
        }
        if material_id:
            payload["material_id"] = material_id
        return self.store.stage(self.access, payload)["material"]

    def admit(self, item):
        self.library.submit_review(
            self.access,
            item["material_id"],
            item["version_id"],
            {
                "deletion_rule": "governed-deletion",
                "permitted_reuse": ["company-internal-reference"],
            },
        )
        self.library.admit(self.access, item["material_id"], item["version_id"])
        return item

    def test_ready_projection_is_exact_rebuildable_non_authoritative_and_non_knowledge(self) -> None:
        item = self.admit(self.stage("operations.md", "Точный рабочий текст.\nSecond line.".encode("utf-8")))
        projection = self.service.text_projection(self.access, item["material_id"], item["version_id"])
        payload = projection.to_payload()
        self.assertEqual(projection.text, "Точный рабочий текст.\nSecond line.")
        self.assertEqual(projection.status, "ready")
        self.assertFalse(projection.canonical_authority)
        self.assertTrue(projection.rebuildable)
        self.assertEqual(projection.knowledge_status, "not-validated-knowledge")
        self.assertEqual(projection.content_sha256, item["content_sha256"])
        self.assertEqual(payload["schema"], "arvectum.workspace.company-asset-text-projection/1")
        self.assertTrue(str(projection.document_version).endswith(item["version_id"]))

    def test_opaque_media_is_explicitly_unsupported_without_interpreting_bytes(self) -> None:
        item = self.admit(self.stage("source.pdf", b"%PDF-opaque-secret", media_type="application/pdf"))
        projection = self.service.text_projection(self.access, item["material_id"], item["version_id"])
        self.assertEqual(projection.status, "unsupported")
        self.assertIsNone(projection.text)
        self.assertIn("application/pdf", projection.limitation or "")

    def test_invalid_utf8_and_oversized_text_fail_without_partial_or_replacement_text(self) -> None:
        invalid = self.admit(self.stage("invalid.txt", b"\xff\xfe", media_type="text/plain"))
        projection = self.service.text_projection(self.access, invalid["material_id"], invalid["version_id"])
        self.assertEqual(projection.status, "unsupported")
        self.assertIsNone(projection.text)
        self.assertIn("valid UTF-8", projection.limitation or "")

        large = self.admit(self.stage("large.md", b"x" * (MAX_DERIVED_TEXT_BYTES + 1)))
        projection = self.service.text_projection(self.access, large["material_id"], large["version_id"])
        self.assertEqual(projection.status, "unsupported")
        self.assertIsNone(projection.text)
        self.assertIn("no partial projection", projection.limitation or "")

    def test_superseded_version_is_not_projected_as_current_derived_source(self) -> None:
        first = self.admit(self.stage("history.md", b"old"))
        self.admit(self.stage("history-v2.md", b"current", material_id=first["material_id"]))
        with self.assertRaises(CompanyAssetContentUnavailable):
            self.service.text_projection(self.access, first["material_id"], first["version_id"])

    def test_cross_organization_access_and_integrity_mismatch_fail_closed(self) -> None:
        item = self.admit(self.stage("private.md", b"organization scoped"))
        other = AccessContext(
            organization=Identity("organization", "other-org", "platform"),
            actor=Identity("principal", "other-owner", "other-org"),
            principal_kind="human",
            credential_id="credential-other",
            grant_id="grant-other",
        )
        with self.assertRaises(CompanyAssetContentUnavailable):
            self.service.text_projection(other, item["material_id"], item["version_id"])

        blob = self.store.blobs / item["content_sha256"]
        blob.write_bytes(b"tampered")
        with self.assertRaises(CompanyAssetProjectionError):
            self.service.text_projection(self.access, item["material_id"], item["version_id"])


if __name__ == "__main__":
    unittest.main()
