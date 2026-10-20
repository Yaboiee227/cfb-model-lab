#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"Timestamp must include timezone: {value}")
    return dt.astimezone(timezone.utc)


def validate(path: Path, max_age_days: int = 8) -> list[str]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []

    if doc.get("league") not in {"cfb", "nfl"}:
        errors.append("league must be cfb or nfl")
    if not isinstance(doc.get("games"), list):
        errors.append("games must be a list")
        return errors

    source_urls = {
        "sagarin": "https://sagarin.com/sports/cfsend.htm" if doc.get("league") == "cfb" else "https://sagarin.com/sports/nflsend.htm",
        "spPlus": "https://www.espn.com/college-football/story/_/id/49868647/2026-college-football-sp+-rankings-all-138-fbs-teams",
    }
    for source, expected in source_urls.items():
        block = (doc.get("sources") or {}).get(source)
        if block and block.get("officialUrl") != expected:
            errors.append(f"{source}: unofficial source URL")

    seen = set()
    for game in doc.get("games", []):
        gid = game.get("gameId")
        if not gid:
            errors.append("game missing gameId")
            continue
        if gid in seen:
            errors.append(f"duplicate gameId: {gid}")
        seen.add(gid)
        try:
            kickoff = parse_dt(game["kickoff"])
        except Exception as exc:
            errors.append(f"{gid}: invalid kickoff: {exc}")
            continue

        for source in ("sagarin", "spPlus"):
            obs = game.get(source)
            if not isinstance(obs, dict):
                continue
            status = str(obs.get("status", "")).upper()
            if status.startswith("PENDING") or status in {"UNAVAILABLE", "STALE", "NOT_LISTED"}:
                continue
            observed_at = obs.get("observedAt")
            if not observed_at:
                errors.append(f"{gid}/{source}: current observation missing observedAt")
                continue
            try:
                observed = parse_dt(observed_at)
                if observed > kickoff:
                    errors.append(f"{gid}/{source}: observation is after kickoff")
            except Exception as exc:
                errors.append(f"{gid}/{source}: invalid observedAt: {exc}")

            through = obs.get("ratingsThrough")
            if through:
                try:
                    through_dt = datetime.fromisoformat(through).replace(tzinfo=timezone.utc)
                    age = (kickoff - through_dt).total_seconds() / 86400
                    if age < 0:
                        errors.append(f"{gid}/{source}: ratingsThrough is after kickoff")
                    elif age > max_age_days and status == "CURRENT":
                        errors.append(f"{gid}/{source}: CURRENT benchmark is {age:.1f} days old")
                except ValueError:
                    errors.append(f"{gid}/{source}: invalid ratingsThrough date")

        sag = game.get("sagarin")
        if isinstance(sag, dict) and str(sag.get("status", "")).upper() == "CURRENT":
            fav = sag.get("predictorFavorite")
            spread = sag.get("impliedSpreadHome")
            margin = sag.get("predictorMargin")
            if fav and spread is not None and margin is not None:
                if fav == game.get("homeTeam") and float(spread) >= 0:
                    errors.append(f"{gid}/sagarin: home favorite must have negative impliedSpreadHome")
                if fav == game.get("awayTeam") and float(spread) <= 0:
                    errors.append(f"{gid}/sagarin: away favorite must have positive impliedSpreadHome")
                if abs(abs(float(spread)) - abs(float(margin))) > 1e-6:
                    errors.append(f"{gid}/sagarin: predictorMargin and impliedSpreadHome disagree")

            hs, aws, total, hm = (
                sag.get("projectedHomeScore"),
                sag.get("projectedAwayScore"),
                sag.get("projectedTotal"),
                sag.get("projectedHomeMargin"),
            )
            if None not in {hs, aws, total, hm}:
                if abs((float(hs) + float(aws)) - float(total)) > 0.02:
                    errors.append(f"{gid}/sagarin: projected scores do not sum to total")
                if abs((float(hs) - float(aws)) - float(hm)) > 0.02:
                    errors.append(f"{gid}/sagarin: projected scores do not match home margin")

    return errors


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--max-age-days", type=int, default=8)
    args = ap.parse_args()
    errors = validate(Path(args.path), args.max_age_days)
    if errors:
        for error in errors:
            print("BENCHMARK_ERROR:", error)
        raise SystemExit(1)
    print(f"Benchmark snapshot valid: {args.path}")


if __name__ == "__main__":
    main()
