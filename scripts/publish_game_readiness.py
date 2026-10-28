import json,html,pathlib
R=pathlib.Path(__file__).resolve().parents[1];d=json.loads((R/'data/game-readiness.json').read_text());e=lambda x:html.escape(str(x))
s='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Game readiness | CB Model Projections</title><style>body{background:#0b1423;color:#eef4fa;font:16px/1.6 system-ui;margin:auto;max-width:1100px;padding:24px}a{color:#9bd8ff}article{background:#17263b;padding:18px;margin:16px 0;border-radius:12px}small{color:#b0c2d6}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><nav><a href="current-matchups.html">Current matchups</a> · <a href="week-9.html">CFB projections</a> · <a href="ratings.html">Power ratings</a></nav><h1>Current-week game readiness</h1><p>CFB Week 9 research projections are published. NFL Week 8 research projections are published at <a href="nfl-week-8.html">NFL Week 8</a>; final-context clearance remains pending. Listed injury information is not final availability clearance. Market values are reference snapshots, not locked executable prices. Weather and final availability require a pregame recheck.</p>'''
s+=f'<p>Evidence checked {e(d["updatedAt"])} · <a href="data/game-readiness.json">Source details</a></p>'
for league in ['cfb','nfl']:
 s+=f'<h2>{league.upper()}</h2>'
 for g in d['games']:
  if g['league']!=league:continue
  s+=f'<article><h3>{e(g["away"])} at {e(g["home"])}</h3><p>{e(g["kickoffET"])} · {e(g["status"])}</p>'
  if g.get('error'):s+=f'<p>Source unavailable: {e(g["error"])}</p>'
  else:
   refs=', '.join(x.get('displayName',str(x)) for x in g['officials'])
   s+=f'<p>Officials: {e(refs or "Not posted in checked source")}</p>'
   s+=f'<p>Injuries: {e(g["injuryStatus"].replace("_"," ").lower())}. Final availability: unverified.</p>'
   s+=f'<p>Markets: {e(g["marketStatus"].replace("_"," ").lower())}</p>'
   for title,key in [('Injury source listings','injuries'),('Market reference details','odds'),('Weather source context','weather')]:
    if g.get(key):s+=f'<details><summary>{title}</summary><pre>{e(json.dumps(g[key],indent=2))}</pre></details>'
  s+=f'<p><a href="{e(g["source"])}">Game source</a></p></article>'
s+='</html>'; (R/'readiness.html').write_text(s)
p=R/'current-matchups.html';s=p.read_text().replace('<nav>','<nav><a href="readiness.html">Game readiness</a>');p.write_text(s)
assert len(d['games'])==70 and len({(g['league'],g['eventId']) for g in d['games']})==70
print('70 unique games validated')
