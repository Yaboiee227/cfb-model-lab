import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from cfb_benchmark_compare import build_comparison
from cfb_benchmark_postgame import grade, preserve_graded_at_if_unchanged, verify_pregame_comparison
from lock_research_shadow import build_lock


class TestCfbBenchmarkPostgame(unittest.TestCase):
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
                    "gameId": "g1",
                    "sourceGameId": "1",
                    "awayTeam": "Away A",
                    "homeTeam": "Home A",
                    "kickoff": "2026-10-20T23:00:00Z",
                    "projectedAwayPoints": 20.0,
                    "projectedHomePoints": 30.0,
                    "projectedMarginHome": 10.0,
                    "projectedSpreadHome": -10.0,
                    "projectedTotal": 50.0,
                    "homeWinProbability": 75.0,
                    "projectedWinner": "Home A",
                },
                {
                    "gameId": "g2",
                    "sourceGameId": "2",
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
                    "gameId": "g3",
                    "sourceGameId": "3",
                    "awayTeam": "Away C",
                    "homeTeam": "Home C",
                    "kickoff": "2026-10-21T00:00:00Z",
                    "projectedAwayPoints": 21.0,
                    "projectedHomePoints": 26.0,
                    "projectedMarginHome": 5.0,
                    "projectedSpreadHome": -5.0,
                    "projectedTotal": 47.0,
                    "homeWinProbability": 62.0,
                    "projectedWinner": "Home C",
                },
            ],
        }
        return build_lock(source, datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc))

    def _benchmark(self):
        base = {
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
            "games": [],
        }
        for gid, sid, away, home, kickoff, margin in [
            ("g1", "1", "Away A", "Home A", "2026-10-20T23:00:00Z", 4.0),
            ("g2", "2", "Away B", "Home B", "2026-10-20T23:30:00Z", 1.0),
            ("g3", "3", "Away C", "Home C", "2026-10-21T00:00:00Z", 9.0),
        ]:
            base["games"].append(
                {
                    "gameId": gid,
                    "sourceGameId": sid,
                    "awayTeam": away,
                    "homeTeam": home,
                    "kickoff": kickoff,
                    "sagarin": {
                        "status": "CURRENT",
                        "impliedHomeMargin": margin,
                        "impliedSpreadHome": -margin,
                        "predictorFavorite": home if margin > 0 else away,
                        "observedAt": "2026-10-20T11:45:56Z",
                        "ratingsThrough": "2026-10-17",
                    },
                }
            )
        return base

    def _comparison(self, lock=None):
        return build_comparison(lock or self._lock(), self._benchmark(), {})

    def _scores(self):
        return [
            {"sourceGameId": "1", "awayTeam": "Away A", "homeTeam": "Home A", "awayScore": 24, "homeScore": 30, "status": "FINAL", "overtime": False, "source": "ESPN"},
            {"sourceGameId": "2", "awayTeam": "Away B", "homeTeam": "Home B", "awayScore": 28, "homeScore": 25, "status": "FINAL", "overtime": False, "source": "ESPN"},
            {"sourceGameId": "3", "awayTeam": "Away C", "homeTeam": "Home C", "awayScore": 0, "homeScore": 0, "status": "PENDING", "overtime": False, "source": "ESPN"},
        ]

    def test_grades_same_final_set_and_directional_disagreement(self):
        lock = self._lock()
        out = grade(lock, self._comparison(lock), self._scores(), {})
        self.assertEqual(out["role"], "POSTGAME_FROZEN_MODEL_VS_OFFICIAL_BENCHMARK_EVALUATION")
        self.assertFalse(out["canonicalInfluence"])
        self.assertFalse(out["canonicalRecordMerged"])
        self.assertEqual(out["status"], "IN_PROGRESS")
        self.assertEqual(out["counts"], {"games": 3, "final": 2, "pending": 1, "review": 0, "void": 0})

        # g1 actual home margin +6: CB +10 error +4; Sagarin +4 error -2.
        g1 = out["games"][0]
        self.assertAlmostEqual(g1["postgameComparison"]["cbAbsoluteMarginError"], 4.0)
        self.assertAlmostEqual(g1["postgameComparison"]["sagarinAbsoluteMarginError"], 2.0)
        self.assertEqual(g1["postgameComparison"]["closerToFinalMargin"], "SAGARIN")
        self.assertTrue(g1["postgameComparison"]["cbStraightUpCorrect"])
        self.assertTrue(g1["postgameComparison"]["sagarinStraightUpCorrect"])

        # g2 actual margin -3 and pregame models picked opposite winners.
        g2 = out["games"][1]
        self.assertFalse(g2["comparison"]["directionalWinnerAgreement"])
        self.assertEqual(g2["postgameComparison"]["closerToFinalMargin"], "TIE")
        self.assertTrue(g2["postgameComparison"]["cbStraightUpCorrect"])
        self.assertFalse(g2["postgameComparison"]["sagarinStraightUpCorrect"])

        agg = out["aggregate"]
        self.assertEqual(agg["closerToFinalMargin"], {"CB": 0, "SAGARIN": 1, "TIE": 1})
        self.assertAlmostEqual(agg["cbMargin"]["mae"], 4.0)
        self.assertAlmostEqual(agg["sagarinMargin"]["mae"], 3.0)
        self.assertEqual(agg["cbStraightUp"]["correct"], 2)
        self.assertEqual(agg["sagarinStraightUp"]["correct"], 1)
        self.assertEqual(agg["directionalDisagreementGames"]["games"], 1)
        self.assertEqual(agg["directionalDisagreementGames"]["cbSuCorrect"], 1)
        self.assertEqual(agg["directionalDisagreementGames"]["sagarinSuCorrect"], 0)

    def test_rejects_postkickoff_benchmark_observation(self):
        lock = self._lock()
        comparison = self._comparison(lock)
        comparison["games"][0]["sagarin"]["observedAt"] = "2026-10-21T01:00:00Z"
        with self.assertRaisesRegex(ValueError, "not pregame"):
            verify_pregame_comparison(lock, comparison)

    def test_rejects_changed_cb_projection(self):
        lock = self._lock()
        comparison = self._comparison(lock)
        comparison["games"][0]["foundation"]["projectedHomeMargin"] = 999.0
        with self.assertRaisesRegex(ValueError, "changed after lock"):
            verify_pregame_comparison(lock, comparison)

    def test_idempotent_timestamp_when_results_unchanged(self):
        lock = self._lock()
        comparison = self._comparison(lock)
        existing = grade(lock, comparison, self._scores(), {})
        existing["gradedAt"] = "2026-10-21T04:00:00Z"
        new = grade(lock, comparison, self._scores(), {})
        out = preserve_graded_at_if_unchanged(new, copy.deepcopy(existing))
        self.assertEqual(out["gradedAt"], "2026-10-21T04:00:00Z")


if __name__ == "__main__":
    unittest.main()
