#!/usr/bin/env python3
"""Add derived final-score error metrics to the NFL Stage 2 evidence.

Projected team scores are algebraic derivatives of canonical total + home margin,
not separately fitted models. This audit measures how those display scores compare
with realized home/away scores across the same 816 outer-OOS games.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

SOURCE = Path('nfl_data/calibration/final_architecture_oos_predictions_2023_2025.csv')
OUT = Path('nfl_data/validation/stage2_final_score_metrics.json')
YEARS = [2023, 2024, 2025]


def metric(errs):
    return {
        'n': len(errs),
        'mae': round(sum(abs(x) for x in errs) / len(errs), 4),
        'rmse': round(math.sqrt(sum(x*x for x in errs) / len(errs)), 4),
        'bias_pred_minus_actual': round(sum(errs) / len(errs), 4),
    }


def summarize(rows):
    away_err, home_err = [], []
    for r in rows:
        pred_total = float(r['pred_total'])
        pred_margin = float(r['pred_home_margin'])
        actual_total = float(r['actual_total'])
        actual_margin = float(r['actual_home_margin'])
        pred_home = (pred_total + pred_margin) / 2.0
        pred_away = (pred_total - pred_margin) / 2.0
        actual_home = (actual_total + actual_margin) / 2.0
        actual_away = (actual_total - actual_margin) / 2.0
        home_err.append(pred_home - actual_home)
        away_err.append(pred_away - actual_away)
    pooled = home_err + away_err
    return {
        'games': len(rows),
        'team_score_observations': len(pooled),
        'home_score': metric(home_err),
        'away_score': metric(away_err),
        'all_team_scores': metric(pooled),
        'derivation': {
            'projected_home_points': '(pred_total + pred_home_margin) / 2',
            'projected_away_points': '(pred_total - pred_home_margin) / 2',
            'actual_home_points': '(actual_total + actual_home_margin) / 2',
            'actual_away_points': '(actual_total - actual_home_margin) / 2',
        },
        'interpretation': 'Score metrics evaluate the display score implied by the canonical spread and total; no separate score model is fitted.',
    }


def main():
    rows = list(csv.DictReader(SOURCE.open(encoding='utf-8', newline='')))
    if len(rows) != 816:
        raise RuntimeError(f'Expected 816 OOS games, found {len(rows)}')
    by_season = {str(y): summarize([r for r in rows if int(r['season']) == y]) for y in YEARS}
    payload = {
        'stage': 2,
        'source': str(SOURCE),
        'aggregate': summarize(rows),
        'by_season': by_season,
        'release_effect': 'NONE_METRIC_ONLY',
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(payload, indent=2))


if __name__ == '__main__':
    main()
