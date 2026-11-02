#!/usr/bin/env python3
"""Podcast recap + waivers — the week that was, and who to grab for the next one.

The data layer for the show's recap segment (skill `podcast-prep`, §8). For the
week just played:

  RESULTS    final score vs the closing DraftKings line: who covered and by how
             much, over/under, how far the market missed; favorites/home/overs
             records for the week; our on-air picks graded.
  GAMES      per game: box (yards and yds/play, turnovers, 3rd down, sacks
             taken, red zone, possession), top fantasy lines (PPR), usage
             swings vs the player's season before this week, injuries.
  INJURIES   ESPN's per-game injury list, keeping entries dated at or after
             kickoff (in-game injuries and post-game updates — pregame
             inactives drop out), skill positions only. Each one carries the
             player's role before the injury and the teammate who absorbed it.
  WAIVERS    by position for next week: players rostered in ≤50% of Sleeper
             redraft leagues, with next week's projection re-scored PPR, this
             week's usage vs before, opponent rank vs the position, trending
             adds, and a mechanical FAAB tier from the CLAUDE.md ladder
             (A = inherited a workhorse backfield, 30-60%; B = starter-level
             role or projection, 15-25%; C = depth/speculative, 1-5%;
             DST streams 0-1%). The research layer confirms injury length
             before an A tier goes on air.

Uso: python3 scripts/podcast_recap.py [week]     (default: the week just played)
Salida: reports/<season>/podcast/weekNN/recap-prep.md (+ recap.json)
"""
import json
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import podcast_prep as pp  # noqa: E402
from sleeper import api, espn  # noqa: E402
from sleeper.scoring import score_stat_line  # noqa: E402

OWNED_MAX = 50          # "available in most leagues"
DEEP_MAX = 80           # above 50%, only a role change makes the list ("if he's free in your league")
WAIVER_N = {"QB": 8, "RB": 12, "WR": 12, "TE": 8, "DST": 8}   # a pool; the spoken recap ranks 5+ per position from it
MIN_PROJ = {"QB": 12, "RB": 5, "WR": 6, "TE": 4}
STARTER_RANK = {"QB": 12, "RB": 24, "WR": 24, "TE": 12}
# a player's role before the injury, big enough that someone inherits it
ROLE_KEY = {"QB": "snap", "RB": "touch", "WR": "tgt", "TE": "tgt"}
ROLE_MIN = {"QB": 0.70, "RB": 0.45, "WR": 0.18, "TE": 0.12}
OUT = {"Out", "IR", "PUP", "Suspension", "Doubtful"}
BLOWOUT = 17            # a usage jump in a game decided by this much may be garbage time, not a role
DST = {"sack": 1, "int": 2, "fum_rec": 2, "def_td": 6, "safe": 2, "blk_kick": 2}


def dst_points(st):
    pa = st.get("pts_allow")
    tier = (0 if pa is None else 10 if pa == 0 else 7 if pa < 7 else 4 if pa < 14 else 1 if pa < 21
            else 0 if pa < 28 else -1 if pa < 35 else -4)
    return score_stat_line(st, DST) + tier


def stat_line(pos, st):
    g = lambda k: int(st.get(k) or 0)  # noqa: E731
    rush = f"{g('rush_att')}-{g('rush_yd')}" + (f", {g('rush_td')} TD" if g("rush_td") else "")
    rec = f"{g('rec')}/{g('rec_tgt')}, {g('rec_yd')} yds" + (f", {g('rec_td')} TD" if g("rec_td") else "")
    if pos == "QB":
        s = f"{g('pass_cmp')}/{g('pass_att')}, {g('pass_yd')} yds, {g('pass_td')} TD, {g('pass_int')} INT"
        return s + (f" · por tierra {rush}" if g("rush_yd") >= 20 or g("rush_td") else "")
    if pos == "RB":
        return f"tierra {rush} · recepción {rec}" if g("rec_tgt") else f"tierra {rush}"
    return rec + (f" · tierra {rush}" if g("rush_att") >= 2 else "")


def pick_txt(p):
    if p["bet"] == "spread":
        return f"{p['side']} {p['line']:+g}"
    if p["bet"] == "total":
        return f"{'altas' if p['side'] == 'over' else 'bajas'} {p['line']:g}"
    return f"{p['side']} ML {p['line']:+g}"


def usage_by_week(season, week):
    """Per player per week: raw volume and team totals, so this week can be
    compared with the season BEFORE it (podcast_prep's shares include it)."""
    with ThreadPoolExecutor(6) as ex:
        futs = {w: ex.submit(api.get_week_stat_rows, season, w, ("QB", "RB", "WR", "TE"),
                             600 if w == week else api.DAY) for w in range(1, week + 1)}
    pl = defaultdict(dict)                                  # pid -> week -> row
    tm = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))  # team -> week -> totals
    meta = {}
    for w, f in futs.items():
        for r in f.result() or []:
            st, p = r.get("stats") or {}, r.get("player") or {}
            pos, team = p.get("position"), r.get("team")
            if pos not in pp.SKILL or not team or not st.get("gms_active"):
                continue
            pl[r["player_id"]][w] = {"st": st, "team": team, "opp": r.get("opponent"), "pos": pos}
            meta[r["player_id"]] = {"name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                                    "pos": pos}
            t = tm[team][w]
            t["tgt"] += st.get("rec_tgt") or 0
            t["rush"] += st.get("rush_att") or 0
            if pos == "RB":
                t["touch"] += (st.get("rush_att") or 0) + (st.get("rec") or 0)

    def share(pid, weeks):
        ws = [w for w in weeks if w in pl[pid] and (pl[pid][w]["st"].get("off_snp") or 0) > 0]
        if not ws:
            return None
        s = lambda k: sum(pl[pid][w]["st"].get(k) or 0 for w in ws)  # noqa: E731
        t = lambda k: sum(tm[pl[pid][w]["team"]][w][k] for w in ws)  # noqa: E731
        d = lambda a, b: a / b if b else 0  # noqa: E731
        rb = pl[pid][ws[-1]]["pos"] == "RB"
        return {"snap": d(s("off_snp"), s("tm_off_snp")), "tgt": d(s("rec_tgt"), t("tgt")),
                "rush": d(s("rush_att"), t("rush")),
                "touch": d(s("rush_att") + s("rec"), t("touch")) if rb else None, "g": len(ws)}

    return pl, meta, share


def team_box(summary):
    out = {}
    for t in (summary.get("boxscore") or {}).get("teams") or []:
        s = {x["name"]: x.get("displayValue") for x in t.get("statistics") or []}
        out[t["team"]["abbreviation"]] = {
            "yds": s.get("totalYards"), "ypp": s.get("yardsPerPlay"), "to": s.get("turnovers"),
            "third": s.get("thirdDownEff"), "sacks": (s.get("sacksYardsLost") or "").split("-")[0] or None,
            "rz": s.get("redZoneAttempts"), "top": s.get("possessionTime"),
            "ypa": s.get("yardsPerPass"), "ypc": s.get("yardsPerRushAttempt")}
    return out


def name_key(name):
    parts = re.sub(r"[^a-z ]", "", (name or "").lower().replace("-", " ")).split()
    return " ".join(p for p in parts if p not in ("jr", "sr", "ii", "iii", "iv", "v"))


def game_injuries(summary, kickoff, resolve):
    out = []
    for t in summary.get("injuries") or []:
        team = t["team"]["abbreviation"]
        for i in t.get("injuries") or []:
            a = i.get("athlete") or {}
            pos = (a.get("position") or {}).get("abbreviation")
            if pos not in pp.SKILL:
                continue
            try:
                when = datetime.fromisoformat(i["date"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            if when < kickoff:   # pregame inactives / last week's list
                continue
            d = i.get("details") or {}
            out.append({"team": team, "name": a.get("displayName"), "pos": pos,
                        "pid": resolve(a.get("id"), a.get("displayName"), team), "status": i.get("status"),
                        "body": pp.body_es(d.get("type") or ""), "side": d.get("side"),
                        "detail": d.get("detail"), "date": i.get("date")})
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cur, season = espn.current_week()
    season = str(season or api.get_state().get("season"))
    if args:
        week = int(args[0])
    else:
        week = cur
        if not any(g["final"] for g in pp.parse_events(espn.scoreboard(cur, season), cur)):
            week = cur - 1
    print(f"Recap del podcast — temporada {season}, semana {week}")

    sched = pp.load_schedule(week, season)
    games = sorted(sched[week], key=lambda g: g["date"])
    finals = [g for g in games if g["final"]]
    pending = [g for g in games if not g["final"]]
    nxt = sched.get(week + 1, [])
    with ThreadPoolExecutor(12) as ex:
        fo = list(ex.map(lambda g: espn.odds(g["id"], True), finals))
        fs = list(ex.map(lambda g: espn.summary(g["id"]), finals))
        no = list(ex.map(lambda g: espn.odds(g["id"]), nxt))
    for g, o, s in zip(finals, fo, fs):
        g["odds"], g["summary"] = o, s

    players = api.get_players() or {}
    # Sleeper carries espn_id for only ~1 in 4 skill players; name + team covers the rest
    by_espn = {str(p["espn_id"]): pid for pid, p in players.items() if p.get("espn_id")}
    by_name = {(name_key(p.get("full_name")), p.get("team")): pid for pid, p in players.items()
               if p.get("team") and p.get("position") in pp.SKILL}

    def resolve(espn_id, name, team):
        return by_espn.get(str(espn_id)) or by_name.get((name_key(name), pp.sl(team)))

    pl, meta, share = usage_by_week(season, week)
    before = list(range(1, week))
    slr = pp.load_sleeper(season, week + 1)           # next week's projections + matchup ranks
    own = api.get_ownership(season, week + 1) or api.get_ownership(season, week) or {}
    trending = {t["player_id"]: t["count"] for t in (api.get_trending("add", 24, 100) or [])}
    record = (pp.grade_picks(sched, week + 1) or "").replace("Semana pasada", f"Semana {week}") or None
    picks = (json.loads(pp.PICKS.read_text()).get("weeks") or {}).get(str(week)) or [] if pp.PICKS.exists() else []

    # ---------- results
    rows, summ = [], {"fav": [0, 0, 0], "home": [0, 0, 0], "ou": [0, 0, 0]}
    for g in finals:
        h, a, o = g["home"], g["away"], g.get("odds") or {}
        sp, tot = o.get("spread"), o.get("total")
        margin = g["hs"] - g["as"]
        r = {"game": f"{a}@{h}", "away": a, "home": h, "as": g["as"], "hs": g["hs"],
             "winner": h if margin > 0 else a if margin < 0 else None, "spread": sp, "total": tot}
        if sp is not None:
            fav = h if sp < 0 else a if sp > 0 else None
            cover = margin + sp                       # home perspective: >0 home covered
            r["line_txt"] = f"{fav} -{abs(sp):g}" if fav else "PK"
            r["ats"] = h if cover > 0 else a if cover < 0 else "push"
            r["cover_by"] = abs(cover)
            r["miss"] = cover                          # how far the market missed, home view
            if fav:
                fav_cov = (cover > 0) == (fav == h) if cover else None
                summ["fav"][0 if fav_cov else 1 if fav_cov is False else 2] += 1
            summ["home"][0 if cover > 0 else 1 if cover < 0 else 2] += 1
        if tot is not None:
            pts = g["hs"] + g["as"]
            r["ou"] = "altas" if pts > tot else "bajas" if pts < tot else "push"
            summ["ou"][0 if pts > tot else 1 if pts < tot else 2] += 1
        r["picks"] = [p for p in picks if p["game"] == r["game"]]
        rows.append(r)
        g["row"] = r

    # ---------- per game: box, fantasy, usage swings, injuries
    injuries = []
    for g in finals:
        h, a = g["home"], g["away"]
        teams = {pp.sl(h), pp.sl(a)}
        wk = {pid: d[week] for pid, d in pl.items() if week in d and d[week]["team"] in teams}
        top = sorted(((score_stat_line(x["st"], pp.PPR), pid, x) for pid, x in wk.items()),
                     key=lambda t: t[0], reverse=True)[:5]
        g["top"] = [{"pid": pid, "name": meta[pid]["name"], "pos": x["pos"], "team": x["team"],
                     "ppr": round(pts, 1), "line": stat_line(x["pos"], x["st"])} for pts, pid, x in top]
        swings = []
        for pid, x in wk.items():
            now, pre = share(pid, [week]), share(pid, before)
            if not now:
                continue
            pos = x["pos"]
            pre = pre or {"snap": 0, "tgt": 0, "touch": 0 if pos == "RB" else None, "g": 0}
            notes = []
            if pos == "RB" and now["touch"] - (pre["touch"] or 0) >= 0.20 and now["touch"] >= 0.35:
                notes.append(("touch", now["touch"], pre["touch"]))
            tg = x["st"].get("rec_tgt") or 0
            # a share of a tiny pie is noise (wk 8: TB completed zero passes, one target = 33%)
            if pos in ("WR", "TE") and now["tgt"] - pre["tgt"] >= 0.10 and now["tgt"] >= 0.15 and tg >= 4:
                notes.append(("tgt", now["tgt"], pre["tgt"]))
            if now["snap"] - pre["snap"] >= 0.25 and now["snap"] >= 0.50:
                notes.append(("snap", now["snap"], pre["snap"]))
            if pre["g"] >= 2 and pre["snap"] >= 0.60 and now["snap"] <= pre["snap"] * 0.5:
                notes.append(("drop", now["snap"], pre["snap"]))
            if notes:
                swings.append({"pid": pid, "name": meta[pid]["name"], "pos": pos, "team": x["team"],
                               "notes": [{"k": k, "now": n, "pre": p} for k, n, p in notes],
                               "first": pre["g"] == 0})
        g["blowout"] = abs(g["hs"] - g["as"]) if abs(g["hs"] - g["as"]) >= BLOWOUT else None
        g["swings"] = sorted(swings, key=lambda s: -max(n["now"] - (n["pre"] or 0) if n["k"] != "drop"
                                                           else n["pre"] - n["now"] for n in s["notes"]))
        kick = g["date"]
        inj = game_injuries(g["summary"], kick, resolve)
        for i in inj:
            pid, pos = i["pid"], i["pos"]
            pre = share(pid, before) if pid else None
            key = ROLE_KEY[pos]
            i["role"] = pre.get(key) if pre else None
            i["key"] = key
            i["played"] = bool(pid and week in pl.get(pid, {}))
            i["now"] = (share(pid, [week]) or {}).get("snap") if pid else None
            heir = None
            # someone only inherits a role the injured player actually lost: out, or a real snap drop
            lost = i["status"] in OUT or not i["played"] or (i["now"] or 0) < 0.6 * ((pre or {}).get("snap") or 0)
            if i["role"] is not None and i["role"] >= ROLE_MIN[pos] and lost:
                hurt = {x["pid"] for x in inj if x["status"] in OUT and x["pid"]}
                mates = [(q, share(q, [week])) for q, d in pl.items()
                         if q != pid and week in d and d[week]["team"] == pp.sl(i["team"]) and d[week]["pos"] == pos
                         and q not in hurt and (players.get(q) or {}).get("injury_status") not in OUT]
                mates = [(q, s) for q, s in mates if s]
                if mates:
                    q, s = max(mates, key=lambda m: (m[1].get(key) or 0, m[1]["snap"]))
                if mates and (s.get(key) or 0) >= ROLE_MIN[pos] * 0.6:
                    heir = {"pid": q, "name": meta[q]["name"], "now": s.get(key), "snap": s["snap"],
                            "owned": (own.get(q) or {}).get("owned", 0)}
            i["heir"] = heir
            i["game"] = f"{a}@{h}"
        g["injuries"] = inj
        injuries += inj

    # latest Sleeper news line for injured players who had a real role
    key_inj = [i for i in injuries if i["pid"] and i["role"] is not None and i["role"] >= ROLE_MIN[i["pos"]]]
    news = api.get_player_news([i["pid"] for i in key_inj], 2) if key_inj else {}
    for i in key_inj:
        items = news.get(i["pid"]) or []
        if items:
            m = items[0].get("metadata") or {}
            i["news"] = m.get("title")

    # ---------- waivers for next week
    # Sleeper's projections lag role changes by days (wk 8: Mike Washington Jr. took 81% of the LV
    # backfield and was projected 5.2), so each candidate also gets a usage-implied projection:
    # this week's share × the team's per-game RB fantasy points (RB) or targets × league PPR/target.
    proj = {p["pid"]: p for p in slr["proj"]}
    team_rb, team_tg, ppt = defaultdict(lambda: [0.0, set()]), defaultdict(lambda: [0.0, set()]), defaultdict(lambda: [0.0, 0])
    for pid, d in pl.items():
        for w, x in d.items():
            st, pts = x["st"], score_stat_line(x["st"], pp.PPR)
            team_tg[x["team"]][0] += st.get("rec_tgt") or 0
            team_tg[x["team"]][1].add(w)
            if x["pos"] == "RB":
                team_rb[x["team"]][0] += pts
                team_rb[x["team"]][1].add(w)
            elif x["pos"] in ("WR", "TE"):
                ppt[x["pos"]][0] += pts
                ppt[x["pos"]][1] += st.get("rec_tgt") or 0

    def usage_proj(pid, pos, team):
        now = share(pid, [week])
        if not now or pos == "QB":
            return None
        if pos == "RB":
            t = team_rb[team]
            return now["touch"] * t[0] / len(t[1]) if t[1] else None
        t, q = team_tg[team], ppt[pos]
        x = pl.get(pid, {}).get(week)
        tg = (x["st"].get("rec_tgt") or 0) if x else 0
        team_wk = sum((pl[o][week]["st"].get("rec_tgt") or 0) for o in pl if week in pl[o] and pl[o][week]["team"] == team)
        sh = now["tgt"]
        if tg < 4 or team_wk < 15:          # too few targets to read a share; fall back to the season
            sh = (share(pid, before) or {}).get("tgt") or sh
        return sh * t[0] / len(t[1]) * q[0] / q[1] if t[1] and q[1] else None

    starter_bar = {}
    for pos in pp.SKILL:
        ordered = sorted((p["ppr"] for p in slr["proj"] if p["pos"] == pos), reverse=True)
        starter_bar[pos] = ordered[STARTER_RANK[pos] - 1] if len(ordered) >= STARTER_RANK[pos] else 0
    sev = {"Out": 0, "IR": 0, "Doubtful": 1, "Questionable": 2}
    heirs = {}
    for i in sorted(key_inj, key=lambda i: (sev.get(i["status"], 3), -(i["role"] or 0))):
        if i["heir"]:
            heirs.setdefault(i["heir"]["pid"], i)
    next_opp = {}
    for g in nxt:
        next_opp[pp.sl(g["home"])] = ("vs", pp.sl(g["away"]))
        next_opp[pp.sl(g["away"])] = ("@", pp.sl(g["home"]))
    played = {pp.sl(t) for g in finals for t in (g["home"], g["away"])}
    monday = {pp.sl(t) for g in pending for t in (g["home"], g["away"])}

    blowout_of = {pp.sl(t): g["blowout"] for g in finals if g.get("blowout") for t in (g["home"], g["away"])}

    def week_label(team):
        return "juega el lunes" if team in monday else "no jugó" if team in played else "descansó"

    def candidate(pid, pos, team):
        p = proj.get(pid)
        o = own.get(pid) or {}
        now, pre = share(pid, [week]), share(pid, before)
        x = pl.get(pid, {}).get(week)
        inh = heirs.get(pid)
        sp = round(p["ppr"], 1) if p else None
        up = usage_proj(pid, pos, team)
        up = round(up, 1) if up is not None else None
        est = (sp + up) / 2 if sp is not None and up is not None else sp if sp is not None else up
        tier, why = "C", []
        if inh:
            what = {"touch": "los toques del backfield", "tgt": "los targets", "snap": "los snaps"}[inh["key"]]
            why.append(f"hereda el rol de {inh['name']} ({pp.STATUS_ES.get(inh['status'], inh['status']).lower()}, "
                       f"{inh['body'].lower() or 'lesión'}; tenía {inh['role']:.0%} de {what})")
            tier = "A" if pos == "RB" and inh["role"] >= 0.55 else "B"
        if tier == "C" and est is not None and est >= starter_bar[pos]:
            tier = "B"
        tg = (x["st"].get("rec_tgt") or 0) if x else 0
        if now and pre and pos in ("RB", "WR", "TE"):
            k = "touch" if pos == "RB" else "tgt"
            if (now[k] or 0) - (pre[k] or 0) >= 0.10 and (k == "touch" or tg >= 4):
                why.append(f"uso al alza: {now[k]:.0%} de {'los toques del backfield' if k == 'touch' else 'los targets'} "
                           f"(antes {pre[k] or 0:.0%})")
        bl = blowout_of.get(team)
        if bl and now and pre and any((now[k] or 0) - (pre[k] or 0) >= 0.10 for k in ("touch", "tgt") if now.get(k) is not None):
            why.append(f"ojo: su partido se decidió por {bl} — confirmar que no fue uso de paliza")
        if sp is not None and up is not None and up - sp >= 3:
            why.append(f"la proyección de Sleeper ({sp:.1f}) todavía no refleja el uso ({up:.1f})")
        opp = next_opp.get(team)
        fr = (slr["fpa_rank"].get(pos) or {}).get(opp[1]) if opp else None
        return {"pid": pid, "name": (p or {}).get("name") or meta.get(pid, {}).get("name"), "pos": pos, "team": team,
                "owned": o.get("owned", 0), "started": o.get("started", 0), "trend": trending.get(pid, 0),
                "pts_wk": round(score_stat_line(x["st"], pp.PPR), 1) if x else None,
                "line_wk": stat_line(pos, x["st"]) if x else week_label(team),
                "now": now, "pre": pre, "proj": sp, "uproj": up, "est": round(est, 1) if est is not None else None,
                "opp": f"{opp[0]} {opp[1]}" if opp else "descansa", "opp_rank": fr,
                "inj": (p or {}).get("inj") or (players.get(pid) or {}).get("injury_status"),
                "tier": tier, "faab": {"A": "30-60%", "B": "15-25%", "C": "1-5%"}[tier],
                "heir": bool(inh), "why": why}

    team_of = {p["pid"]: p["team"] for p in slr["proj"]}
    team_of.update({pid: d[week]["team"] for pid, d in pl.items() if week in d})
    pos_of = {p["pid"]: p["pos"] for p in slr["proj"]}
    pos_of.update({pid: m["pos"] for pid, m in meta.items()})
    waivers = {pos: [] for pos in pp.SKILL}
    for pid, team in team_of.items():
        pos = pos_of.get(pid)
        owned = (own.get(pid) or {}).get("owned", 0)
        if pos not in pp.SKILL or owned > DEEP_MAX:
            continue
        inj = (proj.get(pid) or {}).get("inj") or (players.get(pid) or {}).get("injury_status")
        if inj in OUT or (team not in next_opp and pid not in heirs):
            continue
        c = candidate(pid, pos, team)
        rising = c["heir"] or any(w.startswith("uso al alza") for w in c["why"])
        if owned > OWNED_MAX and not rising:
            continue
        c["deep"] = owned > OWNED_MAX
        if c["heir"] or (c["est"] or 0) >= MIN_PROJ[pos]:
            waivers[pos].append(c)
    for pos in pp.SKILL:
        waivers[pos].sort(key=lambda c: ("ABC".index(c["tier"]), -(c["est"] or 0)))
        waivers[pos] = waivers[pos][:WAIVER_N[pos]]
    # the platform's add list: every big number gets a WHY from the research layer before it's a call
    hot = []
    for t in sorted(trending.items(), key=lambda kv: -kv[1])[:12]:
        pid, n = t
        pos, team = pos_of.get(pid) or (players.get(pid) or {}).get("position"), team_of.get(pid) or (players.get(pid) or {}).get("team")
        if pos not in pp.SKILL:
            continue
        hot.append({"pid": pid, "name": (players.get(pid) or {}).get("full_name") or meta.get(pid, {}).get("name"),
                    "pos": pos, "team": team, "adds": n, "owned": (own.get(pid) or {}).get("owned", 0),
                    "pts_wk": round(score_stat_line(pl[pid][week]["st"], pp.PPR), 1) if week in pl.get(pid, {}) else None,
                    "line_wk": stat_line(pos, pl[pid][week]["st"]) if week in pl.get(pid, {}) else week_label(team),
                    "inj": (players.get(pid) or {}).get("injury_status")})
    # DST streamers: next week's projection (standard scoring) vs the opponent's implied total
    implied = {}
    for g, o in zip(nxt, no):
        if o and o.get("spread") is not None and o.get("total"):
            implied[pp.sl(g["home"])] = (o["total"] - o["spread"]) / 2
            implied[pp.sl(g["away"])] = (o["total"] + o["spread"]) / 2
    dst = []
    for r in api.get_week_projections(season, week + 1, ("DEF",)) or []:
        t = r.get("team") or r["player_id"]
        if (own.get(t) or {}).get("owned", 0) > OWNED_MAX or t not in next_opp:
            continue
        st = r.get("stats") or {}
        side, opp = next_opp[t]
        dst.append({"pid": t, "name": t, "pos": "DST", "team": t, "owned": (own.get(t) or {}).get("owned", 0),
                    "proj": round(dst_points(st), 1), "opp": f"{side} {opp}", "opp_implied": implied.get(opp),
                    "sacks": st.get("sack"), "takeaways": (st.get("int") or 0) + (st.get("fum_rec") or 0),
                    "tier": "DST", "faab": "0-1%", "why": []})
    dst.sort(key=lambda d: (-(d["proj"] or 0), d["opp_implied"] or 99))
    waivers["DST"] = dst[:WAIVER_N["DST"]]

    # ---------- buy / sell / watch (user's week-8 notes: role losers, streaks, flops, QB changes, schedule)
    later = {}
    with ThreadPoolExecutor(4) as ex:
        futs = {w: ex.submit(espn.scoreboard, w, season) for w in range(week + 2, week + 5)}
    for w, f in futs.items():
        later[w] = pp.parse_events(f.result(), w)
    upcoming = defaultdict(list)                       # team -> next 4 opponents
    for w, games_w in [(week + 1, nxt)] + sorted(later.items()):
        for g in games_w:
            upcoming[pp.sl(g["home"])].append(pp.sl(g["away"]))
            upcoming[pp.sl(g["away"])].append(pp.sl(g["home"]))

    def sched(team, pos):
        rk = [(slr["fpa_rank"].get(pos) or {}).get(o) for o in upcoming.get(team, [])[:4]]   # aligned with opps
        ok = [r for r in rk if r]
        return {"opps": upcoming.get(team, [])[:4], "ranks": rk, "avg": sum(ok) / len(ok) if ok else None, "pos": pos}

    def pts(st):
        return score_stat_line(st, pp.PPR)

    def scrim(st):
        return (st.get("rush_yd") or 0) + (st.get("rec_yd") or 0)

    STREAKS = [("RB", "100+ yardas totales", lambda st: scrim(st) >= 100),
               ("RB", "17+ acarreos", lambda st: (st.get("rush_att") or 0) >= 17),
               ("WR", "8+ targets", lambda st: (st.get("rec_tgt") or 0) >= 8),
               ("TE", "7+ targets", lambda st: (st.get("rec_tgt") or 0) >= 7),
               ("QB", "20+ puntos", lambda st: pts(st) >= 20)]
    streaks = []
    for pid, d in pl.items():
        if week not in d:
            continue
        pos = d[week]["pos"]
        for spos, label, test in STREAKS:
            if pos != spos:
                continue
            n = 0
            for w in sorted(d, reverse=True):          # games he played, newest first
                if not test(d[w]["st"]):
                    break
                n += 1
            if n >= 3:
                prev = next((x for x in streaks if x["pid"] == pid), None)
                if prev:
                    prev["what"] += f" y {n} con {label}" if n != prev["n"] else f" y {label}"
                    continue
                streaks.append({"pid": pid, "name": meta[pid]["name"], "pos": pos, "team": d[week]["team"],
                                "what": label, "n": n, "owned": (own.get(pid) or {}).get("owned", 0),
                                "sched": sched(d[week]["team"], pos)})
    streaks.sort(key=lambda x: (-x["n"], x["pos"]))

    losers, flops, qbs = [], [], []
    avg_before = {}
    for pid, d in pl.items():
        games_b = [d[w]["st"] for w in before if w in d]
        if games_b:
            avg_before[pid] = sum(pts(st) for st in games_b) / len(games_b)
    bar = {}
    for pos in pp.SKILL:
        vals = sorted((v for pid, v in avg_before.items() if meta[pid]["pos"] == pos and len([w for w in before if w in pl[pid]]) >= 3),
                      reverse=True)
        bar[pos] = vals[STARTER_RANK[pos] - 1] if len(vals) >= STARTER_RANK[pos] else 99
    for pid, d in pl.items():
        if week not in d:
            continue
        x, pos, team = d[week], d[week]["pos"], d[week]["team"]
        now, pre = share(pid, [week]), share(pid, before)
        if not now or not pre or pre["g"] < 2:
            continue
        hurt = any(i["pid"] == pid for i in injuries)
        # lost the role without an injury: the Jeanty case (2 carries, a rookie got 25)
        if not hurt and pos == "RB" and (pre["touch"] or 0) >= 0.45 and (now["touch"] or 0) <= (pre["touch"] or 0) - 0.25:
            losers.append({"pid": pid, "name": meta[pid]["name"], "pos": pos, "team": team, "k": "touch",
                           "now": now["touch"], "pre": pre["touch"], "snap": now["snap"], "line": stat_line(pos, x["st"])})
        if not hurt and pos in ("WR", "TE") and pre["tgt"] >= 0.15 and now["tgt"] <= 0.05 and now["snap"] >= 0.5:
            losers.append({"pid": pid, "name": meta[pid]["name"], "pos": pos, "team": team, "k": "tgt",
                           "now": now["tgt"], "pre": pre["tgt"], "snap": now["snap"], "line": stat_line(pos, x["st"])})
        # a starter-level player who scored under half his average: buy low if the usage held
        avg = avg_before.get(pid)
        if avg and avg >= bar[pos] and pts(x["st"]) < 0.5 * avg and not hurt:
            k = {"RB": "touch", "QB": "snap"}.get(pos, "tgt")
            held = (now.get(k) or 0) >= 0.85 * (pre.get(k) or 0)
            flops.append({"pid": pid, "name": meta[pid]["name"], "pos": pos, "team": team, "pts": round(pts(x["st"]), 1),
                          "avg": round(avg, 1), "k": k, "now": now.get(k), "pre": pre.get(k), "held": held,
                          "line": stat_line(pos, x["st"]), "owned": (own.get(pid) or {}).get("owned", 0),
                          "sched": sched(team, pos)})
    for x in losers:
        x["blowout"] = blowout_of.get(x["team"])
    flops.sort(key=lambda f: -(f["avg"] - f["pts"]))
    # QB changes: anyone but the team's usual starter taking snaps (benching, injury, or mop-up)
    for g in finals:
        for t in (g["home"], g["away"]):
            st_t = pp.sl(t)
            qb = [(pid, d[week]) for pid, d in pl.items() if week in d and d[week]["team"] == st_t and d[week]["pos"] == "QB"]
            if len(qb) < 2:
                continue
            starter = max(qb, key=lambda q: (share(q[0], before) or {}).get("snap") or 0)[0]
            for pid, x in qb:
                sn = (share(pid, [week]) or {}).get("snap") or 0
                # the season starter, anyone who played the whole game, and kneel-down cameos aren't news
                if pid == starter or sn >= 0.9 or (sn < 0.10 and (x["st"].get("pass_att") or 0) < 2):
                    continue
                margin = abs(g["hs"] - g["as"])
                qbs.append({"pid": pid, "name": meta[pid]["name"], "team": st_t, "starter": meta[starter]["name"],
                            "snap": sn, "line": stat_line("QB", x["st"]), "owned": (own.get(pid) or {}).get("owned", 0),
                            "why": "relevo por lesión" if any(i["pid"] == starter and i["status"] in OUT for i in injuries)
                            else f"paliza de {margin}: puede ser solo relevo" if margin >= BLOWOUT else "entró con el partido en juego"})
    # a hurt QB drags his receivers: show their line with the backup in
    seen_qb_team = set()
    for i in sorted(key_inj, key=lambda i: (sev.get(i["status"], 3), -(i["role"] or 0))):
        lost = i["status"] in OUT or not i["played"] or (i["now"] or 0) < 0.6 * (i["role"] or 0)
        if i["pos"] == "QB" and lost and i["team"] not in seen_qb_team:
            seen_qb_team.add(i["team"])
            mates = sorted(((q, d[week]) for q, d in pl.items() if week in d and d[week]["team"] == pp.sl(i["team"])
                            and d[week]["pos"] in ("WR", "TE", "RB")), key=lambda m: -(m[1]["st"].get("rec_tgt") or 0))[:3]
            i["mates"] = [{"pid": q, "name": meta[q]["name"], "pos": x["pos"], "line": stat_line(x["pos"], x["st"])}
                          for q, x in mates]
    for pos in pp.SKILL:
        for c in waivers.get(pos, []):
            c["sched"] = sched(c["team"], pos)
    watch = {"streaks": streaks, "losers": losers, "flops": flops[:10], "qbs": qbs}

    # ---------- render
    pct = lambda x: f"{x:.0%}" if x is not None else "—"  # noqa: E731
    rec_txt = lambda r: f"{r[0]}-{r[1]}" + (f"-{r[2]}" if r[2] else "")  # noqa: E731
    now_mx = datetime.now(pp.MX)
    out = [f"# Recap del podcast — Semana {week}, {season}\n"]
    pend_txt = ", ".join(f"{g['away']} @ {g['home']} ({pp.fecha(g['date'].astimezone(pp.MX))} "
                         f"{pp.hora(g['date'].astimezone(pp.MX))})" for g in pending)
    out.append(f"*Generado {pp.fecha(now_mx)}, {pp.hora(now_mx)} CDMX · {len(finals)} partidos terminados"
               + (f" · pendientes: {pend_txt} (vuelve a correr después)" if pending else "") + "*\n")
    if record:
        out.append(f"**Nuestro récord de picks** — {record}\n")
    if picks:
        for p in picks:
            res = {"W": "✅ ganado", "L": "❌ perdido", "P": "➖ empate"}.get(p.get("result"), "⏳ pendiente")
            out.append(f"- {p['game']}: {pick_txt(p)} {'★' * p.get('conf', 1)} → {res}")
        out.append("")

    out.append("## Resultados\n")
    out.append("| Partido | Final | Línea de cierre | Contra la línea | Total | Altas/bajas |\n|---|---|---|---|---|---|")
    for r in rows:
        ats = ("empate" if r.get("ats") == "push" else f"{r['ats']} por {r['cover_by']:g}") if r.get("ats") else "—"
        out.append(f"| {r['away']} @ {r['home']} | {r['away']} {r['as']} - {r['hs']} {r['home']} | {r.get('line_txt', '—')} | "
                   f"{ats} | {r['as'] + r['hs']} ({r['total']:g}) | {r.get('ou', '—')} |"
                   if r["total"] is not None else
                   f"| {r['away']} @ {r['home']} | {r['away']} {r['as']} - {r['hs']} {r['home']} | {r.get('line_txt', '—')} | {ats} | {r['as'] + r['hs']} | — |")
    out.append("")
    out.append("## La semana en números\n")
    out.append(f"- Favoritos contra la línea: **{rec_txt(summ['fav'])}** · locales: **{rec_txt(summ['home'])}** · "
               f"altas/bajas: **{rec_txt(summ['ou'])}**")
    misses = sorted((r for r in rows if r.get("miss") is not None), key=lambda r: -abs(r["miss"]))[:3]
    if misses:
        out.append("- Donde más falló el mercado: " + "; ".join(
            f"{r['away']} @ {r['home']} ({r['ats']} cubrió por {r['cover_by']:g})" for r in misses))
    out.append("")

    out.append("## Lesiones que mueven el fantasy\n")
    big = [i for i in injuries if i["role"] is not None and i["role"] >= ROLE_MIN[i["pos"]]]
    if big:
        out.append("| Jugador | Lesión | Estatus | Rol antes | Jugó (snaps) | Quién lo absorbió |\n|---|---|---|---|---|---|")
        for i in sorted(big, key=lambda i: -(i["role"] or 0)):
            what = {"touch": "toques backfield", "tgt": "targets", "snap": "snaps"}[i["key"]]
            heir = (f"{i['heir']['name']} ({pct(i['heir']['now'])} de {what}, {i['heir']['owned']:.0f}% en ligas)"
                    if i["heir"] else "—")
            out.append(f"| {i['name']} ({i['pos']}, {i['team']}) | {i['body'] or '—'} | "
                       f"{pp.STATUS_ES.get(i['status'], i['status'])} | {pct(i['role'])} de {what} | "
                       f"{pct(i['now'])} | {heir} |")
            if i.get("news"):
                out.append(f"|  ↳ *{i['news']}* | | | | | |")
    else:
        out.append("_Sin lesiones de titulares registradas durante los partidos._")
    other = [i for i in injuries if i not in big]
    if other:
        out.append("\nOtras: " + "; ".join(f"{i['name']} ({i['pos']}, {i['team']}, "
                                           f"{pp.STATUS_ES.get(i['status'], i['status']).lower()})" for i in other))
    out.append("")

    out.append("## Partido por partido\n")
    for g in finals:
        r, h, a = g["row"], g["home"], g["away"]
        out.append(f"### {a} @ {h}: {a} {g['as']}, {h} {g['hs']}\n")
        if r.get("line_txt"):
            ats = "empate contra la línea" if r["ats"] == "push" else f"{r['ats']} cubrió por {r['cover_by']:g}"
            out.append(f"- **La línea:** cerró {r['line_txt']}, total {r['total']:g} → {ats}; "
                       f"{r['as'] + r['hs']} puntos ({r.get('ou', '—')})")
        for p in r["picks"]:
            res = {"W": "ganado", "L": "perdido", "P": "empate"}.get(p.get("result"), "pendiente")
            out.append(f"- **Nuestro pick:** {pick_txt(p)} → {res}")
        box = team_box(g["summary"])
        for t in (a, h):
            b = box.get(t)
            if b:
                out.append(f"- **{t}:** {b['yds']} yds ({b['ypp']} por jugada; {b['ypa']} por pase, {b['ypc']} por acarreo) · "
                           f"balones perdidos {b['to']} · 3ª {b['third']} · capturas recibidas {b['sacks']} · "
                           f"zona roja {b['rz']} · posesión {b['top']}")
        g["box"] = box
        if g["top"]:
            out.append("- **Fantasy (PPR):** " + "; ".join(f"{p['name']} ({p['pos']}, {p['team']}) {p['ppr']:.1f} — {p['line']}"
                                                         for p in g["top"]))
        if g["swings"]:
            lab = {"touch": "de los toques del backfield", "tgt": "de los targets", "snap": "de los snaps"}
            bits = []
            for s in g["swings"][:5]:
                parts = []
                for n in s["notes"]:
                    if n["k"] == "drop":
                        parts.append(f"jugó solo {n['now']:.0%} de los snaps (antes {n['pre']:.0%})")
                    else:
                        parts.append(f"{n['now']:.0%} {lab[n['k']]} (antes {pct(n['pre'])})")
                bits.append(f"{s['name']} ({s['pos']}, {s['team']}): " + ", ".join(parts)
                            + (" — primer partido con snaps" if s["first"] else ""))
            out.append("- **Uso:** " + "; ".join(bits)
                       + (f" *(partido decidido por {g['blowout']}: confirmar que no es uso de paliza)*" if g.get("blowout") else ""))
        if g["injuries"]:
            out.append("- **Lesiones:** " + "; ".join(
                f"{i['name']} ({i['pos']}, {i['team']}) {i['body'] or ''} — {pp.STATUS_ES.get(i['status'], i['status'])}"
                for i in g["injuries"]))
        out.append("")

    out.append("## Para comprar, vender y vigilar\n")
    def rk_txt(sc):
        if not sc or not sc.get("avg"):
            return "sin calendario"
        r = {o: (slr["fpa_rank"].get(sc.get("pos")) or {}).get(o) for o in sc["opps"]}
        return "próximos: " + ", ".join(f"{o} {pp.ordinal(r[o])}" if r.get(o) else o for o in sc["opps"]) + f" (promedio {sc['avg']:.0f}º)"
    if streaks:
        out.append("**Rachas** (partidos seguidos; calendario = lugar del rival en puntos que permite a la posición, 1º = el más blando):")
        for x in streaks:
            out.append(f"- {x['name']} ({x['pos']}, {x['team']}, {x['owned']:.0f}% en ligas): {x['n']} seguidos con {x['what']} — {rk_txt(x['sched'])}")
        out.append("")
    if losers:
        out.append("**Perdieron el rol sin estar lesionados:**")
        for x in losers:
            what = "de los toques del backfield" if x["k"] == "touch" else "de los targets"
            out.append(f"- {x['name']} ({x['pos']}, {x['team']}): {pct(x['now'])} {what} (antes {pct(x['pre'])}) con {pct(x['snap'])} de los snaps — {x['line']}"
                       + (f" *(paliza de {x['blowout']}: puede ser guion)*" if x.get("blowout") else ""))
        out.append("")
    if flops:
        out.append("**Titulares que fallaron** (menos de la mitad de su promedio):")
        for x in flops:
            lab = {"touch": "toques del backfield", "tgt": "targets", "snap": "snaps"}[x["k"]]
            verdict = "uso intacto: candidato a comprar barato" if x["held"] else "el uso también bajó: cuidado"
            out.append(f"- {x['name']} ({x['pos']}, {x['team']}): {x['pts']:.1f} contra {x['avg']:.1f} de promedio — {x['line']}; "
                       f"{pct(x['now'])} de {lab} (antes {pct(x['pre'])}): {verdict}. {rk_txt(x['sched'])}")
        out.append("")
    if qbs:
        out.append("**Mariscales en duda** (alguien más jugó):")
        for x in qbs:
            out.append(f"- {x['name']} ({x['team']}, {x['owned']:.0f}% en ligas) por {x['starter']}: {pct(x['snap'])} de los snaps, "
                       f"{x['line']} — {x['why']}")
        out.append("")
    for i in big:
        if i.get("mates"):
            out.append(f"**Sin {i['name']}:** " + "; ".join(f"{m['name']} ({m['pos']}) {m['line']}" for m in i["mates"]))
    out.append("")
    out.append(f"## Waivers para la semana {week + 1}\n")
    out.append(f"*Disponibles = en {OWNED_MAX}% de las ligas redraft de Sleeper o menos (hasta {DEEP_MAX}% si su rol "
               f"cambió esta semana: \"si está libre en tu liga\"). Orden: nivel (A heredó un "
               f"backfield de trabajo · B rol o proyección de titular · C profundidad), luego la proyección PPR de la "
               f"semana {week + 1} (promedio de la de Sleeper y la implícita por el uso). FAAB = % del presupuesto. Confirma la duración de cada lesión antes de decir un nivel A al aire.*\n")
    names = {"QB": "Mariscales", "RB": "Corredores", "WR": "Receptores", "TE": "Alas cerradas", "DST": "Defensivas (streaming)"}
    for pos in ("QB", "RB", "WR", "TE"):
        out.append(f"### {names[pos]}\n")
        if not waivers[pos]:
            out.append("_Nada que valga la pena por encima del mínimo._\n")
            continue
        out.append(f"| # | Jugador | % ligas | Semana {week} | Uso sem. {week} (antes) | Semana {week + 1}: rival | "
                   "Proy. Sleeper / por uso | Por qué | FAAB |\n|---|---|---|---|---|---|---|---|---|")
        for n, c in enumerate(waivers[pos], 1):
            k = "touch" if pos == "RB" else "snap" if pos == "QB" else "tgt"
            use = (f"{pct((c['now'] or {}).get(k))} ({pct((c['pre'] or {}).get(k))}) {'backfield' if k == 'touch' else 'snaps' if k == 'snap' else 'targets'}"
                   if c["now"] else "—")
            nxt_txt = f"{c['opp']}" + (f" ({pp.ordinal(c['opp_rank'])} que más permite)" if c["opp_rank"] else "")
            pj = f"{c['proj'] if c['proj'] is not None else '—'} / {c['uproj'] if c['uproj'] is not None else '—'}"
            name = (f"{c['name']} ({c['team']})" + (f" **{pp.STATUS_ES.get(c['inj'], c['inj'])}**" if c["inj"] else "")
                    + (f" 📈{c['trend']:,}" if c["trend"] else ""))
            wk = f"{c['pts_wk']:.1f} — {c['line_wk']}" if c["pts_wk"] is not None else c["line_wk"]
            own_txt = f"{c['owned']:.0f}% (libre en {100 - c['owned']:.0f}%)" if c.get("deep") else f"{c['owned']:.0f}%"
            out.append(f"| {n} | {name} | {own_txt} | {wk} | {use} | {nxt_txt} | {pj} | {'; '.join(c['why']) or '—'} | "
                       f"**{c['tier']}** {c['faab']} |")
        out.append("")
    out.append(f"### {names['DST']}\n")
    if waivers["DST"]:
        out.append("| # | Defensiva | % ligas | Rival | Puntos implícitos del rival | Proyección | Capturas / robos proy. |\n"
                   "|---|---|---|---|---|---|---|")
        for n, d in enumerate(waivers["DST"], 1):
            imp = f"{d['opp_implied']:.1f}" if d["opp_implied"] is not None else "—"
            out.append(f"| {n} | {d['name']} | {d['owned']:.0f}% | {d['opp']} | {imp} | {d['proj']:.1f} | "
                       f"{d['sacks'] or 0:.1f} / {d['takeaways']:.1f} |")
    out.append("")
    if hot:
        out.append("### Los más agregados en Sleeper (24 h) — resolver por qué antes de recomendarlos\n")
        out.append(f"| Jugador | Agregados | % ligas | Semana {week} |\n|---|---|---|---|")
        for h_ in hot:
            wk = f"{h_['pts_wk']:.1f} — {h_['line_wk']}" if h_["pts_wk"] is not None else h_["line_wk"]
            tag = f" **{pp.STATUS_ES.get(h_['inj'], h_['inj'])}**" if h_["inj"] else ""
            out.append(f"| {h_['name']} ({h_['pos']}, {h_['team']}){tag} | {h_['adds']:,} | {h_['owned']:.0f}% | {wk} |")
        out.append("")
    out.append("*Método: línea de cierre de DraftKings vía ESPN; lesiones = lista de ESPN del partido con fecha desde la "
               "patada inicial (las bajas previas al partido no cuentan); uso = participación de la semana contra la de la "
               "temporada antes de esta semana (Sleeper); % en ligas = ligas redraft de Sleeper; proyecciones de Sleeper "
               "recalculadas en PPR; defensivas en puntuación estándar.*")
    md = "\n".join(out) + "\n"

    dest = ROOT / "reports" / season / "podcast" / f"week{week:02d}"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "recap-prep.md").write_text(md)
    data = {"season": season, "week": week, "generated": now_mx.isoformat(), "record": record, "picks": picks,
            "summary": summ, "results": rows,
            "pending": [{"game": f"{g['away']}@{g['home']}", "date": g["date"].isoformat()} for g in pending],
            "games": [{"game": f"{g['away']}@{g['home']}", "away": g["away"], "home": g["home"],
                       "away_id": g["away_id"], "home_id": g["home_id"], "as": g["as"], "hs": g["hs"],
                       "row": g["row"], "box": g.get("box"), "top": g["top"], "swings": g["swings"],
                       "injuries": g["injuries"], "blowout": g.get("blowout")} for g in finals],
            "injuries": big, "waivers": waivers, "hot": hot, "watch": watch, "md": md}
    (dest / "recap.json").write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str))
    print(f"→ {dest / 'recap-prep.md'}  ({len(finals)} finales, {len(pending)} pendientes, "
          f"{len(big)} lesiones con rol, {sum(len(v) for v in waivers.values())} waivers)")


if __name__ == "__main__":
    main()
