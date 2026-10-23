#!/usr/bin/env python3
"""Populate human-readable CFB team names from ESPN's grouped FBS team payload."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cfb_shadow_engine as engine  # noqa: E402

OUT = ROOT / "data/power-rankings"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def grouped_entries(doc):
    for sport in doc.get("sports", []):
        for league in sport.get("leagues", []):
            for group in league.get("groups", []):
                for entry in group.get("teams", []):
                    yield entry
            for entry in league.get("teams", []):
                yield entry
    for entry in doc.get("teams", []):
        yield entry


def main():
    params = "groups=80&groupType=conference&enable=groups"
    doc = engine.fetch_json(f"{engine.ESPN_FBS_TEAMS}?{params}")
    names = {}
    for entry in grouped_entries(doc):
        team = entry.get("team") or entry
        try:
            key = engine.team_key(team)
        except Exception:
            continue
        display = team.get("location") or team.get("shortDisplayName") or team.get("displayName") or key
        names[key] = str(display)

    json_path = OUT / "cfb.json"
    csv_path = OUT / "cfb.csv"
    manifest_path = OUT / "manifest.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    missing = []
    for row in data.get("teams", []):
        key = row["team"]
        if key not in names:
            missing.append(key)
            continue
        row["teamName"] = names[key]
    if missing:
        raise RuntimeError(f"Missing human-readable ESPN names for {len(missing)} FBS teams: {missing}")
    json_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    fields = list(data["teams"][0])
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data["teams"])

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["cfb.json"] = sha256(json_path)
    manifest["files"]["cfb.csv"] = sha256(csv_path)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"mappedTeams": len(data["teams"]), "sample": [[r["rank"], r["teamName"]] for r in data["teams"][:10]]}, indent=2))


if __name__ == "__main__":
    main()
