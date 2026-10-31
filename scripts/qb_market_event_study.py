"""Measure same-book QB-news repricing. Descriptive benchmark, never causal value."""
import argparse,json,math
from datetime import datetime
from pathlib import Path

def dt(x):
 d=datetime.fromisoformat(x.replace('Z','+00:00'))
 if d.tzinfo is None:raise ValueError('timezone required')
 return d

def measure(r):
 out=dict(caseId=r.get('caseId'),league=r.get('league'),canonicalInfluence=False,status='EXCLUDED',reasons=[])
 try:
  if r['league'] not in ('nfl','cfb'):raise ValueError('invalid league')
  pre,post=r['preNewsQuote'],r['postNewsQuote']
  if not pre.get('bookmaker') or pre['bookmaker']!=post['bookmaker']:raise ValueError('same named bookmaker required')
  if not all(x.get('source') for x in (pre,post,r['news'])):raise ValueError('source provenance missing')
  if not dt(pre['observedAt'])<dt(r['news']['publishedAt'])<=dt(post['observedAt'])<dt(r['kickoff']):raise ValueError('invalid event chronology')
  if r.get('starterExpectedBeforeNews') is not True:raise ValueError('pre-news starter expectation unverified')
  for q in (pre,post):
   for k in ('spreadHome','total'):
    if isinstance(q[k],bool) or not isinstance(q[k],(int,float)) or not math.isfinite(q[k]):raise ValueError('finite quote required')
  side=r['affectedSide']
  if side not in ('home','away'):raise ValueError('affected side required')
  sign=1 if side=='home' else -1
  out.update(status='DESCRIPTIVE_MARKET_EVENT',bookmaker=pre['bookmaker'],homeSpreadChange=post['spreadHome']-pre['spreadHome'],affectedTeamSpreadDeterioration=sign*(post['spreadHome']-pre['spreadHome']),totalChange=post['total']-pre['total'],minutesToPostQuote=(dt(post['observedAt'])-dt(r['news']['publishedAt'])).total_seconds()/60,confounders=r.get('confounders',[]),cleanEventEligible=r.get('confounders')==[])
  out['affectedTeamImpliedPointsChange']=((post['total']-pre['total'])-sign*(post['spreadHome']-pre['spreadHome']))/2
  out['interpretation']='Market benchmark only; not a causal QB valuation or independent forecast adjustment'
 except (KeyError,TypeError,ValueError) as e:out['reasons'].append(str(e))
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('ledger',type=Path);a=p.parse_args()
 print(json.dumps([measure(r) for r in json.loads(a.ledger.read_text())],indent=2,allow_nan=False))
