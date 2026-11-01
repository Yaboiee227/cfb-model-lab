"""Capture dated Sunday context separately from immutable Week 8 forecasts."""
import json,hashlib,datetime,concurrent.futures,urllib.request
from pathlib import Path
from html.parser import HTMLParser
class InjuryParser(HTMLParser):
 def __init__(self):super().__init__();self.teams={};self.team=None;self.tag=None;self.parts=[]
 def handle_starttag(self,tag,attrs):
  if tag in ("h2","h3","li"):self.tag=tag;self.parts=[]
 def handle_data(self,data):
  if self.tag:self.parts.append(data)
 def handle_endtag(self,tag):
  if tag==self.tag:
   text=" ".join(" ".join(self.parts).split())
   if tag=="h3":self.team=text
   elif tag=="h2":self.team=None
   elif tag=="li" and self.team and text.startswith(("OUT:","QUESTIONABLE:","DOUBTFUL:")):self.teams.setdefault(self.team,[]).append(text)
   self.tag=None
R=Path(__file__).resolve().parents[1]
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
OUT=R/'nfl/production/week08-sunday-context';OUT.mkdir(parents=True,exist_ok=True)
URL='https://fantasy-www.nfl.com/news/nfl-week-8-injury-report-2026-season'
def fetch(u):
 with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'CBModelProjections research'}),timeout=25) as f:return f.read()
def injuries():
 try:
  raw=fetch(URL);parser=InjuryParser();parser.feed(raw.decode('utf-8'));teams=parser.teams
  assert len(teams)>=26,'Incomplete official injury article extraction'
  return dict(source=URL,observedAt=NOW,sha256=hashlib.sha256(raw).hexdigest(),teams=teams,status='DATED_GAME_STATUS_REPORT_NOT_FINAL_INACTIVES',finalInactivesVerified=False)
 except Exception as e:return dict(source=URL,status='UNAVAILABLE',error=str(e),finalInactivesVerified=False)
REFS={'BUF':'Clay Martin','CIN':'Brad Allen','DAL':'Ron Torbert','DET':'Craig Wrolstad','JAX':'Adrian Hill','NYJ':'John Hussey','PIT':'Alex Kemp','TB':'Alan Eck','LA':'Brad Rogers','DEN':'Clete Blakeman','MIA':'Alex Moore','WAS':'Shawn Hochuli','SEA':'Shawn Smith','GB':'Scott Novak'}
POINTS={'BUF':(42.7738,-78.787),'CIN':(39.0954,-84.516),'JAX':(30.3239,-81.6373),'NYJ':(40.8135,-74.0745),'PIT':(40.4468,-80.0158),'TB':(27.9759,-82.5033),'DEN':(39.7439,-105.0201),'MIA':(25.958,-80.2389),'WAS':(38.9077,-76.8645),'SEA':(47.5952,-122.3316)}
def weather(g):
 home=g['gameId'].split('_')[-1]
 if home=='DET':return dict(status='FIXED_ROOF_WEATHER_EXPOSURE_LIMITED',roof='Fixed roof')
 if home=='LA':return dict(status='COVERED_OPEN_SIDES_REQUIRES_STADIUM_CONDITIONS',roof='Fixed canopy, open sides')
 if home=='DAL':return dict(status='RETRACTABLE_ROOF_DECISION_UNVERIFIED',roof='Retractable; final decision unverified')
 if home not in POINTS:return dict(status='NOT_CAPTURED')
 try:
  lat,lon=POINTS[home];point=json.loads(fetch(f'https://api.weather.gov/points/{lat},{lon}'));u=point['properties']['forecastHourly'];d=json.loads(fetch(u))['properties'];k=datetime.datetime.fromisoformat(g['kickoffUTC'].replace('Z','+00:00'));end=k+datetime.timedelta(hours=4)
  ps=[p for p in d['periods'] if datetime.datetime.fromisoformat(p['startTime'])<end and datetime.datetime.fromisoformat(p['endTime'])>k]
  return dict(status='NWS_HOURLY_CONTEXT_NOT_MODEL_ADJUSTMENT',source=u,issuedAt=d.get('updateTime'),observedAt=NOW,kickoffThroughFourHours=ps,coverageComplete=bool(ps) and datetime.datetime.fromisoformat(ps[0]['startTime'])<=k and datetime.datetime.fromisoformat(ps[-1]['endTime'])>=end)
 except Exception as e:return dict(status='UNAVAILABLE',error=str(e))
if __name__=='__main__':
 frozen=json.loads((R/'nfl/research-projections/week-08.json').read_text());active=[g for g in frozen['games'] if g['kickoffUTC'][:10]>='2026-11-01'];inj=injuries()
 with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:w=list(ex.map(weather,active))
 out=dict(asOf=NOW,league='nfl',week=8,canonicalInfluence=False,forecastChanges=0,injuryReport=inj,refereeSource='https://www.footballzebras.com/2026/10/week-8-referee-assignments-2026/',policy='Context only. No validated numeric personnel/referee adjustment; final inactives and execution locks remain unresolved.',games=[dict(gameId=g['gameId'],away=g['away'],home=g['home'],kickoffUTC=g['kickoffUTC'],referee=REFS[g['gameId'].split('_')[-1]],refereeStatus='PUBLISHED_ASSIGNMENT_SUBSTITUTIONS_POSSIBLE',weather=we,finalInactivesVerified=False,releaseStatus='HOLD_FINAL_AVAILABILITY_AND_EXECUTION_LOCKS') for g,we in zip(active,w)])
 (OUT/'latest.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(injuryStatus=inj['status'],teams=len(inj.get('teams',{})),games=len(active),weather=[dict(gameId=g['gameId'],status=g['weather']['status']) for g in out['games']]),indent=2))
