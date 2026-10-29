"""Count recorded regulation drives with offensive plays; not non-kneel possessions."""
from collections import Counter

def regulation_drive_counts(rows):
    seen=set();counts=Counter();excluded=Counter()
    for r in rows:
        key=(str(r['game_id']),str(r['drive_id']))
        if key in seen:raise ValueError(f'Duplicate drive: {key}')
        seen.add(key)
        try:start=int(r['start_period']);end=int(r['end_period']);plays=int(r['offensive_plays'])
        except (ValueError,TypeError):excluded['invalid_fields']+=1;continue
        if not (1<=start<=end<=4):excluded['non_regulation']+=1;continue
        if plays<=0:excluded['no_offensive_plays']+=1;continue
        if not r.get('team_id'):excluded['missing_team']+=1;continue
        counts[(str(r['game_id']),str(r['team_id']))]+=1
    return counts,dict(excluded)
