#!/usr/bin/env python3
"""Build leakage-safe NFL Next Gen Stats feature layers.

Development only. No output from this script is production-approved or written to
website paths. Current Week 6 features use 2026 regular-season Weeks 1-5 only.
Historical target rows use only prior weeks from the target season plus a
separate prior-season baseline.
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

CURRENT_SEASON = 2026
TARGET_WEEK = 6
CUTOFF_WEEK = TARGET_WEEK - 1
HISTORICAL_TARGET_SEASONS = range(2022, 2026)
LOAD_SEASONS = range(2021, CURRENT_SEASON + 1)
STAT_TYPES = ("passing", "rushing", "receiving")
BASE_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/nextgen_stats/"
    "ngs_{season}_{stat_type}.csv.gz"
)
GEN_DIR = Path("nfl_data/generated")
HIST_DIR = Path("nfl_data/historical")

COMMON_REQUIRED = {
    "season_type", "player_display_name", "team_abbr", "player_gsis_id",
    "season", "week",
}

PASS_AVG = [
    "avg_time_to_throw",
    "avg_completed_air_yards",
    "avg_intended_air_yards",
    "avg_air_yards_differential",
    "aggressiveness",
    "avg_air_yards_to_sticks",
    "passer_rating",
    "completion_percentage",
    "expected_completion_percentage",
    "completion_percentage_above_expectation",
]
PASS_SUM = ["attempts", "completions", "pass_yards", "pass_touchdowns", "interceptions"]

RUSH_AVG = [
    "efficiency",
    "percent_attempts_gte_eight_defenders",
    "avg_time_to_los",
    "avg_rush_yards",
    "rush_yards_over_expected_per_att",
    "rush_pct_over_expected",
]
RUSH_SUM = [
    "rush_attempts",
    "rush_yards",
    "expected_rush_yards",
    "rush_yards_over_expected",
    "rush_touchdowns",
]

REC_AVG = [
    "avg_cushion",
    "avg_separation",
    "percent_share_of_intended_air_yards",
    "catch_percentage",
    "avg_yac",
    "avg_expected_yac",
    "avg_yac_above_expectation",
    "avg_air_distance",
]
REC_SUM = ["targets", "receptions", "yards", "rec_touchdowns"]

CONFIG = {
    "passing": {"weight": "attempts", "avg": PASS_AVG, "sum": PASS_SUM, "prefix": "pass"},
    "rushing": {"weight": "rush_attempts", "avg": RUSH_AVG, "sum": RUSH_SUM, "prefix": "rush"},
    "receiving": {"weight": "targets", "avg": REC_AVG, "sum": REC_SUM, "prefix": "rec"},
}


def num(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"na", "nan", "none", "null"}:
        return None
    try:
        value = float(text)
        return value if math.isfinite(value) else None
    except ValueError:
        return None


def as_int(value):
    value = num(value)
    return None if value is None else int(value)


def rnd(value, digits=5):
    if value is None or not math.isfinite(value):
        return None
    return round(value, digits)


def download_rows(season: int, stat_type: str):
    url = BASE_URL.format(season=season, stat_type=stat_type)
    req = urllib.request.Request(url, headers={"User-Agent": "cb-model-projections/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            with gzip.GzipFile(fileobj=resp) as gz:
                with io.TextIOWrapper(gz, encoding="utf-8-sig", newline="") as text:
                    reader = csv.DictReader(text)
                    fields = set(reader.fieldnames or [])
                    cfg = CONFIG[stat_type]
                    required = COMMON_REQUIRED | {cfg["weight"]} | set(cfg["avg"]) | set(cfg["sum"])
                    missing = sorted(required - fields)
                    if missing:
                        raise RuntimeError(
                            f"NGS schema missing columns for {season} {stat_type}: {missing}"
                        )
                    rows = []
                    for row in reader:
                        if str(row.get("season_type", "")).upper() != "REG":
                            continue
                        week = as_int(row.get("week"))
                        # Week 0 is a season summary and would leak future games into pregame rows.
                        if week is None or week <= 0:
                            continue
                        rows.append(row)
                    return url, rows
    except Exception as exc:
        raise RuntimeError(f"Unable to load NGS asset {url}: {exc}") from exc


def aggregate(rows, stat_type: str, group_fields):
    cfg = CONFIG[stat_type]
    weight_field = cfg["weight"]
    prefix = cfg["prefix"]

    buckets = {}
    for row in rows:
        key = tuple(str(row.get(field, "")).strip() for field in group_fields)
        if not all(key):
            continue
        bucket = buckets.setdefault(
            key,
            {
                "weeks": set(),
                "weighted_num": defaultdict(float),
                "weighted_den": defaultdict(float),
                "sums": defaultdict(float),
            },
        )
        week = as_int(row.get("week"))
        if week is not None:
            bucket["weeks"].add(week)
        weight = num(row.get(weight_field)) or 0.0
        for field in cfg["sum"]:
            value = num(row.get(field))
            if value is not None:
                bucket["sums"][field] += value
        if weight > 0:
            for field in cfg["avg"]:
                value = num(row.get(field))
                if value is not None:
                    bucket["weighted_num"][field] += value * weight
                    bucket["weighted_den"][field] += weight

    output = {}
    for key, bucket in buckets.items():
        result = {
            f"{prefix}_weeks_used": len(bucket["weeks"]),
            f"{prefix}_max_week_used": max(bucket["weeks"]) if bucket["weeks"] else None,
        }
        for field in cfg["sum"]:
            result[f"{prefix}_{field}"] = rnd(bucket["sums"].get(field, 0.0), 3)
        for field in cfg["avg"]:
            den = bucket["weighted_den"].get(field, 0.0)
            value = None if den <= 0 else bucket["weighted_num"][field] / den
            result[f"{prefix}_{field}"] = rnd(value)
        output[key] = result
    return output


def aggregate_team(rows_by_type):
    merged = defaultdict(dict)
    for stat_type in STAT_TYPES:
        grouped = aggregate(rows_by_type.get(stat_type, []), stat_type, ("team_abbr",))
        for (team,), metrics in grouped.items():
            merged[team].update(metrics)
    return dict(merged)


def aggregate_qb(pass_rows):
    grouped = aggregate(
        pass_rows,
        "passing",
        ("team_abbr", "player_gsis_id", "player_display_name"),
    )
    rows = []
    for (team, player_id, player_name), metrics in grouped.items():
        row = {
            "season": CURRENT_SEASON,
            "target_week": TARGET_WEEK,
            "team": team,
            "player_gsis_id": player_id,
            "player_display_name": player_name,
            **metrics,
            "release_state": "HOLD_RESEARCH_ONLY",
        }
        rows.append(row)
    rows.sort(key=lambda r: (r["team"], -(r.get("pass_attempts") or 0), r["player_display_name"]))
    return rows


def select_rows(rows, season: int, max_week: int | None = None):
    selected = []
    for row in rows:
        if as_int(row.get("season")) != season:
            continue
        week = as_int(row.get("week"))
        if week is None or week <= 0:
            continue
        if max_week is not None and week > max_week:
            continue
        selected.append(row)
    return selected


def prefix_metrics(metrics, prefix):
    return {f"{prefix}{key}": value for key, value in metrics.items()}


def write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise RuntimeError(f"Refusing to write empty output: {path}")
    fieldnames = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if value is None else value for key, value in row.items()})


def build_historical(data):
    rows = []
    qa = {
        "target_seasons": list(HISTORICAL_TARGET_SEASONS),
        "target_rows": 0,
        "target_or_future_source_rows_used": 0,
        "expected_team_week_rows": len(list(HISTORICAL_TARGET_SEASONS)) * 18 * 32,
        "season_counts": {},
    }

    for season in HISTORICAL_TARGET_SEASONS:
        season_count = 0
        prior_agg = aggregate_team(
            {stat: select_rows(data[season - 1][stat], season - 1) for stat in STAT_TYPES}
        )
        for target_week in range(1, 19):
            current_selected = {
                stat: select_rows(data[season][stat], season, max_week=target_week - 1)
                for stat in STAT_TYPES
            }
            for stat in STAT_TYPES:
                for source_row in current_selected[stat]:
                    source_week = as_int(source_row.get("week")) or 0
                    if source_week >= target_week:
                        qa["target_or_future_source_rows_used"] += 1
            current_agg = aggregate_team(current_selected)
            teams = sorted(set(prior_agg) | set(current_agg))
            if len(teams) != 32:
                raise RuntimeError(
                    f"Expected 32 NGS teams for season={season}, target_week={target_week}; got {len(teams)}"
                )
            for team in teams:
                cur = current_agg.get(team, {})
                prior = prior_agg.get(team, {})
                row = {
                    "season": season,
                    "target_week": target_week,
                    "team": team,
                    "max_current_week_allowed": target_week - 1,
                    **prefix_metrics(cur, "cur_"),
                    **prefix_metrics(prior, "prior_"),
                    "release_state": "HOLD_RESEARCH_ONLY",
                }
                rows.append(row)
                season_count += 1
        qa["season_counts"][str(season)] = season_count

    qa["target_rows"] = len(rows)
    if qa["target_or_future_source_rows_used"] != 0:
        raise RuntimeError(f"Historical NGS leakage QA failed: {qa}")
    if qa["target_rows"] != qa["expected_team_week_rows"]:
        raise RuntimeError(f"Historical NGS coverage QA failed: {qa}")
    return rows, qa


def main():
    GEN_DIR.mkdir(parents=True, exist_ok=True)
    HIST_DIR.mkdir(parents=True, exist_ok=True)

    data = defaultdict(dict)
    source_urls = []
    source_counts = {}
    for season in LOAD_SEASONS:
        source_counts[str(season)] = {}
        for stat_type in STAT_TYPES:
            url, rows = download_rows(season, stat_type)
            data[season][stat_type] = rows
            source_urls.append(url)
            source_counts[str(season)][stat_type] = len(rows)

    current_selected = {
        stat: select_rows(data[CURRENT_SEASON][stat], CURRENT_SEASON, max_week=CUTOFF_WEEK)
        for stat in STAT_TYPES
    }
    target_or_future_current = sum(
        1
        for stat in STAT_TYPES
        for row in current_selected[stat]
        if (as_int(row.get("week")) or 0) >= TARGET_WEEK
    )
    if target_or_future_current:
        raise RuntimeError("Current NGS pregame snapshot used target/future rows")

    current_agg = aggregate_team(current_selected)
    prior_agg = aggregate_team(
        {stat: select_rows(data[CURRENT_SEASON - 1][stat], CURRENT_SEASON - 1) for stat in STAT_TYPES}
    )
    teams = sorted(set(current_agg) | set(prior_agg))
    if len(teams) != 32:
        raise RuntimeError(f"Expected 32 current/prior NGS teams, found {len(teams)}")

    current_team_rows = []
    for team in teams:
        current_team_rows.append(
            {
                "season": CURRENT_SEASON,
                "target_week": TARGET_WEEK,
                "team": team,
                "max_current_week_allowed": CUTOFF_WEEK,
                **prefix_metrics(current_agg.get(team, {}), "cur_"),
                **prefix_metrics(prior_agg.get(team, {}), "prior_"),
                "release_state": "HOLD_RESEARCH_ONLY",
            }
        )

    current_qb_rows = aggregate_qb(current_selected["passing"])
    historical_rows, historical_qa = build_historical(data)

    team_path = GEN_DIR / f"ngs_team_{CURRENT_SEASON}_week{TARGET_WEEK}_pregame.csv"
    qb_path = GEN_DIR / f"ngs_qb_{CURRENT_SEASON}_week{TARGET_WEEK}_pregame.csv"
    hist_path = HIST_DIR / "team_week_ngs_2022_2025.csv"
    qa_path = GEN_DIR / f"ngs_qa_{CURRENT_SEASON}_week{TARGET_WEEK}_pregame.json"

    write_csv(team_path, current_team_rows)
    write_csv(qb_path, current_qb_rows)
    write_csv(hist_path, historical_rows)

    qa = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "current_season": CURRENT_SEASON,
        "target_week": TARGET_WEEK,
        "cutoff_week": CUTOFF_WEEK,
        "source_family": "nflverse mirror of NFL Next Gen Stats",
        "source_urls": source_urls,
        "source_row_counts": source_counts,
        "current_team_rows": len(current_team_rows),
        "current_qb_rows": len(current_qb_rows),
        "current_target_or_future_rows_used": target_or_future_current,
        "historical": historical_qa,
        "ngs_minimum_participation_note": (
            "NGS publishes only qualifying players. Missing player rows must not be interpreted as zero performance."
        ),
        "pregame_rule": "Week 0 season summaries excluded; target season uses weeks strictly before target_week.",
        "release_state": "HOLD_RESEARCH_ONLY",
        "website_publish_allowed": False,
    }
    with qa_path.open("w", encoding="utf-8") as fh:
        json.dump(qa, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(json.dumps({
        "team_output": str(team_path),
        "qb_output": str(qb_path),
        "historical_output": str(hist_path),
        "qa_output": str(qa_path),
        "current_team_rows": len(current_team_rows),
        "current_qb_rows": len(current_qb_rows),
        "historical_rows": len(historical_rows),
        "release_state": "HOLD_RESEARCH_ONLY",
    }, indent=2))


if __name__ == "__main__":
    main()
