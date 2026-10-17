#!/usr/bin/env python3
"""Test leakage-safe red-zone efficiency as an incremental NFL feature family.

Spread reference: canonical final architecture (core + coverage + ratings).
Total reference: canonical frozen core total model.
Red-zone shrinkage and candidate ridge lambda are selected from 2022 only and
frozen for outer 2023-2025 evaluation. Research-only.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_nfl_walk_forward as base
import validate_nfl_ngs_team_v1 as ngs
import validate_nfl_ngs_team_v1_aliasfix  # noqa: F401
import validate_nfl_coverage_v1 as cov
import validate_nfl_rating_system_robustness as rat
import validate_nfl_final_plus_ftn_qb_process as qbp

IN = Path("nfl_data/historical/team_week_redzone_2022_2025.csv")
OUT = Path("nfl_data/validation/redzone_efficiency_robustness.json")
YEARS = [2023, 2024, 2025]
RZ_K = [10.0, 25.0, 50.0, 100.0, 200.0]
LAMBDAS = [10.0, 30.0, 100.0, 300.0]
DRAWS = 10000
SEED = 20261017
METRICS = [
    "off_rz_epa_per_play",
    "off_rz_success_rate",
    "def_rz_epa_per_play_allowed",
    "def_rz_success_rate_allowed",
]


def tf(v):
    return base.to_float(v)


def load_index():
    with IN.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    idx = {}
    leak = 0
    for r in rows:
        key = (int(float(r["season"])), int(float(r["target_week"])), r["team"])
        idx[key] = r
        mw = tf(r.get("max_current_week_used"))
        leak += int(mw is not None and mw >= key[1])
    return idx, leak, len(rows)


def attach(rows, idx):
    out = []
    missing = []
    for r in rows:
        h = idx.get((r["season"], r["week"], r["home_team"]))
        a = idx.get((r["season"], r["week"], r["away_team"]))
        if h is None or a is None:
            missing.append(r["game_id"])
            continue
        x = dict(r)
        for side, row in [("home", h), ("away", a)]:
            for k, v in row.items():
                if k not in {"season","target_week","team","release_state"}:
                    x[f"{side}_rz_{k}"] = v
        out.append(x)
    if missing:
        raise RuntimeError(f"missing red-zone snapshots {len(missing)} first={missing[:5]}")
    return out


def blend(r, side, metric, pseudo_plays):
    group = "off" if metric.startswith("off_") else "def"
    cur_n = tf(r.get(f"{side}_rz_cur_{group}_rz_plays")) or 0.0
    prior_n = tf(r.get(f"{side}_rz_prior_{group}_rz_plays")) or 0.0
    cur = tf(r.get(f"{side}_rz_cur_{metric}"))
    prior = tf(r.get(f"{side}_rz_prior_{metric}"))
    if cur is not None and prior is not None:
        # pseudo_plays controls how strongly prior-season efficiency anchors the
        # current small sample; prior_n is intentionally not used as full weight.
        return (cur_n * cur + pseudo_plays * prior) / (cur_n + pseudo_plays)
    return cur if cur is not None else prior


def rz_extras(r, kind, pseudo_plays):
    h = [blend(r, "home", m, pseudo_plays) for m in METRICS]
    a = [blend(r, "away", m, pseudo_plays) for m in METRICS]
    op = base.diff if kind == "spread" else base.summ
    suffix = "diff" if kind == "spread" else "sum"
    return [f"rz_{m}_{suffix}" for m in METRICS], [op(x, y) for x, y in zip(h, a)]


def matrix_spread(rows, team_k, cov_k, rz_k=None):
    names = None; data = []
    for r in rows:
        bn, bv = base.spread_features(r, team_k)
        cn, cv = cov.extras(r, "spread", "coverage", cov_k)
        n = bn + cn + ["rating_win_elo_diff", "rating_margin_rating_diff"]
        v = bv + cv + [float(r["rating_win_elo_diff"]), float(r["rating_margin_rating_diff"])]
        if rz_k is not None:
            en, ev = rz_extras(r, "spread", rz_k); n += en; v += ev
        if names is None: names = n
        data.append([np.nan if x is None else float(x) for x in v])
    return names, np.asarray(data, float)


def matrix_total(rows, team_k, rz_k=None):
    names = None; data = []
    for r in rows:
        bn, bv = base.total_features(r, team_k); n, v = bn, bv
        if rz_k is not None:
            en, ev = rz_extras(r, "total", rz_k); n += en; v += ev
        if names is None: names = n
        data.append([np.nan if x is None else float(x) for x in v])
    return names, np.asarray(data, float)


def fit(rows, kind, team_k, lam, cov_k=None, rz_k=None):
    names, X = matrix_spread(rows, team_k, cov_k, rz_k) if kind == "spread" else matrix_total(rows, team_k, rz_k)
    prep = base.fit_preprocessor(X)
    model = base.ridge_fit(base.transform(X, prep), base.target_array(rows, kind), lam)
    return names, prep, model


def pred(rows, kind, team_k, fitobj, cov_k=None, rz_k=None):
    names, prep, model = fitobj
    _, X = matrix_spread(rows, team_k, cov_k, rz_k) if kind == "spread" else matrix_total(rows, team_k, rz_k)
    return np.asarray(base.predict(model, base.transform(X, prep)), float)


def select(rows22, kind, team_k, cov_k=None):
    tr, va = base.inner_split(rows22); y = base.target_array(va, kind); options = []
    for k in RZ_K:
        for lam in LAMBDAS:
            fo = fit(tr, kind, team_k, lam, cov_k, k)
            p = pred(va, kind, team_k, fo, cov_k, k)
            options.append({"redzone_pseudo_plays":k,"lambda":lam,"mae":base.mae(y,p),"rmse":base.rmse(y,p),"validation_games":len(va)})
    options.sort(key=lambda x:(x["mae"],x["rmse"],x["lambda"],x["redzone_pseudo_plays"]))
    return options[0], options[:8]


def ae(rows, p, kind):
    return np.abs(base.target_array(rows, kind) - np.asarray(p, float))


def boot(diff):
    d=np.asarray(diff,float); rng=np.random.default_rng(SEED); n=len(d); draws=np.empty(DRAWS)
    for i in range(DRAWS): draws[i]=np.mean(d[rng.integers(0,n,size=n)])
    lo,hi=np.quantile(draws,[.025,.975])
    return {"mean_improvement":round(float(np.mean(d)),5),"bootstrap_95_ci":[round(float(lo),5),round(float(hi),5)],"probability_gt_0":round(float(np.mean(draws>0)),4),"draws":DRAWS}


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    idx, leak, nrows = load_index()
    base_rows = base.load_rows()
    ni, nl, _ = ngs.load_index(); ci, cl, _ = cov.loadidx(cov.COV, "cov")
    if leak + nl + cl: raise RuntimeError(f"source leakage redzone={leak} ngs={nl} coverage={cl}")
    covrows = cov.attach(base_rows, ci, ni)
    rows = attach(covrows, idx)
    c22 = [r for r in covrows if r["season"] == 2022]; cp,_ = cov.select(c22,"spread","coverage")
    b22 = [r for r in base_rows if r["season"] == 2022]; tp,_ = base.select_params(b22,"total")
    games = rat.fetch_games(); rmap = rat.rating_maps(games,qbp.RATING["elo_k"],qbp.RATING["elo_hfa"],qbp.RATING["offseason_regression"],qbp.RATING["margin_k"],qbp.RATING["margin_hfa"])
    rated = rat.attach(rows, rmap)
    r22 = [r for r in rated if r["season"] == 2022]
    selected = {
        "spread": select(r22,"spread",cp["team_k"],cp["feature_k"]),
        "total": select(r22,"total",tp["k"],None),
    }
    result_variants = {}
    for kind in ["spread","total"]:
        best, top = selected[kind]
        folds={}; ref_all=[]; cand_all=[]
        for year in YEARS:
            tr=[r for r in rated if r["season"]<year]; te=[r for r in rated if r["season"]==year]
            if kind=="spread":
                rf=fit(tr,"spread",cp["team_k"],qbp.RATING["lambda"],cp["feature_k"],None)
                rp=pred(te,"spread",cp["team_k"],rf,cp["feature_k"],None)
                cf=fit(tr,"spread",cp["team_k"],best["lambda"],cp["feature_k"],best["redzone_pseudo_plays"])
                cpred=pred(te,"spread",cp["team_k"],cf,cp["feature_k"],best["redzone_pseudo_plays"])
            else:
                rf=fit(tr,"total",tp["k"],tp["lambda"],None,None); rp=pred(te,"total",tp["k"],rf,None,None)
                cf=fit(tr,"total",tp["k"],best["lambda"],None,best["redzone_pseudo_plays"]); cpred=pred(te,"total",tp["k"],cf,None,best["redzone_pseudo_plays"])
            re=ae(te,rp,kind); ce=ae(te,cpred,kind); ref_all.extend(re.tolist()); cand_all.extend(ce.tolist())
            folds[str(year)]={"n":len(te),"reference_mae":round(float(np.mean(re)),4),"candidate_mae":round(float(np.mean(ce)),4),"candidate_minus_reference_mae":round(float(np.mean(ce)-np.mean(re)),4)}
        ref=np.asarray(ref_all); cand=np.asarray(cand_all); b=boot(ref-cand); seasons=sum(folds[str(y)]["candidate_minus_reference_mae"]<0 for y in YEARS)
        robust=bool(np.mean(cand)<np.mean(ref) and seasons>=2 and b["bootstrap_95_ci"][0]>0)
        result_variants[kind]={"selected_2022_only":best,"top_2022_candidates":top,"folds":folds,"aggregate":{"n":len(ref),"reference_mae":round(float(np.mean(ref)),4),"candidate_mae":round(float(np.mean(cand)),4),"candidate_minus_reference_mae":round(float(np.mean(cand)-np.mean(ref)),4),"seasons_improved":seasons,"paired_bootstrap_reference_minus_candidate":b},"robust_incremental_value":robust}
    result={"generated_at_utc":datetime.now(timezone.utc).isoformat(),"design":"Leakage-safe red-zone EPA/success family; parameters selected 2022 only; outer 2023-2025. Spread tested on canonical final architecture; totals on canonical core.","source_rows":nrows,"source_leakage_rows":leak,"variants":result_variants,"production_promotion_allowed":False,"week6_frozen_snapshot_may_be_rewritten":False,"website_publish_allowed":False,"recommendation_release_allowed":False,"release_state":"SHADOW_CANDIDATE_EXISTS" if any(v["robust_incremental_value"] for v in result_variants.values()) else "HOLD_NO_ROBUST_INCREMENT"}
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:v["aggregate"]|{"robust_incremental_value":v["robust_incremental_value"]} for k,v in result_variants.items()},indent=2))


if __name__ == "__main__":
    main()
