#!/usr/bin/env python3
"""Build a leakage-safe NFL play-by-play feature snapshot for a target week.

Current production target: 2026 Week 6, using regular-season Weeks 1-5 only.
Outputs are development research inputs only. Nothing produced here is approved
for publication, release, or wager recommendations.
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

SEASON = 2026
TARGET_WEEK = 6
CUTOFF_WEEK = TARGET_WEEK - 1
PBP_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "pbp/play_by_play_2026.csv.gz"
)
OUT_DIR = Path("nfl_data/generated")

CORE_REQUIRED = {
    "season", "week", "season_type", "game_id", "posteam", "defteam",
    "play_type", "epa", "success", "yards_gained", "down", "qtr", "wp",
    "yardline_100", "qb_dropback", "rush_attempt", "sack", "interception",
    "fumble_lost", "no_play", "qb_kneel", "qb_spike",
}


def num(value: str | None) -> float | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in {"na", "nan", "none", "null"}:
        return None
    try:
        x = float(s)
        return x if math.isfinite(x) else None
    except ValueError:
        return None


def zero(value: str | None) -> float:
    x = num(value)
    return 0.0 if x is None else x


def truthy_num(value: str | None) -> bool:
    return zero(value) == 1.0


def safe_div(a: float, b: float) -> float | None:
    return None if not b else a / b


def rnd(value: float | None, digits: int = 4):
    return "" if value is None or not math.isfinite(value) else round(value, digits)


def stream_rows(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "cb-model-projections/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        with gzip.GzipFile(fileobj=resp) as gz:
            with io.TextIOWrapper(gz, encoding="utf-8-sig", newline="") as text:
                reader = csv.DictReader(text)
                fields = list(reader.fieldnames or [])
                missing = sorted(CORE_REQUIRED - set(fields))
                if missing:
                    raise RuntimeError(f"Missing expected nflverse PBP columns: {missing}")
                drive_col = "fixed_drive" if "fixed_drive" in fields else ("drive" if "drive" in fields else None)
                yield fields, drive_col, reader


def add_metric(bucket, name: str, value: float, weight: float = 1.0):
    bucket[f"{name}_sum"] += value * weight
    bucket[f"{name}_den"] += weight


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    offense = defaultdict(lambda: defaultdict(float))
    defense = defaultdict(lambda: defaultdict(float))
    offense_drives = defaultdict(set)
    defense_drives = defaultdict(set)
    games = defaultdict(set)
    all_eligible_teams = set()

    qa = {
        "season": SEASON,
        "target_week": TARGET_WEEK,
        "cutoff_week": CUTOFF_WEEK,
        "source": PBP_URL,
        "rows_scanned": 0,
        "rows_regular_season_through_cutoff": 0,
        "core_scrimmage_plays_used": 0,
        "pass_dropbacks_used": 0,
        "rush_attempts_used": 0,
        "neutral_early_down_plays_used": 0,
        "target_or_future_rows_used": 0,
        "max_week_used": 0,
        "drive_column": None,
        "release_state": "HOLD",
    }

    for fields, drive_col, reader in stream_rows(PBP_URL):
        qa["drive_column"] = drive_col
        for r in reader:
            qa["rows_scanned"] += 1
            season = int(zero(r.get("season")))
            week = int(zero(r.get("week")))
            if season != SEASON or str(r.get("season_type", "")).upper() != "REG":
                continue
            if not 1 <= week <= CUTOFF_WEEK:
                continue
            qa["rows_regular_season_through_cutoff"] += 1
            qa["max_week_used"] = max(qa["max_week_used"], week)
            if week >= TARGET_WEEK:
                qa["target_or_future_rows_used"] += 1

            posteam = str(r.get("posteam", "")).strip()
            defteam = str(r.get("defteam", "")).strip()
            if not posteam or not defteam:
                continue
            all_eligible_teams.update((posteam, defteam))
            game_id = str(r.get("game_id", "")).strip()
            games[posteam].add(game_id)
            games[defteam].add(game_id)

            if truthy_num(r.get("no_play")) or truthy_num(r.get("qb_kneel")) or truthy_num(r.get("qb_spike")):
                continue

            play_type = str(r.get("play_type", "")).strip().lower()
            dropback = truthy_num(r.get("qb_dropback"))
            rush = truthy_num(r.get("rush_attempt"))
            # Include official pass/run scrimmage plays; retain sacks as dropbacks.
            core_play = play_type in {"pass", "run"} or dropback or rush
            if not core_play:
                continue

            epa = num(r.get("epa"))
            success = num(r.get("success"))
            yards = num(r.get("yards_gained"))
            if epa is None:
                continue
            qa["core_scrimmage_plays_used"] += 1

            o = offense[posteam]
            d = defense[defteam]
            o["plays"] += 1
            d["plays"] += 1
            o["epa"] += epa
            d["epa"] += epa
            if success is not None:
                o["success_sum"] += success; o["success_den"] += 1
                d["success_sum"] += success; d["success_den"] += 1

            # Drive tracking on eligible offensive scrimmage plays.
            if drive_col:
                drv = str(r.get(drive_col, "")).strip()
                if drv:
                    key = (game_id, drv, posteam)
                    offense_drives[posteam].add(key)
                    defense_drives[defteam].add(key)

            # Passing / dropback layer.
            if dropback:
                qa["pass_dropbacks_used"] += 1
                o["dropbacks"] += 1; d["dropbacks"] += 1
                o["pass_epa"] += epa; d["pass_epa"] += epa
                if success is not None:
                    o["pass_success_sum"] += success; o["pass_success_den"] += 1
                    d["pass_success_sum"] += success; d["pass_success_den"] += 1
                if yards is not None and yards >= 20:
                    o["explosive_pass20"] += 1; d["explosive_pass20"] += 1
                if truthy_num(r.get("sack")):
                    o["sacks"] += 1; d["sacks"] += 1

            # Rushing layer. nflfastR rush_attempt excludes scrambles differently by definition;
            # keep this raw definition explicit and validate alternatives historically.
            if rush:
                qa["rush_attempts_used"] += 1
                o["rushes"] += 1; d["rushes"] += 1
                o["rush_epa"] += epa; d["rush_epa"] += epa
                if success is not None:
                    o["rush_success_sum"] += success; o["rush_success_den"] += 1
                    d["rush_success_sum"] += success; d["rush_success_den"] += 1
                if yards is not None and yards >= 10:
                    o["explosive_rush10"] += 1; d["explosive_rush10"] += 1

            # Turnover events on eligible scrimmage plays.
            turnover = truthy_num(r.get("interception")) or truthy_num(r.get("fumble_lost"))
            if turnover:
                o["turnovers"] += 1; d["turnovers"] += 1

            # Early-down play calling and neutral-script proxy.
            down = num(r.get("down"))
            qtr = num(r.get("qtr"))
            wp = num(r.get("wp"))
            if down in {1.0, 2.0}:
                o["early_down_plays"] += 1; d["early_down_plays"] += 1
                if dropback:
                    o["early_down_dropbacks"] += 1; d["early_down_dropbacks"] += 1
                if qtr is not None and qtr <= 3 and wp is not None and 0.20 <= wp <= 0.80:
                    qa["neutral_early_down_plays_used"] += 1
                    o["neutral_early_down_plays"] += 1; d["neutral_early_down_plays"] += 1
                    if dropback:
                        o["neutral_early_down_dropbacks"] += 1; d["neutral_early_down_dropbacks"] += 1

            # Red-zone layer.
            yardline = num(r.get("yardline_100"))
            if yardline is not None and yardline <= 20:
                o["rz_plays"] += 1; d["rz_plays"] += 1
                o["rz_epa"] += epa; d["rz_epa"] += epa
                if success is not None:
                    o["rz_success_sum"] += success; o["rz_success_den"] += 1
                    d["rz_success_sum"] += success; d["rz_success_den"] += 1

    if qa["target_or_future_rows_used"] != 0:
        raise RuntimeError(f"Leakage guard failed: {qa}")
    if qa["max_week_used"] != CUTOFF_WEEK:
        raise RuntimeError(f"Expected max week {CUTOFF_WEEK}, got {qa['max_week_used']}")
    if len(all_eligible_teams) != 32:
        raise RuntimeError(f"Expected 32 teams in eligible PBP, found {len(all_eligible_teams)}")

    records = []
    for team in sorted(all_eligible_teams):
        o = offense[team]; d = defense[team]
        odrives = len(offense_drives[team]); ddrives = len(defense_drives[team])
        records.append({
            "season": SEASON,
            "target_week": TARGET_WEEK,
            "data_through_week": CUTOFF_WEEK,
            "team": team,
            "games": len(games[team]),
            "off_plays": int(o["plays"]),
            "off_epa_per_play": rnd(safe_div(o["epa"], o["plays"])),
            "off_success_rate": rnd(safe_div(o["success_sum"], o["success_den"])),
            "off_dropbacks": int(o["dropbacks"]),
            "off_pass_epa_per_dropback": rnd(safe_div(o["pass_epa"], o["dropbacks"])),
            "off_pass_success_rate": rnd(safe_div(o["pass_success_sum"], o["pass_success_den"])),
            "off_explosive_pass20_rate": rnd(safe_div(o["explosive_pass20"], o["dropbacks"])),
            "off_sack_rate": rnd(safe_div(o["sacks"], o["dropbacks"])),
            "off_rushes": int(o["rushes"]),
            "off_rush_epa_per_attempt": rnd(safe_div(o["rush_epa"], o["rushes"])),
            "off_rush_success_rate": rnd(safe_div(o["rush_success_sum"], o["rush_success_den"])),
            "off_explosive_rush10_rate": rnd(safe_div(o["explosive_rush10"], o["rushes"])),
            "off_turnover_event_rate": rnd(safe_div(o["turnovers"], o["plays"])),
            "off_early_down_pass_rate": rnd(safe_div(o["early_down_dropbacks"], o["early_down_plays"])),
            "off_neutral_early_down_pass_rate_proxy": rnd(safe_div(o["neutral_early_down_dropbacks"], o["neutral_early_down_plays"])),
            "off_red_zone_epa_per_play": rnd(safe_div(o["rz_epa"], o["rz_plays"])),
            "off_red_zone_success_rate": rnd(safe_div(o["rz_success_sum"], o["rz_success_den"])),
            "off_drives": odrives,
            "off_plays_per_drive": rnd(safe_div(o["plays"], odrives), 3),
            "def_plays": int(d["plays"]),
            "def_epa_per_play_allowed": rnd(safe_div(d["epa"], d["plays"])),
            "def_success_rate_allowed": rnd(safe_div(d["success_sum"], d["success_den"])),
            "def_dropbacks": int(d["dropbacks"]),
            "def_pass_epa_per_dropback_allowed": rnd(safe_div(d["pass_epa"], d["dropbacks"])),
            "def_pass_success_rate_allowed": rnd(safe_div(d["pass_success_sum"], d["pass_success_den"])),
            "def_explosive_pass20_rate_allowed": rnd(safe_div(d["explosive_pass20"], d["dropbacks"])),
            "def_sack_rate_forced": rnd(safe_div(d["sacks"], d["dropbacks"])),
            "def_rushes_faced": int(d["rushes"]),
            "def_rush_epa_per_attempt_allowed": rnd(safe_div(d["rush_epa"], d["rushes"])),
            "def_rush_success_rate_allowed": rnd(safe_div(d["rush_success_sum"], d["rush_success_den"])),
            "def_explosive_rush10_rate_allowed": rnd(safe_div(d["explosive_rush10"], d["rushes"])),
            "def_takeaway_event_rate": rnd(safe_div(d["turnovers"], d["plays"])),
            "def_early_down_pass_rate_faced": rnd(safe_div(d["early_down_dropbacks"], d["early_down_plays"])),
            "def_neutral_early_down_pass_rate_faced_proxy": rnd(safe_div(d["neutral_early_down_dropbacks"], d["neutral_early_down_plays"])),
            "def_red_zone_epa_per_play_allowed": rnd(safe_div(d["rz_epa"], d["rz_plays"])),
            "def_red_zone_success_rate_allowed": rnd(safe_div(d["rz_success_sum"], d["rz_success_den"])),
            "def_drives_faced": ddrives,
            "def_plays_per_drive_faced": rnd(safe_div(d["plays"], ddrives), 3),
            "raw_net_epa_per_play": rnd(
                (safe_div(o["epa"], o["plays"]) or 0.0) -
                (safe_div(d["epa"], d["plays"]) or 0.0)
            ),
            "raw_net_success_rate": rnd(
                (safe_div(o["success_sum"], o["success_den"]) or 0.0) -
                (safe_div(d["success_sum"], d["success_den"]) or 0.0)
            ),
            "release_state": "HOLD",
            "model_use": "RESEARCH_INPUT_ONLY",
        })

    records.sort(key=lambda r: float(r["raw_net_epa_per_play"] or -999), reverse=True)
    out_csv = OUT_DIR / f"pbp_features_{SEASON}_week{TARGET_WEEK}_pregame.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader(); writer.writerows(records)

    qa.update({
        "teams_found": len(all_eligible_teams),
        "offense_teams_with_plays": len(offense),
        "defense_teams_with_plays": len(defense),
        "output_rows": len(records),
        "feature_rules": {
            "core_play": "play_type pass/run OR qb_dropback==1 OR rush_attempt==1; exclude no_play, kneel, spike",
            "success": "nflfastR success field",
            "explosive_pass_candidate": "yards_gained >= 20 on dropback",
            "explosive_rush_candidate": "yards_gained >= 10 on rush_attempt",
            "neutral_early_down_candidate": "down 1-2, qtr <= 3, wp between 0.20 and 0.80",
            "red_zone": "yardline_100 <= 20",
            "drive": qa["drive_column"],
        },
        "notes": [
            "All feature rows are restricted to regular-season Weeks 1-5 for a Week 6 pregame snapshot.",
            "Explosive and neutral-script thresholds are candidates and must be validated historically before coefficient use.",
            "Turnover rate is descriptive and should be regressed/shrunk before model use.",
            "Raw net EPA/success are diagnostics, not released power ratings.",
            "No value is approved for website publication or wager release.",
        ],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    })
    qa_path = OUT_DIR / f"pbp_qa_{SEASON}_week{TARGET_WEEK}_pregame.json"
    qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(qa, indent=2))
    print(f"Wrote {out_csv}")
    print(f"Wrote {qa_path}")


if __name__ == "__main__":
    main()
