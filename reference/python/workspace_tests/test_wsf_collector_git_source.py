"""Git-first transport is isolated from production GitHub and operator clones."""
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from base64 import b64encode

from workspace_app.company_portfolio import CompanyPortfolioError
from workspace_app.company_portfolio_verified import VerifiedRuntimeCompanyPortfolioProvider
from workspace_app.wsf_collector_git_source import GitPrimaryFixedSourceReader, GitTransportUnavailable
from workspace_app.wsf_local_roadmap_collector import ACTIVE, REGISTRY


class GitSourceTests(TestCase):
    def setUp(self):
        t=TemporaryDirectory();self.addCleanup(t.cleanup)
        self.reader=GitPrimaryFixedSourceReader(Path(t.name).resolve()/"git")
        self.provider=VerifiedRuntimeCompanyPortfolioProvider(REGISTRY,reader=self.reader)
        self.source=next(x for x in self.provider._descriptors if x.project_id=="OS")
        self.body=b"# Synthetic canonical roadmap\n"
        self.sha="a"*40

    def git(self,*args):
        if "get-url" in args:return self.reader._remote_url(self.source).encode()
        if "rev-parse" in args:return (self.sha+"\n").encode()
        if "cat-file" in args:return str(len(self.body)).encode()
        if "show" in args:return self.body
        return b""

    def test_git_fresh_main_no_rest_and_exact_hash(self):
        with patch.object(self.reader,"_git",side_effect=self.git) as git,patch.object(self.reader,"_json",side_effect=AssertionError("REST called")):
            out=self.reader.read(self.source)
        self.assertEqual((out.commit_sha,out.markdown),(self.sha,self.body.decode()))
        self.assertEqual(self.reader.content_sha256_for(out.repository,out.path,out.commit_sha),hashlib.sha256(self.body).hexdigest())
        calls=[x.args for x in git.call_args_list]
        self.assertTrue(any("--filter=blob:none" in x and "refs/heads/main:refs/remotes/origin/main" in " ".join(x) for x in calls))
        self.assertFalse(any("push" in x or "checkout" in x for x in calls))

    def test_git_failure_uses_only_original_fixed_rest(self):
        calls=[]
        def rest(url):
            calls.append(url)
            return {"sha":self.sha} if url.endswith("/commits/main") else {"encoding":"base64","content":b64encode(self.body).decode()}
        with patch.object(self.reader,"_git",side_effect=GitTransportUnavailable("network")),patch.object(self.reader,"_json",side_effect=rest):
            out=self.reader.read(self.source)
        self.assertEqual(out.commit_sha,self.sha)
        self.assertEqual(len(calls),2)
        self.assertTrue(all(x.startswith("https://api.github.com/repos/arvectum2/arvectum-os/") for x in calls))

    def test_two_transports_down_is_unavailable_not_stale_success(self):
        with patch.object(self.reader,"_git",side_effect=GitTransportUnavailable("network")),patch.object(self.reader,"_json",side_effect=CompanyPortfolioError("REST rate limit")):
            with self.assertRaises(CompanyPortfolioError):self.reader.read(self.source)

    def test_wrong_remote_is_not_silently_trusted(self):
        def git(*args):
            return b"https://github.com/unknown/other.git\n" if "get-url" in args else b""
        with patch.object(self.reader,"_git",side_effect=git),patch.object(self.reader,"_json",side_effect=AssertionError("REST called")):
            with self.assertRaises(CompanyPortfolioError):self.reader.read(self.source)

    def test_unauthorized_registry_entries_do_not_use_either_transport(self):
        bad=[x for x in self.provider._descriptors if x.project_id not in ACTIVE]
        self.assertEqual(len(bad),2)
        with patch.object(self.reader,"_git",side_effect=AssertionError("Git called")),patch.object(self.reader,"_json",side_effect=AssertionError("REST called")):
            for d in bad:
                with self.assertRaises(CompanyPortfolioError):self.reader.read(d)
