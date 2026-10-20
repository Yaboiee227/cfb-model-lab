#!/usr/bin/env python3
"""Week 8 runner for the CFB shadow engine.

ESPN's FBS-only `site.web.api` teams response nests teams under conference
`groups[*].teams`. Keep this adapter separate until the upstream engine parser is
fully generalized; the model itself remains unchanged.
"""
from __future__ import annotations

import cfb_shadow_engine as engine


def extract_grouped_team_ids(doc):
    ids = set()
    for sport in doc.get("sports", []):
        for league in sport.get("leagues", []):
            for group in league.get("groups", []):
                for entry in group.get("teams", []):
                    team = entry.get("team") or entry
                    if team.get("id") is not None:
                        ids.add(str(team["id"]))
            # Preserve compatibility if ESPN also returns a flat teams list.
            for entry in league.get("teams", []):
                team = entry.get("team") or entry
                if team.get("id") is not None:
                    ids.add(str(team["id"]))
    for entry in doc.get("teams", []):
        team = entry.get("team") or entry
        if team.get("id") is not None:
            ids.add(str(team["id"]))
    return sorted(ids, key=lambda x: (len(x), x))


engine.extract_team_ids = extract_grouped_team_ids


if __name__ == "__main__":
    engine.main()
