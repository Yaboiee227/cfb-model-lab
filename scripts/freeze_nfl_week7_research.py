"""Create a new immutable paired Week 7 research freeze from cached source bytes.

Canonical coefficients/feature architecture and FTN50 weight remain unchanged.
No legacy artifact is written. Context and markets are separate, unresolved gates.
"""
import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
import run_nfl_walk_forward as base
import build_nfl_week6_research_projections as wk
import build_nfl_coverage_features as coverage
import build_nfl_ftn_charting_features as chart
import build_nfl_week6_ftn50_shadow_snapshot as shadow
import validate_nfl_ftn_charting_robustness as ftn
import validate_nfl_final_plus_ftn_qb_process as model
import validate_nfl_rating_system_robustness as rat

def write_json(path,data):
    with path.open('x') as f: json.dump(data,f,indent=2,allow_nan=False);f.write('\n')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cache',type=Path,required=True);args=ap.parse_args()
    cache=args.cache.resolve(); now=datetime.now(timezone.utc); stamp=now.strftime('%Y%m%dT%H%M%SZ')
    out=Path('nfl_data/prospective/week7')/stamp;out.mkdir(parents=True,exist_ok=False)
    inputs=Path('nfl_data/research/week6_failure_20261021/inputs')
    # Verify all retrieved bytes before using them.
    source_manifest=json.loads((cache/'manifest.json').read_text())
    for item in source_manifest:
        assert 'error' not in item,item
        assert hashlib.sha256((cache/item['file']).read_bytes()).hexdigest()==item['sha256']
        assert datetime.fromisoformat(item['retrieved_at'])<=now
    schedule=pd.read_csv(inputs/'nflverse_games.csv')
    current_schedule=schedule[(schedule.season==2026)&(schedule.week==7)&schedule.game_type.eq('REG')].copy()
    assert len(current_schedule)==14 and not current_schedule.game_id.duplicated().any()
    assert current_schedule.home_score.isna().all() and current_schedule.away_score.isna().all()
    def kickoff(r):return datetime.fromisoformat(r.gameday+'T'+r.gametime).replace(tzinfo=ZoneInfo('America/Detroit')).astimezone(timezone.utc)
    assert all(kickoff(r)>now for r in current_schedule.itertuples())
    wk.TARGET_WEEK=7;wk.CUTOFF_WEEK=6
    wk.hist.PBP_URL=cache.as_uri()+'/play_by_play_{season}.csv.gz'
    wk.hist.fetch_schedule=lambda:list(csv.DictReader((inputs/'nflverse_games.csv').open()))
    coverage.URL=str(cache/'advstats_week_def_{season}.parquet')
    c25=coverage.weekly(coverage.load(2025));c26=coverage.weekly(coverage.load(2026))
    teams=sorted(set(t for t,w in c26)|set(t for t,w in c25));assert len(teams)==32
    covrows=[coverage.snap(2026,7,t,c26,c25) for t in teams]
    assert max(r['max_current_week_used'] for r in covrows)==6
    pd.DataFrame(covrows).to_csv(out/'coverage_inputs.csv',index=False)
    # FTN joins retain PBP's authoritative team/week identity.
    chart.FTN=str(cache/'ftn_charting_{season}.parquet')
    chart.PBP=str(cache/'pbp_join_{season}.parquet')
    for y in [2025,2026]:
        join=cache/f'pbp_join_{y}.parquet'
        if not join.exists():pd.read_csv(cache/f'play_by_play_{y}.csv.gz',usecols=['game_id','play_id','season','week','season_type','posteam','defteam']).to_parquet(join,index=False)
    _,_,j25=chart.load_season(2025);f26,_,j26=chart.load_season(2026)
    # A joined administrative/non-possession play may legitimately lack posteam.
    # Require every FTN key to match PBP's week; do not equate possession with join success.
    assert j26.week.notna().all()
    write_json(out/'ftn_join_qa.json',dict(rows=len(j26),matched_pbp_week=int(j26.week.notna().sum()),rows_without_possession_team=int(j26.posteam.isna().sum()),policy='Non-possession rows excluded by existing canonical charting aggregation; no invented team identity.'))
    o25,d25=chart.weekly(j25);o26,d26=chart.weekly(j26)
    ftrows=[chart.snap(2026,7,t,o26,d26,o25,d25) for t in teams]
    assert max(r['max_current_week_used'] for r in ftrows)==6
    pd.DataFrame(ftrows).to_csv(out/'ftn_inputs.csv',index=False)
    teamrows,qa,mw,future=wk.build_team_snapshot();assert mw==6 and future==0
    pd.DataFrame(teamrows.values()).to_csv(out/'core_inputs.csv',index=False)
    games,excluded=wk.build_current_games(teamrows,{r['team']:r for r in covrows})
    assert len(games)==14 and not excluded
    # Prevent future results from entering recursive ratings, even if a source is malformed.
    sched=schedule[schedule.game_type.eq('REG')&schedule.season.between(2021,2026)].copy()
    sched.loc[(sched.season==2026)&(sched.week>=7),['home_score','away_score']]=float('nan')
    sched=sched.sort_values(['season','week','gameday','gametime','game_id'])
    spec=json.loads(Path('nfl_data/validation/final_ftn_qb_process_blend.json').read_text())
    params=spec['coverage_params']; cand=spec['candidate_params_selected_2022_only'];rp=model.RATING
    rmap=rat.rating_maps(sched,rp['elo_k'],rp['elo_hfa'],rp['offseason_regression'],rp['margin_k'],rp['margin_hfa'])
    historical=base.load_rows(); hc=wk.attach_historical_coverage(historical)
    fi,leak,_=ftn.loadidx();assert leak==0
    hr=rat.attach(ftn.attach(hc,fi),rmap)
    cr=rat.attach(shadow.attach_current_ftn(games,{r['team']:r for r in ftrows}),rmap)
    pd.DataFrame(cr).to_csv(out/'game_feature_inputs.csv',index=False)
    cp,_=model.predict(cr,params['team_k'],params['feature_k'],model.fit(hr,params['team_k'],params['feature_k'],rp['lambda']))
    fp,_=model.predict(cr,params['team_k'],params['feature_k'],model.fit(hr,params['team_k'],params['feature_k'],cand['lambda'],cand['feature_k']),cand['feature_k'])
    tp,_=base.select_params([r for r in historical if r['season']==2022],'total')
    totals,*_=base.fit_and_predict(historical,cr,'total',tp['k'],tp['lambda'])
    results=[];gates=[]
    lookup=current_schedule.set_index('game_id')
    for r,p,f,t in zip(cr,cp,fp,totals):
        gid=r['game_id'];s=lookup.loc[gid];ko=kickoff(s)
        results.append(dict(game_id=gid,kickoff_utc=ko.isoformat(),frozen_at_utc=now.isoformat(),canonical_home_margin=float(p),canonical_home_spread=-float(p),canonical_total=float(t),ftn50_home_margin=float((p+f)/2),ftn50_total=float(t),canonical_model='CANONICAL_V1_UNCHANGED',challenger_model='FTN50_FIXED_EXISTING_SHADOW',release_state='HOLD_RESEARCH_ONLY'))
        gates.append(dict(game_id=gid,kickoff_utc=ko.isoformat(),neutral_site=str(s.location).lower()=='neutral',inactive_check_at=(ko-timedelta(minutes=90)).isoformat(),market_lock_window_start=(ko-timedelta(minutes=30)).isoformat(),market_lock_window_end=ko.isoformat(),context={'qb':'PENDING_OFFICIAL_VERIFICATION','inactives':'NOT_YET_RELEASED','weather':'PENDING_ISSUED_FORECAST','roof':'PENDING_VENUE_VERIFICATION'},market={'spread':None,'total':None,'prices':None,'observed_at':None,'execution_verified':False},benchmarks={},publication_status='HOLD',model_snapshot_id=stamp))
    pd.DataFrame(results).to_csv(out/'paired_projections.csv',index=False)
    write_json(out/'context_market_gates.json',gates)
    write_json(out/'source_manifest.json',source_manifest)
    write_json(out/'manifest.json',dict(snapshot_id=stamp,created_at_utc=now.isoformat(),games=14,max_source_week=6,training_seasons=[2022,2023,2024,2025],training_games=len(historical),canonical_changed=False,promotion_allowed=False,website_publish_allowed=False,release_allowed=False,source_policy='Sources retrieved before Week7; no claim these revised bytes were available before earlier historical games.',coverage_params=params,total_params=tp,ftn_params=cand,rating_params=rp,ftn_weight=.5,source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [inputs/'nflverse_games.csv',Path('nfl_data/historical/game_pregame_features_2022_2025.csv'),Path('nfl_data/historical/team_week_coverage_2022_2025.csv'),Path('nfl_data/historical/team_week_ftn_charting_2022_2025.csv')]},files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}))
    print(str(out));print(pd.DataFrame(results).to_string(index=False))

if __name__=='__main__':main()
