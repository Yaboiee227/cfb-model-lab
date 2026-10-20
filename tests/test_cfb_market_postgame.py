import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from cfb_market_postgame import grade, grade_direction, preserve_graded_at_if_unchanged
from cfb_market_research_lock import merge_market_lock
from lock_research_shadow import build_lock


class TestCfbMarketPostgame(unittest.TestCase):
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
                    "gameId": "g1", "sourceGameId": "1", "awayTeam": "Away A", "homeTeam": "Home A",
                    "kickoff": "2026-10-20T23:00:00Z", "projectedAwayPoints": 20.0, "projectedHomePoints": 30.0,
                    "projectedMarginHome": 10.0, "projectedSpreadHome": -10.0, "projectedTotal": 50.0,
                    "homeWinProbability": 75.0, "projectedWinner": "Home A",
                },
                {
                    "gameId": "g2", "sourceGameId": "2", "awayTeam": "Away B", "homeTeam": "Home B",
                    "kickoff": "2026-10-20T23:30:00Z", "projectedAwayPoints": 32.0, "projectedHomePoints": 28.0,
                    "projectedMarginHome": -4.0, "projectedSpreadHome": 4.0, "projectedTotal": 60.0,
                    "homeWinProbability": 40.0, "projectedWinner": "Away B",
                },
            ],
        }
        return build_lock(source, datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc))

    def _markets(self):
        return {
            "provider": "The Odds API",
            "games": [
                {
                    "id": "m1", "commenceTime": "2026-10-20T23:00:00Z", "awayTeam": "Away A", "homeTeam": "Home A",
                    "books": {
                        "fanduel": {
                            "updatedAt": "2026-10-20T22:40:00Z", "moneyline": {"home": -300, "away": 240},
                            "spread": {"home": -7.0, "homePrice": -110, "away": 7.0, "awayPrice": -110},
                            "total": {"point": 47.0, "overPrice": -110, "underPrice": -110},
                        },
                        "draftkings": {
                            "updatedAt": "2026-10-20T22:42:00Z", "moneyline": {"home": -320, "away": 250},
                            "spread": {"home": -8.0, "homePrice": -105, "away": 8.0, "awayPrice": -115},
                            "total": {"point": 51.0, "overPrice": -108, "underPrice": -112},
                        },
                    },
                },
                {
                    "id": "m2", "commenceTime": "2026-10-20T23:30:00Z", "awayTeam": "Away B", "homeTeam": "Home B",
                    "books": {
                        "fanduel": {
                            "updatedAt": "2026-10-20T23:10:00Z", "moneyline": {"home": 105, "away": -125},
                            "spread": {"home": 1.5, "homePrice": -110, "away": -1.5, "awayPrice": -110},
                            "total": {"point": 62.0, "overPrice": -110, "underPrice": -110},
                        },
                        "draftkings": {
                            "updatedAt": "2026-10-20T23:12:00Z", "moneyline": {"home": 110, "away": -130},
                            "spread": {"home": 2.0, "homePrice": -105, "away": -2.0, "awayPrice": -115},
                            "total": {"point": 61.5, "overPrice": -110, "underPrice": -110},
                        },
                    },
                },
            ],
        }

    def _market_lock(self, foundation):
        first = merge_market_lock(
            foundation, self._markets(), None, {},
            datetime(2026, 10, 20, 22, 45, tzinfo=timezone.utc),
        )
        # g2 is not yet inside its 30-minute window at 22:45. Add it later while
        # preserving g1's already-locked book observations.
        return merge_market_lock(
            foundation, self._markets(), first, {},
            datetime(2026, 10, 20, 23, 15, tzinfo=timezone.utc),
        )

    def _scores(self):
        return [
            {"sourceGameId": "1", "awayTeam": "Away A", "homeTeam": "Home A", "awayScore": 24, "homeScore": 30, "status": "FINAL", "overtime": False, "source": "ESPN"},
            {"sourceGameId": "2", "awayTeam": "Away B", "homeTeam": "Home B", "awayScore": 31, "homeScore": 28, "status": "FINAL", "overtime": False, "source": "ESPN"},
        ]

    def test_direction_grading_rules(self):
        self.assertEqual(grade_direction(0.0, 10.0), "NO_POSITION")
        self.assertEqual(grade_direction(2.0, 0.0), "PUSH")
        self.assertEqual(grade_direction(2.0, 1.0), "WIN")
        self.assertEqual(grade_direction(-2.0, -1.0), "WIN")
        self.assertEqual(grade_direction(2.0, -1.0), "LOSS")

    def test_grades_each_book_separately_against_same_finals(self):
        foundation = self._foundation()
        market_lock = self._market_lock(foundation)
        out = grade(foundation, market_lock, self._scores(), {})
        self.assertEqual(out["role"], "POSTGAME_FROZEN_MODEL_VS_LOCKED_MARKET_RESEARCH_EVALUATION")
        self.assertFalse(out["canonicalInfluence"])
        self.assertFalse(out["canonicalRecordMerged"])
        self.assertEqual(out["status"], "COMPLETE")
        self.assertEqual(out["counts"]["final"], 2)

        fd = out["books"]["fanduel"]
        self.assertEqual(fd["games"], 2)
        self.assertEqual(fd["spreadPositionRecord"], {"wins": 1, "losses": 1, "pushes": 0, "noPosition": 0})
        self.assertEqual(fd["totalPositionRecord"], {"wins": 2, "losses": 0, "pushes": 0, "noPosition": 0})
        self.assertEqual(fd["straightUp"]["correct"], 2)
        self.assertAlmostEqual(fd["cbMargin"]["mae"], 2.5)
        self.assertAlmostEqual(fd["marketMargin"]["mae"], 1.25)
        self.assertEqual(fd["closerMarginForecast"], {"CB": 1, "MARKET": 1, "TIE": 0})
        self.assertEqual(fd["closerTotalForecast"], {"CB": 2, "MARKET": 0, "TIE": 0})

        g1fd = out["games"][0]["books"]["fanduel"]
        self.assertEqual(g1fd["modelVsMarket"]["spreadPosition"], "HOME")
        self.assertEqual(g1fd["modelVsMarket"]["spreadResult"], "LOSS")
        self.assertEqual(g1fd["modelVsMarket"]["totalPosition"], "OVER")
        self.assertEqual(g1fd["modelVsMarket"]["totalResult"], "WIN")
        self.assertEqual(g1fd["accuracy"]["closerMarginForecast"], "MARKET")
        self.assertEqual(g1fd["accuracy"]["closerTotalForecast"], "CB")

    def test_tampered_market_observation_is_rejected(self):
        foundation = self._foundation()
        market_lock = self._market_lock(foundation)
        market_lock["games"][0]["books"]["fanduel"]["marketSpreadHome"] = 99.0
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            grade(foundation, market_lock, self._scores(), {})

    def test_idempotent_timestamp_when_results_unchanged(self):
        foundation = self._foundation()
        market_lock = self._market_lock(foundation)
        existing = grade(foundation, market_lock, self._scores(), {})
        existing["gradedAt"] = "2026-10-21T05:00:00Z"
        new = grade(foundation, market_lock, self._scores(), {})
        out = preserve_graded_at_if_unchanged(new, copy.deepcopy(existing))
        self.assertEqual(out["gradedAt"], "2026-10-21T05:00:00Z")


if __name__ == "__main__":
    unittest.main()
