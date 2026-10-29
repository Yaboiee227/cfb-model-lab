"""Explicit personnel-evidence gate; never invents a numerical adjustment."""
from datetime import datetime

def parse(value):
    try:
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return d if d.tzinfo else None
    except (ValueError,TypeError):return None

def assess_personnel(*,kickoff,observed_at,report_game_id,game_id,final_availability_verified,qb_change,adjustment_validated=False,adjustment_applied=False):
    ko,obs=parse(kickoff),parse(observed_at);blockers=[]
    if ko is None or obs is None or obs>=ko:blockers.append('MISSING_OR_NON_PREGAME_TIMESTAMP')
    if report_game_id!=game_id:blockers.append('REPORT_GAME_SCOPE_MISMATCH')
    if final_availability_verified is not True:blockers.append('FINAL_AVAILABILITY_UNVERIFIED')
    if qb_change is None:blockers.append('QB_STATE_UNVERIFIED')
    if qb_change is True and not (adjustment_validated is True and adjustment_applied is True):blockers.append('QB_CHANGE_NOT_REPRESENTED_IN_FORECAST')
    return dict(status='HOLD' if blockers else 'PERSONNEL_GATE_PASS_ONLY',blockers=blockers,personnelAdjusted=not blockers and qb_change is True and adjustment_validated is True and adjustment_applied is True,baselineResearchDisplayAllowed=True,fullReleaseCertified=False)
