"""Public comparison snapshot only. Never writes projections, results or locks."""
import csv, hashlib, json, math
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

URL='https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&seasontype=2&week=7&limit=100'
def normalize(event, frozen, observed):
    c=event['competitions'][0]
    teams={x['homeAway']:x['team']['abbreviation'] for x in c['competitors']}
    a,h=[{'LAR':'LA'}.get(teams[k],teams[k]) for k in ('away','home')]
    gid=f'2026_07_{a}_{h}'
    assert gid in frozen
    kickoff=datetime.fromisoformat(event['date'].replace('Z','+00:00'))
    assert kickoff==datetime.fromisoformat(frozen[gid]['kickoff_utc'])
    if event['status']['type']['name']!='STATUS_SCHEDULED' or kickoff<=observed:return None
    books=[o for o in c.get('odds',[]) if o.get('provider',{}).get('name')=='Draft Kings']
    if len(books)!=1:return None
    o=books[0]; ps=o['pointSpread']; total=o['total']
    hs=float(ps['home']['close']['line']); aws=float(ps['away']['close']['line'])
    over=float(total['over']['close']['line'].removeprefix('o')); under=float(total['under']['close']['line'].removeprefix('u'))
    assert all(math.isfinite(v) for v in (hs,aws,over,under)) and abs(hs+aws)<1e-8 and over==under and over>0
    assert abs(over-float(o['overUnder']))<1e-8
    model=-float(frozen[gid]['canonical_home_margin']); gap=hs-model
    return dict(gameId=gid,away=a,home=h,kickoffUtc=kickoff.isoformat(),marketSpreadHome=hs,marketTotal=over,
        modelSpreadHome=model,gapHome=gap,gapSide=h if gap>0 else a if gap<0 else 'Aligned',gapMagnitude=abs(gap),
        prices={side:ps[side]['close']['odds'] for side in ('home','away')},
        marketSource='ESPN / DraftKings comparison reference',marketObservedAt=observed.isoformat(),
        providerUpdatedAt=None,executionVerified=False,eligibleForGrading=False,
        sourceFieldNote='API close field is the current displayed quote for a scheduled game, not a certified closing line.')

def main():
    root=Path('nfl_data/prospective/week7'); freeze=root/'20261021T114427Z'
    manifest=json.loads((freeze/'manifest.json').read_text())
    for name,digest in manifest['files'].items():assert hashlib.sha256((freeze/name).read_bytes()).hexdigest()==digest
    with (freeze/'paired_projections.csv').open() as f: frozen={r['game_id']:r for r in csv.DictReader(f)}
    with urlopen(Request(URL,headers={'User-Agent':'CBModelProjections research'}),timeout=30) as r:raw=r.read()
    now=datetime.now(timezone.utc);data=json.loads(raw)
    games=[v for e in data['events'] if (v:=normalize(e,frozen,now)) is not None]
    assert len({g['gameId'] for g in games})==len(games)
    payload=dict(observedAt=now.isoformat(),source=URL,sourceSha256=hashlib.sha256(raw).hexdigest(),provider='DraftKings via ESPN',
        providerUpdatedAt=None,eligibleForGrading=False,executionVerified=False,games=games,
        note='Current comparison only. Retrieval time is not provider update time. Completed games are excluded; no lock backfill.')
    folder=root/'reference_captures'/now.strftime('%Y%m%dT%H%M%SZ');folder.mkdir(parents=True,exist_ok=False)
    (folder/'source.json').write_bytes(raw)
    (folder/'reference.json').write_text(json.dumps(payload,indent=2)+'\n')
    Path('nfl_data/site/market-reference.json').write_text(json.dumps(payload,indent=2)+'\n')
    print(folder)
    for g in games:print(g['gameId'],g['marketSpreadHome'],g['marketTotal'],g['gapSide'],round(g['gapMagnitude'],2))
if __name__=='__main__':main()
