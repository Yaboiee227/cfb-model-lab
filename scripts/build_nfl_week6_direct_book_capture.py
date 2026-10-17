#!/usr/bin/env python3
"""Timestamp a direct sportsbook Week-6 price capture and compare with the locked model snapshot.

The output is an audit record only. Public web prices may differ by jurisdiction,
account, or later movement. No recommendation is created because no historical
edge threshold has earned release.
"""
from __future__ import annotations
import csv,json
from datetime import datetime,timezone
from pathlib import Path

INPUT=Path('nfl_data/prospective/2026_week6_direct_book_capture_input.json')
SNAP=Path('nfl_data/prospective/week6_prelock_20261017T225656Z.json')
OUT=Path('nfl_data/prospective/market_captures')

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 inp=json.loads(INPUT.read_text(encoding='utf-8'));snap=json.loads(SNAP.read_text(encoding='utf-8'))
 sidx={r['game_id']:r for r in snap['rows']};g=inp['games']
 if set(sidx)!=set(g):raise RuntimeError(f'game mismatch snapshot_only={sorted(set(sidx)-set(g))} market_only={sorted(set(g)-set(sidx))}')
 now=datetime.now(timezone.utc);stamp=now.strftime('%Y%m%dT%H%M%SZ');rows=[]
 for gid,s in sidx.items():
  m=g[gid];pm=float(s['final_research_home_margin']);pt=float(s['projected_total']);hs=float(m['home_spread']);tot=float(m['total'])
  spread_dis=pm+hs;total_dis=pt-tot
  if spread_dis>0: direction='HOME_SIDE_OF_BOOK_LINE'
  elif spread_dis<0: direction='AWAY_SIDE_OF_BOOK_LINE'
  else: direction='NO_SPREAD_DISAGREEMENT'
  if total_dis>0:tdir='OVER_SIDE_OF_BOOK_TOTAL'
  elif total_dis<0:tdir='UNDER_SIDE_OF_BOOK_TOTAL'
  else:tdir='NO_TOTAL_DISAGREEMENT'
  rows.append({
   'capture_created_at_utc':now.isoformat(),'snapshot_id':snap['manifest']['snapshot_id'],'game_id':gid,'away_team':s['away_team'],'home_team':s['home_team'],
   'book':inp['book'],'source_type':inp['source_type'],'source_url':inp['source_url'],'odds_format':inp['odds_format'],
   'away_spread':m['away_spread'],'away_spread_odds':m['away_spread_odds'],'home_spread':m['home_spread'],'home_spread_odds':m['home_spread_odds'],
   'total':m['total'],'over_odds':m['over_odds'],'under_odds':m['under_odds'],
   'model_home_margin':round(pm,3),'model_total':round(pt,3),'spread_disagreement_vs_direct_book':round(spread_dis,3),'spread_disagreement_direction':direction,
   'total_disagreement_vs_direct_book':round(total_dis,3),'total_disagreement_direction':tdir,
   'schedule_home_spread_reference_at_snapshot':s['schedule_home_spread_reference'],'schedule_total_reference_at_snapshot':s['schedule_total_reference'],
   'home_spread_move_vs_snapshot_schedule_reference':round(hs-float(s['schedule_home_spread_reference']),3),'total_move_vs_snapshot_schedule_reference':round(tot-float(s['schedule_total_reference']),3),
   'user_account_execution_verified':False,'historical_edge_threshold_earned':False,'recommendation':'HOLD_NO_VALIDATED_EDGE_THRESHOLD','website_publish_allowed':False
  })
 csvp=OUT/f'week6_betmgm_web_capture_{stamp}.csv';jsonp=OUT/f'week6_betmgm_web_capture_{stamp}.json'
 with csvp.open('x',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 payload={'capture_created_at_utc':now.isoformat(),'snapshot_id':snap['manifest']['snapshot_id'],'book':inp['book'],'source_url':inp['source_url'],'capture_policy':inp['capture_policy'],'games':len(rows),'recommendation_policy':'All rows HOLD. Direct book web prices are captured for prospective comparison only; no historical edge threshold has earned release.','rows':rows,'website_publish_allowed':False}
 jsonp.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(json.dumps({'csv':str(csvp),'json':str(jsonp),'games':len(rows),'state':'DIRECT_BOOK_WEB_CAPTURED_HOLD'},indent=2))
if __name__=='__main__':main()
