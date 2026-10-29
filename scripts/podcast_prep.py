#!/usr/bin/env python3
"""Podcast prep — a data sheet for every game of the upcoming NFL week.

The data layer for the weekly podcast (skill `podcast-prep`). For each game:

  LINES      DraftKings spread/total/moneyline, opening line → now, implied
             team totals, market win% (de-vigged) vs ESPN FPI win%.
  LINE CHECK two independent "fair lines" against the market:
               - SRS: points margin adjusted for opponent and home field
                 (blowouts capped at ±21, ratings shrunk toward 0 by
                 n/(n+3) — seven games of margins are mostly noise),
               - ESPN FPI win% converted to a spread (normal, SD 13.5).
             A game is flagged only when BOTH lean the same way off the
             market. Plus a naive points-for/points-against total.
  RECORDS    straight-up, ATS, over/under (from ESPN's closing lines on
             every finished game), average margin and cover margin, last 5.
  TEAM STATS ESPN season stats ranked 1-32 here (ESPN's own rank field is
             unreliable): pass/rush efficiency, 3rd down, red zone,
             turnovers, sacks both ways, pace. Points allowed from Sleeper
             DEF rows.
  SPOTS      rest days, off bye, short week, west-coast team at 1pm ET,
             divisional game, next week's opponent (lookahead).
  INJURIES   ESPN report, Out/Doubtful/Questionable.
  FANTASY    projections re-scored under explicit PPR and half-PPR rules
             (never Sleeper's pts_* fields), target/carry/snap share last 3
             games vs season, opponent's fantasy points allowed by position
             ranked 1-32 (1 = softest), Sleeper trending adds.
  PICKS      grades data/intel/podcast_picks.json against final scores —
             the show's on-air record.

Uso: python3 scripts/podcast_prep.py [week]
Salida: reports/<season>/podcast/weekNN/podcast-prep.md (+ data.json)
"""
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from statistics import NormalDist
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sleeper import api, espn  # noqa: E402
from sleeper.scoring import score_stat_line  # noqa: E402

PICKS = ROOT / "data" / "intel" / "podcast_picks.json"
ET = ZoneInfo("America/New_York")
SD = 13.5          # NFL margin std dev
HFA = 1.5          # home-field points (post-2020 market consensus)
MARGIN_CAP = 21
FLAG_EDGE = 2.0    # both models off the market by at least this many points
WEST = {"SEA", "SF", "LAR", "LAC", "LV", "ARI"}
SKILL = ("QB", "RB", "WR", "TE")

PPR = {"pass_yd": 0.04, "pass_td": 4, "pass_int": -1, "pass_2pt": 2,
       "rush_yd": 0.1, "rush_td": 6, "rush_2pt": 2,
       "rec": 1, "rec_yd": 0.1, "rec_td": 6, "rec_2pt": 2, "fum_lost": -2}
HALF = {**PPR, "rec": 0.5}


def sl(team):
    return espn.TO_SLEEPER.get(team, team)


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def fmt_spread(team, s):
    if s is None:
        return "—"
    return f"{team} {'PK' if s == 0 else f'{s:+g}'}"


def devig(ml_h, ml_a):
    if ml_h is None or ml_a is None:
        return None
    imp = lambda ml: 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)  # noqa: E731
    h, a = imp(ml_h), imp(ml_a)
    return h / (h + a)


# ------------------------------------------------------------ schedule

def parse_events(events, week):
    games = []
    for ev in events:
        c = ev["competitions"][0]
        side = {x["homeAway"]: x for x in c["competitors"]}
        h, a = side["home"], side["away"]
        rec = lambda x: {r.get("type"): r.get("summary") for r in x.get("records") or []}  # noqa: E731
        games.append({
            "id": ev["id"], "week": week,
            "date": datetime.fromisoformat(ev["date"].replace("Z", "+00:00")),
            "home": h["team"]["abbreviation"], "away": a["team"]["abbreviation"],
            "home_id": h["team"]["id"], "away_id": a["team"]["id"],
            "hs": int(h["score"]) if h.get("score") not in (None, "") else None,
            "as": int(a["score"]) if a.get("score") not in (None, "") else None,
            "final": c["status"]["type"]["name"] == "STATUS_FINAL",
            "neutral": bool(c.get("neutralSite")),
            "indoor": bool((c.get("venue") or {}).get("indoor")),
            "venue": (c.get("venue") or {}).get("fullName", ""),
            "rec_home": rec(h), "rec_away": rec(a),
        })
    return games


def load_schedule(week, season):
    sched = {}
    with ThreadPoolExecutor(8) as ex:
        futs = {w: ex.submit(espn.scoreboard, w, season, w < week) for w in range(1, week + 2)}
    for w, f in futs.items():
        sched[w] = parse_events(f.result(), w)
    return sched


# ------------------------------------------------------- records & SRS

def team_records(finals):
    rec = defaultdict(lambda: {"su": [0, 0, 0], "ats": [0, 0, 0], "ou": [0, 0, 0],
                               "fav": [0, 0, 0], "dog": [0, 0, 0], "margin": [],
                               "cover": [], "pf": [], "pa": [], "log": []})
    for g in sorted(finals, key=lambda g: g["date"]):
        m = g["hs"] - g["as"]
        o = g.get("odds")
        for team, opp, mg, pf, pa, home in ((g["home"], g["away"], m, g["hs"], g["as"], True),
                                            (g["away"], g["home"], -m, g["as"], g["hs"], False)):
            r = rec[team]
            r["su"][0 if mg > 0 else 1 if mg < 0 else 2] += 1
            r["margin"].append(mg)
            r["pf"].append(pf)
            r["pa"].append(pa)
            line = ats = ou = None
            if o:
                line = o["spread"] if home else -o["spread"]
                cov = mg + line
                r["cover"].append(cov)
                ats = "W" if cov > 0 else "L" if cov < 0 else "P"
                r["ats"]["WLP".index(ats)] += 1
                bucket = r["fav"] if line < 0 else r["dog"] if line > 0 else None
                if bucket is not None:
                    bucket["WLP".index(ats)] += 1
                if o.get("total") is not None:
                    tot = g["hs"] + g["as"]
                    ou = "O" if tot > o["total"] else "U" if tot < o["total"] else "P"
                    r["ou"]["OUP".index(ou)] += 1
            su = "W" if mg > 0 else "L" if mg < 0 else "T"
            r["log"].append(
                f"{su} {pf}-{pa} {'vs' if home else '@'} {opp}"
                + (f" ({line:+g} {'✓' if ats == 'W' else '✗' if ats == 'L' else 'P'}"
                   f"{', ' + ou if ou else ''})" if line is not None else ""))
    return rec


def srs(finals):
    games = []
    for g in finals:
        adj = g["hs"] - g["as"] - (0 if g["neutral"] else HFA)
        adj = max(-MARGIN_CAP, min(MARGIN_CAP, adj))
        games.append((g["home"], g["away"], adj))
    teams = {t for h, a, _ in games for t in (h, a)}
    r = {t: 0.0 for t in teams}
    n = defaultdict(int)
    for h, a, _ in games:
        n[h] += 1
        n[a] += 1
    for _ in range(200):
        acc = defaultdict(list)
        for h, a, m in games:
            acc[h].append(m + r[a])
            acc[a].append(-m + r[h])
        r = {t: sum(v) / len(v) for t, v in acc.items()}
        mean = sum(r.values()) / len(r)
        r = {t: v - mean for t, v in r.items()}
    return {t: v * n[t] / (n[t] + 3) for t, v in r.items()}


# --------------------------------------------------------- team stats

TEAM_METRICS = [  # key, label, higher_is_better, fmt
    ("passing.netYardsPerPassAttempt", "Net yds/pass att", True, "{:.1f}"),
    ("rushing.yardsPerRushAttempt", "Yds/rush", True, "{:.1f}"),
    ("miscellaneous.thirdDownConvPct", "3rd down %", True, "{:.0f}%"),
    ("miscellaneous.redzoneTouchdownPct", "Red-zone TD %", True, "{:.0f}%"),
    ("miscellaneous.turnOverDifferential", "Turnover diff", True, "{:+.0f}"),
    ("passing.sacks", "Sacks taken", False, "{:.0f}"),
    ("defensive.sacks", "Sacks (defense)", True, "{:.0f}"),
    ("pace", "Plays/game", True, "{:.1f}"),
]


def load_team_stats(team_ids, season):
    with ThreadPoolExecutor(8) as ex:
        res = dict(zip(team_ids, ex.map(lambda t: espn.team_stats(team_ids[t], season), team_ids)))
    for t, st in res.items():
        gp = st.get("general.gamesPlayed") or st.get("passing.teamGamesPlayed") or 0
        plays = st.get("passing.totalOffensivePlays")
        st["pace"] = plays / gp if gp and plays else None
    return res


def rank_map(values, higher_better=True):
    """team -> rank 1..N (1 = best) over the non-None values."""
    vals = sorted(((v, t) for t, v in values.items() if v is not None),
                  key=lambda x: -x[0] if higher_better else x[0])
    return {t: i + 1 for i, (_, t) in enumerate(vals)}


# ------------------------------------------------------ sleeper layer

def load_sleeper(season, week):
    rows_by_week = {}
    with ThreadPoolExecutor(6) as ex:
        futs = {w: ex.submit(api.get_week_stat_rows, season, w) for w in range(1, week)}
    for w, f in futs.items():
        rows_by_week[w] = f.result() or []

    fpa = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))  # def -> week -> pos -> pts
    dst = defaultdict(lambda: defaultdict(list))                         # team -> stat -> [per game]
    usage = defaultdict(lambda: defaultdict(lambda: {"tgt": 0, "rush": 0, "snp": 0, "tm_snp": 0}))
    team_tot = defaultdict(lambda: defaultdict(lambda: {"tgt": 0, "rush": 0}))
    for w, rows in rows_by_week.items():
        for r in rows:
            st = r.get("stats") or {}
            pos = (r.get("player") or {}).get("position")
            team, opp = r.get("team"), r.get("opponent")
            if not team:
                continue
            if pos == "DEF":
                for k in ("pts_allow", "yds_allow", "sack", "int", "fum_rec"):
                    dst[team][k].append(st.get(k) or 0)
                continue
            if pos not in SKILL or not st.get("gms_active"):
                continue
            if opp:
                fpa[opp][w][pos] += score_stat_line(st, PPR)
            u = usage[r["player_id"]][w]
            u.update(tgt=st.get("rec_tgt") or 0, rush=st.get("rush_att") or 0,
                     snp=st.get("off_snp") or 0, tm_snp=st.get("tm_off_snp") or 0, team=team)
            team_tot[team][w]["tgt"] += u["tgt"]
            team_tot[team][w]["rush"] += u["rush"]

    fpa_avg = {d: {p: sum(wk[p] for wk in weeks.values()) / len(weeks) for p in SKILL}
               for d, weeks in fpa.items()}
    fpa_rank = {p: rank_map({d: v[p] for d, v in fpa_avg.items()}) for p in SKILL}

    def shares(pid):
        weeks = sorted(w for w, u in usage[pid].items() if u["snp"] > 0)
        if not weeks:
            return None

        def agg(ws):
            t = sum(usage[pid][w]["tgt"] for w in ws)
            r = sum(usage[pid][w]["rush"] for w in ws)
            tt = sum(team_tot[usage[pid][w]["team"]][w]["tgt"] for w in ws)
            tr = sum(team_tot[usage[pid][w]["team"]][w]["rush"] for w in ws)
            s = sum(usage[pid][w]["snp"] for w in ws)
            ts = sum(usage[pid][w]["tm_snp"] for w in ws)
            return {"tgt": t / tt if tt else 0, "rush": r / tr if tr else 0,
                    "snap": s / ts if ts else 0, "g": len(ws)}
        # L3 = the TEAM's last 3 games, not the player's last 3 appearances —
        # otherwise a back returning from a month out shows month-old usage
        # (Breece Hall wk 8: "60% L3" after missing four games).
        team = usage[pid][weeks[-1]]["team"]
        team_l3 = sorted(team_tot[team])[-3:]
        l3 = [w for w in weeks if w in team_l3]
        return {"season": agg(weeks), "l3": agg(l3) if l3 else {"g": 0}, "missed_l3": len(team_l3) - len(l3)}

    proj = []
    for r in api.get_week_projections(season, week) or []:
        p = r.get("player") or {}
        pos = p.get("position")
        if pos not in SKILL or not r.get("team"):
            continue
        st = r.get("stats") or {}
        proj.append({"pid": r["player_id"], "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                     "pos": pos, "team": r["team"], "opp": r.get("opponent"),
                     "inj": p.get("injury_status"),
                     "ppr": score_stat_line(st, PPR), "half": score_stat_line(st, HALF),
                     "share": shares(r["player_id"])})
    dst_avg = {t: {k: sum(v) / len(v) for k, v in s.items() if v} for t, s in dst.items()}
    return {"fpa": fpa_avg, "fpa_rank": fpa_rank, "proj": proj, "dst": dst_avg}


# ---------------------------------------------------------------- picks

def grade_picks(sched, week):
    if not PICKS.exists():
        return None
    data = json.loads(PICKS.read_text())
    finals = {}
    for w, games in sched.items():
        for g in games:
            if g["final"]:
                finals[(w, f"{g['away']}@{g['home']}")] = g
    lines, season_rec, by_week = [], [0, 0, 0], {}
    for w, picks in sorted(data.get("weeks", {}).items(), key=lambda x: int(x[0])):
        w = int(w)
        if w >= week:
            continue
        wr = [0, 0, 0]
        for p in picks:
            g = finals.get((w, p["game"]))
            if not g:
                continue
            side_home = p.get("side") == g["home"]
            margin = (g["hs"] - g["as"]) * (1 if side_home else -1)
            if p["bet"] == "spread":
                v = margin + p["line"]
            elif p["bet"] == "ml":
                v = margin
            else:  # total
                v = (g["hs"] + g["as"] - p["line"]) * (1 if p["side"] == "over" else -1)
            res = "W" if v > 0 else "L" if v < 0 else "P"
            p["result"] = res
            wr["WLP".index(res)] += 1
        by_week[w] = wr
        season_rec = [a + b for a, b in zip(season_rec, wr)]
    PICKS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    last = by_week.get(week - 1)
    if last:
        lines.append(f"Last week: **{last[0]}-{last[1]}{'-' + str(last[2]) if last[2] else ''}**")
    if any(season_rec):
        lines.append(f"Season: **{season_rec[0]}-{season_rec[1]}{'-' + str(season_rec[2]) if season_rec[2] else ''}**")
    return " · ".join(lines) or None


# -------------------------------------------------------------- render

def rest_days(team, g, all_games):
    prev = [x for x in all_games if team in (x["home"], x["away"]) and x["date"] < g["date"]]
    if not prev:
        return None, False
    last = max(prev, key=lambda x: x["date"])
    return (g["date"] - last["date"]).days, g["week"] - last["week"] > 1


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cur, season = espn.current_week()
    week = int(args[0]) if args else cur
    season = str(season or api.get_state().get("season"))
    print(f"Podcast prep — season {season}, week {week}")

    sched = load_schedule(week, season)
    upcoming = [g for g in sched[week] if not g["final"]]  # TNF already played drops out
    finals = [g for w in range(1, week) for g in sched[w] if g["final"]]
    all_games = [g for w in sched for g in sched[w]]

    with ThreadPoolExecutor(12) as ex:
        fo = list(ex.map(lambda g: espn.odds(g["id"], True), finals))
        uo = list(ex.map(lambda g: espn.odds(g["id"]), upcoming))
        us = list(ex.map(lambda g: espn.summary(g["id"]), upcoming))
    for g, o in zip(finals, fo):
        g["odds"] = o
    for g, o, s in zip(upcoming, uo, us):
        g["odds"], g["summary"] = o, s

    rec = team_records(finals)
    ratings = srs(finals)
    team_ids = {}
    for g in all_games:
        team_ids[g["home"]] = g["home_id"]
        team_ids[g["away"]] = g["away_id"]
    tstats = load_team_stats(team_ids, season)
    metric_ranks = {k: rank_map({t: s.get(k) for t, s in tstats.items()}, hb)
                    for k, _, hb, _ in TEAM_METRICS}
    ppg = {t: sum(r["pf"]) / len(r["pf"]) for t, r in rec.items() if r["pf"]}
    papg = {t: sum(r["pa"]) / len(r["pa"]) for t, r in rec.items() if r["pa"]}
    ppg_rank, papg_rank = rank_map(ppg), rank_map(papg, False)

    slr = load_sleeper(season, week)
    trending = {t["player_id"]: t["count"] for t in (api.get_trending("add", 48, 50) or [])}
    next_opp = {}
    for g in sched.get(week + 1, []):
        next_opp[g["home"]] = f"vs {g['away']}"
        next_opp[g["away"]] = f"@ {g['home']}"

    playing = {t for g in upcoming for t in (g["home"], g["away"])}
    byes = sorted(set(team_ids) - playing)

    out, data_games = [], []
    out.append(f"# Podcast prep — Week {week}, {season}\n")
    out.append(f"*Generated {datetime.now(ET):%a %b %-d, %-I:%M %p} ET · DraftKings lines via ESPN · "
               f"Byes: {', '.join(byes) or 'none'}*\n")
    record = grade_picks(sched, week)
    if record:
        out.append(f"**Our picks record** — {record}\n")

    # ---------- per-game analysis first (slate table is built from it)
    slate_rows, flags, sections = [], [], []
    for g in sorted(upcoming, key=lambda g: g["date"]):
        h, a = g["home"], g["away"]
        o = g.get("odds") or {}
        s = g.get("summary") or {}
        spread, total = o.get("spread"), o.get("total")
        mkt_margin = -spread if spread is not None else None
        p_mkt = devig(o.get("ml_home"), o.get("ml_away"))
        pred = s.get("predictor") or {}
        try:
            ph, pa_ = float(pred["homeTeam"]["gameProjection"]), float(pred["awayTeam"]["gameProjection"])
            p_fpi = ph / (ph + pa_)
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            p_fpi = None
        fpi_margin = SD * NormalDist().inv_cdf(min(max(p_fpi, 0.01), 0.99)) if p_fpi else None
        srs_margin = (ratings.get(h, 0) - ratings.get(a, 0) + (0 if g["neutral"] else HFA)) if ratings else None
        imp_h = imp_a = None
        if spread is not None and total is not None:
            imp_h, imp_a = total / 2 - spread / 2, total / 2 + spread / 2
        naive_total = None
        if h in ppg and a in ppg:
            naive_total = (ppg[h] + papg[a]) / 2 + (ppg[a] + papg[h]) / 2

        flag, verdict = "", ""
        if mkt_margin is not None and srs_margin is not None and fpi_margin is not None:
            e1, e2 = srs_margin - mkt_margin, fpi_margin - mkt_margin
            if e1 * e2 > 0 and min(abs(e1), abs(e2)) >= FLAG_EDGE:
                lean = h if e1 > 0 else a
                flag = f"🚩 both models lean **{lean}** (SRS {e1:+.1f}, FPI {e2:+.1f} vs market, home-margin pts)"
                flags.append((min(abs(e1), abs(e2)), f"{a} @ {h}", lean, e1, e2))
                verdict = flag
            elif max(abs(e1), abs(e2)) < FLAG_EDGE:
                verdict = "models agree with the market ✅"
            elif e1 * e2 > 0:
                verdict = (f"mild lean {h if e1 > 0 else a} (SRS {e1:+.1f}, FPI {e2:+.1f} vs market)"
                           " — below the flag bar")
            else:
                verdict = f"models split (SRS {e1:+.1f}, FPI {e2:+.1f} vs market) — no signal"
        fav = h if (spread or 0) < 0 else a
        fav_line = spread if fav == h else (-spread if spread is not None else None)
        open_fav = None
        if o.get("open_spread") is not None:
            open_fav = o["open_spread"] if fav == h else -o["open_spread"]
        kick = g["date"].astimezone(ET)
        move = ""
        if open_fav is not None and fav_line is not None and open_fav != fav_line:
            move = f" (opened {fmt_spread(fav, open_fav)})"
        tmove = f" (opened {o['open_total']:g})" if o.get("open_total") not in (None, total) else ""
        slate_rows.append(
            f"| {a} @ {h} | {kick:%a %-I:%M %p} | {fmt_spread(fav, fav_line)}{move} | "
            f"{total if total is not None else '—'}{tmove} | "
            f"{f'{h} {imp_h:.1f} / {a} {imp_a:.1f}' if imp_h else '—'} | "
            f"{f'{p_mkt:.0%}' if p_mkt else '—'} | {f'{p_fpi:.0%}' if p_fpi else '—'} | "
            f"{fmt_spread(h, round(-srs_margin * 2) / 2) if srs_margin is not None else '—'} | "
            f"{'🚩' if flag else ''} |")

        L = []
        weather = ""
        wx = (s.get("gameInfo") or {}).get("weather") or {}
        grass = ((s.get("gameInfo") or {}).get("venue") or {}).get("grass")
        if g["indoor"]:
            weather = "indoor"
        elif wx:
            weather = f"{wx.get('temperature')}°F, {wx.get('precipitation', 0)}% precip"
        L.append(f"## {a} @ {h} — {kick:%a %b %-d, %-I:%M %p} ET")
        L.append(f"*{g['venue']} · {'grass' if grass else 'turf'} · {weather or 'weather n/a'}"
                 f"{' · NEUTRAL SITE' if g['neutral'] else ''}"
                 f"{' · DIVISIONAL (' + espn.DIVISION_OF[h] + ')' if espn.DIVISION_OF.get(h) == espn.DIVISION_OF.get(a) else ''}*\n")
        L.append(f"**Line:** {fmt_spread(fav, fav_line)}{move} · O/U {total if total is not None else '—'}{tmove}"
                 + (f" · ML {h} {o['ml_home']:+g} / {a} {o['ml_away']:+g}" if o.get("ml_home") is not None else ""))
        if imp_h:
            L.append(f"**Implied totals:** {h} {imp_h:.1f} · {a} {imp_a:.1f}")
        chk = []
        if mkt_margin is not None:
            chk.append(f"market {h} {mkt_margin:+.1f}")
        if srs_margin is not None:
            chk.append(f"SRS {h} {srs_margin:+.1f}")
        if fpi_margin is not None:
            chk.append(f"FPI {h} {fpi_margin:+.1f}")
        win = []
        if p_mkt:
            win.append(f"market {h} {p_mkt:.0%}")
        if p_fpi:
            win.append(f"FPI {h} {p_fpi:.0%}")
        L.append(f"**Line check (home margin):** {' · '.join(chk)}" + (f" — {verdict}" if verdict else ""))
        if win:
            L.append(f"**Win prob:** {' · '.join(win)}")
        if naive_total is not None and total is not None:
            d = naive_total - total
            L.append(f"**Total check:** PF/PA model {naive_total:.1f} vs {total:g} "
                     f"({'over' if d > 0 else 'under'} lean {abs(d):.1f}{' — noise' if abs(d) < 3 else ''})")
        L.append("")

        # team comparison table
        def recs(t):
            r = rec.get(t)
            if not r:
                return {}
            fmt3 = lambda x: f"{x[0]}-{x[1]}" + (f"-{x[2]}" if x[2] else "")  # noqa: E731
            n = len(r["margin"])
            return {"su": fmt3(r["su"]), "ats": fmt3(r["ats"]), "ou": f"{r['ou'][0]}-{r['ou'][1]}" + (f"-{r['ou'][2]}" if r['ou'][2] else ""),
                    "fav": fmt3(r["fav"]), "dog": fmt3(r["dog"]),
                    "margin": f"{sum(r['margin']) / n:+.1f}" if n else "—",
                    "cover": f"{sum(r['cover']) / len(r['cover']):+.1f}" if r["cover"] else "—"}
        ra, rh = recs(a), recs(h)
        gr = {a: g["rec_away"], h: g["rec_home"]}
        rows = [
            ("Record (home / road)", lambda t, R: f"{R.get('su', '—')} ({gr[t].get('home', '—')} / {gr[t].get('road', '—')})"),
            ("ATS (as fav / as dog)", lambda t, R: f"{R.get('ats', '—')} ({R.get('fav', '—')} / {R.get('dog', '—')})"),
            ("Over/Under", lambda t, R: R.get("ou", "—")),
            ("Avg margin · avg cover", lambda t, R: f"{R.get('margin', '—')} · {R.get('cover', '—')}"),
            ("SRS rating", lambda t, R: f"{ratings[t]:+.1f} ({ordinal(rank_map(ratings)[t])})" if t in ratings else "—"),
            ("Points for / against", lambda t, R: (f"{ppg[t]:.1f} ({ordinal(ppg_rank[t])}) / {papg[t]:.1f} ({ordinal(papg_rank[t])})"
                                                   if t in ppg else "—")),
        ]
        for k, label, _, f in TEAM_METRICS:
            rows.append((label, lambda t, R, k=k, f=f: (f"{f.format(tstats[t][k])} ({ordinal(metric_ranks[k][t])})"
                                                         if tstats.get(t, {}).get(k) is not None and t in metric_ranks[k] else "—")))

        def spot(t):
            days, bye = rest_days(t, g, all_games)
            bits = [f"{days}d rest" if days is not None else "—"]
            if bye:
                bits.append("off bye")
            elif days is not None and days <= 5:
                bits.append("SHORT WEEK")
            if t in WEST and t == a and kick.hour == 13 and h not in WEST:
                bits.append("west coast @ 1pm ET")
            if t in next_opp:
                bits.append(f"next {next_opp[t]}")
            return ", ".join(bits)
        rows.append(("Spot", lambda t, R: spot(t)))
        L.append(f"| | **{a}** | **{h}** |\n|---|---|---|")
        for label, fn in rows:
            L.append(f"| {label} | {fn(a, ra)} | {fn(h, rh)} |")
        L.append("")
        for t in (a, h):
            log = (rec.get(t) or {}).get("log") or []
            if log:
                L.append(f"**{t} last 5:** " + " · ".join(reversed(log[-5:])))
        L.append("")

        # injuries
        for blk in s.get("injuries") or []:
            t = (blk.get("team") or {}).get("abbreviation")
            items = [i for i in blk.get("injuries") or [] if i.get("status") in ("Out", "Doubtful", "Questionable")]
            if not items:
                continue
            txt = ", ".join(f"{i['athlete']['displayName']} {((i['athlete'].get('position') or {}).get('abbreviation') or '')}"
                            f" ({i['status'][0]}{' — ' + (i.get('details') or {}).get('type', '') if (i.get('details') or {}).get('type') else ''})"
                            for i in items[:14])
            L.append(f"**{t} injuries:** {txt}")
        L.append("")

        # fantasy
        L.append("**Fantasy**\n")
        L.append("| Player | Proj PPR (half) | Tgt% L3 (szn) | Rush% L3 (szn) | Snap% L3 | Matchup |\n|---|---|---|---|---|---|")
        game_players = []
        for t in (a, h):
            opp = h if t == a else a
            ps = sorted((p for p in slr["proj"] if p["team"] == sl(t)), key=lambda p: -p["ppr"])
            keep = ([p for p in ps if p["pos"] == "QB"][:1] + [p for p in ps if p["pos"] == "RB"][:3]
                    + [p for p in ps if p["pos"] == "WR"][:4] + [p for p in ps if p["pos"] == "TE"][:2])
            for p in sorted(keep, key=lambda p: -p["ppr"]):
                if p["ppr"] < 3:
                    continue
                sh = p["share"] or {}
                l3, sz = sh.get("l3") or {}, sh.get("season") or {}
                rk = slr["fpa_rank"][p["pos"]].get(sl(opp))
                fp = (slr["fpa"].get(sl(opp)) or {}).get(p["pos"])
                mu = "—"
                if rk:
                    tag = "🟢" if rk <= 8 else "🔴" if rk >= 25 else ""
                    mu = f"{tag} {opp} allows {ordinal(rk)}-most to {p['pos']} ({fp:.1f})"
                trend = ""
                if l3 and sz and l3.get("g", 0) >= 2:
                    dt = l3["tgt"] - sz["tgt"]
                    dr = l3["rush"] - sz["rush"]
                    if dt >= 0.05 or dr >= 0.10:
                        trend = " ⬆️"
                    elif dt <= -0.05 or dr <= -0.10:
                        trend = " ⬇️"
                pct = lambda x: f"{x:.0%}" if x else "—"  # noqa: E731
                name = (f"{p['name']} ({p['pos']}, {t})" + (f" **{p['inj']}**" if p["inj"] else "")
                        + (" 📈" if p["pid"] in trending else "") + trend
                        + (f" *(missed {sh['missed_l3']} of last 3)*" if sh.get("missed_l3") else ""))
                L.append(f"| {name} | {p['ppr']:.1f} ({p['half']:.1f}) | "
                         f"{pct(l3.get('tgt'))} ({pct(sz.get('tgt'))}) | {pct(l3.get('rush'))} ({pct(sz.get('rush'))}) | "
                         f"{pct(l3.get('snap'))} | {mu} |")
                game_players.append({**{k: p[k] for k in ("pid", "name", "pos", "team", "ppr", "half", "inj")},
                                     "matchup_rank": rk, "share": p["share"], "trending": trending.get(p["pid"])})
        for t in (a, h):
            opp = h if t == a else a
            mine = slr["dst"].get(sl(t)) or {}
            if mine:
                L.append(f"\n*{t} DST:* {mine.get('sack', 0):.1f} sacks, {mine.get('int', 0) + mine.get('fum_rec', 0):.1f} takeaways, "
                         f"{mine.get('pts_allow', 0):.1f} pts allowed per game · {opp} offense: "
                         f"{tstats.get(opp, {}).get('passing.sacks') or 0:.0f} sacks taken, "
                         f"{tstats.get(opp, {}).get('miscellaneous.totalGiveaways') or 0:.0f} giveaways"
                         + (f", implied {imp_h if opp == h else imp_a:.1f}" if imp_h else ""))
        L.append("\n---\n")
        sections.append("\n".join(L))
        data_games.append({"game": f"{a}@{h}", "kickoff": kick.isoformat(), "odds": o,
                           "p_market": p_mkt, "p_fpi": p_fpi, "srs_margin": srs_margin,
                           "fpi_margin": fpi_margin, "naive_total": naive_total,
                           "implied": {h: imp_h, a: imp_a}, "flag": flag, "players": game_players})

    out.append("## Slate\n")
    out.append("| Game | Kick (ET) | Spread | Total | Implied | Mkt home% | FPI home% | SRS line | |\n"
               "|---|---|---|---|---|---|---|---|---|")
    out.extend(slate_rows)
    out.append("")
    if flags:
        out.append("### 🚩 Line checks (both models off the market)\n")
        for e, game, lean, e1, e2 in sorted(flags, reverse=True):
            out.append(f"- **{game}** → lean **{lean}** · SRS {e1:+.1f} / FPI {e2:+.1f} pts vs market")
        out.append("")
    imp = sorted(((v, t) for dg in data_games for t, v in dg["implied"].items() if v), reverse=True)
    if imp:
        out.append("### Implied team totals\n")
        out.append("Top: " + " · ".join(f"{t} {v:.1f}" for v, t in imp[:6]))
        out.append("\nBottom: " + " · ".join(f"{t} {v:.1f}" for v, t in imp[-6:][::-1]) + "\n")
    # softest matchups this week
    out.append("### Softest matchups this week (PPR allowed per game, rank of 32)\n")
    opp_of = {sl(g["home"]): sl(g["away"]) for g in upcoming} | {sl(g["away"]): sl(g["home"]) for g in upcoming}
    for pos in SKILL:
        cands = sorted(((slr["fpa_rank"][pos][d], d) for d in opp_of.values() if d in slr["fpa_rank"][pos]))[:4]
        out.append(f"- **{pos}:** " + " · ".join(
            f"vs {d} ({ordinal(r)}, {slr['fpa'][d][pos]:.1f}) → {[t for t, o in opp_of.items() if o == d][0]}" for r, d in cands))
    out.append("")
    risers = []
    for p in slr["proj"]:
        sh = p["share"] or {}
        l3, sz = sh.get("l3") or {}, sh.get("season") or {}
        if p["team"] in {sl(t) for t in playing} and p["ppr"] >= 3 and l3 and sz and l3["g"] >= 2 and sz["g"] > l3["g"]:
            dt, dr = l3["tgt"] - sz["tgt"], l3["rush"] - sz["rush"]
            if dt >= 0.06 or dr >= 0.12:
                risers.append((max(dt, dr / 2), p, dt, dr, l3))
    if risers:
        out.append("### Usage risers (last 3 vs season)\n")
        for _, p, dt, dr, l3 in sorted(risers, key=lambda x: -x[0])[:10]:
            bits = []
            if dt >= 0.06:
                bits.append(f"tgt share {l3['tgt']:.0%} ({dt:+.0%})")
            if dr >= 0.12:
                bits.append(f"carry share {l3['rush']:.0%} ({dr:+.0%})")
            out.append(f"- {p['name']} ({p['pos']}, {p['team']}) — {', '.join(bits)} · proj {p['ppr']:.1f} PPR")
        out.append("")
    tr = [p for p in slr["proj"] if p["pid"] in trending]
    if tr:
        out.append("### Trending adds (Sleeper, 48h) on this slate\n")
        out.append(" · ".join(f"{p['name']} ({p['pos']}, {p['team']}) +{trending[p['pid']]:,}"
                              for p in sorted(tr, key=lambda p: -trending[p["pid"]])[:12]) + "\n")
    out.append("---\n")
    out.extend(sections)
    out[-1] = out[-1].rstrip("-\n")
    out.append("\n*Method: SRS = opponent-adjusted margin (cap ±21, HFA 1.5, shrunk n/(n+3)); "
               "FPI margin = ESPN win% through a normal with SD 13.5; flag needs both ≥2 pts off the market "
               "in the same direction. Fantasy points re-scored under standard PPR/half rules. "
               "Matchup rank 1 = defense allowing the most fantasy points to that position.*\n")

    dest = ROOT / "reports" / season / "podcast" / f"week{week:02d}"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "podcast-prep.md").write_text("\n".join(out))
    (dest / "data.json").write_text(json.dumps({"week": week, "season": season, "games": data_games},
                                               indent=1, default=str))
    print(f"→ {dest / 'podcast-prep.md'}  ({len(upcoming)} games, {len(flags)} line flags)")


if __name__ == "__main__":
    main()
