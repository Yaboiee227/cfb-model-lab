"""Dated Week 7 research display export; no fitting or canonical adjustments."""
import csv, hashlib, json, math, shutil
from datetime import datetime,timezone
from pathlib import Path
from nfl_week7_operations import ROOT,verify

REFS={'CHI':'Alan Eck','NO':'Bill Vinovich','ATL':'Clay Martin','BAL':'Shawn Smith','CAR':'Carl Cheffers','HOU':'Land Clark','MIN':'Brad Rogers','NYJ':'Brad Allen','TEN':'Scott Novak','ARI':'Craig Wrolstad','DET':'Alex Moore','LV':'Ron Torbert','SEA':'John Hussey','PHI':'Alex Kemp'}
FACTORS={
 'efficiency_epa_success':'CANONICAL', 'pass_rush_explosives_sacks':'CANONICAL', 'coverage':'CANONICAL_SPREAD',
 'rest_neutral_site':'CANONICAL_BASIC', 'win_elo_margin_rating':'CANONICAL_SPREAD',
 'ftn_qb_process':'SHADOW_ONLY', 'starting_qb_replacement_value':'PARTIAL_CONTEXT_NO_ADJUSTMENT',
 'ir_suspensions_transactions_depth_snap_roles':'PARTIAL_CONTEXT_REVIEW_REQUIRED', 'ol_continuity_injury_clusters':'PARTIAL_CONTEXT_NO_ADJUSTMENT',
 'referee_assignments':'REPORTED_LEAD_REF_ONLY_FULL_CREW_PENDING', 'referee_penalty_history':'NOT_CAPTURED_NO_ADJUSTMENT',
 'weather_wind_gust_precip_roof_surface':'PARTIAL_CONTEXT_GUSTS_AND_ROOFS_PENDING',
 'travel_timezone_altitude':'NOT_PROMOTED', 'coaching_fourth_down_personnel_motion_scheme':'CATALOGED_NOT_FULLY_CAPTURED',
 'drive_pace_possessions':'TESTED_NOT_PROMOTED', 'red_zone_goal_to_go':'TESTED_NOT_PROMOTED',
 'turnover_regression':'TESTED_NOT_PROMOTED', 'special_teams_kicking_returns':'TESTED_NOT_PROMOTED',
 'team_penalties':'TESTED_NOT_PROMOTED', 'ngs_tracking_trenches':'ADDITIONS_NOT_PROMOTED',
 'nfelo_sagarin_dvoa':'NFELO_CAPTURED_SEPARATELY_SAGARIN_DVOA_GAPS', 'abrams_trends':'WEEK7_PAGE_FOUND_GAME_ENTRIES_NOT_VERIFIED',
 'giffen_luck':'WEEK7_DASHBOARD_FOUND_VALUES_NOT_CAPTURED', 'sic_chao':'CONTEXT_CHECKED_CONFLICTS_FLAGGED_NO_HEALTH_SCORES',
 'fanduel_draftkings':'FINAL_WINDOW_WORKFLOW_PENDING_ACTUAL_LOCKS', 'kalshi_polymarket':'NOT_CAPTURED_SEPARATE_INSTRUMENTS',
 'probability':'PREEXISTING_DISPLAY_CALIBRATION_ONLY', 'intervals_alt_lines_confidence':'WEEK7_INTERVALS_NOT_EXPORTED_RECOMMENDATIONS_BLOCKED',
 'situational_narratives':'NO_NUMERICAL_WEIGHT'}

def put(p,data):p.write_text(json.dumps(data,indent=2)+'\n')

def main():
    now=datetime.now(timezone.utc).isoformat();rows=verify()
    board=json.loads((ROOT/'boards/20261022T165951Z/board.json').read_text())
    site=Path('nfl_data/site');archive=site/'archive/week6-before-week7'
    archive.mkdir(parents=True,exist_ok=False)
    for name in ['projections.csv','config.json','research.json','nfl-trends.json']:
        shutil.copyfile(site/name,archive/name)
    fields=next(csv.reader((site/'projections.csv').open()))
    cal=json.loads((ROOT/'operations/display_calibration_preexisting.json').read_text())
    assert cal['display_probability_eligible'] and not cal['recommendation_release_allowed']
    mapping=cal['production_2026_mapping']; out=[];off=[]
    for g,r in zip(board['games'],rows):
        assert g['game_id']==r['game_id']
        c=g['canonical'];hp=100/(1+math.exp(-(mapping['intercept']+mapping['margin_slope']*c['home_margin'])))
        dt=datetime.fromisoformat(g['kickoff_utc']).astimezone(__import__('zoneinfo').ZoneInfo('America/New_York'))
        row=dict.fromkeys(fields,'');row.update(league='NFL',season=2026,week=7,date=dt.date().isoformat(),kickoffET=dt.strftime('%H:%M'),gameId=g['game_id'],awayTeam=g['away'],homeTeam=g['home'],awayConference='NFL',homeConference='NFL',
            projectedAwayPoints=c['away_score'],projectedHomePoints=c['home_score'],modelSpreadHome=c['home_spread'],modelTotal=c['total'],homeWinProbability=round(hp,2),awayWinProbability=round(100-hp,2),
            marketSource='FD/DK current sportsbook capture pending; aggregator thresholds kept separately',executionVerified='false',signalStrength='UNVALIDATED_RESEARCH',releaseStatus='HOLD_RESEARCH_ONLY',
            notes=g['priority_note']+' Reported lead referee: '+REFS[g['home']]+'. Full crew unverified. Freeze 20261021T114427Z.',
            shadowModelSpreadHome=-g['challenger']['home_margin'],spreadReliability='PENDING_FINAL_GATES',totalReliability='PENDING_FINAL_GATES',personnelState='CONTEXT_PARTIAL_FINAL_INACTIVES_PENDING',hardQbStateBreak='true' if g['home'] in ['HOU','PHI'] else 'false',
            qbOperationalPointAdjustment=0,weatherRoofState=g['weather'],weatherElevatedUncertainty='true' if g['home']=='NO' else 'false',finalInactivesResolved='false',
            releaseBlockers='FINAL_PERSONNEL_PENDING|FINAL_WEATHER_ROOF_PENDING|MARKET_LOCK_PENDING|VALIDATION_HOLD',preferredArchitecture='CANONICAL_UNTIL_PROSPECTIVE_SHADOW_EVIDENCE_ACCUMULATES',winProbabilityState='CANONICAL_MARGIN_CALIBRATION_RESEARCH_ONLY',websitePublishAllowed='true')
        out.append(row)
        off.append({'game_id':g['game_id'],'reported_lead_referee':REFS[g['home']],'state':'REPORTED_SECONDARY_SOURCE_FULL_CREW_UNVERIFIED','canonical_influence':False,'full_crew':None,'statistics':None})
    with (site/'projections.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(out)
    cfg=json.loads((site/'config.json').read_text());cfg.update(currentWeek=7,generatedAtUtc=now,lastUpdated=now,gamesInCurrentSlate=14,publicationStatus='Week 7 frozen research preview — final gates pending',inputCoveragePass=False,averageInputCoveragePct=None,inputCoverageLayersPassed=None,gamesMeetingInputCoverageStandard=0,inputCoverageInterpretation='No complete-coverage claim. See factor register and per-game blockers.',recommendationReleaseAllowed=False)
    put(site/'config.json',cfg)
    cats=[('readiness','Readiness','PARTIAL','Fourteen frozen forecasts; personnel, crews, benchmarks and market locks are not all complete.'),
        ('availability','Personnel','PENDING','Official reports captured for 26 Thursday/Sunday teams. McCarthy announced for NYG; Jackson/Mayfield returns unresolved; Monday reports and final inactives pending.'),
        ('weather','Weather / roofs','PRELIMINARY','Ten NWS game windows captured. Paris exposed field; morning gust risk. Final roof/gust information pending.'),
        ('officiating','Officiating','14 REPORTED LEADS','Football Zebras assignments; full crew and substitutions unverified. RefMetrics assignment page retrieved was Week 6. No referee adjustment.'),
        ('market','Markets','LOCKS PENDING','NFL-specific FD/DK final-window capture configured. No current executable-price, consensus, or CLV claim. Prediction markets separate.'),
        ('efficiency','Canonical / challenger','UNCHANGED','Canonical V1 and FTN50 frozen October 21 at 7:44 AM ET. Existing research probability mapping only; no new coefficients.'),
        ('validation','Validation','HOLD','Week 6 remains 3–10 ATS, 6–6–1 totals, 7–6 SU. New calibration challengers did not pass. No feature promotion.'),
        ('sources','External context','GAPS RECORDED','Abrams/Giffen current pages located but numeric entries not verified. SIC practice conflict defers to official report. All 14 nfelo benchmark games captured separately; Sagarin/DVOA gaps remain.'),
        ('workflow','Workflow','VERIFICATION REQUIRED','Existing hourly pregame task updated for Week 7. Verify actual NFL market workflow runs and immutable locks; configured schedules do not guarantee capture.')]
    put(site/'research.json',{'updated':now,'categories':[{'id':i,'label':l,'short':l,'status':s,'summary':d,'items':[{'title':l,'detail':d,'tag':s}]} for i,l,s,d in cats]})
    trends=json.loads((archive/'nfl-trends.json').read_text());trends.update(week=7,lastUpdated=now,status='PENDING_VERIFIED_WEEK7_ENTRIES',trends=[],coverage={'entryCount':0,'gamesWithVerifiedEntries':0,'currentSlateGames':14,'method':'Current Week 7 article located; detailed records not verified. Prior Week 6 file archived.'},notes='No stale Week 6 entries carried into Week 7; no trend influence on model or confidence.')
    put(site/'nfl-trends.json',trends)
    put(ROOT/'operations/factor_register_20261022.json',{'asof_utc':now,'factors':FACTORS,'promotion_allowed':False})
    put(ROOT/'operations/officiating_20261022.json',{'observed_at_utc':now,'source':'https://www.footballzebras.com/2026/10/week-7-referee-assignments-2026/','crosscheck':'https://www.rotowire.com/football/article/nfl-referee-assignments-betting-trends-by-crew-133202','crosscheck_independent':False,'source_caveat':'Football Zebras paragraph says London but table says Paris; official venue remains Paris. RotoWire cites Football Zebras; not a second independent assignment source.','games':off})
    # Existing result files and official frozen week-06 projection/result paths are untouched.
    print('Exported 14 immutable research forecasts, archived Week 6 display, no results changed.')

if __name__=='__main__':main()
