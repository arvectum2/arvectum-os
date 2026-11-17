"""CRM-specific backup candidate reusing the existing bounded snapshot protocol.

No live provisioning or schedule. Separate destination; never use notes backup.
"""
from .wsf_manual_backup import PilotBackup, VOLUME, VOLUME_UUID, verify_volume

CRM_PARTS = ("Arvectum", "backups", "arvectum-os", "crm-lite")


class _Snapshot:
    def __init__(self, store):
        self.store = store
        self.directory = store.directory
        self.path = store.path
        self._authorize = store._auth
        self._locked = store._lock
        self._load = store._load
        self._encode = store._encode
        self._decode = store._decode


def crm_backup(store, *, volume=VOLUME, uuid=VOLUME_UUID, parts=CRM_PARTS, verifier=verify_volume):
    if tuple(parts) == ("Arvectum", "backups", "arvectum-os", "manual-context"):
        raise ValueError("CRM backup cannot use manual-context destination")
    return PilotBackup(_Snapshot(store), volume=volume, uuid=uuid, parts=parts, verifier=verifier)
