"""Git-first, REST-fallback read-only source for the eight WSF-07A roadmaps."""
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess

from .company_portfolio import CompanyPortfolioError, SourceDocument
from .company_portfolio_verified import _utc_now
from .wsf_collector_source import FixedSourceReader
from .wsf_local_roadmap_collector import ACTIVE

_SHA = re.compile(r"[0-9a-f]{40}")


class GitTransportUnavailable(Exception):
    """Transport errors only; not authority, integrity or policy errors."""


class GitPrimaryFixedSourceReader(FixedSourceReader):
    """Remote GitHub main via public Git transport; fallback to exact REST GET."""

    def __init__(self, cache_root):
        super().__init__()
        self.cache_root = Path(cache_root)
        if not self.cache_root.is_absolute() or self.cache_root.resolve() != self.cache_root:
            raise CompanyPortfolioError("collector cache path denied")

    def _private_dir(self, path):
        if path.is_symlink():
            raise GitTransportUnavailable("unsafe Git cache")
        try:
            path.mkdir(mode=0o700, parents=False, exist_ok=True)
            mode = path.lstat()
        except OSError as exc:
            raise GitTransportUnavailable("Git cache unavailable") from exc
        if not stat.S_ISDIR(mode.st_mode) or mode.st_uid != os.getuid() or mode.st_mode & 0o077:
            raise GitTransportUnavailable("unsafe Git cache")

    def _remote_url(self, descriptor):
        return f"https://github.com/{descriptor.repository}.git"

    def _git(self, *args):
        # No shell, user Git configuration, credentials, agent, hooks or SSH.
        cmd = ["/usr/bin/git", "-c", "credential.helper=", "-c", "core.hooksPath=/dev/null",
               "-c", "protocol.file.allow=never", "-c", "protocol.ssh.allow=never", *args]
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.cache_root),
               "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
               "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/usr/bin/false",
               "GIT_SSH_COMMAND": "/usr/bin/false", "LC_ALL": "C"}
        try:
            out = subprocess.run(cmd, env=env, capture_output=True, timeout=25, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GitTransportUnavailable("Git command unavailable") from exc
        if out.returncode:
            raise GitTransportUnavailable("Git source fetch unavailable")
        return out.stdout

    def _read_git(self, descriptor):
        # Private bare cache only; never modify the operator's working clones.
        self._private_dir(self.cache_root)
        repo = self.cache_root / (descriptor.project_id + ".git")
        if not repo.exists():
            self._private_dir(repo)
            self._git("init", "--bare", "--quiet", str(repo))
            self._git("-C", str(repo), "remote", "add", "origin", self._remote_url(descriptor))
        else:
            self._private_dir(repo)
        remote = self._git("-C", str(repo), "remote", "get-url", "origin").decode("utf-8", "strict").strip()
        if remote != self._remote_url(descriptor):
            raise CompanyPortfolioError("Git cache remote differs from approved locator")
        self._git("-C", str(repo), "fetch", "--quiet", "--no-tags", "--depth=1",
                  "--filter=blob:none", "origin", "+refs/heads/main:refs/remotes/origin/main")
        sha = self._git("-C", str(repo), "rev-parse", "--verify", "refs/remotes/origin/main^{commit}").decode("ascii", "strict").strip()
        if not _SHA.fullmatch(sha):
            raise CompanyPortfolioError("Git main SHA invalid")
        blob = f"{sha}:{descriptor.roadmap_path}"
        try:
            size = int(self._git("-C", str(repo), "cat-file", "-s", blob).strip())
            if size > 1_500_000 or size < 0:
                raise CompanyPortfolioError("canonical roadmap exceeds bounded reader limit")
            markdown = self._git("-C", str(repo), "show", blob).decode("utf-8", "strict")
        except (ValueError, UnicodeError) as exc:
            raise GitTransportUnavailable("Git roadmap bytes unavailable") from exc
        raw = markdown.encode("utf-8")
        if len(raw) != size:
            raise CompanyPortfolioError("Git content size mismatch")
        self._hashes[(descriptor.repository, descriptor.roadmap_path, sha)] = hashlib.sha256(raw).hexdigest()
        return SourceDocument(descriptor.repository, descriptor.roadmap_path, sha, markdown, _utc_now())

    def read(self, descriptor):
        admitted = self.allowed.get(descriptor.project_id)
        if descriptor.project_id not in ACTIVE or admitted != {
            "repository": descriptor.repository, "path": descriptor.roadmap_path, "adapter": descriptor.adapter
        }:
            raise CompanyPortfolioError("collector locator denied")
        try:
            return self._read_git(descriptor)
        except GitTransportUnavailable:
            # The existing adapter still enforces exact two URLs per locator.
            return super().read(descriptor)
