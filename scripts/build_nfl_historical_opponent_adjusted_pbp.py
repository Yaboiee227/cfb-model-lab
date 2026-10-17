#!/usr/bin/env python3
"""Build leakage-safe historical opponent-adjusted NFL PBP ratings.

Research purpose only.  For each target season/week (2022-2025, Weeks 1-18),
this script calculates offensive and defensive PBP strengths using only games
from earlier weeks in the same season.  The completed prior season is also
rated separately to provide an explicit early-season prior.

Model convention for every metric:
    centered observed performance = offense_strength - defense_strength

All transformed metrics are oriented so that higher is better for the offense.
For sacks, the observed metric is negative sack rate ("sack avoidance").
Therefore a positive defensive strength always means better prevention, and a
positive offensive strength always means better offense.

Nothing written by this script is approved for wager release or website use.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import math
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

CONTEXT_SEASONS = [2021, 2022, 2023, 2024, 2025]
TARGET_SEASONS = [2022, 2023, 2024, 2025]
TARGET_WEEKS = list(range(1, 19))
OUT_DIR = Path("nfl_data/historical")
PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz"
SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"

RECENCY_DECAY_PER_WEEK = 0.90
MAX_ITERATIONS = 400
TOLERANCE = 1e-10

# Ridge units are metric-denominator equivalents, not games.  These are
# conservative research settings; validation may later reject or retune them.
METRICS = {
    "epa": {"numerator": "epa", "denominator": "plays", "ridge": 140.0},
    "success": {"numerator": "success", "denominator": "success_n", "ridge": 140.0},
    "pass_epa": {"numerator": "pass_epa", "denominator": "dropbacks", "ridge": 90.0},
    "rush_epa": {"numerator": "rush_epa", "denominator": "rushes", "ridge": 70.0},
    "pass_expl": {"numerator": "pass20", "denominator": "dropbacks", "ridge": 90.0},
    "rush_expl": {"numerator": "rush10", "denominator": "rushes", "ridge": 70.0},
    "sack_avoid": {"numerator": "neg_sacks", "denominator": "dropbacks", "ridge": 90.0},
}

REQUIRED_PBP = {
    "season", "week", "season_type", "game_id", "posteam", "defteam",
    "play_type", "epa", "success", "yards_gained", "qb_dropback",
    "rush_attempt", "sack", "qb_kneel", "qb_spike",
}


def num(v):
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() in {"na", "nan", "none", "null"}:
        return None
    try:
        x = float(s)
        return x if math.isfinite(x) else None
    except ValueError:
        return None


def z(v):
    x = num(v)
    return 0.0 if x is None else x


def flag(v):
    return z(v) == 1.0


def safe_div(a, b):
    return None if not b else a / b


def rnd(v, n=6):
    return "" if v is None or not math.isfinite(v) else round(v, n)


def fetch_text(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "cb-model-projections/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8-sig")


def fetch_schedule():
    return list(csv.DictReader(io.StringIO(fetch_text(SCHEDULE_URL)))


def empty_bucket():
    return defaultdict(float)


def process_pbp_season(season, qa):
    """Return team-offense game observations from raw PBP."""
    url = PBP_URL.format(season=season)
    req = urllib.request.Request(url, headers={"User-Agent": "cb-model-projections/1.0"})
    games = defaultdict(empty_bucket)
    scanned = used = 0
    with urllib.request.urlopen(req, timeout=240) as resp:
        with gzip.GzipFile(fileobj=resp) as gz:
            with io.TextIOWrapper(gz, encoding="utf-8-sig", newline="") as text:
                reader = csv.DictReader(text)
                fields = set(reader.fieldnames or [])
                missing = sorted(REQUIRED_PBP - fields)
                if missing:
                    raise RuntimeError(f"{season} PBP missing columns: {missing}")
                has_no_play = "no_play" in fields
                for r in reader:
                    scanned += 1
                    if int(z(r.get("season"))) != season:
                        continue
                    if str(r.get("season_type", "")).upper().strip() != "REG":
                        continue
                    week = int(z(r.get("week")))
                    posteam = str(r.get("posteam", "")).strip()
                    defteam = str(r.get("defteam", "")).strip()
                    game_id = str(r.get("game_id", "")).strip()
                    if week < 1 or not posteam or not defteam or not game_id or posteam == defteam:
                        continue
                    play_type = str(r.get("play_type", "")).strip().lower()
                    if play_type == "no_play" or (has_no_play and flag(r.get("no_play"))):
                        continue
                    if flag(r.get("qb_kneel")) or flag(r.get("qb_spike")):
                        continue
                    dropback = flag(r.get("qb_dropback"))
                    rush = flag(r.get("rush_attempt"))
                    if not (play_type in {"pass", "run"} or dropback or rush):
                        continue
                    epa = num(r.get("epa"))
                    if epa is None:
                        continue
                    success = num(r.get("success"))
                    yards = num(r.get("yards_gained"))
                    key = (week, game_id, posteam, defteam)
                    b = games[key]
                    b["plays"] += 1
                    b["epa"] += epa
                    if success is not None:
                        b["success"] += success
                        b["success_n"] += 1
                    if dropback:
                        b["dropbacks"] += 1
                        b["pass_epa"] += epa
                        if yards is not None and yards >= 20:
                            b["pass20"] += 1
                        if flag(r.get("sack")):
                            b["sacks"] += 1
                            b["neg_sacks"] -= 1
                    if rush:
                        b["rushes"] += 1
                        b["rush_epa"] += epa
                        if yards is not None and yards >= 10:
                            b["rush10"] += 1
                    used += 1

    observations = []
    teams = set()
    for (week, game_id, offense, defense), b in games.items():
        rec = {
            "season": season,
            "week": week,
            "game_id": game_id,
            "offense": offense,
            "defense": defense,
        }
        rec.update(dict(b))
        observations.append(rec)
        teams.update((offense, defense))
    observations.sort(key=lambda r: (r["week"], r["game_id"], r["offense"]))
    qa[str(season)] = {
        "rows_scanned": scanned,
        "plays_used": used,
        "team_game_observations": len(observations),
        "teams": len(teams),
    }
    if len(teams) != 32:
        raise RuntimeError(f"Expected 32 teams in {season}, found {len(teams)}")
    return observations, teams


def fit_metric(observations, teams, metric_name, cutoff_week=None, reference_week=None):
    """Fit alternating ridge offense/defense strengths for one metric."""
    cfg = METRICS[metric_name]
    numerator = cfg["numerator"]
    denominator = cfg["denominator"]
    ridge = float(cfg["ridge"])

    usable = []
    for r in observations:
        if cutoff_week is not None and r["week"] >= cutoff_week:
            continue
        den = float(r.get(denominator, 0.0) or 0.0)
        if den <= 0:
            continue
        value = float(r.get(numerator, 0.0) or 0.0) / den
        if reference_week is None:
            recency = 1.0
        else:
            recency = RECENCY_DECAY_PER_WEEK ** max(0, reference_week - 1 - int(r["week"]))
        weight = den * recency
        usable.append((r["offense"], r["defense"], value, weight, int(r["week"])))

    if not usable:
        return {
            "baseline": None,
            "offense": {t: 0.0 for t in teams},
            "defense": {t: 0.0 for t in teams},
            "converged": True,
            "iterations": 0,
            "max_delta": 0.0,
            "max_source_week": 0,
            "observations": 0,
        }

    total_w = sum(w for _, _, _, w, _ in usable)
    baseline = sum(value * w for _, _, value, w, _ in usable) / total_w
    by_off = defaultdict(list)
    by_def = defaultdict(list)
    for off, deff, value, weight, _ in usable:
        centered = value - baseline
        by_off[off].append((deff, centered, weight))
        by_def[deff].append((off, centered, weight))

    offense = {t: 0.0 for t in teams}
    defense = {t: 0.0 for t in teams}
    converged = False
    max_delta = None
    iterations = 0
    for iteration in range(1, MAX_ITERATIONS + 1):
        next_off = {}
        for team in teams:
            rows_t = by_off.get(team, [])
            den = ridge + sum(w for _, _, w in rows_t)
            next_off[team] = (
                sum(w * (y + defense[opp]) for opp, y, w in rows_t) / den
                if den else 0.0
            )
        next_def = {}
        for team in teams:
            rows_t = by_def.get(team, [])
            den = ridge + sum(w for _, _, w in rows_t)
            next_def[team] = (
                sum(w * (next_off[opp] - y) for opp, y, w in rows_t) / den
                if den else 0.0
            )
        max_delta = max(
            max(abs(next_off[t] - offense[t]) for t in teams),
            max(abs(next_def[t] - defense[t]) for t in teams),
        )
        offense, defense = next_off, next_def
        iterations = iteration
        if max_delta <= TOLERANCE:
            converged = True
            break
    if not converged:
        raise RuntimeError(
            f"{metric_name} adjustment failed to converge after {MAX_ITERATIONS} iterations"
        )
    return {
        "baseline": baseline,
        "offense": offense,
        "defense": defense,
        "converged": converged,
        "iterations": iterations,
        "max_delta": max_delta,
        "max_source_week": max(w for *_, w in usable),
        "observations": len(usable),
    }


def games_before(observations, target_week):
    by_team = defaultdict(set)
    for r in observations:
        if r["week"] >= target_week:
            continue
        by_team[r["offense"]].add(r["game_id"])
        by_team[r["defense"]].add(r["game_id"])
    return {t: len(g) for t, g in by_team.items()}


def full_prior_ratings(observations, teams):
    # reference_week=19 recency-weights the completed regular season toward its end.
    return {
        metric: fit_metric(observations, teams, metric, cutoff_week=None, reference_week=19)
        for metric in METRICS
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    qa = {
        "architecture": "weekly alternating ridge opponent adjustment on game-level PBP observations",
        "context_seasons": CONTEXT_SEASONS,
        "target_seasons": TARGET_SEASONS,
        "target_weeks": [min(TARGET_WEEKS), max(TARGET_WEEKS)],
        "recency_decay_per_week": RECENCY_DECAY_PER_WEEK,
        "metric_ridge_denominator_units": {k: v["ridge"] for k, v in METRICS.items()},
        "release_state": "HOLD",
        "model_use": "HISTORICAL_RESEARCH_ONLY",
    }

    season_data = {}
    season_teams = {}
    for season in CONTEXT_SEASONS:
        obs, teams = process_pbp_season(season, qa)
        season_data[season] = obs
        season_teams[season] = teams

    prior_final = {
        season: full_prior_ratings(season_data[season], season_teams[season])
        for season in CONTEXT_SEASONS
    }

    team_week_rows = []
    convergence_checks = 0
    max_source_week_used = 0
    leakage_violations = 0
    for season in TARGET_SEASONS:
        obs = season_data[season]
        teams = sorted(season_teams[season])
        previous = prior_final[season - 1]
        for target_week in TARGET_WEEKS:
            ratings = {
                metric: fit_metric(
                    obs, teams, metric,
                    cutoff_week=target_week,
                    reference_week=target_week,
                )
                for metric in METRICS
            }
            g_before = games_before(obs, target_week)
            source_week = max((r["week"] for r in obs if r["week"] < target_week), default=0)
            if source_week >= target_week:
                leakage_violations += 1
            max_source_week_used = max(max_source_week_used, source_week)
            convergence_checks += len(ratings)
            for team in teams:
                row = {
                    "season": season,
                    "target_week": target_week,
                    "team": team,
                    "games_before": g_before.get(team, 0),
                    "max_current_season_week_used": source_week,
                }
                for metric in METRICS:
                    cur = ratings[metric]
                    prior = previous[metric]
                    row[f"adj_{metric}_off"] = rnd(cur["offense"][team])
                    row[f"adj_{metric}_def_prevention"] = rnd(cur["defense"][team])
                    row[f"adj_{metric}_net"] = rnd(cur["offense"][team] + cur["defense"][team])
                    row[f"prior_adj_{metric}_off"] = rnd(prior["offense"].get(team, 0.0))
                    row[f"prior_adj_{metric}_def_prevention"] = rnd(prior["defense"].get(team, 0.0))
                    row[f"prior_adj_{metric}_net"] = rnd(
                        prior["offense"].get(team, 0.0) + prior["defense"].get(team, 0.0)
                    )
                row["release_state"] = "HISTORICAL_RESEARCH"
                team_week_rows.append(row)

    if leakage_violations:
        raise RuntimeError(f"Leakage violations found: {leakage_violations}")

    team_path = OUT_DIR / "team_week_opponent_adjusted_pbp_2022_2025.csv"
    with team_path.open("w", newline="", encoding="utf-8") as fobj:
        writer = csv.DictWriter(fobj, fieldnames=list(team_week_rows[0].keys()))
        writer.writeheader()
        writer.writerows(team_week_rows)

    snapshots = {
        (int(r["season"]), int(r["target_week"]), r["team"]): r
        for r in team_week_rows
    }
    schedule = fetch_schedule()
    game_rows = []
    missing_snapshots = 0
    for r in schedule:
        season = int(z(r.get("season")))
        week = int(z(r.get("week")))
        if season not in TARGET_SEASONS or week not in TARGET_WEEKS:
            continue
        if str(r.get("game_type", "")).upper().strip() != "REG":
            continue
        home = str(r.get("home_team", "")).strip()
        away = str(r.get("away_team", "")).strip()
        if not home or not away:
            continue
        h = snapshots.get((season, week, home))
        a = snapshots.get((season, week, away))
        if h is None or a is None:
            missing_snapshots += 1
            continue
        out = {
            "game_id": r.get("game_id", ""),
            "season": season,
            "week": week,
            "gameday": r.get("gameday", ""),
            "away_team": away,
            "home_team": home,
            "home_games_before": h["games_before"],
            "away_games_before": a["games_before"],
            "home_max_current_season_week_used": h["max_current_season_week_used"],
            "away_max_current_season_week_used": a["max_current_season_week_used"],
        }
        for metric in METRICS:
            for suffix in ("off", "def_prevention", "net"):
                key = f"adj_{metric}_{suffix}"
                prior_key = f"prior_adj_{metric}_{suffix}"
                out[f"home_{key}"] = h[key]
                out[f"away_{key}"] = a[key]
                out[f"home_{prior_key}"] = h[prior_key]
                out[f"away_{prior_key}"] = a[prior_key]
                hv = num(h[key]); av = num(a[key])
                hp = num(h[prior_key]); ap = num(a[prior_key])
                out[f"diff_{key}"] = rnd((hv or 0.0) - (av or 0.0))
                out[f"diff_{prior_key}"] = rnd((hp or 0.0) - (ap or 0.0))
        out["release_state"] = "HISTORICAL_RESEARCH"
        game_rows.append(out)

    if missing_snapshots:
        raise RuntimeError(f"Missing opponent-adjusted game snapshots: {missing_snapshots}")

    game_path = OUT_DIR / "game_opponent_adjusted_pbp_2022_2025.csv"
    with game_path.open("w", newline="", encoding="utf-8") as fobj:
        writer = csv.DictWriter(fobj, fieldnames=list(game_rows[0].keys()))
        writer.writeheader()
        writer.writerows(game_rows)

    qa.update({
        "team_week_rows": len(team_week_rows),
        "historical_game_rows": len(game_rows),
        "missing_game_snapshots": missing_snapshots,
        "leakage_violations": leakage_violations,
        "max_current_season_source_week_used": max_source_week_used,
        "convergence_checks_completed": convergence_checks,
        "leakage_rule": "all current-season observations must have week < target_week",
        "prior_rule": "prior_adj_* uses only the completed immediately preceding regular season",
        "metric_orientation": "higher offense and higher defense-prevention are both better; sack metric is negative sack rate",
        "files": [str(team_path), str(game_path)],
        "notes": [
            "Current-season ratings are recency weighted and shrunk with denominator-equivalent ridge priors.",
            "Prior-season opponent-adjusted ratings are exported separately; no hard blend is imposed by this builder.",
            "No market lines, scores from the target game, injuries, weather, or future games enter these ratings.",
            "Validation must determine whether these features improve spread or total forecasting before production use.",
            "No output authorizes website publication or wager release."
        ],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    })
    qa_path = OUT_DIR / "opponent_adjusted_pbp_build_qa.json"
    qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(qa, indent=2))
    print(team_path)
    print(game_path)
    print(qa_path)


if __name__ == "__main__":
    main()
