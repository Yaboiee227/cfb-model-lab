import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from projection_locking import (
    game_digest,
    lock_game,
    lock_games_before,
    validate_game_lock,
    validate_week_locks,
)


def game(game_id, kickoff):
    return {
        "gameId": game_id,
        "sourceGameId": game_id,
        "awayTeam": "Away",
        "homeTeam": "Home",
        "kickoff": kickoff,
        "projectedSpreadHome": -3.5,
        "projectedTotal": 51.0,
        "projectedWinner": "Home",
        "marketSpreadHome": -2.5,
        "marketTotal": 52.5,
        "marketMoneylineHome": -145,
        "marketMoneylineAway": 125,
        "marketSource": "test",
        "marketObservedAt": "2026-10-20T18:00:00Z",
    }


class TestPerGameLocking(unittest.TestCase):
    def test_lock_game_and_validate(self):
        g = game("g1", "2026-10-20T23:00:00Z")
        lock_game(g, "2026-10-20T22:30:00Z")
        self.assertTrue(g["locked"])
        self.assertEqual(g["lockDigest"], game_digest(g))
        validate_game_lock(g)

    def test_locked_game_rejects_projection_mutation(self):
        g = game("g1", "2026-10-20T23:00:00Z")
        lock_game(g, "2026-10-20T22:30:00Z")
        g["projectedSpreadHome"] = -7.0
        with self.assertRaisesRegex(ValueError, "LOCK VIOLATION"):
            validate_game_lock(g)

    def test_locked_game_rejects_publication_market_mutation(self):
        g = game("g1", "2026-10-20T23:00:00Z")
        lock_game(g, "2026-10-20T22:30:00Z")
        g["marketSpreadHome"] = -4.0
        with self.assertRaisesRegex(ValueError, "LOCK VIOLATION"):
            validate_game_lock(g)

    def test_external_context_is_outside_projection_lock_scope(self):
        g = game("g1", "2026-10-20T23:00:00Z")
        lock_game(g, "2026-10-20T22:30:00Z")
        g["contextSnapshot"] = {"weather": {"status": "UPDATED"}}
        validate_game_lock(g)

    def test_early_game_locks_while_later_game_remains_open(self):
        payload = {
            "games": [
                game("early", "2026-10-20T23:00:00Z"),
                game("late", "2026-10-21T01:00:00Z"),
            ]
        }
        cutoff = datetime(2026, 10, 20, 23, 30, tzinfo=timezone.utc)
        locked = lock_games_before(payload, cutoff, "2026-10-20T22:00:00Z")
        self.assertEqual(locked, ["early"])
        self.assertTrue(payload["games"][0]["locked"])
        self.assertIsNot(payload["games"][1].get("locked"), True)
        validate_week_locks(payload, require_all=False)

    def test_grading_requires_all_games_locked_in_v2_snapshot(self):
        payload = {
            "games": [
                game("early", "2026-10-20T23:00:00Z"),
                game("late", "2026-10-21T01:00:00Z"),
            ]
        }
        lock_game(payload["games"][0], "2026-10-20T22:00:00Z")
        with self.assertRaisesRegex(ValueError, "Unlocked projection games"):
            validate_week_locks(payload, require_all=True)

    def test_cannot_lock_after_kickoff(self):
        g = game("g1", "2026-10-20T23:00:00Z")
        with self.assertRaisesRegex(ValueError, "after kickoff"):
            lock_game(g, "2026-10-20T23:00:01Z")


if __name__ == "__main__":
    unittest.main()
