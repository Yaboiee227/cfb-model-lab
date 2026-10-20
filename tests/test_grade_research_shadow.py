import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from grade_research_shadow import grade, preserve_graded_at_if_unchanged
from lock_research_shadow import build_lock


class TestGradeResearchShadow(unittest.TestCase):
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
            "source": {"marketDataUsed": False},
            "games": [
                {
                    "gameId": "g1",
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
                    "awayTeam": "Away B",
                    "homeTeam": "Home B",
                    "kickoff": "2026-10-20T23:30:00Z",
                    "projectedAwayPoints": 28.0,
                    "projectedHomePoints": 24.0,
                    "projectedMarginHome": -4.0,
                    "projectedSpreadHome": 4.0,
                    "projectedTotal": 52.0,
                    "homeWinProbability": 40.0,
                    "projectedWinner": "Away B",
                },
            ],
        }
        return build_lock(source, datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc))

    def _scores(self):
        return [
            {
                "awayTeam": "Away A",
                "homeTeam": "Home A",
                "awayScore": 24,
                "homeScore": 31,
                "status": "FINAL",
                "overtime": False,
                "source": "ESPN",
            },
            {
                "awayTeam": "Away B",
                "homeTeam": "Home B",
                "awayScore": 0,
                "homeScore": 0,
                "status": "PENDING",
                "overtime": False,
                "source": "ESPN",
            },
        ]

    def test_grades_final_and_preserves_pending_without_canonical_merge(self):
        lock = self._lock()
        out = grade(lock, self._scores(), {})
        self.assertEqual(out["status"], "IN_PROGRESS")
        self.assertFalse(out["canonicalInfluence"])
        self.assertFalse(out["canonicalRecordMerged"])
        self.assertEqual(out["sourceLockDigest"], lock["lockDigest"])
        self.assertEqual(out["counts"], {"games": 2, "final": 1, "pending": 1, "review": 0, "void": 0})
        self.assertAlmostEqual(out["metrics"]["margin"]["mae"], 3.0)
        self.assertAlmostEqual(out["metrics"]["margin"]["bias"], 3.0)
        self.assertAlmostEqual(out["metrics"]["total"]["mae"], 5.0)
        self.assertEqual(out["metrics"]["straightUp"]["wins"], 1)
        self.assertAlmostEqual(out["metrics"]["winProbability"]["brierScore"], 0.0625)
        self.assertEqual(out["games"][0]["projectionDigest"], lock["games"][0]["projectionDigest"])

    def test_unchanged_result_preserves_graded_at(self):
        lock = self._lock()
        existing = grade(lock, self._scores(), {})
        existing["gradedAt"] = "2026-10-21T04:00:00Z"
        new = grade(lock, self._scores(), {})
        out = preserve_graded_at_if_unchanged(new, copy.deepcopy(existing))
        self.assertEqual(out["gradedAt"], "2026-10-21T04:00:00Z")

    def test_changed_result_refreshes_graded_at(self):
        lock = self._lock()
        existing = grade(lock, self._scores(), {})
        existing["gradedAt"] = "2026-10-21T04:00:00Z"
        changed_scores = self._scores()
        changed_scores[0]["homeScore"] = 32
        new = grade(lock, changed_scores, {})
        out = preserve_graded_at_if_unchanged(new, existing)
        self.assertNotEqual(out["gradedAt"], "2026-10-21T04:00:00Z")

    def test_rejects_tampered_lock(self):
        lock = self._lock()
        lock["games"][0]["projectedTotal"] = 999.0
        with self.assertRaises(ValueError):
            grade(lock, [], {})


if __name__ == "__main__":
    unittest.main()
