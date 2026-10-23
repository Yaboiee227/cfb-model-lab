"""Capture current FBS membership and completed games; no historical as-of claim."""
import json,hashlib,time,gzip
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import cfb_shadow_engine as e
ROOT=Path('data/power-ratings');ROOT.mkdir(parents=True,exist_ok=True)
start=datetime.now(timezone.utc)
url=e.ESPN_FBS_TEAMS+'?groups=80&groupType=conference&enable=groups'
doc=e.fetch_json(url);teams={}
for sport in doc['sports']:
 for league in sport['leagues']:
  for group in league.get('groups',[]):
   for ent in group.get('teams',[]):
    t=ent.get('team',ent);teams[str(t['id'])]={'id':str(t['id']),'key':e.team_key(t),'name':t.get('displayName',t.get('location')),'conference':group.get('name','')}
assert 130<=len(teams)<=150,len(teams)
assert len({t['key'] for t in teams.values()})==len(teams)
def fetch(tid):
 u=f'{e.ESPN_SITE_TEAMS}/{tid}/schedule?season=2026&seasontype=2'
 for attempt in range(3):
  try:return {'teamId':tid,'source':u,'retrievedAt':e.iso(datetime.now(timezone.utc)),'payload':e.fetch_json(u)}
  except Exception:
   if attempt==2:raise
   time.sleep(1)
with ThreadPoolExecutor(max_workers=12) as pool: docs=list(pool.map(fetch,sorted(teams)))
raw={'captureStartedAt':e.iso(start),'capturedAt':e.iso(datetime.now(timezone.utc)),'membershipSource':url,'membership':doc,'schedules':docs}
path=ROOT/'cfb-source-capture.json.gz';path.write_bytes(gzip.compress((json.dumps(raw,separators=(',',':'))+'\n').encode(),mtime=0))
games={}
# Current capture only: kickoff must precede capture start, and source says final.
for d in docs:e._ingest_events(d['payload'],games,datetime(2026,8,20,tzinfo=timezone.utc),start)
out={'league':'cfb','asOf':raw['capturedAt'],'cutoff':e.iso(start),'teams':list(teams.values()),'games':[{'gameId':g.game_id,'kickoff':e.iso(g.kickoff),'home':g.home,'away':g.away,'homeScore':g.home_score,'awayScore':g.away_score,'neutral':g.neutral} for g in sorted(games.values(),key=lambda x:x.game_id)],'sourceSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'policy':'Current observed finals only; not evidence of historical pregame availability.'}
(ROOT/'cfb-model-input.json').write_text(json.dumps(out,indent=2)+'\n');print('FBS teams',len(teams),'completed games',len(games))
