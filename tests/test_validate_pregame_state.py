import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from validate_pregame_state import audit_game

UTC = timezone.utc


class TestPregameAudit(unittest.TestCase):
    def base_game(self):
        return {
            "gameId": "g1",
            "awayTeam": "Away",
            "homeTeam": "Home",
            "kickoff": "2026-10-20T23:00:00Z",
            "canonicalProjection": {
                "status": "CANONICAL_OPEN",
                "projectedSpreadHome": -3.0,
                "projectedTotal": 51.0,
                "projectedWinner": "Home",
                "homeWinProbability": 60.0,
            },
            "market": {
                "status": "LOCK_READY",
                "observations": [{
                    "source": "book",
                    "observedAt": "2026-10-20T21:55:00Z",
                    "spreadHome": -2.5,
                    "total": 50.5,
                }],
            },
            "personnel": {"status": "CURRENT", "home": {"startingQB": "QB H"}, "away": {"startingQB": "QB A"}},
            "weather": {"status": "CURRENT"},
            "benchmarks": {
                "spPlus": {"status": "PENDING_CURRENT_OFFICIAL_CAPTURE"},
                "sagarin": {"status": "CURRENT_FOR_WEEK_8_OPEN"},
                "refMetrics": {"status": "NOT_YET_POSTED"},
            },
            "audit": {"oneHourRefreshAt": "2026-10-20T22:00:00Z"},
        }

    def test_missing_refmetrics_is_warning_not_blocker(self):
        g = self.base_game()
        out = audit_game(g, datetime(2026, 10, 20, 22, 5, tzinfo=UTC))
        self.assertTrue(out["readyToFreeze"])
        self.assertTrue(any("RefMetrics" in w for w in out["warnings"]))

    def test_unresolved_material_qb_blocks(self):
        g = self.base_game()
        g["personnel"] = {
            "status": "MATERIAL_QB_ISSUE_OPEN",
            "home": {"startingQB": "UNRESOLVED_AFTER_STARTER_OUT"},
            "away": {"startingQB": "QB A"},
        }
        out = audit_game(g, datetime(2026, 10, 20, 22, 5, tzinfo=UTC))
        self.assertFalse(out["readyToFreeze"])
        self.assertTrue(any("starting-QB" in b for b in out["blockers"]))

    def test_shadow_cannot_replace_canonical(self):
        g = self.base_game()
        g["canonicalProjection"]["status"] = "SHADOW_READY"
        out = audit_game(g, datetime(2026, 10, 20, 22, 5, tzinfo=UTC))
        self.assertFalse(out["readyToFreeze"])
        self.assertTrue(any("shadow/challenger" in b for b in out["blockers"]))

    def test_missing_one_hour_refresh_blocks_inside_window(self):
        g = self.base_game()
        g["audit"].pop("oneHourRefreshAt")
        out = audit_game(g, datetime(2026, 10, 20, 22, 5, tzinfo=UTC))
        self.assertFalse(out["readyToFreeze"])
        self.assertTrue(any("one-hour" in b for b in out["blockers"]))


if __name__ == "__main__":
    unittest.main()
