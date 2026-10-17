#!/usr/bin/env python3
"""Build isolated NFL Week 6 research projections from the validated architecture.

Spread: frozen core + defensive coverage + validated recursive ratings.
Total: frozen core baseline only.

Training uses completed 2022-2025 regular-season games. Current team state uses
2026 regular-season Weeks 1-5 only plus completed 2025 prior-season context.
The completed Week-6 Thursday game is excluded from the projection board.
Schedule market lines are benchmark/reference fields only and are NOT
execution-verified prices.

Every output remains HOLD_RESEARCH_ONLY. This script does not publish website
artifacts and must run only on nfl-model-development.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_nfl_historical_features as hist
import run_nfl_walk_forward as base
import validate_nfl_coverage_v1 as cov
import validate_nfl_rating_system_robustness as rat

SEASON = 2026
TARGET_WEEK = 6
CUTOFF_WEEK = 5
OUT_DIR = Path("nfl_data/generated")
COVERAGE_CURRENT = OUT_DIR / "coverage_2026_week6_pregame.csv"
RATING_STABILITY = Path("nfl_data/validation/rating_system_stability.json")


def tf(v):
    return base.to_float(v)


def load_current_coverage():
    with COVERAGE_CURRENT.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    idx = {}
    leak = 0
    for r in rows:
        team = r["team"]
        key = (int(float(r["season"])), int(float(r["target_week"])), team)
        if key in idx:
            raise RuntimeError(f"Duplicate current coverage row {key}")
        mw = tf(r.get("max_current_week_used"))
        if mw is not None and mw >= TARGET_WEEK:
            leak += 1
        idx[team] = r
    if len(idx) != 32:
        raise RuntimeError(f"Expected 32 current coverage teams, got {len(idx)}")
    if leak:
        raise RuntimeError(f"Current coverage leakage rows={leak}")
    return idx


def attach_historical_coverage(rows):
    ci, leak, _ = cov.loadidx(cov.COV, "cov")
    if leak:
        raise RuntimeError(f"Historical coverage leakage rows={leak}")
    out = []
    miss = []
    for r in rows:
        h = ci.get((r["season"], r["week"], r["home_team"]))
        a = ci.get((r["season"], r["week"], r["away_team"]))
        if h is None or a is None:
            miss.append(r["game_id"])
            continue
        x = dict(r)
        for side, row in (("home", h), ("away", a)):
            for k, v in row.items():
                if k not in {"season", "target_week", "team", "release_state"}:
                    x[f"{side}_cov_{k}"] = v
        out.append(x)
    if miss:
        raise RuntimeError(f"Missing historical coverage snapshots {len(miss)} first={miss[:5]}")
    return out


def build_team_snapshot():
    qa = {}
    wo25, wd25, _ = hist.process_season(2025, qa)
    wo26, wd26, games26 = hist.process_season(2026, qa)
    teams = sorted(set(wo26) | set(wd26))
    if len(teams) != 32:
        raise RuntimeError(f"Expected 32 2026 teams, found {len(teams)}")

    prior = {t: hist.season_full(wo25, wd25, t) for t in sorted(set(wo25) | set(wd25))}
    rows = {}
    max_source_week = 0
    future_rows_used = 0
    for team in teams:
        available = sorted(set(wo26[team]) | set(wd26[team]))
        prior_weeks = [w for w in available if w < TARGET_WEEK]
        if any(w >= TARGET_WEEK for w in prior_weeks):
            future_rows_used += 1
        cur = hist.metrics(hist.aggregate_weeks(wo26, team, prior_weeks), hist.aggregate_weeks(wd26, team, prior_weeks))
        played = [w for w in prior_weeks if games26[team].get(w)]
        last3 = played[-3:]
        rec = hist.metrics(hist.aggregate_weeks(wo26, team, last3), hist.aggregate_weeks(wd26, team, last3)) if last3 else {k: "" for k in cur}
        row = {
            "season": SEASON,
            "target_week": TARGET_WEEK,
            "team": team,
            "games_before": sum(len(games26[team].get(w, set())) for w in prior_weeks),
            "max_current_season_week_used": max(prior_weeks) if prior_weeks else 0,
        }
        row.update({f"std_{k}": v for k, v in cur.items()})
        row.update({f"last3_{k}": v for k, v in rec.items() if k in {"off_epa","def_epa_allowed","net_epa","off_success","def_success_allowed","net_success"}})
        p = prior.get(team, {})
        row.update({f"prior_{k}": v for k, v in p.items() if k in {"off_epa","def_epa_allowed","net_epa","off_success","def_success_allowed","net_success","off_pass_epa","off_rush_epa","off_sack_rate","def_sack_rate_forced"}})
        if row["max_current_season_week_used"] >= TARGET_WEEK:
            raise RuntimeError(f"Current leakage {team}: {row['max_current_season_week_used']}")
        max_source_week = max(max_source_week, row["max_current_season_week_used"])
        rows[team] = row
    return rows, qa, max_source_week, future_rows_used


def build_current_games(team_rows, coverage):
    sched = hist.fetch_schedule()
    games = []
    completed_excluded = []
    for r in sched:
        season = int(hist.z(r.get("season")))
        week = int(hist.z(r.get("week")))
        if season != SEASON or week != TARGET_WEEK or str(r.get("game_type", "")).upper() != "REG":
            continue
        home = str(r.get("home_team", "")).strip()
        away = str(r.get("away_team", "")).strip()
        hs = hist.num(r.get("home_score")); aws = hist.num(r.get("away_score"))
        if hs is not None and aws is not None:
            completed_excluded.append(str(r.get("game_id", "")))
            continue
        if home not in team_rows or away not in team_rows:
            raise RuntimeError(f"Missing current team snapshot {away}@{home}")
        if home not in coverage or away not in coverage:
            raise RuntimeError(f"Missing current coverage snapshot {away}@{home}")
        h = team_rows[home]; a = team_rows[away]
        out = {
            "game_id": r.get("game_id", ""),
            "season": SEASON,
            "week": TARGET_WEEK,
            "gameday": r.get("gameday", ""),
            "gametime": r.get("gametime", ""),
            "away_team": away,
            "home_team": home,
            "neutral_site": 1 if str(r.get("location", "")).lower() == "neutral" else 0,
            "away_rest": r.get("away_rest", ""),
            "home_rest": r.get("home_rest", ""),
            "market_home_spread_reference": hist.rnd(-hist.num(r.get("spread_line")), 2) if hist.num(r.get("spread_line")) is not None else "",
            "market_total_reference": hist.rnd(hist.num(r.get("total_line")), 2),
            "market_reference_policy": "SCHEDULE_REFERENCE_ONLY_NOT_EXECUTION_VERIFIED_NOT_MODEL_FEATURE",
        }
        for side, row in (("home", h), ("away", a)):
            for k, v in row.items():
                if k not in {"season", "target_week", "team"}:
                    out[f"{side}_{k}"] = v
        for side, row in (("home", coverage[home]), ("away", coverage[away])):
            for k, v in row.items():
                if k not in {"season", "target_week", "team", "release_state"}:
                    out[f"{side}_cov_{k}"] = v
        games.append(out)
    games.sort(key=lambda x: (x.get("gameday", ""), x.get("gametime", ""), x["game_id"]))
    return games, completed_excluded


def load_rating_spec():
    spec = json.loads(RATING_STABILITY.read_text(encoding="utf-8"))
    if spec.get("stability_verdict") != "EARNED_WEEK6_RESEARCH_INCLUSION":
        raise RuntimeError(f"Rating layer not cleared for Week-6 research inclusion: {spec.get('stability_verdict')}")
    p = spec["frozen_rating_params"]
    return spec, {
        "elo_hfa": float(p["elo_hfa"]),
        "elo_k": float(p["elo_k"]),
        "lambda": float(p["lambda"]),
        "margin_hfa": float(p["margin_hfa"]),
        "margin_k": float(p["margin_k"]),
        "offseason_regression": float(p["offseason_regression"]),
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    historical = base.load_rows()
    historical_cov = attach_historical_coverage(historical)
    if len(historical) != 1087 or len(historical_cov) != 1087:
        raise RuntimeError(f"Historical coverage mismatch base={len(historical)} cov={len(historical_cov)}")

    # Freeze hyperparameters from 2022 only, matching robustness design.
    spread_2022 = [r for r in historical_cov if r["season"] == 2022]
    frozen_spread, spread_top = cov.select(spread_2022, "spread", "coverage")
    total_2022 = [r for r in historical if r["season"] == 2022]
    frozen_total, total_top = base.select_params(total_2022, "total")
    rating_stability, rating_params = load_rating_spec()

    team_rows, pbp_qa, max_source_week, future_rows_used = build_team_snapshot()
    current_cov = load_current_coverage()
    current_games, completed_excluded = build_current_games(team_rows, current_cov)
    if future_rows_used or max_source_week > CUTOFF_WEEK:
        raise RuntimeError(f"Current source cutoff failure max={max_source_week} future={future_rows_used}")
    if len(current_games) != 13:
        raise RuntimeError(f"Expected 13 remaining Week-6 games after completed Thursday exclusion, got {len(current_games)}")

    # Audit comparison: coverage-only spread.
    coverage_pred, coverage_coef = cov.fitp(
        historical_cov,
        current_games,
        "spread",
        "coverage",
        {"team_k": frozen_spread["team_k"], "feature_k": frozen_spread["feature_k"], "lambda": frozen_spread["lambda"]},
    )

    # Final research spread: core + coverage + market-independent recursive ratings.
    games_df = rat.fetch_games()
    rating_map = rat.rating_maps(
        games_df,
        rating_params["elo_k"],
        rating_params["elo_hfa"],
        rating_params["offseason_regression"],
        rating_params["margin_k"],
        rating_params["margin_hfa"],
    )
    historical_rated = rat.attach(historical_cov, rating_map)
    current_rated = rat.attach(current_games, rating_map)
    rating_fit = rat.fit(
        historical_rated,
        "both",
        frozen_spread["team_k"],
        rating_params["lambda"],
        frozen_spread["feature_k"],
    )
    spread_pred = rat.pred(
        current_rated,
        "both",
        frozen_spread["team_k"],
        frozen_spread["feature_k"],
        rating_fit,
    )

    total_pred, total_model, total_prep, total_names, total_coef = base.fit_and_predict(
        historical,
        current_games,
        "total",
        frozen_total["k"],
        frozen_total["lambda"],
    )

    output = []
    for r, pc, ps, pt in zip(current_games, coverage_pred, spread_pred, total_pred):
        pc = float(pc); ps = float(ps); pt = float(pt)
        qsp = tf(r.get("market_home_spread_reference")); qtot = tf(r.get("market_total_reference"))
        output.append({
            "game_id": r["game_id"],
            "season": SEASON,
            "week": TARGET_WEEK,
            "gameday": r.get("gameday", ""),
            "gametime": r.get("gametime", ""),
            "away_team": r["away_team"],
            "home_team": r["home_team"],
            "coverage_only_home_margin": round(pc, 3),
            "rating_adjusted_home_margin": round(ps, 3),
            "rating_layer_margin_delta": round(ps - pc, 3),
            "projected_home_spread": round(-ps, 3),
            "pred_total": round(pt, 3),
            "schedule_home_spread_reference": "" if qsp is None else round(qsp, 3),
            "schedule_total_reference": "" if qtot is None else round(qtot, 3),
            "spread_edge_vs_schedule_reference": "" if qsp is None else round(ps + qsp, 3),
            "total_edge_vs_schedule_reference": "" if qtot is None else round(pt - qtot, 3),
            "spread_model": "FROZEN_CORE_PLUS_DEFENSIVE_COVERAGE_PLUS_WIN_ELO_PLUS_MARGIN_RATING",
            "total_model": "FROZEN_CORE_ONLY",
            "market_policy": "SCHEDULE_REFERENCE_ONLY_NOT_EXECUTION_VERIFIED_NOT_MODEL_FEATURE",
            "personnel_gate": "PENDING_OFFICIAL_STARTER_INACTIVE_VERIFICATION",
            "roof_weather_gate": "PENDING_FINAL_VERIFICATION",
            "execution_price_gate": "PENDING_DIRECT_BOOK_PRICE",
            "prospective_validation_gate": "PENDING",
            "recommendation": "HOLD",
            "release_state": "HOLD_RESEARCH_ONLY",
            "website_publish_allowed": False,
        })

    pred_path = OUT_DIR / "week6_research_projections.csv"
    with pred_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(output[0]))
        w.writeheader(); w.writerows(output)

    qa = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "season": SEASON,
        "target_week": TARGET_WEEK,
        "cutoff_week": CUTOFF_WEEK,
        "training_seasons": [2022, 2023, 2024, 2025],
        "training_games": len(historical),
        "current_team_rows": len(team_rows),
        "current_remaining_games": len(current_games),
        "completed_week6_games_excluded": completed_excluded,
        "max_current_source_week_used": max_source_week,
        "current_target_or_future_rows_used": future_rows_used,
        "frozen_coverage_params": frozen_spread,
        "frozen_coverage_2022_top_candidates": spread_top,
        "frozen_rating_params": rating_params,
        "rating_stability_verdict": rating_stability.get("stability_verdict"),
        "rating_production_verdict": rating_stability.get("production_verdict"),
        "frozen_total_params": frozen_total,
        "frozen_total_2022_top_candidates": total_top,
        "spread_model": "core baseline + defensive coverage + market-independent win Elo + margin rating",
        "spread_audit_comparison": "coverage-only projection retained beside rating-adjusted projection",
        "total_model": "core baseline only",
        "coverage_training_feature_count": len(coverage_coef),
        "total_training_feature_count": len(total_coef),
        "pbp_source_qa_2025_2026": pbp_qa,
        "market_policy": "schedule line retained only as non-execution-verified benchmark; excluded from all model features and fitting",
        "hard_release_gates": ["official starter/inactive verification", "direct executable sportsbook price", "final roof/weather verification", "prospective calibration/readiness review"],
        "release_state": "HOLD_RESEARCH_ONLY",
        "website_publish_allowed": False,
    }
    qa_path = OUT_DIR / "week6_research_projections_qa.json"
    qa_path.write_text(json.dumps(qa, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"prediction_output": str(pred_path), "qa_output": str(qa_path), "games": len(output), "coverage_params": frozen_spread, "rating_params": rating_params, "total_params": frozen_total, "release_state": qa["release_state"]}, indent=2))


if __name__ == "__main__":
    main()
