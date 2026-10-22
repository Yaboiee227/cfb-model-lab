#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UA = "CBModelProjections/1.0 (+https://github.com/Yaboiee227/cfb-model-lab)"


def read_week(path: Path, fallback: int) -> int:
    try:
        return int(json.loads(path.read_text(encoding="utf-8")).get("currentWeek", fallback))
    except Exception:
        return fallback


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)


def stable_event(event: dict) -> dict:
    # Keep the ESPN event shape expected by live-data.js while dropping unrelated
    # top-level scoreboard metadata. Event status/score/clock updates remain intact.
    return event


def write_feed(path: Path, league: str, week: int, endpoint_sport: str, limit: int) -> tuple[int, bool]:
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports/football/{endpoint_sport}/scoreboard"
        f"?week={week}&seasontype=2&limit={limit}"
    )
    payload = fetch(url)
    out = {
        "schemaVersion": 1,
        "league": league,
        "week": week,
        "source": "ESPN public site scoreboard endpoint",
        "events": [stable_event(event) for event in payload.get("events", [])],
    }
    rendered = json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    changed = previous != rendered
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    return len(out["events"]), changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cfb-week", type=int)
    parser.add_argument("--nfl-week", type=int)
    args = parser.parse_args()

    cfb_week = args.cfb_week or read_week(ROOT / "data/config.json", 8)
    nfl_week = args.nfl_week or read_week(ROOT / "nfl_data/site/config.json", 7)

    cfb_count, cfb_changed = write_feed(
        ROOT / "data/live-scoreboard.json", "cfb", cfb_week, "college-football", 200
    )
    nfl_count, nfl_changed = write_feed(
        ROOT / "nfl_data/site/live-scoreboard.json", "nfl", nfl_week, "nfl", 100
    )
    if cfb_count <= 0:
        raise SystemExit("CFB scoreboard returned zero events")
    if nfl_count <= 0:
        raise SystemExit("NFL scoreboard returned zero events")
    print(json.dumps({
        "cfb": {"week": cfb_week, "events": cfb_count, "changed": cfb_changed},
        "nfl": {"week": nfl_week, "events": nfl_count, "changed": nfl_changed},
    }, indent=2))


if __name__ == "__main__":
    main()
