import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

import record_tracker as legacy
from projection_locking import lock_game
from record_tracker_v2 import validate_lock_v2


def game(game_id="g1", kickoff="2026-10-22T23:00:00Z"):
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
        "marketObservedAt": "2026-10-22T18:00:00Z",
    }


def legacy_payload():
    payload = {
        "league": "cfb",
        "season": 2026,
        "week": 8,
        "games": [game()],
        "locked": True,
        "lockedAt": "2026-10-22T20:00:00Z",
    }
    payload["lockDigest"] = legacy.canonical_digest(payload)
    return payload


def v2_payload(include_unlocked=False):
    first = game("g1", "2026-10-22T23:00:00Z")
    lock_game(first, "2026-10-22T20:00:00Z")
    games = [first]
    if include_unlocked:
        games.append(game("g2", "2026-10-23T01:00:00Z"))
    return {
        "league": "cfb",
        "season": 2026,
        "week": 8,
        "lockMode": "per-game-v2",
        "games": games,
    }


class TestRecordTrackerV2LockCompatibility(unittest.TestCase):
    def test_legacy_lock_fallback_does_not_recurse(self):
        validate_lock_v2(legacy_payload())

    def test_per_game_v2_all_locked_passes(self):
        validate_lock_v2(v2_payload())

    def test_per_game_v2_requires_every_game_locked_before_grading(self):
        with self.assertRaisesRegex(legacy.RecordError, "Unlocked projection games"):
            validate_lock_v2(v2_payload(include_unlocked=True))

    def test_per_game_v2_rejects_projection_tampering(self):
        payload = v2_payload()
        payload["games"][0]["projectedSpreadHome"] = -7.0
        with self.assertRaisesRegex(legacy.RecordError, "LOCK VIOLATION"):
            validate_lock_v2(payload)

    def test_per_game_metadata_without_lock_mode_is_still_validated(self):
        payload = v2_payload()
        payload.pop("lockMode")
        validate_lock_v2(payload)


if __name__ == "__main__":
    unittest.main()
