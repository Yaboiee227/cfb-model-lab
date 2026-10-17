#!/usr/bin/env python3
"""Build reproducible NFL static travel / venue / schedule context.

Uses nflverse schedules plus its team-airport table. Ordinary road travel is
airport-to-airport great-circle distance. Neutral/international travel distance
is deliberately left missing unless a separately verified destination geometry
layer is added; neutral-site status remains available as its own feature.

Historical actual roof state is retained as research context but flagged because
retractable-roof decisions can be made close to kickoff. Historical temp/wind
are intentionally excluded: observed game weather is not an archived pregame
forecast and would overstate information quality.
"""
from __future__ import annotations
import io,json,math,urllib.request
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd

GAMES='https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
AIRPORTS='https://raw.githubusercontent.com/nflverse/nfldata/master/data/airports.csv'
OUT_H=Path('nfl_data/historical/game_static_context_2022_2025.csv');OUT_C=Path('nfl_data/generated/static_context_2026_week6.csv');OUT_Q=Path('nfl_data/generated/static_context_build_qa_2026_week6.json')
HIST=[2022,2023,2024,2025];CURRENT=2026;WEEK=6
ALIASES={'LAR':'LA','STL':'LA','JAC':'JAX','WSH':'WAS','WFT':'WAS','OAK':'LV','SD':'LAC','SDG':'LAC'}

def nt(v):
 s=str(v or '').strip().upper();return ALIASES.get(s,s)
def fetch_csv(url):
 req=urllib.request.Request(url,headers={'User-Agent':'cb-model-projections/1.0'})
 with urllib.request.urlopen(req,timeout=120) as r:return pd.read_csv(io.BytesIO(r.read()))
def hav(lat1,lon1,lat2,lon2):
 r=3958.7613;p1=math.radians(lat1);p2=math.radians(lat2);dp=math.radians(lat2-lat1);dl=math.radians(lon2-lon1);a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2;return 2*r*math.asin(math.sqrt(a))
def norm_surface(v):
 s=str(v or '').strip().lower()
 if not s or s=='nan':return None
 return 'grass' if 'grass' in s else 'artificial' if any(x in s for x in ['turf','artificial','matrixturf','a_turf','sportturf']) else s
def norm_roof(v):
 s=str(v or '').strip().lower()
 if not s or s=='nan':return None
 return s if s in {'dome','outdoors','closed','open','retractable'} else None
def rows_for(df,air,seasons=None,season=None,week=None):
 x=df[df['game_type'].astype(str).str.upper().eq('REG')].copy()
 if seasons is not None:x=x[pd.to_numeric(x['season'],errors='coerce').isin(seasons)]
 if season is not None:x=x[pd.to_numeric(x['season'],errors='coerce').eq(season)]
 if week is not None:x=x[pd.to_numeric(x['week'],errors='coerce').eq(week)]
 out=[]
 for _,g in x.iterrows():
  away,home=nt(g.get('away_team')),nt(g.get('home_team'));loc=str(g.get('location','')).strip().lower();neutral=(loc=='neutral')
  aa,ha=air.get(away),air.get(home);miles=None;tz_shift=None;signed_tz=None
  if not neutral and aa and ha:
   miles=hav(aa['lat'],aa['lon'],ha['lat'],ha['lon']);signed_tz=ha['tz']-aa['tz'];tz_shift=abs(signed_tz)
  weekday=str(g.get('weekday','')).strip().lower();gametime=str(g.get('gametime','')).strip();hour=None
  try:hour=int(gametime.split(':')[0]) if gametime and gametime.lower()!='nan' else None
  except Exception:hour=None
  roof=norm_roof(g.get('roof'));surface=norm_surface(g.get('surface'))
  out.append({'game_id':str(g.get('game_id')),'season':int(g['season']),'week':int(g['week']),'gameday':str(g.get('gameday')),'away_team':away,'home_team':home,'neutral_site':int(neutral),'away_travel_air_miles':None if miles is None else round(miles,2),'away_time_zone_shift_hours':tz_shift,'away_signed_time_zone_shift_hours':signed_tz,'div_game':int(float(g.get('div_game') or 0)) if pd.notna(g.get('div_game')) else 0,'roof':roof,'surface_group':surface,'weekday':weekday,'kickoff_hour_et':hour,'is_thursday':int(weekday.startswith('thu')),'is_monday':int(weekday.startswith('mon')),'is_sunday_night':int(weekday.startswith('sun') and hour is not None and hour>=19),'game_stadium':str(g.get('stadium') if 'stadium' in g.index else g.get('game_stadium','')),'metadata_state':'RESEARCH_STATIC_CONTEXT'})
 return pd.DataFrame(out)
def main():
 OUT_H.parent.mkdir(parents=True,exist_ok=True);OUT_C.parent.mkdir(parents=True,exist_ok=True);games=fetch_csv(GAMES);ap=fetch_csv(AIRPORTS);air={nt(r['team']):{'lat':float(r['latitude']),'lon':float(r['longitude']),'tz':float(r['time_zone'])} for _,r in ap.iterrows()}
 hist=rows_for(games,air,seasons=HIST);cur=rows_for(games,air,season=CURRENT,week=WEEK);hist.to_csv(OUT_H,index=False);cur.to_csv(OUT_C,index=False)
 qa={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'historical_rows':len(hist),'historical_seasons':HIST,'current_rows':len(cur),'current_season':CURRENT,'current_week':WEEK,'airport_teams':len(air),'historical_missing_road_travel':int(hist[(hist['neutral_site']==0)&hist['away_travel_air_miles'].isna()].shape[0]),'historical_neutral_games':int(hist['neutral_site'].sum()),'current_neutral_games':int(cur['neutral_site'].sum()),'current_roof_missing':int(cur['roof'].isna().sum()),'current_surface_missing':int(cur['surface_group'].isna().sum()),'weather_policy':'Historical schedule temp/wind excluded because they are observed game conditions, not archived pregame forecasts.','roof_policy':'Historical roof state is research context only. Retractable/open-close state must be verified prospectively near decision time.','neutral_travel_policy':'Neutral-site travel distance left missing pending verified destination coordinates.','known_2026_metadata_caveat':'nflverse issue #36 reports multiple 2026 international roof/location/stadium inconsistencies; independently verify 2026 international venue metadata before use.','release_state':'HOLD_RESEARCH_ONLY','website_publish_allowed':False}
 OUT_Q.write_text(json.dumps(qa,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps(qa,indent=2))
if __name__=='__main__':main()
