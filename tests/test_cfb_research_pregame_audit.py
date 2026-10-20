import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from cfb_research_pregame_audit import build_audit, preserve_audited_at_if_unchanged, priority_for
from lock_research_shadow import build_lock


class TestCfbResearchPregameAudit(unittest.TestCase):
    def _schedule(self):
        return {
            "season": 2026,
            "week": 8,
            "games": [
                {"gameId": "g1", "sourceGameId": "1", "awayTeam": "Away A", "homeTeam": "Home A", "kickoff": "2026-10-20T23:00:00Z"},
                {"gameId": "g2", "sourceGameId": "2", "awayTeam": "Away B", "homeTeam": "Home B", "kickoff": "2026-10-22T00:00:00Z"},
                {"gameId": "g3", "sourceGameId": "3", "awayTeam": "Away C", "homeTeam": "Home C", "kickoff": "2026-10-24T23:00:00Z"},
            ],
        }

    def _foundation(self):
        games = []
        for g, margin in zip(self._schedule()["games"], (7.0, -2.0, 4.0)):
            games.append({
                **g,
                "projectedAwayPoints": 24.0,
                "projectedHomePoints": 24.0 + margin,
                "projectedMarginHome": margin,
                "projectedSpreadHome": -margin,
                "projectedTotal": 48.0 + margin,
                "homeWinProbability": 60.0 if margin > 0 else 45.0,
                "projectedWinner": g["homeTeam"] if margin > 0 else g["awayTeam"],
            })
        source = {
            "league": "cfb", "season": 2026, "week": 8,
            "modelId": "foundation-test", "canonicalInfluence": False,
            "canonicalPromotionAuthorized": False, "asOf": "2026-10-20T04:00:00Z",
            "lockedParameters": {"alpha": 2.5}, "structuralHomeMarginAdvantage": 4.25,
            "source": {"marketDataUsed": False}, "games": games,
        }
        return build_lock(source, datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc))

    def _sagarin(self):
        return {
            "canonicalInfluence": False,
            "source": {"sourceId": "sagarin-cfb"},
            "games": [
                {**g, "sagarin": {"status": "CURRENT"}}
                for g in self._schedule()["games"]
            ],
        }

    def _context(self):
        return {
            "games": [
                {
                    "gameId": "different-id",
                    "sourceGameId": "1",
                    "awayTeam": "Away A",
                    "homeTeam": "Home A",
                    "kickoff": "2026-10-20T23:00:00Z",
                    "personnel": {"status": "MATERIAL_QB_STATUS_OPEN"},
                    "weather": {"status": "NWS_FINAL_RECHECK_REQUIRED"},
                    "market": {"status": "MORNING_CURRENT_NOT_LOCKED"},
                    "benchmarks": {"refMetrics": {"status": "NOT_YET_POSTED"}},
                }
            ]
        }

    def _second_context(self):
        return {
            "games": [
                {
                    "gameId": "another-id",
                    "sourceGameId": "2",
                    "awayTeam": "Away B",
                    "homeTeam": "Home B",
                    "kickoff": "2026-10-22T00:00:00Z",
                    "personnel": {"status": "OFFICIAL_BASELINE_CAPTURED"},
                    "weather": {"status": "NWS_LOW_IMPACT_BASELINE_CAPTURED"},
                    "market": {"status": "EARLY_PUBLIC_CONTEXT_NOT_LOCKED"},
                    "benchmarks": {"refMetrics": {"status": "NOT_YET_POSTED"}},
                }
            ]
        }

    def test_priority_windows(self):
        as_of = datetime(2026, 10, 20, 21, 30, tzinfo=timezone.utc)
        self.assertEqual(priority_for(datetime(2026, 10, 20, 23, 0, tzinfo=timezone.utc), as_of), "FINAL_WINDOW")
        self.assertEqual(priority_for(datetime(2026, 10, 21, 20, 0, tzinfo=timezone.utc), as_of), "TODAY")
        self.assertEqual(priority_for(datetime(2026, 10, 22, 22, 0, tzinfo=timezone.utc), as_of), "NEXT_72H")

    def test_audit_preserves_research_boundary_and_builds_queue(self):
        as_of = datetime(2026, 10, 20, 12, 30, tzinfo=timezone.utc)
        out = build_audit(self._schedule(), self._foundation(), self._sagarin(), {}, as_of, self._context(), None)
        self.assertEqual(out["role"], "FULL_WEEK_RESEARCH_PREGAME_COVERAGE_AUDIT")
        self.assertFalse(out["canonicalInfluence"])
        self.assertFalse(out["canonicalPromotionAuthorized"])
        self.assertEqual(out["summary"]["games"], 3)
        self.assertEqual(out["summary"]["foundationLocked"], 3)
        self.assertEqual(out["summary"]["sagarinCurrent"], 3)
        self.assertEqual(out["summary"]["personnelCaptured"], 1)
        self.assertEqual(out["summary"]["weatherCaptured"], 1)
        self.assertEqual(out["summary"]["gamesWithMarketLock"], 0)

        g1 = out["games"][0]
        self.assertEqual(g1["priority"], "TODAY")
        self.assertEqual(g1["urgency"], "CRITICAL")
        self.assertIn("personnel requires follow-up: MATERIAL_QB_STATUS_OPEN", g1["gaps"])
        self.assertIn("weather final review pending: NWS_FINAL_RECHECK_REQUIRED", g1["gaps"])
        self.assertIn("referee assignment status: NOT_YET_POSTED; do not guess", g1["warnings"])
        self.assertEqual(g1["marketLock"]["status"], "PENDING")

        g3 = out["games"][2]
        self.assertEqual(g3["priority"], "LATER_WEEK")
        self.assertEqual(g3["urgency"], "PLANNED")
        self.assertIn("personnel context not yet captured", g3["gaps"])
        self.assertIn("weather context not yet captured", g3["gaps"])

        self.assertEqual(out["workQueue"][0]["gameId"], "g1")

    def test_multiple_day_contexts_are_merged_without_rewriting_foundation(self):
        contexts = [("day-one.json", self._context()), ("day-two.json", self._second_context())]
        out = build_audit(
            self._schedule(), self._foundation(), self._sagarin(), {},
            datetime(2026, 10, 20, 12, 30, tzinfo=timezone.utc), contexts, None,
        )
        self.assertEqual(out["summary"]["personnelCaptured"], 2)
        self.assertEqual(out["summary"]["weatherCaptured"], 2)
        self.assertEqual(out["summary"]["refereeCapturedOrExplicitlyChecked"], 2)
        g2 = out["games"][1]
        self.assertEqual(g2["context"]["contextSource"], "day-two.json")
        self.assertEqual(g2["urgency"], "MONITOR")
        self.assertEqual(g2["gaps"], [])
        self.assertEqual(g2["foundation"]["status"], "LOCKED")

    def test_duplicate_context_across_files_fails_closed(self):
        contexts = [("a.json", self._context()), ("b.json", copy.deepcopy(self._context()))]
        with self.assertRaisesRegex(ValueError, "ambiguous pregame context across files"):
            build_audit(
                self._schedule(), self._foundation(), self._sagarin(), {},
                datetime(2026, 10, 20, 12, 30, tzinfo=timezone.utc), contexts, None,
            )

    def test_market_lock_is_reflected(self):
        foundation = self._foundation()
        market_lock = {
            "games": [
                {
                    "gameId": "x",
                    "sourceGameId": "1",
                    "awayTeam": "Away A", "homeTeam": "Home A", "kickoff": "2026-10-20T23:00:00Z",
                    "status": "LOCKED",
                    "books": {"fanduel": {"observationDigest": "x"}, "draftkings": {"observationDigest": "y"}},
                }
            ]
        }
        out = build_audit(
            self._schedule(), foundation, self._sagarin(), {},
            datetime(2026, 10, 20, 12, 30, tzinfo=timezone.utc), self._context(), market_lock,
        )
        self.assertEqual(out["summary"]["gamesWithMarketLock"], 1)
        self.assertEqual(out["games"][0]["marketLock"]["booksLocked"], ["draftkings", "fanduel"])

    def test_missing_foundation_or_sagarin_fails_closed(self):
        foundation = self._foundation()
        foundation["games"] = foundation["games"][:-1]
        with self.assertRaises(ValueError):
            build_audit(self._schedule(), foundation, self._sagarin(), {}, datetime.now(timezone.utc))

        sagarin = self._sagarin()
        sagarin["games"] = sagarin["games"][:-1]
        with self.assertRaisesRegex(ValueError, "Sagarin coverage incomplete"):
            build_audit(self._schedule(), self._foundation(), sagarin, {}, datetime.now(timezone.utc))

    def test_idempotent_timestamp_when_state_unchanged(self):
        first = build_audit(
            self._schedule(), self._foundation(), self._sagarin(), {},
            datetime(2026, 10, 20, 12, 30, tzinfo=timezone.utc), self._context(), None,
        )
        second = copy.deepcopy(first)
        second["auditedAt"] = "2026-10-20T12:35:00Z"
        out = preserve_audited_at_if_unchanged(second, first)
        self.assertEqual(out["auditedAt"], first["auditedAt"])


if __name__ == "__main__":
    unittest.main()
