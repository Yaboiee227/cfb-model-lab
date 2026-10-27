"""Publish frozen Week 9 research projections and attributed market context."""
import csv,json,datetime,html,re
from pathlib import Path
from zoneinfo import ZoneInfo
from lock_research_shadow import verify
R=Path(__file__).resolve().parents[1]
def read(p):return json.loads((R/p).read_text())
def write(p,d):(R/p).write_text(json.dumps(d,indent=2)+'\n')
f=read('cfb/research-locks/week-09-foundation-full.json');verify(f)
s=read('cfb/pregame/week-09-schedule.json');ctx={r['sourceGameId']:r for r in read('cfb/pregame/week09-evidence/week-context.json')}
assert len(f['games'])==len(s['games'])==56
old=list(csv.DictReader((R/'data/projections.csv').open()));fields=list(old[0]);(R/'data/archive').mkdir(exist_ok=True)
archive=R/'data/archive/week-08-projections.csv'
if not archive.exists() and old[0]['week']=='8':archive.write_bytes((R/'data/projections.csv').read_bytes())
rows=[];cards=[];now=datetime.datetime.now(datetime.timezone.utc).isoformat();esc=html.escape
for g in f['games']:
 c=ctx[g['sourceGameId']];o=next((x for x in c.get('odds',[]) if x.get('provider',{}).get('name')=='Draft Kings'),None)
 spread=total=None
 if o and o.get('spread') is not None:
  spread=-abs(o['spread']) if o.get('homeTeamOdds',{}).get('favorite') else abs(o['spread']);total=o['overUnder']
 t=datetime.datetime.fromisoformat(g['kickoff'].replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York'))
 note='Frozen Week 9 foundation research. ESPN-carried DraftKings context is not a qualifying direct-book execution lock. Final availability and referee clearance unresolved; no unvalidated numerical adjustments.'
 row=dict(season=2026,week=9,date=t.date().isoformat(),kickoffET=t.strftime('%-I:%M %p'),gameId=g['gameId'],awayTeam=g['awayTeam'],awayConference='',homeTeam=g['homeTeam'],homeConference='',projectedAwayPoints=g['projectedAwayPoints'],projectedHomePoints=g['projectedHomePoints'],modelSpreadHome=g['projectedSpreadHome'],modelTotal=g['projectedTotal'],homeWinProbability=g['homeWinProbability'],awayWinProbability=100-g['homeWinProbability'],marketSpreadHome=spread,marketTotal=total,marketSource='ESPN / DraftKings reference' if o else '',marketObservedAt=c['observedAt'] if o else '',executionVerified='false',dataQuality='',signalStrength='RESEARCH SHADOW',releaseStatus='RESEARCH SHADOW - CANONICAL HOLD',notes=note)
 rows.append(row)
 gap=spread-g['projectedSpreadHome'] if spread is not None else None
 cards.append('<article><small>'+esc(t.strftime('%a %b %d · %-I:%M %p %Z'))+'</small><h2>'+esc(g['awayTeam']+' at '+g['homeTeam'])+'</h2><p class="score">'+f"{g['projectedAwayPoints']:.1f} – {g['projectedHomePoints']:.1f}"+'</p><p>Model home spread: '+f"{g['projectedSpreadHome']:+.1f}"+' · Total: '+f"{g['projectedTotal']:.1f}"+'</p><p>Market home spread: '+(f'{spread:+.1f}' if spread is not None else '—')+' · Total: '+str(total)+'</p><p>Home spread gap (market − model): '+(f'{gap:+.1f}' if gap is not None else '—')+'</p><small>ESPN / DraftKings reference · '+esc(c['observedAt'])+'</small></article>')
with (R/'data/projections.csv').open('w',newline='') as fp:
 w=csv.DictWriter(fp,fieldnames=fields);w.writeheader();w.writerows(rows)
cfg=read('data/config.json');cfg.update(currentWeek=9,lastUpdated=now,modelVersion='CFB foundation v1 · Week 9 frozen research',publicationStatus='56 Week 9 research projections · canonical HOLD · final personnel/referee checks unresolved');write('data/config.json',cfg)
page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CFB Week 9 | CB Model</title><style>body{font:16px/1.6 system-ui;background:#0b1423;color:#edf4fa;margin:0}main{max-width:1100px;margin:auto;padding:24px}a{color:#9bd8ff}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,310px),1fr));gap:14px}article{padding:20px;background:#17263b;border:1px solid #34465c;border-radius:12px}h2{font-size:18px}.score{font-size:28px;color:#a8e6ce}small{overflow-wrap:anywhere}aside{padding:18px;background:#332e20}</style><main><nav><a href="index.html?league=cfb">CFB dashboard</a> · <a href="current-matchups.html#nfl">NFL matchups</a> · <a href="index.html?league=cfb#record">Records</a></nav><h1>CFB Week 9 projections</h1><p>56 games · Frozen '+esc(f['lockedAt'])+'</p><aside>Research only; canonical release remains on HOLD. Market numbers below are ESPN-carried DraftKings references, not direct-book execution locks. Final availability and referee crews are unconfirmed. Weather is source context, not a completed forecast clearance. No injury, referee, or weather point adjustments have been invented.</aside><p>Delaware’s official preview confirms Nick Minicucci returned last week; older “out” listings should not be carried forward. Tonight’s final CUSA reports could not be verified from the official embedded service.</p><p><a href="https://bluehens.com/news/2026/10/26/football-wraps-weekday-cusa-play-at-wku">Delaware team preview</a> · <a href="cfb/pregame/week09-evidence/week-context.json">Market and game-feed evidence</a></p><div class="grid">'+''.join(cards)+'</div></main></html>'
(R/'week-9.html').write_text(page)
p=R/'index.html';v=p.read_text();v=re.sub(r'<aside id="current-week-matchups".*?</aside>','<aside id="current-week-matchups" style="padding:18px;background:#14293b;color:#fff;text-align:center"><strong>CFB Week 9: 56 research projections published.</strong> <a style="color:#9bd8ff" href="week-9.html">View projections and market gaps</a> · <a style="color:#9bd8ff" href="current-matchups.html#nfl">NFL Week 8 matchups</a><p>Final availability/referee checks unresolved. NFL projections remain pending.</p></aside>',v,flags=re.S);v=v.replace('Week 8 · Canonical HOLD','Week 9 · Canonical HOLD').replace('Tuesday and Wednesday source checks are available.','Week 9 frozen research projections and market references are available.').replace('<a href="week-8.html">View game readiness','<a href="week-9.html">View game readiness');p.write_text(v)
p=R/'site-shell.js';v=p.read_text().replace('CFB · Week 8 production state','CFB · Week 9 research state').replace('href="week-8.html">Open Week 8 audit','href="week-9.html">Open Week 9 projections');p.write_text(v)
p=R/'current-matchups.html';v=p.read_text().replace('New-week model projections and model/market gaps are pending.','CFB Week 9 research projections and reference market gaps are available at <a href="week-9.html">Week 9 projections</a>. NFL projections remain pending.');parts=v.split('<section id="nfl">',1);parts[0]=parts[0].replace('Projection: pending','<a href="week-9.html">View CFB research projection</a>');v='<section id="nfl">'.join(parts);p.write_text(v)
m=read('data/current-matchups.json');m['projectionStatus']='CFB_RESEARCH_PUBLISHED_NFL_PENDING';byid={g['sourceGameId']:g for g in f['games']}
for g in m['leagues']['cfb']['games']:
 assert g['eventId'] in byid;g['projectionStatus']='Frozen research published';g['projectionUrl']='week-9.html'
write('data/current-matchups.json',m)
print('Published',len(rows),'market references',sum(r['marketSpreadHome'] is not None for r in rows))
