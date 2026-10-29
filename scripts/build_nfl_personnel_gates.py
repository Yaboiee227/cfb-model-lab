"""Build fail-closed personnel gates from explicit, game-scoped evidence."""
import json
from pathlib import Path
from personnel_readiness import assess_personnel
R=Path(__file__).resolve().parents[1]
def build(week=8):
 projection=json.loads((R/f'nfl/research-projections/week-{week:02d}.json').read_text())
 source=R/f'nfl_data/prospective/week{week}/personnel-evidence.json'
 evidence=json.loads(source.read_text()) if source.exists() else {'games':[]}
 by_id={g['gameId']:g for g in evidence['games']}
 if len(by_id)!=len(evidence['games']):raise ValueError('Duplicate personnel report game IDs')
 expected={g['gameId'] for g in projection['games']}
 if set(by_id)-expected:raise ValueError('Personnel evidence contains games outside the current frozen slate')
 rows=[]
 for g in projection['games']:
  e=by_id.get(g['gameId'],{});result=assess_personnel(kickoff=g['kickoffUTC'],observed_at=e.get('observedAt'),report_game_id=e.get('gameId'),game_id=g['gameId'],final_availability_verified=e.get('finalAvailabilityVerified') is True,qb_change=e.get('qbChange'),adjustment_validated=False,adjustment_applied=False)
  rows.append(dict(gameId=g['gameId'],source=e.get('sourceUrl'),observedAt=e.get('observedAt'),reportType=e.get('reportType','NO_VERIFIED_REPORT'),finalAvailabilityVerified=e.get('finalAvailabilityVerified') is True,qbChange=e.get('qbChange'),summary=e.get('summary','Current game-specific personnel evidence not supplied.'),**result))
 out=dict(league='nfl',week=week,canonicalInfluence=False,policy='Official designation report is not final inactives. QB state must be explicitly verified. No numerical adjustments are applied.',games=rows)
 path=R/f'nfl_data/site/personnel-gates.json';path.write_text(json.dumps(out,indent=2)+'\n');return out
if __name__=='__main__':print('Personnel gates built:',len(build()['games']))
