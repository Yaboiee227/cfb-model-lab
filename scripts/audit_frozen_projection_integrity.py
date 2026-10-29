"""Cross-check published rows against independent saved freeze/grade artifacts."""
import csv,json,math,datetime,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def load(p):return json.loads((R/p).read_text())
def dt(v):return datetime.datetime.fromisoformat(v.replace('Z','+00:00'))
def close(a,b):return math.isclose(float(a),float(b),abs_tol=1e-6)
issues=[];checks=[]
cfb=load('cfb/research-locks/week-08-foundation-full.json');final=load('cfb/research-results/week-08-foundation-full.json');sched=load('cfb/pregame/week-08-schedule.json')
freezes={g['gameId']:g for g in cfb['games']};grades={g['gameId']:g for g in final['games']};schedule={g['gameId']:g for g in sched['games']}
rows=[r for r in csv.DictReader((R/'data/results.csv').open()) if r['week']=='8']
for r in rows:
 gid=r['gameId'];f=freezes[gid];g=grades[gid];candidates=[x for x in schedule.values() if x['awayTeam']==f['awayTeam'] and x['homeTeam']==f['homeTeam']];assert len(candidates)==1,gid;s=candidates[0];bad=[]
 for k in ['awayTeam','homeTeam']:
  if len({r[k],f[k],g[k],s[k]})!=1:bad.append(k)
 for a,b in [('modelSpreadHome','projectedSpreadHome'),('modelTotal','projectedTotal')]:
  if not close(r[a],f[b]):bad.append(a)
 for k in ['awayScore','homeScore']:
  if not close(r[k],g['final'][k]):bad.append(k)
 if not close(f['projectedAwayPoints']-f['projectedHomePoints'],f['projectedSpreadHome']):bad.append('spread sign')
 if not close(f['projectedAwayPoints']+f['projectedHomePoints'],f['projectedTotal']):bad.append('total arithmetic')
 if dt(cfb['lockedAt'])>=dt(f['kickoff']):bad.append('freeze not before kickoff')
 if s['kickoff']!=f['kickoff']:bad.append('kickoff mismatch')
 if bad:issues.append(dict(gameId=gid,issues=bad))
 checks.append(dict(gameId=gid,league='cfb',passed=not bad,neutralSite=s['neutralSite']))
nfl=load('nfl/research-results/week-07.json');nf={g['gameId']:g for g in nfl['games']}
# Frozen spread and total reproduction was separately verified during extraction.
for r in csv.DictReader((R/'nfl_data/site/results.csv').open()):
 if r['week']!='7':continue
 g=nf[r['gameId']];bad=[]
 for k in ['awayTeam','homeTeam']:
  if r[k]!=g[k]:bad.append(k)
 for k in ['awayScore','homeScore']:
  if not close(r[k],g[k]):bad.append(k)
 if bad:issues.append(dict(gameId=r['gameId'],issues=bad))
 checks.append(dict(gameId=r['gameId'],league='nfl',passed=not bad))
out=dict(generatedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),canonicalInfluence=False,checks=checks,issues=issues,limitations=['Checks internal saved artifacts, not independently re-retrieved official scores.','CFB neutral-site labels matched to saved schedule only; venue classification not externally reverified.','Does not certify advanced feature calculations or point-in-time source availability.'])
p=R/'research/model-improvement/frozen-integrity-audit.json';p.write_text(json.dumps(out,indent=2)+'\n');print(len(checks),'games;',len(issues),'issues');print(json.dumps(issues,indent=2))
