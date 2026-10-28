"""Refresh current-week public game evidence without altering frozen projections."""
import json,urllib.request,concurrent.futures,datetime,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
def collect(item):
 league,g=item;sport='college-football' if league=='cfb' else 'nfl'
 url=f'https://site.api.espn.com/apis/site/v2/sports/football/{sport}/summary?event={g["eventId"]}'
 row=dict(g,league=league,sourceUrl=url,observedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
 try:
  d=json.load(urllib.request.urlopen(url,timeout=25));c=d['header']['competitions'][0]
  row.update(status=c['status']['type']['description'],completed=c['status']['type'].get('completed',False),competitors=c['competitors'],officials=d.get('gameInfo',{}).get('officials',[]),weather=d.get('gameInfo',{}).get('weather'),injuries=d.get('injuries',[]),odds=d.get('pickcenter',[]))
  row['refereeStatus']='POSTED' if row['officials'] else 'NOT_POSTED'
  row['injuryStatus']='SOURCE_LISTED_REQUIRES_OFFICIAL_AVAILABILITY_CONFIRMATION' if row['injuries'] else 'NO_REPORT_IN_SOURCE_NOT_CLEARED'
  row['marketStatus']='REFERENCE_ONLY_NOT_EXECUTION_LOCK' if row['odds'] else 'UNAVAILABLE'
  row['finalAvailabilityStatus']='FINAL_INACTIVES_OR_CONFERENCE_REPORT_NOT_VERIFIED'
 except Exception as e:row.update(error=str(e),status='SOURCE_UNAVAILABLE')
 return row
if __name__=='__main__':
 board=json.loads((ROOT/'data/current-matchups.json').read_text());items=[(l,g) for l,x in board['leagues'].items() for g in x['games']]
 with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:rows=list(ex.map(collect,items))
 out=dict(updatedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),canonicalInfluence=False,games=rows)
 (ROOT/'data/game-readiness.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({l:dict(games=len([r for r in rows if r['league']==l]),completed=sum(r.get('completed',False) for r in rows if r['league']==l),refs=sum(bool(r.get('officials')) for r in rows if r['league']==l),markets=sum(bool(r.get('odds')) for r in rows if r['league']==l),errors=sum('error' in r for r in rows if r['league']==l)) for l in board['leagues']},indent=2))
