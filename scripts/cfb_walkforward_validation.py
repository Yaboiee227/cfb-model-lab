#!/usr/bin/env python3
"""Nested weekly walk-forward validation for CFB rebuild candidates.

Every feature row comes from cfb_rich_challenger.build_rows(), which freezes the
pregame feature state at the start of each football week. For each test week:
  1. use only rows from earlier weeks;
  2. reserve the immediately preceding week as an inner validation set;
  3. select bundle/ridge strength on that inner validation set;
  4. refit on all earlier rows;
  5. score the unseen test week.

This produces genuinely out-of-week predictions and does not use sportsbook,
SP+, Sagarin, RefMetrics, or current/future game results as model inputs.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

import cfb_rich_challenger as rich
import cfb_shadow_engine as engine
from run_cfb_shadow_week8 import estimate_historical_hfa, extract_grouped_team_ids

engine.extract_team_ids = extract_grouped_team_ids

MIN_TRAIN_ROWS = 70
MIN_INNER_VALID_ROWS = 10
MIN_TEST_ROWS = 10


def metric(pred: list[float], actual: list[float]) -> dict[str, float | int | None]:
    if not actual:
        return {"games": 0, "mae": None, "rmse": None, "bias": None}
    p = np.asarray(pred, dtype=float)
    y = np.asarray(actual, dtype=float)
    err = p - y
    return {
        "games": int(len(y)),
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "bias": float(np.mean(err)),
    }


def simple_predictions(rows: list[dict[str, Any]], target: str) -> list[float]:
    index = 0 if target == "margin" else 1
    return [float(r["x"][index]) for r in rows]


def target_values(rows: list[dict[str, Any]], target: str) -> list[float]:
    return [float(r[target]) for r in rows]


def choose_nested(
    prior_rows: list[dict[str, Any]],
    previous_week: str,
    target: str,
    bundles: dict[str, tuple[int, ...]],
):
    inner_valid = [r for r in prior_rows if r["weekStart"] == previous_week]
    inner_train = [r for r in prior_rows if r["weekStart"] != previous_week]
    if len(inner_train) < MIN_TRAIN_ROWS or len(inner_valid) < MIN_INNER_VALID_ROWS:
        return None
    best, candidates = rich.choose_model(inner_train, inner_valid, target, bundles)
    final = rich.ridge_fit(prior_rows, tuple(best["indices"]), target, float(best["alpha"]))
    return best, final, candidates


def evaluate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["weekStart"]].append(row)
    weeks = sorted(grouped)

    fold_outputs = []
    agg = {
        "simpleMarginPred": [], "richMarginPred": [], "marginActual": [],
        "simpleTotalPred": [], "richTotalPred": [], "totalActual": [],
    }

    for idx in range(2, len(weeks)):
        test_week = weeks[idx]
        previous_week = weeks[idx - 1]
        prior_weeks = set(weeks[:idx])
        prior = [r for r in rows if r["weekStart"] in prior_weeks]
        test = list(grouped[test_week])
        if len(test) < MIN_TEST_ROWS:
            continue

        margin_choice = choose_nested(prior, previous_week, "margin", rich.MARGIN_BUNDLES)
        total_choice = choose_nested(prior, previous_week, "total", rich.TOTAL_BUNDLES)
        if margin_choice is None or total_choice is None:
            continue
        best_margin, margin_model, _ = margin_choice
        best_total, total_model, _ = total_choice

        simple_margin = simple_predictions(test, "margin")
        simple_total = simple_predictions(test, "total")
        rich_margin = [float(x) for x in rich.ridge_predict(margin_model, test)]
        rich_total = [float(x) for x in rich.ridge_predict(total_model, test)]
        actual_margin = target_values(test, "margin")
        actual_total = target_values(test, "total")

        agg["simpleMarginPred"].extend(simple_margin)
        agg["richMarginPred"].extend(rich_margin)
        agg["marginActual"].extend(actual_margin)
        agg["simpleTotalPred"].extend(simple_total)
        agg["richTotalPred"].extend(rich_total)
        agg["totalActual"].extend(actual_total)

        fold_outputs.append({
            "testWeekStart": test_week,
            "previousWeekInnerValidation": previous_week,
            "trainRows": len(prior),
            "testRows": len(test),
            "selectedMargin": {"bundle": best_margin["name"], "alpha": best_margin["alpha"]},
            "selectedTotal": {"bundle": best_total["name"], "alpha": best_total["alpha"]},
            "simpleMargin": metric(simple_margin, actual_margin),
            "richMargin": metric(rich_margin, actual_margin),
            "simpleTotal": metric(simple_total, actual_total),
            "richTotal": metric(rich_total, actual_total),
        })

    simple_margin = metric(agg["simpleMarginPred"], agg["marginActual"])
    rich_margin = metric(agg["richMarginPred"], agg["marginActual"])
    simple_total = metric(agg["simpleTotalPred"], agg["totalActual"])
    rich_total = metric(agg["richTotalPred"], agg["totalActual"])

    margin_delta = None if rich_margin["mae"] is None else float(rich_margin["mae"]) - float(simple_margin["mae"])
    total_delta = None if rich_total["mae"] is None else float(rich_total["mae"]) - float(simple_total["mae"])
    prospective_gate = bool(
        margin_delta is not None and total_delta is not None
        and margin_delta <= 0.25
        and total_delta <= 0.25
        and (margin_delta <= -0.50 or total_delta <= -0.50)
        and len(fold_outputs) >= 2
    )

    return {
        "folds": fold_outputs,
        "aggregate": {
            "games": len(agg["marginActual"]),
            "simpleMargin": simple_margin,
            "richMargin": rich_margin,
            "simpleTotal": simple_total,
            "richTotal": rich_total,
            "richMinusSimpleMarginMae": margin_delta,
            "richMinusSimpleTotalMae": total_delta,
        },
        "prospectiveShadowGatePass": prospective_gate,
        "gateRule": "Across >=2 unseen weekly folds, rich challenger must improve at least one MAE by >=0.50 while degrading neither margin nor total MAE by >0.25. Passing only authorizes continued prospective shadowing, never canonical promotion.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default="2026-10-20T00:00:00-04:00")
    ap.add_argument("--start", default="2026-08-20T00:00:00-04:00")
    ap.add_argument("--shadow", default="cfb/shadow/week-08-tuesday.json")
    ap.add_argument("--reference", default="cfb/validation/week-07-canonical-reference.json")
    ap.add_argument("--output", default="cfb/validation/week-08-rebuild-walkforward.json")
    args = ap.parse_args()

    as_of = engine.parse_dt(args.as_of)
    start = engine.parse_dt(args.start)
    shadow = json.loads(Path(args.shadow).read_text(encoding="utf-8"))
    structural_hfa = float(shadow["fit"]["structuralHomeMarginAdvantage"])

    games = engine.fetch_completed_games(start, as_of)
    boxes, failures = rich.fetch_boxes(games)
    coverage = len(boxes) / max(1, len(games))
    if coverage < rich.MIN_SUMMARY_COVERAGE:
        raise RuntimeError(f"box-score coverage {coverage:.3f} below {rich.MIN_SUMMARY_COVERAGE:.2f}")
    rows, _, _ = rich.build_rows(games, boxes, structural_hfa)
    validation = evaluate_rows(rows)

    reference = None
    ref_path = Path(args.reference)
    if ref_path.exists():
        ref = json.loads(ref_path.read_text(encoding="utf-8"))
        reference = {
            "week": ref.get("week"),
            "games": (ref.get("overall") or {}).get("games"),
            "marginMae": ((ref.get("overall") or {}).get("model") or {}).get("marginMae"),
            "totalMae": ((ref.get("overall") or {}).get("model") or {}).get("totalMae"),
            "suAccuracyPct": ((ref.get("overall") or {}).get("model") or {}).get("suAccuracyPct"),
            "policy": "Context only. Do not fit to Week 7 outcomes and then claim Week 7 as out-of-sample validation.",
        }

    out = {
        "schemaVersion": 1,
        "league": "cfb",
        "season": 2026,
        "asOf": engine.iso(as_of),
        "role": "REBUILD_WALKFORWARD_RESEARCH",
        "canonicalInfluence": False,
        "source": {
            "schedule": "ESPN public FBS team schedules",
            "boxscores": "ESPN public college-football summary endpoint",
            "marketDataUsed": False,
            "externalRatingsUsed": False,
            "sameWeekLeakagePrevented": True,
            "boxscoreCoverage": coverage,
            "boxscoreFailures": failures[:20],
            "causalRows": len(rows),
        },
        "structuralHomeMarginAdvantage": structural_hfa,
        "walkForward": validation,
        "establishedWeek7Reference": reference,
        "warning": "Research validation only. No result in this file authorizes changing Week 8 canonical projections without explicit promotion review and prospective frozen-week evidence.",
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "causalRows": len(rows),
        "folds": len(validation["folds"]),
        "aggregate": validation["aggregate"],
        "prospectiveShadowGatePass": validation["prospectiveShadowGatePass"],
    }, indent=2))


if __name__ == "__main__":
    main()
