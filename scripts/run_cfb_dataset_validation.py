"""Run existing feature tests from published SportsDataverse season files."""
import sys,csv,json,argparse,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import cfb_foundation_feature_validation as ff
import cfb_shadow_engine as engine
import cfb_rich_challenger as rich
ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--output',required=True);ap.add_argument('--epa',action='store_true');ap.add_argument('--drives',action='store_true');ap.add_argument('--residual',action='store_true');a=ap.parse_args();assert not(a.epa and a.drives),'Isolate one family';root=Path.cwd();cache={};boxes={}
for year in [2025,2026]:
 rows=list(csv.DictReader((a.inputs/f'cfb_schedule_{year}.csv').open()));games=[];names={}
 for r in rows:
  if r['season_type']!='2' or r['status']!='STATUS_FINAL':continue
  home,away=engine.canonical_school(r['home_team']),engine.canonical_school(r['away_team']);names[r['home_id']]=home;names[r['away_id']]=away
  games.append(engine.Game(str(r['game_id']),engine.parse_dt(r['game_date']),home,away,float(r['home_score']),float(r['away_score']),r['neutral_site'].lower()=='true'))
 cache[year]=sorted(games,key=lambda g:(g.kickoff,g.game_id))
 for r in csv.DictReader((a.inputs/f'team_box_{year}.csv').open()):
  gid=str(r['game_id']);key=names.get(r['team_id'])
  if key:
   boxes.setdefault(gid,{})[key]=rich.normalized_box([dict(name=k,displayValue=v) for k,v in r.items()])
 if a.epa:
  for g in cache[year]:
   for v in boxes.get(g.game_id,{}).values():
    for k in ["yardsPerPlay","passYpa","rushYpa"]:v[k]=None
  matched=0
  for r in csv.DictReader((a.inputs/f'adv_team_gamelog_{year}.csv').open()):
   gid=str(r['game_id']);key=names.get(r['team_id'])
   if key and key in boxes.get(gid,{}):
    vals=[rich.numeric(r.get(k)) for k in ['EPA_per_play','EPA_passing_per_play','EPA_rushing_per_play']]
    for k,v in zip(['yardsPerPlay','passYpa','rushYpa'],vals):boxes[gid][key][k]=v
    matched+=all(v is not None for v in vals)
  print(year,'complete EPA team-game rows',matched,flush=True)
 if a.drives:
  from cfb_drive_counts import regulation_drive_counts
  counts,excluded=regulation_drive_counts(csv.DictReader((a.inputs/f'drives_{year}.csv').open()))
  for g in cache[year]:
   for v in boxes.get(g.game_id,{}).values():v['plays']=None
  for (gid,tid),count in counts.items():
   key=names.get(tid)
   if key in boxes.get(gid,{}):boxes[gid][key]['plays']=float(count)
  print(year,'drive exclusions',excluded,flush=True)
 print(year,len(cache[year]),'regular finals',flush=True)
def fetch_games(start,end):return [g for y in range(start.year,end.year+1) for g in cache.get(y,[]) if start<=g.kickoff<end]
def fetch_boxes(games):
 out={g.game_id:boxes[g.game_id] for g in games if g.home in boxes.get(g.game_id,{}) and g.away in boxes.get(g.game_id,{})}
 return out,[dict(gameId=g.game_id,error='Dataset missing both team boxes') for g in games if g.game_id not in out]
prior=json.loads((root/'cfb/validation/week-08-foundation-feature-family-validation.json').read_text())
ff.estimate_prior_only_hfa=lambda *args,**kwargs:(prior['hfa']['2025'],prior['hfa']['2025SeasonEstimates'])
engine.fetch_completed_games=fetch_games;rich.fetch_boxes=fetch_boxes
if a.epa:ff.ff.FEATURE_FAMILIES={'epa_efficiency':(2,3,4)}
if a.drives:ff.ff.FEATURE_FAMILIES={'regulation_drive_volume':(9,)}
if a.residual:
 original_fit=rich.ridge_fit;original_predict=rich.ridge_predict
 def residual_fit(rows,indices,target,alpha):
  base=0 if target=='margin' else 1
  training=[dict(r,**{target:float(r[target])-float(r['x'][base])}) for r in rows]
  fitted=original_fit(training,tuple(i for i in indices if i!=base),target,alpha)
  return {'fixed_baseline_residual':True,'base':base,'fitted':fitted}
 def residual_predict(model,rows):
  if isinstance(model,dict) and model.get('fixed_baseline_residual'):
   correction=original_predict(model['fitted'],rows)
   return [float(r['x'][model['base']])+float(c) for r,c in zip(rows,correction)]
  return original_predict(model,rows)
 ff.ff.fit_candidate=residual_fit;rich.ridge_predict=residual_predict
sys.argv=['cfb_foundation_feature_validation.py' ,'--as-of','2026-10-27T04:00:00Z','--output',a.output];ff.main()
p=Path(a.output);d=json.loads(p.read_text());d['alternateSource']={'publisher':'SportsDataverse','upstream':'ESPN-derived; not independent corroboration','historicalRevisionWarning':'Current revised season files, not archived original pregame bytes','files':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in a.inputs.glob('*.csv')}};
if a.epa:
 d['featureDefinition']={'epa_efficiency':['opponent-adjusted overall EPA/play difference','opponent-adjusted passing EPA/play difference','opponent-adjusted rushing EPA/play difference'],'excluded':['success rate absent from source schema','possession estimates not implemented in this experiment'],'note':'Existing opponent-adjusted metric fitter reused. Source EPA model training cutoff is not verified, so this cannot certify strictly point-in-time historical evaluation.'}
 d['promotionStatus']='HOLD_EPA_MODEL_POINT_IN_TIME_PROVENANCE_UNVERIFIED'
 d['validation']['families']['epa_efficiency']['marginChallengerEligible']=False
 d['validation']['families']['epa_efficiency']['totalChallengerEligible']=False
 d['validation']['challengerEligibleFamilies']=[]
 d['validation']['families']['epa_efficiency']['features']=['epaMatchupDiff','passingEpaMatchupDiff','rushingEpaMatchupDiff']
if a.drives:
 d['featureDefinition']={'regulation_drive_volume':['sum of opponent-adjusted expected regulation offensive-drive counts for both teams'],'limitations':['includes kneel-only drives if source marks offensive plays','drive ownership relies on source team_id','not a full game-script-aware possession simulator','regulation drive features predict full-game targets; overtime outcome remains in targets']}
 d['validation']['families']['regulation_drive_volume']['features']=['combinedExpectedRegulationDrives']
 d['validation']['families']['regulation_drive_volume']['marginChallengerEligible']=False
 d['promotionStatus']='RESEARCH_ONLY_NO_AUTOMATIC_PROMOTION'
d['baselinePolicy']='Fixed baseline plus learned correction; baseline coefficient is not refit' if a.residual else 'Existing baseline-refit family evaluation'
d['warning']+=' Alternate-source retrospective replication; eligibility requires baseline coverage/parity review.';p.write_text(json.dumps(d,indent=2)+'\n')
