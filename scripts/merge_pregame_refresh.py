#!/usr/bin/env python3
"""Merge timestamped pregame refresh overlays into an effective game state.

Original captures stay immutable audit artifacts. Later official-source refreshes
are applied deterministically by gameId and produce a separate effective state.
Lists in a patch replace the prior list; dictionaries are recursively merged.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


def deep_merge(base: Any, patch: Any) -> Any:
    if isinstance(base, dict) and isinstance(patch, dict):
        out = copy.deepcopy(base)
        for key, value in patch.items():
            if key in out and isinstance(out[key], dict) and isinstance(value, dict):
                out[key] = deep_merge(out[key], value)
            else:
                out[key] = copy.deepcopy(value)
        return out
    return copy.deepcopy(patch)


def merge_state(base_doc: dict[str, Any], overlays: list[dict[str, Any]]) -> dict[str, Any]:
    out = copy.deepcopy(base_doc)
    by_id = {g.get("gameId"): i for i, g in enumerate(out.get("games", []))}
    applied = []

    ordered = sorted(overlays, key=lambda d: str(d.get("observedAt") or ""))
    for overlay in ordered:
        observed_at = overlay.get("observedAt")
        overlay_role = overlay.get("role")
        for item in overlay.get("games", []):
            gid = item.get("gameId")
            if gid not in by_id:
                raise ValueError(f"refresh overlay references unknown gameId: {gid}")
            patch = item.get("patch")
            if not isinstance(patch, dict):
                raise ValueError(f"refresh overlay patch must be object: {gid}")
            idx = by_id[gid]
            out["games"][idx] = deep_merge(out["games"][idx], patch)
        applied.append({
            "observedAt": observed_at,
            "role": overlay_role,
            "gameCount": len(overlay.get("games", [])),
        })

    out["status"] = "OPEN_EFFECTIVE"
    out["effectiveState"] = {
        "baseStatus": base_doc.get("status"),
        "overlayCount": len(ordered),
        "appliedOverlays": applied,
        "rule": "Original base capture remains unchanged; this effective state applies timestamped refresh overlays in observedAt order."
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--overlay", action="append", default=[], required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    base = json.loads(Path(args.base).read_text(encoding="utf-8"))
    overlays = [json.loads(Path(p).read_text(encoding="utf-8")) for p in args.overlay]
    out = merge_state(base, overlays)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(path),
        "games": len(out.get("games", [])),
        "overlays": out["effectiveState"]["overlayCount"]
    }, indent=2))


if __name__ == "__main__":
    main()
