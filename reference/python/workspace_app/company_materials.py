from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import secrets
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .access import AccessContext


class CompanyMaterialsError(RuntimeError):
    """Bounded F11A staged-material operation cannot be completed safely."""


class CompanyMaterialsInputError(CompanyMaterialsError):
    """User supplied material metadata or bytes are outside the bounded contract."""


class CompanyMaterialUnavailable(CompanyMaterialsError):
    """The exact requested staged material/version cannot be resolved."""


MAX_MATERIAL_BYTES = 8 * 1024 * 1024
MAX_OFFICE_EXPANDED_BYTES = 32 * 1024 * 1024
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
_ALLOWED_MEDIA_TYPES = frozenset(
    {
        DOCX_MEDIA_TYPE,
        PPTX_MEDIA_TYPE,
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/webp",
        "text/plain",
        "text/markdown",
    }
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{8,96}$")
_SAFE_PROJECT_ID = re.compile(r"^(?:PORT-[0-9]{3}|COMPANY)$")
_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
_DRAWING_MAIN_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_PICTURE_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
_SUPPORTED_PLACEHOLDERS = ("{{TITLE}}", "{{BODY}}", "{{DATE}}")
_GENERATION_INPUT_USES = frozenset({"brand", "source", "reference"})
_MAX_GENERATION_AUX_INPUTS = 8
_MAX_EMBEDDED_TEXT_BYTES = 64 * 1024


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _identity_text(identity: object) -> str:
    return f"{identity.namespace}:{identity.value}@{identity.scope}"  # type: ignore[attr-defined]


def _bounded(value: object, name: str, *, maximum: int = 320, required: bool = True) -> str:
    if not isinstance(value, str):
        raise CompanyMaterialsInputError(f"{name} must be text")
    normalized = " ".join(value.split())
    if required and not normalized:
        raise CompanyMaterialsInputError(f"{name} is required")
    if len(normalized) > maximum:
        raise CompanyMaterialsInputError(f"{name} exceeds bounded length")
    return normalized


def _secure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError as exc:
        raise CompanyMaterialsError("staged-material directory permissions could not be secured") from exc


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    _secure_dir(path.parent)
    if path.is_symlink():
        raise CompanyMaterialsError("staged-material metadata target must not be a symlink")
    temporary = path.with_suffix(path.suffix + f".{secrets.token_hex(6)}.tmp")
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    try:
        temporary.write_text(data, encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _decode_content(value: object) -> bytes:
    if not isinstance(value, str) or not value:
        raise CompanyMaterialsInputError("content_base64 is required")
    try:
        content = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise CompanyMaterialsInputError("content_base64 is invalid") from exc
    if not content or len(content) > MAX_MATERIAL_BYTES:
        raise CompanyMaterialsInputError("material bytes are empty or exceed 8 MiB")
    return content


def _office_entries(content: bytes, required: frozenset[str]) -> list[tuple[zipfile.ZipInfo, bytes]]:
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
            infos = archive.infolist()
            names = {info.filename for info in infos}
            if not infos or not required.issubset(names):
                raise CompanyMaterialsInputError("Office package structure does not match declared media type")
            if sum(info.file_size for info in infos) > MAX_OFFICE_EXPANDED_BYTES:
                raise CompanyMaterialsInputError("Office package exceeds expanded-size limit")
            entries: list[tuple[zipfile.ZipInfo, bytes]] = []
            for info in infos:
                if info.flag_bits & 0x1:
                    raise CompanyMaterialsInputError("encrypted Office packages are unsupported")
                parts = Path(info.filename).parts
                if info.filename.startswith("/") or ".." in parts:
                    raise CompanyMaterialsInputError("Office package contains unsafe archive paths")
                if info.filename.lower().endswith("vbaproject.bin"):
                    raise CompanyMaterialsInputError("macro-enabled Office content is outside the first F11A slice")
                entries.append((info, archive.read(info.filename)))
            return entries
    except zipfile.BadZipFile as exc:
        raise CompanyMaterialsInputError("declared Office material is not a valid Office package") from exc


def _require_prefix(content: bytes, prefix: bytes, media_label: str) -> None:
    if not content.startswith(prefix):
        raise CompanyMaterialsInputError(f"material bytes do not match declared {media_label} type")


def _validate_webp(content: bytes) -> None:
    if len(content) < 12 or content[:4] != b"RIFF" or content[8:12] != b"WEBP":
        raise CompanyMaterialsInputError("material bytes do not match declared WebP type")


def _validate_utf8_text(content: bytes) -> None:
    if b"\x00" in content:
        raise CompanyMaterialsInputError("text material contains NUL bytes")
    try:
        content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CompanyMaterialsInputError("text material must be valid UTF-8") from exc


def _validate_actual_content(media_type: str, content: bytes) -> None:
    """Validate bytes independently from filename/extension/browser MIME claims."""

    office_required = {
        DOCX_MEDIA_TYPE: frozenset({"[Content_Types].xml", "word/document.xml"}),
        PPTX_MEDIA_TYPE: frozenset({"[Content_Types].xml", "ppt/presentation.xml"}),
    }.get(media_type)
    if office_required is not None:
        _office_entries(content, office_required)
        return

    prefix_rule = {
        "application/pdf": (b"%PDF-", "PDF"),
        "image/png": (b"\x89PNG\r\n\x1a\n", "PNG"),
        "image/jpeg": (b"\xff\xd8\xff", "JPEG"),
    }.get(media_type)
    if prefix_rule is not None:
        _require_prefix(content, *prefix_rule)
        return
    if media_type == "image/webp":
        _validate_webp(content)
        return
    if media_type in {"text/plain", "text/markdown"}:
        _validate_utf8_text(content)
        return
    raise CompanyMaterialsInputError("media_type is outside the bounded F11A allowlist")


@dataclass(frozen=True, slots=True)
class MaterialVersion:
    material_id: str
    version_id: str
    predecessor_version_id: str | None
    organization: str
    project_id: str
    filename: str
    media_type: str
    semantic_role: str
    classification: str
    purpose: str
    rights: str
    retention_rule: str
    uploader: str
    received_at: str
    content_sha256: str
    size_bytes: int
    state: str = "StagedNonCanonical"

    def to_payload(self) -> dict[str, Any]:
        return {
            "material_id": self.material_id,
            "version_id": self.version_id,
            "predecessor_version_id": self.predecessor_version_id,
            "organization": self.organization,
            "project_id": self.project_id,
            "filename": self.filename,
            "media_type": self.media_type,
            "semantic_role": self.semantic_role,
            "classification": self.classification,
            "purpose": self.purpose,
            "rights": self.rights,
            "retention_rule": self.retention_rule,
            "uploader": self.uploader,
            "received_at": self.received_at,
            "content_sha256": self.content_sha256,
            "size_bytes": self.size_bytes,
            "state": self.state,
            "canonical_authority": False,
            "validated_knowledge": False,
        }


class CompanyMaterialsStore:
    """Product-owned owner-local staged material store for the Provisional F11A slice.

    It preserves exact bytes and lineage but deliberately does not admit platform
    canonical Documents/Artifacts. Organization scope is bound into every staged
    manifest/version/output and revalidated for every read or generation use.
    """

    def __init__(self, runtime_root: Path) -> None:
        self.root = runtime_root.expanduser() / "workspace-company-materials"
        self.blobs = self.root / "blobs"
        self.manifests = self.root / "materials"
        self.transient = self.root / "transient"

    def _manifest_path(self, material_id: str) -> Path:
        if not _SAFE_ID.fullmatch(material_id) or not material_id.startswith("MAT-"):
            raise CompanyMaterialUnavailable("material identity invalid")
        return self.manifests / f"{material_id}.json"

    def _read_manifest(self, material_id: str, organization: str) -> dict[str, Any]:
        path = self._manifest_path(material_id)
        try:
            if path.is_symlink():
                raise CompanyMaterialUnavailable("material manifest invalid")
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CompanyMaterialUnavailable("material manifest unavailable") from exc
        if (
            payload.get("schema") != "arvectum.company.staged-material/1"
            or payload.get("material_id") != material_id
            or payload.get("organization") != organization
        ):
            raise CompanyMaterialUnavailable("material manifest unavailable in current Organization scope")
        versions = payload.get("versions")
        if not isinstance(versions, list) or not versions:
            raise CompanyMaterialUnavailable("material manifest has no versions")
        return payload

    def _version(self, access: AccessContext, material_id: str, version_id: str) -> dict[str, Any]:
        if not _SAFE_ID.fullmatch(version_id) or not version_id.startswith("MV-"):
            raise CompanyMaterialUnavailable("version identity invalid")
        organization = _identity_text(access.organization)
        manifest = self._read_manifest(material_id, organization)
        matches = [item for item in manifest["versions"] if isinstance(item, dict) and item.get("version_id") == version_id]
        if len(matches) != 1:
            raise CompanyMaterialUnavailable("exact staged material version unavailable")
        version = matches[0]
        if version.get("state") != "StagedNonCanonical" or version.get("organization") != organization:
            raise CompanyMaterialUnavailable("exact staged material version unavailable")
        return version

    def _write_blob(self, content: bytes, sha256: str) -> None:
        _secure_dir(self.root)
        _secure_dir(self.blobs)
        target = self.blobs / sha256
        if target.exists():
            if not target.is_symlink() and target.is_file() and _content_sha256(target.read_bytes()) == sha256:
                return
            raise CompanyMaterialsError("content-addressed staged blob conflict")
        temporary = self.blobs / f".{sha256}.{secrets.token_hex(6)}.tmp"
        try:
            temporary.write_bytes(content)
            os.chmod(temporary, 0o600)
            if _content_sha256(temporary.read_bytes()) != sha256:
                raise CompanyMaterialsError("staged blob integrity verification failed")
            os.replace(temporary, target)
            os.chmod(target, 0o600)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _validated_metadata(self, payload: dict[str, Any]) -> dict[str, str]:
        project_id = _bounded(payload.get("project_id", "COMPANY"), "project_id", maximum=24)
        if not _SAFE_PROJECT_ID.fullmatch(project_id):
            raise CompanyMaterialsInputError("project_id must be COMPANY or stable PORT-nnn identity")
        filename = _bounded(payload.get("filename"), "filename", maximum=240)
        if "/" in filename or "\\" in filename or filename in {".", ".."}:
            raise CompanyMaterialsInputError("filename must be a basename")
        media_type = _bounded(payload.get("media_type"), "media_type", maximum=160)
        if media_type not in _ALLOWED_MEDIA_TYPES:
            raise CompanyMaterialsInputError("media_type is outside the bounded F11A allowlist")
        return {
            "project_id": project_id,
            "filename": filename,
            "media_type": media_type,
            "semantic_role": _bounded(payload.get("semantic_role"), "semantic_role", maximum=96),
            "classification": _bounded(payload.get("classification"), "classification", maximum=96),
            "purpose": _bounded(payload.get("purpose"), "purpose", maximum=240),
            "rights": _bounded(payload.get("rights"), "rights", maximum=240),
            "retention_rule": _bounded(payload.get("retention_rule"), "retention_rule", maximum=240),
        }

    def stage(self, access: AccessContext, payload: object) -> dict[str, Any]:
        if not isinstance(access, AccessContext):
            raise CompanyMaterialsError("server-authorized AccessContext is required")
        if not isinstance(payload, dict):
            raise CompanyMaterialsInputError("material payload must be an object")
        allowed = {
            "material_id",
            "project_id",
            "filename",
            "media_type",
            "semantic_role",
            "classification",
            "purpose",
            "rights",
            "retention_rule",
            "content_base64",
        }
        if not set(payload).issubset(allowed):
            raise CompanyMaterialsInputError("material payload contains unsupported fields")
        metadata = self._validated_metadata(payload)
        content = _decode_content(payload.get("content_base64"))
        _validate_actual_content(metadata["media_type"], content)
        sha256 = _content_sha256(content)
        organization = _identity_text(access.organization)
        material_id_raw = payload.get("material_id")
        predecessor: str | None = None
        if material_id_raw is None:
            material_id = f"MAT-{secrets.token_hex(16)}"
            manifest: dict[str, Any] = {
                "schema": "arvectum.company.staged-material/1",
                "material_id": material_id,
                "organization": organization,
                "created_at": _utc_now(),
                "versions": [],
            }
        else:
            material_id = _bounded(material_id_raw, "material_id", maximum=96)
            manifest = self._read_manifest(material_id, organization)
            latest = manifest["versions"][-1]
            predecessor = str(latest["version_id"])
            if latest.get("content_sha256") == sha256 and all(latest.get(key) == value for key, value in metadata.items()):
                raise CompanyMaterialsInputError("new version must differ in bytes or declared metadata")

        received_at = _utc_now()
        uploader = _identity_text(access.actor)
        version_basis = json.dumps(
            {
                "organization": organization,
                "material_id": material_id,
                "predecessor": predecessor,
                "sha256": sha256,
                "metadata": metadata,
                "received_at": received_at,
                "uploader": uploader,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        version_id = f"MV-{hashlib.sha256(version_basis).hexdigest()[:32]}"
        version = MaterialVersion(
            material_id=material_id,
            version_id=version_id,
            predecessor_version_id=predecessor,
            organization=organization,
            uploader=uploader,
            received_at=received_at,
            content_sha256=sha256,
            size_bytes=len(content),
            **metadata,
        ).to_payload()
        self._write_blob(content, sha256)
        manifest["versions"].append(version)
        manifest["latest_version_id"] = version_id
        _atomic_json(self._manifest_path(material_id), manifest)
        return {
            "schema": "arvectum.workspace.company-material/1",
            "material": version,
            "governance": self._governance_payload(),
        }

    def project(self, access: AccessContext) -> dict[str, Any]:
        if not isinstance(access, AccessContext):
            raise CompanyMaterialsError("server-authorized AccessContext is required")
        organization = _identity_text(access.organization)
        materials: list[dict[str, Any]] = []
        if self.manifests.is_dir():
            for path in sorted(self.manifests.glob("MAT-*.json")):
                try:
                    if path.is_symlink():
                        continue
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    versions = payload.get("versions")
                    if (
                        payload.get("schema") != "arvectum.company.staged-material/1"
                        or payload.get("organization") != organization
                        or not isinstance(versions, list)
                        or not versions
                    ):
                        continue
                    materials.append(
                        {
                            "material_id": payload.get("material_id"),
                            "latest_version_id": payload.get("latest_version_id"),
                            "versions": versions,
                        }
                    )
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    continue
        return {
            "schema": "arvectum.workspace.company-materials/1",
            "generated_at": _utc_now(),
            "product_contract": {"id": "P9.11-F11", "version": "0.1.0", "lifecycle": "Provisional"},
            "scope": {
                "organization_resolved_server_side": True,
                "actor_resolved_server_side": True,
                "cross_organization_access": False,
            },
            "materials": materials,
            "governance": self._governance_payload(),
        }

    @staticmethod
    def _governance_payload() -> dict[str, Any]:
        return {
            "state": "StagedNonCanonical",
            "canonical_admission_available": False,
            "canonical_state_changed": False,
            "organizational_authority_provided_by_upload": False,
            "validated_knowledge_created": False,
            "reason": (
                "Текущий F11A сохраняет owner-local staged evidence и точные версии, но не выдаёт "
                "Authorization/Organizational Authority и не подменяет RFC-0005 Governed Execution."
            ),
        }

    def generate_docx(
        self,
        access: AccessContext,
        payload: object,
        *,
        admitted_inputs: tuple[dict[str, Any], ...] = (),
    ) -> dict[str, Any]:
        if not isinstance(access, AccessContext):
            raise CompanyMaterialsError("server-authorized AccessContext is required")
        if not isinstance(payload, dict) or set(payload) != {"material_id", "version_id", "title", "body", "date"}:
            raise CompanyMaterialsInputError("generation payload is invalid")
        if not isinstance(admitted_inputs, tuple) or len(admitted_inputs) > _MAX_GENERATION_AUX_INPUTS:
            raise CompanyMaterialsInputError("asset-aware generation accepts at most 8 auxiliary inputs")
        material_id = _bounded(payload.get("material_id"), "material_id", maximum=96)
        version_id = _bounded(payload.get("version_id"), "version_id", maximum=96)
        title = _bounded(payload.get("title"), "title", maximum=320)
        body = _bounded(payload.get("body"), "body", maximum=6000)
        date = _bounded(payload.get("date"), "date", maximum=80)
        version = self._version(access, material_id, version_id)
        if version.get("media_type") != DOCX_MEDIA_TYPE:
            raise CompanyMaterialsInputError("template-aware generation currently requires an exact DOCX version")
        source = self._exact_blob(version, unavailable="exact template bytes unavailable")
        resolved_inputs = tuple(self._resolve_generation_input(access, item) for item in admitted_inputs)
        generation_basis = {
            "profile": "company-docx-asset-aware-v1",
            "template": {
                "material_id": material_id,
                "version_id": version_id,
                "sha256": version["content_sha256"],
            },
            "asset_inputs": [item["manifest"] for item in resolved_inputs],
        }
        generation_input_digest = _content_sha256(
            json.dumps(generation_basis, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        output = self._render_docx(
            source,
            {"{{TITLE}}": title, "{{BODY}}": body, "{{DATE}}": date},
            input_assets=resolved_inputs,
        )
        output_sha = _content_sha256(output)
        output_id = f"OUT-{secrets.token_hex(16)}"
        _secure_dir(self.root)
        _secure_dir(self.transient)
        output_path = self.transient / f"{output_id}.docx"
        output_path.write_bytes(output)
        os.chmod(output_path, 0o600)
        output_manifest = {
            "schema": "arvectum.company.transient-output/1",
            "output_id": output_id,
            "state": "TransientOutput",
            "organization": _identity_text(access.organization),
            "project_id": version["project_id"],
            "created_at": _utc_now(),
            "created_by": _identity_text(access.actor),
            "source_material_id": material_id,
            "source_version_id": version_id,
            "source_sha256": version["content_sha256"],
            "generation_profile": "company-docx-asset-aware-v1",
            "generation_input_digest": generation_input_digest,
            "input_assets": [item["manifest"] for item in resolved_inputs],
            "output_sha256": output_sha,
            "media_type": DOCX_MEDIA_TYPE,
            "filename": f"generated-{output_id}.docx",
            "canonical_authority": False,
            "validated_knowledge": False,
        }
        _atomic_json(self.transient / f"{output_id}.json", output_manifest)
        return {
            "schema": "arvectum.workspace.company-generated-output/1",
            "output": {**output_manifest, "download_href": f"/api/app/v1/company-materials/outputs/{output_id}/download"},
            "governance": {
                "generated_artifact_state": "TransientOutput",
                "canonical_state_changed": False,
                "exact_source_version_pinned": True,
            },
        }

    def _exact_blob(self, version: dict[str, Any], *, unavailable: str) -> bytes:
        blob = self.blobs / str(version["content_sha256"])
        try:
            if blob.is_symlink():
                raise CompanyMaterialUnavailable(unavailable)
            content = blob.read_bytes()
        except OSError as exc:
            raise CompanyMaterialUnavailable(unavailable) from exc
        if _content_sha256(content) != version["content_sha256"]:
            raise CompanyMaterialsError("exact generation input integrity mismatch")
        return content

    def _resolve_generation_input(self, access: AccessContext, item: dict[str, Any]) -> dict[str, Any]:
        required = {
            "use_as", "material_id", "version_id", "content_sha256", "title", "media_type",
            "semantic_role", "document_version", "designation_version", "event_version", "provenance_refs",
        }
        if not isinstance(item, dict) or set(item) != required:
            raise CompanyMaterialsInputError("server-resolved asset input metadata is invalid")
        use_as = _bounded(item.get("use_as"), "use_as", maximum=16)
        if use_as not in _GENERATION_INPUT_USES:
            raise CompanyMaterialsInputError("asset input use is unsupported")
        material_id = _bounded(item.get("material_id"), "material_id", maximum=96)
        version_id = _bounded(item.get("version_id"), "version_id", maximum=96)
        version = self._version(access, material_id, version_id)
        for field in ("content_sha256", "media_type", "semantic_role"):
            if version.get(field) != item.get(field):
                raise CompanyMaterialUnavailable("server-resolved admitted input differs from retained exact version")
        content = self._exact_blob(version, unavailable="exact auxiliary generation input unavailable")
        manifest = {key: item[key] for key in required}
        text: str | None = None
        image: bytes | None = None
        media_type = str(version.get("media_type"))
        application = "pinned-reference"
        if media_type in {"text/plain", "text/markdown"}:
            if len(content) > _MAX_EMBEDDED_TEXT_BYTES:
                raise CompanyMaterialsInputError("text generation input exceeds 64 KiB bounded inclusion limit")
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise CompanyMaterialsInputError("text generation input must be valid UTF-8") from exc
            application = "text-included"
        elif use_as == "brand" and media_type in {"image/png", "image/jpeg"}:
            image = content
            application = "embedded-image"
        manifest["application"] = application
        return {"manifest": manifest, "text": text, "image": image}

    def output_path(self, access: AccessContext, output_id: str) -> tuple[Path, dict[str, Any]]:
        if not isinstance(access, AccessContext):
            raise CompanyMaterialsError("server-authorized AccessContext is required")
        if not _SAFE_ID.fullmatch(output_id) or not output_id.startswith("OUT-"):
            raise CompanyMaterialUnavailable("output identity invalid")
        manifest_path = self.transient / f"{output_id}.json"
        output_path = self.transient / f"{output_id}.docx"
        try:
            if manifest_path.is_symlink() or output_path.is_symlink():
                raise CompanyMaterialUnavailable("transient output unavailable")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            content = output_path.read_bytes()
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CompanyMaterialUnavailable("transient output unavailable") from exc
        if (
            manifest.get("schema") != "arvectum.company.transient-output/1"
            or manifest.get("output_id") != output_id
            or manifest.get("organization") != _identity_text(access.organization)
        ):
            raise CompanyMaterialUnavailable("transient output unavailable in current Organization scope")
        if _content_sha256(content) != manifest.get("output_sha256"):
            raise CompanyMaterialsError("transient output integrity mismatch")
        return output_path, manifest

    @staticmethod
    def _render_docx(
        source: bytes,
        replacements: dict[str, str],
        *,
        input_assets: tuple[dict[str, Any], ...] = (),
    ) -> bytes:
        entries = _office_entries(source, frozenset({"[Content_Types].xml", "word/document.xml"}))
        entry_map = {info.filename: (info, data) for info, data in entries}
        try:
            document_root = ET.fromstring(entry_map["word/document.xml"][1])
        except ET.ParseError as exc:
            raise CompanyMaterialsInputError("selected DOCX document.xml is invalid") from exc

        changed: set[str] = set()
        for node in document_root.iter(f"{{{_WORD_NS}}}t"):
            if node.text is None:
                continue
            value = node.text
            for placeholder, replacement in replacements.items():
                if placeholder in value:
                    value = value.replace(placeholder, replacement)
                    changed.add(placeholder)
            node.text = value
        if not changed:
            raise CompanyMaterialsInputError(
                "DOCX template must contain at least one contiguous placeholder: {{TITLE}}, {{BODY}} or {{DATE}}"
            )
        body = document_root.find(f"{{{_WORD_NS}}}body")
        if body is None:
            raise CompanyMaterialsInputError("selected DOCX has no document body")

        image_relationships: dict[int, str] = {}
        added_entries: list[tuple[str, bytes]] = []
        image_inputs = [(idx, item) for idx, item in enumerate(input_assets) if item.get("image") is not None]
        if image_inputs:
            rel_path = "word/_rels/document.xml.rels"
            if rel_path in entry_map:
                try:
                    rel_root = ET.fromstring(entry_map[rel_path][1])
                except ET.ParseError as exc:
                    raise CompanyMaterialsInputError("selected DOCX relationships are invalid") from exc
            else:
                rel_root = ET.Element(f"{{{_REL_NS}}}Relationships")
            existing_ids = {str(node.get("Id")) for node in list(rel_root) if node.get("Id")}
            for sequence, (idx, resolved) in enumerate(image_inputs, start=1):
                rel_id = f"rIdP1009B{sequence}"
                while rel_id in existing_ids:
                    sequence += 1
                    rel_id = f"rIdP1009B{sequence}"
                existing_ids.add(rel_id)
                media_type = str(resolved["manifest"]["media_type"])
                extension = "png" if media_type == "image/png" else "jpg"
                filename = f"p10_09_asset_{sequence}.{extension}"
                ET.SubElement(
                    rel_root,
                    f"{{{_REL_NS}}}Relationship",
                    {
                        "Id": rel_id,
                        "Type": f"{_OFFICE_REL_NS}/image",
                        "Target": f"media/{filename}",
                    },
                )
                image_relationships[idx] = rel_id
                added_entries.append((f"word/media/{filename}", bytes(resolved["image"])))
            rel_bytes = ET.tostring(rel_root, encoding="utf-8", xml_declaration=True)
            if rel_path in entry_map:
                entry_map[rel_path] = (entry_map[rel_path][0], rel_bytes)
            else:
                added_entries.append((rel_path, rel_bytes))
            CompanyMaterialsStore._ensure_image_content_types(entry_map, input_assets)

        if input_assets:
            CompanyMaterialsStore._append_generation_inputs(body, input_assets, image_relationships)
        entry_map["word/document.xml"] = (
            entry_map["word/document.xml"][0],
            ET.tostring(document_root, encoding="utf-8", xml_declaration=True),
        )

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as target:
            for info, _ in entries:
                current_info, data = entry_map[info.filename]
                clone = zipfile.ZipInfo(current_info.filename, date_time=current_info.date_time)
                clone.compress_type = current_info.compress_type
                clone.comment = current_info.comment
                clone.extra = current_info.extra
                clone.internal_attr = current_info.internal_attr
                clone.external_attr = current_info.external_attr
                clone.create_system = current_info.create_system
                target.writestr(clone, data)
            for filename, data in added_entries:
                if filename in entry_map:
                    continue
                info = zipfile.ZipInfo(filename)
                info.compress_type = zipfile.ZIP_DEFLATED
                target.writestr(info, data)
        return buffer.getvalue()

    @staticmethod
    def _ensure_image_content_types(
        entry_map: dict[str, tuple[zipfile.ZipInfo, bytes]],
        input_assets: tuple[dict[str, Any], ...],
    ) -> None:
        info, data = entry_map["[Content_Types].xml"]
        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            raise CompanyMaterialsInputError("selected DOCX content-types manifest is invalid") from exc
        namespace = root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else ""
        def tag(name: str) -> str:
            return f"{{{namespace}}}{name}" if namespace else name
        defaults = {str(node.get("Extension", "")).lower(): node for node in root.findall(tag("Default"))}
        needed = {
            "png": "image/png",
            "jpg": "image/jpeg",
        }
        used = {"png" if item["manifest"].get("media_type") == "image/png" else "jpg" for item in input_assets if item.get("image") is not None}
        for extension in sorted(used):
            if extension not in defaults:
                ET.SubElement(root, tag("Default"), {"Extension": extension, "ContentType": needed[extension]})
        entry_map["[Content_Types].xml"] = (info, ET.tostring(root, encoding="utf-8", xml_declaration=True))

    @staticmethod
    def _append_generation_inputs(
        body: ET.Element,
        input_assets: tuple[dict[str, Any], ...],
        image_relationships: dict[int, str],
    ) -> None:
        def paragraph(value: str) -> ET.Element:
            p = ET.Element(f"{{{_WORD_NS}}}p")
            r = ET.SubElement(p, f"{{{_WORD_NS}}}r")
            t = ET.SubElement(r, f"{{{_WORD_NS}}}t")
            t.text = value
            return p

        def image_paragraph(rel_id: str, name: str, doc_id: int) -> ET.Element:
            p = ET.Element(f"{{{_WORD_NS}}}p")
            r = ET.SubElement(p, f"{{{_WORD_NS}}}r")
            drawing = ET.SubElement(r, f"{{{_WORD_NS}}}drawing")
            inline = ET.SubElement(drawing, f"{{{_DRAWING_NS}}}inline")
            ET.SubElement(inline, f"{{{_DRAWING_NS}}}extent", {"cx": "1828800", "cy": "914400"})
            ET.SubElement(inline, f"{{{_DRAWING_NS}}}docPr", {"id": str(doc_id), "name": name[:120]})
            graphic = ET.SubElement(inline, f"{{{_DRAWING_MAIN_NS}}}graphic")
            graphic_data = ET.SubElement(
                graphic,
                f"{{{_DRAWING_MAIN_NS}}}graphicData",
                {"uri": _PICTURE_NS},
            )
            pic = ET.SubElement(graphic_data, f"{{{_PICTURE_NS}}}pic")
            nv = ET.SubElement(pic, f"{{{_PICTURE_NS}}}nvPicPr")
            ET.SubElement(nv, f"{{{_PICTURE_NS}}}cNvPr", {"id": "0", "name": name[:120]})
            ET.SubElement(nv, f"{{{_PICTURE_NS}}}cNvPicPr")
            fill = ET.SubElement(pic, f"{{{_PICTURE_NS}}}blipFill")
            ET.SubElement(fill, f"{{{_DRAWING_MAIN_NS}}}blip", {f"{{{_OFFICE_REL_NS}}}embed": rel_id})
            stretch = ET.SubElement(fill, f"{{{_DRAWING_MAIN_NS}}}stretch")
            ET.SubElement(stretch, f"{{{_DRAWING_MAIN_NS}}}fillRect")
            shape = ET.SubElement(pic, f"{{{_PICTURE_NS}}}spPr")
            xfrm = ET.SubElement(shape, f"{{{_DRAWING_MAIN_NS}}}xfrm")
            ET.SubElement(xfrm, f"{{{_DRAWING_MAIN_NS}}}off", {"x": "0", "y": "0"})
            ET.SubElement(xfrm, f"{{{_DRAWING_MAIN_NS}}}ext", {"cx": "1828800", "cy": "914400"})
            geometry = ET.SubElement(shape, f"{{{_DRAWING_MAIN_NS}}}prstGeom", {"prst": "rect"})
            ET.SubElement(geometry, f"{{{_DRAWING_MAIN_NS}}}avLst")
            return p

        children = list(body)
        insert_at = len(children)
        if children and children[-1].tag == f"{{{_WORD_NS}}}sectPr":
            insert_at -= 1
        appendix: list[ET.Element] = [paragraph("Generation inputs")]
        for index, resolved in enumerate(input_assets):
            item = resolved["manifest"]
            appendix.append(
                paragraph(
                    f"[{item['use_as']} / {item['application']}] {item['title']} · {item['semantic_role']} · "
                    f"SHA-256 {item['content_sha256']}"
                )
            )
            if resolved.get("text") is not None:
                appendix.append(paragraph(str(resolved["text"])))
            rel_id = image_relationships.get(index)
            if rel_id is not None:
                appendix.append(image_paragraph(rel_id, str(item["title"]), 1000 + index))
        for offset, node in enumerate(appendix):
            body.insert(insert_at + offset, node)



__all__ = [
    "CompanyMaterialUnavailable",
    "CompanyMaterialsError",
    "CompanyMaterialsInputError",
    "CompanyMaterialsStore",
    "DOCX_MEDIA_TYPE",
    "PPTX_MEDIA_TYPE",
    "MAX_MATERIAL_BYTES",
]
