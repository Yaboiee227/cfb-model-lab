#!/usr/bin/env python3
"""Inspect current nflverse injury schemas without assuming legacy fields."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

SEASONS = [2022, 2023, 2024, 2025, 2026]
URL = "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.parquet"
OUT = Path("nfl_data/generated/injury_schema_probe_2022_2026.json")
TIMESTAMP_HINTS = ["date_modified", "dt", "updated_at", "last_updated", "modified", "timestamp", "report_date", "date"]


def main():
    result = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "seasons": {}}
    for season in SEASONS:
        url = URL.format(season=season)
        try:
            df = pd.read_parquet(url)
            columns = list(df.columns)
            timestamps = [c for c in TIMESTAMP_HINTS if c in columns]
            samples = {}
            for col in timestamps:
                s = df[col].dropna().astype(str)
                samples[col] = s.head(5).tolist()
            result["seasons"][str(season)] = {
                "load_status": "OK",
                "url": url,
                "rows": int(len(df)),
                "columns": columns,
                "timestamp_candidate_columns": timestamps,
                "timestamp_samples": samples,
                "season_values": sorted({str(x) for x in df["season"].dropna().unique()}) if "season" in df.columns else [],
            }
        except Exception as exc:
            result["seasons"][str(season)] = {"load_status": "ERROR", "url": url, "error": str(exc)}
    result["release_state"] = "HOLD_AUDIT_ONLY"
    result["website_publish_allowed"] = False
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
