#!/usr/bin/env python3
"""Render the current matchup page from saved schedules, without refreezing games."""
import argparse
import html
import json
from pathlib import Path

from projection_resource_evidence import ET, digest, instant

ROOT = Path(__file__).resolve().parents[1]


def publish(capture, root=ROOT):
    manifest = json.loads((capture / "manifest.json").read_text())
    board = json.loads((root / "data/current-matchups.json").read_text())
    nfl = manifest["leagues"]["nfl"]
    frozen = json.loads((root / f"nfl/research-projections/week-{nfl['week']:02d}.json").read_text())
    projected = {g["gameId"] for g in frozen["games"]}
    games = []
    for g in nfl["games"]:
        dt = instant(g["kickoff"]).astimezone(ET)
        games.append({"gameId": g["gameId"], "away": g["awayTeam"], "home": g["homeTeam"],
            "kickoffUTC": g["kickoff"], "dateET": str(dt.date()), "kickoffET": dt.strftime("%a %b %d · %I:%M %p %Z"),
            "neutralSite": g["neutralSite"], "source": "https://github.com/nflverse/nfldata/blob/master/data/games.csv",
            "projectionStatus": "Frozen baseline research; final context HOLD" if g["gameId"] in projected else "No archived pregame projection; not backfilled",
            "projectionUrl": "index.html?league=nfl" if g["gameId"] in projected else None})
    board["leagues"]["nfl"] = {"week": nfl["week"], "games": games,
        "coverageStatus": "REMAINING_GAMES_FROZEN_RESEARCH", "sourceManifestSha256": digest((capture / "manifest.json").read_bytes())}
    board["updatedAt"] = manifest["completedAt"]
    board["projectionStatus"] = "CURRENT_LEAGUE_RESEARCH_FINAL_CONTEXT_UNVERIFIED"
    (root / "data/current-matchups.json").write_text(json.dumps(board, indent=2)+"\n")
    page = (root / "current-matchups.html").read_text()
    head = page[:page.index("<body>")+6]
    e = lambda x: html.escape(str(x), quote=True)
    body = '<main><nav><a href="index.html">Projections</a><a href="#cfb">CFB</a><a href="#nfl">NFL</a><a href="recap.html">Recorded results</a></nav><h1>Current matchups</h1><p class="note">Frozen research projections. Final personnel, weather and officials remain unverified. Markets and benchmarks remain separate. Completed games without an archived pregame forecast are not backfilled.</p>'
    for league, data in board["leagues"].items():
        body += f'<section id="{league}"><h2>{league.upper()} · Week {data["week"]} · {len(data["games"])} games</h2><div class="grid">'
        for g in data["games"]:
            status = g.get("projectionStatus", "Projection unavailable")
            link = g.get("projectionUrl")
            body += f'<article class="game"><div class="time">{e(g["kickoffET"])}</div><h3>{e(g["away"])} at {e(g["home"])}</h3><p>{e(status)}</p>'
            if link:
                body += f'<a href="{e(link)}">Open research projections</a>'
            body += '</article>'
        body += '</div></section>'
    body += f'<p><small>Schedule evidence {e(board["updatedAt"])} · <a href="data/current-matchups.json">Source data</a></small></p></main></body></html>'
    (root / "current-matchups.html").write_text(head + body)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--capture", type=Path, required=True); a = p.parse_args(); publish(a.capture)
