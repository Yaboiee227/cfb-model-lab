import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from run_cfb_shadow_week8 import extract_grouped_team_ids


class TestCfbShadowRunner(unittest.TestCase):
    def test_grouped_espn_team_schema(self):
        doc = {
            "sports": [{
                "leagues": [{
                    "groups": [
                        {"teams": [{"id": "1", "name": "Alpha"}, {"id": "2", "name": "Beta"}]},
                        {"teams": [{"id": "2", "name": "Beta"}, {"id": "3", "name": "Gamma"}]},
                    ]
                }]
            }]
        }
        self.assertEqual(extract_grouped_team_ids(doc), ["1", "2", "3"])

    def test_grouped_parser_accepts_wrapped_team(self):
        doc = {"sports": [{"leagues": [{"groups": [{"teams": [{"team": {"id": "42"}}]}]}]}]}
        self.assertEqual(extract_grouped_team_ids(doc), ["42"])


if __name__ == "__main__":
    unittest.main()
