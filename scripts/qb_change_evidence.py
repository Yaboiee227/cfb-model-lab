"""Require genuine as-of starter evidence before a QB-change experiment."""
from personnel_readiness import parse

def validate(event):
    errors=[]
    freeze,kickoff=parse(event.get('forecastFrozenAt')),parse(event.get('kickoff'))
    expected,confirmed=parse(event.get('expectedObservedAt')),parse(event.get('confirmedObservedAt'))
    if not freeze or not kickoff or freeze>=kickoff:errors.append('INVALID_FORECAST_TIMELINE')
    if not event.get('expectedStarter') or not event.get('expectedSource'):errors.append('MISSING_STARTER_EXPECTATION_AT_FREEZE')
    if not expected or not freeze or expected>freeze:errors.append('EXPECTATION_NOT_VERIFIED_BY_FREEZE')
    if not event.get('confirmedStarter') or not event.get('confirmedSource'):errors.append('MISSING_CONFIRMED_STARTER')
    if not confirmed or not kickoff or confirmed>=kickoff:errors.append('CONFIRMATION_NOT_VERIFIED_BEFORE_KICKOFF')
    stats=parse(event.get('replacementStatsAsOf'))
    if not stats or not confirmed or stats>confirmed:errors.append('REPLACEMENT_PRIOR_NOT_POINT_IN_TIME_VERIFIED')
    if event.get('realizedTargetGameStarterUsed') is not False:errors.append('TARGET_GAME_STARTER_LEAKAGE_NOT_EXCLUDED')
    return dict(eligible=not errors,errors=errors,actualChange=event.get('expectedStarter')!=event.get('confirmedStarter') if not errors else None)
