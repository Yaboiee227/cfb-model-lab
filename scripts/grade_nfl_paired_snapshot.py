"""Grade an immutable paired freeze against sourced finals and optional pregame locks.

Usage: python scripts/grade_nfl_paired_snapshot.py SNAPSHOT --results finals.json
Finals: [{game_id, status: FINAL, home_score, away_score, source, observed_at}].
Optional locks: [{game_id, spread_home, total, source, observed_at, captured_at}].
No automatic closing-line reconstruction. All rows, including pending games, survive.
"""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import pandas as pd
from analyze_nfl_week6_failure import grade, record

def utc(v):
    d=datetime.fromisoformat(v.replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('timezone required')
    return d.astimezone(timezone.utc)

def verify_snapshot(snapshot):
    m=json.loads((snapshot/'manifest.json').read_text())
    for name,h in m['files'].items():
        assert hashlib.sha256((snapshot/name).read_bytes()).hexdigest()==h,name
    return m

def validate_lock(lock,kickoff):
    observed=utc(lock['observed_at']);captured=utc(lock['captured_at'])
    assert kickoff-timedelta(minutes=30)<=observed<=captured<kickoff
    assert (captured-observed).total_seconds()<=300
    assert lock['source']
    for field in ['spread_home','total']:assert pd.notna(lock[field])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('snapshot',type=Path);ap.add_argument('--results',type=Path,required=True);ap.add_argument('--locks',type=Path);args=ap.parse_args()
    manifest=verify_snapshot(args.snapshot);p=pd.read_csv(args.snapshot/'paired_projections.csv');now=datetime.now(timezone.utc)
    finalrows=json.loads(args.results.read_text());assert len({x['game_id'] for x in finalrows})==len(finalrows)
    finals={r['game_id']:r for r in finalrows}
    lockrows=json.loads(args.locks.read_text()) if args.locks else [];assert len({x['game_id'] for x in lockrows})==len(lockrows)
    locks={r['game_id']:r for r in lockrows};assert set(finals)<=set(p.game_id) and set(locks)<=set(p.game_id)
    rows=[]
    for r in p.itertuples():
        row={'game_id':r.game_id,'status':'PENDING','canonical_ats':None,'ftn50_ats':None,'totals':None}
        ko=utc(r.kickoff_utc);assert utc(r.frozen_at_utc)<ko
        if r.game_id in finals:
            f=finals[r.game_id];assert f['status']=='FINAL' and ko<utc(f['observed_at'])<=now and f['source']
            hs,aws=f['home_score'],f['away_score'];assert all(isinstance(x,int) and x>=0 for x in [hs,aws])
            margin=hs-aws;total=hs+aws
            row.update(status='FINAL',canonical_margin_ae=abs(r.canonical_home_margin-margin),ftn50_margin_ae=abs(r.ftn50_home_margin-margin),total_ae=abs(r.canonical_total-total),canonical_su=grade(r.canonical_home_margin,margin),ftn50_su=grade(r.ftn50_home_margin,margin),result_source=f['source'])
            if r.game_id in locks:
                lock=locks[r.game_id];validate_lock(lock,ko)
                row.update(canonical_ats=grade(r.canonical_home_margin+lock['spread_home'],margin+lock['spread_home']),ftn50_ats=grade(r.ftn50_home_margin+lock['spread_home'],margin+lock['spread_home']),totals=grade(r.canonical_total-lock['total'],total-lock['total']))
        rows.append(row)
    out=args.snapshot.parent/'grades';out.mkdir(exist_ok=True)
    path=out/(manifest['snapshot_id']+'_'+now.strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    summary={k:record([r.get(k) for r in rows]) for k in ['canonical_ats','ftn50_ats','totals','canonical_su','ftn50_su']}
    with path.open('x') as f:json.dump(dict(snapshot_id=manifest['snapshot_id'],graded_at=now.isoformat(),summary=summary,games=rows,promotion_allowed=False,missing_market_rule='ATS/totals remain null without timely locks; no fabricated prices.'),f,indent=2)
    print(path)

if __name__=='__main__':main()
