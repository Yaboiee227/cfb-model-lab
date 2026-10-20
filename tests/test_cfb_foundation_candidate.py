import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))

import cfb_foundation_candidate as fc
import cfb_shadow_engine as engine


class TestFoundationCandidate(unittest.TestCase):
    def test_uses_locked_validation_parameters_without_retuning(self):
        state={'season':2026,'week':8,'games':[{'gameId':'g','awayTeam':'Middle Tennessee','homeTeam':'FIU','kickoff':'2026-10-20T23:00:00Z'}]}
        validation={
            'lockedDevelopmentCandidate':{
                'status':'FOUNDATION_CANDIDATE_READY',
                'params':{'alpha':2.5,'halfLifeDays':56,'minTeamAppearances':4},
                'holdout2025':{'aggregate':{'marginMae':12.5}},
                'confirmation2026PreWeek8':{'aggregate':{'marginMae':12.4,'marginRmse':15.8,'totalMae':13.4}},
            },
            'structuralHfaResearch':{'for2026':{'value':4.25}},
        }
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);sp=root/'s.json';vp=root/'v.json'
            sp.write_text(json.dumps(state));vp.write_text(json.dumps(validation))
            fake_games=[engine.Game('x',engine.parse_dt('2026-09-01T16:00:00Z'),'floridainternational','middletennessee',30,20,False)]*30
            fake_model={'eligibleTrainingGames':30}
            with patch.object(fc.engine,'fetch_completed_games',return_value=fake_games), \
                 patch.object(fc.engine,'fit_model',return_value=fake_model) as fit, \
                 patch.object(fc.engine,'predict',return_value={'projectedAwayPoints':20.0,'projectedHomePoints':30.0,'projectedMarginHome':10.0,'projectedSpreadHome':-10.0,'projectedTotal':50.0}):
                out=fc.build(sp,vp,engine.parse_dt('2026-10-20T04:00:00Z'),engine.parse_dt('2026-08-20T04:00:00Z'))
            self.assertEqual(out['lockedParameters']['alpha'],2.5)
            self.assertEqual(out['lockedParameters']['halfLifeDays'],56)
            self.assertFalse(out['canonicalInfluence'])
            self.assertFalse(out['canonicalPromotionAuthorized'])
            self.assertEqual(out['games'][0]['status'],'FOUNDATION_SHADOW_READY')
            kwargs=fit.call_args.kwargs
            self.assertEqual(kwargs['alpha'],2.5)
            self.assertEqual(kwargs['half_life_days'],56)
            self.assertEqual(kwargs['min_team_appearances'],4)
            self.assertEqual(kwargs['fixed_hfa'],4.25)


if __name__=='__main__':
    unittest.main()
