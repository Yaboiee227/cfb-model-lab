#!/usr/bin/env python3
"""Build leakage-safe NFL pass-protection / pass-rush / OL-continuity features.

Historical target snapshots: 2022-2025, target weeks 1-18.
2021 is used only as a prior-season baseline for 2022.
Current target: 2026 Week 6, using REG Weeks 1-5 only.

Sources:
- nflverse weekly team stats for offensive/defensive dropback denominators
- nflverse mirror of PFR weekly advanced passing / defense
- nflverse snap counts for offensive-line continuity

No target-week realized information is permitted in a target pregame snapshot.
All output is development/research only.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

CONTEXT_SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
HIST_TARGET_SEASONS = [2022, 2023, 2024, 2025]
CURRENT_SEASON = 2026
CURRENT_TARGET_WEEK = 6
OUT_HIST = Path("nfl_data/historical/team_week_trench_2022_2025.csv")
OUT_CURRENT = Path("nfl_data/generated/trench_2026_week6_pregame.csv")
OUT_QA = Path("nfl_data/generated/trench_build_qa_2026_week6.json")

TEAM_URL = "https://github.com/nflverse/nflverse-data/releases/download/stats_team/stats_team_week_{season}.csv"
PFR_PASS_URL = "https://github.com/nflverse/nflverse-data/releases/download/pfr_advstats/advstats_week_pass_{season}.parquet"
PFR_DEF_URL = "https://github.com/nflverse/nflverse-data/releases/download/pfr_advstats/advstats_week_def_{season}.parquet"
SNAP_URL = "https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_{season}.parquet"

ALIASES = {
    "LAR": "LA", "STL": "LA", "RAM": "LA",
    "OAK": "LV", "SD": "LAC", "SDG": "LAC",
    "JAC": "JAX", "WSH": "WAS", "WFT": "WAS",
}
OL_POS = {"C", "G", "LG", "RG", "T", "LT", "RT", "OT", "OG", "OL"}
PRESSURE_METRICS = [
    "off_pressure_rate", "off_hurry_rate", "off_hit_rate", "off_sack_rate_pfr",
    "off_blitz_faced_rate", "off_pressure_to_sack",
    "def_pressure_events_per_db", "def_hurry_events_per_db", "def_hit_events_per_db",
    "def_sack_rate_pfr", "def_blitzer_events_per_db", "def_pressure_to_sack",
]
OL_METRICS = [
    "ol_last_top5_overlap", "ol_last3_top5_overlap", "ol_last_top5_avg_snap_pct",
    "ol_last_full_snap_count", "ol_last_half_snap_count", "ol_cumulative_top5_concentration",
    "ol_cumulative_unique_players",
]
ALL_METRICS = PRESSURE_METRICS + OL_METRICS


def norm_team(v) -> str:
    s = str(v or "").strip().upper()
    return ALIASES.get(s, s)


def fnum(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def weighted_mean(rows, value_key, weight_key):
    num = den = 0.0
    for r in rows:
        v, w = fnum(r.get(value_key)), fnum(r.get(weight_key))
        if v is None or w is None or w <= 0:
            continue
        num += v * w; den += w
    return None if den <= 0 else num / den


def load_team_stats(season):
    df = pd.read_csv(TEAM_URL.format(season=season))
    df = df[(df["season"] == season) & (df["season_type"].astype(str).str.upper() == "REG")].copy()
    df["team"] = df["team"].map(norm_team)
    df["opponent_team"] = df["opponent_team"].map(norm_team)
    df["week"] = pd.to_numeric(df["week"], errors="coerce").astype("Int64")
    df["dropbacks"] = pd.to_numeric(df["attempts"], errors="coerce").fillna(0) + pd.to_numeric(df["sacks_suffered"], errors="coerce").fillna(0)
    weekly = {}
    for _, r in df.iterrows():
        if pd.isna(r["week"]):
            continue
        weekly[(norm_team(r["team"]), int(r["week"]))] = {
            "dropbacks": float(r["dropbacks"]),
            "opponent": norm_team(r["opponent_team"]),
            "game_id": str(r.get("game_id", "")),
        }
    # Defensive denominator = opponent offensive dropbacks from the same game/week.
    for (team, week), row in list(weekly.items()):
        opp = row["opponent"]
        opp_row = weekly.get((opp, week))
        row["opp_dropbacks"] = None if opp_row is None else opp_row["dropbacks"]
    return weekly, df


def load_pfr(season, kind):
    url = (PFR_PASS_URL if kind == "pass" else PFR_DEF_URL).format(season=season)
    df = pd.read_parquet(url)
    df = df[(pd.to_numeric(df["season"], errors="coerce") == season)].copy()
    if "game_type" in df.columns:
        # nflverse/PFR generally uses REG, but preserve rows if field is blank rather than guessing.
        gt = df["game_type"].astype(str).str.upper()
        df = df[(gt == "REG") | (gt == "") | (gt == "NAN")]
    df["team"] = df["team"].map(norm_team)
    df["week"] = pd.to_numeric(df["week"], errors="coerce").astype("Int64")
    return df


def load_snaps(season):
    df = pd.read_parquet(SNAP_URL.format(season=season))
    df = df[(pd.to_numeric(df["season"], errors="coerce") == season)].copy()
    df["team"] = df["team"].map(norm_team)
    df["week"] = pd.to_numeric(df["week"], errors="coerce").astype("Int64")
    df["position"] = df["position"].astype(str).str.upper().str.strip()
    df["offense_snaps"] = pd.to_numeric(df["offense_snaps"], errors="coerce").fillna(0.0)
    df["offense_pct"] = pd.to_numeric(df["offense_pct"], errors="coerce")
    # Some historical providers encode percent 0-100, others fraction 0-1.
    if df["offense_pct"].dropna().max() > 1.5:
        df["offense_pct"] = df["offense_pct"] / 100.0
    return df


def build_weekly_pressure(season, team_week, ppass, pdef):
    out = defaultdict(dict)
    pass_fields = ["times_pressured", "times_hurried", "times_hit", "times_sacked", "times_blitzed"]
    def_fields = ["def_pressures", "def_times_hurried", "def_times_hitqb", "def_sacks", "def_times_blitzed"]
    for c in pass_fields:
        if c not in ppass.columns: ppass[c] = 0.0
        ppass[c] = pd.to_numeric(ppass[c], errors="coerce").fillna(0.0)
    for c in def_fields:
        if c not in pdef.columns: pdef[c] = 0.0
        pdef[c] = pd.to_numeric(pdef[c], errors="coerce").fillna(0.0)

    for (team, week), g in ppass.dropna(subset=["week"]).groupby(["team", "week"]):
        week = int(week); denom = team_week.get((team, week), {}).get("dropbacks")
        sums = {c: float(g[c].sum()) for c in pass_fields}
        out[(team, week)].update({
            "off_dropbacks": denom,
            "off_pressure_rate": div(sums["times_pressured"], denom),
            "off_hurry_rate": div(sums["times_hurried"], denom),
            "off_hit_rate": div(sums["times_hit"], denom),
            "off_sack_rate_pfr": div(sums["times_sacked"], denom),
            "off_blitz_faced_rate": div(sums["times_blitzed"], denom),
            "off_pressure_to_sack": div(sums["times_sacked"], sums["times_pressured"]),
        })
    for (team, week), g in pdef.dropna(subset=["week"]).groupby(["team", "week"]):
        week = int(week); denom = team_week.get((team, week), {}).get("opp_dropbacks")
        sums = {c: float(g[c].sum()) for c in def_fields}
        out[(team, week)].update({
            "def_opp_dropbacks": denom,
            # PFR defense rows are player-level; multiple defenders may record pressure on a play.
            # Therefore these are deliberately named EVENTS per dropback, not play-level pressure rates.
            "def_pressure_events_per_db": div(sums["def_pressures"], denom),
            "def_hurry_events_per_db": div(sums["def_times_hurried"], denom),
            "def_hit_events_per_db": div(sums["def_times_hitqb"], denom),
            "def_sack_rate_pfr": div(sums["def_sacks"], denom),
            "def_blitzer_events_per_db": div(sums["def_times_blitzed"], denom),
            "def_pressure_to_sack": div(sums["def_sacks"], sums["def_pressures"]),
        })
    return out


def weekly_ol(snaps):
    out = {}
    ol = snaps[snaps["position"].isin(OL_POS) & (snaps["offense_snaps"] > 0)].copy()
    for (team, week), g in ol.dropna(subset=["week"]).groupby(["team", "week"]):
        week = int(week)
        g = g.sort_values("offense_snaps", ascending=False)
        top5 = list(g.head(5)["pfr_player_id"].fillna(g.head(5)["player"]).astype(str))
        pct = g.head(5)["offense_pct"].dropna()
        out[(team, week)] = {
            "top5": top5,
            "top5_avg_snap_pct": None if pct.empty else float(pct.mean()),
            "full_snap_count": int((g["offense_pct"] >= 0.90).sum()),
            "half_snap_count": int((g["offense_pct"] >= 0.50).sum()),
            "player_snaps": {str((r.get("pfr_player_id") if pd.notna(r.get("pfr_player_id")) else r.get("player"))): float(r["offense_snaps"]) for _, r in g.iterrows()},
        }
    return out, ol


def overlap(a, b):
    if not a or not b: return None
    return len(set(a) & set(b)) / 5.0


def aggregate_pressure(weekly, team, weeks):
    rows = [weekly.get((team, w), {}) for w in weeks]
    off_db = sum(fnum(r.get("off_dropbacks")) or 0 for r in rows)
    def_db = sum(fnum(r.get("def_opp_dropbacks")) or 0 for r in rows)

    # Reconstruct approximate event counts from weekly rate * weekly denominator, then re-rate.
    def accum(rate_key, denom_key, denom_sum):
        events = 0.0; anyv = False
        for r in rows:
            rate, den = fnum(r.get(rate_key)), fnum(r.get(denom_key))
            if rate is not None and den is not None:
                events += rate * den; anyv = True
        return None if not anyv or denom_sum <= 0 else events / denom_sum

    out = {
        "off_pressure_rate": accum("off_pressure_rate", "off_dropbacks", off_db),
        "off_hurry_rate": accum("off_hurry_rate", "off_dropbacks", off_db),
        "off_hit_rate": accum("off_hit_rate", "off_dropbacks", off_db),
        "off_sack_rate_pfr": accum("off_sack_rate_pfr", "off_dropbacks", off_db),
        "off_blitz_faced_rate": accum("off_blitz_faced_rate", "off_dropbacks", off_db),
        "def_pressure_events_per_db": accum("def_pressure_events_per_db", "def_opp_dropbacks", def_db),
        "def_hurry_events_per_db": accum("def_hurry_events_per_db", "def_opp_dropbacks", def_db),
        "def_hit_events_per_db": accum("def_hit_events_per_db", "def_opp_dropbacks", def_db),
        "def_sack_rate_pfr": accum("def_sack_rate_pfr", "def_opp_dropbacks", def_db),
        "def_blitzer_events_per_db": accum("def_blitzer_events_per_db", "def_opp_dropbacks", def_db),
    }
    # Conversion rates need event-weighting; approximate by pressure-rate denominators.
    def conv(rate_key, pressure_key, denom_key):
        sacks = pressures = 0.0; anyv = False
        for r in rows:
            cr, pr, den = fnum(r.get(rate_key)), fnum(r.get(pressure_key)), fnum(r.get(denom_key))
            if cr is not None and pr is not None and den is not None:
                p = pr * den; pressures += p; sacks += cr * p; anyv = True
        return None if not anyv or pressures <= 0 else sacks / pressures
    out["off_pressure_to_sack"] = conv("off_pressure_to_sack", "off_pressure_rate", "off_dropbacks")
    out["def_pressure_to_sack"] = conv("def_pressure_to_sack", "def_pressure_events_per_db", "def_opp_dropbacks")
    return out


def aggregate_ol(ol_weekly, team, weeks):
    observed = [w for w in weeks if (team, w) in ol_weekly]
    if not observed:
        return {k: None for k in OL_METRICS}
    last = observed[-1]
    lastrow = ol_weekly[(team, last)]
    pair_overlaps = []
    for a, b in zip(observed[-4:-1], observed[-3:]):
        x = overlap(ol_weekly[(team, a)]["top5"], ol_weekly[(team, b)]["top5"])
        if x is not None: pair_overlaps.append(x)
    last_overlap = None
    if len(observed) >= 2:
        last_overlap = overlap(ol_weekly[(team, observed[-2])]["top5"], lastrow["top5"])

    cum = defaultdict(float)
    for w in observed:
        for pid, snaps in ol_weekly[(team, w)]["player_snaps"].items(): cum[pid] += snaps
    total = sum(cum.values())
    top5sum = sum(sorted(cum.values(), reverse=True)[:5])
    return {
        "ol_last_top5_overlap": last_overlap,
        "ol_last3_top5_overlap": None if not pair_overlaps else sum(pair_overlaps) / len(pair_overlaps),
        "ol_last_top5_avg_snap_pct": lastrow["top5_avg_snap_pct"],
        "ol_last_full_snap_count": float(lastrow["full_snap_count"]),
        "ol_last_half_snap_count": float(lastrow["half_snap_count"]),
        "ol_cumulative_top5_concentration": div(top5sum, total),
        "ol_cumulative_unique_players": float(len(cum)),
    }


def combine_metrics(pressure_weekly, ol_weekly, team, weeks):
    x = aggregate_pressure(pressure_weekly, team, weeks)
    x.update(aggregate_ol(ol_weekly, team, weeks))
    return x


def clean(v):
    x = fnum(v)
    return None if x is None else round(x, 6)


def snapshot_row(season, target_week, team, pressure_weekly, ol_weekly, prior_pressure, prior_ol):
    prior_weeks = [w for w in range(1, target_week) if (team, w) in pressure_weekly or (team, w) in ol_weekly]
    last3 = prior_weeks[-3:]
    cur = combine_metrics(pressure_weekly, ol_weekly, team, prior_weeks) if prior_weeks else {k: None for k in ALL_METRICS}
    rec = combine_metrics(pressure_weekly, ol_weekly, team, last3) if last3 else {k: None for k in ALL_METRICS}
    prior_all_weeks = sorted({w for (t, w) in set(prior_pressure) | set(prior_ol) if t == team})
    prv = combine_metrics(prior_pressure, prior_ol, team, prior_all_weeks) if prior_all_weeks else {k: None for k in ALL_METRICS}
    row = {
        "season": season, "target_week": target_week, "team": team,
        "games_before": len(prior_weeks),
        "max_current_week_used": max(prior_weeks) if prior_weeks else 0,
    }
    for m in ALL_METRICS:
        row[f"cur_{m}"] = clean(cur.get(m)); row[f"last3_{m}"] = clean(rec.get(m)); row[f"prior_{m}"] = clean(prv.get(m))
    row["release_state"] = "HOLD_RESEARCH_ONLY"
    return row


def main():
    OUT_HIST.parent.mkdir(parents=True, exist_ok=True); OUT_CURRENT.parent.mkdir(parents=True, exist_ok=True)
    data = {}; qa = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "release_state": "HOLD_RESEARCH_ONLY", "website_publish_allowed": False, "seasons": {}}
    all_teams = set()
    for season in CONTEXT_SEASONS:
        team_week, team_df = load_team_stats(season)
        ppass, pdef = load_pfr(season, "pass"), load_pfr(season, "def")
        snaps = load_snaps(season)
        pressure = build_weekly_pressure(season, team_week, ppass, pdef)
        ol_week, ol_rows = weekly_ol(snaps)
        teams = sorted(set(t for t, _ in team_week) | set(t for t, _ in pressure) | set(t for t, _ in ol_week))
        all_teams.update(teams)
        pos_counts = snaps.loc[snaps["offense_snaps"] > 0, "position"].value_counts().head(25).to_dict()
        qa["seasons"][str(season)] = {
            "team_stat_rows": int(len(team_df)), "pfr_pass_rows": int(len(ppass)), "pfr_def_rows": int(len(pdef)),
            "snap_rows": int(len(snaps)), "ol_snap_rows": int(len(ol_rows)), "pressure_team_weeks": int(len(pressure)),
            "ol_team_weeks": int(len(ol_week)), "teams": len(teams), "top_position_counts": {str(k): int(v) for k, v in pos_counts.items()},
        }
        data[season] = (pressure, ol_week, teams)

    hist = []
    leakage = 0
    for season in HIST_TARGET_SEASONS:
        pressure, ol_week, teams = data[season]
        prior_pressure, prior_ol, _ = data[season - 1]
        for week in range(1, 19):
            for team in sorted(set(teams) | set(data[season-1][2])):
                r = snapshot_row(season, week, team, pressure, ol_week, prior_pressure, prior_ol)
                if r["max_current_week_used"] >= week: leakage += 1
                hist.append(r)
    hdf = pd.DataFrame(hist)
    hdf.to_csv(OUT_HIST, index=False)

    pressure, ol_week, teams = data[CURRENT_SEASON]
    prior_pressure, prior_ol, _ = data[CURRENT_SEASON - 1]
    current = [snapshot_row(CURRENT_SEASON, CURRENT_TARGET_WEEK, team, pressure, ol_week, prior_pressure, prior_ol) for team in sorted(teams)]
    cdf = pd.DataFrame(current)
    cdf.to_csv(OUT_CURRENT, index=False)

    future_rows = int((cdf["max_current_week_used"] >= CURRENT_TARGET_WEEK).sum())
    qa.update({
        "historical_rows": int(len(hdf)), "historical_leakage_rows": leakage,
        "current_rows": int(len(cdf)), "current_target_or_future_rows_used": future_rows,
        "current_max_week_used": int(cdf["max_current_week_used"].max()),
        "metric_columns": ALL_METRICS,
        "ol_position_policy": sorted(OL_POS),
        "defensive_pressure_note": "PFR defense is player-level; defensive pressure/blitz fields are event counts per opponent dropback, not asserted play-level rates.",
        "pregame_rule": "All current-season source weeks must be strictly less than target_week; prior-season data may be used only as a prior.",
    })
    if leakage or future_rows:
        raise RuntimeError(f"Leakage guard failed historical={leakage} current={future_rows}")
    OUT_QA.write_text(json.dumps(qa, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"historical": str(OUT_HIST), "current": str(OUT_CURRENT), "qa": str(OUT_QA), "historical_rows": len(hdf), "current_rows": len(cdf), "leakage": 0}, indent=2))


if __name__ == "__main__":
    main()
