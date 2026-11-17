"""WSF-03: retain stable portfolio identities and admit only the approved Work descriptor."""
import unittest

from workspace_app.company_portfolio import RuntimeCompanyPortfolioProvider


class WorkspaceFirstProjectRegistryTest(unittest.TestCase):
    def test_work_descriptor_is_explicit_and_existing_ids_remain(self):
        provider = RuntimeCompanyPortfolioProvider()
        descriptors = {item.project_id: item for item in provider._descriptors}
        self.assertTrue({"COMPANY", "OS", *(f"PORT-{i:03d}" for i in range(1, 9))}.issubset(descriptors))
        work = descriptors["PORT-008"]
        self.assertEqual(work.label, "Arvectum Work")
        self.assertEqual(work.repository, "arvectum2/arvectum-work")
        self.assertEqual(work.roadmap_path, "docs/roadmap/ROADMAP.md")
        self.assertEqual(work.disposition, "discover")
        self.assertEqual(work.execution_targets, ())
        self.assertIsNone(descriptors["PORT-005"].repository)
        self.assertIsNone(descriptors["PORT-006"].roadmap_path)
        self.assertIsNone(descriptors["PORT-007"].roadmap_path)
        self.assertIn("PORTFOLIO.md", provider._authority["portfolio_current"])
