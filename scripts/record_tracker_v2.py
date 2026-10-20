#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import record_tracker as legacy
from projection_locking import validate_week_locks


def validate_lock_v2(payload: dict) -> None:
    """Accept legacy whole-file locks and new per-game locks.

    New snapshots must have every game individually locked before grading. Older
    archived weeks keep using the original whole-file digest so historical data
    does not need to be rewritten.
    """
    games = payload.get("games", [])
    if games and all(game.get("locked") is True for game in games):
        validate_week_locks(payload, require_all=True)
        return
    legacy.validate_lock(payload)


# grade_week resolves validate_lock from the imported module's globals at runtime.
legacy.validate_lock = validate_lock_v2


if __name__ == "__main__":
    # Reuse the established CLI and grading behavior; only lock validation changes.
    legacy.main()
