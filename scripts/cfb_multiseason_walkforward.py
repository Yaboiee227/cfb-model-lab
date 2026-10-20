#!/usr/bin/env python3
"""Season-reset multi-season walk-forward validation for the CFB rebuild.

Purpose
-------
Use a completed prior season to learn *feature-to-outcome relationships* without
carrying prior-season team strength, roster state, or box-score state into the
current season.

Leakage controls
----------------
* Each season's team/game history is rebuilt from an empty state.
* Historical feature rows are frozen at the start of each football week by
  cfb_rich_challenger.build_rows().
* The structural HFA used for 2025 is estimated only from 2022-2024.
* The structural HFA used for 2026 is read from the already-audited Week 8
  shadow file, where it was estimated from completed 2023-2025 seasons.
* For every 2026 test week, bundle/ridge selection uses only the immediately
  preceding 2026 week plus 2025/earlier-2026 training rows; the test week is
  unseen.
* No sportsbook, SP+, Sagarin, RefMetrics, or target-game result enters a
  prediction feature.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

import cfb_rich_challenger as rich
import cfb_shadow_engine as engine
from run_cfb_shadow_week8 import extract_grouped_team_ids

engine.extract_team_ids = extract_grouped_team_ids

MIN_PRIOR_SEASON_ROWS = 150
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


def estimate_prior_only_hfa(seasons: tuple[int, ...], alpha: float = 5.0, min_apps: int = 4) -> tuple[float, list[dict[str, Any]]]:
    rows = []
    for season in seasons:
        start = datetime(season, 8, 1, tzinfo=timezone.utc)
        end = datetime(season + 1, 1, 15, tzinfo=timezone.utc)
        games = engine.fetch_completed_games(start, end)
        model = engine.fit_model(
            games,
            end,
            alpha=alpha,
            half_life_days=None,
            min_team_appearances=min_apps,
            fixed_hfa=None,
        )
        rows.append({
            "season": season,
            "rawGames": len(games),
            "eligibleGames": int(model["eligibleTrainingGames"]),
            "homeMarginAdvantage": float(model["homeMarginAdvantage"]),
        })
    hfa = float(statistics.median([r["homeMarginAdvantage"] for r in rows]))
    return hfa, rows


def build_season_rows(season: int, end: datetime, structural_hfa: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    start = datetime(season, 8, 20, tzinfo=timezone.utc)
    games = engine.fetch_completed_games(start, end)
    boxes, failures = rich.fetch_boxes(games)
    coverage = len(boxes) / max(1, len(games))
    if coverage < rich.MIN_SUMMARY_COVERAGE:
        raise RuntimeError(f"{season} box-score coverage {coverage:.3f} below {rich.MIN_SUMMARY_COVERAGE:.2f}")
    rows, _snapshot, _history = rich.build_rows(games, boxes, structural_hfa)
    return rows, {
        "season": season,
        "games": len(games),
        "boxscoreGames": len(boxes),
        "boxscoreCoverage": coverage,
        "boxscoreFailures": failures[:20],
        "causalRows": len(rows),
        "structuralHomeMarginAdvantage": structural_hfa,
    }


def select_and_refit(
    all_training: list[dict[str, Any]],
    inner_valid: list[dict[str, Any]],
    target: str,
    bundles: dict[str, tuple[int, ...]],
):
    valid_ids = {id(r) for r in inner_valid}
    inner_train = [r for r in all_training if id(r) not in valid_ids]
    if len(inner_train) < MIN_PRIOR_SEASON_ROWS or len(inner_valid) < MIN_INNER_VALID_ROWS:
        return None
    best, _candidates = rich.choose_model(inner_train, inner_valid, target, bundles)
    final = rich.ridge_fit(all_training, tuple(best["indices"]), target, float(best["alpha"]))
    return best, final


def evaluate(prior_rows: list[dict[str, Any]], current_rows: list[dict[str, Any]]) -> dict[str, Any]:
    current_by_week: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in current_rows:
        current_by_week[row["weekStart"]].append(row)
    weeks = sorted(current_by_week)

    folds = []
    aggregate = {
        "simpleMargin": [], "richMargin": [], "marginActual": [],
        "simpleTotal": [], "richTotal": [], "totalActual": [],
    }

    for idx in range(1, len(weeks)):
        test_week = weeks[idx]
        previous_week = weeks[idx - 1]
        earlier_weeks = set(weeks[:idx])
        earlier_current = [r for r in current_rows if r["weekStart"] in earlier_weeks]
        all_training = list(prior_rows) + earlier_current
        inner_valid = list(current_by_week[previous_week])
        test = list(current_by_week[test_week])
        if len(test) < MIN_TEST_ROWS:
            continue

        margin_choice = select_and_refit(all_training, inner_valid, "margin", rich.MARGIN_BUNDLES)
        total_choice = select_and_refit(all_training, inner_valid, "total", rich.TOTAL_BUNDLES)
        if margin_choice is None or total_choice is None:
            continue
        best_margin, margin_model = margin_choice
        best_total, total_model = total_choice

        simple_margin = [float(r["x"][0]) for r in test]
        simple_total = [float(r["x"][1]) for r in test]
        rich_margin = [float(x) for x in rich.ridge_predict(margin_model, test)]
        rich_total = [float(x) for x in rich.ridge_predict(total_model, test)]
        actual_margin = [float(r["margin"]) for r in test]
        actual_total = [float(r["total"]) for r in test]

        aggregate["simpleMargin"].extend(simple_margin)
        aggregate["richMargin"].extend(rich_margin)
        aggregate["marginActual"].extend(actual_margin)
        aggregate["simpleTotal"].extend(simple_total)
        aggregate["richTotal"].extend(rich_total)
        aggregate["totalActual"].extend(actual_total)

        folds.append({
            "testWeekStart": test_week,
            "previousWeekInnerValidation": previous_week,
            "priorSeasonRows": len(prior_rows),
            "earlierCurrentSeasonRows": len(earlier_current),
            "trainingRows": len(all_training),
            "innerValidationRows": len(inner_valid),
            "testRows": len(test),
            "selectedMargin": {"bundle": best_margin["name"], "alpha": best_margin["alpha"]},
            "selectedTotal": {"bundle": best_total["name"], "alpha": best_total["alpha"]},
            "simpleMargin": metric(simple_margin, actual_margin),
            "richMargin": metric(rich_margin, actual_margin),
            "simpleTotal": metric(simple_total, actual_total),
            "richTotal": metric(rich_total, actual_total),
        })

    sm = metric(aggregate["simpleMargin"], aggregate["marginActual"])
    rm = metric(aggregate["richMargin"], aggregate["marginActual"])
    st = metric(aggregate["simpleTotal"], aggregate["totalActual"])
    rt = metric(aggregate["richTotal"], aggregate["totalActual"])
    margin_delta = None if rm["mae"] is None else float(rm["mae"]) - float(sm["mae"])
    total_delta = None if rt["mae"] is None else float(rt["mae"]) - float(st["mae"])

    gate = bool(
        len(folds) >= 3
        and margin_delta is not None and total_delta is not None
        and margin_delta <= 0.25
        and total_delta <= 0.25
        and (margin_delta <= -0.50 or total_delta <= -0.50)
    )
    evidence_status = (
        "INSUFFICIENT_FOLDS" if len(folds) < 3
        else ("RICH_SHADOW_ELIGIBLE" if gate else "RICH_REJECTED")
    )
    return {
        "folds": folds,
        "aggregate": {
            "games": len(aggregate["marginActual"]),
            "simpleMargin": sm,
            "richMargin": rm,
            "simpleTotal": st,
            "richTotal": rt,
            "richMinusSimpleMarginMae": margin_delta,
            "richMinusSimpleTotalMae": total_delta,
        },
        "minimumRequiredFolds": 3,
        "evidenceStatus": evidence_status,
        "prospectiveShadowGatePass": gate,
        "gateRule": "Across >=3 unseen 2026 weekly folds, rich must improve at least one MAE by >=0.50 and degrade neither margin nor total MAE by >0.25. Passing still does not authorize canonical promotion.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default="2026-10-20T00:00:00-04:00")
    ap.add_argument("--shadow", default="cfb/shadow/week-08-tuesday.json")
    ap.add_argument("--reference", default="cfb/validation/week-07-canonical-reference.json")
    ap.add_argument("--output", default="cfb/validation/week-08-multiseason-walkforward.json")
    args = ap.parse_args()

    as_of = engine.parse_dt(args.as_of)
    shadow = json.loads(Path(args.shadow).read_text(encoding="utf-8"))
    hfa_2026 = float(shadow["fit"]["structuralHomeMarginAdvantage"])

    # 2025 feature construction may not use 2025 outcomes to estimate its own HFA.
    hfa_2025, hfa_2025_sources = estimate_prior_only_hfa((2022, 2023, 2024), alpha=5.0, min_apps=4)
    rows_2025, meta_2025 = build_season_rows(2025, datetime(2026, 1, 15, tzinfo=timezone.utc), hfa_2025)
    rows_2026, meta_2026 = build_season_rows(2026, as_of, hfa_2026)
    if len(rows_2025) < MIN_PRIOR_SEASON_ROWS:
        raise RuntimeError(f"insufficient 2025 causal rows: {len(rows_2025)}")

    wf = evaluate(rows_2025, rows_2026)

    ref_summary = None
    ref_path = Path(args.reference)
    if ref_path.exists():
        ref = json.loads(ref_path.read_text(encoding="utf-8"))
        overall = ref.get("overall") or {}
        model = overall.get("model") or {}
        ref_summary = {
            "week": ref.get("week"),
            "games": overall.get("games"),
            "marginMae": model.get("marginMae"),
            "totalMae": model.get("totalMae"),
            "suAccuracyPct": model.get("suAccuracyPct"),
            "policy": "Descriptive reference only; not used for coefficient fitting or hyperparameter selection.",
        }

    out = {
        "schemaVersion": 1,
        "league": "cfb",
        "season": 2026,
        "asOf": engine.iso(as_of),
        "role": "MULTISEASON_SEASON_RESET_WALKFORWARD_RESEARCH",
        "canonicalInfluence": False,
        "policy": {
            "priorSeasonTeamStateCarryover": False,
            "priorSeasonUsedFor": "feature-to-outcome coefficient learning only",
            "currentSeasonTeamState": "2026 only, reset at season start",
            "marketDataUsed": False,
            "externalRatingsUsed": False,
            "sameWeekLeakagePrevented": True,
        },
        "hfa": {
            "for2025FeatureRows": hfa_2025,
            "for2025DerivedOnlyFrom": [2022, 2023, 2024],
            "for2025SeasonEstimates": hfa_2025_sources,
            "for2026FeatureRows": hfa_2026,
            "for2026Source": "audited Week 8 shadow structural HFA derived from 2023-2025",
        },
        "dataQuality": {"season2025": meta_2025, "season2026": meta_2026},
        "walkForward2026": wf,
        "establishedWeek7Reference": ref_summary,
        "warning": "Research only. Prior-season coefficient evidence and any gate pass still require prospective frozen-week evidence before canonical promotion.",
    }

    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "rows2025": len(rows_2025),
        "rows2026": len(rows_2026),
        "hfa2025": hfa_2025,
        "folds": len(wf["folds"]),
        "aggregate": wf["aggregate"],
        "evidenceStatus": wf["evidenceStatus"],
        "prospectiveShadowGatePass": wf["prospectiveShadowGatePass"],
    }, indent=2))


if __name__ == "__main__":
    main()
