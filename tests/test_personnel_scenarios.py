import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from personnel_scenarios import build


def fixture(league='cfb'):
    e=dict(gameId='fixture',league=league,source='SYNTHETIC TEST ONLY',observedAt='2026-10-01T10:00:00Z')
    return dict(gameId='fixture',league=league,kickoff='2026-10-02T20:00:00Z',
        baseline=dict(homePoints=30,awayPoints=20),baselineEvidence=e,availabilityEvidence=e,
        exposureEvidence=e,valuationEvidence=dict(e,trainingCutoff='2026-09-30T00:00:00Z',methodStatus='UNVALIDATED_RESEARCH'),
        affectedSide='home',baselineQbShares={'starter':1},
        quarterbackValues={'starter':dict(low=4,estimate=5,high=6),'backup':dict(low=0,estimate=1,high=2)},
        scenarios=[dict(name='backup',qbShares={'backup':1})])

class Scenarios(unittest.TestCase):
    def run_case(self,r):return build(r,'2026-10-01T12:00:00Z')
    def test_scores_and_spread_sign_both_leagues(self):
        for league in ('nfl','cfb'):
            r=fixture(league);before=copy.deepcopy(r);o=self.run_case(r);s=o['scenarios'][0]
            self.assertEqual((s['homePoints'],s['modelSpreadHome'],s['modelTotal']),(26,-6,46))
            self.assertEqual(s['sensitivityBounds'],[-6,-2]);self.assertIsNone(s['homeWinProbability'])
            self.assertEqual(r,before);self.assertFalse(o['canonicalInfluence'])
    def test_no_double_counting_when_backup_already_embedded(self):
        r=fixture();r['baselineQbShares']={'backup':1}
        s=self.run_case(r)['scenarios'][0];self.assertEqual(s['offensivePointDelta'],0);self.assertEqual(s['sensitivityBounds'],[0,0])
    def test_partial_exposure_and_away_side(self):
        r=fixture();r['baselineQbShares']={'starter':.5,'backup':.5};r['affectedSide']='away'
        s=self.run_case(r)['scenarios'][0];self.assertEqual((s['awayPoints'],s['modelSpreadHome']),(18,-12))
    def test_missing_evidence_and_cross_league_withheld(self):
        for key in ('baselineEvidence','availabilityEvidence','exposureEvidence','valuationEvidence'):
            r=fixture();r.pop(key);self.assertEqual(self.run_case(r)['status'],'WITHHELD')
        r=fixture();r['availabilityEvidence']=dict(r['availabilityEvidence'],league='nfl');self.assertEqual(self.run_case(r)['status'],'WITHHELD')
    def test_leakage_bad_shares_and_invalid_interval(self):
        r=fixture();self.assertEqual(build(r,'2026-10-03T00:00:00Z')['status'],'WITHHELD')
        r['baselineQbShares']={'starter':.7};self.assertEqual(self.run_case(r)['status'],'WITHHELD')
        r=fixture();r['quarterbackValues']['starter']['low']=99;self.assertEqual(self.run_case(r)['status'],'WITHHELD')
    def test_probability_requires_separate_league_calibration(self):
        r=fixture();r['marginCalibration']=dict(league='nfl',source='fixture',validated=True,observedAt='2026-09-30T00:00:00Z',trainingCutoff='2026-09-30T00:00:00Z',residualStd=10)
        self.assertEqual(self.run_case(r)['status'],'WITHHELD')
        r['marginCalibration']['league']='cfb';self.assertGreater(self.run_case(r)['scenarios'][0]['homeWinProbability'],50)

if __name__=='__main__':unittest.main()

class Validation(unittest.TestCase):
    def test_paired_metrics_and_reject_leakage(self):
        from validate_personnel_challenger import evaluate
        r=dict(league='cfb',gameId='fixture',predictionSourceSha256='synthetic',resultSource='synthetic',trainingCutoff='2026-09-30T00:00:00Z',frozenAt='2026-10-01T00:00:00Z',kickoff='2026-10-02T00:00:00Z',resultObservedAt='2026-10-03T00:00:00Z',resultStatus='Final',finalHomePoints=24,finalAwayPoints=20,baseline=dict(homePoints=30,awayPoints=20),challenger=dict(homePoints=26,awayPoints=20))
        self.assertEqual(evaluate([r])['metrics']['cfb']['marginMAEChange'],-4)
        with self.assertRaises(ValueError):evaluate([r,r])
        r['trainingCutoff']='2026-10-03T00:00:00Z'
        with self.assertRaises(ValueError):evaluate([r])
