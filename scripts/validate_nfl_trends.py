#!/usr/bin/env python3
"""Validate the static NFL trends data before GitHub Pages publication."""
from __future__ import annotations
import csv,json,re,sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
TRENDS=Path('nfl_data/site/nfl-trends.json');PROJECTIONS=Path('nfl_data/site/projections.csv');CONFIG=Path('nfl_data/site/config.json');RESULTS=Path('nfl_data/site/nfl-trend-results.json')
VALID_TYPES={'ATS','SU','TOTAL','SITUATIONAL'};VALID_POINTS={'home','away','over','under','none'};VALID_TARGETS={'spread','moneyline','total','none'};EXPECTED_TARGET={'ATS':'spread','SU':'moneyline','TOTAL':'total'}
NFL_TEAMS={'ARI','ATL','BAL','BUF','CAR','CHI','CIN','CLE','DAL','DEN','DET','GB','HOU','IND','JAX','KC','LV','LAC','LA','MIA','MIN','NE','NO','NYG','NYJ','PHI','PIT','SEA','SF','TB','TEN','WAS'}
TEAM_ALIASES={'JAC':'JAX','LAR':'LA','WSH':'WAS','OAK':'LV','SD':'LAC','SDG':'LAC'}
def valid_url(v):
 try:p=urlparse(str(v));return p.scheme in {'http','https'} and bool(p.netloc)
 except Exception:return False
def parse_iso(v):
 try:return datetime.fromisoformat(str(v).replace('Z','+00:00'))
 except Exception:return None
def load_json(p):return json.loads(p.read_text(encoding='utf-8'))
def load_rows():
 with PROJECTIONS.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def validate():
 errors=[];warnings=[]
 for p in (TRENDS,PROJECTIONS,CONFIG,RESULTS):
  if not p.exists():errors.append(f'Missing required file: {p}')
 if errors:return errors,warnings
 data=load_json(TRENDS);config=load_json(CONFIG);result_data=load_json(RESULTS);games={r['gameId']:r for r in load_rows()}
 if data.get('schemaVersion')!=1:errors.append('schemaVersion must be 1')
 if not isinstance(data.get('season'),int):errors.append('season must be an integer')
 if not isinstance(data.get('week'),int) or not 1<=data['week']<=25:errors.append('week must be an integer from 1 to 25')
 if not parse_iso(data.get('lastUpdated')):errors.append('lastUpdated must be a valid ISO-8601 timestamp')
 source=data.get('source') or {}
 if not str(source.get('name') or '').strip():errors.append('source.name is required')
 if not valid_url(source.get('url')):errors.append('source.url must be an http(s) URL')
 cfg=data.get('alignmentConfig') or {}
 for key,upper in [('spreadNeutralBand',3),('totalNeutralBand',5),('moneylineNeutralBandPct',10)]:
  val=cfg.get(key)
  if not isinstance(val,(int,float)) or not 0<=val<=upper:errors.append(f'alignmentConfig.{key} must be numeric between 0 and {upper}')
 current=config.get('currentWeek')
 if current is not None and int(data.get('week') or -1)!=int(current):warnings.append(f'Trends file is Week {data.get("week")}; site currentWeek is {current}. It will be stale/archived.')
 trends=data.get('trends');ids=set()
 if not isinstance(trends,list):errors.append('trends must be an array');trends=[]
 for i,t in enumerate(trends):
  p=f'trends[{i}]'
  if not isinstance(t,dict):errors.append(f'{p} must be an object');continue
  tid=str(t.get('id') or '').strip()
  if not tid:errors.append(f'{p}.id is required')
  elif tid in ids:errors.append(f'{p}.id duplicates {tid}')
  ids.add(tid);gid=str(t.get('gameId') or '').strip();g=games.get(gid)
  if g is None:errors.append(f'{p}.gameId {gid!r} does not match projections');continue
  try:season,week=int(t.get('season')),int(t.get('week'))
  except Exception:errors.append(f'{p}.season and week must be integers');continue
  if season!=int(g['season']) or week!=int(g['week']):errors.append(f'{p} season/week does not match game')
  if season!=data.get('season') or week!=data.get('week'):errors.append(f'{p} season/week must match file')
  m=t.get('matchup') or {};away=str(m.get('away') or '').upper();home=str(m.get('home') or '').upper()
  if away!=g['awayTeam'] or home!=g['homeTeam']:errors.append(f'{p}.matchup must be {g["awayTeam"]} at {g["homeTeam"]}')
  if away in TEAM_ALIASES or home in TEAM_ALIASES:errors.append(f'{p}.matchup uses alias; use canonical team codes')
  if away not in NFL_TEAMS or home not in NFL_TEAMS:errors.append(f'{p}.matchup contains unknown team code')
  subject=str(t.get('subject') or '').upper()
  if subject in TEAM_ALIASES:errors.append(f'{p}.subject {subject} is alias; use {TEAM_ALIASES[subject]}')
  if subject!='TOTAL' and subject not in {away,home}:errors.append(f'{p}.subject must be {away}, {home}, or TOTAL')
  typ=str(t.get('trendType') or '').upper();target=str(t.get('alignmentTarget') or '').lower();points=str(t.get('pointsTo') or '').lower()
  if typ not in VALID_TYPES:errors.append(f'{p}.trendType invalid')
  if target not in VALID_TARGETS:errors.append(f'{p}.alignmentTarget invalid')
  if points not in VALID_POINTS:errors.append(f'{p}.pointsTo invalid')
  if typ in EXPECTED_TARGET and target!=EXPECTED_TARGET[typ]:errors.append(f'{p} {typ} requires {EXPECTED_TARGET[typ]}')
  if typ=='SITUATIONAL' and target=='none' and points!='none':errors.append(f'{p} informational situational trend requires pointsTo=none')
  if target=='total' and points not in {'over','under','none'}:errors.append(f'{p} total target requires over/under/none')
  if target in {'spread','moneyline'} and points not in {'home','away','none'}:errors.append(f'{p} side target requires home/away/none')
  text=str(t.get('text') or '').strip()
  if len(text)<5 or len(text)>180:errors.append(f'{p}.text must be 5-180 chars')
  sample=t.get('sampleSize')
  if not isinstance(sample,int) or sample<1:errors.append(f'{p}.sampleSize must be positive integer')
  rec=str(t.get('record') or '').strip()
  if not rec or len(rec)>50:errors.append(f'{p}.record required and <=50 chars')
  if sample and rec and not re.search(r'\d',rec):warnings.append(f'{p}.record contains no number')
  if not str(t.get('sourceName') or '').strip():errors.append(f'{p}.sourceName required')
  if not valid_url(t.get('sourceUrl')):errors.append(f'{p}.sourceUrl invalid')
  tags=t.get('tags',[])
  if tags is not None and (not isinstance(tags,list) or any(not isinstance(x,str) or not x.strip() for x in tags)):errors.append(f'{p}.tags must be non-empty strings')
 if not isinstance(result_data.get('results'),list):errors.append('trend results must be an array')
 else:
  for i,r in enumerate(result_data['results']):
   if r.get('outcome') not in {'win','loss','push','void','pending'}:errors.append(f'results[{i}].outcome invalid')
 return errors,warnings
def main():
 errors,warnings=validate()
 for w in warnings:print('WARNING:',w)
 if errors:
  for e in errors:print('ERROR:',e,file=sys.stderr)
  raise SystemExit(1)
 print(f'NFL trends validation PASSED: {len(warnings)} warning(s).')
if __name__=='__main__':main()
