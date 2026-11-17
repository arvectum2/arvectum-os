"""WSF-04C bounded runtime composition. Nothing is enabled by installation.

An explicit owner-local activation receipt pins the approved policy. It is
re-read for every operation; removal disables use without deleting data.
"""
from pathlib import Path
import json
from .wsf_manual_context import ManualContextError
from .wsf_manual_policy import ManualPolicyGate, _private_file
from .wsf_manual_backup import PilotBackup

APPROVED_DRAFT = "124c2e3b7bee7e89109d5f27d1d0f4f79fb3f7b2"
ACTIVATION_SCHEMA = "arvectum.workspace.manual-context-activation/1"
APPROVAL_DECISION = "DECISION-2026-11-17-WSF-04C-PROVISIONAL-APPROVAL"
ACTIVATION_FILE = "manual-context-activation.json"
API_OPERATIONS = {
    "project": "workspace.context.project", "capture": "workspace.context.capture",
    "revise": "workspace.context.revise", "read": "workspace.context.read",
    "export": "workspace.context.export",
}


class RuntimeManualPilot:
    def __init__(self, runtime_root: Path):
        self.root = Path(runtime_root)

    def authorize_operation(self, access, operation):
        exact = API_OPERATIONS.get(operation)
        if exact is None:
            raise ManualContextError("operation unavailable")
        try:
            receipt = json.loads(_private_file(self.root / "config" / ACTIVATION_FILE))
            if (not isinstance(receipt, dict) or set(receipt) != {
                    "schema", "draft_blob", "decision", "policy_sha256"}
                or receipt["schema"] != ACTIVATION_SCHEMA
                or receipt["draft_blob"] != APPROVED_DRAFT
                or receipt["decision"] != APPROVAL_DECISION):
                raise ManualContextError("activation unavailable")
            return ManualPolicyGate(self.root, receipt["policy_sha256"], APPROVED_DRAFT).authorize(access, exact)
        except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
            raise ManualContextError("manual pilot unavailable") from exc

    def backup(self, access):
        store = self.authorize_operation(access, "export")
        return PilotBackup(store).copy_latest(access)

    def read(self, access):
        store = self.authorize_operation(access, "read")
        data = store.read(access)
        try:
            backup_store = self.authorize_operation(access, "export")
            raw = PilotBackup(backup_store).verified_snapshot(access)
            status = "verified" if raw == store.export(access) else "stale"
        except (ManualContextError, OSError):
            status = "unavailable"
        return {**data, "backup_status": status}

    def submit(self, access, key, operation, payload):
        # Internal primary is authoritative; the two physical devices do not
        # provide a shared transaction. Require a verified pre-write copy,
        # then report a post-write backup failure explicitly without retrying
        # the saved business operation or discarding its idempotency key.
        store = self.authorize_operation(access, operation)
        backup_store = self.authorize_operation(access, "export")
        if store.path != backup_store.path:
            raise ManualContextError("backup scope mismatch")
        backup = PilotBackup(backup_store)
        backup.copy_latest(access)
        store = self.authorize_operation(access, operation)
        result = store.submit(access, key, operation, payload)
        try:
            self.backup(access)
            return {**result, "backup_status": "verified"}
        except (ManualContextError, OSError):
            return {**result, "backup_status": "saved-primary-backup-unavailable"}
