#!/usr/bin/env python3
"""Walk-forward market-anchored NFL spread residual research model v1.

This is a development-only test. The market spread is treated as the baseline
forecast and the football model is allowed to predict only a residual adjustment
around that baseline. Every game's residual model is fit only on earlier weeks.

Inputs come from the already leakage-safe opponent-adjusted walk-forward file.
Outputs remain HOLD / RESEARCH_VALIDATION_ONLY and cannot authorize publication.
"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

INPUT = Path("nfl_data/validation/opponent_adjusted_walkforward_2023_2025.csv")
OUT_DIR = Path("nfl_data/validation")
OUT_CSV = OUT_DIR / "market_residual_v1_walkforward_2023_2025.csv"
OUT_QA = OUT_DIR / "market_residual_v1_qa.json"
MIN_PRIOR_GAMES = 100
RIDGE_LAMBDA = 12.0
EDGE_THRESHOLDS = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0]


def f(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def mean(xs):
    return None if not xs else sum(xs) / len(xs)


def std(xs):
    if len(xs) < 2:
        return None
    m = mean(xs)
    v = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(v) if v > 0 else None


def corr(xs, ys):
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx, my = mean(xs), mean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    return None if not den else sum(a*b for a,b in zip(dx,dy)) / den


def solve_linear(a, b):
    # Small dense Gaussian elimination with partial pivoting.
    n = len(b)
    m = [list(map(float, a[i])) + [float(b[i])] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            return None
        m[col], m[pivot] = m[pivot], m[col]
        p = m[col][col]
        m[col] = [v / p for v in m[col]]
        for r in range(n):
            if r == col:
                continue
            factor = m[r][col]
            if factor:
                m[r] = [rv - factor * cv for rv, cv in zip(m[r], m[col])]
    return [m[i][-1] for i in range(n)]


def fit_ridge(prior):
    net = [r["net_rating_diff"] for r in prior]
    spr = [r["spread_line"] for r in prior]
    y = [r["actual_residual"] for r in prior]
    m_net, s_net = mean(net), std(net)
    m_spr, s_spr = mean(spr), std(spr)
    if s_net is None or s_spr is None:
        return None

    # X = intercept + standardized net rating difference + standardized market spread.
    xrows = [[1.0, (r["net_rating_diff"]-m_net)/s_net, (r["spread_line"]-m_spr)/s_spr] for r in prior]
    p = 3
    xtx = [[0.0]*p for _ in range(p)]
    xty = [0.0]*p
    for x, target in zip(xrows, y):
        for i in range(p):
            xty[i] += x[i] * target
            for j in range(p):
                xtx[i][j] += x[i] * x[j]
    # Do not penalize intercept; shrink signal coefficients toward zero.
    xtx[1][1] += RIDGE_LAMBDA
    xtx[2][2] += RIDGE_LAMBDA
    beta = solve_linear(xtx, xty)
    if beta is None:
        return None
    return {
        "beta": beta,
        "net_mean": m_net,
        "net_std": s_net,
        "spread_mean": m_spr,
        "spread_std": s_spr,
    }


def predict(fit, net, spread):
    b0, b1, b2 = fit["beta"]
    zn = (net - fit["net_mean"]) / fit["net_std"]
    zs = (spread - fit["spread_mean"]) / fit["spread_std"]
    return b0 + b1*zn + b2*zs


def ats_result(actual_margin, spread, edge):
    delta = actual_margin - spread
    if abs(delta) < 1e-9:
        return "PUSH"
    if edge > 0:
        return "WIN" if delta > 0 else "LOSS"
    if edge < 0:
        return "WIN" if delta < 0 else "LOSS"
    return "NO_PLAY"


def summarize(rows):
    if not rows:
        return {"games": 0}
    actual_margin = [r["actual_margin"] for r in rows]
    market = [r["spread_line"] for r in rows]
    model = [r["market_residual_model_margin"] for r in rows]
    pred_resid = [r["predicted_market_residual"] for r in rows]
    actual_resid = [r["actual_residual"] for r in rows]
    out = {
        "games": len(rows),
        "market_mae": sum(abs(a-m) for a,m in zip(actual_margin, market))/len(rows),
        "residual_model_mae": sum(abs(a-m) for a,m in zip(actual_margin, model))/len(rows),
        "market_rmse": math.sqrt(sum((a-m)**2 for a,m in zip(actual_margin, market))/len(rows)),
        "residual_model_rmse": math.sqrt(sum((a-m)**2 for a,m in zip(actual_margin, model))/len(rows)),
        "predicted_vs_actual_residual_correlation": corr(pred_resid, actual_resid),
        "mean_abs_predicted_edge": sum(abs(x) for x in pred_resid)/len(rows),
    }
    ats = {}
    for threshold in EDGE_THRESHOLDS:
        picks = [r for r in rows if abs(r["predicted_market_residual"]) >= threshold]
        wins = sum(r["ats_result"] == "WIN" for r in picks)
        losses = sum(r["ats_result"] == "LOSS" for r in picks)
        pushes = sum(r["ats_result"] == "PUSH" for r in picks)
        graded = wins + losses
        units = wins - 1.1*losses
        ats[str(threshold)] = {
            "bets": len(picks),
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate_ex_push": wins/graded if graded else None,
            "units_at_minus_110": units,
            "roi_at_minus_110": units/graded if graded else None,
        }
    out["ats_by_edge_threshold"] = ats
    return out


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not INPUT.exists():
        raise RuntimeError(f"Missing input {INPUT}")
    with INPUT.open(encoding="utf-8", newline="") as fobj:
        source = list(csv.DictReader(fobj))

    rows = []
    for r in source:
        season = int(float(r["season"]))
        week = int(float(r["week"]))
        net = f(r.get("net_rating_diff"))
        actual = f(r.get("actual_margin"))
        spread = f(r.get("spread_line"))
        if net is None or actual is None or spread is None:
            continue
        rows.append({
            "season": season,
            "week": week,
            "gameday": r.get("gameday", ""),
            "game_id": r.get("game_id", ""),
            "home_team": r.get("home_team", ""),
            "away_team": r.get("away_team", ""),
            "net_rating_diff": net,
            "actual_margin": actual,
            "spread_line": spread,
            "actual_residual": actual - spread,
        })
    rows.sort(key=lambda r: (r["season"], r["week"], r["gameday"], r["game_id"]))

    validated = []
    for row in rows:
        prior = [r for r in rows if (r["season"], r["week"]) < (row["season"], row["week"])]
        if len(prior) < MIN_PRIOR_GAMES:
            continue
        fit = fit_ridge(prior)
        if fit is None:
            continue
        residual = predict(fit, row["net_rating_diff"], row["spread_line"])
        model_margin = row["spread_line"] + residual
        out = dict(row)
        out.update({
            "prior_games": len(prior),
            "ridge_lambda": RIDGE_LAMBDA,
            "predicted_market_residual": residual,
            "market_residual_model_margin": model_margin,
            "ats_result": ats_result(row["actual_margin"], row["spread_line"], residual),
            "release_state": "HOLD",
            "model_use": "RESEARCH_VALIDATION_ONLY",
        })
        validated.append(out)

    if not validated:
        raise RuntimeError("No residual validation rows produced")

    with OUT_CSV.open("w", encoding="utf-8", newline="") as fobj:
        writer = csv.DictWriter(fobj, fieldnames=list(validated[0].keys()))
        writer.writeheader(); writer.writerows(validated)

    seasons = sorted({r["season"] for r in validated})
    qa = {
        "validation_name": "NFL market-anchored spread residual v1",
        "input": str(INPUT),
        "validated_games": len(validated),
        "minimum_prior_games": MIN_PRIOR_GAMES,
        "ridge_lambda": RIDGE_LAMBDA,
        "features": ["opponent_adjusted_net_rating_difference", "market_spread"],
        "target": "actual_home_margin - historical_market_spread",
        "overall": summarize(validated),
        "by_season": {str(s): summarize([r for r in validated if r["season"] == s]) for s in seasons},
        "release_state": "HOLD",
        "model_use": "RESEARCH_VALIDATION_ONLY",
        "notes": [
            "The historical market spread is the baseline forecast; the football model predicts only a residual adjustment.",
            "Every residual fit uses only earlier season/week rows; same-week games are never used to fit one another.",
            "Ridge lambda is a candidate research setting, not a selected production hyperparameter.",
            "Historical nflverse spread_line is not treated as guaranteed executable timestamped pricing.",
            "This test does not include PBP success/explosiveness, QB/personnel, injuries, weather, rest/travel, or price/CLV layers.",
            "No result authorizes website publication or wager release."
        ],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    OUT_QA.write_text(json.dumps(qa, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(qa, indent=2))
    print(f"Wrote {OUT_CSV}")
    print(f"Wrote {OUT_QA}")


if __name__ == "__main__":
    main()
