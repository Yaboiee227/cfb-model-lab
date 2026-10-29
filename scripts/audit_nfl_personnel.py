"""Audit saved Week 7 personnel evidence; unknown timing remains unknown."""
import csv,json,hashlib
from pathlib import Path
from personnel_readiness import assess_personnel
R=Path(__file__).resolve().parents[1];root=R/'nfl_data/prospective/week7'
report_path=root/'pregame_refresh/20261025T163736Z_FINAL_PUBLICATION.json';report=json.loads(report_path.read_text());by_game={g['game_id']:g for g in report['games']}
gates=json.loads((root/'20261021T114427Z/context_market_gates.json').read_text());archive={r['gameId']:r for r in csv.DictReader((R/'nfl_data/site/archive/week7-before-week8/projections.csv').open())};rows=[]
for g in gates:
 gid=g['game_id'];r=archive[gid];e=by_game.get(gid);flag=r['hardQbStateBreak'].lower()=='true'
 # A saved false flag is not positive evidence of an unchanged QB.
 qb_change=True if flag else None
 result=assess_personnel(kickoff=g['kickoff_utc'],observed_at=report['observed_at_utc'] if e else None,report_game_id=e['game_id'] if e else None,game_id=gid,final_availability_verified=e.get('final_inactives_complete') is True if e else False,qb_change=qb_change,adjustment_validated=False,adjustment_applied=False)
 rows.append(dict(gameId=gid,archivedQbBreakFlag=flag,archivedOperationalPointAdjustment=r.get('qbOperationalPointAdjustment'),materialContext=e.get('material_context') if e else None,**result))
out=dict(canonicalInfluence=False,scope='Saved October 25 16:37 UTC publication checkpoint, not all later final-window captures',sourcePath=str(report_path.relative_to(R)),sourceSha256=hashlib.sha256(report_path.read_bytes()).hexdigest(),games=rows,findings=['Saved publication reports zero numerical projection changes.','Final inactive lists are not evidence that the predictor includes current QB/personnel state.','A false hard-QB-break flag is not a verified unchanged starter.','This audit does not establish that personnel changes caused observed forecast errors.'],status='PERSONNEL_INTEGRATION_GAP_CONFIRMED_NO_NUMERIC_FIX_PROMOTED')
(R/'research/model-improvement/nfl-personnel-audit.json').write_text(json.dumps(out,indent=2)+'\n');print('Audited',len(rows),'games;',sum(r['archivedQbBreakFlag'] for r in rows),'archived QB-break flags; no unsupported adjustment applied')

current=json.loads((R/'nfl/research-projections/week-08.json').read_text())
current_rows=[]
for g in current['games']:
 current_rows.append(dict(gameId=g['gameId'],**assess_personnel(kickoff=g['kickoffUTC'],observed_at=None,report_game_id=None,game_id=g['gameId'],final_availability_verified=False,qb_change=None)))
(R/'research/model-improvement/week8-personnel-gates.json').write_text(json.dumps(dict(canonicalInfluence=False,source='nfl/research-projections/week-08.json',policy='Projection freeze timestamp is not an official availability observation. No current dated official report supplied to this audit.',games=current_rows),indent=2)+'\n')
