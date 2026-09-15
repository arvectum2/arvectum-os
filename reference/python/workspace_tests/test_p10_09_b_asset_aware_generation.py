from __future__ import annotations

import base64
import io
import tempfile
import unittest
import zipfile
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
from workspace_app.company_materials import (
    CompanyMaterialUnavailable,
    CompanyMaterialsInputError,
    CompanyMaterialsStore,
)

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def docx_template() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>{{TITLE}} {{BODY}} {{DATE}}</w:t></w:r></w:p></w:body></w:document>',
        )
    return buffer.getvalue()


class RecordingAdmission:
    def __init__(self) -> None:
        self.items: dict[str, list[AdmittedCompanyAssetVersion]] = {}

    @staticmethod
    def _scope(access: AccessContext) -> str:
        return access.organization.value

    def available(self, access: AccessContext) -> bool:
        return True

    def admitted_versions(self, access: AccessContext) -> tuple[AdmittedCompanyAssetVersion, ...]:
        return tuple(self.items.get(self._scope(access), ()))

    def admit(self, *, access, store, material_id, version_id, policy: CompanyAssetReviewPolicy):
        version = store._version(access, material_id, version_id)
        scoped = [
            replace(item, current=False) if item.material_id == material_id and item.current else item
            for item in self.items.get(self._scope(access), ())
        ]
        admitted = AdmittedCompanyAssetVersion(
            material_id=material_id,
            version_id=version_id,
            document_subject=f"document:{material_id}",
            document_version=f"document-version:{version_id}",
            designation_subject=f"organizational-asset:{material_id}",
            designation_version=f"organizational-asset-version:{version_id}",
            event_version=f"event-version:{version_id}",
            admitted_at=datetime.now(timezone.utc).isoformat(),
            provenance_refs=(f"staged:{material_id}", f"staged-version:{version_id}"),
            current=True,
        )
        scoped.append(admitted)
        self.items[self._scope(access)] = scoped
        return admitted


class P1009BAssetAwareGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = CompanyMaterialsStore(self.root)
        self.admission = RecordingAdmission()
        self.library = CompanyAssetLibrary(self.store, self.admission)
        self.access = AccessContext(
            organization=Identity("organization", "org-p1009b", "platform"),
            actor=Identity("principal", "owner-p1009b", "org-p1009b"),
            principal_kind="human",
            credential_id="credential-p1009b",
            grant_id="grant-p1009b",
        )
        self.review = {
            "deletion_rule": "governed-deletion",
            "permitted_reuse": ["company-internal-document-generation"],
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def stage(self, *, filename: str, media_type: str, role: str, content: bytes, material_id=None):
        payload = {
            "project_id": "COMPANY",
            "filename": filename,
            "media_type": media_type,
            "semantic_role": role,
            "classification": "internal",
            "purpose": "company document generation",
            "rights": "company-internal-use",
            "retention_rule": "retain-while-current-plus-history",
            "content_base64": base64.b64encode(content).decode("ascii"),
        }
        if material_id:
            payload["material_id"] = material_id
        return self.store.stage(self.access, payload)["material"]

    def admit(self, item):
        self.library.submit_review(self.access, item["material_id"], item["version_id"], self.review)
        self.library.admit(self.access, item["material_id"], item["version_id"])
        return item

    def test_generation_pins_current_admitted_template_brand_and_source(self) -> None:
        template = self.admit(self.stage(filename="template.docx", media_type=DOCX, role="document-template", content=docx_template()))
        logo = self.admit(self.stage(filename="logo.png", media_type="image/png", role="logo", content=b"\x89PNG\r\n\x1a\nfake-logo"))
        brandbook = self.admit(self.stage(filename="brand.pdf", media_type="application/pdf", role="brandbook", content=b"%PDF-1.4\nbrand"))
        source = self.admit(self.stage(filename="facts.md", media_type="text/markdown", role="source", content=b"# Approved facts\nExact source text."))

        generated = self.library.generate_docx(
            self.access,
            {
                "material_id": template["material_id"],
                "version_id": template["version_id"],
                "asset_inputs": [
                    {"material_id": logo["material_id"], "version_id": logo["version_id"], "use_as": "brand"},
                    {"material_id": brandbook["material_id"], "version_id": brandbook["version_id"], "use_as": "brand"},
                    {"material_id": source["material_id"], "version_id": source["version_id"], "use_as": "source"},
                ],
                "title": "Asset-aware document",
                "body": "Body",
                "date": "2026-09-15",
            },
        )
        output = generated["output"]
        self.assertEqual(output["state"], "TransientOutput")
        self.assertFalse(output["canonical_authority"])
        self.assertEqual(output["generation_profile"], "company-docx-asset-aware-v1")
        self.assertEqual(len(output["generation_input_digest"]), 64)
        self.assertEqual([item["use_as"] for item in output["input_assets"]], ["brand", "brand", "source"])
        self.assertEqual(
            [item["application"] for item in output["input_assets"]],
            ["embedded-image", "pinned-reference", "text-included"],
        )
        self.assertEqual(generated["governance"]["generation_input_count"], 4)
        self.assertTrue(generated["governance"]["all_generation_inputs_exact_admitted"])

        path, manifest = self.store.output_path(self.access, output["output_id"])
        self.assertEqual(manifest["input_assets"], output["input_assets"])
        with zipfile.ZipFile(path, "r") as archive:
            rendered = archive.read("word/document.xml").decode("utf-8")
            relationships = archive.read("word/_rels/document.xml.rels").decode("utf-8")
            media = [name for name in archive.namelist() if name.startswith("word/media/p10_09_asset_")]
        self.assertIn("Approved facts", rendered)
        self.assertIn(logo["content_sha256"], rendered)
        self.assertIn(brandbook["content_sha256"], rendered)
        self.assertIn(source["content_sha256"], rendered)
        self.assertEqual(len(media), 1)
        self.assertIn("relationships/image", relationships)

    def test_nonadmitted_duplicate_wrong_role_and_superseded_inputs_fail_closed(self) -> None:
        template = self.admit(self.stage(filename="template.docx", media_type=DOCX, role="document-template", content=docx_template()))
        staged_source = self.stage(filename="facts.txt", media_type="text/plain", role="source", content=b"facts")
        base = {
            "material_id": template["material_id"],
            "version_id": template["version_id"],
            "title": "x",
            "body": "y",
            "date": "2026-09-15",
        }
        with self.assertRaises(CompanyMaterialUnavailable):
            self.library.generate_docx(self.access, {**base, "asset_inputs": [{"material_id": staged_source["material_id"], "version_id": staged_source["version_id"], "use_as": "source"}]})

        admitted_source = self.admit(staged_source)
        with self.assertRaises(CompanyMaterialsInputError):
            self.library.generate_docx(self.access, {**base, "asset_inputs": [
                {"material_id": admitted_source["material_id"], "version_id": admitted_source["version_id"], "use_as": "source"},
                {"material_id": admitted_source["material_id"], "version_id": admitted_source["version_id"], "use_as": "reference"},
            ]})
        with self.assertRaises(CompanyMaterialsInputError):
            self.library.generate_docx(self.access, {**base, "asset_inputs": [{"material_id": admitted_source["material_id"], "version_id": admitted_source["version_id"], "use_as": "brand"}]})

        newer = self.admit(self.stage(filename="facts-v2.txt", media_type="text/plain", role="source", content=b"facts v2", material_id=admitted_source["material_id"]))
        self.assertNotEqual(newer["version_id"], admitted_source["version_id"])
        with self.assertRaises(CompanyMaterialUnavailable):
            self.library.generate_docx(self.access, {**base, "asset_inputs": [{"material_id": admitted_source["material_id"], "version_id": admitted_source["version_id"], "use_as": "source"}]})

    def test_superseded_template_is_not_an_effective_generation_input(self) -> None:
        first = self.admit(self.stage(filename="template.docx", media_type=DOCX, role="document-template", content=docx_template()))
        self.admit(self.stage(filename="template-v2.docx", media_type=DOCX, role="document-template", content=docx_template(), material_id=first["material_id"]))
        with self.assertRaises(CompanyMaterialUnavailable):
            self.library.generate_docx(self.access, {
                "material_id": first["material_id"], "version_id": first["version_id"],
                "title": "x", "body": "y", "date": "2026-09-15",
            })


if __name__ == "__main__":
    unittest.main()
