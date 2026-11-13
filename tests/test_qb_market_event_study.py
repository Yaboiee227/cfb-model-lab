import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from qb_market_event_study import measure
class Events(unittest.TestCase):
 def fixture(self):
  return dict(caseId='synthetic',league='nfl',affectedSide='away',starterExpectedBeforeNews=True,kickoff='2023-09-17T20:00:00Z',news=dict(source='synthetic',publishedAt='2023-09-12T12:00:00Z'),preNewsQuote=dict(bookmaker='fixture',source='synthetic',observedAt='2023-09-12T11:55:00Z',spreadHome=-3,total=45),postNewsQuote=dict(bookmaker='fixture',source='synthetic',observedAt='2023-09-12T12:05:00Z',spreadHome=-7,total=41),confounders=[])
 def test_sign_and_implied_total(self):
  o=measure(self.fixture());self.assertEqual(o['affectedTeamSpreadDeterioration'],4);self.assertEqual(o['affectedTeamImpliedPointsChange'],-4)
 def test_cross_book_excluded(self):
  r=self.fixture();r['postNewsQuote']['bookmaker']='other';self.assertEqual(measure(r)['status'],'EXCLUDED')
 def test_missing_news_time_excluded(self):
  r=self.fixture();r['news'].pop('publishedAt');self.assertEqual(measure(r)['status'],'EXCLUDED')
