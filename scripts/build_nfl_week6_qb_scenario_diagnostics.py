#!/usr/bin/env python3
"""Build Week 6 replacement-QB residual-state diagnostics.

This is deliberately NOT a point-adjustment model.

Why:
- The frozen Week 6 architecture already contains Weeks 1-5 team performance, so
  recent replacement-QB snaps are partly embedded in the team-state features.
- Historical QB-room variants did not earn promotion over the frozen baseline.
- A confirmed starter change is therefore a release gate / out-of-distribution
  condition, not permission to add a hand-set "QB points" number.

The script creates an auditable stress diagnostic for confirmed hard QB breaks:
1. Verify the named unavailable primary against the pregame QB-room snapshot.
2. Resolve the verified expected starter from the QB-room identities first.
3. If the named starter is not in the generic QB-room proxies, resolve that exact
   player from leakage-safe current-season pregame data, then prior-season data.
4. If identity/profile lineage still fails, fail closed and keep the frozen
   projection.
5. Report a FULL-EXTRAPOLATION passer-EPA stress margin for diagnostics only.
6. Never apply that stress result to the operational projection.

All outputs remain HOLD_RESEARCH_ONLY and website_publish_allowed=False.
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SEASON = 2026
WEEK = 6
ROOT = Path("nfl_data")
PROJ = ROOT / "generated/week6_research_projections.csv"
QB_ROOM = ROOT / "generated/qb_room_2026_week6_pregame.csv"
GATES = ROOT / "prospective/2026_week6_gate_inputs.json"
SCENARIO_INPUTS = ROOT / "prospective/2026_week6_qb_scenario_inputs.json"
QA = ROOT / "validation/qb_room_v1_qa.json"
OUT_JSON = ROOT / "prospective/week6_qb_scenario_diagnostics.json"
OUT_CSV = ROOT / "prospective/week6_qb_scenario_diagnostics.csv"
PLAYER_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/stats_player/"
    "stats_player_week_{season}.parquet"
)


def f(v):
    if v in (None, ""):
        return None
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def load_csv(path):
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def norm_name(v):
    return " ".join(str(v or "").strip().casefold().split())


def select_expected_prefix(qb, expected_name):
    """Return the QB-room prefix matching the verified expected starter."""
    target = norm_name(expected_name)
    for prefix in ("recent", "replacement", "primary"):
        if norm_name(qb.get(f"{prefix}_player_name")) == target:
            return prefix
    return None


def room_profile(qb, prefix):
    return {
        "player_name": qb.get(f"{prefix}_player_name"),
        "player_id": qb.get(f"{prefix}_player_id"),
        "profile_season": SEASON,
        "profile_team": qb.get("team"),
        "weeks": f(qb.get(f"{prefix}_weeks")),
        "first_week": f(qb.get(f"{prefix}_first_week")),
        "latest_week": f(qb.get(f"{prefix}_latest_week")),
        "dropbacks": f(qb.get(f"{prefix}_dropbacks")),
        "pass_epa": f(qb.get(f"{prefix}_pass_epa")),
        "pass_epa_per_db": f(qb.get(f"{prefix}_pass_epa_per_db")),
        "profile_source": f"QB_ROOM_{prefix.upper()}",
        "profile_source_url": None,
        "current_pregame_observed": True,
    }


def read_player_season(season, cache):
    if season in cache:
        return cache[season]
    url = PLAYER_URL.format(season=season)
    df = pd.read_parquet(url)
    needed = {
        "season", "week", "season_type", "player_id", "player_display_name",
        "team", "attempts", "sacks_suffered", "passing_epa",
    }
    missing = sorted(needed - set(df.columns))
    if missing:
        raise RuntimeError(f"Player stats {season} missing required columns: {missing}")
    df = df[
        (df["season_type"].astype(str).str.upper() == "REG")
        & (pd.to_numeric(df["week"], errors="coerce") > 0)
    ].copy()
    for col in ["week", "attempts", "sacks_suffered", "passing_epa"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["dropbacks"] = df["attempts"].fillna(0) + df["sacks_suffered"].fillna(0)
    df = df[df["dropbacks"] > 0].copy()
    df["_norm_name"] = df["player_display_name"].map(norm_name)
    cache[season] = (df, url)
    return cache[season]


def aggregate_exact_rows(df, season, source_label, source_url):
    if df.empty:
        return None
    # A display-name collision is extremely unlikely, but fail closed rather than
    # silently blending two player IDs if it ever occurs.
    ids = [str(x) for x in df["player_id"].dropna().astype(str).unique()]
    if len(ids) != 1:
        raise RuntimeError(f"Exact-name profile is ambiguous across player IDs: {ids}")
    attempts = float(df["attempts"].fillna(0).sum())
    sacks = float(df["sacks_suffered"].fillna(0).sum())
    dropbacks = attempts + sacks
    pass_epa = float(df["passing_epa"].fillna(0).sum())
    ordered = df.sort_values("week")
    return {
        "player_name": str(ordered.iloc[-1]["player_display_name"]),
        "player_id": ids[0],
        "profile_season": int(season),
        "profile_team": str(ordered.iloc[-1]["team"]),
        "weeks": int(df["week"].nunique()),
        "first_week": int(df["week"].min()),
        "latest_week": int(df["week"].max()),
        "dropbacks": round(dropbacks, 3),
        "pass_epa": round(pass_epa, 6),
        "pass_epa_per_db": None if dropbacks <= 0 else round(pass_epa / dropbacks, 6),
        "profile_source": source_label,
        "profile_source_url": source_url,
        "current_pregame_observed": bool(season == SEASON),
    }


def exact_named_profile(expected_name, team, cache):
    """Resolve named starter without letting generic backup rank mask identity.

    Search order is deliberately leakage safe:
    1. Exact player on the current team in current-season Weeks < target week.
    2. Exact player anywhere in current-season Weeks < target week (trade/new team).
    3. Exact player on the current team in the prior season.
    4. Exact player anywhere in the prior season (free-agent/acquisition history).
    """
    target = norm_name(expected_name)
    for season in (SEASON, SEASON - 1):
        df, url = read_player_season(season, cache)
        d = df[df["_norm_name"] == target].copy()
        if season == SEASON:
            d = d[d["week"] < WEEK].copy()
        same_team = d[d["team"].astype(str) == str(team)].copy()
        if not same_team.empty:
            label = "CURRENT_EXACT_PLAYER" if season == SEASON else "PRIOR_SEASON_EXACT_PLAYER"
            return aggregate_exact_rows(same_team, season, label, url)
        if not d.empty:
            label = (
                "CURRENT_EXACT_PLAYER_OTHER_TEAM"
                if season == SEASON
                else "PRIOR_SEASON_EXACT_PLAYER_OTHER_TEAM"
            )
            return aggregate_exact_rows(d, season, label, url)
    return None


def team_dropback_scale(qb):
    """Pregame team QB opportunity scale for stress display only.

    The current QB-room snapshot keeps only primary and observed replacement
    proxies. Their covered dropbacks divided by the latest source week provide a
    transparent magnitude scale; this is NOT a forecasted pass-attempt count.
    """
    primary_db = f(qb.get("primary_dropbacks")) or 0.0
    replacement_db = f(qb.get("replacement_dropbacks")) or 0.0
    source_weeks = f(qb.get("max_current_week_used"))
    if not source_weeks or source_weeks <= 0:
        return None
    return (primary_db + replacement_db) / source_weeks


def main():
    projections = {r["game_id"]: r for r in load_csv(PROJ)}
    qb_rows = {r["team"]: r for r in load_csv(QB_ROOM)}
    gates = json.loads(GATES.read_text(encoding="utf-8"))
    inputs = json.loads(SCENARIO_INPUTS.read_text(encoding="utf-8"))
    qb_qa = json.loads(QA.read_text(encoding="utf-8"))

    if inputs.get("season") != SEASON or inputs.get("week") != WEEK:
        raise RuntimeError("Scenario input season/week mismatch")

    baseline_spread_mae = f(qb_qa.get("baseline", {}).get("spread", {}).get("aggregate", {}).get("mae"))
    room_spread_mae = f(qb_qa.get("variants", {}).get("room", {}).get("spread", {}).get("aggregate", {}).get("mae"))
    primary_spread_mae = f(qb_qa.get("variants", {}).get("primary", {}).get("spread", {}).get("aggregate", {}).get("mae"))

    player_cache = {}
    rows = []
    for game_id, spec in inputs["games"].items():
        p = projections.get(game_id)
        if p is None:
            raise RuntimeError(f"Missing Week 6 projection for {game_id}")
        gate = gates.get("games", {}).get(game_id, {})
        team = spec["affected_team"]
        side = "home" if p["home_team"] == team else "away" if p["away_team"] == team else None
        if side is None:
            raise RuntimeError(f"Affected team {team} not in {game_id}")

        base_margin = f(p.get("rating_adjusted_home_margin"))
        base_total = f(p.get("pred_total"))
        qb = qb_rows.get(team)
        state = "PASS_QB_ROOM_IDENTITY_DIAGNOSTIC_ONLY"
        reason = "Verified expected starter is represented in the pregame QB-room snapshot."
        profile = None
        profile_error = None

        if "HARD_QB_BREAK" not in str(gate.get("personnel_state", "")):
            state = "FAIL_CLOSED_GATE_NOT_HARD_QB_BREAK"
            reason = "Prospective gate does not identify a hard confirmed QB break."
        elif qb is None:
            state = "FAIL_CLOSED_TEAM_MISSING_QB_ROOM"
            reason = "Affected team is absent from the pregame QB-room snapshot."
        elif norm_name(qb.get("primary_player_name")) != norm_name(spec["unavailable_primary"]):
            state = "FAIL_CLOSED_PRIMARY_IDENTITY_MISMATCH"
            reason = (
                f"Verified unavailable primary {spec['unavailable_primary']} does not match "
                f"QB-room primary {qb.get('primary_player_name')}."
            )
        else:
            prefix = select_expected_prefix(qb, spec["expected_starter"])
            if prefix is not None:
                profile = room_profile(qb, prefix)
            else:
                try:
                    profile = exact_named_profile(spec["expected_starter"], team, player_cache)
                except Exception as exc:  # fail closed on source/schema/identity ambiguity
                    profile_error = f"{type(exc).__name__}: {exc}"
                if profile is None:
                    state = (
                        "FAIL_CLOSED_PROFILE_SOURCE_UNAVAILABLE"
                        if profile_error
                        else "FAIL_CLOSED_EXPECTED_STARTER_PROFILE_NOT_FOUND"
                    )
                    reason = (
                        f"Verified expected starter {spec['expected_starter']} is not represented by "
                        "the QB-room proxies and no exact leakage-safe current/prior profile was resolved."
                    )
                else:
                    state = "PASS_EXACT_NAMED_PROFILE_DIAGNOSTIC_ONLY"
                    reason = (
                        f"Verified expected starter {spec['expected_starter']} was resolved by exact identity "
                        f"from {profile['profile_source']}."
                    )

        row = {
            "game_id": game_id,
            "away_team": p["away_team"],
            "home_team": p["home_team"],
            "affected_team": team,
            "affected_side": side,
            "unavailable_primary": spec["unavailable_primary"],
            "expected_starter": spec["expected_starter"],
            "personnel_state": gate.get("personnel_state", ""),
            "scenario_state": state,
            "scenario_reason": reason,
            "profile_resolution_error": profile_error,
            "expected_starter_profile_source": None if profile is None else profile.get("profile_source"),
            "expected_starter_profile_source_url": None if profile is None else profile.get("profile_source_url"),
            "expected_starter_profile_season": None if profile is None else profile.get("profile_season"),
            "expected_starter_profile_team": None if profile is None else profile.get("profile_team"),
            "expected_starter_profile_first_week": None if profile is None else profile.get("first_week"),
            "expected_starter_profile_latest_week": None if profile is None else profile.get("latest_week"),
            "base_home_margin": None if base_margin is None else round(base_margin, 3),
            "base_total": None if base_total is None else round(base_total, 3),
            "primary_pass_epa_per_db": None,
            "expected_starter_pass_epa_per_db": None,
            "raw_expected_minus_primary_epa_per_db": None,
            "expected_starter_observed_dropbacks": None,
            "team_qb_dropbacks_per_source_week_proxy": None,
            "full_extrapolation_raw_offensive_epa_swing": None,
            "full_extrapolation_stress_home_margin": None,
            "full_extrapolation_policy": "DIAGNOSTIC_STRESS_ONLY_NOT_A_PROJECTION",
            "current_history_already_contains_expected_starter_snaps": None,
            "operational_point_adjustment": 0.0,
            "operational_home_margin": None if base_margin is None else round(base_margin, 3),
            "operational_total": None if base_total is None else round(base_total, 3),
            "adjustment_policy": "ZERO_UNTIL_QB_EFFECT_EARNS_HISTORICAL_VALIDATION",
            "recommendation": "HOLD",
            "release_state": "HOLD_RESEARCH_ONLY",
            "website_publish_allowed": False,
        }

        if profile is not None and qb is not None and base_margin is not None:
            primary_epa = f(qb.get("primary_pass_epa_per_db"))
            expected_epa = f(profile.get("pass_epa_per_db"))
            expected_db = f(profile.get("dropbacks"))
            covered_per_week = team_dropback_scale(qb)

            row["primary_pass_epa_per_db"] = None if primary_epa is None else round(primary_epa, 6)
            row["expected_starter_pass_epa_per_db"] = None if expected_epa is None else round(expected_epa, 6)
            row["expected_starter_observed_dropbacks"] = None if expected_db is None else round(expected_db, 1)
            row["current_history_already_contains_expected_starter_snaps"] = bool(
                profile.get("current_pregame_observed") and expected_db and expected_db > 0
            )
            if covered_per_week is not None:
                row["team_qb_dropbacks_per_source_week_proxy"] = round(covered_per_week, 3)

            if primary_epa is not None and expected_epa is not None:
                gap = expected_epa - primary_epa
                row["raw_expected_minus_primary_epa_per_db"] = round(gap, 6)
                if covered_per_week is not None:
                    raw_swing = gap * covered_per_week
                    # Positive offensive swing benefits the affected team.
                    stress_margin = base_margin + raw_swing if side == "home" else base_margin - raw_swing
                    row["full_extrapolation_raw_offensive_epa_swing"] = round(raw_swing, 3)
                    row["full_extrapolation_stress_home_margin"] = round(stress_margin, 3)

        rows.append(row)

    qa_summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "season": SEASON,
        "week": WEEK,
        "games": len(rows),
        "pass_resolved": sum(r["scenario_state"].startswith("PASS_") for r in rows),
        "fail_closed": sum(r["scenario_state"].startswith("FAIL_CLOSED") for r in rows),
        "exact_named_fallbacks": sum(r["scenario_state"] == "PASS_EXACT_NAMED_PROFILE_DIAGNOSTIC_ONLY" for r in rows),
        "qb_validation_baseline_spread_mae": baseline_spread_mae,
        "qb_validation_primary_spread_mae": primary_spread_mae,
        "qb_validation_room_spread_mae": room_spread_mae,
        "qb_validation_interpretation": "QB variants did not earn production promotion; no scenario point adjustment is authorized.",
        "double_count_guard": "Current Weeks 1-5 team state already contains observed replacement snaps where they occurred.",
        "exact_identity_policy": "Verified starter name overrides generic backup rank for diagnostics; current pregame exact profile is preferred, then prior-season exact player history.",
        "release_state": "HOLD_RESEARCH_ONLY",
        "website_publish_allowed": False,
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(qa_summary, indent=2) + "\n", encoding="utf-8")

    fields = list(rows[0])
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(json.dumps({
        "json": str(OUT_JSON),
        "csv": str(OUT_CSV),
        "pass_resolved": qa_summary["pass_resolved"],
        "fail_closed": qa_summary["fail_closed"],
        "exact_named_fallbacks": qa_summary["exact_named_fallbacks"],
        "release_state": qa_summary["release_state"],
    }, indent=2))


if __name__ == "__main__":
    main()
