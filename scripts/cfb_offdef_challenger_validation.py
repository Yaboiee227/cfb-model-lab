#!/usr/bin/env python3
"""Leakage-safe validation for a score-decomposition CFB challenger.

This challenger is research only. It does not modify the canonical model.

Architecture
------------
Each completed game contributes two scoring observations. Team offense and
opponent defensive allowance are estimated separately with ridge shrinkage:

  home_points = intercept + home_scoring_advantage + offense(home) + allowance(away)
  away_points = intercept + offense(away) + allowance(home)

The resulting score pair implies margin and total. Team state resets at the
start of every season. Hyperparameters are selected only on 2024 walk-forward
results, then frozen unchanged for the untouched 2025 holdout and pre-Week-8
2026 confirmation period.

No market, external rating, target-game result, or post-kickoff information is
used to construct a prediction.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

import cfb_shadow_engine as engine
from run_cfb_shadow_week8 import extract_grouped_team_ids

engine.extract_team_ids = extract_grouped_team_ids

FOUNDATION_PARAMS = {"alpha": 2.5, "halfLifeDays": 56, "minTeamAppearances": 4}
GRID_ALPHA = (0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0)
GRID_HALF_LIFE = (28, 42, 56, 84, 112, None)
GRID_MIN_APPS = (2, 3, 4)
MIN_TRAINING_GAMES = 80
MIN_TEST_GAMES = 15


def week_start(dt: datetime) -> datetime:
    d = dt.astimezone(timezone.utc)
    return (d - timedelta(days=d.weekday(), hours=d.hour, minutes=d.minute, seconds=d.second, microseconds=d.microsecond))


def ridge_solve(X: np.ndarray, y: np.ndarray, weights: np.ndarray, penalty: np.ndarray) -> np.ndarray:
    root_w = np.sqrt(weights)
    Xw = X * root_w[:, None]
    yw = y * root_w
    return np.linalg.solve(Xw.T @ Xw + np.diag(penalty), Xw.T @ yw)


def fit_offdef(games: list[engine.Game], as_of: datetime, alpha: float, half_life_days: int | None, min_apps: int) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for g in games:
        counts[g.home] += 1
        counts[g.away] += 1
    core = [g for g in games if counts[g.home] >= min_apps and counts[g.away] >= min_apps]
    if len(core) < 20:
        raise ValueError("insufficient eligible training games")

    teams = sorted({g.home for g in core} | {g.away for g in core})
    idx = {team: i for i, team in enumerate(teams)}
    n = len(teams)
    # intercept, home-scoring advantage, offense[n], defensive-allowance[n]
    X = np.zeros((2 * len(core), 2 + 2 * n), dtype=float)
    y = np.zeros(2 * len(core), dtype=float)
    weights = np.zeros(2 * len(core), dtype=float)

    for i, g in enumerate(core):
        w = engine.recency_weight(g.kickoff, as_of, half_life_days)
        home_row = 2 * i
        away_row = home_row + 1

        X[home_row, 0] = 1.0
        X[home_row, 1] = 0.0 if g.neutral else 1.0
        X[home_row, 2 + idx[g.home]] = 1.0
        X[home_row, 2 + n + idx[g.away]] = 1.0
        y[home_row] = g.home_score
        weights[home_row] = w

        X[away_row, 0] = 1.0
        X[away_row, 2 + idx[g.away]] = 1.0
        X[away_row, 2 + n + idx[g.home]] = 1.0
        y[away_row] = g.away_score
        weights[away_row] = w

    penalty = np.full(2 + 2 * n, float(alpha), dtype=float)
    penalty[0] = 0.0
    penalty[1] = 0.0
    beta = ridge_solve(X, y, weights, penalty)
    return {
        "teams": teams,
        "idx": idx,
        "beta": beta,
        "eligibleTrainingGames": len(core),
        "alpha": float(alpha),
        "halfLifeDays": half_life_days,
        "minTeamAppearances": int(min_apps),
        "homeScoringAdvantage": float(beta[1]),
    }


def predict_offdef(model: dict[str, Any], away: str, home: str, neutral: bool) -> dict[str, float]:
    idx = model["idx"]
    if away not in idx or home not in idx:
        raise ValueError("team absent from eligible offdef training data")
    beta = model["beta"]
    n = len(model["teams"])
    base = float(beta[0])
    hsa = 0.0 if neutral else float(beta[1])
    home_pts = base + hsa + float(beta[2 + idx[home]]) + float(beta[2 + n + idx[away]])
    away_pts = base + float(beta[2 + idx[away]]) + float(beta[2 + n + idx[home]])
    home_pts = max(0.0, home_pts)
    away_pts = max(0.0, away_pts)
    return {
        "awayPoints": away_pts,
        "homePoints": home_pts,
        "homeMargin": home_pts - away_pts,
        "total": home_pts + away_pts,
    }


def metric(errors: list[float]) -> dict[str, Any]:
    if not errors:
        return {"games": 0, "mae": None, "rmse": None, "bias": None}
    e = np.asarray(errors, dtype=float)
    return {
        "games": int(len(e)),
        "mae": float(np.mean(np.abs(e))),
        "rmse": float(np.sqrt(np.mean(e ** 2))),
        "bias": float(np.mean(e)),
    }


def evaluate_params(games: list[engine.Game], alpha: float, half_life_days: int | None, min_apps: int) -> dict[str, Any]:
    grouped: dict[datetime, list[engine.Game]] = defaultdict(list)
    for g in games:
        grouped[week_start(g.kickoff)].append(g)
    weeks = sorted(grouped)

    off_margin_errors: list[float] = []
    off_total_errors: list[float] = []
    base_margin_errors: list[float] = []
    base_total_errors: list[float] = []
    folds = []
    potential = 0

    for ws in weeks:
        training = [g for g in games if g.kickoff < ws]
        test = grouped[ws]
        if len(training) < MIN_TRAINING_GAMES or len(test) < MIN_TEST_GAMES:
            continue
        try:
            challenger = fit_offdef(training, ws, alpha, half_life_days, min_apps)
            baseline = engine.fit_model(
                training,
                ws,
                alpha=FOUNDATION_PARAMS["alpha"],
                half_life_days=FOUNDATION_PARAMS["halfLifeDays"],
                min_team_appearances=FOUNDATION_PARAMS["minTeamAppearances"],
                fixed_hfa=None,
            )
        except Exception:
            continue

        fold_off_m: list[float] = []
        fold_off_t: list[float] = []
        fold_base_m: list[float] = []
        fold_base_t: list[float] = []
        potential += len(test)

        for g in test:
            try:
                off = predict_offdef(challenger, g.away, g.home, g.neutral)
                base = engine.predict(baseline, g.away, g.home, g.neutral)
            except Exception:
                continue
            actual_margin = float(g.home_score - g.away_score)
            actual_total = float(g.home_score + g.away_score)
            fold_off_m.append(float(off["homeMargin"]) - actual_margin)
            fold_off_t.append(float(off["total"]) - actual_total)
            fold_base_m.append(float(base["projectedMarginHome"]) - actual_margin)
            fold_base_t.append(float(base["projectedTotal"]) - actual_total)

        if not fold_off_m:
            continue
        off_margin_errors.extend(fold_off_m)
        off_total_errors.extend(fold_off_t)
        base_margin_errors.extend(fold_base_m)
        base_total_errors.extend(fold_base_t)
        folds.append({
            "weekStart": engine.iso(ws),
            "trainingGames": len(training),
            "testGames": len(test),
            "pairedGames": len(fold_off_m),
            "challengerMargin": metric(fold_off_m),
            "foundationMargin": metric(fold_base_m),
            "challengerTotal": metric(fold_off_t),
            "foundationTotal": metric(fold_base_t),
        })

    off_m = metric(off_margin_errors)
    off_t = metric(off_total_errors)
    base_m = metric(base_margin_errors)
    base_t = metric(base_total_errors)
    return {
        "params": {"alpha": alpha, "halfLifeDays": half_life_days, "minTeamAppearances": min_apps},
        "folds": folds,
        "potentialGames": potential,
        "pairedGames": len(off_margin_errors),
        "coverage": (len(off_margin_errors) / potential) if potential else 0.0,
        "challengerMargin": off_m,
        "foundationMargin": base_m,
        "challengerTotal": off_t,
        "foundationTotal": base_t,
        "marginMaeDeltaVsFoundation": None if not off_margin_errors else float(off_m["mae"] - base_m["mae"]),
        "totalMaeDeltaVsFoundation": None if not off_total_errors else float(off_t["mae"] - base_t["mae"]),
    }


def selection_key(result: dict[str, Any]) -> tuple[float, float, float]:
    # Select on 2024 only. Primary objective is joint score accuracy; coverage is a tie-breaker.
    m = result["challengerMargin"]["mae"]
    t = result["challengerTotal"]["mae"]
    if m is None or t is None:
        return (1e9, 1e9, 1e9)
    return (float(m) + float(t), float(m), -float(result["coverage"]))


def load_season(season: int, end: datetime) -> list[engine.Game]:
    start = datetime(season, 8, 15, tzinfo=timezone.utc)
    return engine.fetch_completed_games(start, end)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default="2026-10-20T00:00:00-04:00")
    ap.add_argument("--output", default="cfb/validation/week-08-offdef-challenger-validation.json")
    args = ap.parse_args()

    cutoff_2026 = engine.parse_dt(args.as_of)
    games_2024 = load_season(2024, datetime(2025, 1, 15, tzinfo=timezone.utc))
    games_2025 = load_season(2025, datetime(2026, 1, 15, tzinfo=timezone.utc))
    games_2026 = load_season(2026, cutoff_2026)

    candidates = []
    for alpha in GRID_ALPHA:
        for half_life in GRID_HALF_LIFE:
            for min_apps in GRID_MIN_APPS:
                result = evaluate_params(games_2024, alpha, half_life, min_apps)
                if result["pairedGames"]:
                    candidates.append(result)
    if not candidates:
        raise RuntimeError("no valid 2024 development candidates")
    best = min(candidates, key=selection_key)
    locked = best["params"]

    holdout = evaluate_params(games_2025, float(locked["alpha"]), locked["halfLifeDays"], int(locked["minTeamAppearances"]))
    confirmation = evaluate_params(games_2026, float(locked["alpha"]), locked["halfLifeDays"], int(locked["minTeamAppearances"]))

    # Evidence classification is deliberately conservative. This can authorize only
    # further prospective shadow testing, never canonical promotion.
    hold_m = holdout["marginMaeDeltaVsFoundation"]
    hold_t = holdout["totalMaeDeltaVsFoundation"]
    conf_m = confirmation["marginMaeDeltaVsFoundation"]
    conf_t = confirmation["totalMaeDeltaVsFoundation"]
    no_material_degradation = all(x is not None and x <= 0.25 for x in (hold_m, hold_t, conf_m, conf_t))
    meaningful_gain = any(x is not None and x <= -0.50 for x in (hold_m, hold_t, conf_m, conf_t))
    coverage_ok = holdout["coverage"] >= 0.80 and confirmation["coverage"] >= 0.80
    shadow_eligible = bool(no_material_degradation and meaningful_gain and coverage_ok)

    out = {
        "schemaVersion": 1,
        "league": "cfb",
        "season": 2026,
        "role": "OFFENSE_DEFENSE_SCORE_DECOMPOSITION_CHALLENGER_VALIDATION",
        "canonicalInfluence": False,
        "canonicalPromotionAuthorized": False,
        "asOf": engine.iso(cutoff_2026),
        "architecture": {
            "description": "Separate recency-weighted ridge offense and defensive-allowance team effects projected into team points, then margin and total.",
            "seasonTeamStateReset": True,
            "marketDataUsed": False,
            "externalRatingsUsed": False,
            "postKickoffTargetDataUsed": False,
        },
        "foundationComparator": {
            "model": "cfb_shadow_engine score-margin foundation comparator",
            "params": FOUNDATION_PARAMS,
            "note": "Comparator is refit only on games prior to each test week; no test-week outcome enters either model.",
        },
        "selection": {
            "developmentSeason": 2024,
            "candidateCount": len(candidates),
            "objective": "minimize challenger margin MAE + total MAE on 2024 weekly walk-forward only",
            "lockedParams": locked,
            "developmentBest": best,
        },
        "holdout2025": holdout,
        "confirmation2026PreWeek8": confirmation,
        "decision": {
            "prospectiveShadowEligible": shadow_eligible,
            "canonicalPromotionAuthorized": False,
            "rule": "Require >=80% paired coverage on 2025 and pre-Week8 2026, no MAE degradation >0.25 in either target on either unseen period, and >=0.50 MAE gain in at least one unseen target/period. Eligibility authorizes prospective shadow testing only.",
            "nextStep": "If eligible, freeze unchanged prospective projections for remaining Week 8 games alongside the existing foundation. If not eligible, retain as rejected research evidence and continue challenger development.",
        },
        "warning": "Tuesday Week 8 outcomes are not used anywhere in parameter selection or validation. This artifact cannot promote or rewrite the canonical model.",
    }

    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "lockedParams": locked,
        "development": {"margin": best["challengerMargin"], "total": best["challengerTotal"], "coverage": best["coverage"]},
        "holdout2025": {"marginDelta": hold_m, "totalDelta": hold_t, "coverage": holdout["coverage"]},
        "confirmation2026PreWeek8": {"marginDelta": conf_m, "totalDelta": conf_t, "coverage": confirmation["coverage"]},
        "prospectiveShadowEligible": shadow_eligible,
    }, indent=2))


if __name__ == "__main__":
    main()
