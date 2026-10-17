#!/usr/bin/env python3
"""Cross-check independent NFL summary-stat and PBP research layers."""
from __future__ import annotations
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

SEASON = 2026
TARGET_WEEK = 6
BASE = Path("nfl_data/generated")
SUMMARY = BASE / f"team_efficiency_{SEASON}_week{TARGET_WEEK}_pregame.csv"
PBP = BASE / f"pbp_features_{SEASON}_week{TARGET_WEEK}_pregame.csv"
OUT = BASE / f"feature_layer_validation_{SEASON}_week{TARGET_WEEK}_pregame.json"


def load(path):
    with path.open(encoding="utf-8") as f:
        return {r["team"]: r for r in csv.DictReader(f)}


def f(row, key):
    try:
        x = float(row.get(key, ""))
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def pearson(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    ax = sum(x for x, _ in pairs) / len(pairs)
    ay = sum(y for _, y in pairs) / len(pairs)
    num = sum((x-ax)*(y-ay) for x, y in pairs)
    dx = math.sqrt(sum((x-ax)**2 for x, _ in pairs))
    dy = math.sqrt(sum((y-ay)**2 for _, y in pairs))
    return None if not dx or not dy else num/(dx*dy)


def median(vals):
    vals = sorted(vals)
    if not vals: return None
    n = len(vals)
    return vals[n//2] if n % 2 else (vals[n//2-1]+vals[n//2])/2


def compare(a, b, akey, bkey):
    teams = sorted(set(a) & set(b))
    xs = [f(a[t], akey) for t in teams]
    ys = [f(b[t], bkey) for t in teams]
    diffs = [(t, abs(x-y)) for t, x, y in zip(teams, xs, ys) if x is not None and y is not None]
    diffs.sort(key=lambda z: z[1], reverse=True)
    return {
        "summary_field": akey,
        "pbp_field": bkey,
        "n": len(diffs),
        "pearson_r": None if (r := pearson(xs, ys)) is None else round(r, 4),
        "median_abs_diff": None if not diffs else round(median([d for _, d in diffs]), 4),
        "max_abs_diff": None if not diffs else round(diffs[0][1], 4),
        "largest_differences": [{"team": t, "abs_diff": round(d, 4)} for t, d in diffs[:5]],
    }


def main():
    a, b = load(SUMMARY), load(PBP)
    if set(a) != set(b) or len(a) != 32:
        raise RuntimeError(f"Team coverage mismatch: summary={len(a)} pbp={len(b)}")
    checks = {
        "off_epa": compare(a,b,"off_epa_per_play_proxy","off_epa_per_play"),
        "pass_epa": compare(a,b,"off_pass_epa_per_dropback","off_pass_epa_per_dropback"),
        "rush_epa": compare(a,b,"off_rush_epa_per_carry","off_rush_epa_per_attempt"),
        "net_epa": compare(a,b,"raw_net_epa_per_play_proxy","raw_net_epa_per_play"),
    }
    warnings = []
    for name, result in checks.items():
        r = result["pearson_r"]
        if r is None or r < 0.85:
            warnings.append(f"{name} correlation below 0.85: {r}")
    result = {
        "season": SEASON,
        "target_week": TARGET_WEEK,
        "teams": 32,
        "summary_release_state": sorted(set(r["release_state"] for r in a.values())),
        "pbp_release_state": sorted(set(r["release_state"] for r in b.values())),
        "checks": checks,
        "warnings": warnings,
        "validation_status": "PASS" if not warnings else "REVIEW",
        "release_state": "HOLD",
        "interpretation": "Consistency test only. PASS does not promote model outputs or validate predictive value.",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    OUT.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if warnings:
        raise RuntimeError("Feature-layer consistency requires review: " + "; ".join(warnings))

if __name__ == "__main__":
    main()
