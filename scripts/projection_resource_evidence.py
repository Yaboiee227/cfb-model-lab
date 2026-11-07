"""Projection research contracts. No production writes, fitting, or promotion.

Home margin always means home points minus away points. Sources fetched now
cannot certify historical availability. All clocks must include a timezone.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def instant(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone required")
    return dt.astimezone(timezone.utc)


def number(value):
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (ValueError, TypeError):
        return None
    return out if math.isfinite(out) else None


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save_new(path, doc):
    """Refuse overwrites, even when a second call supplies identical content."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(doc, stream, indent=2, allow_nan=False)
        stream.write("\n")


def cycle(now):
    """Tuesday through Monday, spanning NFL's Thursday–Monday schedule."""
    today = now.astimezone(ET).date()
    start = today - timedelta(days=(today.weekday() - 1) % 7)
    return start, start + timedelta(days=7)


def nfl_slate(rows, now):
    start, end = cycle(now)
    selected = [r for r in rows if r.get("game_type") == "REG"
                and str(start) <= r.get("gameday", "") < str(end)]
    weeks = {(int(r["season"]), int(r["week"])) for r in selected}
    if len(weeks) != 1:
        raise ValueError("current NFL cycle must resolve to exactly one season/week")
    season, week = weeks.pop()
    games, seen = [], set()
    for row in selected:
        gid = row["game_id"]
        if gid in seen:
            raise ValueError(f"duplicate NFL game: {gid}")
        seen.add(gid)
        kickoff = datetime.fromisoformat(row["gameday"] + "T" + row["gametime"]).replace(tzinfo=ET)
        games.append({"gameId": gid, "awayTeam": row["away_team"], "homeTeam": row["home_team"],
                      "kickoff": kickoff.astimezone(timezone.utc).isoformat(),
                      "neutralSite": row.get("location") == "Neutral"})
    return {"season": season, "week": week, "games": games}


def cfb_slate(root, now):
    start, end = cycle(now)
    matches = []
    for path in sorted((root / "cfb/pregame").glob("week-*-schedule.json")):
        doc = json.loads(path.read_text())
        days = doc.get("dateWindowET", [])
        if days and str(start) <= days[0] < str(end):
            matches.append((path, doc))
    if len(matches) != 1:
        raise ValueError("current CFB cycle has no unique saved schedule; never reuse last week's schedule")
    path, doc = matches[0]
    games, seen = [], set()
    for row in doc["games"]:
        gid = row["gameId"]
        if gid in seen:
            raise ValueError(f"duplicate CFB game: {gid}")
        seen.add(gid)
        kickoff = instant(row["kickoff"])
        if not str(start) <= str(kickoff.astimezone(ET).date()) < str(end):
            raise ValueError(f"CFB game outside current cycle: {gid}")
        games.append({k: row[k] for k in ["gameId", "awayTeam", "homeTeam", "kickoff", "neutralSite"]})
    return {"season": doc["season"], "week": doc["week"], "schedulePath": str(path.relative_to(root)),
            "scheduleSha256": digest(path.read_bytes()), "games": games}


def team_key(name, aliases):
    def key(text):
        # Normalize State/St without collapsing Miami FL/OH or other distinct teams.
        text = str(text).lower().replace("&", "and")
        text = re.sub(r"\bst\.?\b", "state", text)
        return re.sub(r"[^a-z0-9]", "", text)
    lookup = {}
    extra = {"Miami": ["Miami FL.", "Miami (Fla.)"], "Miami (OH)": ["Miami (O)"],
             "USC": ["Southern Cal", "Southern Calif.", "Southern California"],
             "Ole Miss": ["Mississippi"], "NC State": ["North Carolina St."],
             "UMass": ["Massachusetts"], "UConn": ["Connecticut"],
             "Ohio": ["Ohio University"], "Southern Miss": ["Southern Mississippi", "Southern Miss."],
             "UAB": ["Alabama Birmingham"], "Charlotte": ["North Carolina Charlotte"],
             "Troy": ["Troy State"], "UNLV": ["Nevada Las Vegas"]}
    for canonical in set(aliases) | set(extra):
        for value in [canonical, *aliases.get(canonical, []), *extra.get(canonical, [])]:
            normalized = key(value)
            if normalized in lookup and lookup[normalized] != key(canonical):
                raise ValueError(f"ambiguous team alias: {value}")
            lookup[normalized] = key(canonical)
    return lookup.get(key(name), key(name))


def validate_observation(row, game):
    """Evidence must be actually collected before kickoff; no date-only escape."""
    if row.get("league") not in {"nfl", "cfb"} or row.get("canonicalInfluence") is not False:
        raise ValueError("explicit league and noncanonical role required")
    if row.get("vintage") != "game_week":
        raise ValueError("only game-week forecasts eligible")
    if row.get("gameId") != game["gameId"] or any(row.get(k) != game[k] for k in ["homeTeam", "awayTeam", "kickoff"]):
        raise ValueError("game identity/kickoff mismatch")
    captured = instant(row["collectedAt"])
    if captured >= instant(game["kickoff"]):
        raise ValueError("collection must precede kickoff")
    if instant(row["sourceObservedAt"]) > captured:
        raise ValueError("derived observation predates source retrieval")
    if row.get("sourcePublishedAt") and instant(row["sourcePublishedAt"]) > captured:
        raise ValueError("source publication after collection")
    if not re.fullmatch(r"[0-9a-f]{64}", row.get("sourceSha256", "")) or not row.get("sourceUrl"):
        raise ValueError("source URL and SHA256 required")
    if row.get("role") != "external_benchmark":
        raise ValueError("observation is not an external benchmark")
    if not row.get("family") or not row.get("sourceId") or not row.get("conversion"):
        raise ValueError("source family and conversion required")
    if number(row.get("homeMargin")) is None:
        raise ValueError("finite home margin required")
    if row.get("total") is not None and (number(row["total"]) is None or number(row["total"]) < 0):
        raise ValueError("invalid total")


def summarize_errors(pairs):
    if not pairs:
        return {"n": 0, "mae": None, "rmse": None, "medianAbsoluteError": None, "bias": None}
    errors = [predicted - actual for predicted, actual in pairs]
    return {"n": len(errors), "mae": mean(abs(x) for x in errors),
            "rmse": math.sqrt(mean(x*x for x in errors)),
            "medianAbsoluteError": median(abs(x) for x in errors), "bias": mean(errors)}


def compare_forecasts(league, games, forecasts, benchmarks, results=None):
    """Descriptive matched comparisons, with no inferred markets or win probabilities.

    Inputs must already be normalized to home minus away. A fresh benchmark is
    allowed beside an older CB freeze, but the origin difference stays explicit.
    No equal-information or superiority claim is made by these comparisons.
    """
    results = results or {}
    if len({g["gameId"] for g in games}) != len(games):
        raise ValueError("duplicate slate games")
    by_game = {g["gameId"]: g for g in games}
    if len({f["gameId"] for f in forecasts}) != len(forecasts):
        raise ValueError("duplicate CB forecasts")
    by_forecast = {f["gameId"]: f for f in forecasts}
    rows, seen, paired, excluded = [], set(), {}, []
    for b in benchmarks:
        identity = (b["sourceId"], b["gameId"])
        if identity in seen:
            raise ValueError("duplicate source/game observation")
        seen.add(identity)
        game = by_game.get(b["gameId"])
        try:
            if b["league"] != league or game is None:
                raise ValueError("wrong league or out-of-slate benchmark")
            validate_observation(b, game)
            f = by_forecast.get(b["gameId"])
            if not f:
                raise ValueError("no matching CB freeze")
            if any(f.get(k) != game[k] for k in ["homeTeam", "awayTeam", "kickoff"]):
                raise ValueError("CB freeze identity mismatch")
            if instant(f["frozenAt"]) >= instant(game["kickoff"]):
                raise ValueError("CB freeze is not pregame")
            if number(f.get("homeMargin")) is None:
                raise ValueError("missing CB margin")
        except (ValueError, KeyError) as exc:
            excluded.append({"sourceId": b["sourceId"], "gameId": b["gameId"], "reason": str(exc)})
            continue
        delta = (instant(b["collectedAt"]) - instant(f["frozenAt"])).total_seconds()
        row = {"gameId": game["gameId"], "sourceId": b["sourceId"], "family": b["family"],
               "cbHomeMargin": f["homeMargin"], "benchmarkHomeMargin": b["homeMargin"],
               "differenceHomePoints": f["homeMargin"] - b["homeMargin"],
               "cbFrozenAt": f["frozenAt"], "benchmarkCollectedAt": b["collectedAt"],
               "originDifferenceSeconds": delta, "sameOrigin": delta == 0,
               "agreementIsConfidence": False}
        outcome = results.get(game["gameId"])
        if outcome:
            # Results must describe a confirmed final, not an in-progress scoreboard.
            if outcome.get("status") != "FINAL" or instant(outcome["observedAt"]) < instant(game["kickoff"]):
                raise ValueError("results require a post-kickoff confirmed final")
            hs, aws = number(outcome.get("homeScore")), number(outcome.get("awayScore"))
            if hs is None or aws is None:
                raise ValueError("final scores must be finite")
            actual = hs - aws
            group = paired.setdefault(b["sourceId"], {"cb": [], "benchmark": []})
            group["cb"].append((f["homeMargin"], actual))
            group["benchmark"].append((b["homeMargin"], actual))
            row["actualHomeMargin"] = actual
        rows.append(row)
    metrics = {source: {"cb": summarize_errors(v["cb"]), "benchmark": summarize_errors(v["benchmark"])}
               for source, v in paired.items()}
    return {"league": league, "canonicalInfluence": False, "rows": rows, "excluded": excluded,
            "pairedMarginMetrics": metrics, "promotionAuthorized": False,
            "policy": "Descriptive paired sample; origins may differ. No market locks, totals, or probability calibration inferred."}
