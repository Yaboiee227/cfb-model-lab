#!/usr/bin/env python3
from __future__ import annotations

import record_tracker as legacy
from projection_locking import validate_week_locks


# Preserve the original legacy whole-file validator before replacing the module
# global used by grade_week(). Calling legacy.validate_lock after monkey-patching
# would recurse back into validate_lock_v2.
_legacy_validate_lock = legacy.validate_lock


def _uses_per_game_locking(payload: dict) -> bool:
    """Return True only for snapshots carrying the per-game lock contract."""
    if payload.get("lockMode") == "per-game-v2":
        return True
    games = payload.get("games", [])
    return bool(games) and any(
        game.get("locked") is True and bool(game.get("lockDigest")) for game in games
    )


def validate_lock_v2(payload: dict) -> None:
    """Accept legacy whole-file locks and new per-game locks.

    New snapshots must have every game individually locked before grading. Older
    archived weeks keep using the original whole-file digest so historical data
    does not need to be rewritten.
    """
    if _uses_per_game_locking(payload):
        try:
            validate_week_locks(payload, require_all=True)
        except ValueError as exc:
            raise legacy.RecordError(str(exc)) from exc
        return

    _legacy_validate_lock(payload)


# grade_week resolves validate_lock from the imported module's globals at runtime.
legacy.validate_lock = validate_lock_v2


if __name__ == "__main__":
    # Reuse the established CLI and grading behavior; only lock validation changes.
    legacy.main()
