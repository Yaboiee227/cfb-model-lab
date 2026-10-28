import pathlib,json,html,math,hashlib
R=pathlib.Path(__file__).resolve().parents[1];p=R/'nfl/research-projections/week-08.json';d=json.loads(p.read_text());e=lambda v:html.escape(str(v));assert len(d['games'])==14
ctx={g['eventId']:g for g in json.loads((R/'data/game-readiness.json').read_text())['games']}
s='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NFL Week 8 research projections</title><style>body{background:#0b1423;color:#eef4fa;font:16px/1.6 system-ui;max-width:1100px;margin:auto;padding:24px}a{color:#9bd8ff}article{background:#17263b;padding:20px;margin:16px 0;border-radius:12px}strong{color:#9de2c8}</style><nav><a href="current-matchups.html">Matchups</a> · <a href="readiness.html">Readiness</a> · <a href="ratings.html?league=nfl">Power ratings</a></nav><h1>NFL Week 8 projections</h1><p>Prospective research only — final-context release remains on HOLD.</p>'''
s+=f'<p>{e(d["limitations"])}</p><p>Frozen {e(d["frozenAt"])} · <a href="nfl/research-projections/week-08.json">Projection evidence</a></p>'
for g in d['games']:
 assert all(math.isfinite(g[k]) for k in ['modelSpreadHome','modelTotal','projectedHomePoints','projectedAwayPoints'])
 assert abs(g['projectedHomePoints']+g['projectedAwayPoints']-g['modelTotal'])<1e-8
 assert abs(g['projectedAwayPoints']-g['projectedHomePoints']-g['modelSpreadHome'])<1e-8
 c=ctx[g['eventId']];odds=c.get('odds',[]);o=odds[0] if odds else {}
 s+=f'<article><h2>{e(g["away"])} at {e(g["home"])}</h2><p>{e(c["kickoffET"])}</p><p><strong>Projected score: {g["projectedAwayPoints"]:.1f} – {g["projectedHomePoints"]:.1f}</strong></p><p>Model home spread: {g["modelSpreadHome"]:+.2f} · Total: {g["modelTotal"]:.2f}</p>'
 s+=f'<p>Market reference: {e(o.get("details","Unavailable"))} · Total {e(o.get("overUnder","Unavailable"))}. Observed {e(c["observedAt"])} via ESPN; not an execution lock.</p><p>Final availability, officials and weather verification pending.</p></article>'
s+='</html>';(R/'nfl-week-8.html').write_text(s)
p=R/'data/current-matchups.json';b=json.loads(p.read_text());b['projectionStatus']='BOTH_LEAGUES_RESEARCH_PUBLISHED_FINAL_CONTEXT_PENDING'
for g in b['leagues']['nfl']['games']:g.update(projectionStatus='Frozen research published; final context pending',projectionUrl='nfl-week-8.html')
p.write_text(json.dumps(b,indent=2)+'\n')
p=R/'current-matchups.html';s=p.read_text().replace('NFL projections remain pending.','NFL Week 8 research projections are available at <a href="nfl-week-8.html">NFL Week 8 projections</a>; final context remains pending.').replace('Projection: pending','Projection: <a href="nfl-week-8.html">Week 8 research</a>');p.write_text(s)
for name in ['readiness.html','scripts/publish_game_readiness.py']:
 p=R/name;s=p.read_text().replace('NFL Week 8 matchup projections remain pending.','NFL Week 8 research projections are published at <a href="nfl-week-8.html">NFL Week 8</a>; final-context clearance remains pending.');p.write_text(s)
print('14 projections checked; prior spread and total reproduction:',d['priorWeekReproduction'])
