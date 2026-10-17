#!/usr/bin/env python3
"""Assemble a single development-only NFL Week-6 research export contract.

Combines immutable model snapshot, projection reliability, direct-book public web
capture, and model readiness. This is NOT a website export and cannot be
published. It exists to stabilize the future CFB/NFL site data contract while
NFL remains in prospective validation.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

SNAP=Path('nfl_data/prospective/week6_prelock_20261017T225656Z.json')
REL=Path('nfl_data/prospective/week6_projection_reliability_20261017T230853Z.json')
MKT=Path('nfl_data/prospective/market_captures/week6_betmgm_web_capture_20261017T225910Z.json')
READY=Path('nfl_data/validation/model_readiness.json')
OUT=Path('nfl_data/research_exports')

def idx(payload):return {r['game_id']:r for r in payload['rows']}

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 snap=json.loads(SNAP.read_text(encoding='utf-8'));rel=json.loads(REL.read_text(encoding='utf-8'));mkt=json.loads(MKT.read_text(encoding='utf-8'));ready=json.loads(READY.read_text(encoding='utf-8'))
 si=idx(snap);ri=idx(rel);mi=idx(mkt)
 if set(si)!=set(ri) or set(si)!=set(mi):raise RuntimeError('Snapshot/reliability/market game sets do not match')
 if ready.get('website_publish_allowed') is not False:raise RuntimeError('Readiness unexpectedly allows website publication')
 rows=[]
 for gid,s in si.items():
  r=ri[gid];m=mi[gid]
  rows.append({
   'game_id':gid,'gameday':s['gameday'],'gametime_et':s['gametime'],'away_team':s['away_team'],'home_team':s['home_team'],
   'projection':{'home_margin':s['final_research_home_margin'],'home_spread':s['projected_home_spread'],'total':s['projected_total'],'spread_model':s['spread_model'],'total_model':s['total_model']},
   'uncertainty':{'spread_68':[r['spread_68_low'],r['spread_68_high']],'spread_80':[r['spread_80_low'],r['spread_80_high']],'spread_90':[r['spread_90_low'],r['spread_90_high']],'total_68':[r['total_68_low'],r['total_68_high']],'total_80':[r['total_80_low'],r['total_80_high']],'total_90':[r['total_90_low'],r['total_90_high']]},
   'reliability':{'spread_tier':r['spread_reliability_tier'],'spread_reason':r['spread_reliability_reason'],'total_tier':r['total_reliability_tier'],'total_reason':r['total_reliability_reason'],'state_point_adjustment_applied':False},
   'state_gates':{'personnel':s['personnel_state'],'hard_qb_break':s['hard_qb_state_break'],'weather_roof':s['weather_roof_state'],'execution_price':s['execution_price_state']},
   'market_capture':{'book':m['book'],'captured_at_utc':m['capture_created_at_utc'],'home_spread':m['home_spread'],'home_spread_odds_decimal':m['home_spread_odds'],'away_spread':m['away_spread'],'away_spread_odds_decimal':m['away_spread_odds'],'total':m['total'],'over_odds_decimal':m['over_odds'],'under_odds_decimal':m['under_odds'],'spread_disagreement':m['spread_disagreement_vs_direct_book'],'spread_direction':m['spread_disagreement_direction'],'total_disagreement':m['total_disagreement_vs_direct_book'],'total_direction':m['total_disagreement_direction'],'user_account_execution_verified':False},
   'release':{'recommendation':'HOLD_NO_VALIDATED_EDGE_THRESHOLD','historical_spread_edge_threshold_earned':False,'historical_total_edge_threshold_earned':False,'website_publish_allowed':False}
  })
 now=datetime.now(timezone.utc);stamp=now.strftime('%Y%m%dT%H%M%SZ')
 payload={'schema_version':'nfl-research-v1','created_at_utc':now.isoformat(),'league':'NFL','season':2026,'week':6,'snapshot_id':snap['manifest']['snapshot_id'],'projection_state':ready['production_release_state'],'website_publish_allowed':False,'live_site_target':None,'contract_purpose':'Future site/data integration dry-run only; never consumed by live main while NFL remains HOLD.','source_timestamps':{'model_snapshot_utc':snap['manifest']['snapshot_created_at_utc'],'reliability_utc':rel['created_at_utc'],'direct_book_capture_utc':mkt['capture_created_at_utc']},'architecture':ready['final_research_architecture'],'edge_thresholds':ready['calibration_registry']['betting_edge_thresholds'],'games':rows}
 path=OUT/f'week6_research_export_{stamp}.json';path.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(json.dumps({'output':str(path),'games':len(rows),'schema_version':payload['schema_version'],'website_publish_allowed':False,'state':'RESEARCH_EXPORT_CONTRACT_READY_HOLD'},indent=2))
if __name__=='__main__':main()
