"""Verify current Week 8 research publication without claiming final clearance."""
import csv,json,math
from pathlib import Path
from datetime import datetime
R=Path(__file__).resolve().parents[1];site=R/'nfl_data/site'
cfg=json.loads((site/'config.json').read_text());frozen=json.loads((R/'nfl/research-projections/week-08.json').read_text());by_id={g['gameId']:g for g in frozen['games']};rows=list(csv.DictReader((site/'projections.csv').open()));gates=json.loads((site/'personnel-gates.json').read_text());gate_ids={g['gameId'] for g in gates['games']}
assert len(rows)==len(by_id)==len(gate_ids)==14
assert {r['gameId'] for r in rows}==set(by_id)==gate_ids
assert cfg['currentWeek']==8 and cfg['recommendationReleaseAllowed'] is False
assert cfg['inputCoveragePass'] is False,'No complete coverage claim is supported'
assert cfg['spreadValidation']=='HOLD' and cfg['totalValidation']=='HOLD'
for r in rows:
 g=by_id[r['gameId']]
 for k in ['projectedAwayPoints','projectedHomePoints','modelSpreadHome','modelTotal']:
  assert math.isclose(float(r[k]),g[k],abs_tol=1e-9),(r['gameId'],k)
 assert r['projectionFreezeUtc']==frozen['frozenAt']
 assert datetime.fromisoformat(frozen['frozenAt'])<datetime.fromisoformat(g['kickoffUTC'].replace('Z','+00:00'))
 assert r['releaseStatus']=='HOLD_RESEARCH_ONLY' and r['executionVerified']=='false'
 assert r['homeWinProbability']==r['awayWinProbability']=='','Unvalidated Week 8 probabilities must remain withheld'
 assert r['releaseBlockers'] and r['websitePublishAllowed']=='true'
 if r['marketSpreadHome'] and r['spreadGapHome']:
  assert math.isclose(float(r['spreadGapHome']),float(r['marketSpreadHome'])-float(r['modelSpreadHome']),abs_tol=1e-8)
for g in gates['games']:
 assert g['fullReleaseCertified'] is False and g['personnelAdjusted'] is False
 if g['status']=='HOLD':assert g['blockers']
html=(R/'index.html').read_text();assert 'league-bootstrap.js' in html
assert (site/'archive/week7-before-week8/projections.csv').exists()
print('PASS: 14 frozen Week 8 research forecasts; explicit holds; no unsupported full-coverage or probability claim')
