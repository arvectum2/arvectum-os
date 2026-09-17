#!/usr/bin/env python3
"""P7.06 governed deployment/version/migration preflight and evidence helpers.

Bounded owner-operated tooling only. This module does not grant Organizational
Authority, authorize canonical mutation, replay external effects, or establish a
public/stable deployment API. The macOS adapter owns the current concrete
stop/update/re-pin/start sequence; this module makes release identity, state-format
compatibility, migration disposition, and transaction evidence explicit/fail-closed.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

PLAN_SCHEMA = "arvectum.p7_06.deployment-plan/1"
TX_SCHEMA = "arvectum.p7_06.deployment-transaction/1"
MIGRATION_SCHEMA = "arvectum.p7_06.migration-plan/1"
OPERATING_MODE = "Persistent Internal / owner-operated"
ORGANIZATION_SCOPE = "ООО «Арвектум»"
CURRENT_CANONICAL_REPOSITORY = "arvectum2/arvectum-os"
LEGACY_CANONICAL_REPOSITORIES = frozenset({"arvectum/arvectum-os", "arvectum1/arvectum-os"})
REQUIRED_RELEASE_FILES = (
    "source/reference/python/p7_02_persistent_runtime.py",
    "source/reference/python/p7_02_macos_service.sh",
    "source/reference/python/p7_03_durable_state.py",
    "source/reference/python/p7_04_persistent_access.py",
    "source/reference/python/p7_05_operational_visibility.py",
    "source/reference/python/p7_05_macos_observer.sh",
)

class P706Error(RuntimeError):
    pass

class IntegrityError(P706Error):
    pass

class BoundaryError(P706Error):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_sha(value: str) -> str:
    value = value.strip().lower()
    if len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
        raise BoundaryError("release must be a full 40-character Git commit SHA")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise IntegrityError(f"expected JSON object: {path}")
    return value


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(path.parent, 0o700)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if os.name != "nt":
            os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def current_release(root: Path) -> str:
    link = root / "current"
    if not link.is_symlink():
        raise IntegrityError("runtime current release symlink is missing")
    target = os.readlink(link)
    return _validate_sha(Path(target).name)


def _literal_store_schema(module_path: Path) -> str:
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    except (OSError, SyntaxError) as exc:
        raise IntegrityError(f"cannot inspect target P7.03 STORE_SCHEMA: {exc}") from exc
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "STORE_SCHEMA":
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        return node.value.value
    raise IntegrityError("target P7.03 module has no literal STORE_SCHEMA")


def verify_release(
    root: Path,
    release_sha: str,
    *,
    allow_legacy_repository: bool = False,
) -> dict[str, Any]:
    release_sha = _validate_sha(release_sha)
    release = root / "releases" / release_sha
    if not release.is_dir() or release.is_symlink():
        raise IntegrityError(f"exact release is missing or invalid: {release}")
    manifest_path = release / "release-manifest.json"
    archive_path = release / "reference-python.tar"
    manifest = _load_json(manifest_path)
    admitted_repositories = {CURRENT_CANONICAL_REPOSITORY}
    if allow_legacy_repository:
        admitted_repositories.update(LEGACY_CANONICAL_REPOSITORIES)
    if manifest.get("canonical_repository") not in admitted_repositories:
        raise IntegrityError("release manifest canonical repository mismatch")
    if manifest.get("release_sha") != release_sha:
        raise IntegrityError("release manifest SHA mismatch")
    expected_archive = manifest.get("reference_python_archive_sha256")
    if not isinstance(expected_archive, str) or _sha256(archive_path) != expected_archive:
        raise IntegrityError("release archive checksum mismatch")
    for rel in REQUIRED_RELEASE_FILES:
        path = release / rel
        if not path.is_file() or path.is_symlink():
            raise IntegrityError(f"required exact-release file missing/invalid: {rel}")
    python = root / "venvs" / release_sha / "bin" / "python"
    if not python.is_file():
        raise IntegrityError(f"exact-release Python is missing: {python}")
    schema = _literal_store_schema(release / "source/reference/python/p7_03_durable_state.py")
    return {"release_sha": release_sha, "store_schema": schema, "verified": True}


def _live_store_schema(root: Path) -> str:
    config = _load_json(root / "config" / "p7-03-recovery.json")
    value = config.get("store_schema")
    if not isinstance(value, str) or not value:
        raise IntegrityError("P7.03 recovery config has no valid store_schema")
    return value


def _migration_disposition(root: Path, source: str, target: str, target_schema: str, migration_plan: Optional[Path]) -> dict[str, Any]:
    live_schema = _live_store_schema(root)
    if live_schema == target_schema:
        if migration_plan is not None:
            raise BoundaryError("migration plan supplied although state schema is unchanged")
        return {
            "mode": "none",
            "source_store_schema": live_schema,
            "target_store_schema": target_schema,
            "rollback_safe": True,
            "external_effect_replay_authorized": False,
            "reason": "P7.03 durable store schema is unchanged; release re-pin rollback is allowed",
        }
    if migration_plan is None:
        raise BoundaryError(
            f"state schema change {live_schema!r} -> {target_schema!r} requires an explicit P7.06 migration plan"
        )
    plan = _load_json(migration_plan)
    if plan.get("schema") != MIGRATION_SCHEMA:
        raise BoundaryError("unexpected migration plan schema")
    if plan.get("source_release") != source or plan.get("target_release") != target:
        raise BoundaryError("migration plan release identities do not match deployment")
    if plan.get("source_store_schema") != live_schema or plan.get("target_store_schema") != target_schema:
        raise BoundaryError("migration plan store-schema identities do not match deployment")
    if plan.get("external_effects") is not False or plan.get("historical_effect_replay") is not False:
        raise BoundaryError("P7.06 migration plans must not invoke/replay product or external consequential effects")
    if plan.get("reversible") is not True:
        raise BoundaryError("current P7.06 owner-operated baseline refuses irreversible migration")
    raise BoundaryError(
        "schema-changing migration is explicitly described but no governed migration executor is admitted yet; "
        "add a bounded exact-release executor + rollback proof before deployment"
    )


def build_plan(root: Path, target_release: str, decision_ref: str, migration_plan: Optional[Path] = None) -> dict[str, Any]:
    root = root.expanduser().resolve()
    decision_ref = decision_ref.strip()
    if not decision_ref:
        raise BoundaryError("operator/decision reference is required")
    source = current_release(root)
    target = _validate_sha(target_release)
    if source == target:
        raise BoundaryError("target release is already current")
    source_info = verify_release(root, source, allow_legacy_repository=True)
    target_info = verify_release(root, target)
    migration = _migration_disposition(root, source, target, target_info["store_schema"], migration_plan)
    body = {
        "schema": PLAN_SCHEMA,
        "operating_mode": OPERATING_MODE,
        "organization_scope": ORGANIZATION_SCOPE,
        "source_release": source,
        "target_release": target,
        "source_store_schema": source_info["store_schema"],
        "target_store_schema": target_info["store_schema"],
        "operator_decision_ref": decision_ref,
        "migration": migration,
        "required_sequence": [
            "verify-exact-releases",
            "classify-workspace-listener",
            "pre-update-backup",
            "conditionally-stop-known-workspace-listener",
            "stop-observer",
            "stop-runtime",
            "activate-target-release",
            "re-pin-observer",
            "verify-runtime-exact-release-health",
            "verify-observer-loaded-exact-release-pin",
            "conditionally-start-and-verify-exact-target-workspace-listener",
        ],
        "canonical_mutation_authorized_by_plan": False,
        "organizational_authority_satisfied_by_plan": False,
        "external_effect_replay_authorized": False,
        "created_at": _utc_now(),
    }
    plan_id = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    value = {**body, "plan_id": plan_id}
    path = root / "evidence" / "p7-06" / "plans" / f"{plan_id}.json"
    if path.exists():
        if _load_json(path) != value:
            raise IntegrityError("immutable deployment-plan collision")
    else:
        _atomic_json(path, value)
    return value


def record_transaction(root: Path, payload_path: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    payload = _load_json(payload_path)
    required = {
        "plan_id", "source_release", "target_release", "result", "backup_path", "backup_sha256",
        "runtime_release_verified", "observer_release_verified", "workspace_listener_disposition", "rollback_disposition",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise BoundaryError(f"transaction payload missing fields: {missing}")
    if payload["result"] not in {"PASS", "ROLLED_BACK", "FAIL"}:
        raise BoundaryError("invalid transaction result")
    backup = Path(str(payload["backup_path"])).expanduser().resolve()
    backup_root = (root / "backups").resolve()
    if backup.parent != backup_root or not backup.is_file():
        raise BoundaryError("transaction backup must be an existing owner-local P7.03 backup")
    declared_backup_sha = str(payload["backup_sha256"]).strip().lower()
    if len(declared_backup_sha) != 64 or any(ch not in "0123456789abcdef" for ch in declared_backup_sha):
        raise BoundaryError("transaction backup_sha256 must be a full SHA-256")
    if _sha256(backup) != declared_backup_sha:
        raise IntegrityError("transaction backup SHA-256 does not match the retained archive")
    source = _validate_sha(str(payload["source_release"]))
    target = _validate_sha(str(payload["target_release"]))
    plan_path = root / "evidence" / "p7-06" / "plans" / f"{payload['plan_id']}.json"
    plan = _load_json(plan_path)
    if plan.get("source_release") != source or plan.get("target_release") != target:
        raise BoundaryError("transaction does not match immutable deployment plan")
    value = {
        "schema": TX_SCHEMA,
        "operating_mode": OPERATING_MODE,
        "organization_scope": ORGANIZATION_SCOPE,
        **payload,
        "canonical_authority": False,
        "external_effect_replay_authorized": False,
        "recorded_at": _utc_now(),
    }
    tx_id = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    value["transaction_id"] = tx_id
    tx_path = root / "evidence" / "p7-06" / "transactions" / f"{tx_id}.json"
    _atomic_json(tx_path, value)
    _atomic_json(root / "run" / "p7-06-last-transaction.json", {"transaction_id": tx_id, "path": str(tx_path), "result": payload["result"]})
    return value


def status(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    current = current_release(root)
    info = verify_release(root, current, allow_legacy_repository=True)
    pointer = root / "run" / "p7-06-last-transaction.json"
    last = _load_json(pointer) if pointer.exists() else None
    return {"current_release": current, "store_schema": info["store_schema"], "last_transaction": last}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Arvectum OS P7.06 governed deploy/update/version/migration helper")
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--runtime-root", required=True)
    pre.add_argument("--target-release", required=True)
    pre.add_argument("--decision-ref", required=True)
    pre.add_argument("--migration-plan")
    pre.add_argument("--json", action="store_true")
    rec = sub.add_parser("record")
    rec.add_argument("--runtime-root", required=True)
    rec.add_argument("--payload", required=True)
    rec.add_argument("--json", action="store_true")
    sta = sub.add_parser("status")
    sta.add_argument("--runtime-root", required=True)
    sta.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "preflight":
            value = build_plan(Path(args.runtime_root), args.target_release, args.decision_ref, Path(args.migration_plan) if args.migration_plan else None)
        elif args.command == "record":
            value = record_transaction(Path(args.runtime_root), Path(args.payload))
        else:
            value = status(Path(args.runtime_root))
    except P706Error as exc:
        print(f"P7.06 FAIL: {exc}", file=os.sys.stderr)
        return 1
    if getattr(args, "json", False):
        print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    else:
        print(f"P7.06 {args.command} PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
