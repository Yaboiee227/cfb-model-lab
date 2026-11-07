import csv
import gzip
import io
import json
import math
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from projection_resource_evidence import (cfb_slate, compare_forecasts, cycle, instant,
    nfl_slate, number, save_new, summarize_errors, team_key, validate_observation)
from capture_projection_resources import nfl_features, pirate_margins


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.now = instant("2026-11-07T00:00:00Z")
        self.game = {"gameId": "a", "homeTeam": "Home", "awayTeam": "Away",
                     "kickoff": "2026-11-07T18:00:00Z", "neutralSite": False}
        self.obs = {**self.game, "league": "cfb", "canonicalInfluence": False,
                    "vintage": "game_week", "collectedAt": "2026-11-07T00:00:01Z",
                    "sourceObservedAt": "2026-11-07T00:00:00Z", "homeMargin": 4.0,
                    "sourceSha256": "a"*64, "sourceUrl": "https://example.com", "sourceId": "x",
                    "family": "x", "conversion": "direct", "role": "external_benchmark"}
        self.forecast = {**self.game, "homeMargin": 3.0, "frozenAt": "2026-11-03T12:00:00Z"}

    def test_naive_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            instant("2026-11-07T00:00:00")

    def test_nonfinite_and_bool_missing(self):
        for value in ["nan", "inf", True, None, ""]:
            self.assertIsNone(number(value))

    def test_cycle_uses_eastern_date_and_keeps_monday(self):
        self.assertEqual(str(cycle(self.now)[0]), "2026-11-03")
        self.assertEqual(str(cycle(instant("2026-11-10T01:00:00Z"))[0]), "2026-11-03")
        self.assertEqual(str(cycle(instant("2026-11-10T06:00:00Z"))[0]), "2026-11-10")

    def test_nfl_resolves_current_week_not_published_config(self):
        rows = [{"game_type": "REG", "season": "2026", "week": "9", "game_id": "g",
                 "gameday": "2026-11-08", "gametime": "13:00", "home_team": "H", "away_team": "A"}]
        slate = nfl_slate(rows, self.now)
        self.assertEqual(slate["week"], 9)
        self.assertEqual(slate["games"][0]["kickoff"], "2026-11-08T18:00:00+00:00")
        with self.assertRaises(ValueError):
            nfl_slate(rows*2, self.now)

    def test_stale_cfb_schedule_cannot_fall_back(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / "cfb/pregame").mkdir(parents=True)
            (root / "cfb/pregame/week-09-schedule.json").write_text(json.dumps({"dateWindowET": ["2026-10-27", "2026-10-31"]}))
            with self.assertRaises(ValueError):
                cfb_slate(root, self.now)

    def test_capture_is_write_once(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "capture.json"
            save_new(path, {"a": 1})
            with self.assertRaises(FileExistsError):
                save_new(path, {"a": 2})
            self.assertEqual(json.loads(path.read_text()), {"a": 1})

    def test_postkickoff_and_retrospective_benchmarks_rejected(self):
        for update in [{"collectedAt": self.game["kickoff"]}, {"vintage": "postseason"},
                       {"canonicalInfluence": True}, {"homeMargin": float("nan")},
                       {"sourceObservedAt": "2026-11-07T01:00:00Z"},
                       {"homeTeam": "Wrong"}, {"sourceSha256": ""}]:
            with self.subTest(update=update), self.assertRaises(ValueError):
                validate_observation({**self.obs, **update}, self.game)

    def test_aliases_do_not_collapse_miamis(self):
        aliases = {"Miami": ["Miami FL"], "Miami (OH)": ["Miami Ohio"]}
        self.assertNotEqual(team_key("Miami FL", aliases), team_key("Miami Ohio", aliases))
        self.assertEqual(team_key("Ohio St.", aliases), team_key("Ohio State", aliases))

    def test_empty_metrics_are_unavailable_not_zero(self):
        self.assertIsNone(summarize_errors([])["mae"])
        self.assertAlmostEqual(summarize_errors([(3, 1), (5, 9)])["rmse"], math.sqrt(10))

    def test_paired_samples_and_different_origins_explicit(self):
        result = {"a": {"status": "FINAL", "observedAt": "2026-11-07T22:00:00Z", "homeScore": 24, "awayScore": 20}}
        r = compare_forecasts("cfb", [self.game], [self.forecast], [self.obs], result)
        self.assertFalse(r["rows"][0]["sameOrigin"])
        self.assertFalse(r["rows"][0]["agreementIsConfidence"])
        self.assertEqual(r["pairedMarginMetrics"]["x"]["cb"]["n"], 1)
        self.assertEqual(r["pairedMarginMetrics"]["x"]["cb"]["mae"], 1)

    def test_no_freeze_does_not_create_projection(self):
        r = compare_forecasts("cfb", [self.game], [], [self.obs])
        self.assertEqual(r["rows"], [])
        self.assertEqual(r["excluded"][0]["reason"], "no matching CB freeze")

    def test_duplicate_sources_and_nonfinal_scores_rejected(self):
        with self.assertRaises(ValueError):
            compare_forecasts("cfb", [self.game], [self.forecast], [self.obs]*2)
        with self.assertRaises(ValueError):
            compare_forecasts("cfb", [self.game], [self.forecast], [self.obs], {
                "a": {"status": "IN_PROGRESS", "observedAt": "2026-11-07T20:00:00Z"}})

    def test_pirate_does_not_attach_prior_cfb_title_to_new_nfl_post(self):
        table = '<table><tr><td>Home</td><td>Visitor</td><td>PiRate</td></tr><tr><td>Home</td><td>Away</td><td>4</td></tr></table>'
        html = '<h3>PiRate Ratings College Football For Week 99: November 3-7, 2026</h3>' + table
        html += '<h3>PiRate Ratings NFL For Week 8: October 29-November 2, 2026</h3>' + table
        result = pirate_margins(html, {"games": [self.game]}, {}, self.now)
        self.assertEqual(result, {"a": 4.0})


class PbpTests(unittest.TestCase):
    def setUp(self):
        self.row = {"game_id": "g8", "play_id": "1", "season": "2026", "week": "8", "season_type": "REG",
                    "posteam": "A", "defteam": "H", "epa": "2", "pass": "1.0", "rush": "0",
                    "qb_kneel": "0", "qb_spike": "0", "play_type": "pass", "qtr": "1"}
        self.schedule = [{"game_id": "g8", "season": "2026", "week": "8", "game_type": "REG",
                          "home_team": "H", "away_team": "A", "home_score": "24", "away_score": "20", "gameday": "2026-11-01"}]
        self.slate = {"season": 2026, "week": 9, "games": []}

    def run_rows(self, rows):
        text = io.StringIO(); writer = csv.DictWriter(text, fieldnames=list(self.row)); writer.writeheader(); writer.writerows(rows)
        return nfl_features(gzip.compress(text.getvalue().encode()), self.schedule, self.slate, "2026-11-07T00:00:00Z")

    def test_current_week_no_plays_ot_and_missing_epa_excluded(self):
        rows = [self.row]
        for i, update in enumerate([{"game_id": "g9", "week": "9"}, {"play_type": "no_play"},
                                    {"qtr": "5"}, {"epa": ""}, {"qb_kneel": "1.0"}, {"qb_spike": "1"}]):
            rows.append({**self.row, "play_id": str(i+2), **update})
        result = self.run_rows(rows)
        self.assertEqual(len(result["features"]), 2)
        self.assertTrue(all(f["plays"] == 1 and f["maxSourceWeek"] == 8 for f in result["features"]))
        self.assertFalse(result["historicalPregameAvailabilityCertified"])

    def test_duplicate_eligible_play_rejected(self):
        with self.assertRaises(ValueError):
            self.run_rows([self.row, self.row])

    def test_schedule_week_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            self.run_rows([{**self.row, "week": "9"}])

    def test_missing_prior_game_is_reported(self):
        self.schedule.append({**self.schedule[0], "game_id": "missing"})
        result = self.run_rows([self.row])
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["missingPriorGameIds"], ["missing"])


if __name__ == "__main__":
    unittest.main()
