from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
import plistlib

from test_wsf_manual_context import access
from workspace_app.wsf_manual_context import ManualContextStore, ManualContextError
from workspace_app.wsf_manual_backup import PilotBackup, verify_volume, BACKUP_NAME


class BackupCandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.a = access()
        self.store = ManualContextStore(self.root / "primary", self.a)
        self.volume = self.root / "fixture-volume"
        self.volume.mkdir(mode=0o700)
        self.dest = self.volume / "backup"
        self.dest.mkdir(mode=0o700)
        self.mounted = True
        def check(volume, uuid):
            if not self.mounted or uuid != "fixture":
                raise ManualContextError("volume unavailable")
        self.backup = PilotBackup(self.store, volume=self.volume, uuid="fixture", parts=("backup",), verifier=check)

    def note(self, title="Synthetic"):
        return self.store.submit(self.a, uuid4().hex, "capture",
                                 {"title": title, "text": "Fixture", "project_id": None})

    def test_bounded_latest_and_restore(self):
        self.note()
        self.assertEqual(self.backup.copy_latest(self.a)["status"], "verified-copy")
        self.assertEqual(self.backup.copy_latest(self.a)["status"], "verified-current")
        self.note("Second")
        self.assertEqual(self.backup.copy_latest(self.a)["status"], "verified-copy")
        self.assertEqual(list(self.dest.iterdir()), [self.dest / BACKUP_NAME])
        self.assertEqual((self.dest / BACKUP_NAME).stat().st_mode & 0o777, 0o600)
        restored = ManualContextStore(self.root / "restore", self.a)
        restored.restore_empty(self.a, self.backup.verified_snapshot(self.a))
        self.assertEqual(restored.read(self.a), self.store.read(self.a))
        self.assertEqual(restored.export(self.a), self.store.export(self.a))

    def test_unmounted_never_creates_or_overwrites(self):
        self.note()
        self.backup.copy_latest(self.a)
        previous = (self.dest / BACKUP_NAME).read_bytes()
        self.note("Second")
        self.mounted = False
        with self.assertRaises(ManualContextError):
            self.backup.copy_latest(self.a)
        self.assertEqual((self.dest / BACKUP_NAME).read_bytes(), previous)

    def test_missing_directory_never_created(self):
        self.note()
        self.dest.rmdir()
        with self.assertRaises(OSError):
            self.backup.copy_latest(self.a)
        self.assertFalse(self.dest.exists())

    def test_symlink_and_wrong_permissions_denied(self):
        self.note()
        self.dest.chmod(0o755)
        with self.assertRaises(ManualContextError):
            self.backup.copy_latest(self.a)
        self.dest.rmdir()
        actual = self.volume / "elsewhere"
        actual.mkdir(mode=0o700)
        self.dest.symlink_to(actual)
        with self.assertRaises(OSError):
            self.backup.copy_latest(self.a)
        self.assertEqual(list(actual.iterdir()), [])

    def test_corrupt_or_diverged_previous_copy_preserved(self):
        self.note()
        self.backup.copy_latest(self.a)
        path = self.dest / BACKUP_NAME
        path.write_bytes(b"corrupt")
        with self.assertRaises(ManualContextError):
            self.backup.copy_latest(self.a)
        self.assertEqual(path.read_bytes(), b"corrupt")
        other = ManualContextStore(self.root / "different", self.a)
        other.submit(self.a, uuid4().hex, "capture", {"title":"Other","text":"Fixture","project_id":None})
        raw = other.export(self.a)
        path.write_bytes(raw)
        with self.assertRaises(ManualContextError):
            self.backup.copy_latest(self.a)
        self.assertEqual(path.read_bytes(), raw)

    def test_scope_denial(self):
        self.note()
        with self.assertRaises(ManualContextError):
            self.backup.copy_latest(access(actor="foreign"))
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_real_volume_metadata_validation(self):
        good = dict(MountPoint="/Volumes/ArvectumSSD", VolumeUUID="id", FilesystemType="apfs",
                    Internal=False, Writable=True, Encryption=True)
        with patch("workspace_app.wsf_manual_backup.subprocess.check_output", return_value=plistlib.dumps(good)):
            verify_volume(Path("/Volumes/ArvectumSSD"), "id")
        for k, v in (("VolumeUUID","different"), ("MountPoint","/"), ("Encryption",False),
                     ("Internal",True),("Writable",False),("FilesystemType","other")):
            with patch("workspace_app.wsf_manual_backup.subprocess.check_output",
                       return_value=plistlib.dumps({**good,k:v})):
                with self.assertRaises(ManualContextError):
                    verify_volume(Path("/Volumes/ArvectumSSD"), "id")
