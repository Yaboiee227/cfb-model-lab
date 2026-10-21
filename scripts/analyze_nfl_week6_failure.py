"""Read-only source audit and isolated challenger evaluation. Never writes production."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

OUT = Path('nfl_data/research/week6_failure_20261021')

def grade(edge, outcome):
    if abs(edge) < 1e-9: return 'NO_PICK'
    if abs(outcome) < 1e-9: return 'PUSH'
    return 'WIN' if edge * outcome > 0 else 'LOSS'

def record(grades):
    return {g: list(grades).count(g) for g in ['WIN','LOSS','PUSH','NO_PICK']}

def metrics(y,p):
    e=np.asarray(p)-np.asarray(y)
    return dict(n=len(e),mae=float(np.abs(e).mean()),rmse=float(np.sqrt((e*e).mean())),bias=float(e.mean()),prediction_sd=float(np.std(p)),actual_sd=float(np.std(y)))

def cluster_ci(frame, delta, alpha=.05):
    # Preserve all games within each season-week. Seed fixed before evaluation.
    groups=pd.DataFrame({'season':frame.season,'week':frame.week,'d':delta}).groupby(['season','week']).d.agg(['sum','count'])
    rng=np.random.default_rng(20261021)
    ix=rng.integers(0,len(groups),(10000,len(groups)))
    draws=groups['sum'].to_numpy()[ix].sum(axis=1)/groups['count'].to_numpy()[ix].sum(axis=1)
    return dict(improvement=float(np.mean(delta)),ci=list(np.quantile(draws,[alpha/2,1-alpha/2])),clusters=len(groups),draws=10000)

def main():
    frozen=json.loads((OUT/'inputs/published_week06_results.json').read_text())['games']
    pub=pd.read_csv(OUT/'inputs/published_week06_projections.csv').set_index('gameId')
    shadow=pd.read_csv('nfl_data/prospective/shadow/week6_ftn50_shadow_20261017T235342Z.csv').set_index('game_id')
    assert len(frozen)==13 and set(pub.index)=={g['gameId'] for g in frozen}==set(shadow.index)
    records=[]
    for g in frozen:
        gid=g['gameId']; p=g['projection']; m=g['market']; f=g['final']; s=shadow.loc[gid]
        margin=f['homeScore']-f['awayScore']; total=f['total']; pred=-p['spreadHome']; sp=float(s.shadow_50_50_home_margin)
        assert pd.Timestamp(s.shadow_snapshot_created_at_utc)<pd.Timestamp(g['kickoff'])
        assert pd.Timestamp(m['observedAt'])<pd.Timestamp(g['kickoff'])
        assert abs(pred-float(pub.loc[gid,'modelSpreadHome'])*-1)<.0011
        assert abs(pred-float(s.canonical_home_margin))<.0011
        ats=grade(pred+m['spreadHome'],margin+m['spreadHome'])
        tot=grade(p['total']-m['total'],total-m['total'])
        su=grade(pred,margin)
        assert (ats,tot,su)==(g['ats']['result'],g['totals']['result'],g['straightUp']['result'])
        records.append(dict(game_id=gid,home=g['homeTeam'],away=g['awayTeam'],actual_margin=margin,actual_total=total,canonical_margin=pred,canonical_total=p['total'],shadow_margin=sp,market_margin=-m['spreadHome'],market_total=m['total'],ats=ats,totals=tot,su=su,shadow_ats=grade(sp+m['spreadHome'],margin+m['spreadHome']),shadow_su=grade(sp,margin),spread_error=pred-margin,total_error=p['total']-total,spread_edge=pred+m['spreadHome'],hard_qb_break=str(pub.loc[gid,'hardQbStateBreak']).lower()=='true',final_inactives_resolved=str(pub.loc[gid,'finalInactivesResolved']).lower()=='true'))
    w=pd.DataFrame(records); w.to_csv(OUT/'week6_game_attribution.csv',index=False)
    groups={'all':w,'hard_qb_break':w[w.hard_qb_break],'no_hard_qb_break':w[~w.hard_qb_break],'home_ats_pick':w[w.spread_edge>0],'away_ats_pick':w[w.spread_edge<0],'edge_lt_1':w[w.spread_edge.abs()<1],'edge_ge_3':w[w.spread_edge.abs()>=3]}
    report={'official':{k:record(w[k]) for k in ['ats','totals','su']},'canonical_spread':metrics(w.actual_margin,w.canonical_margin),'ftn50_spread':metrics(w.actual_margin,w.shadow_margin),'market_spread_benchmark':metrics(w.actual_margin,w.market_margin),'canonical_total':metrics(w.actual_total,w.canonical_total),'market_total_benchmark':metrics(w.actual_total,w.market_total),'shadow_ats':record(w.shadow_ats),'shadow_su':record(w.shadow_su),'subgroups':{k:{'n':len(v),'ats':record(v.ats),'spread':metrics(v.actual_margin,v.canonical_margin)} for k,v in groups.items() if len(v)},'all_games_preserved':True,'executable_roi':None,'closing_line_value':None,'warning':'Subgroups are exploratory. Missing prices/closing snapshots preclude realized ROI or CLV. Saved official results are preserved; no postgame context reconstruction.'}
    hist=pd.read_csv('nfl_data/calibration/final_architecture_oos_predictions_2023_2025.csv')
    source=pd.read_csv('nfl_data/historical/game_pregame_features_2022_2025.csv')
    assert not hist.game_id.duplicated().any() and len(hist)==816
    for side in ['home','away']:
        assert (source[f'{side}_max_current_season_week_used']<source.week).all()
    hist['ats']=[grade(p+l,y+l) for p,l,y in zip(hist.pred_home_margin,hist.market_home_spread_reference,hist.actual_home_margin)]
    report['historical_by_season']={str(y):{'spread':metrics(v.actual_home_margin,v.pred_home_margin),'total':metrics(v.actual_total,v.pred_total),'market_spread':metrics(v.actual_home_margin,-v.market_home_spread_reference),'market_total':metrics(v.actual_total,v.market_total_reference),'ats':record(v.ats),'home_ats':record(v[v.spread_edge_vs_reference>0].ats),'away_ats':record(v[v.spread_edge_vs_reference<0].ats)} for y,v in hist.groupby('season')}
    candidate_rows=[]; fits={}
    for year in [2024,2025]:
        tr=hist[hist.season<year]; te=hist[hist.season==year].copy()
        assert tr.season.max()<year
        sb=float(np.median(tr.actual_home_margin-tr.pred_home_margin)); tb=float(np.median(tr.actual_total-tr.pred_total))
        x=tr.pred_total.to_numpy(); y=tr.actual_total.to_numpy(); xm=float(x.mean()); ym=float(y.mean())
        slope=float(((x-xm)@(y-ym)+100)/((x-xm)@(x-xm)+100))
        fits[str(year)]={'S_BIAS':sb,'T_BIAS':tb,'T_SLOPE':{'slope':slope,'intercept':ym-slope*xm},'train_seasons':sorted(tr.season.unique().tolist())}
        for name,pred,target,baseline in [('S_BIAS',te.pred_home_margin+sb,'actual_home_margin','pred_home_margin'),('T_BIAS',te.pred_total+tb,'actual_total','pred_total'),('T_SLOPE',ym+slope*(te.pred_total-xm),'actual_total','pred_total')]:
            for (_,r),p in zip(te.iterrows(),pred):
                candidate_rows.append(dict(candidate=name,game_id=r.game_id,season=year,week=int(r.week),actual=float(r[target]),canonical=float(r[baseline]),candidate_prediction=float(p)))
    c=pd.DataFrame(candidate_rows); c.to_csv(OUT/'challenger_oos_predictions.csv',index=False)
    evaluations={}
    for name,v in c.groupby('candidate'):
        d=np.abs(v.actual-v.canonical)-np.abs(v.actual-v.candidate_prediction)
        by={str(y):metrics(f.actual,f.candidate_prediction)['mae']-metrics(f.actual,f.canonical)['mae'] for y,f in v.groupby('season')}
        ci=cluster_ci(v,d,alpha=.05/3)
        evaluations[name]={'canonical':metrics(v.actual,v.canonical),'challenger':metrics(v.actual,v.candidate_prediction),'mae_delta_by_season':by,'simultaneous_cluster_interval':ci,'historical_screen_pass':bool(ci['ci'][0]>0 and all(d<0 for d in by.values())),'promotion_allowed':False,'evidence_status':'REUSED_OOS_DEVELOPMENT_ONLY'}
    report['challengers']={'fits':fits,'evaluations':evaluations,'limitations':['Prior OOS seasons have already informed architecture research; these are not untouched confirmation folds.','Week6 inspired hypotheses but is never a fitting or model-selection sample.','Feature-week exclusion checks pass; historical vendor revision/publication timestamps are not fully archived.','QB replacement and weather effects cannot be estimated from postgame starter or observed weather as if known pregame.']}
    (OUT/'analysis.json').write_text(json.dumps(report,indent=2)+'\n')
    manifest=json.loads((OUT/'preservation_manifest.json').read_text())
    changed=[p for p,h in manifest.items() if not Path(p).exists() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    assert not changed,changed
    (OUT/'integrity_check.json').write_text(json.dumps({'tracked_files_checked':len(manifest),'changed':changed,'official_grades_recomputed':True,'paired_shadow_games':13,'historical_feature_week_checks_pass':True},indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
