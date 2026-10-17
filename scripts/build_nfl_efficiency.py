#!/usr/bin/env python3
"""Build an NFL pregame efficiency snapshot without future-week leakage.

Current production target: 2026 Week 6, using REG Weeks 1-5 only.
This script intentionally does NOT publish anything to the website. It writes only
under nfl_data/generated/ on the isolated nfl-model-development branch.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SEASON = 2026
TARGET_WEEK = 6
CUTOFF_WEEK = TARGET_WEEK - 1
TEAM_STATS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "stats_team/stats_team_week_2026.csv"
)
SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
OUT_DIR = Path("nfl_data/generated")


def fetch_csv(url: str) -> tuple[list[dict[str, str]], list[str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "cb-model-projections/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        text = resp.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader), list(reader.fieldnames or [])


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


def round_or_blank(value: float | None, digits: int = 4):
    return "" if value is None or not math.isfinite(value) else round(value, digits)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    team_rows, team_fields = fetch_csv(TEAM_STATS_URL)
    sched_rows, _ = fetch_csv(SCHEDULE_URL)

    required = {
        "season", "week", "team", "season_type", "game_id", "opponent_team",
        "attempts", "sacks_suffered", "passing_epa", "passing_cpoe",
        "carries", "rushing_epa",
    }
    missing = sorted(required - set(team_fields))
    if missing:
        raise RuntimeError(f"Missing expected nflverse team-stat columns: {missing}")

    eligible = [
        r for r in team_rows
        if int(num(r.get("season"))) == SEASON
        and str(r.get("season_type", "")).upper() == "REG"
        and 1 <= int(num(r.get("week"))) <= CUTOFF_WEEK
    ]
    if not eligible:
        raise RuntimeError("No eligible Weeks 1-5 team-stat rows found")
    if any(int(num(r.get("week"))) >= TARGET_WEEK for r in eligible):
        raise RuntimeError("Leakage guard failed: target/future week present")

    # Preserve the exact pregame-safe source rows used for the snapshot.
    raw_path = OUT_DIR / f"team_stats_{SEASON}_w1_{CUTOFF_WEEK}_raw.csv"
    with raw_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=team_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(eligible)

    off = defaultdict(lambda: defaultdict(float))
    deff = defaultdict(lambda: defaultdict(float))
    opponents = defaultdict(list)
    games_seen = defaultdict(set)

    for r in eligible:
        team = r["team"].strip()
        opp = r["opponent_team"].strip()
        if not team or not opp:
            continue
        week = int(num(r.get("week")))
        game_id = r.get("game_id", "")
        games_seen[team].add(game_id or f"{week}-{opp}")
        opponents[team].append(opp)

        attempts = num(r.get("attempts"))
        sacks = num(r.get("sacks_suffered"))
        dropbacks = attempts + sacks
        carries = num(r.get("carries"))
        pass_epa = num(r.get("passing_epa"))
        rush_epa = num(r.get("rushing_epa"))
        cpoe = num(r.get("passing_cpoe"))
        pass20 = num(r.get("passing_20"))
        rush20 = num(r.get("rushing_20"))

        o = off[team]
        o["dropbacks"] += dropbacks
        o["attempts"] += attempts
        o["carries"] += carries
        o["pass_epa"] += pass_epa
        o["rush_epa"] += rush_epa
        o["cpoe_weighted"] += cpoe * attempts
        o["pass20"] += pass20
        o["rush20"] += rush20

        # The opponent's defensive allowance is the current row's offense.
        d = deff[opp]
        d["dropbacks"] += dropbacks
        d["attempts"] += attempts
        d["carries"] += carries
        d["pass_epa"] += pass_epa
        d["rush_epa"] += rush_epa
        d["pass20"] += pass20
        d["rush20"] += rush20

    # Add scoreboard scoring summaries using only completed REG games <= cutoff.
    pf = defaultdict(float)
    pa = defaultdict(float)
    score_games = defaultdict(int)
    for r in sched_rows:
        if int(num(r.get("season"))) != SEASON:
            continue
        if str(r.get("game_type", "")).upper() != "REG":
            continue
        week = int(num(r.get("week")))
        if not 1 <= week <= CUTOFF_WEEK:
            continue
        home, away = r.get("home_team", ""), r.get("away_team", "")
        hs, aws = r.get("home_score", ""), r.get("away_score", "")
        if not home or not away or str(hs).strip() == "" or str(aws).strip() == "":
            continue
        h, a = num(hs), num(aws)
        pf[home] += h; pa[home] += a; score_games[home] += 1
        pf[away] += a; pa[away] += h; score_games[away] += 1

    teams = sorted(set(off) | set(deff))
    raw_net = {}
    base = {}
    for team in teams:
        o, d = off[team], deff[team]
        oplays = o["dropbacks"] + o["carries"]
        dplays = d["dropbacks"] + d["carries"]
        off_epa = safe_div(o["pass_epa"] + o["rush_epa"], oplays)
        def_epa = safe_div(d["pass_epa"] + d["rush_epa"], dplays)
        net = None if off_epa is None or def_epa is None else off_epa - def_epa
        raw_net[team] = net if net is not None else 0.0
        base[team] = (off_epa, def_epa, oplays, dplays)

    records = []
    for team in teams:
        o, d = off[team], deff[team]
        off_epa, def_epa, oplays, dplays = base[team]
        opp_vals = [raw_net[x] for x in opponents[team] if x in raw_net]
        opp_net = sum(opp_vals) / len(opp_vals) if opp_vals else None
        g = max(len(games_seen[team]), score_games[team])
        record = {
            "season": SEASON,
            "target_week": TARGET_WEEK,
            "data_through_week": CUTOFF_WEEK,
            "team": team,
            "games": g,
            "off_plays_proxy": int(oplays),
            "off_epa_per_play_proxy": round_or_blank(off_epa),
            "off_pass_epa_per_dropback": round_or_blank(safe_div(o["pass_epa"], o["dropbacks"])),
            "off_rush_epa_per_carry": round_or_blank(safe_div(o["rush_epa"], o["carries"])),
            "off_cpoe": round_or_blank(safe_div(o["cpoe_weighted"], o["attempts"]), 3),
            "off_explosive20_rate_proxy": round_or_blank(safe_div(o["pass20"] + o["rush20"], oplays)),
            "points_for_pg": round_or_blank(safe_div(pf[team], score_games[team]), 2),
            "def_plays_proxy": int(dplays),
            "def_epa_per_play_allowed_proxy": round_or_blank(def_epa),
            "def_pass_epa_per_dropback_allowed": round_or_blank(safe_div(d["pass_epa"], d["dropbacks"])),
            "def_rush_epa_per_carry_allowed": round_or_blank(safe_div(d["rush_epa"], d["carries"])),
            "def_explosive20_rate_allowed_proxy": round_or_blank(safe_div(d["pass20"] + d["rush20"], dplays)),
            "points_against_pg": round_or_blank(safe_div(pa[team], score_games[team]), 2),
            "raw_net_epa_per_play_proxy": round_or_blank(raw_net[team]),
            "raw_net_points_pg": round_or_blank(safe_div(pf[team] - pa[team], score_games[team]), 2),
            "avg_opponent_raw_net_epa_proxy": round_or_blank(opp_net),
            "release_state": "HOLD",
            "model_use": "RESEARCH_INPUT_ONLY",
        }
        records.append(record)

    # Sort for inspection only; this is not a released power rating.
    records.sort(key=lambda r: float(r["raw_net_epa_per_play_proxy"] or -999), reverse=True)
    eff_path = OUT_DIR / f"team_efficiency_{SEASON}_week{TARGET_WEEK}_pregame.csv"
    with eff_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader(); writer.writerows(records)

    qa = {
        "season": SEASON,
        "target_week": TARGET_WEEK,
        "cutoff_week": CUTOFF_WEEK,
        "team_stat_rows_used": len(eligible),
        "teams_found": len(teams),
        "max_week_used": max(int(num(r.get("week"))) for r in eligible),
        "target_or_future_rows_used": sum(int(num(r.get("week"))) >= TARGET_WEEK for r in eligible),
        "team_stats_source": TEAM_STATS_URL,
        "schedule_source": SCHEDULE_URL,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "release_state": "HOLD",
        "notes": [
            "Efficiency values are first-pass proxies from weekly team summary stats.",
            "Defense is reconstructed from each opponent's offensive weekly row.",
            "Success rate, neutral-situation pace, drive efficiency, and true play-level explosiveness require the PBP layer and are not claimed here.",
            "No Week 6 team-stat row is used in this Week 6 pregame snapshot.",
            "No value in this output is approved for website publication or wager release.",
        ],
    }
    (OUT_DIR / f"qa_{SEASON}_week{TARGET_WEEK}_pregame.json").write_text(
        json.dumps(qa, indent=2) + "\n", encoding="utf-8"
    )

    if len(teams) != 32:
        raise RuntimeError(f"Expected 32 NFL teams, found {len(teams)}")
    if qa["target_or_future_rows_used"] != 0 or qa["max_week_used"] != CUTOFF_WEEK:
        raise RuntimeError(f"Pregame leakage QA failed: {qa}")

    print(json.dumps(qa, indent=2))
    print(f"Wrote {raw_path}")
    print(f"Wrote {eff_path}")


if __name__ == "__main__":
    main()
