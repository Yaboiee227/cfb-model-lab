#!/usr/bin/env python3
"""Audit NFL Stage 4 confidence / release calibration readiness."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

REG=Path('nfl_data/prospective/validation_registry/nfl_prospective_validation_registry.json')
HIST=Path('nfl_data/validation/stage2_validation_audit.json')
POLICY=Path('NFL_STAGE4_CONFIDENCE_RELEASE_POLICY.md')
OUTJ=Path('nfl_data/validation/stage4_confidence_release_audit.json')
OUTM=Path('nfl_data/validation/STAGE4_CONFIDENCE_RELEASE_AUDIT.md')

def load(p): return json.loads(p.read_text())

def main():
    for p in (REG,HIST,POLICY):
        if not p.exists(): raise RuntimeError(f'missing {p}')
    reg,hist=load(REG),load(HIST)
    games=int(reg.get('completed_prospective_games',0))
    weeks=int(reg.get('distinct_prospective_weeks_with_snapshot',0))
    beta=bool(reg.get('milestones',{}).get('projection_beta_review_eligible'))
    rec=bool(reg.get('milestones',{}).get('recommendation_calibration_review_eligible'))
    assert hist['audit_verdict']=='PASS_HISTORICAL_RESEARCH_VALIDATION__PROSPECTIVE_RELEASE_STILL_REQUIRED'
    assert reg.get('automatic_threshold_promotion_allowed') is False
    assert reg.get('recommendation_release_allowed') is False
    assert reg.get('clv_claims_allowed') is False
    assert reg.get('roi_claims_allowed') is False
    report={
      'generated_at_utc':datetime.now(timezone.utc).isoformat(),
      'stage':4,
      'stage_name':'Confidence / edge / release calibration',
      'framework_complete':True,
      'completed_prospective_games':games,
      'distinct_frozen_weeks':weeks,
      'projection_beta_review_eligible':beta,
      'recommendation_calibration_review_eligible':rec,
      'recommendation_release_allowed':False,
      'play_label_allowed':False,
      'lean_label_allowed':False,
      'validated_edge_badge_allowed':False,
      'alt_line_recommendation_allowed':False,
      'website_research_projection_fields_allowed':True,
      'historical_non_monotonicity_warning':True,
      'automatic_threshold_promotion_allowed':False,
      'audit_verdict':'PASS_STAGE4_FRAMEWORK__RELEASE_EVIDENCE_NOT_EARNED',
      'next_stage':'Stage 5 weekly production / audit verification',
    }
    OUTJ.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    md=f'''# NFL Stage 4 Confidence / Release Audit

**Verdict:** `{report['audit_verdict']}`  
**Framework:** complete  
**Completed prospective games:** {games}  
**Distinct frozen weeks:** {weeks}

## Release state

- Projection beta review eligible: **{beta}**
- Recommendation calibration review eligible: **{rec}**
- PLAY allowed: **False**
- LEAN allowed: **False**
- Validated edge badge allowed: **False**
- Alt-line recommendation allowed: **False**
- Automatic threshold promotion allowed: **False**

## Interpretation

Stage 4's governance and calibration framework are complete, but the prospective evidence is not. Historical Stage 2 results explicitly showed that larger model-market disagreement did not monotonically improve ATS/total outcomes, so disagreement magnitude cannot be converted directly into betting confidence.

The current prospective registry has {games} completed games across {weeks} frozen week(s). Continue to collect immutable weekly outcomes. Research projection fields may be displayed, but recommendation language remains HOLD.

## Handoff

> Move to Stage 5 production/audit verification. The purpose of Stage 5 is to guarantee that future evidence is collected reproducibly enough to revisit Stage 4 without leakage, hindsight edits or missing timestamp context.
'''
    OUTM.write_text(md)
    print(json.dumps({'verdict':report['audit_verdict'],'games':games,'weeks':weeks,'beta':beta,'recommendation_review':rec},indent=2))

if __name__=='__main__': main()
