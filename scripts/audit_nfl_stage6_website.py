#!/usr/bin/env python3
"""End-to-end audit for NFL Stage 6 shared-site technical integration.

Verifies the branch research interface consumes Stage 5 evidence while enforcing
Stage 4 release permissions. This never authorizes a production merge or bet release.
"""
from __future__ import annotations
import csv, json
from datetime import datetime, timezone
from pathlib import Path

INDEX=Path('index.html'); BOOT=Path('league-bootstrap.js'); CONTRACT=Path('NFL_SITE_INTEGRATION_CONTRACT.md')
CONFIG=Path('nfl_data/site/config.json'); PROJ=Path('nfl_data/site/projections.csv'); RESULTS=Path('nfl_data/site/results.csv'); RESEARCH=Path('nfl_data/site/research.json')
STAGE4=Path('nfl_data/validation/stage4_confidence_release_audit.json'); STAGE5=Path('nfl_data/validation/stage5_weekly_production_audit.json')
OUTJ=Path('nfl_data/validation/stage6_website_audit.json'); OUTM=Path('nfl_data/validation/STAGE6_WEBSITE_AUDIT.md')
REQUIRED=[INDEX,BOOT,Path('script.js'),Path('live-suite-loader.js'),CONTRACT,CONFIG,PROJ,RESULTS,RESEARCH,STAGE4,STAGE5]

def j(p): return json.loads(p.read_text(encoding='utf-8'))

def read_csv(path):
    with path.open(encoding='utf-8',newline='') as fh:
        reader=csv.DictReader(fh); rows=list(reader); fields=set(reader.fieldnames or [])
    return rows,fields

def main():
    missing=[str(p) for p in REQUIRED if not p.exists()]
    if missing: raise RuntimeError(f'Missing Stage 6 inputs: {missing}')
    html=INDEX.read_text(encoding='utf-8'); boot=BOOT.read_text(encoding='utf-8'); contract=CONTRACT.read_text(encoding='utf-8')
    cfg,research,s4,s5=j(CONFIG),j(RESEARCH),j(STAGE4),j(STAGE5)
    rows,pfields=read_csv(PROJ); result_rows,rfields=read_csv(RESULTS)
    needp={'league','season','week','gameId','awayTeam','homeTeam','projectedAwayPoints','projectedHomePoints','modelSpreadHome','modelTotal','homeWinProbability','awayWinProbability','marketSpreadHome','marketTotal','marketSource','marketObservedAt','executionVerified','releaseStatus','shadowModelSpreadHome','spreadReliability','totalReliability','personnelState','hardQbStateBreak','weatherRoofState','finalInactivesResolved','releaseBlockers','preferredArchitecture','winProbabilityState','websitePublishAllowed'}
    needr={'season','week','gameId','atsResult','suResult'}
    checks={
      'loader_present_once':html.count('<script src="league-bootstrap.js" defer></script>')==1,
      'loader_before_application':html.index('league-bootstrap.js')<html.index('script.js'),
      'cfb_first_time_default':"localStorage.getItem('cb-active-league') || 'cfb'" in boot,
      'nfl_data_routed_to_separate_root':'nfl_data/site/' in boot,
      'nfl_bookmarks_isolated':'cb-bookmarks-nfl' in boot,
      'nfl_record_language_is_projection_audit':'Prospective projection audit' in boot,
      'model_market_language_is_difference':'Model / market difference' in boot,
      'reliability_not_betting_confidence':'Reliability is not betting confidence' in boot,
      'shadow_is_labeled_challenger':'Shadow challenger' in boot,
      'alt_recommendation_ui_hidden':'alt-target-box' in boot and 'alt-analysis-card' in boot,
      'nfl_csv_export_includes_league':"const columns = ['league'" in boot,
      'nfl_csv_export_includes_release_fields':'releaseBlockers' in boot and 'websitePublishAllowed' in boot,
      'stage4_framework_passed':s4.get('audit_verdict')=='PASS_STAGE4_FRAMEWORK__RELEASE_EVIDENCE_NOT_EARNED',
      'stage4_recommendations_locked':s4.get('recommendation_release_allowed') is False,
      'stage5_infrastructure_passed':s5.get('audit_verdict')=='PASS_STAGE5_INFRASTRUCTURE__WEEKLY_OPERATION_ONGOING',
      'stage5_betting_signal_release_false':s5.get('website_betting_signal_release_allowed') is False,
      'site_config_is_nfl':cfg.get('league')=='NFL',
      'site_config_is_shared_site':cfg.get('separateNflSite') is False,
      'site_config_publish_false':cfg.get('websitePublishAllowed') is False,
      'site_config_moneyline_edge_hold':cfg.get('moneylineEdgeValidation')=='HOLD',
      'site_config_win_probability_research_validated':cfg.get('winProbabilityValidation')=='DISPLAY_VALIDATED_RESEARCH_ONLY',
      'projection_contract_fields_complete':needp.issubset(pfields),
      'projection_count_is_13':len(rows)==13,
      'all_projection_rows_nfl':all(r.get('league')=='NFL' for r in rows),
      'all_projection_rows_hold':all(str(r.get('releaseStatus','')).startswith('HOLD') for r in rows),
      'all_projection_rows_publish_false':all(str(r.get('websitePublishAllowed','')).lower()=='false' for r in rows),
      'all_market_rows_benchmark_labeled':all('benchmark' in str(r.get('marketSource','')).lower() for r in rows),
      'all_execution_unverified_currently':all(str(r.get('executionVerified','')).lower()=='false' for r in rows),
      'all_shadow_values_present':all(str(r.get('shadowModelSpreadHome','')).strip() for r in rows),
      'all_reliability_present':all(str(r.get('spreadReliability','')).strip() and str(r.get('totalReliability','')).strip() for r in rows),
      'all_release_blockers_present':all(str(r.get('releaseBlockers','')).strip() for r in rows),
      'probability_sums_valid':all(abs(float(r['homeWinProbability'])+float(r['awayWinProbability'])-100)<.05 for r in rows),
      'results_contract_fields_complete':needr.issubset(rfields),
      'current_results_empty_before_week6_completion':len(result_rows)==0,
      'research_core_categories_present':{'availability','weather','market','efficiency','validation','workflow'}.issubset({c.get('id') for c in research.get('categories',[])}),
      'contract_stage6_named':contract.startswith('# NFL Stage 6'),
      'contract_production_release_hold':'NFL production website release: **HOLD**' in contract,
      'contract_technical_vs_production_distinction':'Technical Stage 6 completion does **not** itself authorize merging NFL into production `main`' in contract,
    }
    failed=[k for k,v in checks.items() if not v]
    if failed: raise RuntimeError(f'Stage 6 audit failed: {failed}')
    report={
      'generated_at_utc':datetime.now(timezone.utc).isoformat(),'stage':6,'stage_name':'Website / operating interface',
      'audit_verdict':'PASS_STAGE6_TECHNICAL_INTEGRATION__PRODUCTION_RELEASE_HOLD','technical_integration_complete':True,
      'production_merge_authorized':False,'production_nfl_release_allowed':False,'recommendation_release_allowed':False,
      'website_betting_signal_release_allowed':False,'branch_preview_research_mode_ready':True,'checks':checks,'projection_rows':len(rows),
      'completed_prospective_games':s4.get('completed_prospective_games',0),'distinct_frozen_weeks':s4.get('distinct_frozen_weeks',0),
      'current_site_publication_status':cfg.get('publicationStatus'),
      'handoff':'Six-stage technical build is complete on nfl-model-development. Keep NFL production release on HOLD while prospective grading accumulates. Continue Stage 3 game-day refreshes and Stage 5 grading, then revisit Stage 4 milestones before any production-main release or betting-recommendation language.'
    }
    OUTJ.parent.mkdir(parents=True,exist_ok=True); OUTJ.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    passed=[k for k,v in checks.items() if v]
    md=['# NFL Stage 6 Website / Operating Interface Audit','',f"**Verdict:** `{report['audit_verdict']}`  ",'**Technical integration:** COMPLETE on `nfl-model-development`  ','**Production NFL release:** HOLD  ','**Recommendation release:** HOLD','','## Verified contracts','']
    md += [f'- **PASS:** `{k}`' for k in passed]
    md += ['', '## Current evidence state','',f"- NFL projection rows: **{len(rows)}**",f"- Completed prospective games: **{report['completed_prospective_games']}**",f"- Distinct frozen weeks: **{report['distinct_frozen_weeks']}**",f"- Publication status: **{report['current_site_publication_status']}**",'', '## Interpretation','', 'The six-stage technical system is integrated end to end on the NFL development branch. The interface can render the verified NFL research package while preserving HOLD/research permissions. This does not promote NFL to production `main` because the prospective evidence gates for a production release have not been earned.','', '## Handoff','',f"> {report['handoff']}"]
    OUTM.write_text('\n'.join(md)+'\n',encoding='utf-8')
    print(json.dumps({'verdict':report['audit_verdict'],'checks_passed':len(checks),'projection_rows':len(rows),'production_release':False},indent=2))

if __name__=='__main__': main()
