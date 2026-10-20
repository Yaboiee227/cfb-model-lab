import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from cfb_shadow_engine import Game, fit_model, predict, recency_weight, matchup_code

UTC = timezone.utc


class TestCfbShadowEngine(unittest.TestCase):
    def synthetic_games(self):
        games = []
        base = datetime(2026, 9, 1, 16, tzinfo=UTC)
        # A is stronger offensively than B; C provides a third opponent so the
        # ridge fit is not a one-matchup toy.
        scores = [
            ("A", "B", 35, 17),
            ("B", "A", 14, 31),
            ("A", "C", 38, 20),
            ("C", "A", 21, 34),
            ("B", "C", 24, 21),
            ("C", "B", 20, 27),
        ]
        for i in range(24):
            home, away, hs, aas = scores[i % len(scores)]
            games.append(Game(str(i), base.replace(day=1 + i), home, away, hs, aas, False))
        return games

    def test_prediction_is_market_independent_scoring_output(self):
        games = self.synthetic_games()
        as_of = datetime(2026, 10, 1, tzinfo=UTC)
        model = fit_model(games, as_of, alpha=10.0, half_life_days=35)
        row = predict(model, "B", "A")
        self.assertGreater(row["projectedHomePoints"], row["projectedAwayPoints"])
        self.assertAlmostEqual(row["projectedTotal"], row["projectedHomePoints"] + row["projectedAwayPoints"])
        self.assertAlmostEqual(row["projectedSpreadHome"], -row["projectedMarginHome"])

    def test_recency_weight_never_uses_future_age(self):
        as_of = datetime(2026, 10, 1, tzinfo=UTC)
        same_day = recency_weight(as_of, as_of, 35)
        older = recency_weight(datetime(2026, 9, 1, tzinfo=UTC), as_of, 35)
        self.assertEqual(same_day, 1.0)
        self.assertLess(older, same_day)

    def test_week8_aliases(self):
        self.assertEqual(matchup_code("Middle Tennessee"), "MTSU")
        self.assertEqual(matchup_code("FIU"), "FIU")
        self.assertEqual(matchup_code("Missouri State"), "MOST")
        self.assertEqual(matchup_code("Delaware"), "DEL")
        self.assertEqual(matchup_code("South Alabama"), "USA")
        self.assertEqual(matchup_code("Marshall"), "MRSH")


if __name__ == "__main__":
    unittest.main()
