#!/usr/bin/env python3
"""Freeze a non-canonical research shadow before kickoff for prospective grading.

The output is immutable by policy: if it already exists, the script verifies the
stored digest and source payload rather than rewriting history. No market data is
added here; this lock exists solely to preserve the exact research projection
that was available before kickoff.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_dt(value: str) -> datetime:
    dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if dt.tzinfo is None:
        raise ValueError('timezone required')
    return dt.astimezone(timezone.utc)


def iso(dt: datetime)->str:
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00','Z')


def digest(value: Any)->str:
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def build_lock(source:dict[str,Any],locked_at:datetime)->dict[str,Any]:
    if source.get('canonicalInfluence') is not False:
        raise ValueError('research source must have canonicalInfluence=false')
    if source.get('canonicalPromotionAuthorized') is not False:
        raise ValueError('research source must not authorize canonical promotion')
    games=[]
    for g in source.get('games',[]):
        kickoff=parse_dt(g['kickoff'])
        if locked_at>=kickoff:
            raise ValueError(f"cannot prospectively lock {g['gameId']} at/after kickoff")
        required=('projectedAwayPoints','projectedHomePoints','projectedMarginHome','projectedSpreadHome','projectedTotal','homeWinProbability','projectedWinner')
        missing=[k for k in required if g.get(k) is None]
        if missing:
            raise ValueError(f"{g['gameId']} missing projection fields: {missing}")
        payload={
            'gameId':g['gameId'],'awayTeam':g['awayTeam'],'homeTeam':g['homeTeam'],'kickoff':g['kickoff'],
            **{k:g[k] for k in required},
        }
        games.append({**payload,'projectionDigest':digest(payload)})
    body={
        'schemaVersion':1,'league':source.get('league'),'season':source.get('season'),'week':source.get('week'),
        'role':'IMMUTABLE_PROSPECTIVE_RESEARCH_SHADOW_LOCK','canonicalInfluence':False,'canonicalPromotionAuthorized':False,
        'modelId':source.get('modelId'),'sourceAsOf':source.get('asOf'),'lockedAt':iso(locked_at),
        'lockedParameters':source.get('lockedParameters'),'structuralHomeMarginAdvantage':source.get('structuralHomeMarginAdvantage'),
        'sourcePolicy':source.get('source'),
        'games':games,
        'gradingPolicy':'After results, grade these exact frozen research projections separately. Never rewrite them and never merge their record into the established canonical record.',
    }
    body['lockDigest']=digest({k:v for k,v in body.items() if k!='lockDigest'})
    return body


def verify(lock:dict[str,Any])->None:
    expected=digest({k:v for k,v in lock.items() if k!='lockDigest'})
    if lock.get('lockDigest')!=expected:
        raise ValueError('research lock digest mismatch')
    for g in lock.get('games',[]):
        payload={k:v for k,v in g.items() if k!='projectionDigest'}
        if g.get('projectionDigest')!=digest(payload):
            raise ValueError(f"projection digest mismatch: {g.get('gameId')}")


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('source')
    ap.add_argument('output')
    args=ap.parse_args()
    source=json.loads(Path(args.source).read_text(encoding='utf-8'))
    out_path=Path(args.output)
    if out_path.exists():
        existing=json.loads(out_path.read_text(encoding='utf-8'))
        verify(existing)
        if existing.get('modelId')!=source.get('modelId'):
            raise ValueError('existing lock belongs to different model')
        print(json.dumps({'status':'ALREADY_LOCKED_VERIFIED','modelId':existing['modelId'],'lockedAt':existing['lockedAt'],'lockDigest':existing['lockDigest']},indent=2))
        return
    lock=build_lock(source,datetime.now(timezone.utc))
    verify(lock)
    out_path.parent.mkdir(parents=True,exist_ok=True)
    out_path.write_text(json.dumps(lock,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'LOCKED','modelId':lock['modelId'],'lockedAt':lock['lockedAt'],'games':len(lock['games']),'lockDigest':lock['lockDigest']},indent=2))


if __name__=='__main__':
    main()
