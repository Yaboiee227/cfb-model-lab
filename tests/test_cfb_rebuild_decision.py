import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from cfb_rebuild_decision import build


class TestCfbRebuildDecision(unittest.TestCase):
    def test_names_validated_foundation_without_promoting(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            docs={
                'foundation-shadow.json': {
                    'modelId':'cfb-rebuild-foundation-v1-shadow','role':'VALIDATED_FOUNDATION_PROSPECTIVE_SHADOW',
                    'canonicalInfluence':False,'canonicalPromotionAuthorized':False,
                    'lockedParameters':{'alpha':2.5,'halfLifeDays':56,'minTeamAppearances':4},
                    'structuralHomeMarginAdvantage':4.25,
                    'games':[{'status':'FOUNDATION_SHADOW_READY'}]*3,
                },
                'foundation-validation.json': {
                    'lockedDevelopmentCandidate':{
                        'status':'FOUNDATION_CANDIDATE_READY','params':{'alpha':2.5,'halfLifeDays':56,'minTeamAppearances':4},
                        'development2024':{'aggregate':{'marginMae':12.5,'totalMae':13.2}},
                        'holdout2025':{'aggregate':{'marginMae':12.6,'totalMae':12.7}},
                        'confirmation2026PreWeek8':{'aggregate':{'marginMae':12.5,'totalMae':13.4}},
                    }
                },
                'rich.json': {'modelId':'rich','validation':{'comparisonGatePass':False}},
                'multi.json': {'walkForward2026':{'folds':[1,2,3],'aggregate':{'games':173,'richMinusSimpleMarginMae':-0.3,'richMinusSimpleTotalMae':-0.1},'evidenceStatus':'RICH_REJECTED','prospectiveShadowGatePass':False}},
                'incremental.json': {'validation':{
                    'foldCount':2,'minimumRequiredFolds':3,'games':117,'evidenceStatus':'INSUFFICIENT_FOLDS','challengerEligibleFamilies':[],
                    'families':{'efficiency':{'marginMaeDeltaVsSimple':-0.06,'totalMaeDeltaVsSimple':-0.22}}
                }},
                'ref.json': {'overall':{'games':53,'model':{'marginMae':11.3,'totalMae':12.9,'suAccuracyPct':64.2}}},
            }
            for name,data in docs.items():
                (root/name).write_text(json.dumps(data))
            out=build(root/'foundation-shadow.json',root/'foundation-validation.json',root/'rich.json',root/'multi.json',root/'incremental.json',root/'ref.json')
            self.assertEqual(out['status'],'VALIDATED_FOUNDATION_CANDIDATE_IDENTIFIED')
            self.assertEqual(out['leadRebuildCandidate'],'cfb-rebuild-foundation-v1-shadow')
            self.assertEqual(out['leadCandidateTier'],'VALIDATED_FOUNDATION_PROSPECTIVE_SHADOW')
            self.assertFalse(out['canonicalPromotionAuthorized'])
            self.assertFalse(out['week8Policy']['useLeadCandidateAsCanonical'])
            self.assertTrue(out['week8Policy']['supersedeEarlierFamilyEligibilityAgainstWeakerBase'])


if __name__=='__main__':
    unittest.main()
