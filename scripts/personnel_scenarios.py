"""Pregame personnel sensitivity engine. Research only; never promotes features.
Values are points per game for the SAME team, opponent and workload. They must
be supplied by a separately evidenced, league-specific estimator. Not a fitter.
"""
import argparse
import copy
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def timestamp(value):
    d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if d.tzinfo is None:
        raise ValueError('timezone required')
    return d


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('finite numeric input required')
    return float(value)


def mixture(shares, values):
    if not shares or any(number(s) < 0 for s in shares.values()) or abs(sum(shares.values()) - 1) > 1e-8:
        raise ValueError('QB workload shares must sum to one')
    return sum(number(s) * number(values[q]['estimate']) for q, s in shares.items())


def build(request, as_of):
    req = copy.deepcopy(request)
    out = dict(role='PERSONNEL_SCENARIO_CHALLENGER', canonicalInfluence=False,
               promotionAuthorized=False, validated=False, status='WITHHELD',
               asOf=as_of, gameId=req.get('gameId'), league=req.get('league'),
               baselineSha256=hashlib.sha256(json.dumps(req.get('baseline'), sort_keys=True).encode()).hexdigest(),
               blockers=[], scenarios=[])
    try:
        now, kickoff = timestamp(as_of), timestamp(req['kickoff'])
        if now >= kickoff:
            raise ValueError('target game has started; no pregame reconstruction')
        if req['league'] not in ('nfl', 'cfb'):
            raise ValueError('unsupported league')
        for key in ('baselineEvidence', 'availabilityEvidence', 'exposureEvidence', 'valuationEvidence'):
            evidence = req[key]
            if evidence['gameId'] != req['gameId'] or evidence['league'] != req['league']:
                raise ValueError(key + ': scope mismatch')
            if not evidence.get('source') or timestamp(evidence['observedAt']) > now or timestamp(evidence['observedAt']) >= kickoff:
                raise ValueError(key + ': missing or non-pregame evidence')
        if req['valuationEvidence'].get('methodStatus') not in ('UNVALIDATED_RESEARCH', 'VALIDATED_CHALLENGER'):
            raise ValueError('valuation method must declare research status')
        if timestamp(req['valuationEvidence']['trainingCutoff']) > now:
            raise ValueError('future training cutoff')
        home, away = number(req['baseline']['homePoints']), number(req['baseline']['awayPoints'])
        if min(home, away) < 0:
            raise ValueError('negative baseline score')
        values = req['quarterbackValues']
        for v in values.values():
            lo, mid, hi = map(number, (v['low'], v['estimate'], v['high']))
            if not lo <= mid <= hi:
                raise ValueError('invalid valuation interval')
        old = req['baselineQbShares']
        mixture(old, values)
        if req['affectedSide'] not in ('home', 'away'):
            raise ValueError('affectedSide must be home or away')
        for scenario in req['scenarios']:
            new = scenario['qbShares']
            mixture(new, values)
            weights = {q: new.get(q, 0) - old.get(q, 0) for q in set(new) | set(old)}
            delta = sum(w * values[q]['estimate'] for q, w in weights.items())
            low = sum(w * values[q]['low' if w >= 0 else 'high'] for q, w in weights.items())
            high = sum(w * values[q]['high' if w >= 0 else 'low'] for q, w in weights.items())
            h, a = (home + delta, away) if req['affectedSide'] == 'home' else (home, away + delta)
            if min(h, a) < 0:
                raise ValueError('scenario implies negative points; valuation incompatible')
            result = dict(name=scenario['name'], offensivePointDelta=delta,
                          sensitivityBounds=[low, high], homePoints=h, awayPoints=a,
                          modelSpreadHome=a-h, modelTotal=h+a, homeWinProbability=None,
                          probabilityStatus='WITHHELD_NO_LEAGUE_CALIBRATION',
                          interpretation='Conditional sensitivity; bounds are not calibrated confidence intervals')
            calibration = req.get('marginCalibration')
            if calibration:
                if calibration['league'] != req['league'] or not calibration.get('source') or calibration.get('validated') is not True or timestamp(calibration['observedAt']) > now or timestamp(calibration['trainingCutoff']) > now:
                    raise ValueError('invalid league margin calibration')
                sd = number(calibration['residualStd'])
                if sd <= 0:
                    raise ValueError('positive residual standard deviation required')
                result['homeWinProbability'] = 100 * .5 * (1 + math.erf((h-a)/(sd*math.sqrt(2))))
                result['probabilityStatus'] = 'CONDITIONAL_ON_SUPPLIED_NORMAL_MARGIN_CALIBRATION'
            out['scenarios'].append(result)
        if not out['scenarios']:
            raise ValueError('no scenarios supplied')
        out.update(status='UNVALIDATED_RESEARCH_SCENARIOS', evidence={k:req[k] for k in ('baselineEvidence','availabilityEvidence','exposureEvidence','valuationEvidence')})
    except (KeyError, ValueError, TypeError) as exc:
        out['blockers'].append(str(exc))
        out['scenarios'] = []
    return out


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('input', type=Path)
    p.add_argument('--as-of', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.input.resolve() == args.output.resolve():
        p.error('output must not overwrite input')
    result = build(json.loads(args.input.read_text()), args.as_of)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write('\n')
