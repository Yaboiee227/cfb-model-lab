import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from cfb_rebuild_decision import build


class TestCfbRebuildDecision(unittest.TestCase):
    def test_names_simple_lead_without_promoting(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            docs={
                'simple.json': {'modelId':'cfb-rebuild-alpha-shadow-v8h','role':'SHADOW_CHALLENGER_ONLY','canonicalInfluence':False,'source':{'marketDataUsed':False,'externalRatingsUsed':False,'postKickoffDataUsed':False},'rawTrainingGames':510,'eligibleTrainingGames':388,'fit':{'structuralHomeMarginAdvantage':4.25,'homeFieldSanityPass':True,'homeFieldProvenancePass':True},'games':[{'status':'SHADOW_READY'}]},
                'rich.json': {'modelId':'rich','validation':{'comparisonGatePass':False}},
                'wf.json': {'walkForward':{'prospectiveShadowGatePass':False,'aggregate':{'simpleMargin':{'mae':11.5},'simpleTotal':{'mae':13.3}}}},
                'multi.json': {'walkForward2026':{'folds':[1,2,3],'aggregate':{'games':173,'simpleMargin':{'mae':13.0},'richMargin':{'mae':12.7},'richMinusSimpleMarginMae':-0.3,'simpleTotal':{'mae':13.4},'richTotal':{'mae':13.3},'richMinusSimpleTotalMae':-0.1},'evidenceStatus':'RICH_REJECTED','prospectiveShadowGatePass':False}},
                'ref.json': {'overall':{'games':53,'model':{'marginMae':11.3,'totalMae':12.9,'suAccuracyPct':64.2}}},
            }
            for name,data in docs.items():
                (root/name).write_text(json.dumps(data))
            out=build(root/'simple.json',root/'rich.json',root/'wf.json',root/'multi.json',root/'ref.json')
            self.assertEqual(out['status'],'LEAD_SHADOW_IDENTIFIED')
            self.assertEqual(out['leadShadowCandidate'],'cfb-rebuild-alpha-shadow-v8h')
            self.assertFalse(out['canonicalPromotionAuthorized'])
            self.assertFalse(out['week8Policy']['useLeadShadowAsCanonical'])


if __name__=='__main__':
    unittest.main()
