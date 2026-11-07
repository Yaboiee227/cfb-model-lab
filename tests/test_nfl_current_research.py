import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from publish_nfl_current_research import PIN, rows_for


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.doc = {"season": 2026, "week": 9, "frozenAt": "2026-11-07T00:29:37Z", "sourceCommit": PIN,
            "canonicalInfluence": False, "priorWeekReproduction": {"games": 14, "spreadMaxAbsDiff": 0., "totalMaxAbsDiff": 0.},
            "inputs": {"maxSourceWeek": 8}, "limitations": "Unchanged research baseline, context unresolved.",
            "games": [{"gameId": "2026_09_A_H", "home": "H", "away": "A", "kickoffUTC": "2026-11-08T18:00:00Z",
                       "modelSpreadHome": -4., "modelTotal": 44., "projectedHomePoints": 24., "projectedAwayPoints": 20.}]}
        import csv
        self.fields = next(csv.reader((Path(__file__).resolve().parents[1] / "nfl_data/site/projections.csv").open()))

    def test_publication_does_not_invent_context_or_markets(self):
        rows, gates = rows_for(self.doc, self.fields)
        row = rows[0]
        for key in ["hardQbStateBreak", "marketSpreadHome", "marketTotal", "homeWinProbability", "contextObservedAt"]:
            self.assertEqual(row[key], "")
        self.assertEqual(row["projectionFreezeUtc"], self.doc["frozenAt"])
        self.assertEqual(row["releaseStatus"], "HOLD_RESEARCH_ONLY")
        self.assertFalse(gates[0]["fullReleaseCertified"])

    def test_failed_parity_cutoff_or_arithmetic_blocks_publication(self):
        for field in ["parity", "cutoff", "score", "freeze"]:
            doc = copy.deepcopy(self.doc)
            if field == "parity": doc["priorWeekReproduction"]["spreadMaxAbsDiff"] = .1
            if field == "cutoff": doc["inputs"]["maxSourceWeek"] = 9
            if field == "score": doc["games"][0]["projectedHomePoints"] = 25
            if field == "freeze": doc["frozenAt"] = doc["games"][0]["kickoffUTC"]
            with self.subTest(field=field), self.assertRaises(ValueError):
                rows_for(doc, self.fields)


if __name__ == "__main__":
    unittest.main()
