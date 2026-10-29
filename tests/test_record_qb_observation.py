import sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from record_qb_observation import prepare

def test_observation_contract():
 p=dict(frozenAt='2026-10-28T12:00Z',games=[dict(gameId='2026_08_BAL_BUF',kickoffUTC='2026-11-01T18:00Z')])
 r=dict(gameId='2026_08_BAL_BUF',team='BAL',state='PRACTICE_FULL_NOT_START_CONFIRMED',player='Lamar Jackson',sourceUrl='https://www.baltimoreravens.com/news/example',sourcePublishedDate='2026-10-28',reviewed=True)
 now=datetime(2026,10,29,tzinfo=timezone.utc);o=prepare(r,p,now)
 assert o['state']=='PRACTICE_FULL_NOT_START_CONFIRMED' and not o['numericalAdjustmentApplied']
 assert o['baselineStarterAssumption']=='NOT_EXPLICITLY_RECORDED'
 for bad in [dict(r,team='KC'),dict(r,observedAt='2026-10-20'),dict(r,sourcePublishedDate='2026-12-01'),dict(r,reviewed=False)]:
  try:prepare(bad,p,now)
  except AssertionError:pass
  else:raise AssertionError('Bad evidence accepted')
 try:prepare(r,p,datetime(2026,11,2,tzinfo=timezone.utc))
 except AssertionError:pass
 else:raise AssertionError('Postgame observation accepted')
if __name__=='__main__':test_observation_contract();print('Prospective observation tests passed')
