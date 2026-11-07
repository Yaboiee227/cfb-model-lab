#!/usr/bin/env python3
"""Refresh future NFL research games with the existing pinned architecture.

Requires a clean, exact source checkout and captured nflverse bytes. Reproduces
all saved Week 7 canonical spreads/totals before any current forecast is saved.
Never promotes a feature, creates a market lock, or updates the website.
Run in a separate process: legacy modules use checkout-relative data paths.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from capture_projection_resources import PBP_URL, clock, retrieve
from projection_resource_evidence import digest, instant, nfl_slate, save_new

PIN = "0721b59b5f461ad590bd348bd655c4963265856c"


def csv_rows(path):
    return list(csv.DictReader(path.open()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, capture, out = args.source_root.resolve(), args.capture.resolve(), args.output.resolve()
    repo = Path(__file__).resolve().parents[1]
    if out == repo or any(out.is_relative_to(repo / p) for p in ["data", "nfl", "cfb", "nfl_data", "scripts", "tests", ".github"]):
        parser.error("research output must be outside production directories")
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if head != PIN or subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True).strip():
        raise ValueError("NFL model source must be the clean pinned checkout")
    evidence = json.loads((capture / "manifest.json").read_text())
    sources = {s["sourceId"]: s for s in evidence["sources"]}
    for label in ["nflverse-schedule", "nflverse-pbp"]:
        s = sources[label]
        if digest((capture / s["rawPath"]).read_bytes()) != s["sha256"]:
            raise ValueError("capture SHA256 mismatch")
        age = (clock() - instant(s["observedAt"])).total_seconds()
        if not 0 <= age <= 172800:
            raise ValueError("capture older than 48 hours or future-dated")
    schedule_path = capture / sources["nflverse-schedule"]["rawPath"]
    schedule = csv_rows(schedule_path); slate = nfl_slate(schedule, clock())
    if slate["season"] != 2026:
        raise ValueError("pinned generator only supports its audited 2026 season")
    season, week = slate["season"], slate["week"]
    out.mkdir(parents=True, exist_ok=False)
    raw_dir = out / "raw"; raw_dir.mkdir()
    current_path = raw_dir / f"play_by_play_{season}.csv.gz"
    shutil.copyfile(capture / sources["nflverse-pbp"]["rawPath"], current_path)
    for label in ["nflverse-schedule", "nflverse-pbp"]:
        shutil.copyfile(capture / sources[label]["rawPath"], out / sources[label]["rawPath"])
    fetched = []
    raw, meta = retrieve(PBP_URL.format(season=season-1), out, "prior-pbp")
    shutil.copyfile(out / meta["rawPath"], raw_dir / f"play_by_play_{season-1}.csv.gz")
    fetched.append(meta)
    for year in [season-1, season]:
        _, meta = retrieve(f"https://github.com/nflverse/nflverse-data/releases/download/pfr_advstats/advstats_week_def_{year}.parquet", out, f"coverage-{year}")
        shutil.copyfile(out / meta["rawPath"], raw_dir / f"advstats_week_def_{year}.parquet")
        fetched.append(meta)
    # Import only after verifying the checkout. All fits below use frozen specs.
    os.chdir(source); sys.path.insert(0, str(source / "scripts")); sys.dont_write_bytecode = True
    import numpy as np
    import pandas as pd
    import run_nfl_walk_forward as base
    import build_nfl_week6_research_projections as wk
    import build_nfl_coverage_features as coverage
    import validate_nfl_rating_system_robustness as ratings
    import validate_nfl_final_plus_ftn_qb_process as final

    snap = source / "nfl_data/prospective/week7/20261021T114427Z"
    spec = json.loads((snap / "manifest.json").read_text())
    for name, expected in spec["source_hashes"].items():
        if digest((source / name).read_bytes()) != expected:
            raise ValueError(f"pinned training data changed: {name}")
    for name, expected in spec["files"].items():
        if digest((snap / name).read_bytes()) != expected:
            raise ValueError(f"frozen reproduction evidence changed: {name}")
    cp, rp, tp = spec["coverage_params"], spec["rating_params"], spec["total_params"]

    def rating_map(path, target_week):
        df = pd.read_csv(path)
        df = df[df.game_type.eq("REG") & df.season.between(2021, season)].sort_values(["season", "week", "gameday", "gametime", "game_id"])
        df["home_team"] = df.home_team.map(ratings.nt); df["away_team"] = df.away_team.map(ratings.nt)
        df.loc[(df.season == season) & (df.week >= target_week), ["home_score", "away_score"]] = np.nan
        return ratings.rating_maps(df, rp["elo_k"], rp["elo_hfa"], rp["offseason_regression"], rp["margin_k"], rp["margin_hfa"])

    historical = base.load_rows()
    train = ratings.attach(wk.attach_historical_coverage(historical), rating_map(source / "nfl_data/research/week6_failure_20261021/inputs/nflverse_games.csv", 7))
    fitted = final.fit(train, cp["team_k"], cp["feature_k"], rp["lambda"])

    def predict(rows):
        margin, _ = final.predict(rows, cp["team_k"], cp["feature_k"], fitted)
        total, *_ = base.fit_and_predict(historical, rows, "total", tp["k"], tp["lambda"])
        return margin, total

    original_rows = csv_rows(snap / "game_feature_inputs.csv")
    frozen = {r["game_id"]: r for r in csv_rows(snap / "paired_projections.csv")}
    margins, totals = predict(original_rows)
    spread_diff = max(abs(float(m) - float(frozen[r["game_id"]]["canonical_home_margin"])) for r, m in zip(original_rows, margins))
    total_diff = max(abs(float(t) - float(frozen[r["game_id"]]["canonical_total"])) for r, t in zip(original_rows, totals))
    if len(original_rows) != 14 or spread_diff > 1e-8 or total_diff > 1e-8:
        raise ValueError(f"pinned forecast reproduction failed: {spread_diff}, {total_diff}")

    wk.SEASON = season; wk.TARGET_WEEK = week; wk.CUTOFF_WEEK = week-1
    wk.hist.PBP_URL = raw_dir.as_uri() + "/play_by_play_{season}.csv.gz"
    teams, qa, max_week, future_used = wk.build_team_snapshot()
    if future_used or max_week >= week:
        raise ValueError("current input week leakage")
    coverage.URL = str(raw_dir / "advstats_week_def_{season}.parquet")
    previous = coverage.weekly(coverage.load(season-1)); current = coverage.weekly(coverage.load(season))
    cov = {t: coverage.snap(season, week, t, current, previous) for t in teams}
    wk.hist.fetch_schedule = lambda: schedule
    live, completed = wk.build_current_games(teams, cov)
    schedule_games = {g["gameId"]: g for g in slate["games"]}
    live = [r for r in live if instant(schedule_games[r["game_id"]]["kickoff"]) > clock()]
    live = ratings.attach(live, rating_map(schedule_path, week))
    margins, totals = predict(live)
    frozen_at = clock().isoformat(); games = []
    for row, margin, total in zip(live, margins, totals):
        game = schedule_games[row["game_id"]]
        if instant(game["kickoff"]) <= instant(frozen_at):
            raise ValueError("kickoff crossed during computation; rerun for remaining games")
        margin, total = float(margin), float(total)
        if not all(math.isfinite(v) for v in [margin, total]) or total < abs(margin):
            raise ValueError("nonfinite or inconsistent score projection")
        g = {"gameId": game["gameId"], "away": game["awayTeam"], "home": game["homeTeam"],
             "kickoffUTC": game["kickoff"], "neutralSite": game["neutralSite"],
             "modelSpreadHome": -margin, "modelTotal": total,
             "projectedHomePoints": (total+margin)/2, "projectedAwayPoints": (total-margin)/2,
             "releaseStatus": "HOLD_RESEARCH_ONLY", "personnelState": "UNVERIFIED", "finalAvailabilityVerified": False,
             "weatherVerified": False, "officialsVerified": False, "executionVerified": False,
             "homeWinProbability": None}
        games.append(g)
    save_new(out / "model-inputs.json", {"teamCore": teams, "teamCoverage": cov, "gameFeatures": live, "pbpQa": qa})
    save_new(out / "nfl-projections.json", {"league": "nfl", "season": season, "week": week,
        "frozenAt": frozen_at, "role": "PROSPECTIVE_RESEARCH", "canonicalInfluence": False,
        "sourceCommit": PIN, "newFeaturesPromoted": [], "games": games,
        "priorWeekReproduction": {"games": 14, "spreadMaxAbsDiff": spread_diff, "totalMaxAbsDiff": total_diff},
        "excludedAlreadyStartedGameIds": sorted(set(g["gameId"] for g in slate["games"]) - {g["gameId"] for g in games}),
        "inputs": {"maxSourceWeek": max_week, "targetWeek": week, "sources": [sources[k] for k in ["nflverse-schedule", "nflverse-pbp"]] + fetched,
                   "captureManifestSha256": digest((capture / "manifest.json").read_bytes()),
                   "coverageLag": [{"team": t, "latestWeek": r["max_current_week_used"]} for t, r in cov.items()
                                   if r["max_current_week_used"] < teams[t]["max_current_season_week_used"]]},
        "limitations": "Existing core/coverage/Elo/margin spread and core total architecture; no new resource feature or coefficient promotion. No numerical injury, trade, weather or referee adjustment. No market lock or calibrated Week 9 win probability. Final pregame gates remain unresolved."})
    print(json.dumps({"season": season, "week": week, "games": len(games), "reproduction": [spread_diff, total_diff], "output": str(out)}, indent=2))


if __name__ == "__main__":
    main()
