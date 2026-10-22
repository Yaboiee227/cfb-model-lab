import csv,json,math
from pathlib import Path
from nfl_week7_operations import verify

def main():
    frozen={r['game_id']:r for r in verify()}
    site=Path('nfl_data/site')
    with (site/'projections.csv').open() as f:rows=list(csv.DictReader(f))
    assert len(rows)==14 and {r['gameId'] for r in rows}==set(frozen)
    for r in rows:
        p=frozen[r['gameId']]
        for a,b in [('modelSpreadHome','canonical_home_spread'),('modelTotal','canonical_total')]:
            assert math.isclose(float(r[a]),float(p[b]),abs_tol=1e-10)
        assert math.isclose(float(r['shadowModelSpreadHome']),-float(p['ftn50_home_margin']),abs_tol=1e-10)
        assert r['releaseStatus']=='HOLD_RESEARCH_ONLY'
        assert r['executionVerified']=='false' and float(r['qbOperationalPointAdjustment'])==0
        assert abs(float(r['homeWinProbability'])+float(r['awayWinProbability'])-100)<.02
    cfg=json.loads((site/'config.json').read_text())
    assert cfg['currentWeek']==7 and not cfg['recommendationReleaseAllowed'] and not cfg['inputCoveragePass']
    assert (site/'archive/week6-before-week7/projections.csv').exists()
    print('PASS: 14 frozen pairs unchanged; display-only calibration; no recommendation or full-readiness claim.')

if __name__=='__main__':main()
