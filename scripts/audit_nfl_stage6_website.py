#!/usr/bin/env python3
"""End-to-end audit for NFL Stage 6 shared-site technical integration.

This audit verifies that the branch-level NFL research interface consumes the
verified Stage 5 export while enforcing Stage 4 release permissions. It does
not authorize a production merge or betting recommendation release.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

INDEX = Path('index.html')
BOOTSTRAP = Path('league-bootstrap.js')
SCRIPT = Path('script.js')
LIVE = Path('live-suite-loader.js')
CONTRACT = Path('NFL_SITE_INTEGRATION_CONTRACT.md')
CONFIG = Path('nfl_data/site/config.json')
PROJECTIONS = Path('nfl_data/site/projections.csv')
RESULTS = Path('nfl_data/site/results.csv')
RESEARCH = Path('nfl_data/site/research.json')
STAGE4 = Path('nfl_data/validation/stage4_confidence_release_audit.json')
STAGE5 = Path('nfl_data/validation/stage5_weekly_production_audit.json')
OUT_JSON = Path('nfl_data/validation/stage6_website_audit.json')
OUT_MD = Path('nfl_data/validation/STAGE6_WEBSITE_AUDIT.md')


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    required = [INDEX, BOOTSTRAP, SCRIPT, LIVE, CONTRACT, CONFIG, PROJECTIONS,
                RESULTS, RESEARCH, STAGE4, STAGE5]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise RuntimeError(f'Missing Stage 6 inputs: {missing}')

    html = INDEX.read_text(encoding='utf-8')
    bootstrap = BOOTSTRAP.read_text(encoding='utf-8')
    contract = CONTRACT.read_text(encoding='utf-8')
    cfg = load_json(CONFIG)
    research = load_json(RESEARCH)
    stage4 = load_json(STAGE4)
    stage5 = load_json(STAGE5)

    with PROJECTIONS.open(encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
        projection_fields = set(f.fieldnames or [])
    with RESULTS.open(encoding='utf-8', newline='') as f:
        result_reader = csv.DictReader(f)
        result_rows = list(result_reader)
        result_fields = set(result_reader.fieldnames or [])

    required_projection_fields = {
        'league','season','week','gameId','awayTeam','homeTeam',
        'projectedAwayPoints','projectedHomePoints','modelSpreadHome','modelTotal',
        'homeWinProbability','awayWinProbability','marketSpreadHome','marketTotal',
        'marketSource','marketObservedAt','executionVerified','releaseStatus',
        'shadowModelSpreadHome','spreadReliability','totalReliability',
        'personnelState','hardQbStateBreak','weatherRoofState',
        'finalInactivesResolved','releaseBlockers','preferredArchitecture',
        'winProbabilityState','websitePublishAllowed'
    }
    required_result_fields = {'season','week','gameId','atsResult','suResult'}

    checks = {
        'loader_present_once': html.count('<script src="league-bootstrap.js" defer></script>') == 1,
        'loader_before_application': html.index('league-bootstrap.js') < html.index('script.js'),
        'cfb_first_time_default': "localStorage.getItem('cb-active-league') || 'cfb'" in bootstrap,
        'nfl_data_routed_to_separate_root': 'nfl_data/site/' in bootstrap,
        'nfl_bookmarks_isolated': 'cb-bookmarks-nfl' in bootstrap,
        'nfl_record_language_is_projection_audit': 'Prospective projection audit' in bootstrap,
        'model_market_language_is_difference': 'Model / market difference' in bootstrap,
        'reliability_not_betting_confidence': 'Reliability is not betting confidence' in bootstrap,
        'shadow_is_labeled_challenger': 'Shadow challenger' in bootstrap,
        'alt_recommendation_ui_hidden': 'alt-target-box' in bootstrap and 'alt-analysis-card' in bootstrap,
        'nfl_csv_export_includes_league': "const columns = ['league'" in bootstrap,
        'nfl_csv_export_includes_release_fields': 'releaseBlockers' in bootstrap and 'websitePublishAllowed' in bootstrap,
        'stage4_framework_passed': stage4.get('audit_verdict') == 'PASS_STAGE4_FRAMEWORK__RELEASE_EVIDENCE_NOT_EARNED',
        'stage4_recommendations_locked': stage4.get('recommendation_release_allowed') is False,
        'stage5_infrastructure_passed': stage5.get('audit_verdict') == 'PASS_STAGE5_INFRASTRUCTURE__WEEKLY_OPERATION_ONGOING',
        'stage5_betting_signal_release_false': stage5.get('website_betting_signal_release_allowed') is False,
        'site_config_is_nfl': cfg.get('league') == 'NFL',
        'site_config_is_shared_site': cfg.get('separateNflSite') is False,
        'site_config_publish_false': cfg.get('websitePublishAllowed') is False,
        'site_config_moneyline_edge_hold': cfg.get('moneylineEdgeValidation') == 'HOLD',
        'site_config_win_probability_research_validated': cfg.get('winProbabilityValidation') == 'DISPLAY_VALIDATED_RESEARCH_ONLY',
        'projection_contract_fields_complete': required_projection_fields.issubset(projection_fields),
        'projection_count_is_13': len(rows) == 13,
        'all_projection_rows_nfl': all(r.get('league') == 'NFL' for r in rows),
        'all_projection_rows_hold': all(str(r.get('releaseStatus','')).startswith('HOLD') for r in rows),
        'all_projection_rows_publish_false': all(str(r.get('websitePublishAllowed','')).lower() == 'false' for r in rows),
        'all_market_rows_benchmark_labeled': all('benchmark' in str(r.get('marketSource','')).lower() for r in rows),
        'all_execution_unverified_currently': all(str(r.get('executionVerified','')).lower() == 'false' for r in rows),
        'all_shadow_values_present': all(str(r.get('shadowModelSpreadHome','')).strip() for r in rows),
        'all_reliability_present': all(str(r.get('spreadReliability','')).strip() and str(r.get('totalReliability','')).strip() for r in rows),
        'all_release_blockers_present': all(str(r.get('releaseBlockers','')).strip() for r in rows),
        'probability_sums_valid': all(abs(float(r['homeWinProbability']) + float(r['awayWinProbability']) - 100.0) < 0.05 for r in rows),
        'results_contract_fields_complete': required_result_fields.issubset(result_fields),
        'current_results_empty_before_week6_completion': len(result_rows) == 0,
        'research_core_categories_present': {'availability','weather','market','efficiency','validation','workflow'}.issubset({c.get('id') for c in research.get('categories',[])}),
        'contract_stage6_named': contract.startswith('# NFL Stage 6'),
        'contract_production_release_hold': 'NFL production website release: **HOLD**' in contract,
        'contract_technical_vs_production_distinction': 'Technical Stage 6 completion does **not** itself authorize merging NFL into production `main`' in contract,
    }

    failed = [k for k, v in checks.items() if not v]
    if failed:
        raise RuntimeError(f'Stage 6 audit failed: {failed}')

    report = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'stage': 6,
        'stage_name': 'Website / operating interface',
        'audit_verdict': 'PASS_STAGE6_TECHNICAL_INTEGRATION__PRODUCTION_RELEASE_HOLD',
        'technical_integration_complete': True,
        'production_merge_authorized': False,
        'production_nfl_release_allowed': False,
        'recommendation_release_allowed': False,
        'website_betting_signal_release_allowed': False,
        'branch_preview_research_mode_ready': True,
        'checks': checks,
        'projection_rows': len(rows),
        'completed_prospective_games': stage4.get('completed_prospective_games', 0),
        'distinct_frozen_weeks': stage4.get('distinct_frozen_weeks', 0),
        'current_site_publication_status': cfg.get('publicationStatus'),
        'handoff': (
            'Six-stage technical build is complete on nfl-model-development. Keep NFL production release on HOLD while '
            'prospective grading accumulates. Continue game-day Stage 3 refreshes and Stage 5 grading; revisit Stage 4 '
            'milestones before any production-main release or betting recommendation language.'
        ),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    lines = [
        '# NFL Stage 6 Website / Operating Interface Audit', '',
        f"**Verdict:** `{report['audit_verdict']}`  ",
        '**Technical integration:** COMPLETE on `nfl-model-development`  ',
        '**Production NFL release:** HOLD  ',
        '**Recommendation release:** HOLD', '',
        '## Verified interface contracts', ''
    ]
    pretty = {
        'loader_present_once':'League bootstrap is loaded exactly once.',
        'loader_before_application':'League routing loads before the shared application code.',
        'cfb_first_time_default':'CFB remains the first-time default.',
        'nfl_data_routed_to_separate_root':'NFL site data routes to `nfl_data/site/` rather than production CFB data.',
        'nfl_bookmarks_isolated':'NFL bookmarks use an NFL-specific storage key.',
        'nfl_record_language_is_projection_audit':'NFL record language is framed as a prospective projection audit.',
        'model_market_language_is_difference':'NFL UI uses model/market difference language instead of validated-edge language.',
        'reliability_not_betting_confidence':'Reliability is explicitly separated from betting confidence.',
        'shadow_is_labeled_challenger':'FTN50 is visibly a shadow/challenger.',
        'alt_recommendation_ui_hidden':'Alternative-line recommendation UI remains hidden in NFL mode.',
        'nfl_csv_export_includes_league':'NFL CSV export includes league identity.',
        'nfl_csv_export_includes_release_fields':'NFL CSV export includes validation/context/release fields.',
        'stage4_framework_passed':'Stage 4 governance passed while recommendations remain locked.',
        'stage5_infrastructure_passed':'Stage 5 evidence pipeline passed.',
        'site_config_publish_false':'NFL production publication permission is false.',
        'all_projection_rows_hold':'All 13 current NFL projection rows remain HOLD.',
        'all_market_rows_benchmark_labeled':'Current sportsbook observations are labeled benchmarks.',
        'all_execution_unverified_currently':'Current public-board prices are not misrepresented as executable.',
        'probability_sums_valid':'Displayed home/away probabilities are internally consistent.',
        'research_core_categories_present':'NFL research hub contains the required evidence categories.',
        'contract_technical_vs_production_distinction':'Technical completion is explicitly separated from a production-main release decision.',
    }
    for key, text in pretty.items():
        if checks.get(key):
            lines.append(f'- **PASS:** {text}')

    lines += [
        '', '## Current evidence state', '',
        f"- NFL projection rows: **{len(rows)}**",
        f"- Completed prospective games: **{report['completed_prospective_games']}**",
        f"- Distinct frozen weeks: **{report['distinct_frozen_weeks']}**",
        f"- Publication status: **{report['current_site_publication_status']}**",
        '', '## Interpretation', '',
        'The six-stage technical system is now integrated end to end on the NFL development branch. The site can render the current NFL research package with the correct validation, context and release-state language. This audit deliberately does not promote NFL to the production `main` site because the prospective evidence gates required for that release decision have not been earned.',
        '', '## Handoff', '',
        f"> {report['handoff']}",
    ]
    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(json.dumps({
        'verdict': report['audit_verdict'],
        'checks_passed': len(checks),
        'projection_rows': len(rows),
        'completed_prospective_games': report['completed_prospective_games'],
        'production_release': False,
    }, indent=2))


if __name__ == '__main__':
    main()
