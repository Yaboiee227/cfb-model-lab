import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from cfb_multiseason_walkforward import evaluate


def make_row(week, i, margin, total):
    x = [
        margin + (0.5 if i % 2 == 0 else -0.5),
        total + (0.8 if i % 3 == 0 else -0.8),
        (i % 5) / 5.0,
        (i % 7) / 7.0,
        (i % 4) / 4.0,
        (i % 6) / 6.0,
        (i % 3) / 30.0,
        (i % 8) / 8.0,
        (i % 5) / 20.0,
        125.0 + (i % 9),
        (i % 4) / 10.0,
        float((i % 7) - 3),
        float((i % 3) - 1),
    ]
    return {"weekStart": week, "x": x, "margin": float(margin), "total": float(total)}


class TestMultiseasonWalkforward(unittest.TestCase):
    def test_prior_season_enables_multiple_current_season_folds(self):
        prior = []
        for w in range(6):
            week = f"2025-09-{1+w*7:02d}T00:00:00Z"
            for i in range(35):
                prior.append(make_row(week, i + w*100, ((i*2+w)%21)-10, 48+((i+w)%17)))
        current = []
        current_weeks = [
            "2026-09-07T00:00:00Z",
            "2026-09-14T00:00:00Z",
            "2026-09-21T00:00:00Z",
            "2026-09-28T00:00:00Z",
            "2026-10-05T00:00:00Z",
        ]
        for w, week in enumerate(current_weeks):
            for i in range(25):
                current.append(make_row(week, i + w*1000, ((i*3+w)%23)-11, 50+((i+w)%15)))
        out = evaluate(prior, current)
        self.assertGreaterEqual(len(out["folds"]), 3)
        self.assertGreater(out["aggregate"]["games"], 0)
        self.assertIn(out["evidenceStatus"], {"RICH_REJECTED", "RICH_SHADOW_ELIGIBLE"})
        for fold in out["folds"]:
            self.assertEqual(fold["priorSeasonRows"], len(prior))
            self.assertGreaterEqual(fold["trainingRows"], len(prior))


if __name__ == "__main__":
    unittest.main()
