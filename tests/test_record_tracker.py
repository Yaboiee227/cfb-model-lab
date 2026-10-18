import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/"scripts"))
from record_tracker import grade_game

def g(**kw):
 d={"gameId":"t","awayTeam":"Baltimore","homeTeam":"Pittsburgh","kickoff":"2026-10-18T17:00:00Z","projectedSpreadHome":-5,"projectedTotal":42,"projectedWinner":"Pittsburgh","marketSpreadHome":-2.5,"marketTotal":46,"marketMoneylineHome":-140,"marketMoneylineAway":120,"marketSource":"test","marketObservedAt":"2026-10-18T12:00:00Z"};d.update(kw);return d
def s(a,h,ot=False):return {"status":"FINAL","awayTeam":"Baltimore","homeTeam":"Pittsburgh","awayScore":a,"homeScore":h,"overtime":ot,"source":"mock"}
class TestGrading(unittest.TestCase):
 def test_pittsburgh_worked_example(self):
  r=grade_game(g(),s(18,22));self.assertEqual((r["ats"]["result"],r["totals"]["result"],r["straightUp"]["result"]),("WIN","WIN","WIN"))
 def test_push(self):
  r=grade_game(g(projectedSpreadHome=-5,marketSpreadHome=-3,projectedTotal=40,marketTotal=42),s(20,23));self.assertEqual(r["ats"]["result"],"PUSH")
 def test_loss(self):
  r=grade_game(g(),s(24,20));self.assertEqual(r["ats"]["result"],"LOSS");self.assertEqual(r["straightUp"]["result"],"LOSS")
 def test_no_pick(self):
  r=grade_game(g(projectedSpreadHome=-2.5,projectedTotal=46),s(18,22));self.assertEqual(r["ats"]["result"],"NO_PICK");self.assertEqual(r["totals"]["result"],"NO_PICK")
 def test_overtime_counts(self):
  r=grade_game(g(projectedTotal=47),s(27,30,True));self.assertEqual(r["totals"]["result"],"WIN");self.assertTrue(r["final"]["overtime"]);self.assertEqual(r["straightUp"]["result"],"WIN")
 def test_missing_market_never_guessed(self):
  r=grade_game(g(marketSpreadHome=None),s(18,22));self.assertEqual(r["ats"]["result"],"REVIEW")
if __name__=='__main__':unittest.main()
