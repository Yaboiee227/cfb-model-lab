#!/usr/bin/env python3
"""Audit reproducible NFL trench / pressure source coverage.

Development-only source audit. This does not assign model weights.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

OUT = Path("nfl_data/generated/trench_source_audit_2026_week6.json")
SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
CUTOFF_WEEK = 5

URLS = {
    "pfr_pass": "https://github.com/nflverse/nflverse-data/releases/download/pfr_advstats/advstats_week_pass_{season}.parquet",
    "pfr_def": "https://github.com/nflverse/nflverse-data/releases/download/pfr_advstats/advstats_week_def_{season}.parquet",
    "snap_counts": "https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_{season}.parquet",
    "ftn": "https://github.com/nflverse/nflverse-data/releases/download/ftn_charting/ftn_charting_{season}.parquet",
}

KEYWORDS = [
    "pressure", "press", "hurry", "hit", "sack", "blitz", "pocket", "scramble",
    "throwaway", "badthrow", "on_target", "snap", "offense", "defense", "position",
    "team", "week", "player", "block", "rush", "pass", "stunt", "motion", "personnel",
]


def nonnull_summary(df: pd.DataFrame, cols: list[str]) -> dict[str, int]:
    return {c: int(df[c].notna().sum()) for c in cols if c in df.columns}


def audit_one(kind: str, season: int) -> dict:
    if kind == "ftn" and season < 2022:
        return {"available": False, "reason": "documented_not_available_before_2022"}
    url = URLS[kind].format(season=season)
    try:
        df = pd.read_parquet(url)
    except Exception as exc:
        return {"available": False, "url": url, "error": f"{type(exc).__name__}: {exc}"[:500]}

    cols = [str(c) for c in df.columns]
    candidate_cols = [c for c in cols if any(k in c.lower() for k in KEYWORDS)]
    out = {
        "available": True,
        "url": url,
        "rows": int(len(df)),
        "columns": cols,
        "candidate_columns": candidate_cols,
        "candidate_non_null": nonnull_summary(df, candidate_cols),
    }
    for field in ("season", "week", "team", "recent_team", "player_id", "pfr_player_id", "position", "pos"):
        if field in df.columns:
            vals = df[field].dropna()
            out[f"{field}_non_null"] = int(len(vals))
            if field == "week" and len(vals):
                out["max_week"] = int(pd.to_numeric(vals, errors="coerce").max())
            if field in {"team", "recent_team"}:
                out[f"{field}_unique"] = int(vals.astype(str).nunique())
    if season == 2026 and "week" in df.columns:
        w = pd.to_numeric(df["week"], errors="coerce")
        out["rows_week_le_5"] = int((w <= CUTOFF_WEEK).sum())
        out["rows_week_gt_5"] = int((w > CUTOFF_WEEK).sum())
    return out


def main():
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "SCHEMA_AND_COVERAGE_AUDIT_ONLY",
        "release_state": "HOLD_RESEARCH_ONLY",
        "website_publish_allowed": False,
        "target_season": 2026,
        "target_week": 6,
        "current_cutoff_week": CUTOFF_WEEK,
        "sources": {},
        "rules": {
            "pfr_weekly_min_year": 2018,
            "snap_counts_min_year": 2012,
            "ftn_min_year": 2022,
            "current_2026_rows_after_week_5_must_not_enter_week_6_features": True,
            "postgame_charting_must_be_shifted_to_next_pregame_snapshot": True,
        },
    }
    for kind in URLS:
        result["sources"][kind] = {str(s): audit_one(kind, s) for s in SEASONS}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "status": "PASS_SOURCE_AUDIT_BUILT"}, indent=2))


if __name__ == "__main__":
    main()
