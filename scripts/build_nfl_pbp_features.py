#!/usr/bin/env python3
"""Build a leakage-safe NFL PBP feature snapshot for 2026 Week 6.

Only 2026 regular-season Weeks 1-5 are eligible. Outputs are development-only,
HOLD research inputs and are never written to the live website path.
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
CUTOFF_WEEK = 5
PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2026.csv.gz"
OUT_DIR = Path("nfl_data/generated")

# `no_play` is not present in every nflverse PBP schema/version. When absent,
# play_type == "no_play" is the nullified-play guard instead.
CORE_REQUIRED = {
    "season", "week", "season_type", "game_id", "posteam", "defteam",
    "play_type", "epa", "success", "yards_gained", "down", "qtr", "wp",
    "yardline_100", "qb_dropback", "rush_attempt", "sack", "interception",
    "fumble_lost", "qb_kneel", "qb_spike",
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


def div(a, b):
    return None if not b else a / b


def rnd(v, n=4):
    return "" if v is None or not math.isfinite(v) else round(v, n)


def rows_from_gzip(url):
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


def rate(bucket, num_key, den_key):
    return rnd(div(bucket[num_key], bucket[den_key]))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    off = defaultdict(lambda: defaultdict(float))
    deff = defaultdict(lambda: defaultdict(float))
    off_drives = defaultdict(set)
    def_drives = defaultdict(set)
    games = defaultdict(set)
    teams = set()

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
        "no_play_column_present": False,
        "release_state": "HOLD",
    }

    for fields, drive_col, reader in rows_from_gzip(PBP_URL):
        qa["drive_column"] = drive_col
        qa["no_play_column_present"] = "no_play" in fields
        for r in reader:
            qa["rows_scanned"] += 1
            if int(z(r.get("season"))) != SEASON or str(r.get("season_type", "")).upper() != "REG":
                continue
            week = int(z(r.get("week")))
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
            teams.update((posteam, defteam))
            game_id = str(r.get("game_id", "")).strip()
            games[posteam].add(game_id)
            games[defteam].add(game_id)

            play_type = str(r.get("play_type", "")).strip().lower()
            nullified = play_type == "no_play" or (qa["no_play_column_present"] and flag(r.get("no_play")))
            if nullified or flag(r.get("qb_kneel")) or flag(r.get("qb_spike")):
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
            qa["core_scrimmage_plays_used"] += 1

            o, d = off[posteam], deff[defteam]
            o["plays"] += 1; d["plays"] += 1
            o["epa"] += epa; d["epa"] += epa
            if success is not None:
                o["success"] += success; o["success_n"] += 1
                d["success"] += success; d["success_n"] += 1

            if drive_col:
                drive = str(r.get(drive_col, "")).strip()
                if drive:
                    key = (game_id, drive, posteam)
                    off_drives[posteam].add(key)
                    def_drives[defteam].add(key)

            if dropback:
                qa["pass_dropbacks_used"] += 1
                o["dropbacks"] += 1; d["dropbacks"] += 1
                o["pass_epa"] += epa; d["pass_epa"] += epa
                if success is not None:
                    o["pass_success"] += success; o["pass_success_n"] += 1
                    d["pass_success"] += success; d["pass_success_n"] += 1
                if yards is not None and yards >= 20:
                    o["pass20"] += 1; d["pass20"] += 1
                if flag(r.get("sack")):
                    o["sacks"] += 1; d["sacks"] += 1

            if rush:
                qa["rush_attempts_used"] += 1
                o["rushes"] += 1; d["rushes"] += 1
                o["rush_epa"] += epa; d["rush_epa"] += epa
                if success is not None:
                    o["rush_success"] += success; o["rush_success_n"] += 1
                    d["rush_success"] += success; d["rush_success_n"] += 1
                if yards is not None and yards >= 10:
                    o["rush10"] += 1; d["rush10"] += 1

            if flag(r.get("interception")) or flag(r.get("fumble_lost")):
                o["turnovers"] += 1; d["turnovers"] += 1

            down, qtr, wp = num(r.get("down")), num(r.get("qtr")), num(r.get("wp"))
            if down in {1.0, 2.0}:
                o["ed"] += 1; d["ed"] += 1
                if dropback:
                    o["ed_pass"] += 1; d["ed_pass"] += 1
                if qtr is not None and qtr <= 3 and wp is not None and 0.20 <= wp <= 0.80:
                    qa["neutral_early_down_plays_used"] += 1
                    o["neutral_ed"] += 1; d["neutral_ed"] += 1
                    if dropback:
                        o["neutral_ed_pass"] += 1; d["neutral_ed_pass"] += 1

            yardline = num(r.get("yardline_100"))
            if yardline is not None and yardline <= 20:
                o["rz"] += 1; d["rz"] += 1
                o["rz_epa"] += epa; d["rz_epa"] += epa
                if success is not None:
                    o["rz_success"] += success; o["rz_success_n"] += 1
                    d["rz_success"] += success; d["rz_success_n"] += 1

    if qa["target_or_future_rows_used"] != 0 or qa["max_week_used"] != CUTOFF_WEEK:
        raise RuntimeError(f"Pregame leakage QA failed: {qa}")
    if len(teams) != 32:
        raise RuntimeError(f"Expected 32 teams, found {len(teams)}")

    output = []
    for team in sorted(teams):
        o, d = off[team], deff[team]
        od, dd = len(off_drives[team]), len(def_drives[team])
        off_epa = div(o["epa"], o["plays"])
        def_epa = div(d["epa"], d["plays"])
        off_sr = div(o["success"], o["success_n"])
        def_sr = div(d["success"], d["success_n"])
        output.append({
            "season": SEASON, "target_week": TARGET_WEEK, "data_through_week": CUTOFF_WEEK,
            "team": team, "games": len(games[team]),
            "off_plays": int(o["plays"]), "off_epa_per_play": rnd(off_epa), "off_success_rate": rnd(off_sr),
            "off_dropbacks": int(o["dropbacks"]), "off_pass_epa_per_dropback": rnd(div(o["pass_epa"], o["dropbacks"])),
            "off_pass_success_rate": rnd(div(o["pass_success"], o["pass_success_n"])),
            "off_explosive_pass20_rate": rnd(div(o["pass20"], o["dropbacks"])), "off_sack_rate": rnd(div(o["sacks"], o["dropbacks"])),
            "off_rushes": int(o["rushes"]), "off_rush_epa_per_attempt": rnd(div(o["rush_epa"], o["rushes"])),
            "off_rush_success_rate": rnd(div(o["rush_success"], o["rush_success_n"])),
            "off_explosive_rush10_rate": rnd(div(o["rush10"], o["rushes"])),
            "off_turnover_event_rate": rnd(div(o["turnovers"], o["plays"])),
            "off_early_down_pass_rate": rnd(div(o["ed_pass"], o["ed"])),
            "off_neutral_early_down_pass_rate_proxy": rnd(div(o["neutral_ed_pass"], o["neutral_ed"])),
            "off_red_zone_epa_per_play": rnd(div(o["rz_epa"], o["rz"])),
            "off_red_zone_success_rate": rnd(div(o["rz_success"], o["rz_success_n"])),
            "off_drives": od, "off_plays_per_drive": rnd(div(o["plays"], od), 3),
            "def_plays": int(d["plays"]), "def_epa_per_play_allowed": rnd(def_epa), "def_success_rate_allowed": rnd(def_sr),
            "def_dropbacks": int(d["dropbacks"]), "def_pass_epa_per_dropback_allowed": rnd(div(d["pass_epa"], d["dropbacks"])),
            "def_pass_success_rate_allowed": rnd(div(d["pass_success"], d["pass_success_n"])),
            "def_explosive_pass20_rate_allowed": rnd(div(d["pass20"], d["dropbacks"])),
            "def_sack_rate_forced": rnd(div(d["sacks"], d["dropbacks"])),
            "def_rushes_faced": int(d["rushes"]), "def_rush_epa_per_attempt_allowed": rnd(div(d["rush_epa"], d["rushes"])),
            "def_rush_success_rate_allowed": rnd(div(d["rush_success"], d["rush_success_n"])),
            "def_explosive_rush10_rate_allowed": rnd(div(d["rush10"], d["rushes"])),
            "def_takeaway_event_rate": rnd(div(d["turnovers"], d["plays"])),
            "def_early_down_pass_rate_faced": rnd(div(d["ed_pass"], d["ed"])),
            "def_neutral_early_down_pass_rate_faced_proxy": rnd(div(d["neutral_ed_pass"], d["neutral_ed"])),
            "def_red_zone_epa_per_play_allowed": rnd(div(d["rz_epa"], d["rz"])),
            "def_red_zone_success_rate_allowed": rnd(div(d["rz_success"], d["rz_success_n"])),
            "def_drives_faced": dd, "def_plays_per_drive_faced": rnd(div(d["plays"], dd), 3),
            "raw_net_epa_per_play": rnd((off_epa or 0.0) - (def_epa or 0.0)),
            "raw_net_success_rate": rnd((off_sr or 0.0) - (def_sr or 0.0)),
            "release_state": "HOLD", "model_use": "RESEARCH_INPUT_ONLY",
        })

    output.sort(key=lambda r: float(r["raw_net_epa_per_play"] or -999), reverse=True)
    csv_path = OUT_DIR / f"pbp_features_{SEASON}_week{TARGET_WEEK}_pregame.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(output[0].keys())); w.writeheader(); w.writerows(output)

    qa.update({
        "teams_found": len(teams), "offense_teams_with_plays": len(off), "defense_teams_with_plays": len(deff),
        "output_rows": len(output),
        "feature_rules": {
            "nullified_play_guard": "play_type == no_play; use no_play flag too when source column exists",
            "core_play": "pass/run or qb_dropback/rush_attempt; exclude nullified, kneels, spikes",
            "success": "nflfastR success field",
            "explosive_pass_candidate": "yards_gained >= 20 on dropback",
            "explosive_rush_candidate": "yards_gained >= 10 on rush_attempt",
            "neutral_early_down_candidate": "down 1-2, qtr <= 3, 0.20 <= wp <= 0.80",
            "red_zone": "yardline_100 <= 20", "drive": qa["drive_column"],
        },
        "notes": [
            "Regular-season Weeks 1-5 only for the Week 6 pregame snapshot.",
            "Explosive and neutral-script thresholds are candidates pending historical validation.",
            "Turnover rates are descriptive and must be shrunk/regressed before model use.",
            "Raw net EPA/success are diagnostics, not released power ratings.",
            "No value is approved for website publication or wager release.",
        ],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    })
    qa_path = OUT_DIR / f"pbp_qa_{SEASON}_week{TARGET_WEEK}_pregame.json"
    qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(qa, indent=2))
    print(f"Wrote {csv_path}\nWrote {qa_path}")


if __name__ == "__main__":
    main()
