"""Sync published cumulative/weekly records from frozen graded evidence.
Display aggregation does not promote a model or mutate original research grades.
"""
import csv,json,collections,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads((ROOT/p).read_text())
def write(p,d):(ROOT/p).write_text(json.dumps(d,indent=2)+'\n')
def tally(results):
 c=collections.Counter(results);w,l,p=c['WIN'],c['LOSS'],c['PUSH'];return dict(wins=w,losses=l,pushes=p,graded=w+l+p,winPct=round(100*w/(w+l),1) if w+l else None)
def sync(league,week,games,note):
 path=f'{league}/record-summary.json';s=read(path);history=[w for w in s['weeks'] if int(w['week'])!=week]
 review=sum(g['ats']['result']=='REVIEW' or g['totals']['result']=='REVIEW' for g in games)
 current=dict(season=2026,week=week,status='COMPLETE_WITH_EXCLUSIONS' if review else 'COMPLETE',pending=0,review=review,recordType='Frozen research',note=note)
 for key in ['ats','totals','straightUp']:current[key]=tally(g[key]['result'] for g in games)
 s['weeks']=sorted(history+[current],key=lambda w:(w['season'],w['week']));s['currentWeek']=week;s['pending']=0;s['review']=review;s['generatedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat()
 s['sourceNote']='Published-model cumulative display, combining historical audited weeks and explicitly labeled frozen research weeks. Not a single validated model backtest. '+note
 s['label']='Published projection performance; research only, not wagers. Missing market locks excluded.'
 for key in ['ats','totals','straightUp']:
  w=sum(x[key]['wins'] for x in s['weeks']);l=sum(x[key]['losses'] for x in s['weeks']);p=sum(x[key].get('pushes',0) for x in s['weeks']);s['overall'][key]=dict(wins=w,losses=l,pushes=p,graded=w+l+p,winPct=round(100*w/(w+l),1) if w+l else None)
 for w in s['weeks']:w.setdefault('recordType','Historical audited')
 write(path,s);write(f'{league}/results/week-{week:02d}.json',dict(league=league,season=2026,week=week,role='PUBLISHED_RESEARCH_RESULTS_COMPATIBILITY',canonicalInfluence=False,games=games,sourceNote=note))
 csvpath=ROOT/('data/results.csv' if league=='cfb' else 'nfl_data/site/results.csv')
 with csvpath.open() as f:
  reader=csv.DictReader(f);fields=list(reader.fieldnames);old=[r for r in reader if not (int(r['season'])==2026 and int(r['week'])==week)]
 for field in ['trackingClass','gradeReference']:
  if field not in fields:fields.append(field)
 for g in games:
  row=dict(season=2026,week=week,date=g.get('date',''),gameId=g['gameId'],awayTeam=g['awayTeam'],homeTeam=g['homeTeam'],conference='NFL' if league=='nfl' else '',awayScore=g['final']['awayScore'],homeScore=g['final']['homeScore'],modelSpreadHome=g['projection']['spreadHome'],modelTotal=g['projection']['total'],marketSpreadHome=g['market'].get('spreadHome'),marketTotal=g['market'].get('total'),homeWinProbability=g['projection'].get('homeWinProbability'),atsProjection=g['ats']['pick'],atsResult=g['ats']['result'],totalProjection=g['totals']['pick'],totalResult=g['totals']['result'],suProjection=g['straightUp']['pick'],suResult=g['straightUp']['result'],trackingClass='FROZEN_RESEARCH',gradeReference=('cfb/research-results/week-08-foundation-full.json' if league=='cfb' else f'nfl/research-results/week-{week:02d}.json'))
  old.append(row)
 with csvpath.open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(old)
 return s
cfb=read('cfb/research-results/week-08-foundation-full.json');markets={g['gameId']:g for g in read('cfb/validation/week-08-foundation-vs-markets-results.json')['games']};games=[]
for g in cfb['games']:
 b=markets[g['gameId']].get('books',{}).get('draftkings');v=b['modelVsMarket'] if b else {};home=g['homeTeam'];away=g['awayTeam']
 games.append(dict(gameId=g['gameId'],date=g['gameId'][:10],awayTeam=away,homeTeam=home,status=g['status'],final=g['final'],projection=g['projection'],market=dict(spreadHome=b['marketSpreadHome'],total=b['marketTotal'],moneylineHome=b.get('marketMoneylineHome'),moneylineAway=b.get('marketMoneylineAway')) if b else {},ats=dict(pick=(home if v.get('spreadPosition')=='HOME' else away) if b else None,result=v.get('spreadResult','REVIEW')),totals=dict(pick=v.get('totalPosition'),result=v.get('totalResult','REVIEW')),straightUp=dict(pick=g['projection']['winner'],result=g['straightUp']['result'])))
sync('cfb',8,games,'Week 8: frozen foundation research; DraftKings fixed benchmark for this display (FanDuel separately audited). Five games excluded from ATS/totals for missing locks; all 56 SU graded.')
nfl=read('nfl/research-results/week-07.json');paired={r['game_id']:r for r in csv.DictReader((ROOT/'nfl_data/prospective/week7/20261021T114427Z/paired_projections.csv').open())};games=[]
for g in nfl['games']:
 r=paired[g['gameId']];spread=float(r['canonical_home_spread']);total=float(r['canonical_total']);winner=g['homeTeam'] if spread<0 else g['awayTeam'];market=g.get('marketSpreadHome');mt=g.get('marketTotal')
 games.append(dict(gameId=g['gameId'],date=datetime.datetime.fromisoformat(r['kickoff_utc']).astimezone(__import__('zoneinfo').ZoneInfo('America/New_York')).date().isoformat(),awayTeam=g['awayTeam'],homeTeam=g['homeTeam'],status='FINAL',final=dict(awayScore=g['awayScore'],homeScore=g['homeScore']),projection=dict(spreadHome=spread,total=total,winner=winner),market=dict(spreadHome=market,total=mt),ats=dict(pick=(g['homeTeam'] if market>spread else g['awayTeam']) if market is not None else None,result=g['atsResult']),totals=dict(pick=('OVER' if total>mt else 'UNDER') if mt is not None else None,result=g['totalResult']),straightUp=dict(pick=winner,result=g['suResult'])))
sync('nfl',7,games,'Week 7: frozen Canonical V1 research projections, qualifying first-capture market locks. Two games excluded from ATS/totals; all 14 SU graded.')
