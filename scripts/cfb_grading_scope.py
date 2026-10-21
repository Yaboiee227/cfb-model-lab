"""Apply an explicit operational scope without rewriting immutable inputs."""
from datetime import datetime
from zoneinfo import ZoneInfo


def scoped_digests(scope, foundation):
    if scope is None:
        return None
    if scope.get('league') != foundation.get('league') or scope.get('season') != foundation.get('season') or scope.get('week') != foundation.get('week'):
        raise ValueError('scope and foundation league/season/week differ')
    known = {g['projectionDigest']: g for g in foundation['games']}
    selected = set()
    for game in scope['games']:
        digest = game['foundationDigest']
        if digest in selected or digest not in known:
            raise ValueError('duplicate or unknown scope foundation digest')
        kickoff = datetime.fromisoformat(game['kickoff'].replace('Z', '+00:00'))
        if kickoff.tzinfo is None:
            raise ValueError('scope kickoff requires timezone')
        frozen_kickoff = datetime.fromisoformat(known[digest]['kickoff'].replace('Z', '+00:00'))
        if kickoff != frozen_kickoff:
            raise ValueError('scope kickoff differs from immutable foundation')
        day = kickoff.astimezone(ZoneInfo(scope['timezone'])).date().isoformat()
        if day != game['gameDateET'] or not scope['dateWindowET'][0] <= day <= scope['dateWindowET'][1] or day >= scope['pauseBoundary']['beforeGameDateET']:
            raise ValueError('scope includes a paused game')
        selected.add(digest)
    if not selected or len(selected) != scope['includedGameCount']:
        raise ValueError('scope coverage mismatch')
    return selected


def row_digest(game):
    return game.get("projectionDigest") or (game.get("foundation") or {}).get("projectionDigest")


def score_request(document, allowed):
    """Temporary request view only; never save this as a replacement lock."""
    return {**document, 'games': [g for g in document['games'] if allowed is None or row_digest(g) in allowed]}
