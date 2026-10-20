import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from cfb_canonical_reference import build_reference, game_eval, metric_block


class TestCfbCanonicalReference(unittest.TestCase):
    def test_home_spread_sign_is_converted_to_margin(self):
        row = {
            "gameId": "g1",
            "awayTeam": "A",
            "homeTeam": "H",
            "awayScore": "20",
            "homeScore": "30",
            "modelSpreadHome": "-7.5",
            "modelTotal": "48.0",
            "marketSpreadHome": "-3.0",
            "marketTotal": "50.0",
            "homeWinProbability": "70",
        }
        out = game_eval(row)
        self.assertEqual(out["actualMarginHome"], 10.0)
        self.assertEqual(out["modelMarginHome"], 7.5)
        self.assertEqual(out["marginError"], -2.5)
        self.assertEqual(out["marketMarginHome"], 3.0)
        self.assertEqual(out["totalError"], -2.0)
        self.assertTrue(out["suCorrect"])

    def test_metric_block(self):
        games = [
            {"marginError": 2.0, "totalError": -4.0, "marketMarginError": 1.0, "marketTotalError": -3.0, "suCorrect": True, "brier": 0.04, "atsResult": "WIN", "totalResult": "LOSS"},
            {"marginError": -6.0, "totalError": 2.0, "marketMarginError": -5.0, "marketTotalError": 1.0, "suCorrect": False, "brier": 0.36, "atsResult": "PUSH", "totalResult": "WIN"},
        ]
        block = metric_block(games)
        self.assertEqual(block["model"]["marginMae"], 4.0)
        self.assertEqual(block["model"]["totalMae"], 3.0)
        self.assertEqual(block["model"]["suAccuracyPct"], 50.0)
        self.assertAlmostEqual(block["model"]["brierScore"], 0.20)
        self.assertEqual(block["gradedPositions"]["ats"]["wins"], 1)
        self.assertEqual(block["gradedPositions"]["ats"]["pushes"], 1)

    def test_build_reference_dedupes_last_game_row(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            results = root / "results.csv"
            projections = root / "projections.csv"
            fields = ["season","week","gameId","awayTeam","homeTeam","conference","awayScore","homeScore","modelSpreadHome","marketSpreadHome","modelTotal","marketTotal","homeWinProbability","atsResult","totalResult","suResult","gradeReference"]
            with results.open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=fields)
                w.writeheader()
                w.writerow({"season":2026,"week":7,"gameId":"g1","awayTeam":"A","homeTeam":"H","conference":"ACC","awayScore":20,"homeScore":30,"modelSpreadHome":-1,"marketSpreadHome":-3,"modelTotal":40,"marketTotal":50,"homeWinProbability":55,"atsResult":"LOSS","totalResult":"WIN","suResult":"WIN","gradeReference":"old"})
                w.writerow({"season":2026,"week":7,"gameId":"g1","awayTeam":"A","homeTeam":"H","conference":"ACC","awayScore":20,"homeScore":30,"modelSpreadHome":-7,"marketSpreadHome":-3,"modelTotal":50,"marketTotal":50,"homeWinProbability":75,"atsResult":"WIN","totalResult":"PUSH","suResult":"WIN","gradeReference":"new"})
            with projections.open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=["season","week","gameId","signalStrength","releaseStatus"])
                w.writeheader()
                w.writerow({"season":2026,"week":7,"gameId":"g1","signalStrength":"HIGH","releaseStatus":"HOLD"})

            out = build_reference(results, projections, 2026, 7)
            self.assertEqual(out["overall"]["games"], 1)
            self.assertEqual(out["games"][0]["marginError"], -3.0)
            self.assertEqual(out["games"][0]["signalStrength"], "HIGH")
            self.assertEqual(out["games"][0]["gradeReference"], "new")


if __name__ == "__main__":
    unittest.main()
