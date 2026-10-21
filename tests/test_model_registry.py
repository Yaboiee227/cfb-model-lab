import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class TestModelRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ROOT / "data/model-registry.json").read_text(encoding="utf-8"))
        cls.cfb_config = json.loads((ROOT / "data/config.json").read_text(encoding="utf-8"))
        cls.nfl_config = json.loads((ROOT / "nfl_data/site/config.json").read_text(encoding="utf-8"))

    def test_global_promotion_and_reconstruction_guards(self):
        policy = self.registry["policy"]
        self.assertTrue(policy["canonicalPromotionRequiresExplicitApproval"])
        self.assertTrue(policy["prospectiveFrozenEvidenceRequired"])
        self.assertTrue(policy["historicalPregameReconstructionForbidden"])
        self.assertFalse(policy["externalBenchmarksMayModifyCanonical"])
        self.assertFalse(policy["marketContextMayModifyCanonical"])

    def test_cfb_does_not_relabel_foundation_as_09j(self):
        cfb = self.registry["cfb"]
        self.assertEqual(cfb["canonical"]["status"], "HOLD")
        self.assertFalse(cfb["canonical"]["reproducibleGeneratorAvailable"])
        self.assertFalse(cfb["canonical"]["week8CanonicalProjectionAvailable"])
        self.assertEqual(cfb["leadResearchChallenger"]["modelId"], "cfb-rebuild-foundation-v1-shadow")
        self.assertFalse(cfb["leadResearchChallenger"]["canonicalInfluence"])
        self.assertFalse(cfb["leadResearchChallenger"]["promotionAuthorized"])
        self.assertIn("historical version label only", self.cfb_config["modelVersion"])

    def test_nfl_week7_pointer_does_not_overwrite_week6_site_snapshot(self):
        nfl = self.registry["nfl"]
        self.assertEqual(nfl["publishedMainSiteSnapshotWeek"], 6)
        self.assertEqual(nfl["activeProspectiveWeek"], 7)
        self.assertEqual(nfl["canonical"]["activeRef"], "nfl-week7-live-release")
        self.assertEqual(nfl["canonical"]["activeRefHead"], "6e7a5d973308a24d9fc74a8a3e9a238dc1fb6c0a")
        self.assertFalse(nfl["canonical"]["canonicalChanged"])
        self.assertFalse(nfl["canonical"]["promotionAllowed"])
        self.assertFalse(nfl["canonical"]["releaseAllowed"])
        self.assertEqual(self.nfl_config["currentWeek"], 6)
        self.assertEqual(self.nfl_config["activeProspectiveWeek"], 7)

    def test_registry_local_sources_exist(self):
        cfb = self.registry["cfb"]
        for key in ("source",):
            self.assertTrue((ROOT / cfb["canonical"][key]).exists())
        for key in ("generator", "decisionSource", "frozenSource"):
            self.assertTrue((ROOT / cfb["leadResearchChallenger"][key]).exists())
        self.assertTrue((ROOT / self.registry["nfl"]["siteSnapshot"]["config"]).exists())


if __name__ == "__main__":
    unittest.main()
