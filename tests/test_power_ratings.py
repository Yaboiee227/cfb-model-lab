import sys,json,unittest
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from power_ratings.core import pair_ratings,market_ratings
class PowerRatingsTest(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,10,23,tzinfo=timezone.utc)
 def q(self,h,a,s,g='1',book='A',obs='2026-10-22T12:00:00Z'):
  return dict(home=h,away=a,homeSpread=s,gameId=g,book=book,observedAt=obs,kickoff='2026-10-24T12:00:00Z',neutral=False,source='test source')
 def test_exact_point_scale_not_average_opponent_inflation(self):
  r=np.array([7.,2.,-9.]);got,error=pair_ratings(r[:,None]-r[None,:]);np.testing.assert_allclose(got,r);self.assertLess(error,1e-12)
 def test_nontransitive_matchups_report_compression_error(self):
  m=np.array([[0,3,-3],[-3,0,3],[3,-3,0]]);r,error=pair_ratings(m);np.testing.assert_allclose(r,0);self.assertGreater(error,2)
 def test_reject_missing_and_asymmetric_matrix(self):
  for m in [[[0,1],[1,0]],[[0,float('nan')],[float('nan'),0]]]:
   with self.assertRaises(ValueError):pair_ratings(m)
 def test_disconnected_markets_are_not_national_ratings(self):
  r,m=market_ratings(['A','B','C'],[self.q('A','B',-5)],self.now,3);self.assertIsNone(r);self.assertEqual(m['components'],2)
 def test_home_spread_sign_and_neutral_hfa(self):
  qs=[self.q('A','B',-5),self.q('B','C',-4,'2')];qs[1]['neutral']=True
  r,m=market_ratings(['A','B','C'],qs,self.now,3);self.assertAlmostEqual(r[0]-r[1],2);self.assertAlmostEqual(r[1]-r[2],4);self.assertAlmostEqual(sum(r),0)
 def test_reject_future_postkickoff_missing_and_nan(self):
  qs=[self.q('A','B',-5,obs='2026-10-25T00:00:00Z'),self.q('A','B',float('nan')),self.q('A','B',-5)];del qs[2]['observedAt']
  r,m=market_ratings(['A','B'],qs,self.now,3);self.assertEqual(m['rejectedQuotes'],3);self.assertIsNone(r)
 def test_latest_book_quote_and_equal_game_weight(self):
  qs=[self.q('A','B',-5),self.q('A','B',-7,obs='2026-10-22T13:00:00Z'),self.q('A','B',-9,book='B')]
  r,m=market_ratings(['A','B'],qs,self.now,3);self.assertEqual(m['games'],1);self.assertAlmostEqual(r[0]-r[1],5)
 def test_conflicting_event_identity_rejected(self):
  qs=[self.q('A','B',-5),self.q('A','C',-5,book='B')];r,m=market_ratings(['A','B','C'],qs,self.now,3);self.assertIsNone(r);self.assertEqual(m['rejectedQuotes'],2)
 def test_complete_generated_coverage_and_zero_center(self):
  for league,n in [('cfb',138),('nfl',32)]:
   d=json.loads(Path(f'data/power-ratings/{league}.json').read_text());self.assertEqual(len(d['rows']),n);self.assertEqual(len({r['teamId'] for r in d['rows']}),n);self.assertAlmostEqual(sum(r['rating'] for r in d['rows']),0,places=8);self.assertFalse(d['canonicalInfluence']);self.assertTrue(all(r['marketRating'] is None for r in d['rows']))
 def test_nfl_freeze_reproduced_and_pair_summary_exact(self):
  d=json.loads(Path('data/power-ratings/nfl.json').read_text());self.assertLess(d['frozenReproductionMaxError'],1e-8);self.assertLess(d['pairCompressionRmse'],1e-8)
if __name__=='__main__':unittest.main()
