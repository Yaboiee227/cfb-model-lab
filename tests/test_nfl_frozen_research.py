import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from grade_nfl_frozen_research import grade

ROOT = Path(__file__).resolve().parents[1]


class FrozenResearchTests(unittest.TestCase):
    def setUp(self):
        self.freeze = json.loads((ROOT/'nfl/research-projections/week-09.json').read_text())
        self.scores = json.loads((ROOT/'nfl/postgame/20261110/week-09-scoreboard.json').read_text())

    def test_saved_forecasts_grade_without_retrospective_markets(self):
        before = copy.deepcopy(self.freeze)
        games = grade(self.freeze, self.scores)
        self.assertEqual(self.freeze, before)
        self.assertEqual(len(games), 14)
        self.assertEqual(sum(g['straightUp']['result'] == 'WIN' for g in games), 13)
        self.assertTrue(all(g['ats']['result'] == g['totals']['result'] == 'REVIEW' and g['market'] == {} for g in games))
        changed = next(g for g in games if g['gameId'] == '2026_09_LV_SF')
        self.assertNotEqual(changed['savedKickoff'], changed['finalSourceKickoff'])

    def test_partial_week_does_not_publish_complete_record(self):
        event = next(e for e in self.scores['events'] if e['shortName'] == 'BUF @ MIN')
        event['status']['type'] = {'completed': False, 'name': 'STATUS_IN_PROGRESS', 'description': 'In Progress'}
        self.assertIsNone(grade(self.freeze, self.scores))

    def test_postgame_freeze_rejected(self):
        self.freeze['frozenAt'] = '2026-11-10T23:59:00Z'
        with self.assertRaises(ValueError):
            grade(self.freeze, self.scores)
