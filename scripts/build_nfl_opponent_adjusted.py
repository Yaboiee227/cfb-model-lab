#!/usr/bin/env python3
"""Build leakage-safe, opponent-adjusted NFL efficiency ratings for a target week.

Current research target: 2026 Week 6, using regular-season Weeks 1-5 only.
This script reads the already-frozen weekly team-stat snapshot from
nfl_data/generated/, performs recency weighting + ridge shrinkage + iterative
opponent adjustment, and writes development-only outputs.

Nothing produced here is approved for website publication or wager release.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SEASON = 2026
TARGET_WEEK = 6
CUTOFF_WEEK = TARGET_WEEK - 1
INPUT_PATH = Path(f"nfl_data/generated/team_stats_{SEASON}_w1_{CUTOFF_WEEK}_raw.csv")
OUT_DIR = Path("nfl_data/generated")

# Candidate research parameters. These are intentionally explicit and remain
# unapproved until historical walk-forward validation selects or rejects them.
RECENCY_DECAY_PER_WEEK = 0.88
RIDGE_EQUIVALENT_PLAYS = 120.0
MAX_ITERATIONS = 500
CONVERGENCE_TOLERANCE = 1e-10


def num(value: str | None) -> float:
    if value is None:
        return 0.0
    s = str(value).strip()
    if not s or s.lower() in {"na", "nan", "none", "null"}:
        return 0.0
    try:
        x = float(s)
        return x if math.isfinite(x) else 0.0
    except ValueError:
        return 0.0


def safe_div(a: float, b: float) -> float | None:
    return None if not b else a / b


def rnd(value: float | None, digits: int = 4):
    return "" if value is None or not math.isfinite(value) else round(value, digits)


def weighted_mean(pairs: list[tuple[float, float]]) -> float | None:
    den = sum(w for _, w in pairs)
    return None if den <= 0 else sum(v * w for v, w in pairs) / den


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not INPUT_PATH.exists():
        raise RuntimeError(f"Missing frozen input: {INPUT_PATH}")

    with INPUT_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = set(reader.fieldnames or [])
        rows = list(reader)

    required = {
        "season", "week", "team", "season_type", "game_id", "opponent_team",
        "attempts", "sacks_suffered", "passing_epa", "carries", "rushing_epa",
    }
    missing = sorted(required - fields)
    if missing:
        raise RuntimeError(f"Missing required input columns: {missing}")

    eligible = []
    future_rows = 0
    bad_rows = 0
    duplicate_keys = 0
    seen_keys = set()

    for r in rows:
        season = int(num(r.get("season")))
        week = int(num(r.get("week")))
        season_type = str(r.get("season_type", "")).upper().strip()
        if season != SEASON or season_type != "REG":
            continue
        if week >= TARGET_WEEK:
            future_rows += 1
            continue
        if week < 1:
            bad_rows += 1
            continue
        team = str(r.get("team", "")).strip()
        opp = str(r.get("opponent_team", "")).strip()
        if not team or not opp or team == opp:
            bad_rows += 1
            continue
        key = (str(r.get("game_id", "")).strip(), team, week)
        if key in seen_keys:
            duplicate_keys += 1
            continue
        seen_keys.add(key)
        eligible.append(r)

    if future_rows != 0:
        raise RuntimeError(f"Leakage guard failed: {future_rows} target/future rows in frozen input")
    if not eligible:
        raise RuntimeError("No eligible pregame rows found")

    max_week = max(int(num(r.get("week"))) for r in eligible)
    if max_week != CUTOFF_WEEK:
        raise RuntimeError(f"Expected max week {CUTOFF_WEEK}, found {max_week}")
    if duplicate_keys:
        raise RuntimeError(f"Duplicate team-game rows found: {duplicate_keys}")

    # Each weekly team row becomes one offensive observation against that week's
    # opponent. Weight = scrimmage-play proxy * recency decay.
    observations: list[dict[str, float | int | str]] = []
    teams = set()
    games_by_team = defaultdict(set)
    raw_plays_by_team = defaultdict(float)
    weighted_plays_by_team = defaultdict(float)

    for r in eligible:
        team = str(r["team"]).strip()
        opp = str(r["opponent_team"]).strip()
        week = int(num(r.get("week")))
        attempts = num(r.get("attempts"))
        sacks = num(r.get("sacks_suffered"))
        carries = num(r.get("carries"))
        plays = attempts + sacks + carries
        total_epa = num(r.get("passing_epa")) + num(r.get("rushing_epa"))
        if plays <= 0:
            bad_rows += 1
            continue
        epp = total_epa / plays
        recency = RECENCY_DECAY_PER_WEEK ** (CUTOFF_WEEK - week)
        weight = plays * recency
        game_id = str(r.get("game_id", "")).strip() or f"{SEASON}-{week}-{team}-{opp}"
        observations.append({
            "team": team,
            "opp": opp,
            "week": week,
            "game_id": game_id,
            "plays": plays,
            "epp": epp,
            "recency": recency,
            "weight": weight,
        })
        teams.update((team, opp))
        games_by_team[team].add(game_id)
        games_by_team[opp].add(game_id)
        raw_plays_by_team[team] += plays
        weighted_plays_by_team[team] += weight

    if len(teams) != 32:
        raise RuntimeError(f"Expected 32 NFL teams, found {len(teams)}")

    # Overall weighted scoring-environment intercept. The iterative strengths are
    # centered around this baseline by using y = observed EPA/play - league mean.
    league_mean = weighted_mean([(float(o["epp"]), float(o["weight"])) for o in observations])
    if league_mean is None:
        raise RuntimeError("Could not calculate league EPA/play baseline")

    by_offense = defaultdict(list)
    by_defense = defaultdict(list)
    for o in observations:
        y = float(o["epp"]) - league_mean
        w = float(o["weight"])
        by_offense[str(o["team"])].append((str(o["opp"]), y, w))
        by_defense[str(o["opp"])].append((str(o["team"]), y, w))

    # Model: centered observed EPA/play = offense_strength - defense_strength.
    # Alternating ridge updates shrink both units toward league average (0) and
    # avoid overreacting to five-week samples.
    offense = {team: 0.0 for team in teams}
    defense = {team: 0.0 for team in teams}
    converged = False
    max_delta = None
    iterations = 0

    for iteration in range(1, MAX_ITERATIONS + 1):
        next_offense = {}
        for team in teams:
            obs = by_offense[team]
            den = RIDGE_EQUIVALENT_PLAYS + sum(w for _, _, w in obs)
            nume = sum(w * (y + defense[opp]) for opp, y, w in obs)
            next_offense[team] = nume / den if den else 0.0

        next_defense = {}
        for team in teams:
            obs = by_defense[team]
            den = RIDGE_EQUIVALENT_PLAYS + sum(w for _, _, w in obs)
            nume = sum(w * (next_offense[opp_offense] - y) for opp_offense, y, w in obs)
            next_defense[team] = nume / den if den else 0.0

        max_delta = max(
            max(abs(next_offense[t] - offense[t]) for t in teams),
            max(abs(next_defense[t] - defense[t]) for t in teams),
        )
        offense, defense = next_offense, next_defense
        iterations = iteration
        if max_delta <= CONVERGENCE_TOLERANCE:
            converged = True
            break

    if not converged:
        raise RuntimeError(f"Opponent adjustment did not converge after {MAX_ITERATIONS} iterations")

    # Diagnostics and ranking. Defense is expressed as EPA/play prevention, so
    # positive is good on both sides of the ball; net = offense + defense.
    raw_off = {}
    raw_def = {}
    off_opp_def = {}
    def_opp_off = {}
    sos = {}

    for team in teams:
        off_pairs = [(y + league_mean, w) for _, y, w in by_offense[team]]
        def_pairs = [(-(y), w) for _, y, w in by_defense[team]]
        raw_off[team] = weighted_mean(off_pairs)
        raw_def[team] = weighted_mean(def_pairs)
        off_opp_def[team] = weighted_mean([(defense[opp], w) for opp, _, w in by_offense[team]])
        def_opp_off[team] = weighted_mean([(offense[opp], w) for opp, _, w in by_defense[team]])

        opp_quality_pairs = []
        for opp, _, w in by_offense[team]:
            opp_quality_pairs.append((offense[opp] + defense[opp], w))
        sos[team] = weighted_mean(opp_quality_pairs)

    order = sorted(teams, key=lambda t: offense[t] + defense[t], reverse=True)
    rank = {team: i + 1 for i, team in enumerate(order)}

    records = []
    for team in order:
        eff_plays = weighted_plays_by_team[team]
        reliability = eff_plays / (eff_plays + RIDGE_EQUIVALENT_PLAYS) if eff_plays >= 0 else 0.0
        records.append({
            "season": SEASON,
            "target_week": TARGET_WEEK,
            "data_through_week": CUTOFF_WEEK,
            "team": team,
            "games": len(games_by_team[team]),
            "raw_off_plays": int(round(raw_plays_by_team[team])),
            "recency_weighted_off_plays": rnd(eff_plays, 1),
            "reliability_proxy": rnd(reliability, 3),
            "league_epa_per_play_baseline": rnd(league_mean),
            "raw_off_epa_per_play": rnd(raw_off[team]),
            "raw_def_epa_prevention_per_play_centered": rnd(raw_def[team]),
            "avg_opponent_def_strength_for_offense": rnd(off_opp_def[team]),
            "avg_opponent_off_strength_for_defense": rnd(def_opp_off[team]),
            "adj_off_epa_per_play_above_average": rnd(offense[team]),
            "adj_def_epa_prevention_per_play_above_average": rnd(defense[team]),
            "adj_net_epa_per_play_above_average": rnd(offense[team] + defense[team]),
            "schedule_strength_net_epa_proxy": rnd(sos[team]),
            "research_power_rank": rank[team],
            "release_state": "HOLD",
            "model_use": "RESEARCH_INPUT_ONLY",
        })

    out_csv = OUT_DIR / f"opponent_adjusted_{SEASON}_week{TARGET_WEEK}_pregame.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    qa = {
        "season": SEASON,
        "target_week": TARGET_WEEK,
        "cutoff_week": CUTOFF_WEEK,
        "input": str(INPUT_PATH),
        "eligible_rows": len(eligible),
        "observations_used": len(observations),
        "teams_found": len(teams),
        "min_games_per_team": min(len(games_by_team[t]) for t in teams),
        "max_games_per_team": max(len(games_by_team[t]) for t in teams),
        "max_week_used": max_week,
        "target_or_future_rows_used": 0,
        "duplicate_team_game_rows": duplicate_keys,
        "bad_rows_skipped": bad_rows,
        "league_epa_per_play_baseline": round(league_mean, 6),
        "parameters": {
            "recency_decay_per_week": RECENCY_DECAY_PER_WEEK,
            "ridge_equivalent_plays": RIDGE_EQUIVALENT_PLAYS,
            "model_equation": "centered observed EPA/play = offense_strength - defense_strength",
        },
        "convergence": {
            "converged": converged,
            "iterations": iterations,
            "max_delta": max_delta,
            "tolerance": CONVERGENCE_TOLERANCE,
        },
        "release_state": "HOLD",
        "model_use": "RESEARCH_INPUT_ONLY",
        "notes": [
            "All inputs are restricted to regular-season Weeks 1-5 for a Week 6 pregame snapshot.",
            "Recency decay and ridge strength are candidate parameters and require historical walk-forward selection/validation.",
            "Opponent adjustment is iterative and uses no target-week or future observations.",
            "Research power rank is diagnostic only; it is not a spread, total, moneyline, alt-line, or wager recommendation.",
            "No output is approved for website publication or public release.",
        ],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    qa_path = OUT_DIR / f"opponent_adjusted_qa_{SEASON}_week{TARGET_WEEK}_pregame.json"
    qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(qa, indent=2))
    print(f"Wrote {out_csv}")
    print(f"Wrote {qa_path}")


if __name__ == "__main__":
    main()
