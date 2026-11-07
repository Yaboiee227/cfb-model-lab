import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from evaluate_projection_records import evaluate


class RecordEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.row = {"gameId": "g", "season": "2026", "week": "9", "trackingClass": "RESEARCH",
                    "homeScore": "24", "awayScore": "20", "modelSpreadHome": "-3", "marketSpreadHome": "-5",
                    "modelTotal": "45", "marketTotal": "43", "homeWinProbability": "75",
                    "atsResult": "PUSH", "totalResult": "LOSS", "suResult": "WIN"}

    def test_signs_probabilities_and_stored_grades(self):
        r = evaluate([self.row], "nfl")[0]
        self.assertEqual(r["metrics"]["margin"]["allStoredModel"]["bias"], -1)
        self.assertEqual(r["metrics"]["total"]["allStoredModel"]["bias"], 1)
        self.assertEqual(r["winProbability"]["brier"], .0625)
        self.assertEqual(r["storedGrades"]["ats"], {"PUSH": 1})

    def test_pairing_excludes_missing_reference(self):
        r = evaluate([self.row, {**self.row, "gameId": "x", "marketSpreadHome": ""}], "cfb")[0]
        self.assertEqual(r["metrics"]["margin"]["allStoredModel"]["n"], 2)
        self.assertEqual(r["metrics"]["margin"]["pairedStoredModel"]["n"], 1)

    def test_zero_eligible_rows_and_tied_outcome(self):
        r = evaluate([{**self.row, "modelSpreadHome": "nan", "modelTotal": "", "awayScore": "24"}], "nfl")[0]
        self.assertIsNone(r["metrics"]["margin"]["pairedMaeDelta"])
        self.assertEqual(r["winProbability"]["n"], 0)

    def test_week_and_tracking_separation_and_duplicates(self):
        self.assertEqual(len(evaluate([self.row, {**self.row, "gameId": "x", "week": "8"},
                                     {**self.row, "gameId": "y", "trackingClass": "LEGACY"}], "cfb")), 3)
        with self.assertRaises(ValueError):
            evaluate([self.row, self.row], "cfb")


if __name__ == "__main__":
    unittest.main()
