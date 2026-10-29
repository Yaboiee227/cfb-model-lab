import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from personnel_readiness import assess_personnel

def test_gate():
 args=dict(kickoff='2026-10-25T17:00:00Z',observed_at='2026-10-25T16:00:00Z',report_game_id='g',game_id='g',final_availability_verified=True,qb_change=False)
 assert assess_personnel(**args)['status']=='PERSONNEL_GATE_PASS_ONLY'
 assert not assess_personnel(**args)['fullReleaseCertified']
 assert 'QB_CHANGE_NOT_REPRESENTED_IN_FORECAST' in assess_personnel(**dict(args,qb_change=True))['blockers']
 assert 'QB_STATE_UNVERIFIED' in assess_personnel(**dict(args,qb_change=None))['blockers']
 assert 'MISSING_OR_NON_PREGAME_TIMESTAMP' in assess_personnel(**dict(args,observed_at=args['kickoff']))['blockers']
 assert not assess_personnel(**dict(args,qb_change=True,adjustment_validated=True,adjustment_applied=True,observed_at=args['kickoff']))['personnelAdjusted']
 assert 'REPORT_GAME_SCOPE_MISMATCH' in assess_personnel(**dict(args,report_game_id='wrong'))['blockers']
 assert not assess_personnel(**dict(args,qb_change=True,adjustment_validated=True,adjustment_applied=True))['blockers']
if __name__=='__main__':test_gate();print('Personnel gate tests passed')
