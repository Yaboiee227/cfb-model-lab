"""Reproducible paired error audit; never changes predictions or grades."""
import csv,json,math,hashlib,datetime
from pathlib import Path
from collections import defaultdict
R=Path(__file__).resolve().parents[1]
def audit(path,league):
 raw=path.read_bytes();groups=defaultdict(list);seen=set()
 for row in csv.DictReader(raw.decode().splitlines()):
  assert row['gameId'] not in seen;seen.add(row['gameId']);groups[row['week']].append(row)
 out=[]
 for week,rows in groups.items():
  for target,model,market in [('spread','modelSpreadHome','marketSpreadHome'),('total','modelTotal','marketTotal')]:
   pairs=[];missing=[]
   for r in rows:
    if not r[model] or not r[market]:missing.append(r['gameId']);continue
    away,home=float(r['awayScore']),float(r['homeScore']);actual=away-home if target=='spread' else away+home
    p,m=float(r[model]),float(r[market]);assert all(math.isfinite(v) for v in [p,m,actual])
    pairs.append(dict(gameId=r['gameId'],away=r['awayTeam'],home=r['homeTeam'],actual=actual,model=p,market=m,modelError=p-actual,marketError=m-actual,pairedAbsoluteErrorDelta=abs(p-actual)-abs(m-actual)))
   n=len(pairs)
   out.append(dict(league=league,week=int(week),target=target,games=n,excludedMissingReference=missing,modelMAE=sum(abs(r['modelError']) for r in pairs)/n,marketMAE=sum(abs(r['marketError']) for r in pairs)/n,modelBias=sum(r['modelError'] for r in pairs)/n,modelRMSE=math.sqrt(sum(r['modelError']**2 for r in pairs)/n),pairedMAEDelta=sum(r['pairedAbsoluteErrorDelta'] for r in pairs)/n,worstMisses=sorted(pairs,key=lambda r:abs(r['modelError']),reverse=True)[:5]))
 return dict(path=str(path.relative_to(R)),sha256=hashlib.sha256(raw).hexdigest(),groups=out)
if __name__=='__main__':
 out=dict(generatedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),canonicalInfluence=False,referencePolicy='Stored grading references, not verified closing prices. Mixed model periods remain separated by week. Descriptive diagnosis only; no causal or significance claim.',spreadConvention='away score minus home score; negative prediction error means model favored home too strongly',sources=[audit(R/'data/results.csv','cfb'),audit(R/'nfl_data/site/results.csv','nfl')])
 p=R/'research/model-improvement/error-audit.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2)+'\n');print('Audited',sum(len(x['groups']) for x in out['sources']),'league/week/target groups')
