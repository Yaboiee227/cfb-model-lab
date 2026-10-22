import copy
from datetime import timedelta
import sys
import unittest
sys.path.insert(0,'scripts')
from nfl_week7_operations import lock_from,utc,verify

class Gates(unittest.TestCase):
    def setUp(self):
        self.row={'game_id':'2026_07_NE_CHI','kickoff_utc':'2026-10-23T00:15:00Z'}
        self.now=utc('2026-10-22T23:50:00Z')
        self.book={'key':'fanduel','last_update':'2026-10-22T23:49:00Z','markets':[
            {'key':'spreads','outcomes':[{'name':'Chicago Bears','point':-3,'price':-110},{'name':'New England Patriots','point':3,'price':-110}]},
            {'key':'totals','outcomes':[{'name':'Over','point':50.5,'price':-110},{'name':'Under','point':50.5,'price':-110}]}]}
        self.event={'id':'example','home_team':'Chicago Bears','away_team':'New England Patriots','commence_time':self.row['kickoff_utc']}
    def test_valid_and_timing(self):
        self.assertIsNotNone(lock_from(self.row,self.event,self.book,self.now))
        for t in [self.now-timedelta(minutes=10),utc(self.row['kickoff_utc']),self.now+timedelta(minutes=6)]:
            self.assertIsNone(lock_from(self.row,self.event,self.book,t))
    def test_identity_and_market_integrity(self):
        e=dict(self.event,home_team='Detroit Lions');self.assertIsNone(lock_from(self.row,e,self.book,self.now))
        b=copy.deepcopy(self.book);b['markets'][1]['outcomes'][1]['point']=51;self.assertIsNone(lock_from(self.row,self.event,b,self.now))
        b=copy.deepcopy(self.book);b['markets'][0]['outcomes'][0]['price']=None;self.assertIsNone(lock_from(self.row,self.event,b,self.now))
    def test_frozen_slate(self):self.assertEqual(len(verify()),14)
