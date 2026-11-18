#!/usr/bin/env python3
"""P7.04 selected-Mac operational access proof.

The proof requires a healthy P7.02 runtime, reuses the exact P6.05-L4 human
Organization/operator identities, creates/reuses one persistent service identity,
and exercises deny-by-default, exact local/remote grants, credential rotation and
revocation without performing canonical mutation or product/external effects.
Raw identity values and reusable credentials remain owner-local and are omitted
from the emitted non-canonical attestation.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

from arvectum_os_ref.identity import Identity
import p7_03_durable_state as p703
import p7_04_persistent_access as p704

ATTESTATION_SCHEMA = "arvectum.p7_04.selected-mac-attestation/1"


def _runtime(root: Path) -> dict[str, Any]:
    observed = p703._observe_persistent_runtime(root)
    if not observed["observed"] or observed["state"] != "healthy":
        raise p704.IntegrityError("P7.04 selected-Mac proof requires healthy P7.02 runtime")
    return observed


def _identity(raw: dict[str, str]) -> Identity:
    return Identity(raw["namespace"], raw["value"], raw["scope"])


def _active_credential(root: Path, principal: Identity) -> tuple[str, str] | None:
    state = p704.load_access_store(root)
    key = p704._principal_key(principal)
    active = [
        credential for credential in state["credentials"].values()
        if credential["principal_key"] == key and credential["status"] == "active"
    ]
    if len(active) > 1:
        raise p704.IntegrityError("multiple active credentials for one principal")
    if not active:
        return None
    credential_id = active[0]["credential_id"]
    return credential_id, p704.read_credential_secret(p704._secret_path(root, credential_id))


def _ensure_credential(root: Path, principal: Identity) -> tuple[str, str]:
    active = _active_credential(root, principal)
    if active:
        return active
    issued = p704.issue_credential(root, principal)
    return issued["credential_id"], p704.read_credential_secret(Path(issued["secret_path"]))


def run_selected_mac_proof(root: Path, p6_context_file: Path, release_sha: str, *, service_principal_key: Optional[str] = None) -> dict[str, Any]:
    release_sha = p703._validate_release_sha(release_sha)
    root = root.expanduser().resolve()
    before = _runtime(root)

    continuity = p704.bootstrap_from_p6_owner_context(root, p6_context_file, service_principal_key=service_principal_key)
    organization = _identity(continuity["organization"])
    human = _identity(continuity["human_operator"])
    service = _identity(continuity["service_identity"])

    # This proof rotates the observer credential. Never apply it to another
    # service, even when explicitly selected or when it is the only enabled one.
    state = p704.load_access_store(root)
    grants = [g for g in state["grants"].values() if g["principal_key"] == p704._principal_key(service)]
    def observer_grant(g):
        return (g["operation"],g["resource"],g["access_paths"]) == ("runtime.health.observe","runtime:p7-02",["local"])
    if any(not observer_grant(g) for g in grants) or ((grants or service_principal_key is not None) and not any(observer_grant(g) and g["status"]=="active" for g in grants)):
        raise p704.IntegrityError("selected service is not an admitted runtime observer for credential rotation")

    human_cid, human_secret = _ensure_credential(root, human)
    service_cid, service_secret = _ensure_credential(root, service)

    # Persist only bounded operational grants. Remote status is explicit; remote
    # lifecycle mutation remains denied absent another exact grant.
    p704.grant_access(
        root, human, operation="runtime.status", resource="runtime:p7-02",
        access_paths=("local", "remote"),
    )
    p704.grant_access(
        root, service, operation="runtime.health.observe", resource="runtime:p7-02",
        access_paths=("local",),
    )

    human_local = p704.authorize(
        root, organization=organization, principal=human, credential_id=human_cid,
        credential_secret=human_secret, operation="runtime.status", resource="runtime:p7-02",
        access_path="local",
    )
    human_remote = p704.authorize(
        root, organization=organization, principal=human, credential_id=human_cid,
        credential_secret=human_secret, operation="runtime.status", resource="runtime:p7-02",
        access_path="remote",
    )
    remote_restart_denied = p704.authorize(
        root, organization=organization, principal=human, credential_id=human_cid,
        credential_secret=human_secret, operation="runtime.restart", resource="runtime:p7-02",
        access_path="remote",
    )
    service_allowed = p704.authorize(
        root, organization=organization, principal=service, credential_id=service_cid,
        credential_secret=service_secret, operation="runtime.health.observe", resource="runtime:p7-02",
        access_path="local",
    )
    service_admin_denied = p704.authorize(
        root, organization=organization, principal=service, credential_id=service_cid,
        credential_secret=service_secret, operation="runtime.restart", resource="runtime:p7-02",
        access_path="local",
    )
    if not (human_local.allowed and human_remote.allowed and service_allowed):
        raise p704.IntegrityError("required explicit least-privilege grants did not authorize")
    if remote_restart_denied.allowed or service_admin_denied.allowed:
        raise p704.IntegrityError("ambient/hidden admin path detected")

    # Exercise service credential rotation. The old material must stop working;
    # the replacement keeps only the exact already-granted operation.
    rotated = p704.rotate_credential(root, service, service_cid)
    new_service_secret = p704.read_credential_secret(Path(rotated["secret_path"]))
    old_after_rotation = p704.authorize(
        root, organization=organization, principal=service, credential_id=service_cid,
        credential_secret=service_secret, operation="runtime.health.observe", resource="runtime:p7-02",
        access_path="local",
    )
    new_after_rotation = p704.authorize(
        root, organization=organization, principal=service, credential_id=rotated["credential_id"],
        credential_secret=new_service_secret, operation="runtime.health.observe", resource="runtime:p7-02",
        access_path="local",
    )
    if old_after_rotation.allowed or old_after_rotation.reason != "CREDENTIAL_REVOKED" or not new_after_rotation.allowed:
        raise p704.IntegrityError("credential rotation did not fail closed")

    # Exercise grant revocation without removing the persistent operational grants.
    temporary_grant = p704.grant_access(
        root, human, operation="access.proof.revocable", resource="p7-04:self", access_paths=("local",),
    )
    before_revoke = p704.authorize(
        root, organization=organization, principal=human, credential_id=human_cid,
        credential_secret=human_secret, operation="access.proof.revocable", resource="p7-04:self",
        access_path="local",
    )
    p704.revoke_grant(root, temporary_grant)
    after_revoke = p704.authorize(
        root, organization=organization, principal=human, credential_id=human_cid,
        credential_secret=human_secret, operation="access.proof.revocable", resource="p7-04:self",
        access_path="local",
    )
    if not before_revoke.allowed or after_revoke.allowed:
        raise p704.IntegrityError("grant revocation did not take effect")

    summary = p704.verify_store(root)
    after = _runtime(root)
    if after["release_sha"] != before["release_sha"]:
        raise p704.IntegrityError("P7.02 runtime release changed during P7.04 proof")

    authority_decisions = (human_local, human_remote, service_allowed, new_after_rotation)
    if any(
        decision.organizational_authority_satisfied or decision.consequential_approval_satisfied
        for decision in authority_decisions
    ):
        raise p704.IntegrityError("operational access leaked authority semantics")

    attestation = {
        "schema": ATTESTATION_SCHEMA,
        "status": "PASS",
        "classification": "non-canonical operational proof evidence",
        "tool_release_sha": release_sha,
        "persistent_runtime_release_sha_before": before["release_sha"],
        "persistent_runtime_release_sha_after": after["release_sha"],
        "persistent_runtime_healthy_before_after": True,
        "p6_human_identity_reused": True,
        "persistent_human_attributable": summary["human_principals"] >= 1,
        "persistent_service_attributable": summary["service_principals"] >= 1,
        "deny_by_default": summary["default_access"] == "deny",
        "organization_scope_exact": True,
        "operation_resource_scope_exact": True,
        "local_access_explicit": human_local.allowed,
        "remote_administration_path_explicit": human_remote.allowed,
        "remote_lifecycle_admin_denied_without_grant": not remote_restart_denied.allowed,
        "service_ambient_admin_absent": not service_admin_denied.allowed,
        "credential_rotation_fail_closed": not old_after_rotation.allowed and new_after_rotation.allowed,
        "grant_revocation_fail_closed": before_revoke.allowed and not after_revoke.allowed,
        "reusable_secret_in_registry": False,
        "ambient_admin": summary["ambient_admin"],
        "organizational_authority_provided": summary["organizational_authority_provided"],
        "consequential_approval_provided": False,
        "raw_identity_values_emitted": False,
        "reusable_credentials_emitted": False,
        "canonical_mutation": False,
        "external_effects": False,
        "created_at": p703._utc_now(),
    }
    evidence_dir = root / "evidence"
    p703._ensure_private_dir(evidence_dir)
    evidence_path = evidence_dir / (
        f"p7-04-selected-mac-attestation-{p703._stamp()}-{uuid.uuid4().hex[:8]}.json"
    )
    p703._atomic_json_write(evidence_path, attestation)
    attestation["attestation_basename"] = evidence_path.name
    return attestation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Arvectum OS P7.04 selected-Mac closure proof")
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--p6-context-file", required=True)
    parser.add_argument("--release-sha", required=True)
    parser.add_argument("--service-principal-key", help="Exact existing enabled service key from local registry; required if ambiguous")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_selected_mac_proof(
            Path(args.runtime_root), Path(args.p6_context_file), args.release_sha,
            service_principal_key=args.service_principal_key,
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            print(f"P7.04 selected-Mac PASS attestation={result['attestation_basename']}")
        return 0
    except (p704.P704Error, p703.P703Error, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"P7.04 selected-Mac FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
