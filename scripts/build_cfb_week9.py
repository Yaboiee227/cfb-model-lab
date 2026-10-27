import sys,json,pathlib,datetime
sys.path.insert(0,'scripts')
import cfb_week8_schedule as sched
from cfb_foundation_candidate import build
start=sched.parse_dt('2026-10-27T00:00:00-04:00');end=sched.parse_dt('2026-11-03T00:00:00-05:00')
games=sched.discover_games(start,end)
p=pathlib.Path('cfb/pregame/week-09-schedule.json');p.write_text(json.dumps({'schemaVersion':2,'league':'cfb','season':2026,'week':9,'role':'WEEK_SCHEDULE_STATE','observedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'gameCount':len(games),'games':games},indent=2));print('SCHEDULE',len(games),flush=True)
d=build(p,pathlib.Path('cfb/validation/week-08-simple-foundation-validation.json'),start,sched.parse_dt('2026-08-20T00:00:00-04:00'));pathlib.Path('cfb/shadow/week-09-foundation-full.json').write_text(json.dumps(d,indent=2));print('MODEL',d['trainingGames'],[(g['awayTeam'],g['homeTeam'],g['status'],g.get('projectedSpreadHome'),g.get('projectedTotal')) for g in d['games']],flush=True)
