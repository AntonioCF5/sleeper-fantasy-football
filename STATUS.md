# Project Status

*Living document — update at the end of any session that changes strategy,
tooling, or league state. Last updated: **2026-08-25** (preseason final
week; Gallamijos draft dom 30 ago; Destape de Miroslava completo;
expert-daily 8/25 run refreshed trades + claims).*

## What this project is

Claude acts as the user's (elmijo, user_id 214122236888477696) fantasy
football expert across 8 Sleeper leagues. Sleeper's API is read-only, so the
loop is always: **Claude analyzes → user executes in the Sleeper app.**
`CLAUDE.md` holds the operating playbook; this file holds current state.

## League portfolio (2026)

| League | Format | Status | Strategy |
|---|---|---|---|
| FANTASY MEXICA | 18t, half PPR, 6pt paTD, IDP, keeper | **pre_draft, slot 10** | Hero RB + early QB (Lamar @27). Keeper: Tyler Shough @R10 (locked, poor value, +6% Kellen Moore thesis applied). Full plan: `reports/2026/draft/fantasy-mexica-draft-plan.md` |
| Gallamijos League | 18t, full PPR + PPFD, IDP | **DRAFT: dom 30 ago 12pm, slot 2/18, snake 17R** | Hero RB → WR flood → late-round QB. Picks: 2, 35/38, 71/74, 107/110, 143/146, 179/182, 215/218, 251/254, 287/290 (pares por la vuelta del snake). Tarea `draft-morning-gallamijos` corre 8:30am ese día (checklist completo + plan file) |
| 🪓 Guillotine MX | 18t, superflex, 6pt paTD | pre_draft, **order not set** | QB Hammer: 3 QBs in first 5 picks |
| 🪓 Guillotine TRC | 18t, full PPR, 1QB, $1000 FAAB | pre_draft, **order not set** | Robust RB floor + QB R7-9; hoard FAAB |
| Dynasty Mexica | 12t, half PPR | in_season, **#1 of 12** | Win-now. Burrow UNTRADEABLE (Bengals fan) — he's Maye insurance; TE surplus (LaPorta) is the RB2 trade capital |
| DYNASTY TRC | 10t, full PPR (co-owned w/ charlyae17) | in_season, #7 of 10 | One move away: Goff is the tradeable QB surplus (Burrow untouchable) → WR2/TE; pounce trigger armed |
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

## Tooling state (all working, audited across all 8 leagues)

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
  (21 new OCs), 9 documented player adjustments.
- **Reports** (`reports/2026/draft/`): VORP boards per league,
  MEXICA draft plan + keeper analysis, archetype playbook.

## Pending / next actions

- [ ] **STANDING TRADE OFFERS — refreshed 2026-08-25, user to send** (full
  packages + pitch scripts in the 2026-08-25 newsletter "Recommended
  trades"; single source of truth is `data/intel/trade_offers.json` —
  update state there AND here as sent/countered/dead):
  UNTOUCHABLES (user, 2026-08-24): **Joe Burrow — never tradeable, any
  league (Bengals fan)**; **Blake Corum — keep** (young, real LAR path).
  1. Dynasty Mexica → Juliosg: LaPorta for D'Andre Swift (ask) or Etienne
     (fallback, weakened — FF's official bust of the year). You +2.6, them
     -6.4. LaPorta practiced 8/25, so the hip discount a buyer would argue
     for is gone — send now. Never ask Walker (-42 their side).
  2. League of Record → Gernant88: Stroud for Breece Hall (you +66.9, them
     -16.3); fallback Bucky Irving (you +54, them -3) but **push Breece** —
     FF report Gainwell has LOCKED the TB pass-catching role, second
     straight day the Irving fallback lost value. Their QB2 is Flacco.
  3. DYNASTY TRC → RGV95: Goff for Rome Odunze (you 2087.9→2124.4, them
     2100.7→2100.3). Fallback Marvin Harrison (you +15, them ±0). He isn't
     QB-needy, he's WR-choked (7 WRs at 160+ into 4 skill slots). **Pounce
     trigger stays retired** — Geno Smith (242) is still a FA there, so no
     QB scarcity premium exists.
  4. Gallamijos Dynasty → jetsdelalaguna (**NEW 8/25**): David Montgomery
     for Marvin Harrison Jr. — you 1831→1778 (-53, correct for a rebuild),
     them 1721→1756 (+34). Most RB-starved roster in the league carrying
     FOUR QBs in a 1QB format. Aggressive version: Montgomery for Tre'
     Harris + Jordyn Tyson (still +78 for him). Never settle below one
     24-and-under asset.
  5. Gallamijos Dynasty → alealvarez7 (**NEW 8/25**): Patrick Mahomes for
     Bhayshul Tuten — them -6 (Coker version ±0: a QB2 never starts in a
     1QB league, so it's pure insurance). His QB room is Jayden Daniels
     backed by Deshaun Watson (96) — a 200-pt cliff. Your side: Mahomes has
     a -52.3 value gap and -9.1 VORP there = textbook sell-high.
  6. ~~Gallamijos Dynasty → ElGeneral4: Mahomes + Montgomery for Jeanty~~
     **DEAD 2026-08-25.** Rapoport has Jeanty's ankle "more low than high,"
     Kubiak says "on the mend" — the buy-low window shut on exactly the
     trigger the 8/24 edition named. Recomputed it is **-27.8 to their
     starting lineup** (their QB1 Jaxson Dart projects 285 vs Mahomes 275),
     i.e. an auto-decline. Superseded by items 4 and 5.
- [ ] **EL DESTAPE DE MIROSLAVA — COMPLETO Y CALIBRADO, esperando semana 1**:
  canon único en `data/intel/miroslava.md` (personaje, 6 reglas duras incl.
  coherencia interna con pase final, secciones todas bautizadas, 21 managers,
  palmarés redraft 2015-2025 COMPLETO — Mijos 8/SB 2/Gallas 1 —, bitácora de
  lecciones editoriales con 8 correcciones del user). Ediciones 0 (v5)
  aprobadas y enviadas por correo para estreno en los grupos. Tarea martes
  7:30am con gate de semana jugada + on-demand ("roast" en chat). La primera
  edición real: martes post-semana 1, con edición especial post-draft de La
  Gallamijos disponible si el user la pide el domingo/lunes.
- [ ] **Phase-system build items (before week 1)**: (a) lineup optimizer
  ceiling mode for weeks 15-17 (prefer boom/bust when projections close);
  (b) newsletter start/sit-deltas section (task prompt already carries it);
  (c) weekly report notes phase framing. Methodology already in CLAUDE.md
  "The manager".
- [ ] **Draft dates**: Gallamijos League SET (dom 30 ago 12pm — tarea de
  checklist programada). MEXICA + both Guillotines still unscheduled. When
  one is set →
  run the draft-morning checklist (CLAUDE.md pre-draft checklist: fresh ADP,
  injury sweep, ECR cross-check, Vegas moves, re-simulation) + dry-run the
  dashboard with the user ~10 min before.
- [ ] **Guillotine MX & TRC**: commissioner hasn't randomized draft order —
  recs/round-plan appear automatically once slot is known.
- [x] **COACHING DATA — VERIFIED ALL 32 (2026-08-25)**: 4-agent web sweep vs
  team sites/ESPN/NFL.com confirmed every HC/OC in `team_env.json`; added a
  `play_caller` field for all 32 (13 offenses where the caller ≠ OC — key
  scheme reads on the caller, not the OC résumé). ATL HC filled (Stefanski;
  Rees calls plays) and **Pitts +8% written to player_adjust.json** on the
  Stefanski TE-usage thesis (26%+ six straight years, 32% in '25; capped
  below +15 for the Tua/Penix QB mess). ARI HC filled (Mike LaFleur, who
  CALLS the plays — the old Hackett-fade mechanism was void and is
  rewritten). SEA resolved: Fleury confirmed OC + first-time caller,
  Kubiak-scheme continuity with execution risk. Only unverified play-callers:
  BAL (Doyle presumed), NYG (Nagy presumed) — recheck week 1.
- [x] **FANTASY MEXICA assist scoring**: RESOLVED — Sleeper now returns 0.5
  natively; config.json override removed (see standing rule 1).
- [ ] **In-season (from week 1)**: weekly cadence per CLAUDE.md — waivers
  Mon/Tue, lineup calls, trending adds. Candidate feature: lineup/start-sit
  view in the dashboard (user deferred until closer to week 1).
- [x] **Expert layer run — automated (2026-08-22, moved to daily-weekday 2026-08-22)**:
  scheduled task `expert-layer-weekly` runs 9:08pm local Mon-Fri
  (`~/.claude/scheduled-tasks/expert-layer-weekly/SKILL.md`), late enough
  that each day's FF content is already posted (FF cadence: Tue waivers,
  Wed = Thu-Night-Football analysis, Thu/Fri = rest of the slate; Sal's
  cadence is less fixed). Does expert_watch --check/--fetch-new → subagent
  distillation → expert_takes.json merge/prune → --mark → commits + pushes
  ONLY data/intel/expert_takes.json, expert_state.json, expert_methods.md.
  Hard-fenced from player_adjust.json — never makes projection adjustments
  unattended; flags anything adjustment-worthy back to this checklist for
  the user to decide live. Runs independently of interactive sessions now,
  in addition to the existing "check at start of every session" rule.
  Quiet weekends/Mondays are expected, not a failure.
- [ ] Commit generated reports after each draft so history shows how calls aged.
- [ ] **Waiver claims — CURRENT SET 2026-08-25** (source of truth:
  `data/intel/waiver_claims.json`; dashboard Moves tab overlays it):
  DYNASTY TRC — **CLAIM Barion Brown (22) $9, drop Trey Benson** (now
  settled: cleared waivers, all 31 teams passed, season-ending IR, and this
  league has no IR slots so he is a dead bench spot); **CLAIM Xavier
  Hutchinson (26) $13, drop James Conner (31)** — UPGRADED from optional
  because the reason for Monday's downgrade resolved in reverse: FF's
  unnamed "Texans WR2 is undraftable" segment got a name on 8/25 and it was
  positive ("could very well be the starter from day one despite the Boutte
  trade"). Vele/Malik Davis/Ryan Flournoy = skip. Gallamijos Dynasty —
  **CLAIM Colbie Young (24) $5, drop Mack Hollins (32)**: leads CIN in
  preseason targets AND yards, officially WR4 pushing Iosivas; skip Darius
  Slayton (29) and Waller (33) per the dynasty-value rule. Dynasty Mexica
  and League of Record — no claims (Hutchinson + Barion Brown already
  landed in DMX; the LoR wire is TE-only and Joe Royer has no path through
  22yo Harold Fannin).
- [ ] *(superseded)* **Waiver claims recommended 2026-08-22, CORRECTED for dynasty value
  (user executes in Sleeper)**: DYNASTY TRC — add Hutchinson (26) / drop
  James Conner (31, Q); optional add Vele / drop Jennings (29) or Parkinson
  (27), user's call. Dynasty Mexica — add Hutchinson / drop Tillman (stalled
  yr-3); SKIPPED Malik Davis (journeyman points-chase). Gallamijos Dynasty —
  no claims (Waller cancelled: 33yo points don't move a rebuild). League of
  Record — no claims (Stroud trade is the fix). Original version wrongly
  targeted taxi-squad rookies as drops — taxi/IR players don't consume bench
  spots. New standing rule in memory (dynasty-value-waivers) + scheduled
  task. Beat note: Malik Davis named DAL RB2 favorite — contradicts Sal's
  Jaydon Blue handcuff take; Blue watch-list only.
- [ ] **Expert-daily review candidates (2026-08-25 edition)**:
  (a) **GALLAMIJOS LEAGUE IS NOT A PPFD LEAGUE — fix before Sunday's draft.**
  `reports/2026/draft/archetype-playbook.md` line 32 labels it "full PPR +
  PPFD" and line 36 builds the R2-R6 WR plan on first downs double-paying
  possession volume. Live settings show every `bonus_fd_*` field at 0.0;
  what it actually has is bonus_rec_yd_100/200 and bonus_rush_yd_100/200.
  Boards were always computed from live settings so no number is wrong —
  but the stated reasoning is, and yardage bonuses tilt toward big-play
  receivers rather than possession slot types. Highest-value open item.
  (b) **Eli Stowers tripwire now fires on BOTH sources** — Sal repeated the
  fade on 8/25 with a beat report ("struggling with NFL physicality, may
  not be active weeks 1-2") while our TE-premium League of Record board
  still shows +63 / rank 176-186. Two independent expert reads vs our board
  = the CLAUDE.md review standard. Likely cause: TE-prem bonus applied to a
  projection assuming a role he doesn't have. User's call.
  (c) **Keaton Mitchell: `league_winners` flags him in ALL 8 leagues** while
  FF call availability the disqualifier and the wire confirms a mild
  setback + two missed practices. Looks like a systematic gap —
  `league_winners` scores contingent role upside but doesn't consult
  `risk_index` (which already has him at 30). Decide whether to wire them.
  (d) Josh Downs is contested BETWEEN sources same-day (Sal targets at ADP
  89, FF say the Keenan Allen signing hits him hardest) and he missed
  practice 8/25 — our positive gap is mostly pre-Allen ADP lag, so it's
  weak evidence either way. Not adjustment-worthy.
  (e) Rashod Bateman is under NFL personal-conduct investigation (up to a
  6-game suspension per FF) — that is the real transmission channel behind
  the Ja'Kobi Lane sleeper call (BAL vac_tgt 27.7%). Single-source with an
  unresolved league process; flagged, NOT written to player_adjust.json.
- [ ] **Expert-daily review candidates (2026-08-24 edition)**: (a) ATL/Pitts
  — see the coaching-gap item above, the highest-value open decision;
  (b) Eli Stowers is a **review tripwire** — our TE-premium board has him
  +74 / rank 176 in League of Record while Sal spent a segment saying he's
  a third-string non-asset (14 snaps with the backups, now a hamstring
  DNP); (c) FF's "Texans WR2" segment never named the player on the day
  Boutte was traded there — unresolved, used only as directional caution.
  Contested-within-FF and therefore NOT tripwires: Jonathon Brooks, Josh
  Jacobs, Kyle Pitts, De'Von Achane.
- [ ] **Expert-daily review candidates (2026-08-22 edition)**: Nabers (back in
  full team drills off ACL — projection may carry a stale discount), MHJ
  (camp usage: 100% preseason wk-1 snaps, 27-spot ADP gap), Garrett Wilson
  (20-spot gap, Geno-volume thesis). All single-source, none acted on —
  decide on draft morning. Etienne is contested *within* FF (bust-risk vs
  can't-stop-drafting) — price-sensitive only.
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
  in draft data; roster resolution handles co_owners.
- `data/cache/` is gitignored API cache (delete to force refresh);
  `data/intel/` is curated and committed.
- **Git push**: the machine's active gh account is `antonioLBR`, but this
  repo belongs to `AntonioCF5` (both are logged into gh). To push:
  `gh auth switch --user AntonioCF5 && git push && gh auth switch --user antonioLBR`.
