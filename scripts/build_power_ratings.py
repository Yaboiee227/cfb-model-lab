"""Build reproducible independent league ratings from captured model inputs."""
import csv,json,hashlib,gzip
from pathlib import Path
from datetime import datetime,timezone,timedelta
import numpy as np
import cfb_shadow_engine as e
from power_ratings.core import pair_ratings,market_ratings
ROOT=Path('data/power-ratings')
def read(p):
 p=Path(p);return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build():
 now=datetime.now(timezone.utc); outputs={}
 c=read(ROOT/'cfb-model-input.json');v=read('cfb/validation/week-08-simple-foundation-validation.json')
 assert sha(ROOT/'cfb-source-capture.json.gz')==c['sourceSha256']
 params=v['lockedDevelopmentCandidate']['params'];hfa=v['structuralHfaResearch']['for2026']['value']
 games=[e.Game(g['gameId'],e.parse_dt(g['kickoff']),g['home'],g['away'],g['homeScore'],g['awayScore'],g['neutral']) for g in c['games']]
 assert len({g.game_id for g in games})==len(games)
 assert all(g.kickoff<e.parse_dt(c['cutoff']) for g in games)
 model=e.fit_model(games,e.parse_dt(c['cutoff']),params['alpha'],params['halfLifeDays'],params['minTeamAppearances'],hfa)
 teams=sorted(c['teams'],key=lambda t:t['key']);keys=[t['key'] for t in teams]
 missing=[t for t in keys if t not in model['idx']]
 if missing:raise ValueError('Unsupported FBS teams; do not invent ratings: '+str(missing))
 strength=np.array([model['strength'][model['idx'][t]] for t in keys]);strength-=strength.mean()
 counts=e.appearance_counts(e.filter_core_games(games,params['minTeamAppearances']))
 # Reranking starts a new dated snapshot; never overwrites frozen Week 8 projections.
 rows=[dict(teamId=t['id'],team=t['name'],key=t['key'],conference=t['conference'],rating=float(r),games=counts[t['key']]) for t,r in zip(teams,strength)]
 n=read(ROOT/'nfl-model-input.json');nr,residual=pair_ratings(n['margins'])
 outputs['cfb']={'modelId':'cfb-rebuild-foundation-v1-shadow','modelAsOf':c['asOf'],'status':'RESEARCH_SHADOW','rows':rows,'hfa':hfa,'parameters':params,'trainingGames':len(games),'eligibleTrainingGames':model['eligibleTrainingGames'],'validation':v['lockedDevelopmentCandidate'].get('holdout2025'),'inputHashes':{'cfb-model-input.json':sha(ROOT/'cfb-model-input.json'),'validation':sha('cfb/validation/week-08-simple-foundation-validation.json')},'method':'Existing opponent-adjusted ridge strengths, centered over all FBS teams; no retuning.'}
 outputs['nfl']={'modelId':n['modelId'],'modelAsOf':n['asOf'],'status':'CANONICAL_DERIVED_RESEARCH','sourceWeek':6,'rows':[dict(teamId=t,team=t,key=t,conference='NFL',rating=float(r),games=n['gamesBefore'][t]) for t,r in zip(n['teams'],nr)],'hfa':None,'pairCompressionRmse':residual,'frozenReproductionMaxError':n['frozenReproductionMaxError'],'inputHashes':{'nfl-model-input.json':sha(ROOT/'nfl-model-input.json')},'method':n['method']}
 quotes={'cfb':[],'nfl':[]}; gaps={'cfb':{},'nfl':{}}
 # Match only exact vetted identities; never substring/mascot guessing.
 names={e.norm(t['name']):t['key'] for t in teams};names.update({e.norm(t['key']):t['key'] for t in teams})
 names[e.norm('Southern Mississippi Golden Eagles')]='southernmiss' # ESPN ID 2572; sportsbook long name
 aliases=read('data/team-aliases.json')
 for canonical,vals in aliases.items():
  matched={names[e.norm(s)] for s in [canonical]+vals if e.norm(s) in names}
  if len(matched)==1:
   for s in [canonical]+vals:names[e.norm(s)]=next(iter(matched))
 raw=read(ROOT/'cfb-source-capture.json.gz');fixtures={}
 for d in raw['schedules']:
  for event in d['payload'].get('events',[]):
   comp=event['competitions'][0];sides={z['homeAway']:e.team_key(z['team']) for z in comp['competitors']}
   fixtures[(sides.get('home'),sides.get('away'))]={'kickoff':comp.get('date') or event['date'],'neutral':comp.get('neutralSite',False)}
 markets=read('data/markets-sportsbooks.json');unmatched=[]
 for g in markets.get('games',[]):
  if e.parse_dt(g['commenceTime'])<=now:continue
  h=names.get(e.norm(g['homeTeam']));a=names.get(e.norm(g['awayTeam']));fixture=fixtures.get((h,a))
  if not fixture or e.parse_dt(fixture['kickoff'])!=e.parse_dt(g['commenceTime']):unmatched.append(g['id']);continue
  for book,b in g['books'].items():
   if b.get('spread',{}).get('home') is None or not np.isfinite(float(b['spread']['home'])):continue
   quotes['cfb'].append(dict(gameId=g['id'],home=h,away=a,kickoff=g['commenceTime'],neutral=fixture['neutral'],homeSpread=b['spread']['home'],book=book,observedAt=b['updatedAt'],source='data/markets-sportsbooks.json'))
 # NFL published projection and market reference are kept distinct from ratings.
 ref=read('nfl_data/site/market-reference.json');frozen=read('nfl_data/prospective/week7/20261021T114427Z/context_market_gates.json');neutral={g['game_id']:g['neutral_site'] for g in frozen}
 for g in ref['games']:
  if e.parse_dt(g['kickoffUtc'])<=now or not e.parse_dt(g['marketObservedAt'])<=now:continue
  if not np.isfinite(float(g['marketSpreadHome'])) or not np.isfinite(float(g['gapHome'])):continue
  quotes['nfl'].append(dict(gameId=g['gameId'],home=g['home'],away=g['away'],kickoff=g['kickoffUtc'],neutral=neutral[g['gameId']],homeSpread=g['marketSpreadHome'],book=ref['provider'],observedAt=g['marketObservedAt'],source=ref['source']))
  for t,sign in [(g['home'],1),(g['away'],-1)]:gaps['nfl'][t]=dict(opponent=g['away'] if sign==1 else g['home'],gap=sign*g['gapHome'],observedAt=g['marketObservedAt'],source=ref['source'],basis='Frozen game projection versus current market reference')
 lookup=dict(zip(keys,strength));grouped={}
 for q in quotes['cfb']:
  if e.parse_dt(q['observedAt'])<=now and e.parse_dt(q['observedAt'])<e.parse_dt(q['kickoff']):grouped.setdefault(q['gameId'],[]).append(q)
 for qs in grouped.values():
  q=qs[0];h,a=q['home'],q['away'];gap=float(np.median([z['homeSpread'] for z in qs]))+lookup[h]-lookup[a]+(0 if q['neutral'] else hfa)
  for t,sign in [(h,1),(a,-1)]:gaps['cfb'][t]=dict(opponent=a if sign==1 else h,gap=sign*gap,observedAt=max(z['observedAt'] for z in qs),source='The Odds API / FanDuel and DraftKings',basis='Current research rating difference + frozen structural HFA versus median quote')
 for league,out in outputs.items():
  keys=[r['key'] for r in out['rows']]
  # NFL HFA assumption is benchmark-only and explicitly not its fitted game HFA.
  mhfa=out['hfa'] if league=='cfb' else 3.0
  history=[]
  for archived in sorted((ROOT/'snapshots').glob('*/'+league+'.json')):
   history.extend(read(archived).get('market',{}).get('normalizedQuotes',[]))
  unique={}
  for q in history+quotes[league]:
   if now-timedelta(days=42)<=e.parse_dt(q['observedAt'])<=now:
    unique[(q['gameId'],q['book'],q['observedAt'])]=q
  market_quotes=list(unique.values())
  market,meta=market_ratings(keys,market_quotes,now,mhfa)
  meta['lookbackDays']=42
  meta['lookbackStatus']='BENCHMARK_DESIGN_NOT_PREDICTIVELY_VALIDATED'
  out.update(schemaVersion=1,league=league,generatedAt=e.iso(now),canonicalInfluence=False,market=meta,marketAsOf=max((q['observedAt'] for q in quotes[league]),default=None),coverage=len(keys),ratingUnit='points above league-average team on neutral field',uncertainty='Rank intervals not calibrated; no probability or betting-confidence claim.',rankChange=None)
  out['market']['note']='National ratings withheld until quote graph connects every team. Matchup gaps are separate, dated comparisons, not national rating gaps.'
  out['market']['inputHashes']={q['source']:sha(q['source']) for q in quotes[league] if Path(q['source']).is_file()}
  out['market']['normalizedQuotes']=market_quotes
  if league=='cfb':out['market']['unmatchedEvents']=unmatched
  if league=='nfl':out['market']['inputHashes']['nfl_data/site/market-reference.json']=sha('nfl_data/site/market-reference.json')
  ranks={t:i+1 for i,t in enumerate(sorted(keys,key=lambda t:market[keys.index(t)],reverse=True))} if market is not None else {}
  for i,r in enumerate(out['rows']):
   r.update(marketRating=None if market is None else float(market[i]),marketRank=ranks.get(r['key']),ratingGap=None if market is None else r['rating']-float(market[i]),matchup=gaps[league].get(r['key']))
  out['rows'].sort(key=lambda r:(-r['rating'],r['key']))
  prev=None;rank=0
  for i,r in enumerate(out['rows']):
   if prev is None or abs(r['rating']-prev)>1e-10:rank=i+1
   r['rank']=rank;prev=r['rating']
  archive=ROOT/'snapshots'/now.strftime('%Y%m%dT%H%M%S%fZ');archive.mkdir(parents=True,exist_ok=True)
  (archive/(league+'.json')).write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
  path=ROOT/(league+'.json');path.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
  with (ROOT/(league+'.csv')).open('w') as f:
   fields=['rank','team','conference','rating','games','marketRank','marketRating','ratingGap'];w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(out['rows'])
  print(league,len(keys),'teams;',meta['status'],'market games',meta['games'],'matchup gaps',len(gaps[league]))
if __name__=='__main__':build()
