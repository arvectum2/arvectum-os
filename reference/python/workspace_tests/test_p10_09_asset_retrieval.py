from __future__ import annotations

import base64
import tempfile
import unittest
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


TEXT_MEDIA_TYPE = "text/plain"


class Resolver:
    def __init__(self) -> None:
        self.organization = Identity("organization", "org-a", "platform")
        self.actor = Identity("principal", "owner-a", "org-a")

    def authorize(self) -> AccessContext:
        return AccessContext(
            organization=self.organization,
            actor=self.actor,
            principal_kind="human",
            credential_id="credential-p10-09",
            grant_id="grant-p10-09",
        )


class Portfolio:
    def project(self, access: AccessContext):
        return {"schema": "test", "projects": [], "scope": {"actor": access.actor.value}}


class Admission:
    def __init__(self) -> None:
        self.items: list[AdmittedCompanyAssetVersion] = []

    def available(self, access: AccessContext) -> bool:
        return True

    def admitted_versions(self, access: AccessContext) -> tuple[AdmittedCompanyAssetVersion, ...]:
        return tuple(self.items)

    def admit(self, *, access: AccessContext, store: CompanyMaterialsStore, material_id: str, version_id: str, policy: CompanyAssetReviewPolicy) -> AdmittedCompanyAssetVersion:
        store._version(access, material_id, version_id)
        self.items = [replace(value, current=False) if value.material_id == material_id else value for value in self.items]
        admitted = AdmittedCompanyAssetVersion(
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
        self.items.append(admitted)
        return admitted


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


class P1009AssetRetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        static = self.root / "dist"
        static.mkdir()
        (static / "index.html").write_text("<!doctype html><div id='root'>SPA</div>", encoding="utf-8")
        (static / "assets").mkdir()
        self.store = CompanyMaterialsStore(self.root)
        self.admission = Admission()
        app = create_app(settings(self.root), access_resolver=Resolver(), static_dir=static)
        install_f11_routes(app, portfolio_provider=Portfolio(), materials_store=self.store, asset_admission=self.admission)  # type: ignore[arg-type]
        self.client = TestClient(app, base_url="http://127.0.0.1:8769", client=("127.0.0.1", 50000))
        self.release_headers = {RELEASE_HEADER: load_release().release_id}
        bootstrap = self.client.post("/api/app/v1/session/bootstrap", headers={**self.release_headers, "Origin": "http://127.0.0.1:8769"})
        self.assertEqual(bootstrap.status_code, 200)
        self.csrf = bootstrap.json()["session"]["csrf_token"]

    def tearDown(self) -> None:
        self.client.close()
        self.temp.cleanup()

    @property
    def command_headers(self) -> dict[str, str]:
        return {**self.release_headers, "Origin": "http://127.0.0.1:8769", CSRF_HEADER: self.csrf}

    def stage(self, content: bytes, material_id: str | None = None) -> dict[str, object]:
        payload = {
            "project_id": "COMPANY",
            "filename": "company-note.txt",
            "media_type": TEXT_MEDIA_TYPE,
            "semantic_role": "source",
            "classification": "internal",
            "purpose": "company reference",
            "rights": "company-internal-use",
            "retention_rule": "until-replaced",
            "content_base64": base64.b64encode(content).decode("ascii"),
        }
        if material_id is not None:
            payload["material_id"] = material_id
        response = self.client.post("/api/app/v1/company-materials", headers=self.command_headers, json=payload)
        self.assertEqual(response.status_code, 200)
        return response.json()["material"]

    def admit(self, material: dict[str, object]) -> None:
        base = f"/api/app/v1/company-assets/{material['material_id']}/versions/{material['version_id']}"
        reviewed = self.client.post(
            f"{base}/review",
            headers=self.command_headers,
            json={"deletion_rule": "governed-deletion", "permitted_reuse": ["company-internal"]},
        )
        self.assertEqual(reviewed.status_code, 200)
        admitted = self.client.post(f"{base}/admit", headers=self.command_headers)
        self.assertEqual(admitted.status_code, 200)

    def content_path(self, material: dict[str, object]) -> str:
        return f"/api/app/v1/company-assets/{material['material_id']}/versions/{material['version_id']}/content"

    def test_staged_bytes_are_not_retrievable_until_exact_version_is_admitted(self) -> None:
        material = self.stage(b"draft-only")
        blocked = self.client.get(self.content_path(material), headers=self.release_headers)
        self.assertEqual(blocked.status_code, 404)
        self.assertEqual(blocked.json()["detail"], "COMPANY_ASSET_CONTENT_UNAVAILABLE")

        self.admit(material)
        opened = self.client.get(self.content_path(material), headers=self.release_headers)
        self.assertEqual(opened.status_code, 200)
        self.assertEqual(opened.content, b"draft-only")
        self.assertEqual(opened.headers["content-type"], TEXT_MEDIA_TYPE + "; charset=utf-8")
        self.assertEqual(opened.headers["cache-control"], "no-store")
        self.assertEqual(opened.headers["x-content-type-options"], "nosniff")
        self.assertTrue(opened.headers["content-disposition"].startswith("inline;"))

        downloaded = self.client.get(self.content_path(material) + "?download=true", headers=self.release_headers)
        self.assertEqual(downloaded.status_code, 200)
        self.assertTrue(downloaded.headers["content-disposition"].startswith("attachment;"))

    def test_superseded_exact_version_remains_retrievable_without_internal_id_discovery(self) -> None:
        first = self.stage(b"version-one")
        self.admit(first)
        second = self.stage(b"version-two", str(first["material_id"]))
        self.admit(second)

        projection = self.client.get("/api/app/v1/company-assets", headers=self.release_headers).json()
        self.assertEqual(projection["views"]["accepted"][0]["version_id"], second["version_id"])
        self.assertEqual(projection["views"]["archive"][0]["version_id"], first["version_id"])
        old = self.client.get(self.content_path(first), headers=self.release_headers)
        current = self.client.get(self.content_path(second), headers=self.release_headers)
        self.assertEqual(old.content, b"version-one")
        self.assertEqual(current.content, b"version-two")

    def test_retrieval_is_session_protected(self) -> None:
        material = self.stage(b"admitted")
        self.admit(material)
        self.client.cookies.clear()
        denied = self.client.get(self.content_path(material), headers=self.release_headers)
        self.assertEqual(denied.status_code, 401)
        self.assertNotIn("SPA", denied.text)


if __name__ == "__main__":
    unittest.main()
