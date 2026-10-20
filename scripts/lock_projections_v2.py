#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from projection_locking import lock_game, lock_games_before, validate_week_locks
from record_tracker import atomic_json


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Per-game projection locker. Later kickoffs remain editable until their own lock."
    )
    ap.add_argument("path", help="Weekly projection JSON path")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="Lock every game now")
    group.add_argument(
        "--through",
        help="Lock games with kickoff <= this timezone-aware ISO timestamp",
    )
    ap.add_argument(
        "--lead-minutes",
        type=int,
        default=0,
        help="With default mode, lock games kicking off within this many minutes",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = Path(args.path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    stamp = now.isoformat().replace("+00:00", "Z")

    if args.all:
        locked = []
        for game in payload.get("games", []):
            if game.get("locked") is not True:
                lock_game(game, locked_at=stamp)
                locked.append(str(game.get("gameId")))
    elif args.through:
        cutoff = datetime.fromisoformat(args.through.replace("Z", "+00:00"))
        if cutoff.tzinfo is None:
            raise SystemExit("--through must include a timezone")
        locked = lock_games_before(payload, cutoff, locked_at=stamp)
    else:
        cutoff = now + timedelta(minutes=max(args.lead_minutes, 0))
        locked = lock_games_before(payload, cutoff, locked_at=stamp)

    # Validate every already-locked game. Unlocked later games are intentionally allowed.
    validate_week_locks(payload, require_all=False)
    payload["lockMode"] = "per-game-v2"
    payload["lastLockSweepAt"] = stamp

    if args.dry_run:
        print(json.dumps({"locked": locked, "payload": payload}, indent=2))
        return

    atomic_json(path, payload)
    print(json.dumps({"locked": locked, "count": len(locked), "path": str(path)}))


if __name__ == "__main__":
    main()
