import copy, unittest
from datetime import datetime, timezone
from scripts.refresh_nfl_market_reference import normalize

class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,23,12,tzinfo=timezone.utc)
        self.f={'2026_07_PIT_NO':{'kickoff_utc':'2026-10-25T13:30:00+00:00','canonical_home_margin':'-3.34'}}
        self.e={'date':'2026-10-25T13:30Z','status':{'type':{'name':'STATUS_SCHEDULED'}},'competitions':[{'competitors':[{'homeAway':'home','team':{'abbreviation':'NO'}},{'homeAway':'away','team':{'abbreviation':'PIT'}}],'odds':[{'provider':{'name':'Draft Kings'},'overUnder':44.5,'pointSpread':{'home':{'close':{'line':'+3','odds':'-102'}},'away':{'close':{'line':'-3','odds':'-118'}}},'total':{'over':{'close':{'line':'o44.5'}},'under':{'close':{'line':'u44.5'}}}}]}]}
    def test_sign_and_separation(self):
        before=copy.deepcopy(self.f); r=normalize(self.e,self.f,self.now)
        self.assertAlmostEqual(r['gapHome'],-.34);self.assertEqual(r['gapSide'],'PIT')
        self.assertFalse(r['eligibleForGrading']);self.assertFalse(r['executionVerified']);self.assertEqual(self.f,before)
    def test_finished_excluded(self):
        self.e['status']['type']['name']='STATUS_FINAL';self.assertIsNone(normalize(self.e,self.f,self.now))
    def test_mismatch_rejected(self):
        self.e['competitions'][0]['odds'][0]['pointSpread']['away']['close']['line']='-4'
        with self.assertRaises(AssertionError):normalize(self.e,self.f,self.now)
    def test_wrong_provider_missing(self):
        self.e['competitions'][0]['odds'][0]['provider']['name']='Unknown';self.assertIsNone(normalize(self.e,self.f,self.now))
