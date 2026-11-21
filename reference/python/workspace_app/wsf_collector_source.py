"""Read-only fixed-locator source adapter; no ambient/human token reuse."""
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .company_portfolio import CompanyPortfolioError
from .company_portfolio_verified import ContentHashingGitHubRoadmapReader, VerifiedRuntimeCompanyPortfolioProvider
from .wsf_manual_context import ManualContextError, _digest
from .wsf_manual_policy import _private_file
from .wsf_local_roadmap_collector import ACTIVE, REGISTRY, exact_registry

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

class FixedSourceReader(ContentHashingGitHubRoadmapReader):
    def __init__(self):
        super().__init__(token="")
        self.allowed=exact_registry()
        self.opener=build_opener(NoRedirect())
        self.current_urls=set()

    def read(self,descriptor):
        if descriptor.project_id not in ACTIVE or self.allowed[descriptor.project_id]!={
            "repository":descriptor.repository,"path":descriptor.roadmap_path,"adapter":descriptor.adapter}:
            raise CompanyPortfolioError("collector locator denied")
        self.current_urls={f"https://api.github.com/repos/{descriptor.repository}/commits/main"}
        self.content_prefix=f"https://api.github.com/repos/{descriptor.repository}/contents/{quote(descriptor.roadmap_path,safe='/')}?ref="
        try:return super().read(descriptor)
        finally:self.current_urls=set();self.content_prefix=""

    def _json(self,url):
        if url not in self.current_urls:
            raise CompanyPortfolioError("collector URL denied")
        headers={"Accept":"application/vnd.github+json","User-Agent":"Arvectum-Roadmap-Collector",
                 "X-GitHub-Api-Version":"2022-11-28"}
        try:
            with self.opener.open(Request(url,headers=headers,method="GET"),timeout=self.timeout_seconds) as r:
                raw=r.read(2_000_001)
            if len(raw)>2_000_000:raise ValueError()
            payload=json.loads(raw)
            if not isinstance(payload,dict):raise ValueError()
        except (HTTPError,URLError,OSError,ValueError) as exc:
            raise CompanyPortfolioError("collector source unavailable") from exc
        if url.endswith("/commits/main"):
            sha=payload.get("sha")
            if not isinstance(sha,str) or not re.fullmatch("[0-9a-f]{40}",sha):
                raise CompanyPortfolioError("invalid source commit")
            self.current_urls.add(self.content_prefix+sha)
        return payload

def provider_for(root,p):
    # Review file is a pinned operator attestation, not independent proof of GitHub scopes.
    # Selected-device activation must separately verify the provider-side restrictions.
    root=Path(root)
    raw=_private_file(root/"config"/"roadmap-collector-source-review.json")
    if _digest(raw)!=p["source_review_sha256"]:
        raise ManualContextError("collector source review mismatch")
    review=json.loads(raw)
    b=exact_registry()
    if review!={"schema":"arvectum.workspace.collector-source-review/1","mode":p["source_mode"],
                "repositories":sorted(b[k]["repository"] for k in ACTIVE),
                "contents":"read-only","metadata":"read-only","credential":"none",
                "external_verification_required":True}:
        raise ManualContextError("collector source assurance unavailable")
    if p["source_mode"]!="anonymous-public":
        raise ManualContextError("only anonymous public source access admitted")
    from .wsf_collector_git_source import GitPrimaryFixedSourceReader
    return VerifiedRuntimeCompanyPortfolioProvider(REGISTRY,reader=GitPrimaryFixedSourceReader(root/"source-git-cache"))
