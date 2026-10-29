"""Append an immutable, manually reviewed pregame QB observation.
This records evidence, not a starter probability or point adjustment.
"""
import json,hashlib,argparse
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
R=Path(__file__).resolve().parents[1]
STATES={'UNRESOLVED','PRACTICE_FULL_NOT_START_CONFIRMED','CONFIRMED_STARTER','RULED_OUT'}

def prepare(request,projection,now):
 games={g['gameId']:g for g in projection['games']};g=games[request['gameId']]
 team=request['team'];assert team in g['gameId'].split('_')[-2:],'Team does not belong to game'
 kickoff=datetime.fromisoformat(g['kickoffUTC'].replace('Z','+00:00'))
 assert now.tzinfo and now<kickoff,'Prospective observation must be before kickoff'
 assert request['state'] in STATES
 assert request.get('reviewed') is True,'Explicit source review required'
 assert urlparse(request['sourceUrl']).scheme=='https'
 assert request.get('sourcePublishedDate') and request.get('player')
 published=datetime.fromisoformat(request['sourcePublishedDate']).date();assert published<=now.date(),'Future publication date'
 # Do not accept supplied historical observation timestamps as new observations.
 assert 'observedAt' not in request
 record={**request,'observedAt':now.isoformat(),'kickoff':g['kickoffUTC'],'forecastFrozenAt':projection['frozenAt'],'baselineStarterAssumption':'NOT_EXPLICITLY_RECORDED','numericalAdjustmentApplied':False,'canonicalInfluence':False,'evidenceClass':'CURRENT_SOURCE_REVIEW_NOT_ARCHIVED_HISTORICAL_CAPTURE'}
 record['observationDigest']=hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()
 return record

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--request',type=Path,required=True);ap.add_argument('--week',type=int,default=8);a=ap.parse_args()
 projection_path=R/f'nfl/research-projections/week-{a.week:02d}.json';projection=json.loads(projection_path.read_text());request=json.loads(a.request.read_text());record=prepare(request,projection,datetime.now(timezone.utc));record['projectionSha256']=hashlib.sha256(projection_path.read_bytes()).hexdigest()
 folder=R/f'nfl_data/prospective/week{a.week}/qb-observations';folder.mkdir(parents=True,exist_ok=True);path=folder/(record['observationDigest']+'.json')
 with path.open('x') as f:json.dump(record,f,indent=2);f.write('\n')
 print(path.relative_to(R))
if __name__=='__main__':main()
