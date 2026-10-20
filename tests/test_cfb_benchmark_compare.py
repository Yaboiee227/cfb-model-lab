import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from cfb_benchmark_compare import build_comparison, disagreement_bucket, match_benchmark
from lock_research_shadow import build_lock


class TestCfbBenchmarkCompare(unittest.TestCase):
    def _lock(self):
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
            "source": {"marketDataUsed": False, "externalRatingsUsed": False},
            "games": [
                {
                    "gameId": "g-source",
                    "sourceGameId": "100",
                    "awayTeam": "Middle Tennessee",
                    "homeTeam": "Florida International",
                    "kickoff": "2026-10-20T23:00:00Z",
                    "projectedAwayPoints": 17.0,
                    "projectedHomePoints": 27.0,
                    "projectedMarginHome": 10.0,
                    "projectedSpreadHome": -10.0,
                    "projectedTotal": 44.0,
                    "homeWinProbability": 72.0,
                    "projectedWinner": "Florida International",
                },
                {
                    "gameId": "g-id",
                    "awayTeam": "Away B",
                    "homeTeam": "Home B",
                    "kickoff": "2026-10-20T23:30:00Z",
                    "projectedAwayPoints": 31.0,
                    "projectedHomePoints": 24.0,
                    "projectedMarginHome": -7.0,
                    "projectedSpreadHome": 7.0,
                    "projectedTotal": 55.0,
                    "homeWinProbability": 33.0,
                    "projectedWinner": "Away B",
                },
                {
                    "gameId": "g-alias-lock",
                    "awayTeam": "UConn",
                    "homeTeam": "Miami",
                    "kickoff": "2026-10-21T00:00:00Z",
                    "projectedAwayPoints": 21.0,
                    "projectedHomePoints": 24.0,
                    "projectedMarginHome": 3.0,
                    "projectedSpreadHome": -3.0,
                    "projectedTotal": 45.0,
                    "homeWinProbability": 57.0,
                    "projectedWinner": "Miami",
                },
            ],
        }
        return build_lock(source, datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc))

    def _benchmark(self):
        return {
            "league": "cfb",
            "season": 2026,
            "week": 8,
            "role": "OFFICIAL_EXTERNAL_BENCHMARK_SNAPSHOT",
            "canonicalInfluence": False,
            "source": {
                "sourceId": "sagarin-cfb",
                "publisher": "Jeff Sagarin",
                "officialUrl": "https://sagarin.com/sports/cfsend.htm",
                "observedAt": "2026-10-20T11:45:56Z",
                "ratingsThrough": "2026-10-17",
                "sourceWeek": 7,
            },
            "games": [
                {
                    "gameId": "different-id",
                    "sourceGameId": "100",
                    "awayTeam": "Middle Tennessee",
                    "homeTeam": "FIU",
                    "kickoff": "2026-10-20T23:00:00Z",
                    "sagarin": {
                        "status": "CURRENT",
                        "impliedHomeMargin": 12.0,
                        "impliedSpreadHome": -12.0,
                        "predictorFavorite": "FIU",
                        "observedAt": "2026-10-20T11:45:56Z",
                        "ratingsThrough": "2026-10-17",
                    },
                },
                {
                    "gameId": "g-id",
                    "awayTeam": "Away B",
                    "homeTeam": "Home B",
                    "kickoff": "2026-10-20T23:30:00Z",
                    "sagarin": {
                        "status": "CURRENT",
                        "impliedHomeMargin": 1.0,
                        "impliedSpreadHome": -1.0,
                        "predictorFavorite": "Home B",
                        "observedAt": "2026-10-20T11:45:56Z",
                        "ratingsThrough": "2026-10-17",
                    },
                },
                {
                    "gameId": "different-alias-id",
                    "awayTeam": "Connecticut",
                    "homeTeam": "Miami-Florida",
                    "kickoff": "2026-10-21T00:00:00Z",
                    "sagarin": {
                        "status": "CURRENT",
                        "impliedHomeMargin": 8.0,
                        "impliedSpreadHome": -8.0,
                        "predictorFavorite": "Miami-Florida",
                        "observedAt": "2026-10-20T11:45:56Z",
                        "ratingsThrough": "2026-10-17",
                    },
                },
            ],
        }

    def _aliases(self):
        return {
            "floridainternational": "FIU",
            "fiu": "FIU",
            "uconn": "UConn",
            "connecticut": "UConn",
            "miami": "Miami",
            "miamiflorida": "Miami",
        }

    def test_bucket_boundaries(self):
        self.assertEqual(disagreement_bucket(0.0), "LT_2")
        self.assertEqual(disagreement_bucket(1.999), "LT_2")
        self.assertEqual(disagreement_bucket(2.0), "2_TO_LT_5")
        self.assertEqual(disagreement_bucket(4.999), "2_TO_LT_5")
        self.assertEqual(disagreement_bucket(5.0), "5_TO_LT_10")
        self.assertEqual(disagreement_bucket(9.999), "5_TO_LT_10")
        self.assertEqual(disagreement_bucket(10.0), "GE_10")

    def test_matching_priority_source_id_game_id_then_alias_kickoff(self):
        lock = self._lock()
        bench = self._benchmark()["games"]
        aliases = self._aliases()
        self.assertEqual(match_benchmark(lock["games"][0], bench, aliases)["gameId"], "different-id")
        self.assertEqual(match_benchmark(lock["games"][1], bench, aliases)["gameId"], "g-id")
        self.assertEqual(match_benchmark(lock["games"][2], bench, aliases)["gameId"], "different-alias-id")

    def test_comparison_math_coverage_and_direction(self):
        out = build_comparison(self._lock(), self._benchmark(), self._aliases())
        self.assertEqual(out["role"], "FROZEN_MODEL_VS_OFFICIAL_BENCHMARK_COMPARISON")
        self.assertFalse(out["canonicalInfluence"])
        self.assertFalse(out["canonicalPromotionAuthorized"])
        self.assertEqual(out["coverage"]["comparedGames"], 3)
        self.assertEqual(out["coverage"]["ratio"], 1.0)
        self.assertEqual(out["coverage"]["reviewGames"], [])

        first = out["games"][0]
        self.assertAlmostEqual(first["comparison"]["cbMinusSagarinHomeMargin"], -2.0)
        self.assertAlmostEqual(first["comparison"]["absoluteDisagreement"], 2.0)
        self.assertEqual(first["comparison"]["disagreementBucket"], "2_TO_LT_5")
        self.assertTrue(first["comparison"]["directionalWinnerAgreement"])

        second = out["games"][1]
        self.assertAlmostEqual(second["comparison"]["cbMinusSagarinHomeMargin"], -8.0)
        self.assertFalse(second["comparison"]["directionalWinnerAgreement"])
        self.assertEqual(second["comparison"]["disagreementBucket"], "5_TO_LT_10")

        third = out["games"][2]
        self.assertAlmostEqual(third["comparison"]["cbMinusSagarinHomeMargin"], -5.0)
        self.assertTrue(third["comparison"]["directionalWinnerAgreement"])
        self.assertAlmostEqual(out["aggregate"]["meanAbsoluteDisagreement"], 5.0)
        self.assertAlmostEqual(out["aggregate"]["medianAbsoluteDisagreement"], 5.0)
        self.assertAlmostEqual(out["aggregate"]["directionalWinnerAgreement"]["pct"], 200.0 / 3.0)
        self.assertEqual(out["largestDisagreements"][0]["gameId"], "g-id")

    def test_tampered_foundation_lock_is_rejected(self):
        lock = self._lock()
        lock["games"][0]["projectedMarginHome"] = 999.0
        with self.assertRaisesRegex(ValueError, "digest"):
            build_comparison(lock, self._benchmark(), self._aliases())


if __name__ == "__main__":
    unittest.main()
