"""WSF-04C backup candidate. No provisioner, scheduler or live wiring.

Only a separately approved offline/operator path may construct this for
production. Directory must already exist; mount failure never creates paths.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import plistlib
import stat
import subprocess
from uuid import uuid4

from .wsf_manual_context import ManualContextError, ManualContextStore, MAX_BYTES

VOLUME = Path("/Volumes/ArvectumSSD")
VOLUME_UUID = "88D0A566-E762-4ACC-9CC7-B01D1EBC29E1"
BACKUP_PARTS = ("Arvectum", "backups", "arvectum-os", "manual-context")
BACKUP_NAME = "latest.private.json"


def verify_volume(volume: Path, uuid: str):
    try:
        raw = subprocess.check_output(["/usr/sbin/diskutil", "info", "-plist", str(volume)],
                                      timeout=5, stderr=subprocess.DEVNULL)
        info = plistlib.loads(raw)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise ManualContextError("backup volume unavailable") from exc
    if (info.get("MountPoint") != str(volume) or info.get("VolumeUUID") != uuid
            or info.get("FilesystemType") != "apfs" or info.get("Internal") is not False
            or info.get("Writable") is not True or info.get("Encryption") is not True):
        raise ManualContextError("backup volume identity or handling mismatch")


class PilotBackup:
    """One bounded latest snapshot on the selected encrypted external device."""

    def __init__(self, store: ManualContextStore, *, volume=VOLUME, uuid=VOLUME_UUID,
                 parts=BACKUP_PARTS, verifier=verify_volume):
        self.store = store
        self.volume = Path(volume)
        self.uuid = uuid
        self.parts = tuple(parts)
        self.verifier = verifier
        if not self.volume.is_absolute() or not self.parts or any(
                not x or x in (".", "..") or "/" in x for x in self.parts):
            raise ManualContextError("invalid backup path")

    @contextmanager
    def _destination(self):
        self.verifier(self.volume, self.uuid)
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        fd = os.open(self.volume, flags)
        try:
            device = os.fstat(fd).st_dev
            # Recheck mount after obtaining a descriptor. Never traverse a symlink
            # or mount crossing. The production default must be a separate device.
            self.verifier(self.volume, self.uuid)
            if self.volume.stat().st_dev != device:
                raise ManualContextError("backup mount changed")
            if self.verifier is verify_volume and self.store.directory.stat().st_dev == device:
                raise ManualContextError("backup is not a separate device")
            for part in self.parts:
                child = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = child
                if os.fstat(fd).st_dev != device:
                    raise ManualContextError("backup path crossed a mount")
            s = os.fstat(fd)
            if s.st_uid != os.getuid() or s.st_mode & 0o077:
                raise ManualContextError("backup directory not private")
            yield fd
        finally:
            os.close(fd)

    @staticmethod
    def _read(fd):
        filefd = os.open(BACKUP_NAME, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        with os.fdopen(filefd, "rb") as f:
            s = os.fstat(f.fileno())
            if not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077 or s.st_nlink != 1:
                raise ManualContextError("unsafe backup file")
            raw = f.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ManualContextError("backup too large")
            return raw

    def copy_latest(self, access):
        self.store._authorize(access)
        # Serialize with primary writes and competing backup runs; the previous
        # complete copy is retained until the new one is durable and validated.
        with self.store._locked():
            if not self.store.path.is_file():
                raise ManualContextError("primary snapshot missing")
            raw = self.store._encode(self.store._load())
            self.store._decode(raw)
            with self._destination() as fd:
                try:
                    previous = self._read(fd)
                except FileNotFoundError:
                    previous = None
                if previous is not None:
                    old = self.store._decode(previous)
                    new = self.store._decode(raw)
                    if new[:len(old)] != old:
                        raise ManualContextError("backup history diverges from primary")
                    if previous == raw:
                        return {"status": "verified-current", "bytes": len(raw)}
                if os.fstatvfs(fd).f_bavail * os.fstatvfs(fd).f_frsize < MAX_BYTES * 2:
                    raise ManualContextError("backup free space insufficient")
                name = ".latest-" + uuid4().hex
                try:
                    filefd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                    with os.fdopen(filefd, "wb") as f:
                        f.write(raw)
                        f.flush()
                        os.fsync(f.fileno())
                    self.verifier(self.volume, self.uuid)
                    os.replace(name, BACKUP_NAME, src_dir_fd=fd, dst_dir_fd=fd)
                    os.fsync(fd)
                    if self._read(fd) != raw:
                        raise ManualContextError("backup verification failed")
                    return {"status": "verified-copy", "bytes": len(raw)}
                finally:
                    try:
                        os.unlink(name, dir_fd=fd)
                    except FileNotFoundError:
                        pass

    def verified_snapshot(self, access):
        self.store._authorize(access)
        with self._destination() as fd:
            raw = self._read(fd)
            self.store._decode(raw)
            return raw
