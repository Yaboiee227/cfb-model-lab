import hashlib
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from cfb_operations_check import check
from validate_pregame_state import parse_dt

ROOT = Path(__file__).parents[1]

class OperationsCheckTest(unittest.TestCase):
    def test_handoff_preserves_files_and_does_not_claim_fresh_sources(self):
        files = list((ROOT / 'cfb').rglob('*.json'))
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        out = check(ROOT, parse_dt('2026-10-21T01:00:00Z'))
        self.assertEqual(out['summary']['games'], 7)
        self.assertEqual(sum(g['phase'] == 'KICKOFF_PASSED_VERIFY_FINAL' for g in out['games']), 3)
        self.assertFalse(out['sourceRefreshPerformed'])
        self.assertEqual(out['canonicalGate']['status'], 'HOLD')
        self.assertTrue(all(g['releaseBlockers'] for g in out['games']))
        self.assertNotEqual(out['auditedAt'], out['sourceObservedAt'])
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
        self.assertEqual(out, check(ROOT, parse_dt('2026-10-21T01:00:00Z')))

if __name__ == '__main__':
    unittest.main()
