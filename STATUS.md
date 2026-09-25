# Project Status

*Living document — update at the end of any session that changes strategy,
tooling, or league state. Last updated: **2026-09-24** (jueves de la semana 3,
antes del TNF Green Bay–Atlanta; boletín diario de la noche incluido).*

**Lo grande de hoy: NADA DE LO ORDENADO AYER SE EJECUTÓ Y EL MERCADO SE MOVIÓ.**
Las dos casillas vacías de la Gallamijos siguen en 0.0 por tercera semana y
**Edgerrin Cooper** —la recomendación #1 de ayer— se lo llevó My Son Dave hoy
a las 15:05 como agente libre; en Guillotine **Emanuel Wilson** se fue en **$10**
(el plan decía $231) sin que se metiera ninguna puja. Lección de proceso, no de
análisis: en esa liga los claims ganadores cierran en $0-$16, así que las pujas
se dimensionan contra ese mercado observado y no contra la escalera cruda.

**Dos fallos del boletín del 23 revertidos con información nueva:** (1) **Zach
Ertz se QUEDA** — firmó con Philadelphia el 22 y Sleeper ya lo lista TE dc1 con
Goedert en Doubtful, así que la orden de tirarlo estaba mal (la regla de
"resolver POR QUÉ un jugador es trending antes de descartarlo" era justo la que
faltaba aplicar); (2) el LB de la Gallamijos ya no es Cooper sino **Terrel
Bernard**, que además ya pasó waivers.

**Estado del portafolio (verificado en vivo hoy):** Gallamijos Lg sigue con LB
y DB en cero (17/17, y `allow_out`/`allow_doubtful` en 0 = NADIE de ese roster
es elegible de IR); MEXICA sigue con DL vacío (19/19, `reserve_slots=0`, sin IR
en absoluto) y con riesgo de una segunda casilla muerta si Devin Lloyd sale OUT
el viernes. DYNASTY TRC tiene 7.8 puntos en la banca que no dependen de sus dos
receptores lesionados. MEXICA y LoR 2-0; las otras cuatro 1-1.

## What this project is

Claude acts as the user's (elmijo, user_id 214122236888477696) fantasy
football expert across 8 Sleeper leagues. Sleeper's API is read-only, so the
loop is always: **Claude analyzes → user executes in the Sleeper app.**
`CLAUDE.md` holds the operating playbook; this file holds current state.

## League portfolio (2026)

| League | Format | Status | Strategy |
|---|---|---|---|
| FANTASY MEXICA | 18t, half PPR, 6pt paTD, IDP, keeper | **in_season — DRAFTED (slot 10)** | Post-draft: Kenneth Walker (1.10) + Bowers (2.27) + Garrett Wilson (3.46); Shough kept at R10 as the starting QB with Daniel Jones behind him. Pre-draft plan preserved at `reports/2026/draft/fantasy-mexica-draft-plan.md`. K. Walker's foot (Q) is the live risk. |
| Gallamijos League | 18t, full PPR + bonos de yardaje (100/200 rush-rec, 300/400 pase — NO es PPFD), IDP · **waivers por PRIORIDAD DE TABLA desde 2026-09-23** (antes rodantes) | **in_season — DRAFTED from slot 2**. Took Ja'Marr Chase at 1.02 (the user's call over the checklist's RB anchor), then Swift/Egbuka/Dobbins/MHJ. ⚠️ **DL starting slot left EMPTY** — see pending actions. | Post-draft: WR-anchored (Chase / Egbuka / MHJ) with a five-deep RB room (Swift, Dobbins, Corum, Marks, Mitchell) and Mayfield at QB. Two DEFs carried for two-week-ahead streaming, per the 18-team rule. Egbuka's turf toe is the live Week-1 risk. |
| 🪓 Guillotine MX | 18t, superflex, 6pt paTD | ⚠️ **USER NOT IN LEAGUE** — drafted 2026-09-06 with 18 rosters, none his (found 9/9). config.json still lists it; re-run setup_user.py or confirm intentional. | — |
| 🪓 Guillotine TRC | 18t, full PPR, 1QB, $1000 FAAB | **in_season — DRAFTED 2026-09-08** (14/14: Lamar, Gibbs, G.Wilson, Godwin, Likely, MHJ, Shakir, Marks, Willis, Tucker, Dotson, Kolar, Saylors, Kaleb Johnson) | Survive weekly; $1000 FAAB untouched — hoard for the post-Week-1 cut wire. Week 1: Tre Tucker over MHJ in the flex (+1.2). |
| Dynasty Mexica | 12t, half PPR | in_season, **#1 of 12** | Win-now. Burrow UNTRADEABLE (Bengals fan) — he's Maye insurance; TE surplus (LaPorta) is the RB2 trade capital |
| DYNASTY TRC | 10t, full PPR (co-owned w/ charlyae17) | in_season, #7 of 10 | One move away: **Lloyd-for-Odunze to RGV95 (rebuilt 9/9, +36.5; Goff version is the fallback — RGV95 carries three QBs)**; Burrow untouchable |
| League of Record | 12t, **dynasty**, TE-prem, 6pt paTD | in_season, #8 of 12 | Stroud is the trade chip; Bowers untouchable; RB is the hole. (Confirmed settings.type=2 — apply dynasty rules here, incl. dynasty-value waivers and trade-posture framing.) |
| Gallamijos Dynasty | 12t, full PPR | in_season, #10 of 12 | Rebuild: sell Mahomes/Montgomery for youth + 2027 firsts (offer out to ElGeneral4 for Jeanty) |

## Key decisions & standing rules (chronological)

1. **FANTASY MEXICA scoring override**: RESOLVED 2026-08-25 — Sleeper now
   returns `idp_tkl_ast: 0.5` natively (commissioner fixed the 5.0 typo);
   the config.json override was removed per this rule. The 5-pt-assist IDP
   edge no longer exists; the IDP board exclusion stands on its own merits.
   `get_league_corrected()` remains the read path (no-op without overrides).
2. **Shough keeper locked** (user confirmed unchangeable) — R10 pick #171.
3. **Ranking rules R1-R15 agreed with user** (see conversation-derived rules
   in CLAUDE.md): projections re-scored per league, VORP via league-wide
   greedy fill, intel caps (±5% environment, -2% cold-Dec, ±15% research
   with written reason), ECR tripwire at 15+ spots, tiers at 12+pt cliffs.
4. **NO ad-hoc individual player adjustments** — user explicitly banned
   nudging single players to match consensus (e.g. McBride was left T2
   despite expert buzz). Only systematic rules, or explicit user request.
   The coaching-scheme adjustments (Shough, McConkey, Herbert, Flowers,
   Andrews, Ward, Egbuka, Godwin, D.Smith) predate/comply. Aug 22: user
   approved a batch of 10 expert-layer FACT-based adjustments (JCM +6%,
   Golden +5%, Walker/Watson/Odunze +4%, Hall +3%, Gadsden -6%,
   Hubbard/Pierce -5%, Shough trimmed +6%→+3% on the Tyson injury) — all
   in `player_adjust.json` with written reasons. Standard: real-world
   info (usage/role/injury) only, never opinion.
5. **Risk index is systematic** (age curves + durability + injury +
   volatility), shaves ≤12% of positive VORP before ranking. Never hand-tune.
6. **Elite = capped top-3 by VORP within tier 1 per position**, excludes K
   everywhere and DEF in dynasty leagues (2026-08-24: DEF is a streaming
   commodity there — a crown invites paying up for one).
7. **Travis Hunter positional fix**: `analysis.canonical_pos()` prefers
   offensive tags for two-way players — never take `fantasy_positions[0]` raw.
8. **IDP excluded from all boards** (2026-08-24, user decision): DL/LB/DB
   are single-starter slots with bottomless depth — ranking them alongside
   offense distorted the offensive board and the Value column (all-position
   rank vs offense-only ADP; Tre' Harris was "rank 508" in MEXICA with 314
   defenders above him, rank 225 after). `analysis.IDP_BOARD_EXCLUDE` filters
   board rows + starter-fill slots; weekly lineup optimization still covers
   IDP starters. Fill IDP slots with final-round picks/waivers. If MEXICA's
   assist scoring ever really plays at 5.0, re-enable deliberately for that
   league (see draft plan standing rules).

### Decisiones nuevas del 2026-09-23

1. **Waivers de la Gallamijos por tabla** (user, es el comisionado): el orden
   se resetea cada semana al inverso de la tabla. Verificado que
   `waiver_type` 2 = FAAB contrastando las 8 ligas (las 6 de tipo 2 tienen
   bids reales, las 2 de tipo 1 tienen cero), y que el 0 era rodante porque
   la simulación con esa regla reprodujo **19 de 19** ganadores reales.
2. **"Puntos dejados en la banca" = RECUPERABLES, no la suma de la banca**
   (user): es *lineup óptimo − marcador real*. El cálculo viejo sumaba dos QB
   cuando solo se alinea uno e inflaba las cifras al doble o triple (la
   Dinastía: 1,155 inflado vs **390.5** real). `roast_facts.py` publica el
   campo RECUPERABLE con quién debió entrar.
3. **Mapa de bandos fijado** (`BANDOS` en roast_facts.py + tabla en
   miroslava.md): el dato estaba disperso en tres lugares del canon y por eso
   una edición salió sin Marcador de la Guerra. Validado contra los conteos
   del canon (4/9/5 y 5/5/2) y contra los récords ya publicados.
4. **Prohibido el ángulo "sale con foto"** en el Destape (user); las
   metáforas de cinematografía SÍ pasan. Con chequeo mecánico en el linter.
5. **No mezclar ligas** en el Destape: roles y plantillas son por liga (el
   Bebé es commish de la Dinastía, no de la redraft; Pancho solo juega
   Dinastía).

## Tooling state (all working, audited across all 8 leagues)

**Full-system audit 2026-08-25 (4 parallel agents: library code, scripts/
dashboard, data-vs-API facts, doc consistency) — all findings fixed same
night**: optimal_lineup is now EXACT (DP assignment; greedy mis-slotted
dual-eligible players) and weekly reports exclude taxi/IR from lineups and
bench math; draft reports run the same risk pipeline as the dashboard
(`analysis.apply_standard_risk` — one pipeline, coherent ranks); power
rankings align all-play strictly by week; ADP-999 sentinel filtered;
send_newsletter rejects unknown flags (a bare `--help` used to SEND the
email); dashboard waiver rulings now ALWAYS render (injected when auto
signals miss them, name-matching normalized) and league-switch races can't
poison caches or paint stale boards; live_draft honors draft type
(linear/reversal_round) and attributes picks by picked_by; roast_facts
falls back to the last played week and prints Spanish dates; expert_watch
--mark refuses unfetched ids. Data fixes: Gainwell take re-teamed PIT→TB,
Waddle take re-teamed MIA→DEN (its Nix caveat was itself the stale part),
80 takes got player_ids and 30 got dates backfilled, two moot skip-rulings
removed (Strand, Davis-DMX both since claimed), team_env now carries
hc+oc+play_caller for ALL 32 teams. KNOWN LIMITATION (accepted): the live
draft pick SCHEDULE ignores traded future picks (attribution is correct);
revisit before the 2027 rookie drafts. Jeanty data flag: Sleeper's
injury field says Knee while its own news wire says low-ankle — offer file
tells the user to re-check news once before accepting.


- **Command center** (`scripts/draft_dashboard.py`, port 8787): Draft Room
  (3-column desktop app-shell, mobile segmented tabs), Rankings
  (search/sort/filter, ownership, tier-break lines, risk column), My Team
  (category filter cards + **🤝 Trade center**: standing offers from
  `data/intel/trade_offers.json` + algorithmic partner ideas), and
  **🔥 Moves tab** (in-season: FAAB state, drop-it-like-it's-hot scan,
  waiver targets, weakest active bench; pre-draft shows an empty state).
  **👥 Rival roster viewer** (header button lists all teams by projected
  lineup; every manager-name mention anywhere — rankings owner pills,
  drops, trade cards — is a link opening their roster: starters/bench/IR/
  taxi with projections, /api/rosters cached 10 min). Also a **👥 Rivals tab**: rival dropdown
  (record + projected lineup in each option, per-league selection
  remembered) with the full roster inline. **Breadcrumb path bar**
  (terminal-style, monospace): `← League / View / Rival` under the tabs —
  segments clickable (league = that league's Draft Room), ← is true
  history-back, and the URL carries the full path incl. selected rival so
  browser back/forward restores everything.
  League switcher, glossary, custom tooltips, on-clock beep + auto-jump,
  collapsible sections. `/api/moves` caches 10 min (force=1 to refresh).
  Launch config: `.claude/launch.json`. NOTE for the daily task + future
  sessions: `data/intel/trade_offers.json` is the single source of truth
  for standing offers — update states there (the newsletter and dashboard
  both read it).
- **Live draft engine** (`scripts/live_draft.py`): recs w/ urgency +
  tier-scarcity + balance nudge, round plan (upside/sleeper/safe lanes),
  sleeper queue w/ closing windows, league-winner stashes, risk-adjusted
  boards. CLI + JSON (`compute_advice`).
- **In-season scavenging**: `api.get_player_news(pids)` — Sleeper's own news
  wire (undocumented GraphQL, rotowire/rotoballer; same feed the app shows);
  `analysis.recent_drops(league_id, players, season_proj)` — valuable
  players dropped by other managers still sitting as FAs ("drop it like
  it's hot" — first live scan found Hutchinson dropped in DYNASTY TRC 5
  days before the Higgins ACL news made him the #1 add in fantasy).
- **Intel layer** (`sleeper/intel.py` + `data/intel/*.json`): 32-team Vegas
  win totals, offense tiers, venue/cold-Dec flags, full 2026 coaching map
  (21 new OCs), 19 documented player adjustments.
- **Reports** (`reports/2026/draft/`): VORP boards per league,
  MEXICA draft plan + keeper analysis, archetype playbook.
- **Survivor pool** (`scripts/survivor_plan.py`, 2026-09-17): calendario
  restante con líneas de lookahead de DraftKings vía ESPN, probabilidades
  (moneyline sin vig / spread), y asignación EXACTA equipo-semana sin repetir
  (Hungarian) que maximiza la supervivencia. Regresión del edge por distancia
  y tope de fades al mismo rival. Estado en `data/intel/survivor.json`
  (3 vidas, S1 PIT, S2 pendiente de confirmar).
- **Capa gráfica del Destape** (todo con SVG→`sips`+ffmpeg; el ffmpeg de brew
  NO trae drawtext): `destape_guion.py` (WhatsApp→guion hablado),
  `destape_montaje.py` (video 1080x1920 con escudo, escaleta de cintillos y
  tarjetas, himno en intro y outro), `roast_imagen_guerra.py` (imagen
  1080x1080 del Marcador de la Guerra con Miroslava; corona y 💩 respetan
  empates). Personaje congelado en `data/intel/brand/` (cara, avatar, voz
  "Dani - Podcast Host" en Eleven v3, himno mp3).
- **Comunicados oficiales** (`scripts/comunicado_pdf.py`, 2026-09-23): PDF
  carta membretado (escudo, franja #013369, filete rojo, pie con fecha) desde
  un .txt con marcas simples. Para avisos de comisionado, no para el Destape.
  Salidas en `reports/<season>/comunicados/`.
- **expert_watch con RESPALDO** (2026-09-17): el edge del RSS de YouTube
  404/500 para ambos canales en ventanas completas de la corrida de 9pm
  (9/7, 9/13, 9/16). `fetch_feed` reintenta RSS 10x y cae a la API InnerTube
  browse (pestaña Videos con corte de 10 días + 8 Shorts). `feed_health.via`
  registra qué camino sirvió.

## Pending / next actions

*(Reescritos 2026-09-24 contra el estado en vivo. Los del 23 ya no aplican tal
cual: NINGUNO se ejecutó, y el mercado se movió mientras las casillas seguían
en cero — Edgerrin Cooper y Emanuel Wilson ya tienen dueño.)*

- [ ] 🔴 **GALLAMIJOS LG — LB y DB LLEVAN DOS SEMANAS EN 0.0.** Cooper se lo
  llevó My Son Dave hoy a las 15:05 como AGENTE LIBRE. El mejor LB del wire
  ahora es **Jack Campbell** (DET, 7.7/132) pero lo tiraron hoy a las 08:56 y
  esta liga tiene `waiver_clear_days=1`, así que probablemente esté bloqueado
  hasta el viernes y el user va 10 de 18 en la prioridad por tabla. La jugada
  segura: **Terrel Bernard** (BUF, 6.8/96, ya libre) por **Tyler Badie**, y
  **Dillon Thieneman** (CHI, 6.0/100) por **Roman Wilson**. +12.8/semana.
  Si la app muestra a Campbell con botón **Add**, es Campbell. Woody Marks
  está PROTEGIDO (handcuff limpio detrás de Montgomery, 206).
- [ ] 🔴 **MEXICA — LA CASILLA DL SIGUE VACÍA.** **Byron Young** (LAR, 4.2/79,
  elegible DL y LB) por **Tyler Badie**. 19/19 y `reserve_slots=0`.
- [ ] 🟠 **MEXICA, disparador del viernes:** Devin Lloyd (LB titular) no
  entrenó ni miércoles ni jueves. Si sale OUT, entra **Demetrius Knight**
  (CIN, 6.8/96) y se va **Jonah Coleman**. Waller NO se toca (es el seguro de
  Bowers); Carnell Tate tampoco (21 años, liga de keepers).
- [ ] 🔴 **DYNASTY TRC — 7.8 puntos en la banca, y no dependen de los
  lesionados.** Goff por Bryce Young, Kelce al TE con Kraft al FLEX,
  Rhamondre Stevenson por MarShawn Lloyd, PHI DEF sobre CAR. **Lloyd juega
  el jueves: ese cambio vence en el kickoff.**
- [ ] 🔴 **TRADES CON RELOJ:** (a) Lloyd por Rome Odunze a RGV95 ("PRISON
  MIKE") **antes del kickoff** — Kaleb Johnson tiene más carga anunciada para
  hoy y Lloyd jugó 16 de 59 snaps, detrás de Chris Brooks; (b) **NUEVA**:
  Jalen Coker por Matthew Golden a SpunkyNuggets en LoR (+5.1 de temporada
  para el user, ±0.0 para él), mandarla antes del reporte del viernes.
- [ ] 🟡 **LoR:** Croskey-Merritt por Kamara (+2.9). Coker no entrenó el
  jueves; si sale, entra Jauan Jennings (-6.1). Iosivas sigue sin poder ir a
  IR (`allow_out=0`) — NO cortarlo.
- [ ] 🟡 **GUILLOTINE — lección de precio, no de jugada.** Emanuel Wilson se
  fue en **$10** (el plan decía $231 y no se metió ninguna puja). Los claims
  ganadores de la liga cerraron en $0/$0/$0/$10/$16: dimensionar las pujas
  contra ese mercado (~$25-35), no contra la escalera cruda. **Zach Ertz se
  QUEDA** — firmó con Philadelphia el 22 y Sleeper ya lo pone TE dc1 con
  Goedert en Doubtful; la orden de tirarlo del 23 quedó revertida.
- [ ] 🟡 **Vigilancias de IR:** Gallamijos Dyn tiene UN lugar libre (22/23);
  Caleb Williams (no entrenó, no se espera el lunes) y Rico Dowdle (sin
  uniforme) pasan a ser elegibles de IR en cuanto el tag diga Out
  (`allow_out=1` ahí).
- [ ] 🟡 **SURVIVOR — sigue sin confirmar el pick de la semana 2** (Tampa
  Bay sobre SF). Anotarlo en `data/intel/survivor.json` y recorrer.
- [ ] **Ofertas con estado desconocido en Sleeper: ElGeneral4 y Jro91** —
  tercera edición preguntando.
- [ ] **Bitácoras del canon**: mover a "libre" los términos que ya
  descansaron una edición (`criaturas`, `humanos promedio`, `señores del
  fantasy` salen del descanso tras la edición del 09-29).
- [ ] **Pendiente de método**: el cupo real de cada manager en el escenario
  de waivers no es "las bajas que hizo" sino "cuántas habría estado dispuesto
  a hacer" — Sleeper NO guarda el drop de un claim perdido, así que eso solo
  se resuelve preguntando.

- [x] **Play-callers de BAL y NYG ya NO son "presumidos"** — Declan Doyle
  (confirmado 2026-09-02, sitio de los Ravens) y Matt Nagy (confirmado
  2026-09-07, encuesta de ESPN + The Ringer). Se elimina el caveat.
- [x] **Computable features from expert methods** — built (Aug 22):
  (a) '25 usage shares (target/carry/snap) on every board + sortable
  Rankings column (`sleeper/usage.py`); (b) vacated-opportunity accounting
  (`scripts/vacated_report.py` → report + team_env fields; validated vs
  Sal's on-air numbers — GB 37.4% vs his "37%"); (c) draft-slot value
  tables (`analysis.slot_values`) in every pre-draft board report.

## Known quirks / gotchas

- Sleeper 404s on empty draft-picks lists — handled in `api._fetch` (returns
  None). All callers use `or []`.
- Dashboard port 8787; kill stale processes if `preview_start` reports the
  port busy. LAN IP for phone access changes between sessions.
- DYNASTY TRC: user is co-owner (roster owner charlyae17) — `slot` is None
  in draft data; roster resolution handles co_owners. **Ojo al escribir
  scripts nuevos**: buscar el roster del user SOLO por `owner_id` pierde
  DYNASTY TRC y Guillotine TRC; hay que mirar también `co_owners` (me pasó
  el 2026-09-23 y reporté dos ligas como "no participas").
- **Waivers, hallazgos del 2026-09-23** (de volcar el objeto completo):
  · `waiver_type`: **0** = rodante, **1** = prioridad por tabla, **2** =
    FAAB (confirmado empíricamente: las 6 ligas de tipo 2 tienen bids, las
    de tipo 1 tienen cero).
  · Un claim FALLIDO trae `drops: null` **siempre** — Sleeper no guarda a
    quién ibas a tirar si perdiste. No es recuperable, solo preguntable.
  · Pero sí trae `metadata.notes` con la razón exacta del fallo ("This
    player was claimed by another owner" vs "your roster will have too many
    players"). Vale más que cualquier inferencia: distingue perder en la
    fila de quedarse sin cupo.
  · Los ganados traen a veces `settings.priority`, pero solo en 7 de 19 —
    no sirve para reconstruir la fila. Para eso, el orden de proceso (`seq`)
    sí funciona: reprodujo 19/19.
  · La ronda (`leg`) de una transacción es la semana ANTERIOR a la que se
    juega: las waivers del miércoles 23 están en la semana 2.
- **ffmpeg de Homebrew NO trae drawtext** (sin libfreetype): todo texto en
  video/imagen se rasteriza de SVG con `sips`, que sí usa las fuentes del
  sistema y renderiza emoji a color. Las barras del letterbox de HeyGen son
  BLANCAS: `cropdetect` necesita `negate` antes.
- `data/cache/` is gitignored API cache (delete to force refresh);
  `data/intel/` is curated and committed.
- **Git push**: the machine's active gh account is `antonioLBR`, but this
  repo belongs to `AntonioCF5` (both are logged into gh). To push:
  `gh auth switch --user AntonioCF5 && git push && gh auth switch --user antonioLBR`.
