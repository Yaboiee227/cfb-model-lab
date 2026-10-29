"""Test prior-only QB-room proxies against the current canonical NFL baseline.
Run from pinned NFL checkout. This is NOT a confirmed-starter change model.
"""
import sys,json,csv,argparse,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path.cwd()/'scripts'))
import run_nfl_walk_forward as base
import build_nfl_week6_research_projections as wk
import validate_nfl_rating_system_robustness as rat
import validate_nfl_final_plus_ftn_qb_process as fm
ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
spec=json.load(open('nfl_data/validation/final_ftn_qb_process_blend.json'));cp=spec['coverage_params'];rp=fm.RATING
s=pd.read_csv('nfl_data/research/week6_failure_20261021/inputs/nflverse_games.csv');s=s[s.game_type.eq('REG')&s.season.between(2021,2026)].sort_values(['season','week','gameday','gametime','game_id']);s.loc[(s.season==2026)&(s.week>=7),['home_score','away_score']]=np.nan
s['home_team']=s.home_team.map(rat.nt);s['away_team']=s.away_team.map(rat.nt)
rmap=rat.rating_maps(s,rp['elo_k'],rp['elo_hfa'],rp['offseason_regression'],rp['margin_k'],rp['margin_hfa']);rows=rat.attach(wk.attach_historical_coverage(base.load_rows()),rmap)
source=Path('nfl_data/historical/team_week_qb_room_2022_2025.csv');qrows=list(csv.DictReader(source.open()));idx={}
for q in qrows:
 key=(int(q['season']),int(q['target_week']),q['team']);assert key not in idx
 assert int(q['max_current_week_used'])<key[1]
 idx[key]=q

def value(q,k):return base.to_float(q.get(k))
def diff(x,y):return np.nan if x is None or y is None else x-y

def extra(r,variant):
 h=idx[(r['season'],r['week'],r['home_team'])];aw=idx[(r['season'],r['week'],r['away_team'])]
 if variant=='primary_quality_proxy':return [diff(value(h,'primary_pass_epa_per_db'),value(aw,'primary_pass_epa_per_db'))]
 # Delta between recent/cumulative room proxies does not assert an actual QB change.
 def delta(q):
  x,y=value(q,'recent_pass_epa_per_db'),value(q,'primary_pass_epa_per_db');return None if x is None or y is None else x-y
 return [diff(delta(h),delta(aw)),diff(value(h,'raw_primary_minus_replacement_epa_per_db'),value(aw,'raw_primary_minus_replacement_epa_per_db'))]

def matrix(rs,v):
 _,x=fm.matrix(rs,cp['team_k'],cp['feature_k'])
 return x if v=='baseline' else np.column_stack([x,np.asarray([extra(r,v) for r in rs])])
variants=['baseline','primary_quality_proxy','room_transition_proxy'];agg={v:[] for v in variants};actual=[];folds={}
def metrics(y,p):
 e=np.asarray(p)-np.asarray(y);return dict(games=len(e),mae=float(np.mean(abs(e))),rmse=float(np.sqrt(np.mean(e**2))),bias=float(np.mean(e)))
for year in [2023,2024,2025]:
 train=[r for r in rows if r['season']<year];test=[r for r in rows if r['season']==year];y=base.target_array(test,'spread');actual.extend(y);folds[str(year)]={}
 for v in variants:
  x,xt=matrix(train,v),matrix(test,v);prep=base.fit_preprocessor(x);fit=base.ridge_fit(base.transform(x,prep),base.target_array(train,'spread'),rp['lambda']);p=base.predict(fit,base.transform(xt,prep));agg[v].extend(p);folds[str(year)][v]=metrics(y,p)
result={v:metrics(actual,p) for v,p in agg.items()};assert abs(result['baseline']['mae']-10.25639224074248)<1e-8
out=dict(canonicalInfluence=False,status='EXPLORATORY_NO_PROMOTION',sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(),sourceTeamWeeks=len(qrows),historicalFolds=folds,aggregate=result,policy=['Only pre-target-week performance proxies used.','No target-game realized starter used.','Existing canonical feature architecture and lambda preserved; one feature family added at a time.','These seasons have been examined previously; not new blind holdouts.','Does not test actual timestamped starter changes or position-group injuries.'])
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(result,indent=2))
