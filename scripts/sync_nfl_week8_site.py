"""Publish frozen Week 8 research into the main site's existing NFL schema."""
import csv,json,pathlib,datetime
from zoneinfo import ZoneInfo
R=pathlib.Path(__file__).resolve().parents[1];S=R/'nfl_data/site';d=json.loads((R/'nfl/research-projections/week-08.json').read_text());ctx={g['eventId']:g for g in json.loads((R/'data/game-readiness.json').read_text())['games']}
archive=S/'archive/week7-before-week8';archive.mkdir(parents=True,exist_ok=True)
for name in ['config.json','projections.csv','research.json']:
 p=archive/name
 if not p.exists():p.write_bytes((S/name).read_bytes())
with (S/'projections.csv').open() as f:fields=csv.DictReader(f).fieldnames
rows=[]
for g in d['games']:
 r={k:'' for k in fields};c=ctx[g['eventId']];o=(c.get('odds') or [{}])[0];dt=datetime.datetime.fromisoformat(g['kickoffUTC'].replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York'));away,home=g['gameId'].split('_')[-2:]
 r.update(league='NFL',season=2026,week=8,date=dt.strftime('%Y-%m-%d'),kickoffET=dt.strftime('%H:%M'),gameId=g['gameId'],awayTeam=away,homeTeam=home,awayConference='NFL',homeConference='NFL',executionVerified='false',signalStrength='UNVALIDATED_RESEARCH',releaseStatus='HOLD_RESEARCH_ONLY',notes=d['limitations'],spreadReliability='PENDING_FINAL_GATES',totalReliability='PENDING_FINAL_GATES',personnelState='FINAL_AVAILABILITY_UNVERIFIED',hardQbStateBreak='false',weatherRoofState='PENDING_VERIFICATION',finalInactivesResolved='false',releaseBlockers='FINAL_PERSONNEL_PENDING|FINAL_WEATHER_ROOF_PENDING|OFFICIALS_PENDING|MARKET_LOCK_PENDING|VALIDATION_HOLD',preferredArchitecture='UNCHANGED_CANONICAL_ARCHITECTURE_RESEARCH',winProbabilityState='WITHHELD_NOT_GENERATED_FOR_WEEK8',websitePublishAllowed='true',projectionFreezeUtc=d['frozenAt'],contextObservedAt=c['observedAt'],contextSource=c['sourceUrl'],marketLockState='REFERENCE_ONLY_NOT_LOCKED')
 for k in ['projectedAwayPoints','projectedHomePoints','modelSpreadHome','modelTotal']:r[k]=g[k]
 if o.get('spread') is not None:
  r['marketSpreadHome']=(-1 if o.get('homeTeamOdds',{}).get('favorite') else 1)*abs(float(o['spread']));r['spreadGapHome']=r['marketSpreadHome']-g['modelSpreadHome']
 r.update(marketTotal=o.get('overUnder',''),marketSource='ESPN / '+o.get('provider',{}).get('name','unavailable'),marketObservedAt=c['observedAt'])
 rows.append(r)
assert len(rows)==14 and len({r['gameId'] for r in rows})==14
with (S/'projections.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
p=S/'config.json';c=json.loads(p.read_text());c.update(currentWeek=8,lastUpdated=d['frozenAt'],generatedAtUtc=d['frozenAt'],modelVersion='NFL Week 8 frozen baseline research',publicationStatus='14 Week 8 research projections published; final context and market locks pending',finalAuditArtifact='nfl/research-projections/week-08.json',winProbabilityValidation='HOLD_NOT_GENERATED_FOR_WEEK8',completedProspectiveGames=0);p.write_text(json.dumps(c,indent=2)+'\n')
r=dict(updated=d['frozenAt'],categories=[dict(id='readiness',label='Readiness',short='Readiness',status='HOLD',summary=d['limitations'],items=[dict(title='Week 8 research',detail='All 14 frozen projections published. Final personnel, weather, officials and execution locks remain unverified. Win probabilities are withheld.',tag='RESEARCH HOLD')])]);(S/'research.json').write_text(json.dumps(r,indent=2)+'\n')
print('Main NFL board: 14 Week 8 projections; old context archived')
