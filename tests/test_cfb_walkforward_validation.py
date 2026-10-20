import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from cfb_walkforward_validation import evaluate_rows


def row(week, i, margin, total):
    # 13-feature vector. The first two entries are the simple causal shadow
    # predictions; remaining values provide stable variation for ridge fitting.
    x = [
        margin + (0.8 if i % 2 == 0 else -0.8),
        total + (1.0 if i % 3 == 0 else -1.0),
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
    return {
        "gameId": f"{week}-{i}",
        "kickoff": f"2026-09-{1+i%20:02d}T16:00:00Z",
        "weekStart": week,
        "home": f"h{i}",
        "away": f"a{i}",
        "x": x,
        "margin": margin,
        "total": total,
    }


class TestCfbWalkForwardValidation(unittest.TestCase):
    def test_nested_weekly_evaluation_produces_unseen_folds(self):
        weeks = [
            "2026-08-24T00:00:00Z",
            "2026-08-31T00:00:00Z",
            "2026-09-07T00:00:00Z",
            "2026-09-14T00:00:00Z",
            "2026-09-21T00:00:00Z",
            "2026-09-28T00:00:00Z",
        ]
        rows = []
        for widx, week in enumerate(weeks):
            for i in range(30):
                margin = float(((i * 3 + widx) % 21) - 10)
                total = float(48 + ((i + widx) % 15))
                rows.append(row(week, i + 100 * widx, margin, total))
        out = evaluate_rows(rows)
        self.assertGreaterEqual(len(out["folds"]), 2)
        self.assertGreater(out["aggregate"]["games"], 0)
        for fold in out["folds"]:
            self.assertNotEqual(fold["testWeekStart"], fold["previousWeekInnerValidation"])
            self.assertGreaterEqual(fold["trainRows"], 70)
            self.assertGreaterEqual(fold["testRows"], 10)
        self.assertIn("prospectiveShadowGatePass", out)


if __name__ == "__main__":
    unittest.main()
