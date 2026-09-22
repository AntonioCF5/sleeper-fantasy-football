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
from sleeper import analysis, api, scoring  # noqa: E402

ROAST_LEAGUES = ("Gallamijos League", "Gallamijos Dynasty")

# BANDOS POR MANAGER — la fuente de verdad (fijado 2026-09-22 tras que el
# Marcador de la Guerra se omitiera una edición por no tenerlo escrito).
# Derivado del canon (palmarés 2015-2025 + el recuento del top-8 del 08-31 +
# expedientes) y VALIDADO contra los tres conteos publicados: redraft
# 4/9/5 y dinastía 5/5/2 cuadran exacto, igual que los récords de la
# jornada 1 ya impresos (Mijos 4-0 con tres contra Gallaghers, los nueve
# 2-7 con una intra-bando, francotiradores 3-2; mijada 3-2 y los dos
# francotiradores 0-2 en la Dinastía). NUNCA inferir un bando: si aparece un
# manager nuevo, se pregunta al user y se agrega aquí.
# Etiquetas de display para la tabla de WhatsApp (el bando canónico es la
# clave; el nombre que se imprime rota según la edición — ver canon).
ETIQUETA = {"Sin Bandera": "Independientes", "Mijo": "Mijos", "Gallagher": "Gallaghers"}

BANDOS = {
    # Mijos — 4 en la redraft, 5 en la Dinastía (La Pepa solo juega Dinastía)
    "elmijo": "Mijo", "alealvarez7": "Mijo", "charlyae17": "Mijo",
    "rodrigodiaz": "Mijo", "panchocruz": "Mijo",
    # Sin Bandera / Los Independientes — 5 en la redraft, 2 en la Dinastía
    "jffaya": "Sin Bandera", "Tibu23": "Sin Bandera", "aledlg": "Sin Bandera",
    "maudlgarza": "Sin Bandera", "FilledUpRivers": "Sin Bandera",
    "damarante": "Sin Bandera", "jetsdelalaguna": "Sin Bandera",
    # Gallaghers — 9 en la redraft, 5 en la Dinastía
    "drw25": "Gallagher", "Gallaghers4": "Gallagher", "Jro91": "Gallagher",
    "hectordavid1989TRC": "Gallagher", "tbarg91": "Gallagher",
    "ElGeneral4": "Gallagher", "Jebusf": "Gallagher",
    "davidcruz77": "Gallagher", "canogutierrez": "Gallagher",
}
TOP_SKILL = 6  # jugadores top por proyección mostrados por manager


def _limpiar_cache():
    """Borra el caché del API antes de cada hoja (regla del user 2026-08-31:
    los equipos cambian de nombre y los rosters se mueven con la agencia
    libre; una hoja con datos de ayer es una hoja con datos falsos)."""
    import shutil
    cache = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
    n = 0
    if os.path.isdir(cache):
        for f in os.listdir(cache):
            if f.endswith(".json.gz"):
                os.remove(os.path.join(cache, f))
                n += 1
    print(f"[fresco] {n} entradas de caché borradas antes de generar la hoja")


def _sleeper_pts(season):
    """Proyección PROPIA DE SLEEPER (pts_ppr) — es la que ve el grupo en la
    app. Para el roast se usa ESTA, no nuestro VORP re-scoreado: si Miroslava
    dice que alguien es 17º, el grupo lo va a verificar en Sleeper y tiene que
    cuadrar. (El análisis serio del portafolio sigue usando nuestro scoring.)"""
    out = {}
    for r in api.get_season_projections(season):
        pid = r.get("player_id")
        if pid:
            out[pid] = (r.get("stats") or {}).get("pts_ppr", 0) or 0
    return out


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

    # Ranking con NÚMEROS DE SLEEPER (lo que ve el grupo en la app)
    spts = _sleeper_pts(season)
    tabla = []
    for r in rosters:
        u = users.get(r.get("owner_id"), {})
        eq = (u.get("metadata") or {}).get("team_name") or u.get("display_name", "?")
        lu, _ = analysis.optimal_lineup(r.get("players") or [], league["roster_positions"],
                                        players, spts)
        tabla.append((round(sum(v for _, _, v in lu), 1), eq, u.get("display_name", "?")))
    tabla.sort(reverse=True)
    lines.append("\n## Ranking por proyección DE SLEEPER (pts_ppr, rosters de hoy)")
    lines.append("*Es el número que el grupo ve en la app — úsalo para el roast, "
                 "no nuestro VORP.*\n")
    for i, (pts, eq, h) in enumerate(tabla, 1):
        lines.append(f"{i}. **{eq}** ({h}) — {pts}")

    # TABLA DE POSICIONES REAL vs proyección (regla del user 2026-09-15):
    # "Del Penthouse al Sótano" se ordena por la tabla de la liga, y el
    # comentario compara con lo proyectado — caballos negros (🐎, tabla
    # muy arriba de su proyección), decepciones (📉, muy abajo).
    prank = {eq: i for i, (_, eq, _) in enumerate(tabla, 1)}
    lines.append("\n## TABLA DE POSICIONES (récord, puntos) vs rank de proyección")
    lines.append("*Orden de 'Del Penthouse al Sótano'. Delta = rank proyectado − lugar "
                 "real: +4 o más = 🐎 caballo negro; −4 o menos = 📉 decepción.*\n")
    for i, (dn, team, w, l, t_, fpts, r) in enumerate(standings, 1):
        pr = prank.get(team, 0)
        d = pr - i
        tag = " 🐎 CABALLO NEGRO" if d >= 4 else (" 📉 DECEPCIÓN" if d <= -4 else "")
        lines.append(f"{i}. **{team}** ({dn}) — {w}-{l}, {fpts:.1f} pts · proy #{pr} ({d:+d}){tag}")

    # ADDENDUM DE LINEUPS VERIFICADOS (permanente desde 2026-09-22; antes lo
    # anexaba a mano la tarea programada y se perdía al regenerar la hoja).
    # Es el material del que salen La Cagada, El Muerto y medio ranking:
    # titulares en cero, casillas VACÍAS, y banca que anotó más que el titular.
    # Aritmética de titulares: los ceros NO cuentan como jugador alineado.
    lines.append(f"\n## ADDENDUM — lineups verificados de la semana {shown_week}")
    lines.append("*Puntos REALES por jugador (players_points de Sleeper). "
                 "'Casilla vacía' = slot sin jugador; 'cero' = alineado que no anotó.*\n")
    slots = [s for s in league["roster_positions"] if s != "BN"]
    for m in sorted(api.get_matchups(lid, shown_week) or [],
                    key=lambda x: -(x.get("points") or 0)):
        dn = rid_owner.get(m["roster_id"], "?")
        pp = m.get("players_points") or {}
        st = m.get("starters") or []
        vacias = sum(1 for s in st if s in ("0", 0, "", None))
        titulares = [(pp.get(p, 0), p) for p in st if p not in ("0", 0, "", None)]
        banca = sorted(((pp.get(p, 0), p) for p in (m.get("players") or []) if p not in st),
                       reverse=True)
        lines.append(f"\n**{dn}** — {m.get('points', 0):.1f} pts, "
                     f"{len(titulares)} alineados de {len(slots)}"
                     + (f", **{vacias} CASILLA(S) VACÍA(S)**" if vacias else ""))
        best = sorted(titulares, reverse=True)[:3]
        lines.append("- Mejores: " + ", ".join(
            f"{players.get(p, {}).get('full_name') or p} {v:.1f}" for v, p in best))
        ceros = [p for v, p in titulares if v <= 0]
        if ceros:
            lines.append("- TITULARES EN CERO: " + ", ".join(
                f"{players.get(p, {}).get('full_name') or p}" for p in ceros))
        if banca:
            lines.append("- Mejor banca: " + ", ".join(
                f"{players.get(p, {}).get('full_name') or p} {v:.1f}" for v, p in banca[:3]))
            # PUNTOS RECUPERABLES DE VERDAD (regla del user 2026-09-22): no se
            # suma toda la banca que superó al peor titular — eso cuenta dos
            # QB cuando solo se alinea uno. Se calcula el LINEUP ÓPTIMO de esa
            # semana (mismo DP que usa el resto del sistema) y se resta el
            # marcador real: esa diferencia sí se podía ganar. El injury_status
            # de hoy no aplica a una semana ya jugada, así que se neutraliza.
            meta = {pid: dict(players.get(pid) or {}, injury_status=None)
                    for pid in (m.get("players") or [])}
            pts = {pid: pp.get(pid, 0) for pid in (m.get("players") or [])}
            mejor, _ = analysis.optimal_lineup(m.get("players") or [],
                                               league["roster_positions"], meta, pts)
            optimo = sum(v for _, _, v in mejor)
            perdido = optimo - (m.get("points") or 0)
            if perdido > 0.05:
                entrarian = [(v, pid) for _, pid, v in mejor if pid not in st]
                entrarian.sort(reverse=True)
                lines.append(f"- RECUPERABLE (lineup óptimo {optimo:.1f} − real "
                             f"{m.get('points', 0):.1f}): **{perdido:.1f}**"
                             + ("; debieron entrar: " + ", ".join(
                                 f"{players.get(pid, {}).get('full_name') or pid} {v:.1f}"
                                 for v, pid in entrarian[:4]) if entrarian else ""))

    # MARCADOR DE LA GUERRA, calculado (no inferido) — semana y acumulado.
    lines.append("\n## MARCADOR DE LA GUERRA (bandos leídos de BANDOS, nunca inferidos)")
    faltan = sorted({dn for dn in rid_owner.values() if dn not in BANDOS})
    if faltan:
        lines.append(f"⚠️ SIN BANDO REGISTRADO: {', '.join(faltan)} — preguntar al "
                     "user y agregarlos a BANDOS antes de publicar la sección.")
    plantel = {}
    for dn in rid_owner.values():
        plantel[BANDOS.get(dn, "???")] = plantel.get(BANDOS.get(dn, "???"), 0) + 1
    lines.append("Integrantes: " + " · ".join(f"{k} {v}" for k, v in sorted(plantel.items())))
    for etiqueta, semanas in (("Esta semana", [shown_week]),
                              ("Acumulado", list(range(1, shown_week + 1)))):
        rec, h2h = {}, {}
        for wk in semanas:
            by = {}
            for mm in api.get_matchups(lid, wk) or []:
                by.setdefault(mm.get("matchup_id"), []).append(
                    (mm.get("points") or 0, rid_owner.get(mm["roster_id"])))
            for pair in by.values():
                if len(pair) != 2 or pair[0][0] == pair[1][0]:
                    continue
                (_, gana), (_, pierde) = sorted(pair, reverse=True)
                bg, bp = BANDOS.get(gana, "???"), BANDOS.get(pierde, "???")
                for b, w in ((bg, 1), (bp, 0)):
                    g, p = rec.get(b, (0, 0))
                    rec[b] = (g + w, p + (1 - w))
                if bg != bp:
                    k = tuple(sorted((bg, bp)))
                    a, b_ = h2h.get(k, (0, 0))
                    h2h[k] = (a + (1 if bg == k[0] else 0), b_ + (1 if bg == k[1] else 0))
        lines.append(f"- **{etiqueta}**: "
                     + " · ".join(f"{k} {v[0]}-{v[1]}" for k, v in sorted(rec.items()))
                     + (" | head-to-head: " + ", ".join(
                         f"{k[0]} {v[0]}-{v[1]} {k[1]}" for k, v in sorted(h2h.items())) if h2h else ""))

    # Tabla lista para PEGAR en WhatsApp: monoespaciado con ``` (formato
    # nativo de WhatsApp, no markdown), alineada para pantalla de teléfono.
    # Orden por PORCENTAJE, no por victorias: 6-12 no va arriba de 5-3.
    orden = sorted(rec.items(), key=lambda kv: -kv[1][0] / max(1, sum(kv[1])))
    ancho = max(len(ETIQUETA.get(k, k)) for k, _ in orden)
    tabla = ["```", f"{'BANDO'.ljust(ancho)}   G -  P    %", "-" * (ancho + 16)]
    for b, (g, pp) in orden:
        pct = g / max(1, g + pp)
        tabla.append(f"{ETIQUETA.get(b, b).ljust(ancho)}  {g:>2} - {pp:>2}  {pct:.3f}"
                     .replace("0.", " ."))
    tabla.append("```")
    lines.append("\n### Tabla para WhatsApp (copiar tal cual, con los backticks)")
    lines.append("\n".join(tabla))

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
    _limpiar_cache()
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
