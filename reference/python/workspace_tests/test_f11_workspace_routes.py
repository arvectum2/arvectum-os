from __future__ import annotations

import base64
import io
import tempfile
import unittest
import zipfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from arvectum_os_ref.identity import Identity
from workspace_app.access import AccessContext
from workspace_app.company_asset_library import AdmittedCompanyAssetVersion, CompanyAssetReviewPolicy
from workspace_app.company_materials import CompanyMaterialsStore
from workspace_app.config import WorkspaceSettings
from workspace_app.f11_routes import install_f11_routes
from workspace_app.main import CSRF_HEADER, RELEASE_HEADER, create_app
from workspace_app.release import load_release


DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class FakeResolver:
    def __init__(self) -> None:
        self.organization = Identity("organization", "org-a", "platform")
        self.actor = Identity("principal", "owner-a", "org-a")

    def authorize(self) -> AccessContext:
        return AccessContext(
            organization=self.organization,
            actor=self.actor,
            principal_kind="human",
            credential_id="credential-f11",
            grant_id="grant-f11",
        )


class FakePortfolio:
    def project(self, access: AccessContext):
        return {
            "schema": "arvectum.workspace.company-portfolio/1",
            "product_contract": {"id": "P9.11-F11", "version": "0.1.0", "lifecycle": "Provisional"},
            "projects": [
                {
                    "id": "PORT-002",
                    "label": "Data Platform",
                    "state": "reconciliation-required",
                    "source": None,
                    "roadmap": {"status": None},
                }
            ],
            "scope": {"actor": access.actor.value},
        }


class FakeAdmission:
    """Route seam only; P10.03 semantics are covered by platform tests."""

    def __init__(self) -> None:
        self.items: list[AdmittedCompanyAssetVersion] = []
        self.calls = 0

    def available(self, access: AccessContext) -> bool:
        return True

    def admitted_versions(self, access: AccessContext) -> tuple[AdmittedCompanyAssetVersion, ...]:
        return tuple(self.items)

    def admit(
        self,
        *,
        access: AccessContext,
        store: CompanyMaterialsStore,
        material_id: str,
        version_id: str,
        policy: CompanyAssetReviewPolicy,
    ) -> AdmittedCompanyAssetVersion:
        store._version(access, material_id, version_id)
        self.items = [replace(item, current=False) if item.material_id == material_id else item for item in self.items]
        item = AdmittedCompanyAssetVersion(
            material_id=material_id,
            version_id=version_id,
            document_subject=f"document:{material_id}",
            document_version=f"document-version:{version_id}",
            designation_subject=f"asset:{material_id}",
            designation_version=f"asset-version:{version_id}",
            event_version=f"event-version:{version_id}",
            admitted_at=datetime.now(timezone.utc).isoformat(),
            provenance_refs=(f"source:{material_id}", f"source-version:{version_id}"),
            current=True,
        )
        self.items.append(item)
        self.calls += 1
        return item


def settings(root: Path) -> WorkspaceSettings:
    return WorkspaceSettings(
        runtime_root=root,
        public_origin="http://127.0.0.1:8769",
        bind_host="127.0.0.1",
        bind_port=8769,
        allowed_hosts=("127.0.0.1:8769",),
        organization_label="ООО «Арвектум»",
        actor_label="Owner operator",
        session_idle_seconds=60,
        session_absolute_seconds=300,
        allow_loopback_http=True,
    )


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


class F11WorkspaceRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.static = self.root / "dist"
        self.static.mkdir()
        (self.static / "index.html").write_text("<!doctype html><div id='root'>SPA</div>", encoding="utf-8")
        (self.static / "assets").mkdir()
        app = create_app(settings(self.root), access_resolver=FakeResolver(), static_dir=self.static)
        self.admission = FakeAdmission()
        install_f11_routes(
            app,
            portfolio_provider=FakePortfolio(),  # type: ignore[arg-type]
            materials_store=CompanyMaterialsStore(self.root),
            asset_admission=self.admission,
        )
        self.client = TestClient(app, base_url="http://127.0.0.1:8769", client=("127.0.0.1", 50000))
        self.release = load_release().release_id
        self.release_headers = {RELEASE_HEADER: self.release}
        bootstrap = self.client.post(
            "/api/app/v1/session/bootstrap",
            headers={**self.release_headers, "Origin": "http://127.0.0.1:8769"},
        )
        self.assertEqual(bootstrap.status_code, 200)
        self.csrf = bootstrap.json()["session"]["csrf_token"]

    def tearDown(self) -> None:
        self.client.close()
        self.temp.cleanup()

    @property
    def command_headers(self) -> dict[str, str]:
        return {
            **self.release_headers,
            "Origin": "http://127.0.0.1:8769",
            CSRF_HEADER: self.csrf,
        }

    def stage_template(self) -> dict[str, object]:
        payload = {
            "project_id": "COMPANY",
            "filename": "template.docx",
            "media_type": DOCX_MEDIA_TYPE,
            "semantic_role": "document-template",
            "classification": "internal",
            "purpose": "company standard",
            "rights": "company-internal-use",
            "retention_rule": "until-replaced",
            "content_base64": base64.b64encode(docx_template()).decode("ascii"),
        }
        response = self.client.post("/api/app/v1/company-materials", headers=self.command_headers, json=payload)
        self.assertEqual(response.status_code, 200)
        return response.json()["material"]

    def submit_review(self, material: dict[str, object]) -> None:
        response = self.client.post(
            f"/api/app/v1/company-assets/{material['material_id']}/versions/{material['version_id']}/review",
            headers=self.command_headers,
            json={
                "deletion_rule": "delete-through-governed-retention",
                "permitted_reuse": ["company-internal-document-generation"],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["canonical_state_changed"])

    def test_portfolio_route_precedes_spa_and_is_session_protected(self) -> None:
        response = self.client.get("/api/app/v1/company/portfolio", headers=self.release_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["projects"][0]["state"], "reconciliation-required")
        self.client.cookies.clear()
        denied = self.client.get("/api/app/v1/company/portfolio", headers=self.release_headers)
        self.assertEqual(denied.status_code, 401)
        self.assertNotIn("SPA", denied.text)

    def test_stage_requires_csrf_and_library_exposes_truthful_draft(self) -> None:
        payload = {
            "project_id": "COMPANY",
            "filename": "template.docx",
            "media_type": DOCX_MEDIA_TYPE,
            "semantic_role": "document-template",
            "classification": "internal",
            "purpose": "company standard",
            "rights": "company-internal-use",
            "retention_rule": "until-replaced",
            "content_base64": base64.b64encode(docx_template()).decode("ascii"),
        }
        missing = self.client.post(
            "/api/app/v1/company-materials",
            headers={**self.release_headers, "Origin": "http://127.0.0.1:8769"},
            json=payload,
        )
        self.assertEqual(missing.status_code, 403)
        staged = self.client.post("/api/app/v1/company-materials", headers=self.command_headers, json=payload)
        self.assertEqual(staged.status_code, 200)
        material = staged.json()["material"]
        self.assertEqual(material["state"], "StagedNonCanonical")

        projection = self.client.get("/api/app/v1/company-assets", headers=self.release_headers)
        self.assertEqual(projection.status_code, 200)
        self.assertEqual(projection.json()["product_contract"]["version"], "0.2.0")
        draft = projection.json()["views"]["drafts"][0]
        self.assertEqual(draft["version_id"], material["version_id"])
        self.assertEqual(draft["staging_state"], "StagedNonCanonical")
        self.assertIsNone(draft["canonical"])

    def test_review_reject_and_admit_are_csrf_protected_and_distinct(self) -> None:
        material = self.stage_template()
        path = f"/api/app/v1/company-assets/{material['material_id']}/versions/{material['version_id']}"
        missing = self.client.post(
            f"{path}/review",
            headers={**self.release_headers, "Origin": "http://127.0.0.1:8769"},
            json={
                "deletion_rule": "delete-through-governed-retention",
                "permitted_reuse": ["company-internal-document-generation"],
            },
        )
        self.assertEqual(missing.status_code, 403)

        self.submit_review(material)
        reviewing = self.client.get("/api/app/v1/company-assets", headers=self.release_headers).json()
        self.assertEqual(reviewing["views"]["review"][0]["version_id"], material["version_id"])

        rejected = self.client.post(
            f"{path}/reject",
            headers=self.command_headers,
            json={"reason": "needs correction"},
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertFalse(rejected.json()["canonical_state_changed"])
        self.assertEqual(self.admission.calls, 0)

        self.submit_review(material)
        admitted = self.client.post(f"{path}/admit", headers=self.command_headers)
        self.assertEqual(admitted.status_code, 200)
        self.assertTrue(admitted.json()["canonical_state_changed"])
        self.assertTrue(admitted.json()["through_governed_execution"])
        self.assertEqual(self.admission.calls, 1)
        projection = self.client.get("/api/app/v1/company-assets", headers=self.release_headers).json()
        self.assertEqual(projection["views"]["accepted"][0]["version_id"], material["version_id"])
        self.assertIsNotNone(projection["views"]["accepted"][0]["canonical"])

    def test_generation_requires_admitted_exact_source_and_downloads_transient_docx(self) -> None:
        material = self.stage_template()
        generation = {
            "material_id": material["material_id"],
            "version_id": material["version_id"],
            "title": "Заголовок",
            "body": "Содержание",
            "date": "26.08.2026",
        }
        blocked = self.client.post(
            "/api/app/v1/company-materials/generate",
            headers=self.command_headers,
            json=generation,
        )
        self.assertEqual(blocked.status_code, 404)

        self.submit_review(material)
        path = f"/api/app/v1/company-assets/{material['material_id']}/versions/{material['version_id']}/admit"
        admitted = self.client.post(path, headers=self.command_headers)
        self.assertEqual(admitted.status_code, 200)

        generated = self.client.post(
            "/api/app/v1/company-materials/generate",
            headers=self.command_headers,
            json=generation,
        )
        self.assertEqual(generated.status_code, 200)
        output = generated.json()["output"]
        self.assertEqual(output["source_version_id"], material["version_id"])
        self.assertEqual(output["state"], "TransientOutput")
        self.assertTrue(generated.json()["governance"]["source_admitted_company_asset"])
        download = self.client.get(output["download_href"], headers=self.release_headers)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.headers["content-type"], DOCX_MEDIA_TYPE)
        self.assertGreater(len(download.content), 100)

    def test_content_search_is_session_scoped_rebuildable_and_non_authoritative(self) -> None:
        payload = {
            "project_id": "COMPANY", "filename": "policy.md", "media_type": "text/markdown",
            "semantic_role": "source", "classification": "internal", "purpose": "company policy",
            "rights": "company-internal-use", "retention_rule": "until-replaced",
            "content_base64": base64.b64encode(b"Internal procurement policy alpha").decode("ascii"),
        }
        staged = self.client.post("/api/app/v1/company-materials", headers=self.command_headers, json=payload).json()["material"]
        self.submit_review(staged)
        admitted = self.client.post(f"/api/app/v1/company-assets/{staged['material_id']}/versions/{staged['version_id']}/admit", headers=self.command_headers)
        self.assertEqual(admitted.status_code, 200)
        response = self.client.get("/api/app/v1/company-assets/search?q=procurement", headers=self.release_headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["hits"][0]["version_id"], staged["version_id"] )
        self.assertFalse(result["governance"]["canonical_authority"] )
        self.assertFalse(result["governance"]["validated_knowledge_created"] )
        self.assertFalse(result["limitations"]["persisted_index"] )
        self.client.cookies.clear()
        denied = self.client.get("/api/app/v1/company-assets/search?q=procurement", headers=self.release_headers)
        self.assertEqual(denied.status_code, 401)

    def test_export_is_session_scoped_and_bounded(self) -> None:
        self.stage_template()
        response = self.client.get("/api/app/v1/company-assets/export?limit=1", headers=self.release_headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["bounded"])
        self.assertFalse(response.json()["canonical_authority"])
        self.assertEqual(len(response.json()["items"]), 1)
        rejected = self.client.get("/api/app/v1/company-assets/export?limit=101", headers=self.release_headers)
        self.assertEqual(rejected.status_code, 400)


if __name__ == "__main__":
    unittest.main()
