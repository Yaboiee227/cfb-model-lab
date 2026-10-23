"""Append-only early-week context capture. No model features/projections changed."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
from html.parser import HTMLParser
import hashlib,json,re
from pathlib import Path
from urllib.request import Request,urlopen
import pandas as pd

DOMAINS={'NE':'patriots','CHI':'chicagobears','PIT':'steelers','NO':'neworleanssaints','SF':'49ers','ATL':'atlantafalcons','CIN':'bengals','BAL':'baltimoreravens','TB':'buccaneers','CAR':'panthers','NYG':'giants','HOU':'houstontexans','IND':'colts','MIN':'vikings','MIA':'miamidolphins','NYJ':'newyorkjets','CLE':'clevelandbrowns','TEN':'tennesseetitans','DEN':'denverbroncos','ARI':'azcardinals','GB':'packers','DET':'detroitlions','LA':'therams','LV':'raiders','KC':'chiefs','SEA':'seahawks','DAL':'dallascowboys','PHI':'philadelphiaeagles'}
# Approximate stadium points. NWS provides the authoritative selected grid.
POINTS={'CHI':(41.8623,-87.6167),'ATL':(33.7554,-84.4008),'BAL':(39.278,-76.623),'CAR':(35.2258,-80.8528),'HOU':(29.6847,-95.4107),'NYJ':(40.8135,-74.0745),'TEN':(36.1665,-86.7713),'ARI':(33.5276,-112.2626),'SEA':(47.5952,-122.3316),'PHI':(39.9008,-75.1675)}

def fetch(url):
    with urlopen(Request(url,headers={'User-Agent':'CBModelProjections research; public pregame context','Accept':'application/geo+json,application/json,text/html'}),timeout=20) as r:
        b=r.read();return b,dict(url=url,resolved_url=r.url,observed_at=datetime.now(timezone.utc).isoformat(),sha256=hashlib.sha256(b).hexdigest())

class TableParser(HTMLParser):
    def __init__(self):super().__init__();self.tables=[];self.headers=[];self.table=None;self.row=None;self.cell=None;self.heading=None
    def handle_starttag(self,tag,attrs):
        if tag=='table':self.table=[]
        if tag=='tr' and self.table is not None:self.row=[]
        if tag in ['td','th'] and self.row is not None:self.cell=[]
        if tag in ['h1','h2','h3','title']:self.heading=[]
    def handle_data(self,d):
        if self.cell is not None:self.cell.append(d)
        if self.heading is not None:self.heading.append(d)
    def handle_endtag(self,tag):
        if tag in ['td','th'] and self.cell is not None:
            self.row.append(' '.join(' '.join(self.cell).split()));self.cell=None
        if tag=='tr' and self.row is not None:
            self.table.append(self.row);self.row=None
        if tag=='table' and self.table is not None:
            self.tables.append(self.table);self.table=None
        if tag in ['h1','h2','h3','title'] and self.heading is not None:
            self.headers.append(' '.join(' '.join(self.heading).split()));self.heading=None

def injury(team):
    url=f'https://www.{DOMAINS[team]}.com/team/injury-report/'
    try:
        b,m=fetch(url);p=TableParser();p.feed(b.decode('utf-8',errors='replace'))
        # Capture evidence, do not certify report week from footer/navigation text.
        return dict(team=team,**m,headings=p.headers,tables=p.tables,scope_status='REQUIRES_REPORT_DATE_AND_OPPONENT_VERIFICATION',canonical_influence=False)
    except Exception as e:return dict(team=team,url=url,error=str(e),scope_status='UNAVAILABLE',canonical_influence=False)

def weather(item):
    team,ko=item;lat,lon=POINTS[team];u=f'https://api.weather.gov/points/{lat},{lon}'
    try:
        b,pointmeta=fetch(u);point=json.loads(b);hourly=point['properties']['forecastHourly'];b,m=fetch(hourly);d=json.loads(b);pr=d['properties'];start=datetime.fromisoformat(ko);end=start+timedelta(hours=4)
        periods=[p for p in pr['periods'] if datetime.fromisoformat(p['startTime'])<end and datetime.fromisoformat(p['endTime'])>start]
        contiguous=bool(periods) and datetime.fromisoformat(periods[0]['startTime'])<=start and datetime.fromisoformat(periods[-1]['endTime'])>=end and all(a['endTime']==b['startTime'] for a,b in zip(periods,periods[1:]))
        updated=pr.get('updateTime');valid_time=bool(updated) and datetime.fromisoformat(updated.replace('Z','+00:00'))<=datetime.now(timezone.utc)
        return dict(home=team,**m,point=pointmeta,coordinates=[lat,lon],coordinate_precision='approximate stadium point; retain selected NWS grid',forecast_issued_at=updated,generated_at=pr.get('generatedAt'),kickoff_utc=ko,through_plus4h_contiguous=contiguous,issue_time_valid=valid_time,periods=periods,status='EARLY_FORECAST_ONLY' if contiguous and valid_time else 'MISSING_OR_INVALID_COVERAGE',gusts='UNAVAILABLE_IN_HOURLY_ENDPOINT',final_window_refresh_required=True,canonical_influence=False)
    except Exception as e:return dict(home=team,url=u,error=str(e),status='UNAVAILABLE',canonical_influence=False)

def main():
    root=Path('nfl_data/prospective/week7');stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');out=root/'context_captures'/stamp;out.mkdir(parents=True,exist_ok=False)
    p=pd.read_csv(root/'20261021T114427Z/paired_projections.csv')
    with ThreadPoolExecutor(max_workers=8) as ex:inj=list(ex.map(injury,DOMAINS))
    with ThreadPoolExecutor(max_workers=6) as ex:wea=list(ex.map(weather,[(r.game_id.split('_')[-1],r.kickoff_utc) for r in p.itertuples() if r.game_id.split('_')[-1] in POINTS]))
    for name,data in [('official_injury_pages.json',inj),('nws_hourly_forecasts.json',wea)]:
        (out/name).write_text(json.dumps(data,indent=2)+'\n')
    print(out)
    print(json.dumps({'injury_pages':[{k:r.get(k) for k in ['team','scope_status','error','headings']}|{'tables':len(r.get('tables',[]))} for r in inj],'weather':[{k:r.get(k) for k in ['home','status','forecast_issued_at','through_plus4h_contiguous','error']} for r in wea]},indent=2))

if __name__=='__main__':main()
