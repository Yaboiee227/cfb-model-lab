"""Append-only Week 7 operations board around the immutable paired freeze."""
import csv
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from collect_nfl_week7_context import fetch, TableParser

ROOT = Path('nfl_data/prospective/week7')
FREEZE = ROOT / '20261021T114427Z'
NAMES = dict(zip('NE CHI PIT NO SF ATL CIN BAL NYG HOU MIA NYJ TB CAR IND MIN CLE TEN DEN ARI LA LV GB DET KC SEA DAL PHI'.split(),
    ['Patriots','Bears','Steelers','Saints','49ers','Falcons','Bengals','Ravens','Giants','Texans','Dolphins','Jets','Buccaneers','Panthers','Colts','Vikings','Browns','Titans','Broncos','Cardinals','Rams','Raiders','Packers','Lions','Chiefs','Seahawks','Cowboys','Eagles']))
NOTES = {
 'CHI':'Final statuses available; five Patriots ruled out; Chicago Edwards doubtful. Inactives pending.',
 'NO':'Paris neutral site, exposed field. Sunday morning showers/gusts in regional forecast; afternoon easing. Kickoff-specific refresh required.',
 'BAL':'Jackson limited Wednesday; starter confirmation pending. Do not infer return from participation.',
 'TEN':'Near pick-em; Canonical and FTN50 disagree on winner. Check Browns injury burden.',
 'MIN':'Post-bye Minnesota; verify concussion clearance and Colts availability.',
 'NYJ':'Review Hall practice trajectory; model-market winner disagreement is not proven value.',
 'HOU':'Giants announced McCarthy starter after model freeze; new QB regime flag. Roof decision pending.',
 'ATL':'Review 49ers availability; distinguish veteran rest from injury. Roof decision pending.',
 'CAR':'Mayfield full Wednesday, return not final. Largest Canonical–FTN50 margin disagreement.',
 'ARI':'Roof decision pending; review Cardinals RB availability.',
 'DET':'Love limited Wednesday (back); verify final status. Detroit return-to-roster decisions pending.',
 'LV':'Verify Rams report and Bowers/Miller availability; indoor venue.',
 'SEA':'Monitor Chiefs pass catchers/line and Seattle availability; outdoor forecast refresh.',
 'PHI':'Hurts IR carried forward; Week 7 starter confirmation and both Monday reports pending.'}
MARKETS = {'CHI':(-2.5,50.5),'NO':(3.5,44.5),'ATL':(2.5,49.5),'TEN':(1.5,37.5),'MIN':(-6.5,41.5),'NYJ':(-4.5,39.5),'CAR':(-3.5,44.5),'BAL':(1.5,48.5),'HOU':(-10.5,42.5),'ARI':(4.5,43.5),'DET':(-3.5,53.5),'LV':(3.5,48.5),'SEA':(-2.5,42.5),'PHI':(4.5,44.5)}

def main():
    now=datetime.now(timezone.utc); stamp=now.strftime('%Y%m%dT%H%M%SZ')
    assert now.date().isoformat()=='2026-10-22', 'Dated staging script: refresh manually reviewed facts and market thresholds before reuse.'
    out=ROOT/'boards'/stamp; out.mkdir(parents=True,exist_ok=False)
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in FREEZE.iterdir() if p.is_file()}
    rows=list(csv.DictReader((FREEZE/'paired_projections.csv').open()))
    assert len(rows)==14 and len({r['game_id'] for r in rows})==14
    body,meta=fetch('https://www.nfl.com/injuries/'); html=body.decode()
    assert '2026 NFL Injury Report' in html and 'WEEK 7' in html
    # Each table is associated with its explicit section title, never page host/order.
    pattern=r'<div class="d3-o-section-sub-title"><span>([^<]+)</span></div>.*?(<table\b.*?</table>)'
    team_tables={}
    for name,table in re.findall(pattern,html,re.S):
        if name.strip() not in NAMES.values(): continue
        p=TableParser();p.feed(table)
        assert len(p.tables)==1
        assert name.strip() not in team_tables
        team_tables[name.strip()]=p.tables[0]
    assert len(team_tables)==26, f'Expected 26 Thursday/Sunday reports, got {len(team_tables)}; review manually'
    (out/'league_injury_tables.json').write_text(json.dumps(dict(**meta,scope='2026 Week 7; current practice tables, not final Sunday statuses',tables=team_tables),indent=2)+'\n')
    capture=sorted((ROOT/'context_captures').glob('20261022T*'))[-1]
    weather={r['home']:r for r in json.loads((capture/'nws_hourly_forecasts.json').read_text())}
    source_urls={
        'market':'https://www.covers.com/nfl/week-7-odds-opening-lines-2026',
        'paris':'https://meteofrance.com/previsions-meteo-france/saint-denis/93200',
        'giants_qb':'https://www.giants.com/news/j-j-mccarthy-to-start-quarterback-new-york-giants-week-7-houston-texans-john-harbaugh-jameis-winston'}
    source_meta={}
    for key,url in source_urls.items():
        try:
            b,m=fetch(url);source_meta[key]=m
            if key=='market':
                p=TableParser();p.feed(b.decode());source_meta[key]['tables']=p.tables
        except Exception as e:source_meta[key]={'url':url,'error':str(e)}
    games=[]
    for row in rows:
        _,_,away,home=row['game_id'].split('_');ko=datetime.fromisoformat(row['kickoff_utc'])
        m=float(row['canonical_home_margin']);t=float(row['canonical_total']);c=float(row['ftn50_home_margin'])
        personnel={}
        for team in [away,home]:
            table=team_tables.get(NAMES[team]);personnel[team]={'status':'CURRENT_PRACTICE_TABLE_FINAL_REVIEW_PENDING' if table else 'REPORT_PENDING_NOT_HEALTHY', 'rows':table[1:] if table else [],'source':meta['url']}
        w=weather.get(home);periods=w.get('periods',[]) if w else []
        pops=[p.get('probabilityOfPrecipitation',{}).get('value') for p in periods]
        rain=f'{max(pops)}%' if pops and all(v is not None for v in pops) else 'unavailable or incomplete'
        wx=(f"{min(p['temperature'] for p in periods)}–{max(p['temperature'] for p in periods)} F; winds "+', '.join(sorted({p['windSpeed'] for p in periods}))+f"; max rain probability {rain}") if periods else ('Indoor venue' if home in ['MIN','DET','LV'] else 'Paris: afternoon fair, lighter wind; morning gust risk; hourly check pending')
        spread,total=MARKETS[home]
        games.append(dict(game_id=row['game_id'],away=away,home=home,kickoff_utc=ko.isoformat(),kickoff_et=ko.astimezone(ZoneInfo('America/New_York')).strftime('%a %m/%d %I:%M %p'),
            canonical={'home_margin':m,'home_spread':-m,'total':t,'away_score':(t-m)/2,'home_score':(t+m)/2},challenger={'name':'FTN50','home_margin':c,'total':float(row['ftn50_total'])},
            market_context={'home_spread':spread,'total':total,'source':source_urls['market'],'source_asof':'2026-10-22','instrument':'Covers percentage-priced displayed thresholds; instrument/provider not verified','eligible_for_grading':False,'price':None,'note':'Manually read table, not conflicting headline; not sportsbook execution or consensus.'},
            personnel=personnel,weather=wx,weather_source=w,priority_note=NOTES[home],
            inactive_review_et=(ko-timedelta(minutes=90)).astimezone(ZoneInfo('America/New_York')).isoformat(),market_lock_start_et=(ko-timedelta(minutes=30)).astimezone(ZoneInfo('America/New_York')).isoformat(),
            release_state='HOLD_RESEARCH_ONLY',benchmark_status='NO_NEW_VERIFIED_INDEPENDENT_BENCHMARK',final_inactives=False,market_lock=None))
    board=dict(asof_utc=now.isoformat(),frozen_snapshot=str(FREEZE),canonical_changed=False,challenger_changed=False,promotion_allowed=False,
        context_capture=str(capture),sources=source_meta,games=games,automation_scheduled=False)
    (out/'board.json').write_text(json.dumps(board,indent=2)+'\n')
    lines=['# NFL Week 7 full slate — Thursday staging','',f'Context retrieved {now.isoformat()}. Model freeze October 21, 7:44:27 AM ET. Research only; every game remains HOLD. Canonical V1 and FTN50 unchanged.','',
        'Projected scores are algebraic implied means (total ± home margin)/2, not separately fitted score models. No confidence labels or calibrated win probabilities are invented. FTN50 uses the same totals.','',
        '| Kickoff ET | Matchup | Canonical score (away–home) | Canonical fair spread | Total | FTN50 fair spread |', '|---|---|---:|---|---:|---|']
    for g in games:
        a,h=g['away'],g['home'];v=g['canonical'];m=v['home_margin'];c=g['challenger']['home_margin']
        lines.append(f"| {g['kickoff_et']} | {a} at {h} | {v['away_score']:.1f}–{v['home_score']:.1f} | {h if m>0 else a} −{abs(m):.2f} | {v['total']:.2f} | {h if c>0 else a} −{abs(c):.2f} |")
    lines+=['','## Context and remaining checks','','League report tables cover 26 Thursday/Sunday teams. Monday reports remain pending. Blank Sunday game designations do not mean cleared; practice participation is not starter confirmation. Official team-page captures are retained as raw evidence and are not assigned by website host.','', '| Game | Priority check | Weather at game window (preliminary) |','|---|---|---|']
    for g in games:lines.append(f"| {g['away']} at {g['home']} | {g['priority_note']} | {g['weather']} |")
    lines+=['','## Separate market context','','Covers table dated October 22 supplies displayed thresholds only. Percentage prices and conflicting headline text prevent treating it as a uniform sportsbook board. These values cannot grade the projections; actual book/provider, line, price and observation time must be captured in the final window. No new independent rating benchmark is claimed.','', '| Game | Home spread threshold | Total threshold |','|---|---:|---:|']
    for g in games:lines.append(f"| {g['away']} at {g['home']} | {g['market_context']['home_spread']:+.1f} | {g['market_context']['total']:.1f} |")
    lines+=['','## Minimal-change handoff','','1. On final-report day, compare player/status changes against the saved league tables. Prioritize QB decisions, OL/secondary clusters, activations and late transactions. Friday for Sunday games; Saturday for Monday.','2. Recheck outdoor forecasts and retractable roofs; preserve Paris exposed-field correction. Do not interpret missing gust data as zero.','3. At T−90, record official inactives and confirmed starters for each kickoff group.','4. During T−30 to kickoff, capture eligible sourced market locks with observation/capture timestamps; never backfill after kickoff.','5. Grade all frozen games with the existing paired grader. Missing locks leave ATS/totals ungraded, not reconstructed. No feature promotions or hindsight exclusions.','','These are remaining checkpoints, not scheduled background monitoring. All model outputs and inputs remain frozen; context changes do not alter numerical predictions.','','## Sources','',f'- Official league tables: {meta["url"]}',*[f'- {k}: {v}' for k,v in source_urls.items()],f'- Timestamped team pages and NWS forecast grids: `{capture}`','- Prior Week 6 validation: `docs/NFL_WEEK6_FAILURE_ANALYSIS_20261021.md`','']
    (out/'NFL_WEEK7_FULL_SLATE.md').write_text('\n'.join(lines))
    after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in FREEZE.iterdir() if p.is_file()}
    assert before==after
    (out/'integrity.json').write_text(json.dumps({'freeze_unchanged':True,'freeze_sha256':after,'games':len(games),'unique_team_reports':len(team_tables),'all_hold':True},indent=2)+'\n')
    print(out)

if __name__=='__main__':main()
