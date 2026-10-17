#!/usr/bin/env python3
"""Audit historical NFL depth-chart and injury data for pregame-safe use.

Goal: determine which seasons can support starter/depth/injury features without
hindsight. This script does NOT create model predictions and does NOT publish
website data.

Safety policy:
- 2022-2024 legacy depth charts are NFL-week scoped but do not expose an exact
  snapshot timestamp. They are audited as WEEK_SCOPED_NO_EXACT_TIMESTAMP, not
  automatically treated as exact pregame truth.
- 2025+ depth charts expose an ISO timestamp (dt). For each team/game we select
  only the latest snapshot strictly before kickoff.
- Injury rows expose date_modified. A row is pregame-eligible only when its
  timestamp is strictly before kickoff. Because the released injury file may
  not retain every earlier revision, the audit separately reports coverage and
  post-kick/future rows rather than assuming reconstructibility.
"""
from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

SEASONS = [2022, 2023, 2024, 2025, 2026]
DEPTH_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/depth_charts/"
    "depth_charts_{season}.parquet"
)
INJURY_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/injuries/"
    "injuries_{season}.parquet"
)
SCHEDULE_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.parquet"
)
OUT_DIR = Path("nfl_data/generated")
ET = ZoneInfo("America/New_York")


def clean_team(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    team = str(value).strip().upper()
    aliases = {"JAX": "JAX", "JAC": "JAX", "LA": "LA", "LAR": "LA", "LV": "LV", "OAK": "LV"}
    return aliases.get(team, team)


def parse_schedule():
    df = pd.read_parquet(SCHEDULE_URL)
    needed = {"season", "week", "game_type", "gameday", "gametime", "home_team", "away_team", "game_id"}
    missing = sorted(needed - set(df.columns))
    if missing:
        raise RuntimeError(f"Schedule missing columns: {missing}")
    df = df[
        pd.to_numeric(df["season"], errors="coerce").isin(SEASONS)
        & (df["game_type"].astype(str).str.upper() == "REG")
    ].copy()
    rows = []
    for _, r in df.iterrows():
        season = int(r["season"]); week = int(r["week"])
        day = str(r["gameday"]); tm = str(r["gametime"])
        if not day or day == "nan" or not tm or tm == "nan":
            continue
        # nflverse gametime is Eastern time; convert to an aware UTC cutoff.
        naive = datetime.fromisoformat(f"{day}T{tm}")
        kickoff_et = naive.replace(tzinfo=ET)
        kickoff_utc = kickoff_et.astimezone(timezone.utc)
        for side in ("home", "away"):
            rows.append({
                "season": season,
                "week": week,
                "game_id": str(r["game_id"]),
                "team": clean_team(r[f"{side}_team"]),
                "side": side,
                "gameday": day,
                "gametime_et": tm,
                "kickoff_utc": kickoff_utc,
            })
    if not rows:
        raise RuntimeError("No schedule team-game rows loaded")
    return pd.DataFrame(rows)


def position_is_qb(series):
    return series.astype(str).str.upper().isin(["QB", "QUARTERBACK"])


def load_depth(season):
    url = DEPTH_URL.format(season=season)
    df = pd.read_parquet(url)
    cols = set(df.columns)
    if season <= 2024:
        required = {"season", "week", "club_code", "depth_team", "gsis_id", "depth_position", "full_name"}
        missing = sorted(required - cols)
        if missing:
            raise RuntimeError(f"Legacy depth {season} missing {missing}")
        out = df.copy()
        out["team_norm"] = out["club_code"].map(clean_team)
        out["week_norm"] = pd.to_numeric(out["week"], errors="coerce")
        out["rank_norm"] = pd.to_numeric(out["depth_team"], errors="coerce")
        out["is_qb"] = position_is_qb(out["depth_position"])
        out["player_id_norm"] = out["gsis_id"].astype(str)
        out["player_name_norm"] = out["full_name"].astype(str)
        out["snapshot_utc"] = pd.NaT
        mode = "WEEK_SCOPED_NO_EXACT_TIMESTAMP"
    else:
        required = {"dt", "team", "gsis_id", "pos_abb", "pos_rank", "player_name"}
        missing = sorted(required - cols)
        if missing:
            raise RuntimeError(f"Timestamped depth {season} missing {missing}")
        out = df.copy()
        out["team_norm"] = out["team"].map(clean_team)
        out["week_norm"] = pd.NA
        out["rank_norm"] = pd.to_numeric(out["pos_rank"], errors="coerce")
        out["is_qb"] = position_is_qb(out["pos_abb"])
        out["player_id_norm"] = out["gsis_id"].astype(str)
        out["player_name_norm"] = out["player_name"].astype(str)
        out["snapshot_utc"] = pd.to_datetime(out["dt"], errors="coerce", utc=True)
        mode = "TIMESTAMPED_DAILY"
    return out, mode, url


def audit_depth(schedule):
    season_summary = {}
    team_game_rows = []
    all_source_urls = []

    for season in SEASONS:
        depth, mode, url = load_depth(season)
        all_source_urls.append(url)
        qbs = depth[depth["is_qb"]].copy()
        games = schedule[schedule["season"] == season].copy()
        summary = {
            "mode": mode,
            "rows": int(len(depth)),
            "qb_rows": int(len(qbs)),
            "teams": int(depth["team_norm"].replace("", pd.NA).dropna().nunique()),
            "qb_rank_distribution": {
                str(k): int(v) for k, v in qbs["rank_norm"].dropna().astype(int).value_counts().sort_index().items()
            },
            "team_games": int(len(games)),
        }

        if season <= 2024:
            covered = unique_qb1 = qb2_covered = 0
            for _, g in games.iterrows():
                d = qbs[
                    (qbs["team_norm"] == g["team"])
                    & (pd.to_numeric(qbs["week_norm"], errors="coerce") == g["week"])
                ]
                qb1 = d[d["rank_norm"] == 1]
                qb2 = d[d["rank_norm"] == 2]
                covered += int(not d.empty)
                unique_qb1 += int(len(qb1) == 1)
                qb2_covered += int(len(qb2) >= 1)
                team_game_rows.append({
                    **g.to_dict(),
                    "depth_mode": mode,
                    "depth_snapshot_utc": "",
                    "depth_hours_before_kickoff": "",
                    "qb_rows_in_selected_snapshot": int(len(d)),
                    "qb1_count": int(len(qb1)),
                    "qb1_name": qb1.iloc[0]["player_name_norm"] if len(qb1) == 1 else "",
                    "qb1_gsis": qb1.iloc[0]["player_id_norm"] if len(qb1) == 1 else "",
                    "qb2_count": int(len(qb2)),
                    "qb2_name": qb2.iloc[0]["player_name_norm"] if len(qb2) >= 1 else "",
                    "qb2_gsis": qb2.iloc[0]["player_id_norm"] if len(qb2) >= 1 else "",
                    "depth_pregame_exact_timestamp_safe": False,
                    "depth_reason": "legacy weekly chart has no exact snapshot timestamp",
                })
            summary.update({
                "team_games_with_any_qb_depth": covered,
                "team_games_with_unique_qb1": unique_qb1,
                "team_games_with_qb2": qb2_covered,
                "any_qb_depth_coverage_rate": round(covered / len(games), 6) if len(games) else None,
                "unique_qb1_coverage_rate": round(unique_qb1 / len(games), 6) if len(games) else None,
                "qb2_coverage_rate": round(qb2_covered / len(games), 6) if len(games) else None,
                "pregame_safety_class": "WEEK_SCOPED_PROXY_ONLY",
            })
        else:
            covered = unique_qb1 = qb2_covered = 0
            same_day = prior_day = no_snapshot = post_only = 0
            hours = []
            for _, g in games.iterrows():
                dteam = qbs[qbs["team_norm"] == g["team"]].copy()
                valid_ts = dteam[dteam["snapshot_utc"].notna()].copy()
                pre = valid_ts[valid_ts["snapshot_utc"] < g["kickoff_utc"]]
                if pre.empty:
                    no_snapshot += 1
                    post_only += int(not valid_ts.empty and (valid_ts["snapshot_utc"] >= g["kickoff_utc"]).any())
                    team_game_rows.append({
                        **g.to_dict(),
                        "depth_mode": mode,
                        "depth_snapshot_utc": "",
                        "depth_hours_before_kickoff": "",
                        "qb_rows_in_selected_snapshot": 0,
                        "qb1_count": 0, "qb1_name": "", "qb1_gsis": "",
                        "qb2_count": 0, "qb2_name": "", "qb2_gsis": "",
                        "depth_pregame_exact_timestamp_safe": False,
                        "depth_reason": "no timestamped QB depth snapshot strictly before kickoff",
                    })
                    continue
                ts = pre["snapshot_utc"].max()
                snap = pre[pre["snapshot_utc"] == ts]
                qb1 = snap[snap["rank_norm"] == 1]
                qb2 = snap[snap["rank_norm"] == 2]
                delta_h = (g["kickoff_utc"] - ts.to_pydatetime()).total_seconds() / 3600.0
                hours.append(delta_h)
                covered += 1
                unique_qb1 += int(len(qb1) == 1)
                qb2_covered += int(len(qb2) >= 1)
                same_day += int(ts.date() == g["kickoff_utc"].date())
                prior_day += int(ts.date() < g["kickoff_utc"].date())
                team_game_rows.append({
                    **g.to_dict(),
                    "depth_mode": mode,
                    "depth_snapshot_utc": ts.isoformat(),
                    "depth_hours_before_kickoff": round(delta_h, 3),
                    "qb_rows_in_selected_snapshot": int(len(snap)),
                    "qb1_count": int(len(qb1)),
                    "qb1_name": qb1.iloc[0]["player_name_norm"] if len(qb1) == 1 else "",
                    "qb1_gsis": qb1.iloc[0]["player_id_norm"] if len(qb1) == 1 else "",
                    "qb2_count": int(len(qb2)),
                    "qb2_name": qb2.iloc[0]["player_name_norm"] if len(qb2) >= 1 else "",
                    "qb2_gsis": qb2.iloc[0]["player_id_norm"] if len(qb2) >= 1 else "",
                    "depth_pregame_exact_timestamp_safe": bool(len(qb1) == 1),
                    "depth_reason": "latest timestamped snapshot strictly before kickoff",
                })
            summary.update({
                "team_games_with_pregame_snapshot": covered,
                "team_games_with_unique_qb1": unique_qb1,
                "team_games_with_qb2": qb2_covered,
                "team_games_without_pregame_snapshot": no_snapshot,
                "team_games_with_only_postkick_or_no_pregame": post_only,
                "selected_snapshot_same_utc_date_as_kickoff": same_day,
                "selected_snapshot_prior_utc_date": prior_day,
                "median_hours_before_kickoff": round(float(pd.Series(hours).median()), 3) if hours else None,
                "pregame_snapshot_coverage_rate": round(covered / len(games), 6) if len(games) else None,
                "unique_qb1_coverage_rate": round(unique_qb1 / len(games), 6) if len(games) else None,
                "qb2_coverage_rate": round(qb2_covered / len(games), 6) if len(games) else None,
                "pregame_safety_class": "EXACT_TIMESTAMP_FILTERABLE",
            })
        season_summary[str(season)] = summary
    return season_summary, team_game_rows, all_source_urls


def load_injuries(season):
    url = INJURY_URL.format(season=season)
    df = pd.read_parquet(url)
    required = {"season", "week", "team", "gsis_id", "position", "full_name", "report_status", "practice_status", "date_modified"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise RuntimeError(f"Injuries {season} missing {missing}")
    out = df.copy()
    out["team_norm"] = out["team"].map(clean_team)
    out["week_norm"] = pd.to_numeric(out["week"], errors="coerce")
    out["modified_utc"] = pd.to_datetime(out["date_modified"], errors="coerce", utc=True)
    out["is_qb"] = position_is_qb(out["position"])
    return out, url


def audit_injuries(schedule):
    season_summary = {}
    qb_game_rows = []
    urls = []
    for season in SEASONS:
        try:
            inj, url = load_injuries(season)
        except Exception as exc:
            season_summary[str(season)] = {
                "load_status": "UNAVAILABLE",
                "error": str(exc),
                "pregame_safety_class": "UNAVAILABLE",
            }
            continue
        urls.append(url)
        games = schedule[schedule["season"] == season]
        qb = inj[inj["is_qb"]].copy()
        eligible_team_games = 0
        any_team_injury = 0
        qb_injury_games = 0
        qb_rows_pregame = 0
        qb_rows_postkick = 0
        modified_missing = int(inj["modified_utc"].isna().sum())
        report_statuses = Counter(str(x) for x in inj["report_status"].dropna())
        practice_statuses = Counter(str(x) for x in inj["practice_status"].dropna())

        for _, g in games.iterrows():
            d = inj[(inj["team_norm"] == g["team"]) & (inj["week_norm"] == g["week"])]
            if not d.empty:
                any_team_injury += 1
            pre = d[d["modified_utc"].notna() & (d["modified_utc"] < g["kickoff_utc"])]
            if not pre.empty:
                eligible_team_games += 1
            q = d[d["is_qb"]]
            qpre = q[q["modified_utc"].notna() & (q["modified_utc"] < g["kickoff_utc"])]
            qpost = q[q["modified_utc"].notna() & (q["modified_utc"] >= g["kickoff_utc"])]
            qb_rows_pregame += len(qpre)
            qb_rows_postkick += len(qpost)
            if not qpre.empty:
                qb_injury_games += 1
                for _, r in qpre.iterrows():
                    qb_game_rows.append({
                        **g.to_dict(),
                        "player_gsis": str(r["gsis_id"]),
                        "player_name": str(r["full_name"]),
                        "report_status": "" if pd.isna(r["report_status"]) else str(r["report_status"]),
                        "practice_status": "" if pd.isna(r["practice_status"]) else str(r["practice_status"]),
                        "date_modified_utc": r["modified_utc"].isoformat(),
                        "hours_before_kickoff": round((g["kickoff_utc"] - r["modified_utc"].to_pydatetime()).total_seconds()/3600, 3),
                        "pregame_eligible": True,
                    })
        season_summary[str(season)] = {
            "load_status": "OK",
            "rows": int(len(inj)),
            "qb_rows": int(len(qb)),
            "teams": int(inj["team_norm"].replace("", pd.NA).dropna().nunique()),
            "team_games": int(len(games)),
            "team_games_with_any_injury_row": any_team_injury,
            "team_games_with_at_least_one_pregame_timestamped_injury_row": eligible_team_games,
            "team_games_with_pregame_qb_injury_row": qb_injury_games,
            "pregame_qb_rows": int(qb_rows_pregame),
            "postkick_qb_rows_excluded": int(qb_rows_postkick),
            "rows_missing_date_modified": modified_missing,
            "report_status_distribution": dict(report_statuses),
            "practice_status_distribution": dict(practice_statuses),
            "pregame_safety_class": "ROW_TIMESTAMP_FILTERABLE_BUT_REVISION_HISTORY_NOT_ASSUMED",
        }
    return season_summary, qb_game_rows, urls


def json_safe(obj):
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_safe(v) for v in obj]
    return obj


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("status\nNO_ROWS\n", encoding="utf-8")
        return
    fields, seen = [], set()
    for row in rows:
        for k in row:
            if k not in seen:
                fields.append(k); seen.add(k)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: json_safe(v) for k, v in row.items()})


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    schedule = parse_schedule()
    depth_summary, depth_rows, depth_urls = audit_depth(schedule)
    injury_summary, injury_rows, injury_urls = audit_injuries(schedule)

    exact_depth_seasons = [s for s in SEASONS if depth_summary[str(s)].get("pregame_safety_class") == "EXACT_TIMESTAMP_FILTERABLE"]
    legacy_depth_seasons = [s for s in SEASONS if depth_summary[str(s)].get("pregame_safety_class") == "WEEK_SCOPED_PROXY_ONLY"]
    injury_ok_seasons = [s for s in SEASONS if injury_summary[str(s)].get("load_status") == "OK"]

    decision = {
        "exact_timestamp_depth_backtest_seasons": exact_depth_seasons,
        "legacy_week_scoped_depth_proxy_seasons": legacy_depth_seasons,
        "injury_files_available_seasons": injury_ok_seasons,
        "starter_v2_historical_policy": (
            "Use timestamped depth directly only where latest snapshot is strictly before kickoff. "
            "Legacy weekly depth is a separate proxy candidate and must not be labeled exact timestamp-safe."
        ),
        "injury_policy": (
            "Use only rows with date_modified strictly before kickoff; do not assume unreleased earlier revisions exist."
        ),
        "current_release_policy": (
            "Official NFL injury/inactive status and timestamped current depth override schedule-feed QB fields."
        ),
    }

    qa = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "seasons": SEASONS,
        "schedule_source": SCHEDULE_URL,
        "depth_sources": depth_urls,
        "injury_sources": injury_urls,
        "depth": depth_summary,
        "injuries": injury_summary,
        "decision": decision,
        "release_state": "HOLD_AUDIT_ONLY",
        "website_publish_allowed": False,
    }

    qa_path = OUT_DIR / "depth_injury_audit_2022_2026.json"
    depth_path = OUT_DIR / "qb_depth_snapshot_audit_2022_2026.csv"
    injury_path = OUT_DIR / "qb_injury_timestamp_audit_2022_2026.csv"
    qa_path.write_text(json.dumps(json_safe(qa), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(depth_path, depth_rows)
    write_csv(injury_path, injury_rows)

    print(json.dumps({
        "qa": str(qa_path),
        "depth_diagnostics": str(depth_path),
        "injury_diagnostics": str(injury_path),
        "exact_depth_seasons": exact_depth_seasons,
        "legacy_depth_proxy_seasons": legacy_depth_seasons,
        "injury_available_seasons": injury_ok_seasons,
        "release_state": "HOLD_AUDIT_ONLY",
    }, indent=2))


if __name__ == "__main__":
    main()
