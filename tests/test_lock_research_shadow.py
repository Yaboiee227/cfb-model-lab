import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from lock_research_shadow import build_lock, verify


class TestResearchShadowLock(unittest.TestCase):
    def source(self):
        return {
            'league':'cfb','season':2026,'week':8,'modelId':'m','asOf':'2026-10-20T04:00:00Z',
            'canonicalInfluence':False,'canonicalPromotionAuthorized':False,
            'lockedParameters':{'alpha':2.5},'structuralHomeMarginAdvantage':4.25,
            'source':{'marketDataUsed':False},
            'games':[{
                'gameId':'g','awayTeam':'A','homeTeam':'H','kickoff':'2026-10-20T23:00:00Z',
                'projectedAwayPoints':20.0,'projectedHomePoints':30.0,'projectedMarginHome':10.0,
                'projectedSpreadHome':-10.0,'projectedTotal':50.0,'homeWinProbability':70.0,'projectedWinner':'H',
            }]
        }

    def test_build_and_verify_before_kickoff(self):
        lock=build_lock(self.source(),datetime(2026,10,20,12,0,tzinfo=timezone.utc))
        verify(lock)
        self.assertFalse(lock['canonicalInfluence'])
        self.assertEqual(len(lock['games']),1)

    def test_refuses_post_kickoff_lock(self):
        with self.assertRaises(ValueError):
            build_lock(self.source(),datetime(2026,10,21,0,0,tzinfo=timezone.utc))

    def test_tamper_detection(self):
        lock=build_lock(self.source(),datetime(2026,10,20,12,0,tzinfo=timezone.utc))
        lock['games'][0]['projectedTotal']=55.0
        with self.assertRaises(ValueError):
            verify(lock)


if __name__=='__main__':
    unittest.main()
