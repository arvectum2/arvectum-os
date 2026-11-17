"""Offline, explicitly authorized 0.6.1 migration; no grants or network actions.

Use only after Workspace is stopped and the daily backup job is quiescent.
The receipt is removed first and installed last; interruption fails closed.
The caller retains the independent encrypted rollback archive, never in Git.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

from .wsf_manual_context import ManualContextError, _digest, _json
from .wsf_manual_policy import _private_file
from .wsf_manual_backup import PilotBackup
from .wsf_inbox_routes import INBOX_PARTS
from .wsf_inbox_runtime import (
    APPROVED_DRAFT, SUCCESSOR_DRAFT, PREDECESSOR_REGISTRY, SUCCESSOR_REGISTRY,
    SUCCESSOR_PATH, OPERATIONS, RuntimeInboxPilot,
)
from .wsf_roadmap_inbox import RoadmapInbox, registry_bindings
from .wsf_inbox_registry_preview import preview_resolved_bindings


def atomic(path, raw):
    """Use a new private file, fsync contents and parent; never follow symlinks."""
    path = Path(path)
    if path.resolve() != path or path.parent.resolve() != path.parent:
        raise ManualContextError("unsafe migration path")
    fd, name = tempfile.mkstemp(prefix=".migration-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
        syncdir(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def syncdir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_archive(directory, docs):
    directory.mkdir(mode=0o700, exist_ok=False)
    for name, raw in docs.items():
        atomic(directory / name, raw)
    atomic(directory / "sha256.json", _json({k: _digest(v) for k, v in docs.items()}))
    syncdir(directory.parent)


def plan(root, access, *, backup_factory=None):
    """Validate actual predecessor gates and prepare exact in-memory replacement."""
    root = Path(root)
    pilot = RuntimeInboxPilot(root, successor_draft=None)
    for operation in OPERATIONS:
        pilot.authorize(access, operation)
    source = pilot.authorize(access, "export")
    if source.file.binding_digest != PREDECESSOR_REGISTRY:
        raise ManualContextError("wrong predecessor registry")
    backup_factory = backup_factory or (lambda store: PilotBackup(store, parts=INBOX_PARTS))
    primary = source.export(access)
    backup = backup_factory(source.file).verified_snapshot(access)
    if primary != backup:
        raise ManualContextError("backup not current")
    policy = _private_file(root / "config" / "roadmap-inbox-policy.json")
    receipt = _private_file(root / "config" / "roadmap-inbox-activation.json")
    doc = json.loads(policy)
    pin = json.loads(receipt)
    if doc["draft_blob"] != APPROVED_DRAFT or pin["draft_blob"] != APPROVED_DRAFT or pin["policy_sha256"] != _digest(policy):
        raise ManualContextError("wrong predecessor approval")
    with tempfile.TemporaryDirectory(prefix="inbox-locator-preview-", dir=root) as temp:
        new = RoadmapInbox(Path(temp) / "target", access, bindings=registry_bindings(SUCCESSOR_PATH))
        if new.file.binding_digest != SUCCESSOR_REGISTRY:
            raise ManualContextError("wrong successor registry")
        candidate, evidence = preview_resolved_bindings(access, source, new)
        if evidence["source_sha256"] != _digest(primary):
            raise ManualContextError("source changed during preparation")
        new.restore_empty(access, candidate)
        if new.export(access) != candidate:
            raise ManualContextError("restore verification failed")
    doc["draft_blob"] = SUCCESSOR_DRAFT
    doc["registry_sha256"] = SUCCESSOR_REGISTRY
    newpolicy = _json(doc)
    newreceipt = _json({**pin, "draft_blob": SUCCESSOR_DRAFT, "policy_sha256": _digest(newpolicy)})
    return {"inbox.json": primary, "backup.json": backup, "policy.json": policy, "receipt.json": receipt}, {
        "inbox.json": candidate, "backup.json": candidate, "policy.json": newpolicy, "receipt.json": newreceipt,
    }, evidence


def replace_set(paths, docs, *, write=atomic):
    """Receipt must be absent while writing all other files."""
    receipt = paths["receipt.json"]
    if receipt.is_symlink():
        raise ManualContextError("unsafe receipt")
    receipt.unlink(missing_ok=True)
    syncdir(receipt.parent)
    for key in ("inbox.json", "backup.json", "policy.json"):
        write(paths[key], docs[key])
    write(receipt, docs["receipt.json"])


def cutover(root, access, archive, *, assert_quiescent, confirm, backup_factory=None, write=atomic):
    """Selected-device offline operator only. No automatic rollback on later edits.

    Caller must prove the actual service and backup job are stopped throughout,
    and supply an independently verified encrypted private archive directory.
    """
    if not confirm:
        raise ManualContextError("explicit cutover confirmation required")
    root, archive = Path(root), Path(archive)
    assert_quiescent()
    old, new, evidence = plan(root, access, backup_factory=backup_factory)
    oldpilot = RuntimeInboxPilot(root, successor_draft=None)
    store = oldpilot.authorize(access, "export")
    factory = backup_factory or (lambda s: PilotBackup(s, parts=INBOX_PARTS))
    b = factory(store.file)
    # backup destination validated by existing volume identity and permission gate.
    with b._destination() as fd:
        backup_dir = b.volume.joinpath(*b.parts)
        if archive.parent != backup_dir or archive.resolve()!=archive:
            raise ManualContextError("rollback archive must be in verified backup destination")
        paths = {
            "inbox.json": store.file.path, "backup.json": backup_dir / "latest.private.json",
            "policy.json": root / "config" / "roadmap-inbox-policy.json",
            "receipt.json": root / "config" / "roadmap-inbox-activation.json",
        }
        with store.file._locked():
            assert_quiescent()
            if (store.file._encode(store.file._load()) != old["inbox.json"]
                or b._read(fd) != old["backup.json"]
                or any(_private_file(paths[k]) != old[k] for k in ("policy.json", "receipt.json"))):
                raise ManualContextError("concurrent predecessor change")
            write_archive(archive, old)
            # Hold the store lock while replacing all files, including receipt.
            try:
                replace_set(paths, new, write=write)
                assert_quiescent()
                if (paths["inbox.json"].read_bytes() != new["inbox.json"] or b._read(fd) != new["backup.json"]
                    or any(_private_file(paths[k]) != new[k] for k in ("policy.json","receipt.json"))):
                    raise ManualContextError("successor bytes mismatch")
            except Exception:
                replace_set(paths, old)
                raise
    try:
        for op in OPERATIONS:
            RuntimeInboxPilot(root).authorize(access, op)
        if RuntimeInboxPilot(root).read(access)["backup_status"]!="verified":
            raise ManualContextError("successor backup not verified")
        assert_quiescent()
    except Exception:
        # A service must remain stopped. Do not overwrite post-cutover writes.
        assert_quiescent()
        if paths["inbox.json"].read_bytes() != new["inbox.json"] or paths["backup.json"].read_bytes()!=new["backup.json"]:
            raise ManualContextError("successor changed; manual recovery required") from None
        replace_set(paths, old)
        raise
    return {**evidence,"status":"migrated","grants_unchanged":True,"expiry_unchanged":True}
