"""Verify the immutable publication gate without production data or services."""
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workspace_app.wsf_manual_context import ManualContextError
from wsf_inbox_registry_operator import (
    DRAFT_PATH, PUBLICATION_PATH, APPROVAL_PATH, verify_publication,
)

class RegistryPublicationTests(unittest.TestCase):
    def test_exact_git_commit_without_installed_docs(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d).resolve()
            def git(*args):
                return subprocess.check_output(["/usr/bin/git", "-C", str(repo), *args], stderr=subprocess.DEVNULL)
            git("init", "-b", "main")
            git("config", "user.name", "Fixture")
            git("config", "user.email", "fixture@example.invalid")
            draft = b"synthetic contract\n"
            blob = hashlib.sha1(b"blob " + str(len(draft)).encode() + b"\x00" + draft).hexdigest()
            for name, raw in ((DRAFT_PATH, draft), (PUBLICATION_PATH, blob.encode()), (APPROVAL_PATH, blob.encode())):
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            git("add", ".")
            git("commit", "-m", "fixture publication")
            release = git("rev-parse", "HEAD").decode().strip()
            with patch("wsf_inbox_registry_operator.SUCCESSOR_DRAFT", blob):
                self.assertTrue(verify_publication(release, repo))
                with self.assertRaises(ManualContextError):
                    verify_publication("a"*40, repo)
                (repo / APPROVAL_PATH).write_text("edited outside commit")
                with self.assertRaises(ManualContextError):
                    verify_publication(release, repo)
                git("add", ".")
                git("commit", "-m", "remove approval pin")
                with self.assertRaises(ManualContextError):
                    verify_publication(git("rev-parse", "HEAD").decode().strip(), repo)

if __name__ == "__main__":
    unittest.main()
