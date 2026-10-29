import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from qb_change_evidence import validate

def test_timing():
 e=dict(forecastFrozenAt='2026-10-21T12:00Z',kickoff='2026-10-25T17:00Z',expectedObservedAt='2026-10-21T11:00Z',confirmedObservedAt='2026-10-25T16:00Z',expectedStarter='A',confirmedStarter='B',expectedSource='official archived report',confirmedSource='official archived report',replacementStatsAsOf='2026-10-20T00:00Z',realizedTargetGameStarterUsed=False)
 assert validate(e)['eligible'] and validate(e)['actualChange']
 assert not validate(dict(e,expectedObservedAt='2026-10-22T00:00Z'))['eligible']
 assert not validate(dict(e,confirmedObservedAt=e['kickoff']))['eligible']
 assert not validate(dict(e,replacementStatsAsOf=e['kickoff']))['eligible']
 assert not validate(dict(e,expectedStarter=None))['eligible']
 assert not validate(dict(e,realizedTargetGameStarterUsed=True))['eligible']
if __name__=='__main__':test_timing();print('QB evidence timeline tests passed')
