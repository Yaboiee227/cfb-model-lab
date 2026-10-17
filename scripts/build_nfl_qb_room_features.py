#!/usr/bin/env python3
"""Build leakage-safe QB-room features for NFL spread/total research.

This layer intentionally avoids using the target game's realized starting QB.
Historical rows are based only on player performance observed before the target
week. The output names the cumulative and recent *primary QB proxies* plus an
observed room/replacement proxy. A later timestamped depth-chart/injury layer
will map the expected starter/backup known before kickoff.

Development only. No website output and no predictive weight is implied.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

CURRENT_SEASON = 2026
TARGET_WEEK = 6
CUTOFF_WEEK = TARGET_WEEK - 1
CONTEXT_SEASONS = list(range(2021, CURRENT_SEASON + 1))
HISTORICAL_TARGET_SEASONS = [2022, 2023, 2024, 2025]
PLAYER_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/stats_player/"
    "stats_player_week_{season}.parquet"
)
NGS_PASS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/nextgen_stats/"
    "ngs_passing.parquet"
)
GEN_DIR = Path("nfl_data/generated")
HIST_DIR = Path("nfl_data/historical")

PLAYER_REQUIRED = {
    "season", "week", "season_type", "player_id", "player_display_name", "team",
    "attempts", "completions", "passing_yards", "passing_tds",
    "passing_interceptions", "sacks_suffered", "passing_epa", "passing_cpoe",
    "carries", "rushing_yards", "rushing_epa",
}

NGS_REQUIRED = {
    "season", "week", "season_type", "player_gsis_id", "team_abbr", "attempts",
    "avg_time_to_throw", "avg_intended_air_yards", "aggressiveness",
    "avg_air_yards_to_sticks", "expected_completion_percentage",
    "completion_percentage_above_expectation",
}


def fnum(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def safe_div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def rnd(v, n=6):
    if v is None or not math.isfinite(v):
        return None
    return round(v, n)


def read_player_stats():
    frames = []
    schema = {}
    for season in CONTEXT_SEASONS:
        url = PLAYER_URL.format(season=season)
        df = pd.read_parquet(url)
        missing = sorted(PLAYER_REQUIRED - set(df.columns))
        if missing:
            raise RuntimeError(f"Player stats {season} missing required columns: {missing}")
        position_col = "position_group" if "position_group" in df.columns else (
            "position" if "position" in df.columns else None
        )
        if position_col is None:
            raise RuntimeError(f"Player stats {season} has no position/position_group column")
        df = df[
            (df["season_type"].astype(str).str.upper() == "REG")
            & (pd.to_numeric(df["week"], errors="coerce") > 0)
            & (df[position_col].astype(str).str.upper() == "QB")
        ].copy()
        for col in [
            "attempts", "completions", "passing_yards", "passing_tds",
            "passing_interceptions", "sacks_suffered", "passing_epa",
            "passing_cpoe", "carries", "rushing_yards", "rushing_epa",
        ]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["dropbacks"] = df["attempts"].fillna(0) + df["sacks_suffered"].fillna(0)
        # Remove rows without meaningful QB opportunity while retaining low-volume backups.
        df = df[df["dropbacks"] > 0].copy()
        frames.append(df)
        schema[str(season)] = {
            "rows": int(len(df)),
            "teams": int(df["team"].nunique()),
            "players": int(df["player_id"].nunique()),
            "position_column": position_col,
        }
    return pd.concat(frames, ignore_index=True), schema


def read_ngs_passing():
    df = pd.read_parquet(NGS_PASS_URL)
    missing = sorted(NGS_REQUIRED - set(df.columns))
    if missing:
        raise RuntimeError(f"NGS passing missing required columns: {missing}")
    df = df[
        (df["season_type"].astype(str).str.upper() == "REG")
        & (pd.to_numeric(df["season"], errors="coerce").isin(CONTEXT_SEASONS))
        & (pd.to_numeric(df["week"], errors="coerce") > 0)
    ].copy()
    for col in [
        "attempts", "avg_time_to_throw", "avg_intended_air_yards", "aggressiveness",
        "avg_air_yards_to_sticks", "expected_completion_percentage",
        "completion_percentage_above_expectation",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def merge_weekly(player, ngs):
    ngs_cols = [
        "season", "week", "player_gsis_id", "team_abbr", "attempts",
        "avg_time_to_throw", "avg_intended_air_yards", "aggressiveness",
        "avg_air_yards_to_sticks", "expected_completion_percentage",
        "completion_percentage_above_expectation",
    ]
    n = ngs[ngs_cols].rename(columns={
        "player_gsis_id": "player_id",
        "team_abbr": "ngs_team",
        "attempts": "ngs_attempts",
        "completion_percentage_above_expectation": "ngs_cpoe",
        "expected_completion_percentage": "ngs_xcomp",
    })
    out = player.merge(n, how="left", on=["season", "week", "player_id"])
    out["ngs_team_match"] = out["ngs_team"].isna() | (out["team"] == out["ngs_team"])
    # If an unusual midweek/team mapping disagrees, preserve official player stats
    # and null NGS for that row rather than joining ambiguous tracking data.
    bad = ~out["ngs_team_match"]
    for col in [
        "ngs_attempts", "avg_time_to_throw", "avg_intended_air_yards",
        "aggressiveness", "avg_air_yards_to_sticks", "ngs_xcomp", "ngs_cpoe",
    ]:
        out.loc[bad, col] = math.nan
    return out


def aggregate_player_rows(df):
    """Return cumulative QB metrics from a set of prior weekly rows."""
    if df.empty:
        return None
    attempts = float(df["attempts"].fillna(0).sum())
    sacks = float(df["sacks_suffered"].fillna(0).sum())
    dropbacks = attempts + sacks
    carries = float(df["carries"].fillna(0).sum())
    pass_epa = float(df["passing_epa"].fillna(0).sum())
    rush_epa = float(df["rushing_epa"].fillna(0).sum())
    ints = float(df["passing_interceptions"].fillna(0).sum())

    # Weekly passing_cpoe is attempt-based; weight it by attempts.
    cpoe_mask = df["passing_cpoe"].notna() & (df["attempts"].fillna(0) > 0)
    cpoe_den = float(df.loc[cpoe_mask, "attempts"].sum())
    cpoe = None
    if cpoe_den > 0:
        cpoe = float(
            (df.loc[cpoe_mask, "passing_cpoe"] * df.loc[cpoe_mask, "attempts"]).sum()
            / cpoe_den
        )

    def weighted_ngs(col):
        mask = df[col].notna() & (df["ngs_attempts"].fillna(0) > 0)
        den = float(df.loc[mask, "ngs_attempts"].sum())
        if den <= 0:
            return None, 0.0
        val = float((df.loc[mask, col] * df.loc[mask, "ngs_attempts"]).sum() / den)
        return val, den

    tt, tt_n = weighted_ngs("avg_time_to_throw")
    iay, iay_n = weighted_ngs("avg_intended_air_yards")
    agg, agg_n = weighted_ngs("aggressiveness")
    ayts, ayts_n = weighted_ngs("avg_air_yards_to_sticks")
    xcomp, xcomp_n = weighted_ngs("ngs_xcomp")
    ngs_cpoe, ngs_cpoe_n = weighted_ngs("ngs_cpoe")

    latest_week = int(df["week"].max())
    first_week = int(df["week"].min())
    name = str(df.sort_values("week").iloc[-1]["player_display_name"])
    team = str(df.sort_values("week").iloc[-1]["team"])
    player_id = str(df.iloc[0]["player_id"])
    return {
        "player_id": player_id,
        "player_name": name,
        "team": team,
        "weeks": int(df["week"].nunique()),
        "first_week": first_week,
        "latest_week": latest_week,
        "attempts": rnd(attempts, 3),
        "dropbacks": rnd(dropbacks, 3),
        "pass_epa": rnd(pass_epa),
        "pass_epa_per_db": rnd(safe_div(pass_epa, dropbacks)),
        "cpoe": rnd(cpoe),
        "int_rate": rnd(safe_div(ints, attempts)),
        "sack_rate": rnd(safe_div(sacks, dropbacks)),
        "rush_epa": rnd(rush_epa),
        "rush_epa_per_carry": rnd(safe_div(rush_epa, carries)),
        "rush_carries": rnd(carries, 3),
        "ngs_time_to_throw": rnd(tt),
        "ngs_iay": rnd(iay),
        "ngs_aggressiveness": rnd(agg),
        "ngs_ayts": rnd(ayts),
        "ngs_xcomp": rnd(xcomp),
        "ngs_cpoe": rnd(ngs_cpoe),
        "ngs_attempts_time_to_throw": rnd(tt_n, 3),
        "ngs_attempts_iay": rnd(iay_n, 3),
        "ngs_attempts_aggressiveness": rnd(agg_n, 3),
        "ngs_attempts_ayts": rnd(ayts_n, 3),
        "ngs_attempts_xcomp": rnd(xcomp_n, 3),
        "ngs_attempts_cpoe": rnd(ngs_cpoe_n, 3),
    }


def build_player_pool(weekly, season, team, before_week=None, weeks=None):
    d = weekly[(weekly["season"] == season) & (weekly["team"] == team)].copy()
    if before_week is not None:
        d = d[d["week"] < before_week]
    if weeks is not None:
        d = d[d["week"].isin(weeks)]
    pool = []
    for _, pdf in d.groupby("player_id", sort=False):
        m = aggregate_player_rows(pdf)
        if m is not None:
            pool.append(m)
    pool.sort(key=lambda x: (-(x["dropbacks"] or 0), -(x["latest_week"] or 0), x["player_id"]))
    return pool


def recent_primary(weekly, season, team, target_week):
    d = weekly[
        (weekly["season"] == season)
        & (weekly["team"] == team)
        & (weekly["week"] < target_week)
    ].copy()
    if d.empty:
        return None
    # Most recent played week with a QB dropback, then the QB with most dropbacks in that week.
    latest = int(d["week"].max())
    w = d[d["week"] == latest].copy()
    w["db"] = w["attempts"].fillna(0) + w["sacks_suffered"].fillna(0)
    if w.empty:
        return None
    pid = str(w.sort_values(["db", "attempts"], ascending=False).iloc[0]["player_id"])
    hist = d[d["player_id"] == pid]
    return aggregate_player_rows(hist)


def prefix_player(prefix, player):
    fields = [
        "player_id", "player_name", "weeks", "first_week", "latest_week", "attempts",
        "dropbacks", "pass_epa", "pass_epa_per_db", "cpoe", "int_rate", "sack_rate",
        "rush_epa", "rush_epa_per_carry", "rush_carries", "ngs_time_to_throw", "ngs_iay",
        "ngs_aggressiveness", "ngs_ayts", "ngs_xcomp", "ngs_cpoe",
        "ngs_attempts_time_to_throw", "ngs_attempts_iay", "ngs_attempts_aggressiveness",
        "ngs_attempts_ayts", "ngs_attempts_xcomp", "ngs_attempts_cpoe",
    ]
    if player is None:
        return {f"{prefix}{field}": None for field in fields}
    return {f"{prefix}{field}": player.get(field) for field in fields}


def make_snapshot(weekly, season, target_week, team):
    current_pool = build_player_pool(weekly, season, team, before_week=target_week)
    prior_pool = build_player_pool(weekly, season - 1, team)
    cumulative_primary = current_pool[0] if current_pool else (prior_pool[0] if prior_pool else None)
    current_backup = current_pool[1] if len(current_pool) > 1 else None
    prior_backup = prior_pool[1] if len(prior_pool) > 1 else None
    observed_replacement = current_backup or prior_backup
    recent = recent_primary(weekly, season, team, target_week)
    if recent is None:
        recent = cumulative_primary

    primary_source = "CURRENT_PRIOR_WEEKS" if current_pool else (
        "PRIOR_SEASON_TEAM_PROXY" if prior_pool else "NO_OBSERVED_QB"
    )
    replacement_source = "CURRENT_PRIOR_WEEKS_SECONDARY" if current_backup else (
        "PRIOR_SEASON_TEAM_SECONDARY" if prior_backup else "LEAGUE_REPLACEMENT_NEEDED"
    )
    changed = bool(
        cumulative_primary and recent
        and cumulative_primary["player_id"] != recent["player_id"]
    )
    raw_delta = None
    if cumulative_primary and observed_replacement:
        a, b = cumulative_primary.get("pass_epa_per_db"), observed_replacement.get("pass_epa_per_db")
        if a is not None and b is not None:
            raw_delta = a - b

    max_week = 0
    d = weekly[(weekly["season"] == season) & (weekly["team"] == team) & (weekly["week"] < target_week)]
    if not d.empty:
        max_week = int(d["week"].max())

    return {
        "season": season,
        "target_week": target_week,
        "team": team,
        "max_current_week_used": max_week,
        "primary_proxy_source": primary_source,
        "replacement_proxy_source": replacement_source,
        "recent_primary_differs_from_cumulative": changed,
        "raw_primary_minus_replacement_epa_per_db": rnd(raw_delta),
        **prefix_player("primary_", cumulative_primary),
        **prefix_player("recent_", recent),
        **prefix_player("replacement_", observed_replacement),
        "release_state": "HOLD_RESEARCH_ONLY",
    }


def teams_by_season(weekly, season):
    # Use player data plus prior-season teams so Week 1 has a row for every continuing franchise.
    current = set(weekly.loc[weekly["season"] == season, "team"].dropna().astype(str))
    prior = set(weekly.loc[weekly["season"] == season - 1, "team"].dropna().astype(str))
    teams = sorted(current | prior)
    if len(teams) != 32:
        raise RuntimeError(f"Expected 32 teams for {season}; found {len(teams)}: {teams}")
    return teams


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise RuntimeError(f"Refusing to write empty output {path}")
    fields, seen = [], set()
    for row in rows:
        for key in row:
            if key not in seen:
                fields.append(key)
                seen.add(key)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{k: "" if v is None else v for k, v in r.items()} for r in rows])


def main():
    GEN_DIR.mkdir(parents=True, exist_ok=True)
    HIST_DIR.mkdir(parents=True, exist_ok=True)

    player, player_schema = read_player_stats()
    ngs = read_ngs_passing()
    weekly = merge_weekly(player, ngs)

    historical = []
    leakage_count = 0
    for season in HISTORICAL_TARGET_SEASONS:
        teams = teams_by_season(weekly, season)
        for target_week in range(1, 19):
            for team in teams:
                row = make_snapshot(weekly, season, target_week, team)
                if row["max_current_week_used"] >= target_week:
                    leakage_count += 1
                historical.append(row)

    current = [
        make_snapshot(weekly, CURRENT_SEASON, TARGET_WEEK, team)
        for team in teams_by_season(weekly, CURRENT_SEASON)
    ]
    current_future = sum(1 for r in current if r["max_current_week_used"] >= TARGET_WEEK)

    expected_hist = len(HISTORICAL_TARGET_SEASONS) * 18 * 32
    if len(historical) != expected_hist or leakage_count or current_future:
        raise RuntimeError(
            f"QB-room QA failed: hist={len(historical)}/{expected_hist}, "
            f"historical_leakage={leakage_count}, current_future={current_future}"
        )

    # Join-rate diagnostic for NGS tracking data. NGS is thresholded, so incomplete join
    # coverage is expected; the important rule is that missing NGS never becomes zero.
    qb_week_rows = int(len(weekly))
    ngs_join_rows = int(weekly["ngs_attempts"].notna().sum())
    ngs_team_mismatch_rows = int((~weekly["ngs_team_match"]).sum())

    hist_path = HIST_DIR / "team_week_qb_room_2022_2025.csv"
    cur_path = GEN_DIR / f"qb_room_{CURRENT_SEASON}_week{TARGET_WEEK}_pregame.csv"
    qa_path = GEN_DIR / f"qb_room_qa_{CURRENT_SEASON}_week{TARGET_WEEK}_pregame.json"
    write_csv(hist_path, historical)
    write_csv(cur_path, current)

    current_sources = defaultdict(int)
    replacement_sources = defaultdict(int)
    recent_switches = 0
    for row in current:
        current_sources[row["primary_proxy_source"]] += 1
        replacement_sources[row["replacement_proxy_source"]] += 1
        recent_switches += int(bool(row["recent_primary_differs_from_cumulative"]))

    qa = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_week": TARGET_WEEK,
        "current_season": CURRENT_SEASON,
        "current_rows": len(current),
        "historical_rows": len(historical),
        "expected_historical_rows": expected_hist,
        "historical_target_or_future_rows_used": leakage_count,
        "current_target_or_future_rows_used": current_future,
        "weekly_qb_rows_2021_2026": qb_week_rows,
        "ngs_joined_weekly_qb_rows": ngs_join_rows,
        "ngs_join_rate": rnd(ngs_join_rows / qb_week_rows if qb_week_rows else None),
        "ngs_team_mismatch_rows_nulled": ngs_team_mismatch_rows,
        "player_source_schema": player_schema,
        "current_primary_proxy_sources": dict(current_sources),
        "current_replacement_proxy_sources": dict(replacement_sources),
        "current_recent_primary_switch_flags": recent_switches,
        "historical_safety_note": (
            "No target-game realized starter is used. Primary/replacement identities are inferred only from prior observed QB opportunity."
        ),
        "replacement_note": (
            "Observed secondary QB is a proxy, not necessarily the listed current backup. Depth/injury data must override prospectively."
        ),
        "release_state": "HOLD_RESEARCH_ONLY",
        "website_publish_allowed": False,
    }
    with qa_path.open("w", encoding="utf-8") as fh:
        json.dump(qa, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(json.dumps({
        "historical_output": str(hist_path),
        "current_output": str(cur_path),
        "qa_output": str(qa_path),
        "current_rows": len(current),
        "historical_rows": len(historical),
        "ngs_join_rate": qa["ngs_join_rate"],
        "release_state": qa["release_state"],
    }, indent=2))


if __name__ == "__main__":
    main()
