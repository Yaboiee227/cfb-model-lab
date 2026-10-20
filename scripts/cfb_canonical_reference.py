#!/usr/bin/env python3
"""Build a reference performance profile from frozen CB CFB projections.

The reference profile is descriptive. It is NOT a target to fit against and must
never be used to tune a candidate on the same games. Its purpose is to preserve
how the established CB model actually behaved on a frozen week so future
rebuilds/challengers have an auditable comparison point.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


def f(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        out = float(text)
    except ValueError:
        return None
    return out if math.isfinite(out) else None


def mean(values: Iterable[float]) -> float | None:
    vals = list(values)
    return sum(vals) / len(vals) if vals else None


def mae(errors: list[float]) -> float | None:
    return mean(abs(x) for x in errors)


def rmse(errors: list[float]) -> float | None:
    return math.sqrt(mean(x * x for x in errors)) if errors else None


def pct(n: int, d: int) -> float | None:
    return 100.0 * n / d if d else None


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def dedupe_results(rows: list[dict[str, str]], season: int, week: int) -> list[dict[str, str]]:
    """Keep one completed record per gameId.

    data/results.csv is an audit ledger; duplicate game IDs can exist across
    rebuilds. Prefer the last occurrence because later rows contain the most
    complete frozen grade metadata while preserving the same game result.
    """
    keep: dict[str, dict[str, str]] = {}
    for row in rows:
        try:
            row_season = int(str(row.get("season", "")).strip())
            row_week = int(str(row.get("week", "")).strip())
        except ValueError:
            continue
        if row_season != season or row_week != week:
            continue
        gid = str(row.get("gameId") or "").strip()
        if not gid:
            continue
        if f(row.get("awayScore")) is None or f(row.get("homeScore")) is None:
            continue
        keep[gid] = row
    return list(keep.values())


def build_projection_meta(rows: list[dict[str, str]], season: int, week: int) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        try:
            if int(str(row.get("season", "")).strip()) != season or int(str(row.get("week", "")).strip()) != week:
                continue
        except ValueError:
            continue
        gid = str(row.get("gameId") or "").strip()
        if gid:
            out[gid] = row
    return out


def game_eval(row: dict[str, str], meta: dict[str, str] | None = None) -> dict[str, Any]:
    away_score = f(row.get("awayScore"))
    home_score = f(row.get("homeScore"))
    assert away_score is not None and home_score is not None
    actual_margin_home = home_score - away_score
    actual_total = home_score + away_score

    model_spread_home = f(row.get("modelSpreadHome"))
    model_total = f(row.get("modelTotal"))
    model_margin_home = -model_spread_home if model_spread_home is not None else None
    margin_error = model_margin_home - actual_margin_home if model_margin_home is not None else None
    total_error = model_total - actual_total if model_total is not None else None

    market_spread_home = f(row.get("marketSpreadHome"))
    market_total = f(row.get("marketTotal"))
    market_margin_home = -market_spread_home if market_spread_home is not None else None
    market_margin_error = market_margin_home - actual_margin_home if market_margin_home is not None else None
    market_total_error = market_total - actual_total if market_total is not None else None

    home_prob_pct = f(row.get("homeWinProbability"))
    home_prob = home_prob_pct / 100.0 if home_prob_pct is not None else None
    if home_score == away_score:
        actual_home_win = None
        su_correct = None
        brier = None
    else:
        actual_home_win = 1.0 if home_score > away_score else 0.0
        if model_margin_home is None or model_margin_home == 0:
            su_correct = None
        else:
            su_correct = (model_margin_home > 0) == (home_score > away_score)
        brier = (home_prob - actual_home_win) ** 2 if home_prob is not None else None

    meta = meta or {}
    return {
        "gameId": row.get("gameId"),
        "awayTeam": row.get("awayTeam"),
        "homeTeam": row.get("homeTeam"),
        "conference": row.get("conference") or meta.get("homeConference") or meta.get("awayConference") or "UNKNOWN",
        "signalStrength": meta.get("signalStrength") or "UNKNOWN",
        "releaseStatus": meta.get("releaseStatus") or "UNKNOWN",
        "actualMarginHome": actual_margin_home,
        "actualTotal": actual_total,
        "modelMarginHome": model_margin_home,
        "modelTotal": model_total,
        "marginError": margin_error,
        "totalError": total_error,
        "marketMarginHome": market_margin_home,
        "marketTotal": market_total,
        "marketMarginError": market_margin_error,
        "marketTotalError": market_total_error,
        "homeWinProbability": home_prob_pct,
        "suCorrect": su_correct,
        "brier": brier,
        "atsResult": row.get("atsResult") or None,
        "totalResult": row.get("totalResult") or None,
        "suResult": row.get("suResult") or None,
        "gradeReference": row.get("gradeReference") or None,
    }


def metric_block(games: list[dict[str, Any]]) -> dict[str, Any]:
    margin_errors = [g["marginError"] for g in games if g["marginError"] is not None]
    total_errors = [g["totalError"] for g in games if g["totalError"] is not None]
    market_margin_errors = [g["marketMarginError"] for g in games if g["marketMarginError"] is not None]
    market_total_errors = [g["marketTotalError"] for g in games if g["marketTotalError"] is not None]
    su = [g["suCorrect"] for g in games if g["suCorrect"] is not None]
    briers = [g["brier"] for g in games if g["brier"] is not None]

    ats_graded = [g for g in games if str(g.get("atsResult") or "").upper() in {"WIN", "LOSS", "PUSH"}]
    ats_wins = sum(str(g.get("atsResult") or "").upper() == "WIN" for g in ats_graded)
    ats_losses = sum(str(g.get("atsResult") or "").upper() == "LOSS" for g in ats_graded)
    ats_pushes = sum(str(g.get("atsResult") or "").upper() == "PUSH" for g in ats_graded)

    total_graded = [g for g in games if str(g.get("totalResult") or "").upper() in {"WIN", "LOSS", "PUSH"}]
    total_wins = sum(str(g.get("totalResult") or "").upper() == "WIN" for g in total_graded)
    total_losses = sum(str(g.get("totalResult") or "").upper() == "LOSS" for g in total_graded)
    total_pushes = sum(str(g.get("totalResult") or "").upper() == "PUSH" for g in total_graded)

    return {
        "games": len(games),
        "model": {
            "marginGames": len(margin_errors),
            "marginMae": mae(margin_errors),
            "marginRmse": rmse(margin_errors),
            "marginBias": mean(margin_errors),
            "totalGames": len(total_errors),
            "totalMae": mae(total_errors),
            "totalRmse": rmse(total_errors),
            "totalBias": mean(total_errors),
            "suGames": len(su),
            "suCorrect": sum(bool(x) for x in su),
            "suAccuracyPct": pct(sum(bool(x) for x in su), len(su)),
            "probabilityGames": len(briers),
            "brierScore": mean(briers),
        },
        "marketReference": {
            "marginGames": len(market_margin_errors),
            "marginMae": mae(market_margin_errors),
            "marginRmse": rmse(market_margin_errors),
            "totalGames": len(market_total_errors),
            "totalMae": mae(market_total_errors),
            "totalRmse": rmse(market_total_errors),
        },
        "gradedPositions": {
            "ats": {"wins": ats_wins, "losses": ats_losses, "pushes": ats_pushes, "graded": len(ats_graded), "winPctExPush": pct(ats_wins, ats_wins + ats_losses)},
            "total": {"wins": total_wins, "losses": total_losses, "pushes": total_pushes, "graded": len(total_graded), "winPctExPush": pct(total_wins, total_wins + total_losses)},
        },
    }


def grouped(games: list[dict[str, Any]], key: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for game in games:
        buckets[str(game.get(key) or "UNKNOWN")].append(game)
    return {name: metric_block(rows) for name, rows in sorted(buckets.items())}


def build_reference(results_path: Path, projections_path: Path | None, season: int, week: int) -> dict[str, Any]:
    result_rows = dedupe_results(load_csv(results_path), season, week)
    meta_map: dict[str, dict[str, str]] = {}
    if projections_path and projections_path.exists():
        meta_map = build_projection_meta(load_csv(projections_path), season, week)
    games = [game_eval(row, meta_map.get(str(row.get("gameId") or ""))) for row in result_rows]
    games.sort(key=lambda g: str(g["gameId"]))

    return {
        "schemaVersion": 1,
        "league": "cfb",
        "season": season,
        "week": week,
        "role": "FROZEN_CANONICAL_REFERENCE_PROFILE",
        "canonicalInfluence": False,
        "source": {
            "results": str(results_path),
            "projectionMetadata": str(projections_path) if projections_path else None,
        },
        "policy": {
            "descriptiveOnly": True,
            "antiLeakage": "Never tune a candidate using these game outcomes and then claim this same-week profile as out-of-sample evidence.",
            "promotionUse": "Use as an observed-behavior reference only; promotion still requires leakage-safe walk-forward and prospective frozen-week evidence.",
        },
        "overall": metric_block(games),
        "byConference": grouped(games, "conference"),
        "bySignalStrength": grouped(games, "signalStrength"),
        "games": games,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="data/results.csv")
    ap.add_argument("--projections", default="data/projections.csv")
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--week", type=int, default=7)
    ap.add_argument("--output", default="cfb/validation/week-07-canonical-reference.json")
    args = ap.parse_args()

    output = build_reference(Path(args.results), Path(args.projections) if args.projections else None, args.season, args.week)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "games": output["overall"]["games"],
        "marginMae": output["overall"]["model"]["marginMae"],
        "totalMae": output["overall"]["model"]["totalMae"],
        "suAccuracyPct": output["overall"]["model"]["suAccuracyPct"],
        "marketMarginMae": output["overall"]["marketReference"]["marginMae"],
        "marketTotalMae": output["overall"]["marketReference"]["totalMae"],
    }, indent=2))


if __name__ == "__main__":
    main()
