import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from merge_pregame_refresh import merge_state


class TestPregameRefreshMerge(unittest.TestCase):
    def test_overlay_replaces_weaker_qb_state_without_mutating_base(self):
        base = {
            "status": "OPEN",
            "games": [{
                "gameId": "g1",
                "personnel": {
                    "status": "OLD",
                    "home": {"startingQB": "CONFIRMED_OUT", "note": "old"},
                    "sources": ["third-party"]
                }
            }]
        }
        original = copy.deepcopy(base)
        overlay = {
            "observedAt": "2026-10-20T03:15:00Z",
            "role": "OFFICIAL_SOURCE_REFRESH_OVERLAY",
            "games": [{
                "gameId": "g1",
                "patch": {
                    "personnel": {
                        "status": "MATERIAL_QB_STATUS_OPEN",
                        "home": {"startingQB": "UNRESOLVED_TUESDAY_STARTER", "officialContext": "official"},
                        "sources": ["official"]
                    }
                }
            }]
        }
        out = merge_state(base, [overlay])
        self.assertEqual(base, original)
        self.assertEqual(out["personnel"] if "personnel" in out else out["games"][0]["personnel"]["status"], "MATERIAL_QB_STATUS_OPEN")
        self.assertEqual(out["games"][0]["personnel"]["home"]["startingQB"], "UNRESOLVED_TUESDAY_STARTER")
        self.assertEqual(out["games"][0]["personnel"]["home"]["note"], "old")
        self.assertEqual(out["games"][0]["personnel"]["sources"], ["official"])
        self.assertEqual(out["effectiveState"]["overlayCount"], 1)

    def test_unknown_game_fails_closed(self):
        base = {"status": "OPEN", "games": [{"gameId": "g1"}]}
        overlay = {"observedAt": "2026-10-20T03:15:00Z", "games": [{"gameId": "g2", "patch": {"x": 1}}]}
        with self.assertRaises(ValueError):
            merge_state(base, [overlay])


if __name__ == "__main__":
    unittest.main()
