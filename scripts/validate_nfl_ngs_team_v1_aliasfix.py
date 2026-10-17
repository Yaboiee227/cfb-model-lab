#!/usr/bin/env python3
"""Canonical team-ID shim for the NGS v1 validator.

The NGS feed uses historical/provider abbreviations such as LAR/JAC/WSH while
the model canonical schedule uses LA/JAX/WAS. This adds canonical lookup keys
without dropping or modifying any source rows.
"""
from __future__ import annotations
import validate_nfl_ngs_team_v1 as v1

ALIASES = {"LAR":"LA", "STL":"LA", "JAC":"JAX", "WSH":"WAS", "WFT":"WAS", "OAK":"LV", "SD":"LAC", "SDG":"LAC"}
_orig = v1.load_index

def load_index_canonical():
    idx, leak, nrows = _orig()
    additions = {}
    for (season, week, team), row in list(idx.items()):
        canonical = ALIASES.get(team, team)
        if canonical != team:
            key = (season, week, canonical)
            if key in idx and idx[key] is not row:
                raise RuntimeError(f"Canonical NGS team collision: {key}")
            additions[key] = row
    idx.update(additions)
    return idx, leak, nrows

v1.load_index = load_index_canonical

if __name__ == "__main__":
    v1.main()
