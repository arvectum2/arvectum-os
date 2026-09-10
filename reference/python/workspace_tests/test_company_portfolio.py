from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from arvectum_os_ref.identity import Identity
from workspace_app.access import AccessContext
from workspace_app.company_portfolio import CompanyPortfolioError, SourceDocument
from workspace_app.company_portfolio_verified import VerifiedRuntimeCompanyPortfolioProvider


class FakeReader:
    def __init__(self, sources: dict[str, str]):
        self.sources = sources
        self.hashes: dict[tuple[str, str, str], str] = {}

    def read(self, descriptor):  # type: ignore[no-untyped-def]
        markdown = self.sources[descriptor.project_id]
        source = SourceDocument(
            descriptor.repository,
            descriptor.roadmap_path,
            "a" * 40,
            markdown,
            "2026-08-26T10:00:00Z",
        )
        self.hashes[(source.repository, source.path, source.commit_sha)] = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
        return source

    def content_sha256_for(self, repository: str, path: str, commit_sha: str) -> str | None:
        return self.hashes.get((repository, path, commit_sha))


class ToggleReader(FakeReader):
    def __init__(self, sources: dict[str, str]):
        super().__init__(sources)
        self.available = True
        self.calls = 0

    def read(self, descriptor):  # type: ignore[no-untyped-def]
        self.calls += 1
        if not self.available:
            raise CompanyPortfolioError("simulated canonical source outage")
        return super().read(descriptor)


def _access(*, organization: str = "ООО «Арвектум»") -> AccessContext:
    return AccessContext(
        organization=Identity("org", organization, "local"),
        actor=Identity("actor", "owner", organization),
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
                "authority": {"portfolio_identity": "AC-301", "git_primary": "2026-08-25 migration closure"},
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
                    },
                    {
                        "id": "PORT-007",
                        "label": "Data Platform",
                        "kind": "initiative",
                        "disposition": "clarify",
                        "repository": "arvectum2/data-platform",
                        "roadmap_path": None,
                        "adapter": "reconciliation-required",
                        "execution_targets": [],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _owner_adapter_registry(root: Path) -> Path:
    path = root / "owner-adapters.json"
    path.write_text(
        json.dumps(
            {
                "schema": "arvectum.company.workspace-project-registry/1",
                "authority": {"portfolio_identity": "AC-301", "git_primary": "2026-08-25 migration closure"},
                "projects": [
                    {
                        "id": "PORT-001",
                        "label": "Tender Agent",
                        "kind": "product",
                        "disposition": "continue",
                        "repository": "arvectum2/tender-agent",
                        "roadmap_path": "STATUS.md",
                        "adapter": "tender-status-v1",
                        "execution_targets": [],
                    },
                    {
                        "id": "PORT-002",
                        "label": "Discount Parser",
                        "kind": "product",
                        "disposition": "continue",
                        "repository": "arvectum2/discount-parser",
                        "roadmap_path": "docs/ROADMAP.md",
                        "adapter": "generic-roadmap-v1",
                        "execution_targets": [],
                    },
                    {
                        "id": "PORT-003",
                        "label": "Proxy Launcher",
                        "kind": "product",
                        "disposition": "continue",
                        "repository": "arvectum2/proxy-launcher",
                        "roadmap_path": "docs/ROADMAP.md",
                        "adapter": "proxy-roadmap-v1",
                        "execution_targets": [],
                    },
                    {
                        "id": "PORT-004",
                        "label": "Creative Test Agent",
                        "kind": "product",
                        "disposition": "continue",
                        "repository": "arvectum2/creative-test-agent",
                        "roadmap_path": "docs/roadmap/CURRENT.md",
                        "adapter": "creative-roadmap-v1",
                        "execution_targets": [],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


class CompanyPortfolioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_company_portfolio_preserves_source_authority_hash_and_reconciliation(self) -> None:
        markdown = """# Roadmap\nСтатус: Active\nВерсия: 0.44.0\nТекущее каноническое действие: AC-505 — external evidence wait\n\n## 9. Available implementation paths now\n### A. Canonical empirical M5 path\n### B. Parallel business-evidence work\n"""
        provider = VerifiedRuntimeCompanyPortfolioProvider(
            _registry(self.root),
            reader=FakeReader({"COMPANY": markdown}),  # type: ignore[arg-type]
        )

        payload = provider.project(_access())
        self.assertEqual(
            payload["projection"],
            {
                "derived": True,
                "canonical_authority": False,
                "read_only": True,
                "roadmap_write_available": False,
                "remote_execution_available": False,
                "chat_or_model_memory_used_as_authority": False,
                "visibility_implies_permission": False,
            },
        )
        company, data_platform = payload["projects"]
        self.assertEqual(company["state"], "current-source-backed")
        self.assertEqual(company["source"]["commit_sha"], "a" * 40)
        self.assertEqual(company["source"]["content_sha256"], hashlib.sha256(markdown.encode("utf-8")).hexdigest())
        self.assertEqual(company["roadmap"]["current"], ["AC-505 — external evidence wait"])
        self.assertEqual(
            company["roadmap"]["branches"],
            ["A. Canonical empirical M5 path", "B. Parallel business-evidence work"],
        )
        self.assertEqual(company["execution_targets"], ["unspecified"])
        self.assertEqual(data_platform["state"], "reconciliation-required")
        self.assertIsNone(data_platform["source"])
        self.assertEqual(data_platform["roadmap"]["current"], [])

    def test_company_portfolio_isolates_source_failure_without_manufacturing_status(self) -> None:
        class SelectiveReader(FakeReader):
            def read(self, descriptor):  # type: ignore[no-untyped-def]
                if descriptor.project_id == "COMPANY":
                    raise CompanyPortfolioError("network detail must not leak")
                return super().read(descriptor)

        registry = json.loads(_registry(self.root).read_text(encoding="utf-8"))
        registry["projects"][1]["roadmap_path"] = "README.md"
        registry["projects"][1]["adapter"] = "generic-roadmap-v1"
        path = self.root / "registry-two.json"
        path.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
        provider = VerifiedRuntimeCompanyPortfolioProvider(
            path,
            reader=SelectiveReader({"PORT-007": "# Data Platform\nStatus: Planned"}),  # type: ignore[arg-type]
        )
        payload = provider.project(_access())
        self.assertEqual(payload["projects"][0]["state"], "unavailable")
        self.assertEqual(payload["projects"][0]["roadmap"]["current"], [])
        self.assertEqual(payload["projects"][1]["state"], "current-source-backed")
        self.assertRegex(payload["projects"][1]["source"]["content_sha256"], r"^[0-9a-f]{64}$")

    def test_missing_content_hash_fails_closed_instead_of_claiming_source_backing(self) -> None:
        class NoHashReader(FakeReader):
            def content_sha256_for(self, repository: str, path: str, commit_sha: str) -> str | None:
                return None

        provider = VerifiedRuntimeCompanyPortfolioProvider(
            _registry(self.root),
            reader=NoHashReader({"COMPANY": "# Roadmap\nStatus: Active"}),  # type: ignore[arg-type]
        )
        card = provider.project(_access())["projects"][0]
        self.assertEqual(card["state"], "unavailable")
        self.assertIsNone(card["source"])
        self.assertEqual(card["roadmap"]["current"], [])

    def test_recent_last_known_good_cache_prevents_navigation_from_refetching_github(self) -> None:
        markdown = """# Roadmap\nСтатус: Active\nТекущее каноническое действие: AC-505 — external evidence wait\n"""
        reader = ToggleReader({"COMPANY": markdown})
        provider = VerifiedRuntimeCompanyPortfolioProvider(
            _registry(self.root),
            reader=reader,  # type: ignore[arg-type]
            cache_root=self.root,
            cache_max_age_seconds=900,
        )

        first = provider.project(_access())
        self.assertEqual(first["projects"][0]["state"], "current-source-backed")
        self.assertEqual(reader.calls, 1)

        reader.available = False
        second = provider.project(_access())
        self.assertEqual(reader.calls, 1, "ordinary page revisit must use recent read-model cache instead of GitHub")
        self.assertEqual(second["projects"][0]["state"], "cached-source-backed")
        self.assertEqual(second["projects"][0]["roadmap"]["current"], ["AC-505 — external evidence wait"])
        self.assertEqual(second["projects"][0]["source"]["commit_sha"], "a" * 40)
        self.assertEqual(second["projects"][0]["source"]["freshness"], "cached-within-window")

    def test_explicit_refresh_failure_keeps_last_known_good_projection_visible_as_stale(self) -> None:
        markdown = """# Roadmap\nСтатус: Active\nТекущее каноническое действие: AC-505 — external evidence wait\n"""
        reader = ToggleReader({"COMPANY": markdown})
        provider = VerifiedRuntimeCompanyPortfolioProvider(
            _registry(self.root),
            reader=reader,  # type: ignore[arg-type]
            cache_root=self.root,
        )
        provider.project(_access())
        reader.available = False

        refreshed = provider.project(_access(), force_refresh=True)
        company = refreshed["projects"][0]
        self.assertEqual(reader.calls, 2)
        self.assertEqual(company["state"], "stale-cache")
        self.assertEqual(company["roadmap"]["current"], ["AC-505 — external evidence wait"])
        self.assertEqual(company["source"]["commit_sha"], "a" * 40)
        self.assertEqual(company["source"]["freshness"], "stale-cache")
        self.assertIn("последняя успешно полученная", company["message"])

    def test_cache_is_organization_scoped_and_never_crosses_access_context(self) -> None:
        markdown = "# Roadmap\nСтатус: Active\nТекущее каноническое действие: AC-505 — wait\n"
        reader = ToggleReader({"COMPANY": markdown})
        provider = VerifiedRuntimeCompanyPortfolioProvider(
            _registry(self.root),
            reader=reader,  # type: ignore[arg-type]
            cache_root=self.root,
        )
        provider.project(_access())
        reader.available = False

        other = provider.project(_access(organization="Other Org"))
        company = other["projects"][0]
        self.assertEqual(company["state"], "unavailable")
        self.assertEqual(company["roadmap"]["current"], [])
        self.assertIsNone(company["source"])

    def test_owner_focused_adapters_fill_uniform_fields_without_memory_inference(self) -> None:
        sources = {
            "PORT-001": """# Arvectum R0 status\n\n## Product snapshot\nStage: `R0_CLOSED_FUNCTIONALLY`.\n\n## Known limitations\nFunctional acceptance is PASS. Public reliability is NOT PROVEN.\n\n## Next milestone\nNext stage is limited to extraction quality, analysis quality, report structure, and evidence coverage.\n""",
            "PORT-002": """# Discount Parser\nСтатус: **готово к реализации**\nДата фиксации: **2026-08-08**\n\n## R0 — Specification freeze\n**Статус: DONE**\n\n## R1 — Project foundation\n### Задачи\n- create app\n\n## R2 — Offer domain + persistence\n""",
            "PORT-003": """# Proxy\nCurrent product line: `0.2.3`\n\n## 8. What can be done now\n### [Web] ChatGPT/GitHub\n1. **READY — architecture decision.**\n### [Win] ARVECTUM-DEMO\n1. **CURRENT — APL-WIN-014 enforced gate.**\n### [Linux] ARVECTUM-DEMO\n1. **READY — APL-LNX-010 after Windows gate.**\n\n### Windows production enforcement STOP-GATE\n""",
            "PORT-004": """# Current Creative Test Agent roadmap\n\n## Current state\n- Blocks A–D: complete;\n- Block E: blocked on client data;\n- Waiting-for-Data Lane: 4/7 complete and active;\n- `CTA-PILOT-PREP-002`: DONE;\n- next task: `CTA-PILOT-PREP-003 — Synthetic Controlled Pilot Rehearsal`;\n- this next task is HYBRID and requires a local Mac mini/OpenCode rehearsal after GitHub implementation.\n""",
        }
        provider = VerifiedRuntimeCompanyPortfolioProvider(
            _owner_adapter_registry(self.root),
            reader=FakeReader(sources),  # type: ignore[arg-type]
        )

        tender, discount, proxy, creative = provider.project(_access())["projects"]
        self.assertEqual(tender["roadmap"]["status"], "R0_CLOSED_FUNCTIONALLY.")
        self.assertTrue(any("Next stage" in item for item in tender["roadmap"]["current"]))
        self.assertTrue(any("NOT PROVEN" in item for item in tender["roadmap"]["blocked"]))
        self.assertEqual(tender["roadmap"]["branches"], [])

        self.assertEqual(discount["roadmap"]["done"], ["R0 — Specification freeze"])
        self.assertEqual(discount["roadmap"]["current"], ["R1 — Project foundation"])
        self.assertEqual(discount["roadmap"]["unlocked"], ["R1 — Project foundation"])
        self.assertEqual(discount["roadmap"]["branches"], ["R2 — Offer domain + persistence"])

        self.assertTrue(any("APL-WIN-014" in item for item in proxy["roadmap"]["current"]))
        self.assertEqual(proxy["execution_targets"], ["web", "windows-test-laptop", "linux-test-laptop"])

        self.assertTrue(any("CTA-PILOT-PREP-003" in item for item in creative["roadmap"]["current"]))
        self.assertTrue(any("blocked on client data" in item for item in creative["roadmap"]["blocked"]))
        self.assertEqual(creative["execution_targets"], ["web", "mac-mini"])


if __name__ == "__main__":
    unittest.main()
