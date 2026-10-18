#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

IMMUTABLE_FIELDS = [
    "gameId","awayTeam","homeTeam","kickoff","projectedSpreadHome","projectedTotal",
    "projectedWinner","marketSpreadHome","marketTotal","marketMoneylineHome","marketMoneylineAway",
    "marketSource","marketObservedAt"
]

class RecordError(RuntimeError): pass

def read_json(path: Path, default=None):
    if not path.exists():
        if default is not None: return default
        raise RecordError(f"Missing required file: {path}")
    with path.open(encoding="utf-8") as f: return json.load(f)

def atomic_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=path.name, dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f: f.write(text)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def canonical_digest(payload: dict) -> str:
    games=[]
    for g in payload.get("games",[]): games.append({k:g.get(k) for k in IMMUTABLE_FIELDS})
    body={"league":payload.get("league"),"season":payload.get("season"),"week":payload.get("week"),"games":games}
    raw=json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()

def validate_lock(payload: dict):
    if payload.get("locked") is not True: raise RecordError("Projection file is not locked")
    locked_at=payload.get("lockedAt")
    if not locked_at: raise RecordError("Projection file missing lockedAt")
    expected=payload.get("lockDigest")
    actual=canonical_digest(payload)
    if not expected: raise RecordError("Locked projection file missing lockDigest")
    if expected != actual: raise RecordError("LOCK VIOLATION: immutable projection/market fields changed after lock")
    lock_dt=datetime.fromisoformat(locked_at.replace("Z","+00:00"))
    for g in payload.get("games",[]):
        ko=datetime.fromisoformat(str(g["kickoff"]).replace("Z","+00:00"))
        if lock_dt > ko: raise RecordError(f"lockedAt is after kickoff for {g['gameId']}")

def norm_name(s:str)->str: return re.sub(r"[^a-z0-9]","",str(s).lower())
def load_aliases(root:Path):
    legacy=read_json(root/"data/team-aliases.json",{}) if (root/"data/team-aliases.json").exists() else {}
    mapping={}
    def add(canon, vals):
        mapping[norm_name(canon)]=canon
        for v in vals or []: mapping[norm_name(v)]=canon
    if isinstance(legacy,dict):
        for k,v in legacy.items(): add(k,v if isinstance(v,list) else [v])
    return mapping

def canonical_team(name, aliases): return aliases.get(norm_name(name), name)

def match_score(game:dict, scores:list[dict], aliases:dict):
    source_id=str(game.get("sourceGameId") or "")
    if source_id:
        hits=[s for s in scores if str(s.get("sourceGameId"))==source_id]
        if len(hits)==1:return hits[0]
        if len(hits)>1:raise RecordError(f"Duplicate sourceGameId {source_id}")
    a,h=canonical_team(game["awayTeam"],aliases),canonical_team(game["homeTeam"],aliases)
    hits=[s for s in scores if canonical_team(s["awayTeam"],aliases)==a and canonical_team(s["homeTeam"],aliases)==h]
    if len(hits)==1:return hits[0]
    if not hits:return None
    raise RecordError(f"Ambiguous team match for {game['gameId']}")

def fmt_num(value):
    n=float(value)
    return str(int(n)) if n.is_integer() else f"{n:.2f}".rstrip("0").rstrip(".")

def signed_line(value):
    n=float(value)
    if n == 0: return "PK"
    return f"{'+' if n > 0 else ''}{fmt_num(n)}"

def ats_position(game:dict, pick:str|None):
    market=game.get("marketSpreadHome")
    if market is None or pick not in {game.get("homeTeam"),game.get("awayTeam")}:
        return None
    team_line=float(market) if pick==game["homeTeam"] else -float(market)
    return f"{pick} {signed_line(team_line)}"

def total_position(game:dict, pick:str|None):
    market=game.get("marketTotal")
    if market is None or pick not in {"OVER","UNDER"}: return None
    return f"{pick.title()} {fmt_num(market)}"

def su_position(game:dict, winner:str|None):
    if winner not in {game.get("homeTeam"),game.get("awayTeam")}: return None
    return f"{winner} SU"

def su_market_price(game:dict, winner:str|None):
    if winner==game.get("homeTeam"): return game.get("marketMoneylineHome")
    if winner==game.get("awayTeam"): return game.get("marketMoneylineAway")
    return None

def result_obj(status="PENDING", pick=None, detail=None, position=None, market_price=None):
    d={"pick":pick,"result":status}
    if position is not None:d["position"]=position
    if market_price is not None:d["marketPrice"]=market_price
    if detail:d["detail"]=detail
    return d

def grade_game(game:dict, score:dict|None, override:dict|None=None):
    if override:
        action=str(override.get("action","")).upper()
        if action=="VOID": score={"status":"VOID","awayTeam":game["awayTeam"],"homeTeam":game["homeTeam"],"source":"manual-override"}
        elif action=="SET_FINAL":
            score={"status":"FINAL","awayTeam":game["awayTeam"],"homeTeam":game["homeTeam"],"awayScore":int(override["awayScore"]),"homeScore":int(override["homeScore"]),"source":"manual-override","overtime":bool(override.get("overtime",False))}
    base={"gameId":game["gameId"],"awayTeam":game["awayTeam"],"homeTeam":game["homeTeam"],"kickoff":game["kickoff"],
          "projection":{"spreadHome":game.get("projectedSpreadHome"),"total":game.get("projectedTotal"),"winner":game.get("projectedWinner")},
          "market":{"spreadHome":game.get("marketSpreadHome"),"total":game.get("marketTotal"),"moneylineHome":game.get("marketMoneylineHome"),"moneylineAway":game.get("marketMoneylineAway"),"source":game.get("marketSource"),"observedAt":game.get("marketObservedAt")}}
    if score is None:
        return {**base,"status":"REVIEW","reviewReason":"No score source match; no guess made","ats":result_obj("REVIEW"),"totals":result_obj("REVIEW"),"straightUp":result_obj("REVIEW")}
    st=str(score.get("status","")).upper()
    if st in {"CANCELLED","CANCELED","POSTPONED","VOID"}:
        return {**base,"status":"VOID","final":None,"ats":result_obj("VOID"),"totals":result_obj("VOID"),"straightUp":result_obj("VOID")}
    if st!="FINAL":
        return {**base,"status":"PENDING","final":None,"ats":result_obj("PENDING"),"totals":result_obj("PENDING"),"straightUp":result_obj("PENDING")}
    away,home=int(score["awayScore"]),int(score["homeScore"])
    margin=home-away; combined=home+away
    final={"awayScore":away,"homeScore":home,"total":combined,"overtime":bool(score.get("overtime",False)),"source":score.get("source","ESPN")}

    # ATS: the model creates the projection position; the locked market spread is the grading benchmark.
    ms,ks=game.get("projectedSpreadHome"),game.get("marketSpreadHome")
    if ks is None:
        ats=result_obj("REVIEW",detail="Missing saved market spread")
    elif ms is None:
        ats=result_obj("NO_PICK",detail="Missing model spread")
    elif float(ms)==float(ks):
        ats=result_obj("NO_PICK",detail="Model spread equals saved market spread")
    else:
        pick=game["homeTeam"] if float(ms)<float(ks) else game["awayTeam"]
        cover=margin+float(ks)
        if cover==0: r="PUSH"
        elif pick==game["homeTeam"]: r="WIN" if cover>0 else "LOSS"
        else: r="WIN" if cover<0 else "LOSS"
        ats=result_obj(r,pick,position=ats_position(game,pick))

    # Totals: model above market = Over projection; model below market = Under projection.
    mt,kt=game.get("projectedTotal"),game.get("marketTotal")
    if kt is None: totals=result_obj("REVIEW",detail="Missing saved market total")
    elif mt is None: totals=result_obj("NO_PICK",detail="Missing model total")
    elif float(mt)==float(kt): totals=result_obj("NO_PICK",detail="Model total equals saved market total")
    else:
        pick="OVER" if float(mt)>float(kt) else "UNDER"
        if combined==float(kt):r="PUSH"
        elif pick=="OVER":r="WIN" if combined>float(kt) else "LOSS"
        else:r="WIN" if combined<float(kt) else "LOSS"
        totals=result_obj(r,pick,position=total_position(game,pick))

    # Straight Up: grade only whether the projected winner won. Moneyline price is reference metadata only.
    winner=game.get("projectedWinner")
    price=su_market_price(game,winner)
    if away==home:
        su=result_obj("TIE",winner,detail="Final score tied; excluded from straight-up W/L record",position=su_position(game,winner),market_price=price)
    elif winner not in {game["awayTeam"],game["homeTeam"]}:
        su=result_obj("REVIEW",winner,detail="Projected winner missing or invalid")
    else:
        actual=game["homeTeam"] if home>away else game["awayTeam"]
        su=result_obj("WIN" if winner==actual else "LOSS",winner,position=su_position(game,winner),market_price=price)
    return {**base,"status":"FINAL","final":final,"ats":ats,"totals":totals,"straightUp":su}

def counts(games,key):
    vals=[str(g.get(key,{}).get("result","")).upper() for g in games]
    w,l,p=vals.count("WIN"),vals.count("LOSS"),vals.count("PUSH")
    return {"wins":w,"losses":l,"pushes":p,"winPct":round(w/(w+l)*100,1) if w+l else None,"graded":w+l+p}

def merge_counts(*parts):
    w=sum(int((p or {}).get("wins",0)) for p in parts);l=sum(int((p or {}).get("losses",0)) for p in parts);push=sum(int((p or {}).get("pushes",0)) for p in parts)
    return {"wins":w,"losses":l,"pushes":push,"winPct":round(w/(w+l)*100,1) if w+l else None,"graded":w+l+push}

def build_summary(root:Path, league:str):
    games=[]; generated_weeks=[]
    for path in sorted((root/league/"results").glob("week-*.json")):
        doc=read_json(path); gs=doc.get("games",[]); games.extend(gs)
        generated_weeks.append({"season":doc.get("season"),"week":doc.get("week"),"status":doc.get("status"),"ats":counts(gs,"ats"),"totals":counts(gs,"totals"),"straightUp":counts(gs,"straightUp"),"pending":sum(g.get("status")=="PENDING" for g in gs),"review":sum(g.get("status")=="REVIEW" for g in gs)})
    baseline=read_json(root/league/"record-baseline.json",{}) if (root/league/"record-baseline.json").exists() else {}
    generated_keys={(w.get("season"),w.get("week")) for w in generated_weeks}
    baseline_weeks=[w for w in baseline.get("weeks",[]) if (w.get("season"),w.get("week")) not in generated_keys]
    by_week=sorted(baseline_weeks+generated_weeks,key=lambda w:(int(w.get("season") or 0),int(w.get("week") or 0)))
    baseline_overall={"ats":{},"totals":{},"straightUp":{}}
    for w in baseline_weeks:
        for key in baseline_overall: baseline_overall[key]=merge_counts(baseline_overall[key],w.get(key,{}))
    generated_overall={"ats":counts(games,"ats"),"totals":counts(games,"totals"),"straightUp":counts(games,"straightUp")}
    overall={key:merge_counts(baseline_overall.get(key),generated_overall.get(key)) for key in generated_overall}
    current=by_week[-1]["week"] if by_week else None
    out={"schemaVersion":1,"league":league,"generatedAt":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),"currentWeek":current,
         "label":"Projection performance graded against locked publication-time market numbers; not a wager ledger.","overall":overall,"weeks":by_week,
         "pending":sum(int(w.get("pending",0)) for w in by_week),"review":sum(int(w.get("review",0)) for w in by_week)}
    if baseline_weeks: out["baselineSource"]=baseline.get("source")
    if league=="cfb":
        groups={}
        for g in games:
            c=g.get("conference") or "Other";groups.setdefault(c,[]).append(g)
        out["byConference"]=[{"conference":c,"ats":counts(gs,"ats"),"totals":counts(gs,"totals"),"straightUp":counts(gs,"straightUp"),"games":len(gs)} for c,gs in sorted(groups.items())]
        if baseline_weeks: out["conferenceNote"]="Conference breakdown currently covers generated JSON result weeks; the migrated Week 7 baseline remains included in overall and weekly records."
    atomic_json(root/league/"record-summary.json",out);return out

def load_overrides(root,league):
    doc=read_json(root/league/"manual-overrides.json",{"overrides":[]});return {x["gameId"]:x for x in doc.get("overrides",[])}

def grade_week(root:Path,league:str,week:str,score_file:Path|None,dry_run=False):
    if week=="latest":
        files=sorted((root/league/"projections").glob("week-*.json"))
        if not files: raise RecordError(f"No {league} projection files")
        p=files[-1]
    else:p=root/league/"projections"/f"week-{int(week):02d}.json"
    proj=read_json(p);validate_lock(proj)
    if score_file:scores=read_json(score_file).get("games",[])
    else:
        from score_sources import fetch_scores_for_projection
        scores=fetch_scores_for_projection(league,proj)
    aliases=load_aliases(root); overrides=load_overrides(root,league)
    graded=[]; unmatched=[]
    for game in proj.get("games",[]):
        s=match_score(game,scores,aliases)
        if s is None: unmatched.append(game["gameId"])
        row=grade_game(game,s,overrides.get(game["gameId"]));row["conference"]=game.get("conference");row["confidenceTier"]=game.get("confidenceTier");graded.append(row)
    if unmatched: raise RecordError("Unmatched projection games: "+", ".join(unmatched))
    status="COMPLETE" if all(g["status"] in {"FINAL","VOID"} for g in graded) else "PARTIAL"
    out={"schemaVersion":1,"league":league,"season":proj.get("season"),"week":proj.get("week"),"generatedAt":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),"status":status,"source":"ESPN scoreboard via scripts/score_sources.py" if not score_file else f"mock:{score_file.name}","games":graded}
    if dry_run:
        print(json.dumps(out,indent=2));return out
    out_path=root/league/"results"/f"week-{int(proj['week']):02d}.json";atomic_json(out_path,out);build_summary(root,league)
    log=root/league/"grading-log.json";doc=read_json(log,{"runs":[]});doc["runs"].append({"at":out["generatedAt"],"week":proj["week"],"status":status,"final":sum(g["status"]=="FINAL" for g in graded),"pending":sum(g["status"]=="PENDING" for g in graded),"void":sum(g["status"]=="VOID" for g in graded),"overridesUsed":[gid for gid in overrides if any(g["gameId"]==gid for g in graded)]});doc["runs"]=doc["runs"][-200:];atomic_json(log,doc)
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--league",choices=["cfb","nfl"],required=True);ap.add_argument("--week",default="latest");ap.add_argument("--scores");ap.add_argument("--dry-run",action="store_true");ap.add_argument("--root",default=".");args=ap.parse_args()
    try: grade_week(Path(args.root),args.league,args.week,Path(args.scores) if args.scores else None,args.dry_run)
    except Exception as e: print(f"RECORD_TRACKER_ERROR: {e}",file=sys.stderr);sys.exit(1)
if __name__=="__main__":main()
