"""Paired walk-forward evaluation; does not authorize promotion.
Each row contains pregame frozen predictions and later final scores. Strictly
separate NFL/CFB metrics. A timestamp assertion is necessary, not proof of an
honest historical archive; callers must supply immutable source provenance.
"""
import argparse
import json
from pathlib import Path
from personnel_scenarios import timestamp, number


def evaluate(rows):
    groups={}; seen=set()
    for r in rows:
        key=(r['league'],r['gameId'])
        if key in seen:raise ValueError('duplicate game: '+str(key))
        seen.add(key)
        if r['league'] not in ('nfl','cfb'):raise ValueError('league')
        if not r.get('predictionSourceSha256') or not r.get('resultSource'):raise ValueError('provenance required')
        if not timestamp(r['trainingCutoff']) <= timestamp(r['frozenAt']) < timestamp(r['kickoff']) <= timestamp(r['resultObservedAt']):raise ValueError('leakage or invalid chronology')
        if r['resultStatus']!='Final':raise ValueError('non-final result')
        actual=number(r['finalHomePoints'])-number(r['finalAwayPoints'])
        total=number(r['finalHomePoints'])+number(r['finalAwayPoints'])
        bucket=groups.setdefault(r['league'],[])
        bucket.append({name:{'marginError':number(r[name]['homePoints'])-number(r[name]['awayPoints'])-actual,'totalError':number(r[name]['homePoints'])+number(r[name]['awayPoints'])-total} for name in ('baseline','challenger')})
    out={}
    for league, rs in groups.items():
        out[league]={'games':len(rs)}
        for name in ('baseline','challenger'):
            out[league][name]={metric:sum(abs(r[name][field]) for r in rs)/len(rs) for metric,field in [('marginMAE','marginError'),('totalMAE','totalError')]}
        out[league]['marginMAEChange']=out[league]['challenger']['marginMAE']-out[league]['baseline']['marginMAE']
        out[league]['totalMAEChange']=out[league]['challenger']['totalMAE']-out[league]['baseline']['totalMAE']
    return dict(role='PERSONNEL_PAIRED_EVALUATION',canonicalInfluence=False,promotionAuthorized=False,metrics=out,limitations=['No automatic promotion or significance claim.','Requires independently audited as-of archives and per-fold fitting.','Report missing-input coverage and rejected games separately; never select only favorable cases.','Point-error evaluation only; ATS/total grading and probability calibration require separate saved market/probability evidence.'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);args=p.parse_args()
    print(json.dumps(evaluate(json.loads(args.input.read_text())),indent=2,allow_nan=False))
