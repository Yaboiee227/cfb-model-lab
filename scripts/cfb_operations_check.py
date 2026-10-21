#!/usr/bin/env python3
"""Read-only Week 8 handoff: verify saved evidence and show the active work queue.

No network calls, locks, grading, model fitting or production-file writes.
The JSON on stdout is a new audit, never a new source observation.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from cfb_active_window_state import build_state, unique_context_match
from cfb_market_research_lock import verify_existing
from cfb_research_pregame_audit import build_audit
from record_tracker import load_aliases
from validate_pregame_state import audit_game, parse_dt


def check(root, as_of):
    root = Path(root)
    evidence = {}

    def read(name):
        raw = (root / name).read_bytes()
        evidence[name] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    scope = read('cfb/pregame/week-08-active-through-thursday.json')
    foundation = read(scope['frozenFoundation'])
    gate = read('cfb/projections/week-08-status.json')
    market = read('cfb/research-market-locks/week-08-foundation-market.json')
    sagarin = read('cfb/benchmarks/week-08-sagarin-full.json')
    decision = read('cfb/validation/week-08-rebuild-decision.json')
    read('data/team-aliases.json')
    aliases = load_aliases(root)
    contexts = [(f'cfb/pregame/week-08-{day}-effective.json',
                 read(f'cfb/pregame/week-08-{day}-effective.json'))
                for day in ('tuesday', 'wednesday', 'thursday')]
    boundary = scope['pauseBoundary']['beforeGameDateET']
    for game in scope['games']:
        date_et = parse_dt(game['kickoff']).astimezone(ZoneInfo(scope['timezone'])).date().isoformat()
        if date_et != game['gameDateET'] or not scope['dateWindowET'][0] <= date_et <= scope['dateWindowET'][1] or date_et >= boundary:
            raise ValueError(f"game outside authorized date window: {game['gameId']}")
    verify_existing(market, foundation)
    unified = build_state(scope, foundation, contexts, aliases)
    coverage = build_audit(scope, foundation, sagarin, aliases, as_of, contexts, market)
    games = []
    for row in coverage['games']:
        _, _, context_game = unique_context_match(row, contexts, aliases)
        ready = audit_game(context_game, as_of)
        started = parse_dt(row['kickoff']) <= as_of
        games.append({
            **row,
            'phase': 'KICKOFF_PASSED_VERIFY_FINAL' if started else 'PREGAME',
            'nextAction': 'Check final status; grade only preserved evidence. No pregame reconstruction.' if started else 'Refresh unresolved sources before T-60; existing market job captures T-30 locks.',
            'canonicalGate': gate['status'],
            'releaseBlockers': gate.get('reasons', []) + ready['blockers'],
            'readinessWarnings': ready['warnings'],
        })
    return {
        'schemaVersion': 1, 'role': 'READ_ONLY_OPERATIONS_HANDOFF',
        'auditedAt': as_of.isoformat(), 'canonicalInfluence': False,
        'sourceRefreshPerformed': False, 'pauseBeforeGameDateET': boundary,
        'canonicalGate': gate,
        'challengerDecision': {'source': 'cfb/validation/week-08-rebuild-decision.json',
                               'status': decision['status'], 'policy': decision['week8Policy']},
        'summary': coverage['summary'], 'games': games,
        'sourceObservedAt': unified['observedAt'],
        'inputSha256': evidence,
        'policy': 'Audit time does not refresh source timestamps. Kickoff passed does not mean FINAL. No release or promotion is authorized by this check.'
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    parser.add_argument('--as-of', help='Audit clock for reproducible review, never a source observation time')
    args = parser.parse_args()
    as_of = parse_dt(args.as_of) if args.as_of else datetime.now(timezone.utc)
    print(json.dumps(check(args.root, as_of), indent=2))


if __name__ == '__main__':
    main()
