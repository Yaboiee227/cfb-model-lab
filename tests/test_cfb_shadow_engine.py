import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from cfb_shadow_engine import (
    Game,
    fit_model,
    matchup_code,
    predict,
    recency_weight,
    team_key,
)

UTC = timezone.utc


class TestCfbShadowEngine(unittest.TestCase):
    def synthetic_games(self):
        games = []
        base = datetime(2026, 9, 1, 16, tzinfo=UTC)
        scores = [
            ("a", "b", 35, 17),
            ("b", "a", 14, 31),
            ("a", "c", 38, 20),
            ("c", "a", 21, 34),
            ("b", "c", 24, 21),
            ("c", "b", 20, 27),
        ]
        for i in range(24):
            home, away, hs, aas = scores[i % len(scores)]
            games.append(Game(str(i), base.replace(day=1 + i), home, away, hs, aas, False))
        return games

    def test_prediction_is_market_independent_scoring_output(self):
        games = self.synthetic_games()
        as_of = datetime(2026, 10, 1, tzinfo=UTC)
        model = fit_model(games, as_of, alpha=10.0, half_life_days=35)
        row = predict(model, "b", "a")
        self.assertGreater(row["projectedHomePoints"], row["projectedAwayPoints"])
        self.assertAlmostEqual(row["projectedTotal"], row["projectedHomePoints"] + row["projectedAwayPoints"])
        self.assertAlmostEqual(row["projectedSpreadHome"], -row["projectedMarginHome"])

    def test_recency_weight_never_uses_future_age(self):
        as_of = datetime(2026, 10, 1, tzinfo=UTC)
        same_day = recency_weight(as_of, as_of, 35)
        older = recency_weight(datetime(2026, 9, 1, tzinfo=UTC), as_of, 35)
        self.assertEqual(same_day, 1.0)
        self.assertLess(older, same_day)

    def test_week8_aliases_use_school_identity_not_abbreviation(self):
        self.assertEqual(matchup_code("Middle Tennessee"), "middletennessee")
        self.assertEqual(matchup_code("Middle Tennessee State"), "middletennessee")
        self.assertEqual(matchup_code("FIU"), "floridainternational")
        self.assertEqual(matchup_code("Florida International"), "floridainternational")
        self.assertEqual(matchup_code("Missouri State"), "missouristate")
        self.assertEqual(matchup_code("Delaware"), "delaware")
        self.assertEqual(matchup_code("South Alabama"), "southalabama")
        self.assertEqual(matchup_code("Marshall"), "marshall")

    def test_espn_team_key_prefers_location(self):
        self.assertEqual(
            team_key({"id": "2229", "location": "Florida International", "abbreviation": "FIU"}),
            "floridainternational",
        )
        self.assertEqual(
            team_key({"id": "2393", "location": "Middle Tennessee", "abbreviation": "MTSU"}),
            "middletennessee",
        )
        self.assertEqual(
            team_key({"id": "6", "location": "South Alabama", "abbreviation": "USA"}),
            "southalabama",
        )


if __name__ == "__main__":
    unittest.main()
