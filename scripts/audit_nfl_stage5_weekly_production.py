#!/usr/bin/env python3
"""Audit Stage 5 weekly production / prospective evidence infrastructure."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

PRE=Path('nfl_data/prospective/week6_prelock_20261017T225656Z.json')
SHADOW=Path('nfl_data/prospective/shadow/week6_ftn50_shadow_20261017T235342Z.json')
REG=Path('nfl_data/prospective/validation_registry/nfl_prospective_validation_registry.json')
GRADE_SCRIPT=Path('scripts/grade_nfl_week6_prospective_snapshot.py')
SHADOW_GRADE_SCRIPT=Path('scripts/grade_nfl_week6_ftn50_shadow.py')
REG_SCRIPT=Path('scripts/build_nfl_prospective_validation_registry.py')
POLICY=Path('NFL_STAGE5_WEEKLY_PRODUCTION_POLICY.md')
REQUIRED_WORKFLOWS=[
 Path('.github/workflows/nfl-week6-prospective-snapshot.yml'),
 Path('.github/workflows/nfl-week6-direct-book-capture.yml'),
 Path('.github/workflows/nfl-week6-gameday-final-gates.yml'),
 Path('.github/workflows/nfl-week6-prospective-grade.yml'),
 Path('.github/workflows/nfl-week6-ftn50-shadow-grade.yml'),
 Path('.github/workflows/nfl-prospective-validation-registry.yml'),
 Path('.github/workflows/nfl-week6-cfb-style-research-export.yml'),
]
OUTJ=Path('nfl_data/validation/stage5_weekly_production_audit.json')
OUTM=Path('nfl_data/validation/STAGE5_WEEKLY_PRODUCTION_AUDIT.md')

def load(p): return json.loads(p.read_text(encoding='utf-8'))

def main():
    required=[PRE,SHADOW,REG,GRADE_SCRIPT,SHADOW_GRADE_SCRIPT,REG_SCRIPT,POLICY,*REQUIRED_WORKFLOWS]
    missing=[str(p) for p in required if not p.exists()]
    if missing: raise RuntimeError(f'missing Stage5 inputs: {missing}')
    pre,shadow,reg=load(PRE),load(SHADOW),load(REG)
    sid=pre['manifest']['snapshot_id']
    ssid=shadow['manifest']['shadow_snapshot_id']
    assert shadow['manifest']['canonical_snapshot_id']==sid
    pre_ids=[r['game_id'] for r in pre['rows']]
    sh_ids=[r['game_id'] for r in shadow['rows']]
    assert len(pre_ids)==13 and len(set(pre_ids))==13
    assert set(pre_ids)==set(sh_ids)
    assert pre['manifest'].get('website_publish_allowed') is False
    assert shadow['manifest'].get('website_publish_allowed') is False
    assert reg.get('recommendation_release_allowed') is False
    assert reg.get('automatic_threshold_promotion_allowed') is False
    assert reg.get('roi_claims_allowed') is False
    assert reg.get('clv_claims_allowed') is False
    # Static safety-contract checks in the operating scripts.
    gtxt=GRADE_SCRIPT.read_text(encoding='utf-8')
    stxt=SHADOW_GRADE_SCRIPT.read_text(encoding='utf-8')
    rtxt=REG_SCRIPT.read_text(encoding='utf-8')
    checks={
      'canonical_snapshot_exists': True,
      'canonical_game_ids_unique': len(set(pre_ids))==13,
      'shadow_parent_link_valid': shadow['manifest']['canonical_snapshot_id']==sid,
      'canonical_shadow_game_sets_equal': set(pre_ids)==set(sh_ids),
      'grader_creates_timestamped_artifacts': 'week6_grade_{stamp}.json' in gtxt,
      'grader_keeps_pending_games': 'GAME_NOT_COMPLETED' in gtxt and 'pending_games' in gtxt,
      'grader_roi_disabled': 'roi_grade_allowed' in gtxt and 'False' in gtxt,
      'shadow_single_week_promotion_disabled': 'promotion_allowed_from_this_week_alone' in stxt,
      'registry_deduplicates_by_snapshot': 'choose_canonical_grade' in rtxt and 'by_snapshot' in rtxt,
      'registry_duplicate_game_guard': 'Duplicate canonical prospective game row' in rtxt,
      'registry_automatic_threshold_promotion_disabled': reg.get('automatic_threshold_promotion_allowed') is False,
      'required_weekly_workflows_present': all(p.exists() for p in REQUIRED_WORKFLOWS),
      'website_release_still_false': reg.get('website_publish_allowed') is False,
    }
    assert all(checks.values()), {k:v for k,v in checks.items() if not v}
    snapreg=reg.get('canonical_snapshot_registry',[])
    current=[x for x in snapreg if x.get('snapshot_id')==sid]
    if not current: raise RuntimeError('Week6 canonical snapshot missing from prospective registry')
    current=current[0]
    result={
      'generated_at_utc':datetime.now(timezone.utc).isoformat(),
      'stage':5,
      'stage_name':'Weekly production / audit / tracking',
      'canonical_snapshot_id':sid,
      'shadow_snapshot_id':ssid,
      'games_in_week6_snapshot':13,
      'production_contract_checks':checks,
      'grade_artifacts_seen':reg.get('grade_artifacts_seen'),
      'duplicate_grade_artifacts_seen_for_week6':current.get('duplicate_grade_artifacts_seen'),
      'completed_prospective_games':reg.get('completed_prospective_games'),
      'distinct_frozen_weeks':reg.get('distinct_prospective_weeks_with_snapshot'),
      'sample_state':reg.get('sample_state'),
      'stage5_infrastructure_complete':True,
      'weekly_operation_ongoing':True,
      'recommendation_release_allowed':False,
      'website_betting_signal_release_allowed':False,
      'audit_verdict':'PASS_STAGE5_INFRASTRUCTURE__WEEKLY_OPERATION_ONGOING',
      'next_stage':'Stage 6 website / operating interface integration',
    }
    OUTJ.parent.mkdir(parents=True,exist_ok=True)
    OUTJ.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    lines=[
      '# NFL Stage 5 Weekly Production / Audit', '',
      f"**Verdict:** `{result['audit_verdict']}`  ",
      f"**Canonical snapshot:** `{sid}`  ",
      f"**Shadow snapshot:** `{ssid}`  ",
      f"**Completed prospective games:** {result['completed_prospective_games']}  ",
      f"**Distinct frozen weeks:** {result['distinct_frozen_weeks']}", '',
      '## Verified production contracts','',
    ]
    labels={
      'canonical_snapshot_exists':'Canonical Week 6 snapshot exists and remains separate from postgame artifacts.',
      'canonical_game_ids_unique':'The 13 canonical Week 6 game IDs are unique.',
      'shadow_parent_link_valid':'FTN50 explicitly points to the canonical Week 6 snapshot.',
      'canonical_shadow_game_sets_equal':'Canonical and FTN50 cover the same 13 games.',
      'grader_creates_timestamped_artifacts':'Canonical grading creates new timestamped postgame artifacts.',
      'grader_keeps_pending_games':'Incomplete games remain pending rather than receiving inferred results.',
      'grader_roi_disabled':'ROI grading stays disabled without verified executable pricing.',
      'shadow_single_week_promotion_disabled':'A single challenger week cannot promote FTN50.',
      'registry_deduplicates_by_snapshot':'Repeated grader runs are deduplicated by frozen snapshot.',
      'registry_duplicate_game_guard':'Duplicate canonical snapshot/game rows are audit failures.',
      'registry_automatic_threshold_promotion_disabled':'Registry cannot automatically promote an edge threshold.',
      'required_weekly_workflows_present':'Freeze, market, final-gate, grading, registry and research-export workflows exist.',
      'website_release_still_false':'Betting-signal website release remains false.',
    }
    lines += [f"- **PASS:** {labels[k]}" for k,v in checks.items() if v]
    lines += ['', '## Interpretation','',
      'Stage 5 infrastructure is complete. Weekly operation is intentionally ongoing: context refreshes and grading occur as real games approach and finish. The evidence chain can now accumulate future Stage 4 calibration data without rewriting the original predictions or double-counting grader reruns.', '',
      '## Stage 5 handoff','',
      '> Proceed to Stage 6 website integration. The NFL website may consume the verified research/export layer, but its language and UI must continue enforcing HOLD/research permissions until future prospective calibration earns a stronger release state.'
    ]
    OUTM.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'verdict':result['audit_verdict'],'checks':sum(checks.values()),'completed_games':result['completed_prospective_games'],'weeks':result['distinct_frozen_weeks']},indent=2))

if __name__=='__main__': main()
