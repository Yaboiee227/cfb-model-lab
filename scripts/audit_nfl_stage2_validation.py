#!/usr/bin/env python3
"""Consolidate the NFL Stage 2 historical/walk-forward validation evidence.

This is an audit/reporting layer. It does not refit or retune the model.
Source predictions are the frozen final canonical architecture's outer OOS rows
for 2023-2025. Market references are benchmark fields only and are not treated
as executable prices or proof of CLV/ROI.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PRED = Path("nfl_data/calibration/final_architecture_oos_predictions_2023_2025.csv")
WINPROB = Path("nfl_data/validation/win_probability_calibration.json")
OUT_JSON = Path("nfl_data/validation/stage2_validation_audit.json")
OUT_MD = Path("nfl_data/validation/STAGE2_VALIDATION_AUDIT.md")
YEARS = [2023, 2024, 2025]
THRESHOLDS = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]


def f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def wilson(wins: int, n: int, z: float = 1.959963984540054):
    if n <= 0:
        return [None, None]
    p = wins / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def error_summary(rows, pred_key, actual_key):
    errs = []
    for r in rows:
        p, a = f(r[pred_key]), f(r[actual_key])
        if p is not None and a is not None:
            errs.append(p - a)
    ae = [abs(x) for x in errs]
    return {
        "n": len(errs),
        "mae": round(sum(ae) / len(ae), 4),
        "rmse": round(math.sqrt(sum(x * x for x in errs) / len(errs)), 4),
        "bias_pred_minus_actual": round(sum(errs) / len(errs), 4),
    }


def market_error(rows, kind):
    errs = []
    for r in rows:
        if kind == "spread":
            line = f(r.get("market_home_spread_reference"))
            actual = f(r.get("actual_home_margin"))
            if line is None or actual is None:
                continue
            implied_home_margin = -line
            errs.append(implied_home_margin - actual)
        else:
            line = f(r.get("market_total_reference"))
            actual = f(r.get("actual_total"))
            if line is None or actual is None:
                continue
            errs.append(line - actual)
    if not errs:
        return {"n": 0, "mae": None, "rmse": None, "bias_reference_minus_actual": None}
    return {
        "n": len(errs),
        "mae": round(sum(abs(x) for x in errs) / len(errs), 4),
        "rmse": round(math.sqrt(sum(x * x for x in errs) / len(errs)), 4),
        "bias_reference_minus_actual": round(sum(errs) / len(errs), 4),
    }


def su_record(rows):
    w = l = ties = no_pick = 0
    by_year = {}
    for y in YEARS:
        yy = [r for r in rows if int(r["season"]) == y]
        yw = yl = yt = yn = 0
        for r in yy:
            p, a = f(r["pred_home_margin"]), f(r["actual_home_margin"])
            if p is None or a is None:
                continue
            if abs(a) < 1e-12:
                yt += 1
                continue
            if abs(p) < 1e-12:
                yn += 1
                continue
            if (p > 0) == (a > 0):
                yw += 1
            else:
                yl += 1
        decided = yw + yl
        by_year[str(y)] = {
            "wins": yw, "losses": yl, "actual_ties": yt, "model_pickems": yn,
            "accuracy": None if not decided else round(yw / decided, 4),
            "wilson_95": wilson(yw, decided),
        }
        w += yw; l += yl; ties += yt; no_pick += yn
    n = w + l
    return {
        "wins": w, "losses": l, "actual_ties": ties, "model_pickems": no_pick,
        "accuracy": None if not n else round(w / n, 4),
        "wilson_95": wilson(w, n),
        "by_season": by_year,
    }


def benchmark_record(rows, kind, threshold):
    wins = losses = pushes = aligned = 0
    by_year = defaultdict(lambda: {"wins": 0, "losses": 0, "pushes": 0, "aligned": 0})
    for r in rows:
        y = str(int(r["season"]))
        if kind == "spread":
            pred = f(r.get("pred_home_margin"))
            line = f(r.get("market_home_spread_reference"))
            actual = f(r.get("actual_home_margin"))
            if None in (pred, line, actual):
                continue
            edge = pred + line
            result = actual + line
        else:
            pred = f(r.get("pred_total"))
            line = f(r.get("market_total_reference"))
            actual = f(r.get("actual_total"))
            if None in (pred, line, actual):
                continue
            edge = pred - line
            result = actual - line
        if abs(edge) < threshold or abs(edge) < 1e-12:
            aligned += 1
            by_year[y]["aligned"] += 1
            continue
        if abs(result) < 1e-12:
            pushes += 1
            by_year[y]["pushes"] += 1
        elif edge * result > 0:
            wins += 1
            by_year[y]["wins"] += 1
        else:
            losses += 1
            by_year[y]["losses"] += 1
    decided = wins + losses
    season_out = {}
    for y in YEARS:
        d = by_year[str(y)]
        n = d["wins"] + d["losses"]
        season_out[str(y)] = {
            **d,
            "win_rate": None if not n else round(d["wins"] / n, 4),
            "wilson_95": wilson(d["wins"], n),
        }
    return {
        "threshold_points": threshold,
        "wins": wins, "losses": losses, "pushes": pushes, "aligned_or_below_threshold": aligned,
        "decisions": decided,
        "win_rate": None if not decided else round(wins / decided, 4),
        "wilson_95": wilson(wins, decided),
        "by_season": season_out,
        "interpretation": "Historical market-benchmark directional grading only; not a released-bet record.",
    }


def load_winprob():
    if not WINPROB.exists():
        return {"status": "MISSING"}
    d = json.loads(WINPROB.read_text(encoding="utf-8"))
    folds = []
    for x in d.get("validation_folds", []):
        folds.append({
            "train_years": x.get("train_years"),
            "test_year": x.get("test_year"),
            "n": x.get("n"),
            "brier": x.get("brier"),
            "log_loss": x.get("log_loss"),
            "accuracy_at_50pct": x.get("accuracy_at_50pct"),
            "ece_10bin": x.get("ece_10bin"),
            "margin_slope": x.get("margin_slope"),
            "beats_50_50_brier": x.get("beats_50_50_brier"),
            "beats_50_50_logloss": x.get("beats_50_50_logloss"),
            "positive_margin_slope": x.get("positive_margin_slope"),
        })
    return {
        "status": "DISPLAY_VALIDATED_RESEARCH_ONLY" if d.get("display_probability_eligible") else "HOLD",
        "source_games_excluding_ties": d.get("source_games_excluding_ties"),
        "market_used_in_fit": d.get("market_used_in_fit"),
        "folds": folds,
        "moneyline_edge_release_allowed": d.get("moneyline_edge_release_allowed", False),
    }


def md_table(rows, columns):
    out = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(c, "")) for c in columns) + " |")
    return "\n".join(out)


def main():
    rows = list(csv.DictReader(PRED.open(encoding="utf-8", newline="")))
    if len(rows) != 816:
        raise RuntimeError(f"Expected 816 canonical OOS rows, found {len(rows)}")

    aggregate = {
        "spread": error_summary(rows, "pred_home_margin", "actual_home_margin"),
        "total": error_summary(rows, "pred_total", "actual_total"),
    }
    folds = {}
    for y in YEARS:
        yy = [r for r in rows if int(r["season"]) == y]
        folds[str(y)] = {
            "n": len(yy),
            "spread": error_summary(yy, "pred_home_margin", "actual_home_margin"),
            "total": error_summary(yy, "pred_total", "actual_total"),
            "straight_up": su_record(yy),
            "market_reference": {
                "spread": market_error(yy, "spread"),
                "total": market_error(yy, "total"),
            },
        }

    ats = {str(t): benchmark_record(rows, "spread", t) for t in THRESHOLDS}
    totals = {str(t): benchmark_record(rows, "total", t) for t in THRESHOLDS}
    wp = load_winprob()

    market = {"spread": market_error(rows, "spread"), "total": market_error(rows, "total")}

    leakage_controls = {
        "outer_walk_forward": "2023 trained on prior seasons; 2024 trained on prior seasons; 2025 trained on prior seasons.",
        "hyperparameter_policy": "Core/tuning operations use only training-era data; promoted rating dynamics were selected on 2022 only and frozen for 2023-2025.",
        "pregame_features": "Historical feature rows are constructed from prior completed games only. Current-game outcomes never enter their own features.",
        "preprocessing": "Median imputation and standardization are fit on training rows only and then applied to unseen rows.",
        "market_policy": "Market references are not canonical model features or tuning targets; used only after prediction for benchmark comparison.",
        "win_probability": "Probability calibration uses canonical OOS margin predictions; market moneylines are not used in fitting.",
    }

    clv = {
        "status": "NOT_CLAIMED",
        "reason": "A genuine CLV statistic requires a timestamped executable price at the decision time plus a consistently defined closing price. Historical schedule market references can benchmark prediction accuracy/direction, but they do not prove the price the model could have executed. Prospective timestamped market captures will be used for future CLV-style analysis only when execution/timing is verifiable.",
        "historical_market_reference_allowed_for": ["MAE comparison", "directional ATS/total benchmark grading", "calibration research"],
        "historical_market_reference_not_allowed_for": ["ROI", "verified CLV", "claim of executable betting edge"],
    }

    warnings = [
        "816 unseen games is useful for error estimation, but still small for slicing many betting thresholds/features.",
        "Threshold records are multiple comparisons; an attractive historical bucket is not automatically a release rule.",
        "The market benchmark is more accurate than the independent model on aggregate MAE, which is a strong warning against claiming market-beating predictive superiority.",
        "Historical backtests are not a substitute for prospectively frozen weekly predictions.",
        "The totals model retains measurable negative bias; the tested sequential correction did not earn robust promotion.",
        "Win probability is validated for research/display, not for moneyline-edge or staking claims.",
    ]

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": 2,
        "stage_name": "Historical + walk-forward validation",
        "source": str(PRED),
        "canonical_oos_games": len(rows),
        "outer_test_seasons": YEARS,
        "aggregate_prediction_error": aggregate,
        "by_season": folds,
        "straight_up": su_record(rows),
        "market_reference_accuracy": market,
        "ats_market_benchmark_records": ats,
        "total_market_benchmark_records": totals,
        "win_probability_calibration": wp,
        "clv": clv,
        "leakage_controls": leakage_controls,
        "sample_and_overfit_warnings": warnings,
        "audit_verdict": "PASS_HISTORICAL_RESEARCH_VALIDATION__PROSPECTIVE_RELEASE_STILL_REQUIRED",
        "recommendation_release_allowed": False,
        "website_betting_signal_release_allowed": False,
    }

    OUT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    fold_rows = []
    for y in YEARS:
        z = folds[str(y)]
        fold_rows.append({
            "Season": y,
            "N": z["n"],
            "Spread MAE": z["spread"]["mae"],
            "Spread RMSE": z["spread"]["rmse"],
            "Total MAE": z["total"]["mae"],
            "Total RMSE": z["total"]["rmse"],
        })
    threshold_rows = []
    for t in THRESHOLDS:
        s, u = ats[str(t)], totals[str(t)]
        threshold_rows.append({
            "Threshold": t,
            "ATS W-L-P": f"{s['wins']}-{s['losses']}-{s['pushes']}",
            "ATS win%": s["win_rate"],
            "Total W-L-P": f"{u['wins']}-{u['losses']}-{u['pushes']}",
            "Total win%": u["win_rate"],
        })

    md = [
        "# NFL Stage 2 Validation Audit",
        "",
        f"**Verdict:** `{report['audit_verdict']}`  ",
        f"**Canonical unseen games:** {len(rows)} (2023-2025)  ",
        "**Release implication:** historical research validation passes; recommendation/betting-signal release remains HOLD pending prospective evidence.",
        "",
        "## Prediction error",
        "",
        f"- Spread MAE: **{aggregate['spread']['mae']}**; RMSE: **{aggregate['spread']['rmse']}**; bias: **{aggregate['spread']['bias_pred_minus_actual']}**.",
        f"- Total MAE: **{aggregate['total']['mae']}**; RMSE: **{aggregate['total']['rmse']}**; bias: **{aggregate['total']['bias_pred_minus_actual']}**.",
        f"- Market-reference spread MAE: **{market['spread']['mae']}**.",
        f"- Market-reference total MAE: **{market['total']['mae']}**.",
        "",
        md_table(fold_rows, ["Season", "N", "Spread MAE", "Spread RMSE", "Total MAE", "Total RMSE"]),
        "",
        "## Straight-up accuracy",
        "",
        f"Canonical winner direction: **{report['straight_up']['wins']}-{report['straight_up']['losses']}** (accuracy **{report['straight_up']['accuracy']}**, 95% Wilson {report['straight_up']['wilson_95']}). Actual ties/model pick'ems are excluded from decided accuracy.",
        "",
        "## Historical market-benchmark directional grading",
        "",
        "These are not released-bet records. They grade the model's direction versus the historical market reference at different disagreement thresholds.",
        "",
        md_table(threshold_rows, ["Threshold", "ATS W-L-P", "ATS win%", "Total W-L-P", "Total win%"]),
        "",
        "## Win probability",
        "",
        f"Status: **{wp.get('status')}**. Moneyline-edge release allowed: **{wp.get('moneyline_edge_release_allowed')}**.",
        "",
        "## CLV policy",
        "",
        f"**{clv['status']}** — {clv['reason']}",
        "",
        "## Leakage controls",
        "",
    ]
    md.extend([f"- **{k}:** {v}" for k, v in leakage_controls.items()])
    md.extend(["", "## Sample / overfitting warnings", ""])
    md.extend([f"- {x}" for x in warnings])
    md.extend([
        "",
        "## Stage 2 handoff",
        "",
        "> Historical validation is consolidated and passes as research validation, not as proof of betting edge. The canonical architecture has 816 outer-OOS games across 2023-2025, with market-independent spread/total predictions, season-by-season error metrics, SU grading, historical market-benchmark ATS/total direction records, and separately walk-forward-validated display win probability. Genuine historical CLV/ROI is not claimed because executable decision-time prices are not verified. Proceed to Stage 3 using timestamped personnel, weather/roof, rest/travel and market snapshots as context/execution gates without retroactively changing the frozen canonical Week 6 prediction.",
        "",
    ])
    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print(json.dumps({
        "verdict": report["audit_verdict"],
        "spread": aggregate["spread"],
        "total": aggregate["total"],
        "straight_up": report["straight_up"],
        "market_reference": market,
        "win_probability": wp.get("status"),
        "clv": clv["status"],
    }, indent=2))


if __name__ == "__main__":
    main()
