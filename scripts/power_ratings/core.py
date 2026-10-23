"""Read-only ranking transforms; no model promotion or prediction writes."""
import numpy as np


def pair_ratings(margins):
    """Least-squares projection of a complete antisymmetric neutral margin matrix.

    Divide by N, including the zero self-match, so additive team differences
    recover the original points scale (not N/(N-1) inflated ratings).
    """
    m = np.asarray(margins, dtype=float)
    if m.ndim != 2 or m.shape[0] != m.shape[1] or len(m) < 2:
        raise ValueError('complete square matchup matrix required')
    if not np.isfinite(m).all() or not np.allclose(m, -m.T, atol=1e-8):
        raise ValueError('finite antisymmetric margins required')
    r = m.mean(axis=1)
    residual = m - (r[:, None] - r[None, :])
    return r, float(np.sqrt(np.mean(residual**2)))


def market_ratings(teams, quotes, as_of, hfa):
    """Do not manufacture national ranks from disconnected weekly matchups.

    Quotes are normalized HOME spreads, with explicit observedAt and kickoff.
    One latest observation per game/book, then median across books per game.
    Caller supplies timezone-aware datetime and frozen HFA, in points.
    """
    from datetime import datetime
    parse = lambda s: datetime.fromisoformat(s.replace('Z', '+00:00'))
    if as_of.tzinfo is None: raise ValueError('timezone required')
    idx = {t:i for i,t in enumerate(teams)}
    if len(idx) != len(teams): raise ValueError('duplicate teams')
    latest = {}; rejected = 0
    for q in quotes:
        try:
            obs, kick = parse(q['observedAt']), parse(q['kickoff'])
            if obs.tzinfo is None or kick.tzinfo is None: raise ValueError('timezone')
            spread = float(q['homeSpread'])
            if not np.isfinite(spread) or not obs <= as_of or not obs < kick: raise ValueError('late')
            if q['home'] not in idx or q['away'] not in idx or q['home']==q['away']: raise ValueError('identity')
            if not q['source'] or not q['book'] or not isinstance(q['neutral'],bool): raise ValueError('provenance')
            key=(q['gameId'],q['book'])
            if key not in latest or obs>parse(latest[key]['observedAt']):latest[key]=q
        except (ValueError,KeyError,TypeError):rejected+=1
    groups={}
    for q in latest.values(): groups.setdefault(q['gameId'],[]).append(q)
    adj={t:set() for t in teams}; rows=[]; y=[]
    for qs in groups.values():
        q=qs[0]
        if any((z['home'],z['away'],z['neutral'],z['kickoff']) != (q['home'],q['away'],q['neutral'],q['kickoff']) for z in qs):
            rejected+=len(qs);continue
        h,a=q['home'],q['away'];adj[h].add(a);adj[a].add(h)
        row=np.zeros(len(teams));row[idx[h]]=1;row[idx[a]]=-1;rows.append(row)
        y.append(-float(np.median([float(z['homeSpread']) for z in qs]))-(0 if q['neutral'] else hfa))
    components=[]; unseen=set(teams)
    while unseen:
        todo=[min(unseen)];component=set()
        while todo:
            t=todo.pop()
            if t in component:continue
            component.add(t);todo.extend(adj[t]-component)
        unseen-=component;components.append(sorted(component))
    meta={'games':len(rows),'components':len(components),'rejectedQuotes':rejected,
          'status':'CONNECTED' if len(components)==1 else 'INSUFFICIENT_CONNECTED_MARKETS',
          'method':'equal-game-weight least squares; median of latest book quotes; zero-sum; fixed HFA',
          'homeFieldPoints':hfa}
    if len(components)!=1:return None,meta
    X=np.vstack([rows,np.ones(len(teams))]);y=np.r_[y,0.]
    r=np.linalg.lstsq(X,y,rcond=None)[0];meta['fitRmse']=float(np.sqrt(np.mean((np.asarray(rows)@r-y[:-1])**2)))
    return r,meta
