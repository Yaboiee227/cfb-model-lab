import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from cfb_simple_foundation_validation import week_start, score_predictions


class TestSimpleFoundationValidation(unittest.TestCase):
    def test_week_start_is_monday_utc(self):
        dt=datetime(2026,10,17,20,0,tzinfo=timezone.utc)
        ws=week_start(dt)
        self.assertEqual(ws.isoformat(),'2026-10-12T00:00:00+00:00')

    def test_score_predictions(self):
        rows=[
            {'predMargin':7,'actualMargin':10,'predTotal':50,'actualTotal':48},
            {'predMargin':-2,'actualMargin':-5,'predTotal':40,'actualTotal':44},
        ]
        out=score_predictions(rows,2)
        self.assertEqual(out['games'],2)
        self.assertEqual(out['coverage'],1.0)
        self.assertEqual(out['marginMae'],3.0)
        self.assertEqual(out['totalMae'],3.0)
        self.assertEqual(out['suAccuracyPct'],100.0)


if __name__=='__main__':
    unittest.main()
