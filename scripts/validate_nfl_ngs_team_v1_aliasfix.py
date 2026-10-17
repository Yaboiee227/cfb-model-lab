#!/usr/bin/env python3
"""Canonical team-ID and validation-metadata shim for the NGS v1 validator.

The NGS feed uses provider abbreviations such as LAR/JAC/WSH while the model
uses LA/JAX/WAS. The base validator also returned an inner-validation `n` inside
the selected parameter record; its summary merge could overwrite the outer-fold
sample count. This shim preserves that value as `inner_validation_n` so aggregate
metrics are weighted by the actual unseen fold sizes.
"""
from __future__ import annotations
import validate_nfl_ngs_team_v1 as v1

ALIASES = {"LAR":"LA", "STL":"LA", "JAC":"JAX", "WSH":"WAS", "WFT":"WAS", "OAK":"LV", "SD":"LAC", "SDG":"LAC"}
_orig_index = v1.load_index
_orig_select = v1.select

def load_index_canonical():
    idx, leak, nrows = _orig_index()
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

def select_without_outer_n_collision(train, kind, family):
    best, top = _orig_select(train, kind, family)
    best = dict(best)
    if "n" in best:
        best["inner_validation_n"] = best.pop("n")
    return best, top

v1.load_index = load_index_canonical
v1.select = select_without_outer_n_collision

if __name__ == "__main__":
    v1.main()
