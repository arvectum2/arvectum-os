#!/usr/bin/env python3
"""P7.05 selected-Mac health/observability/alerting/retention closure proof."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import plistlib
import subprocess
import sys
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional

from arvectum_os_ref.identity import Identity
import p7_03_durable_state as p703
import p7_04_persistent_access as p704
import p7_05_operational_visibility as p705

ATTESTATION_SCHEMA = "arvectum.p7_05.selected-mac-attestation/1"
OBSERVER_LABEL = "com.arvectum.os.p7-05-observer"


def _identity(raw: dict[str, str]) -> Identity:
    return Identity(raw["namespace"], raw["value"], raw["scope"])


def _active_credential(root: Path, principal: Identity) -> tuple[str, str] | None:
    state = p704.load_access_store(root)
    key = p704._principal_key(principal)
    active = [c for c in state["credentials"].values()
              if c["principal_key"] == key and c["status"] == "active"]
    if len(active) > 1:
        raise p704.IntegrityError("multiple active credentials for P7.05 operator")
    if not active:
        return None
    cid = active[0]["credential_id"]
    return cid, p704.read_credential_secret(p704._secret_path(root, cid))


def _ensure_credential(root: Path, principal: Identity) -> tuple[str, str]:
    active = _active_credential(root, principal)
    if active:
        return active
    issued = p704.issue_credential(root, principal)
    return issued["credential_id"], p704.read_credential_secret(Path(issued["secret_path"]))


def _tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    if not path.exists():
        return digest.hexdigest()
    for item in sorted(path.rglob("*")):
        if item.is_symlink():
            raise p705.IntegrityError(f"symlink not allowed in protected governed tree: {item}")
        relative = item.relative_to(path).as_posix().encode()
        digest.update(relative)
        digest.update(b"\0")
        if item.is_file():
            digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _macos_observer_state(root: Path, release_sha: str) -> Optional[dict[str, Any]]:
    """Inspect launchd state and exact-release pin on macOS; non-macOS fixtures return None."""
    if platform.system() != "Darwin":
        return None
    target = f"gui/{os.getuid()}/{OBSERVER_LABEL}"
    try:
        completed = subprocess.run(
            ["launchctl", "print", target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise p705.IntegrityError(f"cannot inspect P7.05 launchd observer: {exc}") from exc
    if completed.returncode != 0:
        return {"loaded": False, "exact_release_pinned": False}

    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{OBSERVER_LABEL}.plist"
    try:
        with plist_path.open("rb") as handle:
            payload = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException) as exc:
        raise p705.IntegrityError(f"cannot inspect P7.05 observer LaunchAgent: {exc}") from exc

    args = payload.get("ProgramArguments")
    expected_python = str(root / "venvs" / release_sha / "bin" / "python")
    expected_script = str(
        root / "releases" / release_sha / "source" / "reference" / "python" /
        "p7_05_operational_visibility.py"
    )
    exact = (
        isinstance(args, list)
        and len(args) >= 2
        and args[0] == expected_python
        and args[1] == expected_script
        and "/current/" not in args[1]
    )
    return {
        "loaded": True,
        "exact_release_pinned": exact,
        "expected_python": expected_python,
        "expected_script": expected_script,
    }


def run_selected_mac_proof(root: Path, p6_context_file: Path, release_sha: str, *, service_principal_key: Optional[str] = None) -> dict[str, Any]:
    release_sha = p703._validate_release_sha(release_sha)
    root = root.expanduser().resolve()
    p705.initialize(root)

    observer = _macos_observer_state(root, release_sha)
    if observer is not None and observer["loaded"] is False:
        raise p705.IntegrityError("P7.05 selected-Mac proof requires the launchd observer to be loaded")
    if observer is not None and observer["exact_release_pinned"] is False:
        raise p705.IntegrityError("P7.05 launchd observer is not pinned to the exact proof release")

    current = p705.classify_health(root)
    if current.state != "healthy":
        raise p705.IntegrityError(f"selected-Mac runtime is not healthy: {current.code}")
    if current.release_sha != release_sha:
        raise p705.IntegrityError(
            f"selected-Mac runtime release mismatch: health={current.release_sha} proof={release_sha}"
        )

    continuity = p704.bootstrap_from_p6_owner_context(root, p6_context_file, service_principal_key=service_principal_key)
    organization = _identity(continuity["organization"])
    human = _identity(continuity["human_operator"])
    cid, secret = _ensure_credential(root, human)
    p704.grant_access(
        root, human, operation="audit.inspect", resource="state:governed",
        access_paths=("local",),
    )
    decision = p704.authorize(
        root, organization=organization, principal=human,
        credential_id=cid, credential_secret=secret,
        operation="audit.inspect", resource="state:governed", access_path="local",
    )
    if not decision.allowed:
        raise p705.IntegrityError("exact P7.04 audit visibility grant did not authorize")
    audit = p705.audit_visibility(root, decision, limit=100)

    # Exercise actionable alert creation and healthy clearing without perturbing
    # the real runtime. The alert itself is non-canonical owner-local state.
    simulated = p705.HealthStatus(
        "degraded", "PROOF_DEGRADED", "bounded P7.05 alert-path proof",
        "operator would inspect health details; no canonical action is automatic",
        current.release_sha, current.heartbeat_age_seconds,
    )
    alert = p705.publish_health_signal(root, simulated)
    alert_path = root / "run" / "p7-05-alert.json"
    if not alert or not alert_path.exists() or alert.get("operator_action") == "":
        raise p705.IntegrityError("actionable alert was not published")
    p705.publish_health_signal(root, current)
    if alert_path.exists():
        raise p705.IntegrityError("healthy signal did not clear transient alert")

    # Exercise retention against a deliberately old telemetry record while
    # fingerprinting the governed tree. Cleanup is allow-listed and must not
    # traverse canonical/governed state.
    old_at = (p705._utc_now_dt() - timedelta(hours=p705.DEFAULT_RETENTION_HOURS + 2)).isoformat().replace("+00:00", "Z")
    p705.emit_telemetry(root, event="proof.retention.old", recorded_at=old_at,
                        attributes={"component": "p7-05-proof", "status": "expired"})
    p705.emit_telemetry(root, event="proof.retention.current",
                        attributes={"component": "p7-05-proof", "status": "current"})
    protected_before = _tree_digest(root / "state" / "governed")
    cleanup = p705.cleanup(root)
    protected_after = _tree_digest(root / "state" / "governed")
    if cleanup["removed_telemetry_records"] < 1:
        raise p705.IntegrityError("retention proof did not remove expired telemetry")
    if protected_before != protected_after or cleanup["canonical_state_deleted"]:
        raise p705.IntegrityError("telemetry cleanup changed governed state")

    status = p705.operational_status(root)
    if status["state"] != "healthy" or status["active_alert"] is not None:
        raise p705.IntegrityError("final selected-Mac status is not healthy")
    if status["release_sha"] != release_sha:
        raise p705.IntegrityError("final selected-Mac status no longer matches the exact proof release")

    policy = p705.load_policy(root)
    attestation = {
        "schema": ATTESTATION_SCHEMA,
        "status": "PASS",
        "classification": "non-canonical operational proof evidence",
        "tool_release_sha": release_sha,
        "persistent_runtime_release_sha": status["release_sha"],
        "healthy_degraded_down_classifier_present": True,
        "final_runtime_state": status["state"],
        "structured_jsonl_telemetry_verified": True,
        "telemetry_canonical_authority": False,
        "audit_visibility_authorized_by_exact_p7_04_grant": True,
        "audit_projection_payload_bytes_exposed": audit["payload_bytes_exposed"],
        "audit_projection_count": audit["count"],
        "actionable_alert_path_verified": True,
        "healthy_alert_clear_verified": True,
        "macos_observer_loaded": None if observer is None else observer["loaded"],
        "macos_observer_exact_release_pinned": None if observer is None else observer["exact_release_pinned"],
        "observer_required_on_selected_macos": platform.system() == "Darwin",
        "retention_hours": policy["retention_hours"],
        "expired_telemetry_removed": cleanup["removed_telemetry_records"],
        "governed_tree_hash_unchanged_by_cleanup": protected_before == protected_after,
        "canonical_state_deleted_by_cleanup": cleanup["canonical_state_deleted"],
        "evidence_deleted_by_cleanup": cleanup["evidence_deleted"],
        "payload_logging": policy["payload_logging"],
        "reusable_secret_logging": policy["reusable_secret_logging"],
        "raw_diagnostics_authority": policy["raw_diagnostics_authority"],
        "canonical_mutation": False,
        "external_effects": False,
        "created_at": p705._utc_now(),
    }
    evidence = root / "evidence"
    p703._ensure_private_dir(evidence)
    path = evidence / f"p7-05-selected-mac-attestation-{p703._stamp()}-{uuid.uuid4().hex[:8]}.json"
    p703._atomic_json_write(path, attestation)
    attestation["attestation_basename"] = path.name
    return attestation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Arvectum OS P7.05 selected-Mac closure proof")
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
            print(f"P7.05 selected-Mac PASS attestation={result['attestation_basename']}")
        return 0
    except (p705.P705Error, p704.P704Error, p703.P703Error, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"P7.05 selected-Mac FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
