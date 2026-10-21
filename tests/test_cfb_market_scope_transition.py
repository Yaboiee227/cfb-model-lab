import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from cfb_market_research_lock import merge_market_lock
from lock_research_shadow import build_lock


class TestCfbMarketScopeTransition(unittest.TestCase):
    def _foundation(self):
        source = {
            "league": "cfb",
            "season": 2026,
            "week": 8,
            "modelId": "foundation-test",
            "canonicalInfluence": False,
            "canonicalPromotionAuthorized": False,
            "asOf": "2026-10-20T04:00:00Z",
            "lockedParameters": {"alpha": 2.5},
            "structuralHomeMarginAdvantage": 4.25,
            "source": {"marketDataUsed": False},
            "games": [
                {
                    "gameId": "old",
                    "awayTeam": "Away One",
                    "homeTeam": "Home One",
                    "kickoff": "2026-10-20T23:00:00Z",
                    "projectedAwayPoints": 20.0,
                    "projectedHomePoints": 24.0,
                    "projectedMarginHome": 4.0,
                    "projectedSpreadHome": -4.0,
                    "projectedTotal": 44.0,
                    "homeWinProbability": 60.0,
                    "projectedWinner": "Home One",
                },
                {
                    "gameId": "future",
                    "awayTeam": "Away Two",
                    "homeTeam": "Home Two",
                    "kickoff": "2026-10-22T23:00:00Z",
                    "projectedAwayPoints": 21.0,
                    "projectedHomePoints": 25.0,
                    "projectedMarginHome": 4.0,
                    "projectedSpreadHome": -4.0,
                    "projectedTotal": 46.0,
                    "homeWinProbability": 61.0,
                    "projectedWinner": "Home Two",
                },
            ],
        }
        return build_lock(source, datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc))

    def _old_market(self):
        return {
            "provider": "The Odds API",
            "games": [
                {
                    "commenceTime": "2026-10-20T23:00:00Z",
                    "homeTeam": "Home One",
                    "awayTeam": "Away One",
                    "books": {
                        "fanduel": {
                            "updatedAt": "2026-10-20T22:40:00Z",
                            "moneyline": {"home": -180, "away": 150},
                            "spread": {"home": -4.0, "homePrice": -110, "away": 4.0, "awayPrice": -110},
                            "total": {"point": 44.5, "overPrice": -110, "underPrice": -110},
                        }
                    },
                }
            ],
        }

    def test_prior_locked_game_is_preserved_but_not_counted_active(self):
        foundation = self._foundation()
        first = merge_market_lock(
            foundation,
            self._old_market(),
            None,
            {},
            datetime(2026, 10, 20, 22, 45, tzinfo=timezone.utc),
            active_game_ids={"old"},
        )
        second = merge_market_lock(
            foundation,
            {"provider": "The Odds API", "games": []},
            first,
            {},
            datetime(2026, 10, 21, 21, 0, tzinfo=timezone.utc),
            active_game_ids={"future"},
        )
        by_id = {g["gameId"]: g for g in second["games"]}
        self.assertEqual(second["counts"]["activeScopeGames"], 1)
        self.assertEqual(second["counts"]["preservedOutOfScopeLockedGames"], 1)
        self.assertEqual(second["counts"]["pausedGames"], 0)
        self.assertEqual(by_id["old"]["status"], "LOCKED")
        self.assertIn("fanduel", by_id["old"]["books"])
        self.assertEqual(by_id["future"]["status"], "PENDING")


if __name__ == "__main__":
    unittest.main()
