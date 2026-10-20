import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))

import cfb_foundation_feature_validation as fv


class TestFoundationFeatureValidation(unittest.TestCase):
    def test_snapshot_factory_uses_locked_foundation_parameters(self):
        params={'alpha':2.5,'halfLifeDays':56,'minTeamAppearances':4}
        snapshot=fv.configured_snapshot_factory(params)
        fake_history=[object()]*80
        with patch.object(fv.engine,'fit_model',return_value={'idx':{}}) as fit, \
             patch.object(fv.rich,'metric_pair_fit',return_value={}):
            out=snapshot(fake_history,{},fv.engine.parse_dt('2026-10-01T00:00:00Z'),4.25)
        self.assertIsNotNone(out['score'])
        kwargs=fit.call_args.kwargs
        self.assertEqual(kwargs['alpha'],2.5)
        self.assertEqual(kwargs['half_life_days'],56)
        self.assertEqual(kwargs['min_team_appearances'],4)
        self.assertEqual(kwargs['fixed_hfa'],4.25)


if __name__=='__main__':
    unittest.main()
