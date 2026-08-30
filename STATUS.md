# Project Status

*Living document — update at the end of any session that changes strategy,
tooling, or league state. Last updated: **2026-08-30** (preseason final
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
| FANTASY MEXICA | 18t, half PPR, 6pt paTD, IDP, keeper | **pre_draft, slot 10** | Hero RB + early QB (Lamar @27). Keeper: Tyler Shough @R10 (locked, poor value; Kellen Moore thesis currently +3% tras el recorte por la lesión de Tyson). Full plan: `reports/2026/draft/fantasy-mexica-draft-plan.md` |
| Gallamijos League | 18t, full PPR + bonos de yardaje (100/200 rush-rec, 300/400 pase — NO es PPFD), IDP | **DRAFT: dom 30 ago 13:00 (API), slot 2/18, snake 17R** | **Branch EN DISPUTA**: checklist del 30/8 recomienda ANCLA RB en el 2 (Gibbs si cae, si no Bijan) sobre el Chase que el user eligió el 29/8 — Bijan supera a Chase por 38.0 VORP en simulación de 50 drafts; decisión final del user. Picks: 2, 35/38, 71/74, 107/110, 143/146, 179/182, 215/218, 251/254, 287/290 (pares por la vuelta del snake). Tarea `draft-morning-gallamijos` corre 8:30am ese día (checklist completo + plan file) |
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

## Pending / next actions

- [ ] **STANDING TRADE OFFERS — re-verified live 2026-08-28** (every piece
  still on the correct side; `data/intel/trade_offers.json` is the source of
  truth). **MONTGOMERY CONFLICT RESOLVED 2026-08-28: accept the ElGeneral4
  Jeanty package; the jetsdelalaguna Marvin Harrison offer is SHELVED (not
  dead) and gets sent only if the Jeanty deal collapses.** The alealvarez7
  Mahomes-for-Tuten ask stays DEAD and got more expensive on 8/28 (Sal named
  Tuten the #1 league-winner at RB in all of fantasy) — do not reopen.
  Judkins health verified on the Jro91 offer (Thursday's absence was rest). Details below,
  refreshed 2026-08-25, user to send** (full
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
- [x] **FF feed flakiness — INVESTIGATED AND FIXED 2026-08-29**: diagnosed
  properly instead of retrying a third time. Findings: the FF `channel_id`
  is correct and the feed is healthy (6/6 clean fetches on manual test,
  both channels) — the misses are genuine upstream edge flakiness at the
  moment of the 9:08pm run, not a code bug. **But the retry loop had a real
  defect**: uncapped linear backoff (`sleep(1+attempt)`) made a full 25-retry
  cycle sleep 5.4 min, up to **24 min worst case per channel** with curl
  timeouts — long enough for a run to be abandoned mid-fetch. Backoff is now
  capped at 5s (same 25 attempts, ~2 min, and they actually complete).
  Added `feed_health` per channel in `expert_state.json`
  (consecutive_failures / last_success / last_failure) with recovery and
  miss lines printed, and the daily task now MUST report channel health in
  the Experts section — an absent Experts section can no longer look like a
  quiet day. Escalation rule moved into the code: 3+ consecutive misses on
  one channel prints an investigate-don't-retry warning. An InnerTube browse
  fallback was tested and rejected — the response carries no cleanly
  parseable video list, so no speculative code was added.
  The 3 FF videos missed on 8/28 (incl. Ep. 1960) were caught up manually
  on 8/29 — the weekday-only schedule meant no automatic run would have
  recovered them before Sunday's draft.
- [x] **Expert feed outage 2026-08-27 — RESOLVED 2026-08-28**: was transient
  (feeds responded normally the next check, one-day outage, not a code
  bug — `_fetch_feed` needs no changes). The 3 videos missed that day were
  caught up and distilled: 35 new takes + 23 new facts merged into
  `expert_takes.json`, one methodology lesson added (cross-season/cross-team
  opportunity normalization). One rookie WR take flagged `player_id: null`
  — ASR-garbled name ("De'Jon Kumerow") with no confident match in the
  player DB; left unresolved rather than guessed. **For your review**:
  Gallamijos Dynasty now carries a same-roster-spot conflict — Rico Dowdle
  AND Woody Marks are fresh high-conviction targets while David Montgomery
  (same roster) is a fresh fade ("no upside/shaky floor") — worth a look
  before next week's lineup call. If a future outage repeats on BOTH
  channels a second consecutive day, that's when to investigate the fetch
  code instead of just retrying.

- [ ] Commit generated reports after each draft so history shows how calls aged.
- [ ] **Waiver claims — CURRENT SET 2026-08-28** (`data/intel/waiver_claims.json`
  is the source of truth and ALWAYS wins over this summary). COMPLIANCE FIRST,
  both dynasty rosters re-read live 8/28 and STILL ILLEGAL. **Gallamijos Dyn**
  25/23 + taxi 7/6 — Cowing, Tillman and Will Howard CONFIRMED already cut;
  three remain: **Mack Hollins (32) + Panthers DEF** active, **Tai Felton (23)**
  taxi. Kaelon Black stays a PROTECTED clean handcuff. **DYNASTY TRC** 30/25,
  zero movement — the same five (Brissett 33, Conner 31, Ridley 31, Parkinson
  27, Packers DEF); IR re-read again and still unusable (Out/Sus/NA only, every
  injured body Questionable). THEN: GALD claim **Colbie Young (24) $5 — DROP
  RE-PAIRED to Evan Engram** (Panthers DEF became a compliance cut and cannot
  fund the claim too). New skips 8/28: **Dohnte Meyers (26)** both dynasty
  leagues (the Ja'Marr Chase knee scare that drove his 71.7k adds is already
  closed) and **Mike Gesicki (30)** in GALD. **Jonnu Smith skip is now
  PERMANENT** — Tucker Kraft is full-go for Week 1 (his Sleeper "Knee — ACL"
  tag is last season's Week 9 tear, not a new event), so the "competition for
  Kraft" mechanism is dead. Justice Hill (28), Waller (33), MarShawn Lloyd
  protected-hold, Malik Davis watch in LoR — all unchanged. Dynasty Mexica and
  League of Record: no claims, both legal and full.

- [ ] *(superseded 2026-08-28)* **Waiver claims — SET 2026-08-27** (`data/intel/waiver_claims.json`
  is the source of truth and ALWAYS wins over this summary). COMPLIANCE
  FIRST — both dynasty rosters were re-read live on 8/27 and are STILL
  ILLEGAL; no waiver can process. **DYNASTY TRC** 30 active vs 25 cap → cut
  Brissett (33), Conner (31, now ARI depth 3 at 57.2), Ridley (31),
  Parkinson (27), Packers DEF (IR re-checked and still unusable: 3 slots
  open but the league takes Out/Sus/NA only and every injured body is
  Questionable). **Gallamijos Dynasty** 27 vs 23 + taxi 8 vs 6 → active cuts
  Cowing, Tillman (RELEASED by CLE 8/27, no team), Hollins, Engram; **TAXI
  CUTS CORRECTED 8/27 → Will Howard + Tai Felton**. **Kaelon Black is now a
  PROTECTED clean handcuff and must NOT be cut** — SF depth 2, McCaffrey
  291.0 at depth 1 (Questionable, age 30), best depth-3+ Niner Jordan James
  59.7 (< 80). Will Howard replaces him: PIT QB3 behind Rodgers/Rudolph,
  projects 20.5, and was being evaluated for a concussion 8/27 with Allar in
  line to take QB3 by default. If the Jro91 trade lands, Cyrus Allen leaves
  the taxi → only ONE taxi cut needed (Howard), keep Felton, and it nets +1
  active slot. THEN: GALD claim **Colbie Young (24) $5, drop Panthers DEF**
  (re-verified FA 8/27). Standing skips: Barion Brown DEAD, Xavier
  Hutchinson skip, Justice Hill (28) skip, Darren Waller (33) skip, **Jonnu
  Smith skip NEW 8/27** (44.7k adds but the "competition for Kraft"
  mechanism fails — Kraft TE1 174.4 vs Jonnu 31yo depth 2 at 35.9).
  **MarShawn Lloyd remains a protected hold** in Dynasty Mexica AND DYNASTY
  TRC. Dynasty Mexica and League of Record: no claims, both legal and full.

- [ ] *(superseded 2026-08-27)* **Waiver claims — CURRENT SET 2026-08-26** (`data/intel/waiver_claims.json`
  is the source of truth and ALWAYS wins over this summary). COMPLIANCE
  FIRST — both dynasty rosters are still ILLEGAL and no waiver can process:
  **DYNASTY TRC** 30 active vs 25 cap → cut Brissett (33), Conner (31),
  Ridley (31), Parkinson (27), Packers DEF (IR is unusable — this league
  allows Out/Sus/NA only and everyone left is Questionable). **Gallamijos
  Dynasty** 27 vs 23 + taxi 8 vs 6 → cut Cowing, Tillman, Hollins, Engram;
  taxi Felton + Black (if the Jro91 trade lands: Cyrus Allen leaves taxi so
  only Felton goes, and it nets +1 active → one more cut, Nailor). THEN:
  GALD claim **Colbie Young (24) $5, drop Panthers DEF** (re-paired — Engram
  became a compliance cut). CHANGED 8/26: the **Barion Brown claim is DEAD**
  (RGV95 rostered him before waivers ran — do not re-bid), **Xavier
  Hutchinson stays skip** (after the five cuts TRC sits exactly 25/25 and
  every remaining body is startable, a protected handcuff, or a 23yo stash),
  **MarShawn Lloyd is a protected hold in Dynasty Mexica AND DYNASTY TRC** —
  Packers GM Gutekunst confirmed on the record they are preparing for a Josh
  Jacobs suspension, he is the #1 add in fantasy (171,684), and the
  clean-handcuff test passes on live data (Jacobs 202.6 at depth 1, best
  depth-3+ Packer 56.3; Emanuel Wilson left for Seattle). New skips: Justice
  Hill (clean Henry handcuff but 28 on a rebuild), Darren Waller (33).
  Dynasty Mexica and League of Record: no claims, both legal and full.
- [ ] *(superseded 2026-08-26)* **Waiver claims — SET 2026-08-25 (corrected by the
  roster-compliance audit; `data/intel/waiver_claims.json` is the source of
  truth and ALWAYS wins over this summary)**: FIRST the compliance cuts —
  rosters were over limit and waivers can't process until legal. DYNASTY
  TRC (was 30/25): cut Brissett, Conner, Parkinson, GB DEF, Ridley; Benson
  moved to IR by the user (the league HAS 4 IR slots — an earlier version
  falsely said none and ordered dropping him; corrected). Gallamijos
  Dynasty (was 27/23 + taxi 8/6): cut Cowing, Tillman, CAR DEF, Hollins;
  taxi-cut Felton + Black. THEN the Wednesday claims: TRC — **Barion Brown
  (22) $9, drop Brian Robinson**; **Xavier Hutchinson (26) $13, drop
  MarShawn Lloyd** (upgraded: FF named him day-one Texans starter despite
  the Boutte trade). Vele/Flournoy = skip; Malik Davis = skip in TRC but
  WATCH in League of Record (he is the handcuff to the user's Javonte and
  is owned by ExpiredBagels). Gallamijos Dynasty — **Colbie Young (24) $5,
  drop Evan Engram**; skip Slayton (29) and Waller (33) per dynasty-value.
  Dynasty Mexica and League of Record — no claims (LoR is full at 28/28;
  its wire is TE-only, Joe Royer has no path through 22yo Harold Fannin).
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
- [ ] **Expert-daily review candidates (2026-08-26 edition)**:
  (a) **Eli Stowers tripwire has now fired on THREE independent sources** —
  Jimmy Kempski (PhillyVoice) reported 8/26 he may be a game-day inactive
  even once the hamstring clears, joining Sal's and FF's fades, while our
  TE-premium League of Record board still shows +63 / rank 176-186. Second
  consecutive edition. Likely cause unchanged: a TE-premium bonus applied to
  a projection that assumes a role he does not have. Needs a live decision —
  either document why the board stands or adjust with a written reason.
  (b) **Puka Nacua suspension claim is single-source and unverified** — FF
  said he is "facing a possible suspension pending NFL investigation";
  Sleeper's wire attributes his two-week absence from team drills entirely
  to a groin/psoas issue and mentions no investigation. NOT repeated in the
  edition and NOT allowed to move the Terrance Ferguson take. Recheck.
  (c) BAL/NYG play-callers (Doyle, Nagy) are still presumed, not confirmed —
  recheck at week 1 as planned. No coaching changes anywhere on 8/26.
- [ ] **Expert-daily review candidates (2026-08-25 edition)**:
  (a) **RESOLVED same night** — Gallamijos League is NOT PPFD: the
  archetype playbook was corrected (yardage-bonus ceiling tilt, branch
  survives on full-PPR volume), the `scoring.py` presence-vs-value bug that
  generated the false note was fixed, and STATUS's portfolio row updated.
  Boards were always computed from live settings; only prose was wrong.
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
