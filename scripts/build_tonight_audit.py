"""Publish reviewed October 29 context separately from frozen model outputs."""
import json,csv,datetime,html,re
from pathlib import Path
R=Path(__file__).resolve().parents[1];now=datetime.datetime.now(datetime.timezone.utc).isoformat();e=lambda x:html.escape(str(x));folder=R/'research/operations/2026-10-29';weather=json.loads((folder/'nws-weather.json').read_text());slate=json.loads((R/'data/current-matchups.json').read_text());games=[]
feeds={}
for feed_path in (R/'data/live-scoreboard.json',R/'nfl_data/site/live-scoreboard.json'):
 feed=json.loads(feed_path.read_text())
 for event in feed.get('events',[]):
  feeds[str(event.get('id'))]=(feed,event)
refs={'CAR_GB':'Scott Novak','ARI_DAL':'Ron Torbert','ATL_TB':'Alan Eck','BAL_BUF':'Clay Martin','CLE_PIT':'Alex Kemp','IND_JAX':'Adrian Hill','LV_NYJ':'John Hussey','MIN_DET':'Craig Wrolstad','TEN_CIN':'Brad Allen','LAC_LA':'Brad Rogers','KC_DEN':'Clete Blakeman','NE_MIA':'Shawn Hochuli','PHI_WAS':'Alex Moore','CHI_SEA':'Shawn Smith'}
assignments=[dict(gameId='2026_08_'+key,reportedReferee=name,source='https://www.footballzebras.com/2026/10/week-8-referee-assignments-2026/',observedAt='2026-10-29T17:46:00.829452+00:00',status='REPORTED_ASSIGNMENT_SUBSTITUTIONS_POSSIBLE',canonicalInfluence=False) for key,name in refs.items()]
crew=[dict(role=k,name=v) for k,v in [('Referee','Scott Novak'),('Umpire','Mike Morton'),('Down Judge','Brian Sakowski'),('Line Judge','Mark Stewart'),('Back Judge','Tony Josselyn'),('Field Judge','John Jenkins'),('Side Judge','Don Willard')]]
for league,b in slate['leagues'].items():
 for g in b['games']:
  if g['dateET']!='2026-10-29':continue
  r=dict(g,league=league,checkedAt=now,canonicalInfluence=False,releaseStatus='RESEARCH_ONLY_FINAL_GATES_PENDING',executionVerified=False)
  if g['eventId']=='401873023':
   key='GB';r.update(personnelStatus='OFFICIAL_PANTHERS_INACTIVES_VERIFIED_PACKERS_LIST_PARTIAL',personnelSummary='Panthers.com published Carolina inactives at 6:48 p.m. EDT: Ja\'Tavion Sanders, Jaelan Phillips, emergency QB Haynes King, AJ Dillon, Damien Lewis, Torricelli Simpkins III, and Bobby Brown III. The same report lists six Packers inactives (Jonnu Smith, Kaleb Johnson, Zaire Franklin, Donovan Jennings, Sean Rhyan, Travis Glover); complete Packers list not independently verified. Packers.com separately added CB Keisean Nixon (shoulder) as questionable at 12:50 p.m. EDT; his final status is not verified here. No forecast adjustment applied.',personnelSources=['https://www.panthers.com/news/week-8-inactives-at-green-bay-panthers-down-three-starters-for-packers','https://www.packers.com/news/packers-announce-injury-update-oct-29-2026'],confirmedInactives={'CAR':['Ja\'Tavion Sanders','Jaelan Phillips','Haynes King (emergency third QB)','AJ Dillon','Damien Lewis','Torricelli Simpkins III','Bobby Brown III'],'GB':['Jonnu Smith','Kaleb Johnson','Zaire Franklin','Donovan Jennings','Sean Rhyan','Travis Glover']},reportedCrew=crew,crewSources=['https://www.footballzebras.com/2026/10/week-8-referee-assignments-2026/','https://www.refmetrics.com/nfl/official-assignments-today'],crewStatus='REPORTED_CREW_SUBSTITUTIONS_POSSIBLE')
  elif g['eventId']=='401869963':
   key='JMU';r.update(personnelStatus='SECONDARY_GAME_DAY_REPORT_OFFICIAL_VERIFICATION_PENDING',personnelSummary='Tracker reports Troy six out and JMU five out, including Tanner Vibabul; Goose Crowder and TK Keyes listed available. Source versions differ; official conference report not independently retrieved. Available does not establish starter identity.',personnelSources=['https://kickoffstatus.com/games/2026-10-29-troy-at-james-madison/','https://sunbeltsports.org/news/2025/8/11/football-availability-report-new.aspx'],reportedCrew=[],crewStatus='NOT_VERIFIED',marketSpreadHome=-19.0,marketTotal=49.5,marketSource='https://www.actionnetwork.com/ncaaf-game/troy-trojans-james-madison-dukes/289710')
  else:
   key='UNT';r.update(personnelStatus='CURRENT_CONFERENCE_REPORT_NOT_VERIFIED',personnelSummary='Tracker lists conference report pending. Prior-week and unofficial injury lists are not treated as current clearance.',personnelSources=['https://kickoffstatus.com/teams/north-texas/'],reportedCrew=[],crewStatus='NOT_VERIFIED',marketSpreadHome=-14.0,marketTotal=76.5,marketSource='https://www.actionnetwork.com/ncaaf-game/florida-atlantic-north-texas-score-odds-october-29-2026/289709')
  feed,event=feeds[g['eventId']];odds=(event.get('competitions') or [{}])[0].get('odds') or []
  if not odds or odds[0].get('spread') is None or odds[0].get('overUnder') is None:
   raise SystemExit(f'Current ESPN spread/total unavailable for {g["eventId"]}; refusing to timestamp stale prices')
  r.update(marketSpreadHome=float(odds[0]['spread']),marketTotal=float(odds[0]['overUnder']),marketSource=g['source'],marketReferenceSource='ESPN DraftKings public scoreboard reference',marketObservedAt=feed['refreshedAt'],marketRole='CURRENT_REFERENCE_NOT_EXECUTION_LOCK')
  w=weather[key];ko=datetime.datetime.fromisoformat(g['kickoffUTC'].replace('Z','+00:00'));end=ko+datetime.timedelta(hours=4);ps=w.get('periods',[])
  contiguous=bool(ps) and datetime.datetime.fromisoformat(ps[0]['startTime'])<=ko and datetime.datetime.fromisoformat(ps[-1]['endTime'])>=end and all(a['endTime']==b['startTime'] for a,b in zip(ps,ps[1:]))
  issued=w.get('forecastIssuedAt');valid=bool(issued) and datetime.datetime.fromisoformat(issued.replace('Z','+00:00'))<=datetime.datetime.fromisoformat(w['observedAt'])
  observed=datetime.datetime.fromisoformat(w['observedAt'].replace('Z','+00:00'))
  final_window_refreshed=(ko-datetime.timedelta(minutes=30)<=observed<=ko)
  r['weather']=dict(w,kickoffThroughPlus4HoursCovered=contiguous,forecastIssueTimeValid=valid,finalWindowRefreshRequired=not final_window_refreshed,gusts='NOT_SUPPLIED_BY_HOURLY_ENDPOINT');r['nextCheckWindows']={'ninetyMinutesBeforeKickoff':(ko-datetime.timedelta(minutes=90)).isoformat(),'marketLockWindowStart':(ko-datetime.timedelta(minutes=30)).isoformat()}
  path=R/('nfl_data/site/projections.csv' if league=='nfl' else 'data/projections.csv');rows=list(csv.DictReader(path.open()));match=[x for x in rows if x['date']=='2026-10-29' and (x['homeTeam']=='GB' if league=='nfl' else x['homeTeam'] in ('James Madison',) if key=='JMU' else x['homeTeam']=='North Texas')];assert len(match)==1,(key,len(match));f=match[0]
  r['projection']=dict(gameId=f['gameId'],awayPoints=float(f['projectedAwayPoints']),homePoints=float(f['projectedHomePoints']),spreadHome=float(f['modelSpreadHome']),total=float(f['modelTotal']));r['modelMarketGapHome']=r['marketSpreadHome']-r['projection']['spreadHome'];games.append(r)
assert len(games)==3
out=dict(checkedAt=now,canonicalInfluence=False,numericalForecastChanges=0,games=games,nflReportedAssignments=assignments,limitations=['Sources are context and secondary market references, not execution locks.','Referee assignments may change. No numerical officiating adjustments.','Recheck weather if kickoff is delayed.','No complete injury/availability clearance claimed.'])
(R/'data/tonight-readiness.json').write_text(json.dumps(out,indent=2)+'\n')
s='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Tonight’s readiness · CB Model Projections</title><link rel="stylesheet" href="audit-shell.css"><main class="shell"><nav><a href="index.html">CFB board</a> · <a href="index.html?league=nfl">NFL board</a> · <a href="readiness.html">Full slate</a></nav><h1>Thursday, October 29</h1><p>Frozen research forecasts with current context. Final gates remain pending; no numerical forecast adjustments applied.</p>'''
s+=f'<p>Checked {e(now)} · <a href="data/tonight-readiness.json">Evidence and timestamps</a></p>'
for g in games:
 w=g['weather'];ps=w.get('periods',[]);temps=[p['temperature'] for p in ps];winds=[int(n) for p in ps for n in re.findall(r'\d+',p['windSpeed'])];rain=[p['probabilityOfPrecipitation']['value'] for p in ps if p['probabilityOfPrecipitation']['value'] is not None];p=g['projection']
 s+=f'<section><h2>{e(g["away"])} at {e(g["home"])}</h2><p>{e(g["kickoffET"])} · {e(g["venue"])}</p><p><strong>Model score {p["awayPoints"]:.1f}–{p["homePoints"]:.1f}</strong> · Home spread {p["spreadHome"]:+.2f} · Total {p["total"]:.2f}</p><p>Current reference home spread {g["marketSpreadHome"]:+.1f} · Total {g["marketTotal"]:.1f} · Home model/market gap {g["modelMarketGapHome"]:+.2f}. {e(g["marketReferenceSource"])} observed {e(g["marketObservedAt"])}. <a href="{e(g["marketSource"])}">Scoreboard source</a>; reference only, not a locked price.</p><p><strong>Availability:</strong> {e(g["personnelSummary"])}</p>'
 for url in g['personnelSources']:s+=f'<p><a href="{e(url)}">Availability source</a></p>'
 if temps:
  refresh_note=f'Final-window refresh completed {e(w["observedAt"])}.' if not w['finalWindowRefreshRequired'] else 'Final-window refresh still required.'
  s+=f'<p><strong>NWS forecast:</strong> {min(temps)}–{max(temps)}°F; wind up to {max(winds)} mph; hourly precipitation probability up to {max(rain) if rain else "unavailable"}%. Kickoff through +4h coverage: {w["kickoffThroughPlus4HoursCovered"]}. <a href="{e(w["sourceUrl"])}">Forecast</a>. {refresh_note}</p>'
 if g.get('confirmedInactives'):
  for team,names in g['confirmedInactives'].items():s+=f'<p><strong>{e(team)} reported inactives:</strong> {e(", ".join(names))}</p>'
 if g['reportedCrew']:
  s+='<p><strong>Reported crew:</strong> '+e('; '.join(c['role']+': '+c['name'] for c in g['reportedCrew']))+'. Substitutions possible.</p>'
 else:s+='<p>CFB officiating crew not verified.</p>'
 s+='<p><strong>HOLD:</strong> final availability/QB verification and execution locks remain pending.</p></section>'
s+='</main></html>';(R/'tonight.html').write_text(s)
for name in ['index.html','current-matchups.html','readiness.html']:
 p=R/name;s=p.read_text()
 if 'tonight.html' not in s:s=s.replace('<body>','<body><p style="padding:12px"><a href="tonight.html">Tonight: current projections, availability, weather and reported officials →</a></p>',1)
 p.write_text(s)
print('3 games audited; NWS coverage:',[(g['eventId'],g['weather']['kickoffThroughPlus4HoursCovered'],g['weather']['forecastIssueTimeValid']) for g in games])
