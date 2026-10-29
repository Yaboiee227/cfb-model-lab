"""Apply reviewed context/market references while preserving frozen numeric forecasts."""
import csv,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];d=json.loads((R/'data/tonight-readiness.json').read_text());by_id={g['projection']['gameId']:g for g in d['games']};refs={g['gameId']:g for g in d['nflReportedAssignments']};archive=R/'research/operations/2026-10-29'
for league,path in [('cfb',R/'data/projections.csv'),('nfl',R/'nfl_data/site/projections.csv')]:
 before=path.read_bytes();saved=archive/f'{league}-before-context.csv'
 if not saved.exists():saved.write_bytes(before)
 with path.open() as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
 protected=['gameId','projectedAwayPoints','projectedHomePoints','modelSpreadHome','modelTotal']
 frozen={r['gameId']:tuple(r[k] for k in protected) for r in rows}
 for r in rows:
  g=by_id.get(r['gameId'])
  if r['gameId'] in refs:
   ref=refs[r['gameId']];r['notes']=r['notes'].split(' Reported Week 8 referee:')[0]+' Reported Week 8 referee: '+ref['reportedReferee']+' (Football Zebras; substitutions possible; no numerical effect).'
  if g:
   r.update(marketSpreadHome=g['marketSpreadHome'],marketTotal=g['marketTotal'],marketSource='Action Network secondary reference; not a direct-book lock',marketObservedAt=g['marketObservedAt'],executionVerified='false')
   if 'spreadGapHome' in fields:r['spreadGapHome']=g['modelMarketGapHome']
   r['notes']=r['notes'].split(' Tonight audit:')[0]+' Tonight audit: '+g['personnelSummary']+' NWS kickoff/+4h forecast captured; final-window refresh required. Full evidence: tonight.html. No numerical adjustment.'
   if 'weatherRoofState' in fields:r['weatherRoofState']='NWS_FORECAST_CAPTURED_FINAL_WINDOW_REFRESH_PENDING'
 assert frozen=={r['gameId']:tuple(r[k] for k in protected) for r in rows}
 with path.open('w') as f:w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
for path in [R/'data/config.json',R/'nfl_data/site/config.json']:
 c=json.loads(path.read_text());c['currentContextAudit']='data/tonight-readiness.json';c['contextLastUpdated']=d['checkedAt'];path.write_text(json.dumps(c,indent=2)+'\n')
print('Context and reference lines applied; all frozen numeric projections preserved')
