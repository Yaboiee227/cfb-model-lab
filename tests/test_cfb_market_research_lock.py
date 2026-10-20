import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from cfb_market_research_lock import merge_market_lock, preserve_updated_at_if_unchanged, verify_existing
from lock_research_shadow import build_lock


class TestCfbMarketResearchLock(unittest.TestCase):
    def _foundation(self):
        source = {
            "league": "cfb",
            "season": 2026,
            "week": 8,
            "modelId": "foundation-test",
            "canonicalInfluence": False,
            "canonicalPromotionAuthorized": False,
            "asOf": "2026-10-20T04:00:00Z",
            "lockedParameters": {"alpha": 2.5},
            "structuralHomeMarginAdvantage": 4.25,
            "source": {"marketDataUsed": False},
            "games": [
                {
                    "gameId": "g1",
                    "sourceGameId": "espn-1",
                    "awayTeam": "Middle Tennessee",
                    "homeTeam": "FIU",
                    "kickoff": "2026-10-20T23:00:00Z",
                    "projectedAwayPoints": 17.0,
                    "projectedHomePoints": 27.0,
                    "projectedMarginHome": 10.0,
                    "projectedSpreadHome": -10.0,
                    "projectedTotal": 44.0,
                    "homeWinProbability": 72.0,
                    "projectedWinner": "FIU",
                }
            ],
        }
        return build_lock(source, datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc))

    def _markets(self, fd_updated="2026-10-20T22:40:00Z", include_dk=True):
        books = {
            "fanduel": {
                "updatedAt": fd_updated,
                "moneyline": {"home": -400, "away": 310},
                "spread": {"home": -9.5, "homePrice": -110, "away": 9.5, "awayPrice": -110},
                "total": {"point": 45.5, "overPrice": -108, "underPrice": -112},
            }
        }
        if include_dk:
            books["draftkings"] = {
                "updatedAt": "2026-10-20T22:42:00Z",
                "moneyline": {"home": -390, "away": 305},
                "spread": {"home": -10.0, "homePrice": -105, "away": 10.0, "awayPrice": -115},
                "total": {"point": 46.0, "overPrice": -110, "underPrice": -110},
            }
        return {
            "provider": "The Odds API",
            "games": [
                {
                    "id": "odds-1",
                    "commenceTime": "2026-10-20T23:00:00Z",
                    "homeTeam": "Florida International Panthers",
                    "awayTeam": "Middle Tennessee Blue Raiders",
                    "books": books,
                }
            ],
        }

    def _aliases(self):
        return {
            "fiu": "FIU",
            "floridainternational": "FIU",
            "fiupanthers": "FIU",
            "middletennessee": "Middle Tennessee",
            "middletennesseeblueraiders": "Middle Tennessee",
        }

    def test_does_not_lock_before_final_window(self):
        out = merge_market_lock(
            self._foundation(), self._markets(), None, self._aliases(),
            datetime(2026, 10, 20, 22, 20, tzinfo=timezone.utc),
        )
        self.assertEqual(out["counts"]["gamesWithMarketLock"], 0)
        self.assertEqual(out["games"][0]["status"], "PENDING")

    def test_locks_both_fresh_books_with_mascot_name_matching(self):
        foundation = self._foundation()
        out = merge_market_lock(
            foundation, self._markets(), None, self._aliases(),
            datetime(2026, 10, 20, 22, 45, tzinfo=timezone.utc),
        )
        self.assertEqual(out["role"], "IMMUTABLE_PREGAME_MARKET_RESEARCH_LOCK")
        self.assertFalse(out["canonicalInfluence"])
        self.assertFalse(out["canonicalRecordMerged"])
        self.assertEqual(out["foundationLockDigest"], foundation["lockDigest"])
        self.assertEqual(out["counts"]["gamesWithMarketLock"], 1)
        self.assertEqual(out["counts"]["bookObservationsLocked"], 2)
        row = out["games"][0]
        self.assertEqual(row["status"], "LOCKED")
        self.assertAlmostEqual(row["books"]["fanduel"]["marketSpreadHome"], -9.5)
        self.assertAlmostEqual(row["books"]["draftkings"]["marketTotal"], 46.0)
        verify_existing(out, foundation)

    def test_stale_observation_is_not_locked(self):
        out = merge_market_lock(
            self._foundation(), self._markets(fd_updated="2026-10-20T21:30:00Z", include_dk=False), None, self._aliases(),
            datetime(2026, 10, 20, 22, 45, tzinfo=timezone.utc),
            max_observation_age_minutes=35,
        )
        self.assertEqual(out["counts"]["bookObservationsLocked"], 0)
        self.assertEqual(out["games"][0]["status"], "PENDING")

    def test_existing_book_is_immutable_but_missing_book_can_be_added(self):
        foundation = self._foundation()
        first = merge_market_lock(
            foundation, self._markets(include_dk=False), None, self._aliases(),
            datetime(2026, 10, 20, 22, 45, tzinfo=timezone.utc),
        )
        old_fd = copy.deepcopy(first["games"][0]["books"]["fanduel"])

        changed = self._markets(fd_updated="2026-10-20T22:50:00Z", include_dk=True)
        changed["games"][0]["books"]["fanduel"]["spread"]["home"] = -12.0
        second = merge_market_lock(
            foundation, changed, first, self._aliases(),
            datetime(2026, 10, 20, 22, 55, tzinfo=timezone.utc),
        )
        self.assertEqual(second["games"][0]["books"]["fanduel"], old_fd)
        self.assertIn("draftkings", second["games"][0]["books"])
        self.assertEqual(second["counts"]["newBookObservationsThisRun"], 1)

    def test_never_creates_new_lock_after_kickoff(self):
        out = merge_market_lock(
            self._foundation(), self._markets(), None, self._aliases(),
            datetime(2026, 10, 20, 23, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(out["games"][0]["status"], "MISSED")
        self.assertEqual(out["counts"]["bookObservationsLocked"], 0)

    def test_unchanged_durable_state_preserves_updated_at(self):
        foundation = self._foundation()
        first = merge_market_lock(
            foundation, self._markets(), None, self._aliases(),
            datetime(2026, 10, 20, 22, 45, tzinfo=timezone.utc),
        )
        second = merge_market_lock(
            foundation, self._markets(), first, self._aliases(),
            datetime(2026, 10, 20, 22, 50, tzinfo=timezone.utc),
        )
        second = preserve_updated_at_if_unchanged(second, first)
        self.assertEqual(second["updatedAt"], first["updatedAt"])
        self.assertEqual(second["counts"]["newBookObservationsThisRun"], 0)

    def test_tampered_existing_book_digest_is_rejected(self):
        foundation = self._foundation()
        out = merge_market_lock(
            foundation, self._markets(), None, self._aliases(),
            datetime(2026, 10, 20, 22, 45, tzinfo=timezone.utc),
        )
        out["games"][0]["books"]["fanduel"]["marketSpreadHome"] = 99.0
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            verify_existing(out, foundation)


if __name__ == "__main__":
    unittest.main()
