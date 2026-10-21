import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from cfb_grading_scope import scoped_digests, score_request, row_digest
from grade_research_shadow import grade as shadow_grade
from cfb_market_postgame import grade as market_grade
from cfb_benchmark_postgame import grade as benchmark_grade
from record_tracker import load_aliases

ROOT = Path(__file__).parents[1]
def read(p):
    return json.loads((ROOT / p).read_text())

class GradingScopeTest(unittest.TestCase):
    def setUp(self):
        self.scope = read('cfb/pregame/week-08-active-through-thursday.json')
        self.foundation = read('cfb/research-locks/week-08-foundation-full.json')

    def test_all_three_graders_exclude_paused_games_and_preserve_lock(self):
        original = copy.deepcopy(self.foundation)
        aliases = load_aliases(ROOT)
        allowed = scoped_digests(self.scope, self.foundation)
        # Adversarial score fixture: even FINAL results for every paused game
        # cannot enter this operational pass. This fixture is never published.
        scores = [{**g, 'awayScore': 17, 'homeScore': 21, 'status': 'FINAL', 'source': 'TEST_ONLY'} for g in self.foundation['games']]
        results = [
            shadow_grade(self.foundation, scores, aliases, scope=self.scope),
            market_grade(self.foundation, read('cfb/research-market-locks/week-08-foundation-market.json'), scores, aliases, scope=self.scope),
            benchmark_grade(self.foundation, read('cfb/validation/week-08-foundation-vs-sagarin.json'), scores, aliases, scope=self.scope),
        ]
        for result in results:
            self.assertEqual(len(result['games']), 7)
            self.assertTrue(all(row_digest(g) in allowed for g in result['games']))
            self.assertFalse(result['canonicalRecordMerged'])
        request = score_request(self.foundation, allowed)
        self.assertEqual(len(request['games']), 7)
        self.assertEqual(original, self.foundation)

    def test_paused_game_cannot_be_added_to_scope(self):
        paused = next(g for g in self.foundation['games'] if g['kickoff'].startswith('2026-10-24'))
        self.scope['games'].append({**paused, 'foundationDigest': paused['projectionDigest'], 'gameDateET': '2026-10-24'})
        self.scope['includedGameCount'] += 1
        with self.assertRaisesRegex(ValueError, 'paused'):
            scoped_digests(self.scope, self.foundation)

    def test_tampered_digest_and_kickoff_rejected(self):
        for key, value in [('foundationDigest', 'fake'), ('kickoff', '2026-10-21T23:00:00Z')]:
            bad = copy.deepcopy(self.scope)
            bad['games'][0][key] = value
            with self.assertRaises(ValueError):
                scoped_digests(bad, self.foundation)

if __name__ == '__main__':
    unittest.main()
