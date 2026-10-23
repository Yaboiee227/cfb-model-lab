#!/usr/bin/env python3
"""Extract research-only NFL team power ratings from the frozen pre-Week-7 model.

Run this script from the pinned nfl-week7-live-release source tree. It does not
retune, read post-Week-6 results, or alter any projection. Team CB Points are a
least-squares point-scale summary of the frozen model's all-pairs neutral-field
matchups. The underlying predictor is first regression-checked against every
frozen Week 7 canonical margin.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path.cwd()
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_nfl_walk_forward as base  # noqa: E402
import build_nfl_week6_research_projections as wk  # noqa: E402
import validate_nfl_rating_system_robustness as rat  # noqa: E402
import validate_nfl_final_plus_ftn_qb_process as final_model  # noqa: E402

SNAPSHOT = ROOT / "nfl_data/prospective/week7/20261021T114427Z"
HIST_SCHEDULE = ROOT / "nfl_data/research/week6_failure_20261021/inputs/nflverse_games.csv"
SPEC = ROOT / "nfl_data/validation/final_ftn_qb_process_blend.json"
PINNED_SNAPSHOT_ID = "20261021T114427Z"

TEAM_NAMES = {
    "ARI":"Arizona Cardinals","ATL":"Atlanta Falcons","BAL":"Baltimore Ravens","BUF":"Buffalo Bills",
    "CAR":"Carolina Panthers","CHI":"Chicago Bears","CIN":"Cincinnati Bengals","CLE":"Cleveland Browns",
    "DAL":"Dallas Cowboys","DEN":"Denver Broncos","DET":"Detroit Lions","GB":"Green Bay Packers",
    "HOU":"Houston Texans","IND":"Indianapolis Colts","JAX":"Jacksonville Jaguars","KC":"Kansas City Chiefs",
    "LA":"Los Angeles Rams","LAC":"Los Angeles Chargers","LV":"Las Vegas Raiders","MIA":"Miami Dolphins",
    "MIN":"Minnesota Vikings","NE":"New England Patriots","NO":"New Orleans Saints","NYG":"New York Giants",
    "NYJ":"New York Jets","PHI":"Philadelphia Eagles","PIT":"Pittsburgh Steelers","SEA":"Seattle Seahawks",
    "SF":"San Francisco 49ers","TB":"Tampa Bay Buccaneers","TEN":"Tennessee Titans","WAS":"Washington Commanders",
}


def read_csv(path: Path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def rating_state_through_week6(schedule: pd.DataFrame, params: dict):
    df = schedule.copy()
    df = df[df["game_type"].astype(str).str.upper().eq("REG")].copy()
    df["season"] = pd.to_numeric(df["season"], errors="coerce")
    df["week"] = pd.to_numeric(df["week"], errors="coerce")
    df["home_team"] = df["home_team"].map(rat.nt)
    df["away_team"] = df["away_team"].map(rat.nt)
    df["home_score"] = pd.to_numeric(df["home_score"], errors="coerce")
    df["away_score"] = pd.to_numeric(df["away_score"], errors="coerce")
    df = df[df["season"].between(2021, 2026)].sort_values(["season","week","gameday","gametime","game_id"])
    # Hard prospective cutoff: no Week 7 or later result can update state.
    df.loc[(df["season"] == 2026) & (df["week"] >= 7), ["home_score","away_score"]] = float("nan")

    elo = {}
    margin = {}
    last_season = None
    for _, g in df.iterrows():
        season = int(g["season"])
        home, away = str(g["home_team"]), str(g["away_team"])
        if last_season is None:
            last_season = season
        if season != last_season:
            reg = float(params["offseason_regression"])
            for team in list(elo):
                elo[team] = 1500.0 + (elo[team] - 1500.0) * reg
            for team in list(margin):
                margin[team] *= reg
            last_season = season
        eh, ea = elo.get(home, 1500.0), elo.get(away, 1500.0)
        mh, ma = margin.get(home, 0.0), margin.get(away, 0.0)
        hs, aws = g["home_score"], g["away_score"]
        if pd.isna(hs) or pd.isna(aws):
            continue
        actual_margin = float(hs - aws)
        actual = 1.0 if actual_margin > 0 else 0.0 if actual_margin < 0 else 0.5
        p = rat.expected(eh, ea, float(params["elo_hfa"]))
        delta = float(params["elo_k"]) * (actual - p)
        elo[home], elo[away] = eh + delta, ea - delta
        residual = actual_margin - ((mh - ma) + float(params["margin_hfa"]))
        md = float(params["margin_k"]) * residual
        margin[home], margin[away] = mh + md / 2.0, ma - md / 2.0
    return elo, margin, df


def attach_team_row(out: dict, side: str, row: dict, skip: set[str], prefix: str = ""):
    for key, value in row.items():
        if key in skip:
            continue
        out[f"{side}_{prefix}{key}"] = value


def synthetic_row(home: str, away: str, core: dict, coverage: dict, elo: dict, margin: dict):
    out = {
        "game_id": f"POWER_{away}_{home}",
        "season": 2026,
        "week": 7,
        "gameday": "2026-10-23",
        "gametime": "16:03",
        "away_team": away,
        "home_team": home,
        "neutral_site": 1,
        "away_rest": 7,
        "home_rest": 7,
        "market_home_spread_reference": "",
        "market_total_reference": "",
    }
    attach_team_row(out, "home", core[home], {"season","target_week","team"})
    attach_team_row(out, "away", core[away], {"season","target_week","team"})
    attach_team_row(out, "home", coverage[home], {"season","target_week","team","release_state"}, "cov_")
    attach_team_row(out, "away", coverage[away], {"season","target_week","team","release_state"}, "cov_")
    out["rating_win_elo_diff"] = float(elo.get(home, 1500.0) - elo.get(away, 1500.0))
    out["rating_margin_rating_diff"] = float(margin.get(home, 0.0) - margin.get(away, 0.0))
    return out


def solve_team_points(teams: list[str], pair_margins: dict[tuple[str,str], float]):
    idx = {team:i for i,team in enumerate(teams)}
    rows, y = [], []
    for i, a in enumerate(teams):
        for b in teams[i+1:]:
            # Symmetrize the two neutral orientations to remove any constant
            # home/away encoding artifact while retaining matchup interactions.
            m = 0.5 * (pair_margins[(a,b)] - pair_margins[(b,a)])
            row = np.zeros(len(teams))
            row[idx[a]] = 1.0
            row[idx[b]] = -1.0
            rows.append(row)
            y.append(m)
    # Zero-mean identifiability constraint.
    rows.append(np.ones(len(teams)))
    y.append(0.0)
    A = np.asarray(rows, dtype=float)
    yy = np.asarray(y, dtype=float)
    points, *_ = np.linalg.lstsq(A, yy, rcond=None)
    fitted = A[:-1] @ points
    residual = np.asarray(y[:-1]) - fitted
    return {team:float(points[idx[team]]) for team in teams}, float(np.sqrt(np.mean(residual ** 2)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    ap.add_argument("--source-commit", required=True)
    args = ap.parse_args()

    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    coverage_params = spec["coverage_params"]
    rating_params = dict(final_model.RATING)

    schedule = pd.read_csv(HIST_SCHEDULE)
    elo, margin, cutoff_schedule = rating_state_through_week6(schedule, rating_params)

    historical = base.load_rows()
    historical_cov = wk.attach_historical_coverage(historical)
    rmap = rat.rating_maps(
        cutoff_schedule,
        rating_params["elo_k"], rating_params["elo_hfa"], rating_params["offseason_regression"],
        rating_params["margin_k"], rating_params["margin_hfa"],
    )
    historical_rated = rat.attach(historical_cov, rmap)
    fitobj = final_model.fit(
        historical_rated,
        coverage_params["team_k"], coverage_params["feature_k"], rating_params["lambda"],
    )

    # Regression guard: the extraction machinery must reproduce every frozen
    # Week 7 canonical margin before team ratings are allowed to publish.
    frozen_features = read_csv(SNAPSHOT / "game_feature_inputs.csv")
    frozen_projection_rows = read_csv(SNAPSHOT / "paired_projections.csv")
    frozen_by_game = {r["game_id"]: float(r["canonical_home_margin"]) for r in frozen_projection_rows}
    frozen_pred, _ = final_model.predict(
        frozen_features,
        coverage_params["team_k"], coverage_params["feature_k"], fitobj,
    )
    regression = []
    for row, pred in zip(frozen_features, frozen_pred):
        target = frozen_by_game[row["game_id"]]
        regression.append({"gameId":row["game_id"],"reproduced":float(pred),"frozen":target,"absDiff":abs(float(pred)-target)})
    max_diff = max(x["absDiff"] for x in regression)
    if max_diff > 1e-8 or len(regression) != 14:
        raise RuntimeError(f"Frozen Week 7 regression failed n={len(regression)} maxDiff={max_diff}")

    core = {r["team"]:r for r in read_csv(SNAPSHOT / "core_inputs.csv")}
    coverage = {r["team"]:r for r in read_csv(SNAPSHOT / "coverage_inputs.csv")}
    teams = sorted(core)
    if len(teams) != 32 or set(teams) != set(coverage):
        raise RuntimeError(f"Expected identical 32-team core/coverage state, core={len(core)} coverage={len(coverage)}")

    synth = []
    ordered_pairs = []
    for home in teams:
        for away in teams:
            if home == away:
                continue
            synth.append(synthetic_row(home, away, core, coverage, elo, margin))
            ordered_pairs.append((home, away))
    preds, _ = final_model.predict(
        synth,
        coverage_params["team_k"], coverage_params["feature_k"], fitobj,
    )
    pair_margins = {(h,a):float(p) for (h,a),p in zip(ordered_pairs,preds)}
    points, residual_rmse = solve_team_points(teams, pair_margins)

    ranked = sorted(teams, key=lambda t:(-points[t], t))
    rows = []
    for rank, team in enumerate(ranked, 1):
        rows.append({
            "rank": rank,
            "team": team,
            "teamName": TEAM_NAMES.get(team, team),
            "cbPoints": round(points[team], 4),
            "movement": "NEW",
            "marketRank": None,
            "marketPoints": None,
            "marketGap": None,
            "evidenceStatus": "FROZEN_PRE_WEEK7_MODEL_EXTRACT",
        })

    out = {
        "schemaVersion": 1,
        "league": "nfl",
        "season": 2026,
        "week": 7,
        "snapshotAsOf": "2026-10-21T11:44:27Z",
        "sourceCommit": args.source_commit,
        "sourceSnapshotId": PINNED_SNAPSHOT_ID,
        "modelRole": "RESEARCH_POWER_RATING_ONLY",
        "canonicalInfluence": False,
        "canonicalPromotionAuthorized": False,
        "method": "Frozen canonical spread architecture summarized by all-pairs neutral-field model matchups, then least-squares reduced to zero-mean team point ratings.",
        "modelComponents": ["efficiency", "defensive coverage", "win Elo", "margin rating"],
        "teamCount": len(rows),
        "allPairsNeutralMatchups": len(synth),
        "pointScaleFitResidualRmse": residual_rmse,
        "frozenRegression": {"games":len(regression),"maxAbsDiff":max_diff,"pass":True,"rows":regression},
        "marketNationalRatingStatus": "WITHHELD_UNTIL_CONNECTED_TIMESTAMPED_MARKET_GRAPH",
        "teams": rows,
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"teamCount":len(rows),"top10":[[r["rank"],r["team"],r["cbPoints"]] for r in rows[:10]],"frozenRegressionMaxAbsDiff":max_diff,"pointScaleFitResidualRmse":residual_rmse}, indent=2))


if __name__ == "__main__":
    main()
