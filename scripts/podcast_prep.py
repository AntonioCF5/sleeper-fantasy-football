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

from sleeper import api, espn, history  # noqa: E402
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
    return f"{n}º"


# The sheet is in Spanish (user 2026-10-28: the podcast is in Spanish).
MX = ZoneInfo("America/Mexico_City")
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
STATUS_ES = {"Out": "Fuera", "Doubtful": "Dudoso", "Questionable": "Cuestionable", "IR": "Reserva",
             "Suspension": "Suspendido", "PUP": "PUP"}
BODY_ES = {"Knee": "Rodilla", "Ankle": "Tobillo", "Hamstring": "Isquiotibial", "Shoulder": "Hombro",
           "Concussion": "Conmoción", "Groin": "Ingle", "Calf": "Pantorrilla", "Hip": "Cadera", "Foot": "Pie",
           "Back": "Espalda", "Chest": "Pecho", "Neck": "Cuello", "Toe": "Dedo del pie", "Hand": "Mano",
           "Wrist": "Muñeca", "Illness": "Enfermedad", "Quadriceps": "Cuádriceps", "Ribs": "Costillas",
           "Elbow": "Codo", "Shin": "Espinilla", "Thumb": "Pulgar", "Finger": "Dedo", "Achilles": "Aquiles",
           "Forearm": "Antebrazo", "Abdomen": "Abdomen", "Oblique": "Oblicuo", "Pectoral": "Pectoral",
           "Heel": "Talón", "Thigh": "Muslo", "Head": "Cabeza", "Face": "Cara", "Eye": "Ojo", "Jaw": "Mandíbula",
           "Suspension": "Suspensión", "Personal": "Personal", "Rest": "Descanso", "ACL": "LCA", "MCL": "LCM",
           "AC Joint": "articulación AC", "High Ankle": "esguince alto", "Sprain": "esguince"}


def body_es(txt):
    return " - ".join(BODY_ES.get(part.strip(), part.strip()) for part in (txt or "").split(" - "))


def fecha(dt):
    return f"{DIAS[dt.weekday()]} {dt.day} {MESES[dt.month - 1]}"


def hora(dt):
    return f"{dt.hour % 12 or 12}:{dt.minute:02d} {'am' if dt.hour < 12 else 'pm'}"


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
                f"{ {'W': 'G', 'L': 'P', 'T': 'E'}[su]} {pf}-{pa} {'vs' if home else '@'} {opp}"
                + (f" ({line:+g} {'✓' if ats == 'W' else '✗' if ats == 'L' else 'P'}"
                   f"{', ' + {'O': 'A', 'U': 'B', 'P': 'P'}[ou] if ou else ''})" if line is not None else ""))
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
    ("passing.netYardsPerPassAttempt", "Yds netas/intento de pase", True, "{:.1f}"),
    ("rushing.yardsPerRushAttempt", "Yds/acarreo", True, "{:.1f}"),
    ("miscellaneous.thirdDownConvPct", "% en 3ª oportunidad", True, "{:.0f}%"),
    ("miscellaneous.redzoneTouchdownPct", "% de TD en zona roja", True, "{:.0f}%"),
    ("miscellaneous.turnOverDifferential", "Diferencial de balones", True, "{:+.0f}"),
    ("passing.sacks", "Capturas recibidas", False, "{:.0f}"),
    ("defensive.sacks", "Capturas (defensiva)", True, "{:.0f}"),
    ("pace", "Jugadas/partido", True, "{:.1f}"),
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
    team_tot = defaultdict(lambda: defaultdict(lambda: {"tgt": 0, "rush": 0, "air": 0, "rz_tgt": 0,
                                                       "rz_rush": 0, "rb_touch": 0}))
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
            # rec_air_yd is COMPLETED air yards (rec_yd - rec_yar), not air yards on every target
            u.update(tgt=st.get("rec_tgt") or 0, rush=st.get("rush_att") or 0,
                     snp=st.get("off_snp") or 0, tm_snp=st.get("tm_off_snp") or 0, team=team, pos=pos,
                     rec=st.get("rec") or 0, air=st.get("rec_air_yd") or 0,
                     rz_tgt=st.get("rec_rz_tgt") or 0, rz_rush=st.get("rush_rz_att") or 0)
            tt = team_tot[team][w]
            for k in ("tgt", "rush", "air", "rz_tgt", "rz_rush"):
                tt[k] += u[k]
            if pos == "RB":
                tt["rb_touch"] += u["rush"] + u["rec"]

    fpa_avg = {d: {p: sum(wk[p] for wk in weeks.values()) / len(weeks) for p in SKILL}
               for d, weeks in fpa.items()}
    fpa_rank = {p: rank_map({d: v[p] for d, v in fpa_avg.items()}) for p in SKILL}

    def shares(pid):
        weeks = sorted(w for w, u in usage[pid].items() if u["snp"] > 0)
        if not weeks:
            return None

        def agg(ws):
            mine = lambda k: sum(usage[pid][w][k] for w in ws)  # noqa: E731
            team = lambda k: sum(team_tot[usage[pid][w]["team"]][w][k] for w in ws)  # noqa: E731
            share = lambda a, b: a / b if b else 0  # noqa: E731
            snp = mine("snp")
            return {"tgt": share(mine("tgt"), team("tgt")), "rush": share(mine("rush"), team("rush")),
                    "snap": share(snp, mine("tm_snp")), "air": share(mine("air"), team("air")),
                    "rz_tgt": share(mine("rz_tgt"), team("rz_tgt")),
                    "rz_rush": share(mine("rz_rush"), team("rz_rush")),
                    # backfield share: carries + catches over every RB touch the team had
                    "touch": share(mine("rush") + mine("rec"), team("rb_touch")) if usage[pid][ws[0]].get("pos") == "RB" else 0,
                    "tgt_snap": share(mine("tgt"), snp), "tgt_g": mine("tgt") / len(ws),
                    "touch_g": (mine("rush") + mine("rec")) / len(ws), "g": len(ws)}
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


def _pp(x):
    return f"{x:.0%}" if x else "—"


def usage_data(t, proj):
    """Per-team usage: backfield split + target tree, the numbers that back an argument on air.
    Routes run are not in any free 2026 feed (nflverse participation ends 2025);
    route participation comes from the research layer."""
    ps = [p for p in proj if p["team"] == sl(t) and p["share"] and p["pos"] in ("RB", "WR", "TE")]
    key = lambda p, k: ((p["share"].get("l3") or {}).get(k) or 0, p["share"]["season"].get(k) or 0)  # noqa: E731
    rbs = sorted((p for p in ps if p["pos"] == "RB" and max(key(p, "touch")) >= 0.10),
                 key=lambda p: key(p, "touch"), reverse=True)[:3]
    rec = sorted((p for p in ps if p["pos"] in ("WR", "TE") and max(key(p, "tgt")) >= 0.08),
                 key=lambda p: key(p, "tgt"), reverse=True)[:6]
    if not rbs and not rec:
        return None
    rows = []
    for p in rbs + rec:
        sh = p["share"]
        l3, sz = sh.get("l3") or {}, sh["season"]
        pair = lambda k: [l3.get(k) if l3.get("g") else None, sz.get(k)]  # noqa: E731
        rb = p["pos"] == "RB"
        rows.append({"pid": p["pid"], "name": p["name"], "pos": p["pos"], "missed": sh.get("missed_l3") or 0,
                     "snap": pair("snap"), "tgt": pair("tgt"), "tgt_g": (l3 if l3.get("g") else sz)["tgt_g"],
                     "touch_g": (l3 if l3.get("g") else sz)["touch_g"],
                     "air": None if rb else pair("air"), "rz": pair("rz_rush" if rb else "rz_tgt"),
                     "rz_kind": "acarreos" if rb else "targets", "touch": pair("touch") if rb else None})
    out = {"team": t, "rows": rows}
    if rbs:
        cur = lambda p: (p["share"].get("l3") or {}).get("touch") or p["share"]["season"]["touch"]  # noqa: E731
        top = cur(rbs[0])
        # a back returning from injury can show a big share over the games he did play
        second = max((cur(p) for p in rbs[1:]), default=0)
        label = ("comité" if second >= 0.30 else "un solo hombre" if top >= 0.70
                 else "reparto claro" if top >= 0.55 else "comité")
        out["backfield"] = {"label": label, "name": rbs[0]["name"], "share": top}
    if len(rec) >= 2:
        two = sum(((p["share"].get("l3") or {}).get("tgt") or p["share"]["season"]["tgt"]) for p in rec[:2])
        out["top2"] = {"share": two, "label": "árbol concentrado" if two >= 0.50 else "reparto abierto" if two < 0.38 else ""}
    return out


def usage_table(u):
    if not u:
        return []
    out = [f"*{u['team']}*\n", "| Jugador | % snaps | % targets | Targets/partido | % yds aéreas compl. | % zona roja | % toques backfield |",
           "|---|---|---|---|---|---|---|"]
    pair = lambda v: f"{_pp(v[0]) if v[0] is not None else '—'} ({_pp(v[1])})"  # noqa: E731
    for r in u["rows"]:
        rb = r["pos"] == "RB"
        name = f"{r['name']} ({r['pos']})" + (f" *(se perdió {r['missed']})*" if r["missed"] else "")
        out.append(f"| {name} | {pair(r['snap'])} | {pair(r['tgt'])} | {r['tgt_g']:.1f} | "
                   f"{'—' if rb else pair(r['air'])} | {pair(r['rz'])}{' acarreos' if rb else ''} | "
                   f"{pair(r['touch']) if rb else '—'} |")
    bits = []
    if u.get("backfield"):
        b = u["backfield"]
        bits.append(f"backfield: {b['label']} ({b['name']} {b['share']:.0%} de los toques)")
    if u.get("top2"):
        bits.append(f"top-2 de targets: {u['top2']['share']:.0%} del equipo"
                    + (f" — {u['top2']['label']}" if u["top2"]["label"] else ""))
    if bits:
        out.append("\n_" + " · ".join(bits) + "_\n")
    return out


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
        lines.append(f"Semana pasada: **{last[0]}-{last[1]}{'-' + str(last[2]) if last[2] else ''}**")
    if any(season_rec):
        lines.append(f"Temporada: **{season_rec[0]}-{season_rec[1]}{'-' + str(season_rec[2]) if season_rec[2] else ''}**")
    return " · ".join(lines) or None


# -------------------------------------------------------------- render

def rest_days(team, g, all_games):
    prev = [x for x in all_games if team in (x["home"], x["away"]) and x["date"] < g["date"]]
    if not prev:
        return None, False
    last = max(prev, key=lambda x: x["date"])
    return (g["date"] - last["date"]).days, g["week"] - last["week"] > 1


# ------------------------------------------------- history (nflverse)

NOTABLE_N = {"su": 6, "ats": 8}   # minimum sample before a split is "notable"


def _split(rows, which="su"):
    led = history.tally(rows)
    n = led.n if which == "su" else led.n_ats
    return led, n


def _cell(rows, both=True):
    led = history.tally(rows)
    if not led.n:
        return "—"
    s = f"{led.fmt()}"
    if both and led.n_ats:
        s += f" · ATS {led.fmt('ats')}"
    return s


def history_block(g, hist, ctx):
    """Coach / QB / series / venue / luck rows for one upcoming game.
    Returns (markdown lines, notable [(score, text)], data dict)."""
    by_coach, by_qb, by_team, row = hist["coach"], hist["qb"], hist["team"], ctx["row"]
    h, a = g["home"], g["away"]
    season = int(ctx["season"])
    teams = {
        a: {"coach": row["away_coach"], "opp_coach": row["home_coach"], "home": False,
            "qb": ctx["qb"].get(a) or row["away_qb_name"], "opp": h, "line": ctx["line"].get(a)},
        h: {"coach": row["home_coach"], "opp_coach": row["away_coach"], "home": not g["neutral"],
            "qb": ctx["qb"].get(h) or row["home_qb_name"], "opp": a, "line": ctx["line"].get(h)},
    }
    rest = {a: row["away_rest"], h: row["home_rest"]}
    notable, cells = [], defaultdict(dict)

    def note(team, label, rows, which, mech=False):
        led, n = _split(rows, which)
        p = led.pct(which)
        if p is None or n < NOTABLE_N[which]:
            return
        if p >= 0.70 or p <= 0.30 or (which == "ats" and (p >= 0.65 or p <= 0.35)):
            tag = "" if mech else " *(tendencia — color)*"
            rec = led.fmt(which)
            notable.append((abs(p - 0.5) * n ** 0.5,
                            f"**{team}** — {label}: {rec}{' ATS' if which == 'ats' else ''}{tag}"))

    for t, info in teams.items():
        c, opp = info["coach"], info["opp"]
        crow = [r for r in by_coach.get(c, []) if r["g"]["final"]]
        line = info["line"]
        role = None if line is None else "fav" if line < 0 else "dog" if line > 0 else None
        big = line is not None and abs(line) >= 7
        role_rows = [r for r in crow if r["line"] is not None and
                     (r["line"] < 0 if role == "fav" else r["line"] > 0) and (abs(r["line"]) >= 7 if big else True)]
        venue_rows = [r for r in crow if r["home"] == info["home"]]
        vs_team = [r for r in crow if r["opp"] == opp]
        h2h = [r for r in crow if r["opp_coach"] == info["opp_coach"]]
        prev = [r for r in by_team.get(t, []) if r["g"]["final"]]
        last = prev[-1] if prev else None
        after = []
        if last and last["margin"]:
            won = last["margin"] > 0
            seq = by_coach.get(c, [])
            after = [seq[i + 1] for i in range(len(seq) - 1)
                     if seq[i]["g"]["final"] and seq[i + 1]["g"]["final"]
                     and seq[i]["margin"] and (seq[i]["margin"] > 0) == won
                     and seq[i + 1]["g"]["season"] == seq[i]["g"]["season"]]
        spot_rows, spot_label = [], None
        r_days = rest.get(t)
        if r_days and r_days >= 13:
            spot_rows, spot_label = [r for r in crow if (r["rest"] or 0) >= 13], "tras semana de descanso"
        elif r_days and r_days <= 5:
            spot_rows, spot_label = [r for r in crow if r["rest"] and r["rest"] <= 5], "con descanso corto"
        prime_rows = [r for r in crow if r["g"]["primetime"]] if row["primetime"] else []
        div_rows = [r for r in crow if r["g"]["div_game"]] if row["div_game"] else []

        cells[t]["Entrenador en jefe"] = c or "—"
        cells[t]["Carrera del coach (desde '99)"] = _cell(crow)
        role_word = "favorito" if role == "fav" else "no favorito"
        role_lbl = (f"como {role_word}{' de 7+' if big else ''}" if role else "pick'em")
        cells[t]["Coach en este rol"] = (f"{role_lbl}: {_cell(role_rows)}" if role else "—")
        cells[t]["Coach de local / de visita"] = f"{'local' if info['home'] else 'visita'}: {_cell(venue_rows)}"
        cells[t]["Coach vs esta franquicia"] = _cell(vs_team)
        cells[t]["Cara a cara vs el otro coach"] = _cell(h2h)
        if last:
            cells[t]["Coach después de " + ("victoria" if last["margin"] > 0 else "derrota")] = _cell(after)
        if spot_label:
            cells[t][f"Coach {spot_label}"] = _cell(spot_rows)
        if prime_rows:
            cells[t]["Coach en horario estelar"] = _cell(prime_rows)
        if div_rows:
            cells[t]["Coach en partidos divisionales"] = _cell(div_rows)

        qb = info["qb"]
        qrows = [r for r in by_qb.get(qb, []) if r["g"]["final"]]
        cells[t]["QB"] = qb or "—"
        cells[t]["QB, carrera como titular (desde '99)"] = _cell(qrows)
        cells[t]["QB vs este rival"] = _cell([r for r in qrows if r["opp"] == opp])
        qrole = [r for r in qrows if r["line"] is not None and role and (r["line"] < 0 if role == "fav" else r["line"] > 0)]
        if role:
            cells[t]["QB en este rol"] = f"como {role_word}: {_cell(qrole)}"

        # venue splits — this season and the last three
        tr = [r for r in by_team.get(t, []) if r["g"]["final"] and r["g"]["game_type"] == "REG"]
        cur = [r for r in tr if r["g"]["season"] == season]
        for flag in (True, False):
            rr = [r for r in cur if r["home"] == flag]
            led = history.tally(rr)
            pf = sum((r["g"]["home_score"] if r["home"] else r["g"]["away_score"]) for r in rr)
            pa = sum((r["g"]["away_score"] if r["home"] else r["g"]["home_score"]) for r in rr)
            cells[t][f"Esta temporada {'de local' if flag else 'de visita'}"] = (f"{led.fmt()} · ATS {led.fmt('ats')} · {pf / len(rr):.1f}-{pa / len(rr):.1f}"
                                                 if rr else "—")
        last3 = [r for r in tr if season - 2 <= r["g"]["season"] <= season]
        hm = [r["margin"] for r in last3 if r["home"]]
        rm = [r["margin"] for r in last3 if not r["home"] and r["g"].get("location") != "Neutral"]
        if hm and rm:
            edge = (sum(hm) / len(hm) - sum(rm) / len(rm)) / 2
            hl, rl = history.tally([r for r in last3 if r["home"]]), history.tally([r for r in last3 if not r["home"]])
            cells[t]["Ventaja de local, últimas 3 temporadas"] = f"{edge:+.1f} pts (local {hl.fmt()}, visita {rl.fmt()})"
            # ~25 home + ~25 road games → about ±2 pts of noise on this number;
            # team-specific home field is mostly noise (Denver's altitude aside),
            # so only an extreme gap earns a note.
            if abs(edge) >= 5.5:
                notable.append((abs(edge) / 4, f"**{t}** — brecha local/visita en 3 temporadas de {edge:+.1f} pts por lado "
                                f"(local {hl.fmt()}, visita {rl.fmt()}); norma de la liga ~+1.5, ruido ±2"))
        # luck: pythagorean + one-score games
        if cur:
            pf = sum((r["g"]["home_score"] if r["home"] else r["g"]["away_score"]) for r in cur)
            pa = sum((r["g"]["away_score"] if r["home"] else r["g"]["home_score"]) for r in cur)
            led = history.tally(cur)
            py = history.pythagorean(pf, pa, len(cur))
            close = history.tally([r for r in cur if abs(r["margin"]) <= 8])
            cells[t]["Victorias pitagóricas vs reales"] = f"{py:.1f} vs {led.su[0] + led.su[2] / 2:g}" if py is not None else "—"
            cells[t]["Partidos de una posesión (≤8)"] = close.fmt() if close.n else "—"
            if py is not None:
                d = led.su[0] + led.su[2] / 2 - py
                if abs(d) >= 1.3:
                    notable.append((abs(d), f"**{t}** — {'rinde arriba' if d > 0 else 'rinde abajo'} de su diferencial de puntos "
                                    f"por {abs(d):.1f} victorias (partidos de una posesión {close.fmt()}) — "
                                    f"{'riesgo de regresión' if d > 0 else 'mejor que su récord'}"))

        note(t, f"{c} {role_lbl}", role_rows, "ats")
        note(t, f"{c} vs {opp}", vs_team, "su")
        note(t, f"{c} vs {opp}", vs_team, "ats")
        note(t, f"{c} vs {info['opp_coach']} cara a cara", h2h, "su")
        note(t, f"{c} {spot_label}", spot_rows, "su", mech=True) if spot_label else None
        note(t, f"{c} {spot_label}", spot_rows, "ats", mech=True) if spot_label else None
        note(t, f"{c} en horario estelar", prime_rows, "su") if prime_rows else None
        note(t, f"{c} {'de local' if info['home'] else 'de visita'}", venue_rows, "ats")
        note(t, f"{qb} vs {opp}", [r for r in qrows if r["opp"] == opp], "su", mech=True)
        note(t, f"{c} después de {'victoria' if last and last['margin'] > 0 else 'derrota'}", after, "ats")

    # series history (franchise vs franchise), from the home team's perspective
    series = [r for r in by_team.get(h, []) if r["opp"] == a and r["g"]["final"]][-10:]
    L = []
    keys = list(dict.fromkeys(k for t in (a, h) for k in cells[t]))
    L.append(f"**Coaches e historia** *(nflverse, desde 1999, incluye playoffs; ATS con líneas de cierre)*\n")
    L.append(f"| | **{a}** | **{h}** |\n|---|---|---|")
    for k in keys:
        L.append(f"| {k} | {cells[a].get(k, '—')} | {cells[h].get(k, '—')} |")
    if series:
        led = history.tally(series)
        streak_team, streak = None, 0
        for r in reversed(series):
            w = h if r["margin"] > 0 else a if r["margin"] < 0 else None
            if streak_team is None:
                streak_team = w
            if w != streak_team or w is None:
                break
            streak += 1
        tot = [r["g"]["total"] for r in series]
        last = series[-1]
        L.append(f"\n**Serie, últimos {len(series)}:** {h} {led.fmt()} directo · {led.fmt('ats')} ATS · "
                 f"altas/bajas {led.ou[0]}-{led.ou[1]} · total promedio {sum(tot) / len(tot):.1f}"
                 f"{f' · {streak_team} ha ganado {streak} seguidos' if streak_team and streak >= 2 else ''}"
                 f" · último: {last['g']['season']:.0f} sem {last['g']['week']:.0f}, "
                 f"{h} {last['g']['home_score'] if last['home'] else last['g']['away_score']:.0f}-"
                 f"{last['g']['away_score'] if last['home'] else last['g']['home_score']:.0f}")
        if streak_team and streak >= 4:
            notable.append((streak / 2, f"**{streak_team}** ha ganado {streak} seguidos en la serie"))
    if notable:
        L.append("\n**A destacar:**")
        for _, txt in sorted(notable, key=lambda x: -x[0])[:7]:
            L.append(f"- {txt}")
    L.append("")
    return L, notable, {t: dict(cells[t]) for t in (a, h)}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cur, season = espn.current_week()
    week = int(args[0]) if args else cur
    season = str(season or api.get_state().get("season"))
    print(f"Preparación del podcast — temporada {season}, semana {week}")

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
    hgames = history.load_games()
    hc, hq, ht = history.index(hgames)
    hist = {"coach": hc, "qb": hq, "team": ht}
    hist_row = {g["espn"]: g for g in hgames if g.get("espn")}
    slate_notes = []
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
    out.append(f"# Preparación del podcast — Semana {week}, {season}\n")
    now = datetime.now(MX)
    out.append(f"*Generado {fecha(now)}, {hora(now)} CDMX · líneas de DraftKings vía ESPN · horarios en CDMX "
               f"(ET entre paréntesis) · descansan: {', '.join(byes) or 'nadie'}*\n")
    record = grade_picks(sched, week)
    if record:
        out.append(f"**Nuestro récord de picks** — {record}\n")

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
                flag = f"🚩 los dos modelos se inclinan por **{lean}** (SRS {e1:+.1f}, FPI {e2:+.1f} vs mercado, pts de margen del local)"
                flags.append((min(abs(e1), abs(e2)), f"{a} @ {h}", lean, e1, e2))
                verdict = flag
            elif max(abs(e1), abs(e2)) < FLAG_EDGE:
                verdict = "los modelos coinciden con el mercado ✅"
            elif e1 * e2 > 0:
                verdict = (f"leve inclinación por {h if e1 > 0 else a} (SRS {e1:+.1f}, FPI {e2:+.1f} vs mercado)"
                           " — debajo del umbral de alerta")
            else:
                verdict = f"modelos divididos (SRS {e1:+.1f}, FPI {e2:+.1f} vs mercado) — sin señal"
        fav = h if (spread or 0) < 0 else a
        fav_line = spread if fav == h else (-spread if spread is not None else None)
        open_fav = None
        if o.get("open_spread") is not None:
            open_fav = o["open_spread"] if fav == h else -o["open_spread"]
        kick = g["date"].astimezone(ET)
        kmx = g["date"].astimezone(MX)
        move = ""
        if open_fav is not None and fav_line is not None and open_fav != fav_line:
            move = f" (abrió {fmt_spread(fav, open_fav)})"
        tmove = f" (abrió {o['open_total']:g})" if o.get("open_total") not in (None, total) else ""
        slate_rows.append(
            f"| {a} @ {h} | {DIAS[kmx.weekday()]} {hora(kmx)} | {fmt_spread(fav, fav_line)}{move} | "
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
            weather = "techado"
        elif wx:
            weather = f"{wx.get('temperature')}°F, {wx.get('precipitation', 0)}% de lluvia"
        L.append(f"## {a} @ {h} — {fecha(kmx)}, {hora(kmx)} CDMX ({hora(kick)} ET)")
        L.append(f"*{g['venue']} · {'pasto' if grass else 'sintético'} · {weather or 'clima n/d'}"
                 f"{' · SEDE NEUTRAL' if g['neutral'] else ''}"
                 f"{' · DIVISIONAL (' + espn.DIVISION_OF[h].replace('North', 'Norte').replace('South', 'Sur').replace('East', 'Este').replace('West', 'Oeste') + ')' if espn.DIVISION_OF.get(h) == espn.DIVISION_OF.get(a) else ''}*\n")
        L.append(f"**Línea:** {fmt_spread(fav, fav_line)}{move} · total {total if total is not None else '—'}{tmove}"
                 + (f" · ML {h} {o['ml_home']:+g} / {a} {o['ml_away']:+g}" if o.get("ml_home") is not None else ""))
        if imp_h:
            L.append(f"**Totales implícitos:** {h} {imp_h:.1f} · {a} {imp_a:.1f}")
        chk = []
        if mkt_margin is not None:
            chk.append(f"mercado {h} {mkt_margin:+.1f}")
        if srs_margin is not None:
            chk.append(f"SRS {h} {srs_margin:+.1f}")
        if fpi_margin is not None:
            chk.append(f"FPI {h} {fpi_margin:+.1f}")
        win = []
        if p_mkt:
            win.append(f"mercado {h} {p_mkt:.0%}")
        if p_fpi:
            win.append(f"FPI {h} {p_fpi:.0%}")
        L.append(f"**Chequeo de línea (margen del local):** {' · '.join(chk)}" + (f" — {verdict}" if verdict else ""))
        if win:
            L.append(f"**Prob. de victoria:** {' · '.join(win)}")
        if naive_total is not None and total is not None:
            d = naive_total - total
            L.append(f"**Chequeo del total:** modelo PF/PA {naive_total:.1f} vs {total:g} "
                     f"(inclinación a {'altas' if d > 0 else 'bajas'} por {abs(d):.1f}{' — ruido' if abs(d) < 3 else ''})")
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
            ("Récord (local / visita)", lambda t, R: f"{R.get('su', '—')} ({gr[t].get('home', '—')} / {gr[t].get('road', '—')})"),
            ("ATS (de favorito / de no favorito)", lambda t, R: f"{R.get('ats', '—')} ({R.get('fav', '—')} / {R.get('dog', '—')})"),
            ("Altas/Bajas", lambda t, R: R.get("ou", "—")),
            ("Margen prom. · cobertura prom.", lambda t, R: f"{R.get('margin', '—')} · {R.get('cover', '—')}"),
            ("Rating SRS", lambda t, R: f"{ratings[t]:+.1f} ({ordinal(rank_map(ratings)[t])})" if t in ratings else "—"),
            ("Puntos a favor / en contra", lambda t, R: (f"{ppg[t]:.1f} ({ordinal(ppg_rank[t])}) / {papg[t]:.1f} ({ordinal(papg_rank[t])})"
                                                   if t in ppg else "—")),
        ]
        for k, label, _, f in TEAM_METRICS:
            rows.append((label, lambda t, R, k=k, f=f: (f"{f.format(tstats[t][k])} ({ordinal(metric_ranks[k][t])})"
                                                         if tstats.get(t, {}).get(k) is not None and t in metric_ranks[k] else "—")))

        def spot(t):
            days, bye = rest_days(t, g, all_games)
            bits = [f"{days} días de descanso" if days is not None else "—"]
            if bye:
                bits.append("tras semana de descanso")
            elif days is not None and days <= 5:
                bits.append("SEMANA CORTA")
            if t in WEST and t == a and kick.hour == 13 and h not in WEST:
                bits.append("costa oeste a la 1 pm ET")
            if t in next_opp:
                bits.append(f"luego {next_opp[t]}")
            return ", ".join(bits)
        rows.append(("Situación", lambda t, R: spot(t)))
        team_rows = [(label, fn(a, ra), fn(h, rh)) for label, fn in rows]
        L.append(f"| | **{a}** | **{h}** |\n|---|---|---|")
        for label, va, vh in team_rows:
            L.append(f"| {label} | {va} | {vh} |")
        L.append("")
        last5 = {t: list(reversed(((rec.get(t) or {}).get("log") or [])[-5:])) for t in (a, h)}
        for t in (a, h):
            log = (rec.get(t) or {}).get("log") or []
            if log:
                L.append(f"**{t} últimos 5:** " + " · ".join(reversed(log[-5:])))
        L.append("")

        hrow = hist_row.get(g["id"])
        if hrow:
            qb1 = {}
            for t in (a, h):
                qbs = sorted((p for p in slr["proj"] if p["team"] == sl(t) and p["pos"] == "QB"), key=lambda p: -p["ppr"])
                if qbs:
                    qb1[t] = qbs[0]["name"]
            ctx = {"row": hrow, "season": season, "qb": qb1,
                   "line": {h: spread, a: -spread} if spread is not None else {}}
            hl, hn, hdata = history_block(g, hist, ctx)
            L.extend(hl)
            series = next((x.strip() for x in hl if "**Serie" in x), None)
            notables = [txt for _, txt in sorted(hn, key=lambda x: -x[0])[:7]]
            slate_notes.extend((sc, f"{a} @ {h}: {txt}") for sc, txt in hn)
        else:
            hdata, series, notables = None, None, []

        # injuries
        injuries = {}
        for blk in s.get("injuries") or []:
            t = (blk.get("team") or {}).get("abbreviation")
            items = [i for i in blk.get("injuries") or [] if i.get("status") in ("Out", "Doubtful", "Questionable")]
            if not items:
                continue
            injuries[t] = [{"name": i["athlete"]["displayName"],
                            "pos": (i["athlete"].get("position") or {}).get("abbreviation") or "",
                            "status": STATUS_ES.get(i["status"], i["status"]),
                            "body": body_es((i.get("details") or {}).get("type", "")) if (i.get("details") or {}).get("type") else ""}
                           for i in items]
            txt = ", ".join(f"{i['athlete']['displayName']} {((i['athlete'].get('position') or {}).get('abbreviation') or '')}"
                            f" ({STATUS_ES.get(i['status'], i['status'])}{' — ' + body_es((i.get('details') or {}).get('type', '')) if (i.get('details') or {}).get('type') else ''})"
                            for i in items[:14])
            L.append(f"**{t} lesiones:** {txt}")
        L.append("")

        # fantasy
        L.append("**Fantasy**\n")
        L.append("| Jugador | Proy. PPR (half) | % targets últ. 3 (temp.) | % acarreos últ. 3 (temp.) | % snaps últ. 3 | Enfrentamiento |\n|---|---|---|---|---|---|")
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
                    mu = f"{tag} {opp} es {ordinal(rk)} que más permite a {p['pos']} ({fp:.1f})"
                trend = ""
                if l3 and sz and l3.get("g", 0) >= 2:
                    dt = l3["tgt"] - sz["tgt"]
                    dr = l3["rush"] - sz["rush"]
                    if dt >= 0.05 or dr >= 0.10:
                        trend = " ⬆️"
                    elif dt <= -0.05 or dr <= -0.10:
                        trend = " ⬇️"
                pct = lambda x: f"{x:.0%}" if x else "—"  # noqa: E731
                name = (f"{p['name']} ({p['pos']}, {t})" + (f" **{STATUS_ES.get(p['inj'], p['inj'])}**" if p["inj"] else "")
                        + (" 📈" if p["pid"] in trending else "") + trend
                        + (f" *(se perdió {sh['missed_l3']} de los últimos 3)*" if sh.get("missed_l3") else ""))
                L.append(f"| {name} | {p['ppr']:.1f} ({p['half']:.1f}) | "
                         f"{pct(l3.get('tgt'))} ({pct(sz.get('tgt'))}) | {pct(l3.get('rush'))} ({pct(sz.get('rush'))}) | "
                         f"{pct(l3.get('snap'))} | {mu} |")
                game_players.append({**{k: p[k] for k in ("pid", "name", "pos", "team", "ppr", "half", "inj")},
                                     "team_code": t, "opp": opp, "fpa": fp, "trend": trend.strip(),
                                     "inj_es": STATUS_ES.get(p["inj"], p["inj"]) if p["inj"] else None,
                                     "matchup_rank": rk, "share": p["share"], "trending": trending.get(p["pid"])})
        L.append("\n**Uso por equipo** (últimos 3 del equipo · temporada entre paréntesis)\n")
        usage = {t: usage_data(t, slr["proj"]) for t in (a, h)}
        for t in (a, h):
            L.extend(usage_table(usage[t]))
        dst_lines = {}
        for t in (a, h):
            opp = h if t == a else a
            mine = slr["dst"].get(sl(t)) or {}
            if mine:
                L.append(f"\n*DST {t}:* {mine.get('sack', 0):.1f} capturas, {mine.get('int', 0) + mine.get('fum_rec', 0):.1f} balones recuperados, "
                         f"{mine.get('pts_allow', 0):.1f} pts permitidos por partido · ofensiva de {opp}: "
                         f"{tstats.get(opp, {}).get('passing.sacks') or 0:.0f} capturas recibidas, "
                         f"{tstats.get(opp, {}).get('miscellaneous.totalGiveaways') or 0:.0f} balones perdidos"
                         + (f", total implícito {imp_h if opp == h else imp_a:.1f}" if imp_h else ""))
                dst_lines[t] = L[-1].split(":* ", 1)[1]
        L.append("\n---\n")
        sections.append("\n".join(L))
        data_games.append({"game": f"{a}@{h}", "kickoff": kick.isoformat(), "odds": o,
                           "p_market": p_mkt, "p_fpi": p_fpi, "srs_margin": srs_margin,
                           "fpi_margin": fpi_margin, "naive_total": naive_total,
                           "implied": {h: imp_h, a: imp_a}, "flag": flag, "players": game_players,
                           "history": hdata,
                           "sheet": {
                               "away": a, "home": h, "away_id": g["away_id"], "home_id": g["home_id"],
                               "kick_mx": f"{fecha(kmx)}, {hora(kmx)}", "kick_et": hora(kick),
                               "day": DIAS[kmx.weekday()], "venue": g["venue"],
                               "surface": "pasto" if grass else "sintético", "weather": weather or None,
                               "indoor": bool(g["indoor"]), "neutral": bool(g["neutral"]),
                               "divisional": espn.DIVISION_OF.get(h) == espn.DIVISION_OF.get(a),
                               "fav": fav, "fav_line": fav_line, "open_fav": open_fav,
                               "line_txt": fmt_spread(fav, fav_line), "open_txt": fmt_spread(fav, open_fav) if open_fav is not None else None,
                               "srs_line": fmt_spread(h, round(-srs_margin * 2) / 2) if srs_margin is not None else None,
                               "verdict": verdict, "mkt_margin": mkt_margin,
                               "team_rows": team_rows, "last5": last5, "injuries": injuries,
                               "usage": usage, "dst": dst_lines, "series": series, "notables": notables,
                               "md": "\n".join(L)}})

    out.append("## Cartelera\n")
    out.append("| Partido | Hora (CDMX) | Spread | Total | Implícitos | % local mercado | % local FPI | Línea SRS | |\n"
               "|---|---|---|---|---|---|---|---|---|")
    out.extend(slate_rows)
    out.append("")
    if flags:
        out.append("### 🚩 Alertas de línea (los dos modelos lejos del mercado)\n")
        for e, game, lean, e1, e2 in sorted(flags, reverse=True):
            out.append(f"- **{game}** → inclinación por **{lean}** · SRS {e1:+.1f} / FPI {e2:+.1f} pts vs mercado")
        out.append("")
    if slate_notes:
        out.append("### Notas históricas que vale la pena mencionar\n")
        out.extend(f"- {txt}" for _, txt in sorted(slate_notes, key=lambda x: -x[0])[:12])
        out.append("")
    imp = sorted(((v, t) for dg in data_games for t, v in dg["implied"].items() if v), reverse=True)
    if imp:
        out.append("### Totales implícitos por equipo\n")
        out.append("Arriba: " + " · ".join(f"{t} {v:.1f}" for v, t in imp[:6]))
        out.append("\nAbajo: " + " · ".join(f"{t} {v:.1f}" for v, t in imp[-6:][::-1]) + "\n")
    # softest matchups this week
    out.append("### Enfrentamientos más blandos de la semana (PPR permitido por partido, lugar de 32)\n")
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
        out.append("### Uso en ascenso (últimos 3 vs temporada)\n")
        for _, p, dt, dr, l3 in sorted(risers, key=lambda x: -x[0])[:10]:
            bits = []
            if dt >= 0.06:
                bits.append(f"% de targets {l3['tgt']:.0%} ({dt:+.0%})")
            if dr >= 0.12:
                bits.append(f"% de acarreos {l3['rush']:.0%} ({dr:+.0%})")
            out.append(f"- {p['name']} ({p['pos']}, {p['team']}) — {', '.join(bits)} · proy. {p['ppr']:.1f} PPR")
        out.append("")
    big_t, horses = [], []
    for p in slr["proj"]:
        sh = p["share"] or {}
        l3 = sh.get("l3") or {}
        if p["team"] not in {sl(t) for t in playing} or l3.get("g", 0) < 2:
            continue
        if p["pos"] in ("WR", "TE") and l3["tgt"] >= 0.27:
            big_t.append((l3["tgt"], p, l3))
        if p["pos"] == "RB" and l3["touch"] >= 0.70:
            horses.append((l3["touch"], p, l3))
    if big_t or horses:
        out.append("### Roles más grandes de la cartelera (últimos 3)\n")
        if big_t:
            out.append("- **Imanes de targets (≥27%):** " + " · ".join(
                f"{p['name']} ({p['team']}) {v:.0%}, {l3['tgt_g']:.1f}/partido" for v, p, l3 in sorted(big_t, key=lambda x: -x[0])[:10]))
        if horses:
            out.append("- **Caballos de trabajo (≥70% de los toques del backfield):** " + " · ".join(
                f"{p['name']} ({p['team']}) {v:.0%}, {l3['touch_g']:.1f} toques/partido" for v, p, l3 in sorted(horses, key=lambda x: -x[0])[:10]))
        out.append("")
    tr = [p for p in slr["proj"] if p["pid"] in trending]
    if tr:
        out.append("### Más agregados en Sleeper (48h) de esta cartelera\n")
        out.append(" · ".join(f"{p['name']} ({p['pos']}, {p['team']}) +{trending[p['pid']]:,}"
                              for p in sorted(tr, key=lambda p: -trending[p["pid"]])[:12]) + "\n")
    out.append("---\n")
    slate_md = "\n".join(out[2:])
    out.extend(sections)
    out[-1] = out[-1].rstrip("-\n")
    out.append("\n*Método: SRS = margen ajustado por rival (tope ±21, ventaja de local 1.5, encogido n/(n+3)); "
               "margen FPI = % de victoria de ESPN pasado por una normal con DE 13.5; la alerta 🚩 pide que los dos "
               "estén a ≥2 pts del mercado hacia el mismo lado. Puntos de fantasy recalculados con reglas estándar "
               "PPR/half. Enfrentamiento 1º = la defensa que más puntos de fantasy permite a esa posición. "
               "Últimos 5: G/P/E = ganado/perdido/empate; ✓/✗ = cubrió/no cubrió; A/B = altas/bajas. "
               "Uso: yardas aéreas = completadas (Sleeper no da las de todos los targets); zona roja = % de los "
               "targets (WR/TE) o acarreos (RB) del equipo dentro del 20; toques backfield = acarreos + recepciones "
               "sobre los de todos los RB del equipo. Rutas corridas no salen en ninguna fuente gratuita de 2026: "
               "vienen de la investigación (Rotowire / FTN).*\n")

    dest = ROOT / "reports" / season / "podcast" / f"week{week:02d}"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "podcast-prep.md").write_text("\n".join(out))
    (dest / "data.json").write_text(json.dumps({"week": week, "season": season, "generated": now.isoformat(),
                                                "record": record, "byes": byes, "slate_md": slate_md,
                                                "games": data_games}, indent=1, default=str))
    print(f"→ {dest / 'podcast-prep.md'}  ({len(upcoming)} partidos, {len(flags)} alertas de línea)")


if __name__ == "__main__":
    main()
