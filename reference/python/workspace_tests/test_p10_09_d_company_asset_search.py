from __future__ import annotations

import base64
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from arvectum_os_ref.identity import Identity
from workspace_app.access import AccessContext
from workspace_app.company_asset_library import AdmittedCompanyAssetVersion, CompanyAssetLibrary, CompanyAssetReviewPolicy
from workspace_app.company_asset_projections import CompanyAssetDerivedProjectionService
from workspace_app.company_asset_retrieval import CompanyAssetRetrieval
from workspace_app.company_asset_search import CompanyAssetSearchError, CompanyAssetSearchService
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
        return admitted


class P1009DCompanyAssetSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = CompanyMaterialsStore(Path(self.temp.name))
        self.admission = RecordingAdmission()
        self.library = CompanyAssetLibrary(self.store, self.admission)
        retrieval = CompanyAssetRetrieval(self.library, self.store)
        projections = CompanyAssetDerivedProjectionService(self.library, retrieval)
        self.search = CompanyAssetSearchService(self.library, projections)
        self.access = AccessContext(
            organization=Identity("organization", "org-search", "platform"),
            actor=Identity("principal", "owner-search", "org-search"),
            principal_kind="human",
            credential_id="credential-search",
            grant_id="grant-search",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def admit(self, name: str, content: bytes, *, media_type="text/markdown"):
        material = self.store.stage(self.access, {
            "project_id": "COMPANY",
            "filename": name,
            "media_type": media_type,
            "semantic_role": "source",
            "classification": "internal",
            "purpose": "bounded company operations",
            "rights": "company-internal-use",
            "retention_rule": "retain-while-current-plus-history",
            "content_base64": base64.b64encode(content).decode("ascii"),
        })["material"]
        self.library.submit_review(self.access, material["material_id"], material["version_id"], {
            "deletion_rule": "governed-deletion",
            "permitted_reuse": ["company-internal-reference"],
        })
        self.library.admit(self.access, material["material_id"], material["version_id"])
        return material

    def test_search_returns_exact_attributed_non_authoritative_hit(self) -> None:
        item = self.admit("operations.md", "Alpha process. Needle phrase. Omega.".encode())
        payload = self.search.search(self.access, "needle PHRASE")
        self.assertEqual(payload["schema"], "arvectum.workspace.company-asset-search/1")
        self.assertEqual(len(payload["hits"]), 1)
        hit = payload["hits"][0]
        self.assertEqual(hit["material_id"], item["material_id"])
        self.assertEqual(hit["version_id"], item["version_id"])
        self.assertEqual(hit["content_sha256"], item["content_sha256"])
        self.assertFalse(hit["canonical_authority"])
        self.assertEqual(hit["knowledge_status"], "not-validated-knowledge")
        self.assertFalse(payload["limitations"]["persisted_index"])
        self.assertFalse(payload["limitations"]["semantic_search"])

    def test_opaque_sources_are_explicitly_counted_and_not_searched(self) -> None:
        self.admit("opaque.pdf", b"needle-secret", media_type="application/pdf")
        payload = self.search.search(self.access, "needle")
        self.assertEqual(payload["hits"], [])
        self.assertEqual(payload["limitations"]["unsupported_current_sources"], 1)

    def test_query_and_limit_are_bounded(self) -> None:
        for query in ("", " " * 3, "x" * 201, None):
            with self.assertRaises(CompanyAssetSearchError):
                self.search.search(self.access, query)
        for limit in (0, 21, True):
            with self.assertRaises(CompanyAssetSearchError):
                self.search.search(self.access, "valid", limit=limit)

    def test_cross_organization_search_isolated_by_server_access_context(self) -> None:
        self.admit("private.md", b"needle private company text")
        other = AccessContext(
            organization=Identity("organization", "other-org", "platform"),
            actor=Identity("principal", "other-owner", "other-org"),
            principal_kind="human",
            credential_id="credential-other",
            grant_id="grant-other",
        )
        payload = self.search.search(other, "needle")
        self.assertEqual(payload["hits"], [])


if __name__ == "__main__":
    unittest.main()
