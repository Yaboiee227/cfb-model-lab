import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from cfb_rich_challenger import normalized_box, ridge_fit, ridge_predict, week_start

UTC = timezone.utc


class TestCfbRichChallenger(unittest.TestCase):
    def test_normalized_box(self):
        stats = [
            {"name": "completionAttempts", "displayValue": "20/30"},
            {"name": "rushingAttempts", "displayValue": "40"},
            {"name": "totalYards", "displayValue": "420"},
            {"name": "netPassingYards", "displayValue": "240"},
            {"name": "rushingYards", "displayValue": "180"},
            {"name": "thirdDownEff", "displayValue": "6-12"},
            {"name": "turnovers", "displayValue": "1"},
            {"name": "firstDowns", "displayValue": "24"},
            {"name": "totalPenaltiesYards", "displayValue": "7-65"},
            {"name": "possessionTime", "displayValue": "32:30"},
        ]
        box = normalized_box(stats)
        self.assertEqual(box["plays"], 70)
        self.assertAlmostEqual(box["yardsPerPlay"], 6.0)
        self.assertAlmostEqual(box["passYpa"], 8.0)
        self.assertAlmostEqual(box["rushYpa"], 4.5)
        self.assertAlmostEqual(box["thirdRate"], 0.5)
        self.assertAlmostEqual(box["turnoverRate"], 1/70)
        self.assertAlmostEqual(box["firstDownRate"], 24/70)
        self.assertAlmostEqual(box["penaltyYardsPerPlay"], 65/70)
        self.assertAlmostEqual(box["possessionShare"], 32.5/60)

    def test_week_start_is_monday_utc(self):
        dt = datetime(2026, 10, 17, 19, 30, tzinfo=UTC)
        self.assertEqual(week_start(dt), datetime(2026, 10, 12, 0, 0, tzinfo=UTC))

    def test_ridge_fit_predicts_linear_signal(self):
        rows = []
        for i in range(20):
            x = [float(i), float(i % 3)] + [0.0] * 11
            rows.append({"x": x, "margin": 2.0 + 3.0 * i, "total": 40.0 + i})
        model = ridge_fit(rows, (0,), "margin", 0.1)
        pred = ridge_predict(model, [{"x": [5.0] + [0.0] * 12}])[0]
        self.assertTrue(np.isfinite(pred))
        self.assertAlmostEqual(pred, 17.0, delta=0.5)


if __name__ == "__main__":
    unittest.main()
