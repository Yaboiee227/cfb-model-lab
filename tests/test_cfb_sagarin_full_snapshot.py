import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from cfb_sagarin_full_snapshot import build_snapshot, parse_ratings, verify_crosscheck


def sagarin_text() -> str:
    teams = [
        ("Middle Tennessee", 71.0, 70.0),
        ("Fla. International", 76.0, 78.0),
        ("Missouri State", 72.0, 73.0),
        ("Delaware", 75.0, 76.0),
        ("South Alabama", 80.0, 82.0),
        ("Marshall", 77.0, 78.0),
    ]
    for i in range(1, 116):
        teams.append((f"Synthetic Team {i}", 50.0 + i / 100.0, 49.0 + i / 100.0))
    lines = [
        "2026 College Football through games of October 17 Saturday - Week 7",
        "HOME ADVANTAGE=[ 3.82] [ 3.80]",
    ]
    for rank, (name, rating, predictor) in enumerate(teams, 1):
        lines.append(
            f" {rank:3d} {name} A = {rating:.2f} some columns | 6 1 | {predictor:.2f} {rank:3d} |"
        )
    return "\n".join(lines)


def three_game_schedule():
    return {
        "season": 2026,
        "week": 8,
        "games": [
            {
                "gameId": "full-fi",
                "sourceGameId": "1",
                "awayTeam": "Middle Tennessee",
                "homeTeam": "Florida International",
                "kickoff": "2026-10-20T23:00:00Z",
                "neutralSite": False,
            },
            {
                "gameId": "full-de",
                "sourceGameId": "2",
                "awayTeam": "Missouri State",
                "homeTeam": "Delaware",
                "kickoff": "2026-10-20T23:00:00Z",
                "neutralSite": False,
            },
            {
                "gameId": "full-ma",
                "sourceGameId": "3",
                "awayTeam": "South Alabama",
                "homeTeam": "Marshall",
                "kickoff": "2026-10-20T23:30:00Z",
                "neutralSite": False,
            },
        ],
    }


class TestCfbSagarinFullSnapshot(unittest.TestCase):
    def test_parses_predictor_hfa_and_source_metadata(self):
        ratings, hfa, meta = parse_ratings(sagarin_text())
        self.assertGreaterEqual(len(ratings), 120)
        self.assertAlmostEqual(hfa, 3.80)
        self.assertEqual(meta["sourceWeek"], 7)
        self.assertEqual(meta["ratingsThrough"], "October 17 Saturday")
        self.assertAlmostEqual(ratings["floridainternational"]["predictor"], 78.0)
        self.assertEqual(ratings["floridainternational"]["sourceName"], "Fla. International")

    def test_builds_home_and_neutral_implied_margins(self):
        schedule = {
            "season": 2026,
            "week": 8,
            "games": [
                three_game_schedule()["games"][0],
                {
                    "gameId": "neutral",
                    "sourceGameId": "4",
                    "awayTeam": "South Alabama",
                    "homeTeam": "Marshall",
                    "kickoff": "2026-10-20T23:30:00Z",
                    "neutralSite": True,
                },
            ],
        }
        out = build_snapshot(
            schedule,
            sagarin_text(),
            {},
            "2026-10-20T12:00:00Z",
            min_coverage=1.0,
            transport={"tlsVerified": False, "certificateWorkaroundUsed": True, "warning": "test"},
        )
        self.assertEqual(out["role"], "OFFICIAL_EXTERNAL_BENCHMARK_SNAPSHOT")
        self.assertFalse(out["canonicalInfluence"])
        self.assertEqual(out["source"]["sourceId"], "sagarin-cfb")
        self.assertEqual(out["source"]["ratingsThrough"], "2026-10-17")
        self.assertEqual(out["source"]["ratingsThroughLabel"], "October 17 Saturday")
        self.assertFalse(out["source"]["transport"]["tlsVerified"])
        self.assertEqual(out["coverage"]["ratio"], 1.0)

        home = out["games"][0]["sagarin"]
        self.assertEqual(home["observedAt"], "2026-10-20T12:00:00Z")
        self.assertEqual(home["ratingsThrough"], "2026-10-17")
        self.assertAlmostEqual(home["impliedHomeMargin"], 11.8)
        self.assertAlmostEqual(home["impliedSpreadHome"], -11.8)
        self.assertEqual(home["predictorFavorite"], "Florida International")
        self.assertEqual(home["homeSourceName"], "Fla. International")

        neutral = out["games"][1]["sagarin"]
        self.assertAlmostEqual(neutral["predictorHomeAdvantage"], 0.0)
        self.assertAlmostEqual(neutral["impliedHomeMargin"], -4.0)
        self.assertEqual(neutral["predictorFavorite"], "South Alabama")

    def test_known_game_crosscheck_accepts_aliases_and_rejects_mismatch(self):
        aliases = {
            "fiu": "FIU",
            "floridainternational": "FIU",
            "middletennessee": "Middle Tennessee",
            "missouristate": "Missouri State",
            "delaware": "Delaware",
            "southalabama": "South Alabama",
            "marshall": "Marshall",
        }
        snapshot = build_snapshot(
            three_game_schedule(),
            sagarin_text(),
            aliases,
            "2026-10-20T12:00:00Z",
            min_coverage=1.0,
        )
        reference = {
            "games": [
                {
                    "gameId": "old-fi",
                    "awayTeam": "Middle Tennessee",
                    "homeTeam": "FIU",
                    "kickoff": "2026-10-20T23:00:00Z",
                    "sagarin": {"status": "CURRENT", "impliedSpreadHome": -11.8},
                },
                {
                    "gameId": "old-de",
                    "awayTeam": "Missouri State",
                    "homeTeam": "Delaware",
                    "kickoff": "2026-10-20T23:00:00Z",
                    "sagarin": {"status": "CURRENT", "impliedSpreadHome": -6.8},
                },
                {
                    "gameId": "old-ma",
                    "awayTeam": "South Alabama",
                    "homeTeam": "Marshall",
                    "kickoff": "2026-10-20T23:30:00Z",
                    "sagarin": {"status": "CURRENT", "impliedSpreadHome": 0.2},
                },
            ]
        }
        check = verify_crosscheck(snapshot, reference, aliases)
        self.assertEqual(check["status"], "PASS")
        self.assertEqual(check["games"], 3)

        reference["games"][0]["sagarin"]["impliedSpreadHome"] = -9.0
        with self.assertRaisesRegex(ValueError, "crosscheck failed"):
            verify_crosscheck(snapshot, reference, aliases)

    def test_fails_closed_below_schedule_coverage_gate(self):
        schedule = {
            "season": 2026,
            "week": 8,
            "games": [
                three_game_schedule()["games"][0],
                {
                    "gameId": "unknown",
                    "awayTeam": "Unknown State",
                    "homeTeam": "Delaware",
                    "kickoff": "2026-10-20T23:00:00Z",
                    "neutralSite": False,
                },
            ],
        }
        with self.assertRaisesRegex(ValueError, "coverage"):
            build_snapshot(schedule, sagarin_text(), {}, "2026-10-20T12:00:00Z", min_coverage=0.90)

    def test_rejects_incomplete_source_capture(self):
        short = "\n".join(
            [
                "2026 College Football through games of October 17 Saturday - Week 7",
                "HOME ADVANTAGE=[ 3.82] [ 3.80]",
                " 1 Middle Tennessee A = 71.00 x | 6 1 | 70.00 1 |",
            ]
        )
        with self.assertRaisesRegex(ValueError, "Too few"):
            parse_ratings(short)


if __name__ == "__main__":
    unittest.main()
