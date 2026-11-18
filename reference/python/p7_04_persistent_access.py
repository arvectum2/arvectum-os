#!/usr/bin/env python3
"""P7.04 bounded persistent least-privilege operational access.

Identity stays an opaque value. Authentication, operational authorization and
Organizational Authority remain separate. Reusable credentials live only in
owner-only ``secrets/p7-04`` files; the registry stores salted verifiers. Grants
are exact Organization/operation/resource/access-path tuples. There is no role,
wildcard, superuser or ambient-admin bypass. A successful access decision never
satisfies consequential approval or Organizational Authority.

This is a reversible owner-local Phase-7 adapter, not a public/stable IAM API or
an Active Platform Capability. Access decisions are non-canonical by default;
P7.05 owns durable observability/log-retention concerns.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import stat
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from arvectum_os_ref.identity import Identity

STORE_SCHEMA = "arvectum.p7_04.persistent-access/1"
P6_SCHEMA = "p6.05-l4-local-context-1"
KINDS = frozenset({"human", "service"})
ACCESS_PATHS = frozenset({"local", "remote"})
KDF = "pbkdf2-sha256"
KDF_ITERATIONS = 200_000
MAX_STATE_BYTES = 2 * 1024 * 1024


class P704Error(RuntimeError):
    pass


class IntegrityError(P704Error):
    pass


class BoundaryError(P704Error):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _id_dict(value: Identity) -> dict[str, str]:
    if not isinstance(value, Identity):
        raise BoundaryError("identity must be an Identity")
    return {"namespace": value.namespace, "value": value.value, "scope": value.scope}


def _id_load(value: Mapping[str, Any], label: str) -> Identity:
    if not isinstance(value, Mapping) or set(value) != {"namespace", "value", "scope"}:
        raise IntegrityError(f"{label} identity shape invalid")
    try:
        return Identity(value["namespace"], value["value"], value["scope"])
    except Exception as exc:
        raise IntegrityError(f"{label} identity invalid") from exc


def _principal_key(value: Identity) -> str:
    raw = json.dumps(_id_dict(value), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _component(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BoundaryError(f"{label} must be non-empty")
    value = value.strip()
    if len(value) > 256 or "*" in value or any(ch in value for ch in "\x00\r\n"):
        raise BoundaryError(f"{label} is not an exact safe scope")
    return value


def _paths(values: Sequence[str]) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise BoundaryError("access_paths must be an explicit sequence")
    result = sorted(set(values))
    if not result or any(value not in ACCESS_PATHS for value in result):
        raise BoundaryError("unsupported or empty access path set")
    return result


def _assert_no_symlink(path: Path) -> None:
    current = Path(os.path.abspath(str(path.expanduser())))
    while True:
        if current.is_symlink():
            raise IntegrityError(f"symlink not allowed in P7.04 path: {current}")
        if current.parent == current:
            return
        current = current.parent


def _owner_only(path: Path) -> None:
    if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise IntegrityError(f"P7.04 path is not owner-only: {path}")


def _private_dir(path: Path) -> None:
    _assert_no_symlink(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir() or path.is_symlink():
        raise IntegrityError(f"unsafe P7.04 directory: {path}")
    if os.name != "nt":
        os.chmod(path, 0o700)
    _owner_only(path)


def _atomic(path: Path, payload: bytes, *, exclusive: bool = False) -> None:
    _private_dir(path.parent)
    _assert_no_symlink(path)
    if exclusive and path.exists():
        raise BoundaryError(f"refusing to replace {path}")
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        if os.name != "nt":
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if exclusive and path.exists():
            raise BoundaryError(f"refusing to replace {path}")
        os.replace(tmp, path)
        if os.name != "nt":
            os.chmod(path, 0o600)
        _owner_only(path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def _state_path(root: Path) -> Path:
    return root.expanduser() / "config" / "p7-04-access.json"


def _secret_path(root: Path, credential_id: str) -> Path:
    return root.expanduser() / "secrets" / "p7-04" / f"{credential_id}.secret"


def _empty(organization: Identity) -> dict[str, Any]:
    if organization.namespace != "organization" or organization.scope != "platform":
        raise BoundaryError("Organization identity must be organization/platform scoped")
    return {
        "schema": STORE_SCHEMA,
        "classification": "owner-local operational access registry; non-canonical",
        "format_status": "bounded-internal-provisional",
        "default_access": "deny",
        "ambient_admin": False,
        "organizational_authority_provided": False,
        "organization": _id_dict(organization),
        "principals": {},
        "credentials": {},
        "grants": {},
    }


def initialize_access_store(root: Path, organization: Identity) -> dict[str, Any]:
    for path in (root.expanduser(), root.expanduser() / "config", root.expanduser() / "secrets" / "p7-04"):
        _private_dir(path)
    state_path = _state_path(root)
    if state_path.exists():
        state = load_access_store(root)
        if _id_load(state["organization"], "Organization") != organization:
            raise BoundaryError("existing store belongs to another Organization")
        return state
    state = _empty(organization)
    _atomic(state_path, (json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(), exclusive=True)
    return state


def _validate(state: Mapping[str, Any]) -> dict[str, Any]:
    keys = {"schema", "classification", "format_status", "default_access", "ambient_admin",
            "organizational_authority_provided", "organization", "principals", "credentials", "grants"}
    if not isinstance(state, Mapping) or set(state) != keys or state.get("schema") != STORE_SCHEMA:
        raise IntegrityError("P7.04 registry shape/schema invalid")
    if state["default_access"] != "deny" or state["ambient_admin"] is not False or state["organizational_authority_provided"] is not False:
        raise IntegrityError("P7.04 deny/admin/authority invariants violated")
    org = _id_load(state["organization"], "Organization")
    if org.namespace != "organization" or org.scope != "platform":
        raise IntegrityError("P7.04 Organization scope invalid")
    if not all(isinstance(state[name], dict) for name in ("principals", "credentials", "grants")):
        raise IntegrityError("P7.04 registries must be JSON objects")

    for key, record in state["principals"].items():
        if not isinstance(record, dict) or set(record) != {"identity", "kind", "status", "created_at", "disabled_at"}:
            raise IntegrityError("principal record shape invalid")
        identity = _id_load(record["identity"], "principal")
        if identity.namespace != "principal" or identity.scope != org.value or key != _principal_key(identity):
            raise IntegrityError("principal identity/scope invalid")
        if record["kind"] not in KINDS or record["status"] not in {"enabled", "disabled"}:
            raise IntegrityError("principal kind/status invalid")
        if (record["status"] == "enabled") != (record["disabled_at"] is None):
            raise IntegrityError("principal disablement evidence invalid")

    for cid, record in state["credentials"].items():
        keys = {"credential_id", "principal_key", "generation", "status", "kdf", "iterations", "salt",
                "verifier", "issued_at", "revoked_at", "rotated_from", "rotated_to"}
        if not isinstance(record, dict) or set(record) != keys or record["credential_id"] != cid:
            raise IntegrityError("credential record shape invalid")
        if record["principal_key"] not in state["principals"] or record["status"] not in {"active", "revoked"}:
            raise IntegrityError("credential binding/status invalid")
        if not isinstance(record["generation"], int) or record["generation"] < 1 or record["kdf"] != KDF or record["iterations"] != KDF_ITERATIONS:
            raise IntegrityError("credential verifier metadata invalid")
        try:
            base64.b64decode(record["salt"], validate=True); base64.b64decode(record["verifier"], validate=True)
        except Exception as exc:
            raise IntegrityError("credential verifier encoding invalid") from exc
        if (record["status"] == "active") != (record["revoked_at"] is None):
            raise IntegrityError("credential revocation evidence invalid")

    for gid, record in state["grants"].items():
        keys = {"grant_id", "principal_key", "organization", "operation", "resource", "access_paths",
                "status", "created_at", "revoked_at"}
        if not isinstance(record, dict) or set(record) != keys or record["grant_id"] != gid:
            raise IntegrityError("grant record shape invalid")
        if record["principal_key"] not in state["principals"] or _id_load(record["organization"], "grant Organization") != org:
            raise IntegrityError("grant principal/Organization binding invalid")
        try:
            if _component(record["operation"], "operation") != record["operation"] or _component(record["resource"], "resource") != record["resource"] or _paths(record["access_paths"]) != record["access_paths"]:
                raise IntegrityError("grant scope is not normalized")
        except BoundaryError as exc:
            raise IntegrityError(str(exc)) from exc
        if record["status"] not in {"active", "revoked"} or ((record["status"] == "active") != (record["revoked_at"] is None)):
            raise IntegrityError("grant status/revocation evidence invalid")
    return dict(state)


def load_access_store(root: Path) -> dict[str, Any]:
    path = _state_path(root); _assert_no_symlink(path)
    try:
        if path.stat().st_size > MAX_STATE_BYTES:
            raise IntegrityError("P7.04 registry too large")
        _owner_only(path)
        return _validate(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError as exc:
        raise IntegrityError("P7.04 registry not initialized") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError("P7.04 registry unreadable") from exc


def _save(root: Path, state: Mapping[str, Any]) -> None:
    state = _validate(state)
    _atomic(_state_path(root), (json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode())


def register_principal(root: Path, identity: Identity, *, kind: str) -> str:
    state = load_access_store(root); org = _id_load(state["organization"], "Organization")
    if identity.namespace != "principal" or identity.scope != org.value or kind not in KINDS:
        raise BoundaryError("principal identity/kind outside bounded Organization scope")
    key = _principal_key(identity); old = state["principals"].get(key)
    if old:
        if old["identity"] != _id_dict(identity) or old["kind"] != kind:
            raise BoundaryError("principal already registered with different semantics")
        return key
    state["principals"][key] = {"identity": _id_dict(identity), "kind": kind, "status": "enabled", "created_at": _now(), "disabled_at": None}
    _save(root, state); return key


def load_p6_owner_context(path: Path) -> tuple[Identity, Identity]:
    path = path.expanduser(); _assert_no_symlink(path)
    try:
        if path.stat().st_size > 64 * 1024: raise IntegrityError("P6 context too large")
        _owner_only(path); raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc: raise IntegrityError("P6 owner context missing") from exc
    except (OSError, json.JSONDecodeError) as exc: raise IntegrityError("P6 owner context unreadable") from exc
    top = {"schema_version", "organization", "operator", "authority", "authentication", "bootstrap"}
    if not isinstance(raw, dict) or set(raw) != top or raw["schema_version"] != P6_SCHEMA: raise IntegrityError("P6 context schema invalid")
    org, op = raw["organization"], raw["operator"]
    if not isinstance(org, dict) or set(org) != {"identity", "context_label"} or org["context_label"] != "ООО «Арвектум»": raise IntegrityError("P6 Organization context invalid")
    if not isinstance(op, dict) or set(op) != {"identity", "principal_category", "operating_mode"} or op["principal_category"] != "human" or op["operating_mode"] != "owner-operated": raise IntegrityError("P6 operator context invalid")
    if raw["authority"] != {"authorization_grants": [], "delegations": [], "organizational_authority_claimed": False}: raise IntegrityError("P6 continuity requires authority-free bootstrap state")
    if raw["authentication"] != {"evidence_refs": []}: raise IntegrityError("P6 continuity requires authentication-evidence-free bootstrap state")
    if raw["bootstrap"] != {"scope": "P6.05-L4", "owner_authorization_asserted": True}: raise IntegrityError("P6 bootstrap provenance invalid")
    org_id, op_id = _id_load(org["identity"], "P6 Organization"), _id_load(op["identity"], "P6 operator")
    if org_id.namespace != "organization" or org_id.scope != "platform" or op_id.namespace != "principal" or op_id.scope != org_id.value: raise IntegrityError("P6 identity scope invalid")
    return org_id, op_id


def bootstrap_from_p6_owner_context(root: Path, context_file: Path, *,
                                    service_principal_key: Optional[str] = None) -> dict[str, Any]:
    """Resolve continuity, not authority. Explicit recovery never creates a service."""
    org, human = load_p6_owner_context(context_file)
    if service_principal_key is not None:
        # Resolve existing exact identity before any registry mutation.
        if not isinstance(service_principal_key, str) or len(service_principal_key) != 64 or any(c not in "0123456789abcdef" for c in service_principal_key):
            raise BoundaryError("invalid exact service selector")
        state = load_access_store(root)
        if _id_load(state["organization"], "Organization") != org:
            raise BoundaryError("existing store belongs to another Organization")
        selected = state["principals"].get(service_principal_key)
        if not selected or selected["kind"] != "service" or selected["status"] != "enabled":
            raise IntegrityError("selected service is not enabled and registered")
        service = _id_load(selected["identity"], "service")
        created = False
    else:
        state = initialize_access_store(root, org)
        services = [r for r in state["principals"].values() if r["kind"] == "service" and r["status"] == "enabled"]
        if len(services) > 1:
            raise IntegrityError("multiple enabled service identities require explicit selection")
        if services:
            service = _id_load(services[0]["identity"], "service"); created = False
        else:
            service = Identity("principal", secrets.token_hex(16), org.value)
            register_principal(root, service, kind="service"); created = True
    human_key = register_principal(root, human, kind="human")
    return {"organization": _id_dict(org), "human_operator": _id_dict(human), "service_identity": _id_dict(service),
            "human_principal_key": human_key, "service_created": created, "credentials_issued": 0, "grants_issued": 0,
            "organizational_authority_provided": False}


def _verifier(secret: str, salt: bytes) -> bytes:
    if not isinstance(secret, str) or not secret: raise BoundaryError("credential secret must be non-empty")
    return hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, KDF_ITERATIONS)


def issue_credential(root: Path, principal: Identity, *, rotated_from: Optional[str] = None) -> dict[str, Any]:
    state = load_access_store(root); key = _principal_key(principal); p = state["principals"].get(key)
    if not p or p["identity"] != _id_dict(principal) or p["status"] != "enabled": raise BoundaryError("enabled registered principal required")
    active = [c for c in state["credentials"].values() if c["principal_key"] == key and c["status"] == "active"]
    if rotated_from is None and active: raise BoundaryError("active credential exists; rotate explicitly")
    if rotated_from is not None and (rotated_from not in state["credentials"] or state["credentials"][rotated_from] not in active): raise BoundaryError("rotation source is not this principal's active credential")
    cid, secret, salt, now = uuid.uuid4().hex, secrets.token_urlsafe(48), secrets.token_bytes(32), _now()
    path = _secret_path(root, cid); _atomic(path, (secret + "\n").encode(), exclusive=True)
    generations = [c["generation"] for c in state["credentials"].values() if c["principal_key"] == key]
    record = {"credential_id": cid, "principal_key": key, "generation": max(generations, default=0) + 1,
              "status": "active", "kdf": KDF, "iterations": KDF_ITERATIONS,
              "salt": base64.b64encode(salt).decode(), "verifier": base64.b64encode(_verifier(secret, salt)).decode(),
              "issued_at": now, "revoked_at": None, "rotated_from": rotated_from, "rotated_to": None}
    try:
        if rotated_from:
            old = state["credentials"][rotated_from]; old["status"] = "revoked"; old["revoked_at"] = now; old["rotated_to"] = cid
        state["credentials"][cid] = record; _save(root, state)
    except Exception:
        path.unlink(missing_ok=True); raise
    if rotated_from: _secret_path(root, rotated_from).unlink(missing_ok=True)
    return {"credential_id": cid, "generation": record["generation"], "secret_path": str(path), "secret_returned": False, "organizational_authority_provided": False}


def rotate_credential(root: Path, principal: Identity, credential_id: str) -> dict[str, Any]:
    return issue_credential(root, principal, rotated_from=credential_id)


def revoke_credential(root: Path, credential_id: str) -> None:
    state = load_access_store(root); c = state["credentials"].get(credential_id)
    if not c: raise BoundaryError("credential does not exist")
    if c["status"] == "active": c["status"], c["revoked_at"] = "revoked", _now(); _save(root, state)
    _secret_path(root, credential_id).unlink(missing_ok=True)


def disable_principal(root: Path, principal: Identity) -> None:
    state = load_access_store(root); key = _principal_key(principal); p = state["principals"].get(key)
    if not p or p["identity"] != _id_dict(principal): raise BoundaryError("principal not registered")
    if p["status"] == "disabled": return
    now = _now(); p["status"], p["disabled_at"] = "disabled", now
    for c in state["credentials"].values():
        if c["principal_key"] == key and c["status"] == "active": c["status"], c["revoked_at"] = "revoked", now
    for g in state["grants"].values():
        if g["principal_key"] == key and g["status"] == "active": g["status"], g["revoked_at"] = "revoked", now
    _save(root, state)
    for cid, c in state["credentials"].items():
        if c["principal_key"] == key: _secret_path(root, cid).unlink(missing_ok=True)


def grant_access(root: Path, principal: Identity, *, operation: str, resource: str, access_paths: Sequence[str] = ("local",)) -> str:
    state = load_access_store(root); org = _id_load(state["organization"], "Organization"); key = _principal_key(principal); p = state["principals"].get(key)
    if not p or p["identity"] != _id_dict(principal) or p["status"] != "enabled": raise BoundaryError("enabled registered principal required")
    operation, resource, paths = _component(operation, "operation"), _component(resource, "resource"), _paths(access_paths)
    for gid, g in state["grants"].items():
        if g["principal_key"] == key and g["operation"] == operation and g["resource"] == resource and g["access_paths"] == paths and g["status"] == "active": return gid
    gid = uuid.uuid4().hex
    state["grants"][gid] = {"grant_id": gid, "principal_key": key, "organization": _id_dict(org), "operation": operation,
                             "resource": resource, "access_paths": paths, "status": "active", "created_at": _now(), "revoked_at": None}
    _save(root, state); return gid


def revoke_grant(root: Path, grant_id: str) -> None:
    state = load_access_store(root); g = state["grants"].get(grant_id)
    if not g: raise BoundaryError("grant does not exist")
    if g["status"] == "active": g["status"], g["revoked_at"] = "revoked", _now(); _save(root, state)


def read_credential_secret(path: Path) -> str:
    path = path.expanduser(); _assert_no_symlink(path)
    try: _owner_only(path); value = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc: raise IntegrityError("credential secret missing") from exc
    except OSError as exc: raise IntegrityError("credential secret unreadable") from exc
    value = value[:-1] if value.endswith("\n") else value
    if not value or "\n" in value or "\r" in value: raise IntegrityError("credential secret shape invalid")
    return value


def _matches(c: Mapping[str, Any], supplied: str) -> bool:
    try: return hmac.compare_digest(_verifier(supplied, base64.b64decode(c["salt"], validate=True)), base64.b64decode(c["verifier"], validate=True))
    except Exception: return False


@dataclass(frozen=True, slots=True)
class AccessDecision:
    allowed: bool
    reason: str
    organization: dict[str, str]
    principal: Optional[dict[str, str]]
    principal_kind: Optional[str]
    credential_id: Optional[str]
    grant_id: Optional[str]
    operation: str
    resource: str
    access_path: str
    operational_access_only: bool = True
    organizational_authority_satisfied: bool = False
    consequential_approval_satisfied: bool = False


def _decision(allowed: bool, reason: str, org: Identity, principal: Optional[Identity], operation: str, resource: str, path: str,
              *, kind: Optional[str] = None, cid: Optional[str] = None, gid: Optional[str] = None) -> AccessDecision:
    return AccessDecision(allowed, reason, _id_dict(org), _id_dict(principal) if principal else None, kind, cid, gid, operation, resource, path)


def authorize(root: Path, *, organization: Identity, principal: Identity, credential_id: str, credential_secret: str,
              operation: str, resource: str, access_path: str) -> AccessDecision:
    try: operation, resource = _component(operation, "operation"), _component(resource, "resource")
    except BoundaryError: return _decision(False, "INVALID_SCOPE", organization, principal if isinstance(principal, Identity) else None, str(operation), str(resource), str(access_path))
    if access_path not in ACCESS_PATHS: return _decision(False, "UNSUPPORTED_ACCESS_PATH", organization, principal, operation, resource, str(access_path))
    try: state = load_access_store(root)
    except P704Error: return _decision(False, "ACCESS_STATE_UNAVAILABLE", organization, principal, operation, resource, access_path)
    org = _id_load(state["organization"], "Organization")
    if organization != org: return _decision(False, "ORGANIZATION_SCOPE_MISMATCH", organization, principal, operation, resource, access_path)
    key = _principal_key(principal); p = state["principals"].get(key)
    if not p or p["identity"] != _id_dict(principal): return _decision(False, "PRINCIPAL_NOT_REGISTERED", org, principal, operation, resource, access_path)
    kind = p["kind"]
    if p["status"] != "enabled": return _decision(False, "PRINCIPAL_DISABLED", org, principal, operation, resource, access_path, kind=kind)
    c = state["credentials"].get(credential_id)
    if not c or c["principal_key"] != key: return _decision(False, "CREDENTIAL_NOT_BOUND", org, principal, operation, resource, access_path, kind=kind, cid=credential_id)
    if c["status"] != "active": return _decision(False, "CREDENTIAL_REVOKED", org, principal, operation, resource, access_path, kind=kind, cid=credential_id)
    if not _matches(c, credential_secret): return _decision(False, "AUTHENTICATION_FAILED", org, principal, operation, resource, access_path, kind=kind, cid=credential_id)
    matches = sorted((g for g in state["grants"].values() if g["principal_key"] == key and g["status"] == "active" and g["organization"] == _id_dict(org)
                      and g["operation"] == operation and g["resource"] == resource and access_path in g["access_paths"]), key=lambda g: g["grant_id"])
    if not matches: return _decision(False, "NO_EXPLICIT_GRANT", org, principal, operation, resource, access_path, kind=kind, cid=credential_id)
    return _decision(True, "EXPLICIT_LEAST_PRIVILEGE_GRANT", org, principal, operation, resource, access_path, kind=kind, cid=credential_id, gid=matches[0]["grant_id"])


def authorize_from_credential_file(root: Path, *, organization: Identity, principal: Identity, credential_id: str,
                                   credential_file: Path, operation: str, resource: str, access_path: str) -> AccessDecision:
    try: supplied = read_credential_secret(credential_file)
    except P704Error: return _decision(False, "CREDENTIAL_SECRET_UNAVAILABLE", organization, principal, str(operation), str(resource), str(access_path), cid=credential_id)
    return authorize(root, organization=organization, principal=principal, credential_id=credential_id, credential_secret=supplied,
                     operation=operation, resource=resource, access_path=access_path)


def verify_store(root: Path) -> dict[str, Any]:
    state = load_access_store(root); active = 0
    secret_dir = root.expanduser() / "secrets" / "p7-04"
    _assert_no_symlink(secret_dir)
    if not secret_dir.is_dir(): raise IntegrityError("P7.04 secret directory missing/unsafe")
    _owner_only(secret_dir)
    known_credentials = set(state["credentials"])
    for secret_file in secret_dir.iterdir():
        if secret_file.is_symlink() or not secret_file.is_file():
            raise IntegrityError("unexpected non-file entry in P7.04 secret directory")
        if secret_file.suffix != ".secret" or secret_file.stem not in known_credentials:
            raise IntegrityError("orphan or unrecognized credential plaintext remains")
        _owner_only(secret_file)
    for cid, c in state["credentials"].items():
        path = _secret_path(root, cid)
        if c["status"] == "active":
            active += 1
            if not path.is_file() or path.is_symlink(): raise IntegrityError("active credential secret missing/unsafe")
            _owner_only(path)
            if not _matches(c, read_credential_secret(path)): raise IntegrityError("active credential verifier mismatch")
        elif path.exists(): raise IntegrityError("revoked credential plaintext remains")
    return {"status": "PASS", "schema": STORE_SCHEMA, "organization": state["organization"], "principals": len(state["principals"]),
            "human_principals": sum(p["kind"] == "human" for p in state["principals"].values()),
            "service_principals": sum(p["kind"] == "service" for p in state["principals"].values()),
            "active_credentials": active, "active_grants": sum(g["status"] == "active" for g in state["grants"].values()),
            "default_access": "deny", "ambient_admin": False, "organizational_authority_provided": False}
