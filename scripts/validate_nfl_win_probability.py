#!/usr/bin/env python3
"""Validate a leakage-safe NFL win-probability mapping from canonical home margin.

The spread model remains unchanged. This script only tests whether the canonical
home-margin projection can be converted into a calibrated home-win probability
for presentation/research.

Validation design:
- Source: final canonical OOS predictions for 2023-2025.
- 2024 test fold: fit logistic calibration using 2023 only.
- 2025 test fold: fit logistic calibration using 2023-2024 only.
- If both folds clear fixed quality gates, fit the 2026 presentation mapping on
  all 2023-2025 OOS observations (all are historical as of 2026 Week 6).
- No market line enters fitting.
- No wager threshold, confidence tier, or recommendation is authorized.
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SOURCE = Path("nfl_data/calibration/final_architecture_oos_predictions_2023_2025.csv")
OUT = Path("nfl_data/validation/win_probability_calibration.json")
WEEK6 = Path("nfl_data/research_exports/week6_cfb_style_research_latest.csv")
WEEK6_OUT = Path("nfl_data/validation/week6_win_probability_research.csv")

EPS = 1e-9


def sigmoid(z):
    z = np.asarray(z, dtype=float)
    out = np.empty_like(z)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    ez = np.exp(z[~pos])
    out[~pos] = ez / (1.0 + ez)
    return out


def fit_logistic(x, y, ridge=1e-4, max_iter=100):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    X = np.column_stack([np.ones(len(x)), x])
    beta = np.zeros(2, dtype=float)
    for _ in range(max_iter):
        p = np.clip(sigmoid(X @ beta), 1e-7, 1 - 1e-7)
        w = p * (1 - p)
        H = X.T @ (X * w[:, None]) + ridge * np.diag([0.0, 1.0])
        g = X.T @ (y - p) - ridge * np.array([0.0, beta[1]])
        step = np.linalg.solve(H, g)
        beta += step
        if np.max(np.abs(step)) < 1e-10:
            break
    return beta


def metrics(y, p):
    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    pred = (p >= 0.5).astype(float)
    brier = float(np.mean((p - y) ** 2))
    logloss = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    accuracy = float(np.mean(pred == y))
    # Equal-width calibration bins; ECE weighted by bin sample size.
    bins = []
    ece = 0.0
    for lo in np.arange(0.0, 1.0, 0.1):
        hi = lo + 0.1
        mask = (p >= lo) & (p < hi if hi < 1.0 else p <= hi)
        n = int(mask.sum())
        if not n:
            continue
        mean_p = float(np.mean(p[mask]))
        win_rate = float(np.mean(y[mask]))
        ece += n / len(y) * abs(mean_p - win_rate)
        bins.append({
            "lo": round(float(lo), 1), "hi": round(float(hi), 1), "n": n,
            "mean_probability": round(mean_p, 4), "observed_home_win_rate": round(win_rate, 4),
        })
    return {
        "n": len(y),
        "brier": round(brier, 6),
        "log_loss": round(logloss, 6),
        "accuracy_at_50pct": round(accuracy, 4),
        "ece_10bin": round(float(ece), 6),
        "calibration_bins": bins,
    }


def load_rows():
    rows = list(csv.DictReader(SOURCE.open(encoding="utf-8", newline="")))
    for r in rows:
        r["season"] = int(r["season"])
        r["pred_home_margin"] = float(r["pred_home_margin"])
        margin = float(r["actual_home_margin"])
        # Ties are excluded from binary calibration. NFL ties are rare and a two-way
        # win probability cannot represent them without a third outcome state.
        r["home_win"] = None if abs(margin) < 1e-12 else (1.0 if margin > 0 else 0.0)
    return [r for r in rows if r["home_win"] is not None]


def fold(rows, train_years, test_year):
    train = [r for r in rows if r["season"] in train_years]
    test = [r for r in rows if r["season"] == test_year]
    beta = fit_logistic([r["pred_home_margin"] for r in train], [r["home_win"] for r in train])
    p = sigmoid(np.array([r["pred_home_margin"] for r in test]) * beta[1] + beta[0])
    m = metrics([r["home_win"] for r in test], p)
    baseline_p = np.full(len(test), np.mean([r["home_win"] for r in train]), dtype=float)
    base = metrics([r["home_win"] for r in test], baseline_p)
    fixed = metrics([r["home_win"] for r in test], np.full(len(test), 0.5))
    m["train_years"] = train_years
    m["test_year"] = test_year
    m["train_n"] = len(train)
    m["intercept"] = round(float(beta[0]), 8)
    m["margin_slope"] = round(float(beta[1]), 8)
    m["training_base_rate"] = round(float(np.mean([r["home_win"] for r in train])), 4)
    m["prior_base_rate_baseline"] = base
    m["fifty_fifty_baseline"] = fixed
    m["beats_50_50_brier"] = m["brier"] < fixed["brier"]
    m["beats_50_50_logloss"] = m["log_loss"] < fixed["log_loss"]
    m["beats_prior_base_rate_brier"] = m["brier"] < base["brier"]
    m["positive_margin_slope"] = beta[1] > 0
    return m


def probability(beta, margin):
    return float(sigmoid(np.array([beta[0] + beta[1] * float(margin)]))[0])


def main():
    rows = load_rows()
    folds = [fold(rows, [2023], 2024), fold(rows, [2023, 2024], 2025)]

    # Fixed, intentionally conservative presentation gate chosen before seeing these
    # fold outputs. This is a display/research gate, not a betting release gate.
    gates = {
        "each_fold_beats_50_50_brier": all(f["beats_50_50_brier"] for f in folds),
        "each_fold_beats_50_50_logloss": all(f["beats_50_50_logloss"] for f in folds),
        "each_fold_beats_prior_base_rate_brier": all(f["beats_prior_base_rate_brier"] for f in folds),
        "each_fold_positive_slope": all(f["positive_margin_slope"] for f in folds),
        "each_fold_ece_le_0_10": all(f["ece_10bin"] <= 0.10 for f in folds),
        "each_fold_brier_le_0_245": all(f["brier"] <= 0.245 for f in folds),
    }
    eligible = all(gates.values())

    beta_2026 = fit_logistic([r["pred_home_margin"] for r in rows], [r["home_win"] for r in rows])
    current = []
    if WEEK6.exists():
        for r in csv.DictReader(WEEK6.open(encoding="utf-8", newline="")):
            margin = float(r["canonical_home_margin"])
            p_home = probability(beta_2026, margin)
            hard_qb = str(r.get("hard_qb_state_break", "")).lower() == "true"
            current.append({
                "game_id": r["game_id"],
                "away_team": r["away_team"],
                "home_team": r["home_team"],
                "canonical_home_margin": round(margin, 4),
                "home_win_probability": round(p_home, 4),
                "away_win_probability": round(1.0 - p_home, 4),
                "hard_qb_state_break": hard_qb,
                "spread_reliability_tier": r.get("spread_reliability_tier", ""),
                "display_eligible": eligible,
                "display_caveat": "OUT_OF_DISTRIBUTION_QB_BREAK" if hard_qb else "CANONICAL_MARGIN_CALIBRATION",
            })

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Research/presentation calibration from canonical projected home margin to home-win probability.",
        "source": str(SOURCE),
        "source_games_excluding_ties": len(rows),
        "method": "Two-parameter logistic calibration of canonical home margin; walk-forward validation by season.",
        "market_used_in_fit": False,
        "validation_folds": folds,
        "predeclared_display_gates": gates,
        "display_probability_eligible": eligible,
        "production_2026_mapping": {
            "fit_years": [2023, 2024, 2025],
            "n": len(rows),
            "intercept": round(float(beta_2026[0]), 8),
            "margin_slope": round(float(beta_2026[1]), 8),
            "policy": "Presentation/research probability only. Does not authorize a wager, confidence tier, moneyline edge, or sizing rule.",
        },
        "week6_rows": current,
        "recommendation_release_allowed": False,
        "moneyline_edge_release_allowed": False,
        "website_publish_allowed": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if current:
        with WEEK6_OUT.open("w", encoding="utf-8", newline="") as fobj:
            fields = list(current[0])
            w = csv.DictWriter(fobj, fieldnames=fields)
            w.writeheader(); w.writerows(current)

    print(json.dumps({
        "eligible": eligible,
        "gates": gates,
        "folds": [{k: f[k] for k in ["test_year", "n", "brier", "log_loss", "ece_10bin", "accuracy_at_50pct", "margin_slope"]} for f in folds],
        "mapping_2026": payload["production_2026_mapping"],
        "week6_games": len(current),
    }, indent=2))


if __name__ == "__main__":
    main()
