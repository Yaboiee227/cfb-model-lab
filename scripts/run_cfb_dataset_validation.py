"""Run existing feature tests from published SportsDataverse season files."""
import sys,csv,json,argparse,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import cfb_foundation_feature_validation as ff
import cfb_shadow_engine as engine
import cfb_rich_challenger as rich
ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--output',required=True);a=ap.parse_args();root=Path.cwd();cache={};boxes={}
for year in [2025,2026]:
 rows=list(csv.DictReader((a.inputs/f'cfb_schedule_{year}.csv').open()));games=[];names={}
 for r in rows:
  if r['season_type']!='2' or r['status']!='STATUS_FINAL':continue
  home,away=engine.canonical_school(r['home_team']),engine.canonical_school(r['away_team']);names[r['home_id']]=home;names[r['away_id']]=away
  games.append(engine.Game(str(r['game_id']),engine.parse_dt(r['game_date']),home,away,float(r['home_score']),float(r['away_score']),r['neutral_site'].lower()=='true'))
 cache[year]=sorted(games,key=lambda g:(g.kickoff,g.game_id))
 for r in csv.DictReader((a.inputs/f'team_box_{year}.csv').open()):
  gid=str(r['game_id']);key=names.get(r['team_id'])
  if key:
   boxes.setdefault(gid,{})[key]=rich.normalized_box([dict(name=k,displayValue=v) for k,v in r.items()])
 print(year,len(cache[year]),'regular finals',flush=True)
def fetch_games(start,end):return [g for y in range(start.year,end.year+1) for g in cache.get(y,[]) if start<=g.kickoff<end]
def fetch_boxes(games):
 out={g.game_id:boxes[g.game_id] for g in games if g.home in boxes.get(g.game_id,{}) and g.away in boxes.get(g.game_id,{})}
 return out,[dict(gameId=g.game_id,error='Dataset missing both team boxes') for g in games if g.game_id not in out]
prior=json.loads((root/'cfb/validation/week-08-foundation-feature-family-validation.json').read_text())
ff.estimate_prior_only_hfa=lambda *args,**kwargs:(prior['hfa']['2025'],prior['hfa']['2025SeasonEstimates'])
engine.fetch_completed_games=fetch_games;rich.fetch_boxes=fetch_boxes
sys.argv=['cfb_foundation_feature_validation.py','--as-of','2026-10-27T04:00:00Z','--output',a.output];ff.main()
p=Path(a.output);d=json.loads(p.read_text());d['alternateSource']={'publisher':'SportsDataverse','upstream':'ESPN-derived; not independent corroboration','historicalRevisionWarning':'Current revised season files, not archived original pregame bytes','files':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in a.inputs.glob('*.csv')}};d['warning']+=' Alternate-source retrospective replication; eligibility requires baseline coverage/parity review.';p.write_text(json.dumps(d,indent=2)+'\n')
