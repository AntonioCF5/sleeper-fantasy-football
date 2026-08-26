#!/usr/bin/env python3
"""Hoja de hechos verificada para EL DESTAPE DE MIROSLAVA.

Genera, POR LIGA, todo dato factual que el roast tiene permitido usar:
managers (display name + team name), roster resumido por manager (QB room
completo + top skill players), standings con récord/puntos, resultados de
matchups de la semana (con margen — candidatos a Putiza de la Semana),
transacciones recientes (trades con ambos lados, waivers con FAAB, drops),
y estado/fecha del draft. Todo sale del API de Sleeper en el momento de la
corrida — nada de memoria.

Regla de uso (miroslava.md, regla 2): NINGÚN dato factual entra al Destape
si no está en esta hoja o en el canon (miroslava.md). Si un chiste necesita
un hecho que no está aquí, se verifica y se AGREGA aquí primero, o el chiste
no sale.

Uso: python3 scripts/roast_facts.py [--week N]
Escribe reports/<season>/roast/facts-<liga>-<fecha>.md y también imprime.
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sleeper import api, scoring  # noqa: E402

ROAST_LEAGUES = ("Gallamijos League", "Gallamijos Dynasty")
TOP_SKILL = 6  # jugadores top por proyección mostrados por manager


def _proj_map(season, scoring_settings):
    rows = api.get_season_projections(season)
    out = {}
    for r in rows:
        pid = r.get("player_id")
        if pid:
            out[pid] = round(scoring.score_stat_line(r.get("stats") or {}, scoring_settings), 1)
    return out


MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _fecha_es(dt):
    return f"{DIAS[dt.weekday()]} {dt.day} de {MESES[dt.month]} {dt.year}, {dt:%H:%M}"


def _fmt_player(players, pid, proj):
    p = players.get(pid, {})
    name = p.get("full_name") or pid
    pos = p.get("position") or "?"
    team = p.get("team") or "FA"
    return f"{name} ({pos} {team}, proy {proj.get(pid, 0)})"


def league_facts(lg_cfg, season, week, players):
    lid = lg_cfg["league_id"]
    league = api.get_league(lid)
    users = {u["user_id"]: u for u in api.get_league_users(lid)}
    rosters = api.get_rosters(lid)
    proj = _proj_map(season, league["scoring_settings"])
    rid_owner = {}
    lines = [f"# HOJA DE HECHOS — {lg_cfg['name']} — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ')}",
             "", "Fuente: API de Sleeper en vivo. Todo chiste factual del Destape sale de aquí o de miroslava.md.", ""]

    drafts = api.get_league_drafts(lid) or []
    for d in drafts:
        when = d.get("start_time")
        when_s = _fecha_es(datetime.fromtimestamp(when / 1000)) if when else "SIN FECHA"
        lines.append(f"**Draft**: status `{d.get('status')}`, fecha {when_s}, tipo {d.get('type')}")
    lines.append("")

    lines.append("## Managers, récords y rosters")
    standings = []
    for r in rosters:
        u = users.get(r.get("owner_id"), {})
        dn = u.get("display_name", "?")
        team = (u.get("metadata") or {}).get("team_name") or dn
        s = r.get("settings", {})
        rid_owner[r["roster_id"]] = dn
        standings.append((dn, team, s.get("wins", 0), s.get("losses", 0), s.get("ties", 0),
                          s.get("fpts", 0) + s.get("fpts_decimal", 0) / 100.0, r))
    standings.sort(key=lambda x: (-x[2], -x[5]))
    for dn, team, w, l, t, fpts, r in standings:
        lines.append(f"\n### {dn} — \"{team}\" — {w}-{l}{('-' + str(t)) if t else ''}, {fpts:.1f} pts")
        allp = r.get("players") or []
        reserve = set((r.get("reserve") or []) + (r.get("taxi") or []))
        active = [p for p in allp if p not in reserve]
        qbs = [p for p in active if players.get(p, {}).get("position") == "QB"]
        lines.append("- QB room: " + (", ".join(_fmt_player(players, p, proj) for p in
                     sorted(qbs, key=lambda x: -proj.get(x, 0))) or "ninguno"))
        skill = sorted((p for p in active if players.get(p, {}).get("position") in ("RB", "WR", "TE")),
                       key=lambda x: -proj.get(x, 0))[:TOP_SKILL]
        lines.append("- Top jugadores: " + ", ".join(_fmt_player(players, p, proj) for p in skill))
        if r.get("taxi"):
            lines.append("- Taxi: " + ", ".join(players.get(p, {}).get("full_name") or p for p in r["taxi"]))

    # El martes en la mañana Sleeper ya suele haber rolado a la semana
    # siguiente — si la semana actual no tiene puntos, cae a la anterior:
    # esos son los resultados que el Destape roastea.
    def _week_results(wk):
        matchups = api.get_matchups(lid, wk) or []
        by_m = {}
        for m in matchups:
            by_m.setdefault(m.get("matchup_id"), []).append(m)
        rows = []
        for mid, pair in sorted(by_m.items(), key=lambda kv: str(kv[0])):
            if mid is None or len(pair) != 2:
                continue
            a, b = sorted(pair, key=lambda m: -(m.get("points") or 0))
            pa, pb = a.get("points") or 0, b.get("points") or 0
            if pa == 0 and pb == 0:
                continue
            tie = " — EMPATE (no hay ganador, no inventar uno)" if pa == pb else ""
            rows.append(f"- **{rid_owner.get(a['roster_id'], '?')}** {pa:.1f} vs {pb:.1f} "
                        f"{rid_owner.get(b['roster_id'], '?')} (margen {pa - pb:.1f}){tie}")
        return rows

    shown_week, rows = week, _week_results(week)
    if not rows and week > 1:
        shown_week, rows = week - 1, _week_results(week - 1)
    lines.append(f"\n## Resultados de la semana {shown_week}"
                 + (" (semana anterior — la actual aún no se juega)" if shown_week != week else ""))
    if rows:
        lines.extend(rows)
    else:
        lines.append("- SIN RESULTADOS todavía (semana no jugada) — el Destape NO inventa marcadores.")

    lines.append("\n## Transacciones (últimas 2 semanas de rondas)")
    any_tx = False
    for wk in range(max(1, week - 1), week + 1):
        for tx in api.get_transactions(lid, wk) or []:
            if tx.get("status") != "complete":
                continue
            any_tx = True
            kind = tx.get("type")
            who = [rid_owner.get(rid, "?") for rid in (tx.get("roster_ids") or [])]
            adds = ", ".join(f"{players.get(p, {}).get('full_name') or p}→{rid_owner.get(rid, '?')}"
                             for p, rid in (tx.get("adds") or {}).items())
            drops = ", ".join(f"{players.get(p, {}).get('full_name') or p} (dropeado por {rid_owner.get(rid, '?')})"
                              for p, rid in (tx.get("drops") or {}).items())
            bid = (tx.get("settings") or {}).get("waiver_bid")
            lines.append(f"- [{kind}] {'/'.join(who)}: " + "; ".join(x for x in (
                f"altas: {adds}" if adds else "", f"bajas: {drops}" if drops else "",
                f"FAAB ${bid}" if bid is not None else "") if x))
    if not any_tx:
        lines.append("- Sin transacciones completadas en la ventana.")

    return "\n".join(lines) + "\n"


def main():
    week = None
    if "--week" in sys.argv:
        week = int(sys.argv[sys.argv.index("--week") + 1])
    cfg = json.load(open(os.path.join(os.path.dirname(__file__), "..", "config.json")))
    season = cfg.get("season") or str(datetime.now().year)
    if week is None:
        week = max(1, api.get_state().get("week") or 1)
    players = api.get_players()
    outdir = os.path.join(os.path.dirname(__file__), "..", "reports", str(season), "roast")
    os.makedirs(outdir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    for lg in cfg["leagues"]:
        if lg["name"] not in ROAST_LEAGUES:
            continue
        text = league_facts(lg, season, week, players)
        slug = "gallamijos" if "Dynasty" not in lg["name"] else "dynasty"
        path = os.path.join(outdir, f"facts-{slug}-{today}.md")
        with open(path, "w") as f:
            f.write(text)
        print(f"=== {lg['name']} → {os.path.relpath(path)} ===")
        print(text)


if __name__ == "__main__":
    main()
