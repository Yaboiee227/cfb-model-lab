#!/usr/bin/env python3
"""Rebuild derived Week 8 pregame views without changing source captures or locks."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from merge_pregame_refresh import merge_state
from cfb_active_window_state import build_state
from record_tracker import atomic_json, load_aliases
from validate_pregame_state import audit_state, parse_dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--as-of')
    args = ap.parse_args()
    as_of = parse_dt(args.as_of) if args.as_of else datetime.now(timezone.utc)
    root = Path('.')
    read = lambda p: json.loads(Path(p).read_text())
    paths = [f'cfb/pregame/week-08-{day}-effective.json' for day in ('tuesday', 'wednesday', 'thursday')]
    overlays = [read(p) for p in sorted(root.glob('cfb/pregame-refresh/week-08-tuesday-*.json'))]
    if not overlays:
        raise ValueError('Tuesday source overlays missing')
    tuesday = merge_state(read('cfb/pregame/week-08-tuesday-open.json'), overlays)
    tuesday["observedAt"] = max(o["observedAt"] for o in overlays)
    atomic_json(Path(paths[0]), tuesday)
    contexts = [(p, read(p)) for p in paths]
    unified = build_state(read('cfb/pregame/week-08-active-through-thursday.json'),
                          read('cfb/research-locks/week-08-foundation-full.json'),
                          contexts, load_aliases(root))
    atomic_json(Path('cfb/pregame/week-08-through-thursday-effective.json'), unified)
    for day, (_, doc) in zip(('tuesday', 'wednesday'), contexts[:2]):
        atomic_json(Path(f'cfb/pregame/week-08-{day}-readiness.json'), audit_state(doc, as_of))
    print(json.dumps({'games': len(unified['games']), 'readinessDays': ['tuesday', 'wednesday'],
                      'sourceObservedAt': unified['observedAt'], 'canonicalPromotionAuthorized': False}))


if __name__ == '__main__':
    main()
