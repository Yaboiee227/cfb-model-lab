#!/usr/bin/env python3
"""Read-only diagnostics of existing stored records, never regrade or refit.

These files mix model periods and unverified market reference timestamps. Keep
league/season/week/tracking class separate and do not call this a new holdout.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from projection_resource_evidence import digest, number, save_new, summarize_errors

ROOT = Path(__file__).resolve().parents[1]


def evaluate(rows, league):
    groups = defaultdict(list); seen = set()
    for r in rows:
        key = (r["season"], r["gameId"])
        if key in seen:
            raise ValueError(f"duplicate result: {key}")
        seen.add(key)
        groups[(r["season"], r["week"], r.get("trackingClass") or "UNSPECIFIED")].append(r)
    report = []
    for (season, week, tracking), games in sorted(groups.items()):
        metrics = {}; exclusions = []
        for target, field, market_field in [("margin", "modelSpreadHome", "marketSpreadHome"),
                                            ("total", "modelTotal", "marketTotal")]:
            model, paired_model, paired_market = [], [], []
            for r in games:
                home, away = number(r.get("homeScore")), number(r.get("awayScore"))
                predicted, market = number(r.get(field)), number(r.get(market_field))
                if home is None or away is None or predicted is None:
                    exclusions.append({"gameId": r["gameId"], "target": target, "reason": "missing/nonfinite prediction or final score"})
                    continue
                # Legacy stored spread is away minus home; normalize for all metrics.
                actual = home - away if target == "margin" else home + away
                if target == "margin":
                    predicted = -predicted
                    if market is not None:
                        market = -market
                model.append((predicted, actual))
                if market is not None:
                    paired_model.append((predicted, actual)); paired_market.append((market, actual))
                else:
                    exclusions.append({"gameId": r["gameId"], "target": target, "reason": "missing stored market reference"})
            metrics[target] = {"allStoredModel": summarize_errors(model), "pairedStoredModel": summarize_errors(paired_model),
                               "pairedStoredMarketReference": summarize_errors(paired_market)}
            metrics[target]["pairedMaeDelta"] = (metrics[target]["pairedStoredModel"]["mae"] - metrics[target]["pairedStoredMarketReference"]["mae"]) if paired_model else None
        probabilities = []; bins = defaultdict(list)
        for r in games:
            p, home, away = number(r.get("homeWinProbability")), number(r.get("homeScore")), number(r.get("awayScore"))
            if p is None or not 0 <= p <= 100 or home is None or away is None or home == away:
                exclusions.append({"gameId": r["gameId"], "target": "win_probability", "reason": "missing/invalid percent probability, score, or tied outcome"})
                continue
            p /= 100
            outcome = float(home > away); probabilities.append((p, outcome)); bins[min(int(p*5), 4)].append((p, outcome))
        brier = mean((p-y)**2 for p, y in probabilities) if probabilities else None
        loss = mean(-(y*math.log(max(1e-15, p)) + (1-y)*math.log(max(1e-15, 1-p))) for p, y in probabilities) if probabilities else None
        grades = {target: dict(Counter(r.get(field) or "UNAVAILABLE" for r in games))
                  for target, field in [("ats", "atsResult"), ("total", "totalResult"), ("straightUp", "suResult")]}
        report.append({"league": league, "season": int(season), "week": int(week), "trackingClass": tracking,
                       "games": len(games), "metrics": metrics, "storedGrades": grades,
                       "winProbability": {"n": len(probabilities), "brier": brier, "logLoss": loss,
                            "inputUnits": "percent", "logLossProbabilityFloor": 1e-15,
                            "calibration": [{"lower": k/5, "upper": (k+1)/5, "n": len(v),
                                             "meanPrediction": mean(p for p, _ in v), "actualHomeWinRate": mean(y for _, y in v)} for k, v in sorted(bins.items())]},
                       "exclusions": exclusions})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(ROOT / "data") or args.output.resolve().is_relative_to(ROOT / "nfl_data"):
        parser.error("diagnostics must not overwrite production data")
    sources = []; groups = []
    for league, name in [("cfb", "data/results.csv"), ("nfl", "nfl_data/site/results.csv")]:
        path = ROOT / name; raw = path.read_bytes()
        sources.append({"path": name, "sha256": digest(raw)})
        groups.extend(evaluate(list(csv.DictReader(raw.decode().splitlines())), league))
    save_new(args.output, {"generatedAt": datetime.now(timezone.utc).isoformat(), "canonicalInfluence": False,
        "promotionAuthorized": False, "newOutOfSampleValidation": False, "sources": sources, "groups": groups,
        "policy": "Stored historical diagnosis only; groups preserve league/season/week/tracking class, not certified model-version homogeneity. Uses existing grades without changing them. Market references are not verified publication or closing prices. No ROI claim."})
    print(f"Saved {len(groups)} separate diagnostic groups")


if __name__ == "__main__":
    main()
