import sys
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from analyze_nfl_week6_failure import grade
from grade_nfl_paired_snapshot import validate_lock,verify_snapshot

class Integrity(unittest.TestCase):
    def test_spread_signs_and_push(self):
        self.assertEqual(grade(4-3,2-3),'LOSS')
        self.assertEqual(grade(-4+3,-7+3),'WIN')
        self.assertEqual(grade(2,0),'PUSH')
        self.assertEqual(grade(0,10),'NO_PICK')

    def test_lock_timing(self):
        ko=datetime(2026,10,23,0,15,tzinfo=timezone.utc)
        lock=dict(observed_at=(ko-timedelta(minutes=20)).isoformat(),captured_at=(ko-timedelta(minutes=19)).isoformat(),source='test fixture',spread_home=-1,total=45)
        validate_lock(lock,ko)
        for changes in [dict(captured_at=ko.isoformat()),dict(observed_at=(ko-timedelta(hours=1)).isoformat()),dict(captured_at=(ko-timedelta(minutes=10)).isoformat())]:
            with self.assertRaises(AssertionError):validate_lock({**lock,**changes},ko)

    def test_committed_freeze(self):
        snapshots=list(Path('nfl_data/prospective/week7').glob('*/manifest.json'))
        self.assertEqual(len(snapshots),1)
        m=verify_snapshot(snapshots[0].parent)
        self.assertEqual(m['games'],14)
        self.assertFalse(m['canonical_changed'])
        self.assertFalse(m['promotion_allowed'])

if __name__=='__main__':unittest.main()
