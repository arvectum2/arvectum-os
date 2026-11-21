"""Two regression guards for the Git-first Mission Control rollout."""
from pathlib import Path
from unittest import TestCase
from workspace_app.wsf_local_roadmap_collector import REGISTRY, ACTIVE, exact_registry
from workspace_app.company_portfolio_verified import VerifiedRuntimeCompanyPortfolioProvider

ROOT=Path(__file__).resolve().parents[1]

class FollowupGuards(TestCase):
    def test_f11_routes_use_same_exact_admitted_registry_as_collector(self):
        code=(ROOT/'workspace_app/f11_routes.py').read_text()
        self.assertIn('registry_path=ADMITTED_ROADMAP_REGISTRY',code)
        self.assertIn('from .wsf_local_roadmap_collector import REGISTRY as ADMITTED_ROADMAP_REGISTRY',code)
        self.assertEqual(len(ACTIVE),8)
        self.assertEqual(set(exact_registry()),set(x.project_id for x in VerifiedRuntimeCompanyPortfolioProvider(REGISTRY)._descriptors))
        self.assertEqual(exact_registry()['PORT-007']['repository'],'arvectum2/data-platform')
    def test_p706_does_not_create_python315_workspace(self):
        source=(ROOT/'p7_06_macos_deploy.sh').read_text()
        self.assertIn('PINNED_PYTHON_314="/opt/homebrew/opt/python@3.14/libexec/bin/python3"',source)
        self.assertNotIn('python3 -m venv "$venv"',source)
        self.assertIn('target release Python must be exactly 3.14',source)
