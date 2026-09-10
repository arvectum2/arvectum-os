from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from arvectum_os_ref.identity import Identity
from workspace_app.access import AccessContext
from workspace_app.company_portfolio import CompanyPortfolioError, SourceDocument
from workspace_app.company_portfolio_verified import PortfolioProjectionCache, VerifiedRuntimeCompanyPortfolioProvider


def _access() -> AccessContext:
    return AccessContext(
        organization=Identity("org", "ООО «Арвектум»", "local"),
        actor=Identity("actor", "owner", "ООО «Арвектум»"),
        principal_kind="human",
        credential_id="credential",
        grant_id="grant",
    )


def _registry(root: Path) -> Path:
    path = root / "registry.json"
    path.write_text(
        json.dumps(
            {
                "schema": "arvectum.company.workspace-project-registry/1",
                "authority": {"portfolio_identity": "AC-301"},
                "projects": [
                    {
                        "id": "COMPANY",
                        "label": "Arvectum Company",
                        "kind": "company",
                        "disposition": "continue",
                        "repository": "arvectum2/arvectum-company",
                        "roadmap_path": "docs/roadmap/ROADMAP.md",
                        "adapter": "company-roadmap-v1",
                        "execution_targets": [],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


class FakeReader:
    def __init__(self) -> None:
        self.hashes: dict[tuple[str, str, str], str] = {}

    def read(self, descriptor):  # type: ignore[no-untyped-def]
        markdown = "# Roadmap\nСтатус: Active\nТекущее каноническое действие: AC-505 — wait\n"
        source = SourceDocument(
            descriptor.repository,
            descriptor.roadmap_path,
            "a" * 40,
            markdown,
            "2026-08-26T19:00:00Z",
        )
        self.hashes[(source.repository, source.path, source.commit_sha)] = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
        return source

    def content_sha256_for(self, repository: str, path: str, commit_sha: str) -> str | None:
        return self.hashes.get((repository, path, commit_sha))


class CompanyPortfolioCacheResilienceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_noncanonical_cache_write_failure_does_not_hide_verified_live_source(self) -> None:
        provider = VerifiedRuntimeCompanyPortfolioProvider(
            _registry(self.root),
            reader=FakeReader(),  # type: ignore[arg-type]
            cache_root=self.root,
        )
        self.assertIsNotNone(provider.cache)

        def fail_save(access: AccessContext, projection: dict[str, object]) -> None:
            raise CompanyPortfolioError("simulated cache persistence failure")

        provider.cache.save = fail_save  # type: ignore[method-assign,union-attr]
        payload = provider.project(_access(), force_refresh=True)
        card = payload["projects"][0]
        self.assertEqual(card["state"], "current-source-backed")
        self.assertEqual(card["roadmap"]["current"], ["AC-505 — wait"])
        self.assertRegex(card["source"]["content_sha256"], r"^[0-9a-f]{64}$")

    @unittest.skipIf(not hasattr(os, "symlink"), "symlinks unavailable")
    def test_cache_refuses_symlink_directory(self) -> None:
        runtime_root = self.root / "runtime"
        runtime_root.mkdir()
        target = self.root / "redirected"
        target.mkdir()
        cache_dir = runtime_root / "workspace-company-portfolio-cache"
        cache_dir.symlink_to(target, target_is_directory=True)
        cache = PortfolioProjectionCache(runtime_root)
        projection = {
            "schema": "arvectum.workspace.company-portfolio/1",
            "projects": [],
        }
        with self.assertRaises(CompanyPortfolioError):
            cache.save(_access(), projection)


if __name__ == "__main__":
    unittest.main()
