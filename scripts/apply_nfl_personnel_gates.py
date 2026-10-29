"""Update personnel context only; preserve numerical forecasts and market snapshots."""
import csv,json
from pathlib import Path
from build_nfl_personnel_gates import build
R=Path(__file__).resolve().parents[1];gates={g['gameId']:g for g in build()['games']};p=R/'nfl_data/site/projections.csv'
with p.open() as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
numeric=['modelSpreadHome','modelTotal','projectedAwayPoints','projectedHomePoints','projectionFreezeUtc','marketSpreadHome','marketTotal','marketObservedAt']
before={r['gameId']:tuple(r[k] for k in numeric) for r in rows}
for r in rows:
 g=gates[r['gameId']];r['personnelState']='PERSONNEL_'+g['status'];r['hardQbStateBreak']='true' if g['qbChange'] is True else 'false' if g['qbChange'] is False else ''
 r['finalInactivesResolved']='true' if g['finalAvailabilityVerified'] else 'false'
 r['notes']=r['notes'].split(' Personnel evidence:')[0]+' Personnel evidence: '+g['summary']+' Final availability and QB state remain unverified; no personnel points applied.'
 blockers=r['releaseBlockers'].split('|')+g['blockers'];r['releaseBlockers']='|'.join(dict.fromkeys(blockers))
 assert r['releaseStatus']=='HOLD_RESEARCH_ONLY'
assert before=={r['gameId']:tuple(r[k] for k in numeric) for r in rows}
with p.open('w') as f:w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
p=R/'nfl_data/site/config.json';c=json.loads(p.read_text());c['personnelGateArtifact']='nfl_data/site/personnel-gates.json';p.write_text(json.dumps(c,indent=2)+'\n')
print('14 personnel gates integrated; all forecast, freeze and market fields unchanged')
