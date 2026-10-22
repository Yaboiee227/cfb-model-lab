"""Capture the actual data endpoint used by nfelo.com; separate benchmark only."""
from datetime import datetime,timezone
import hashlib,json
from urllib.request import urlopen,Request
from nfl_week7_operations import ROOT,verify,write_new,utc

def main():
    url='https://raw.githubusercontent.com/walk-the-program/NFLELO/main/site/data/upcoming.json'
    with urlopen(Request(url,headers={'User-Agent':'CB Model research'}),timeout=20) as response:raw=response.read()
    now=datetime.now(timezone.utc);data=json.loads(raw);expected={r['game_id']:r for r in verify()}
    assert data['season']==2026 and data['week']==7 and len(data['games'])==14
    assert {g['game_id'] for g in data['games']}==set(expected)
    for g in data['games']:
        assert utc(g['kickoff_utc'])==utc(expected[g['game_id']]['kickoff_utc'])
        assert now<utc(g['kickoff_utc']), 'Do not capture this full pregame baseline after first kickoff'
    out=ROOT/'operations'/('nfelo_benchmark_'+now.strftime('%Y%m%dT%H%M%SZ')+'.json')
    write_new(out,{'source_site':'https://nfelo.com/','data_url':url,'endpoint_discovery':'nfelo.com/common.js REMOTE_DATA','observed_at':now.isoformat(),'source_published_at':None,'sha256':hashlib.sha256(raw).hexdigest(),'canonical_influence':False,'identity_note':'NFLELO/walk-the-program endpoint used by nfelo.com; do not conflate with another nfelo provider. Vendor as-of date is not established by retrieval time.','source_data':data,'normalized':[{'game_id':g['game_id'],'benchmark_home_margin':g['elo_spread'],'benchmark_home_spread':-g['elo_spread'],'home_probability':g['p_home']} for g in data['games']]})
    print(out)

if __name__=='__main__':main()
