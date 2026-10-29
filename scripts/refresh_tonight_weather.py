#!/usr/bin/env python3
"""Refresh pregame NWS hourly context for the current tonight readiness page."""
from __future__ import annotations

import datetime as dt
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "research/operations/2026-10-29/nws-weather.json"
UA = "CBModelProjections/1.0 (https://github.com/Yaboiee227/cfb-model-lab)"


def fetch(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/geo+json"})
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def main() -> None:
    saved = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    now = dt.datetime.now(dt.timezone.utc)
    updated = {}
    for key, old in saved.items():
        payload = fetch(old["sourceUrl"])
        properties = payload["properties"]
        kickoff = dt.datetime.fromisoformat(old["kickoff"].replace("Z", "+00:00"))
        end = kickoff + dt.timedelta(hours=4)
        periods = []
        for period in properties["periods"]:
            start = dt.datetime.fromisoformat(period["startTime"])
            finish = dt.datetime.fromisoformat(period["endTime"])
            if finish <= kickoff or start >= end:
                continue
            periods.append({field: period.get(field) for field in (
                "number", "name", "startTime", "endTime", "isDaytime", "temperature",
                "temperatureUnit", "temperatureTrend", "probabilityOfPrecipitation",
                "dewpoint", "relativeHumidity", "windSpeed", "windDirection", "icon",
                "shortForecast", "detailedForecast",
            )})
        updated[key] = {
            "observedAt": now.isoformat(),
            "sourceUrl": old["sourceUrl"],
            "forecastIssuedAt": properties.get("updateTime") or properties.get("generatedAt"),
            "kickoff": old["kickoff"],
            "periods": periods,
        }
        print(f"{key}: observed {now.isoformat()}, {len(periods)} hourly periods through kickoff + 4h")
    DATA_PATH.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
