# Project Status

*Living document — update at the end of any session that changes strategy,
tooling, or league state. Last updated: **2026-09-22** (expert-daily 9/22 —
Tuesday of Week 3, waivers clear tonight. 5 videos / 77 takes (Sal panic-meter
+ FF Ep. 1977 Week-3 waivers + 3 shorts). TWO REVERSALS of the 9/21 rulings:
(1) Terrance Ferguson is OFF the Gallamijos Lg drop board — FF call him the
#1 overall pickup if Nacua needs hernia surgery and the mechanism tested clean
(36/62 snaps, 9 tgt, 6-54-TD with Nacua out); claims re-rank to Starks →
Gadsden → Jonah Coleman. (2) Guillotine's $451 moves off Nacua onto TreVeyon
Henderson (+ Flowers $201) — McVay "not sure" on Nacua, and guillotine spots
must produce now. Dobbins had LEG CRAMPS, not a hamstring (Klis), which
demoted the Coleman claim. Bowers expected to debut Week 3 → starts in MEXICA
and LoR. Dowdle day-to-day so his IR move is cancelled; Tua logged a full
practice and must come off Gallamijos Dyn IR when his tag lifts.)*

## What this project is

Claude acts as the user's (elmijo, user_id 214122236888477696) fantasy
football expert across 8 Sleeper leagues. Sleeper's API is read-only, so the
loop is always: **Claude analyzes → user executes in the Sleeper app.**
`CLAUDE.md` holds the operating playbook; this file holds current state.

## League portfolio (2026)

| League | Format | Status | Strategy |
|---|---|---|---|
| FANTASY MEXICA | 18t, half PPR, 6pt paTD, IDP, keeper | **in_season — DRAFTED (slot 10)** | Post-draft: Kenneth Walker (1.10) + Bowers (2.27) + Garrett Wilson (3.46); Shough kept at R10 as the starting QB with Daniel Jones behind him. Pre-draft plan preserved at `reports/2026/draft/fantasy-mexica-draft-plan.md`. K. Walker's foot (Q) is the live risk. |
| Gallamijos League | 18t, full PPR + bonos de yardaje (100/200 rush-rec, 300/400 pase — NO es PPFD), IDP | **in_season — DRAFTED from slot 2**. Took Ja'Marr Chase at 1.02 (the user's call over the checklist's RB anchor), then Swift/Egbuka/Dobbins/MHJ. ⚠️ **DL starting slot left EMPTY** — see pending actions. | Post-draft: WR-anchored (Chase / Egbuka / MHJ) with a five-deep RB room (Swift, Dobbins, Corum, Marks, Mitchell) and Mayfield at QB. Two DEFs carried for two-week-ahead streaming, per the 18-team rule. Egbuka's turf toe is the live Week-1 risk. |
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

- [ ] 🔴 **GALLAMIJOS LG WAIVERS (2026-09-22, re-ranked, priority 14/18):**
  Malaki Starks DB (drop Malachi Fields) → Oronde Gadsden TE (drop Kenyon
  Sadiq) → Jonah Coleman RB (drop Baker Mayfield; Winston 14.4 is wire QB
  insurance). **Terrance Ferguson is PROTECTED** — he was yesterday's named
  drop and is now FF's contingent #1 overall pickup pending Nacua's status.
  Lineup unchanged: Shough at QB, LAR DEF.
- [ ] 🔴 **GUILLOTINE TRC chop wire (co-owned — alealvarez7 keys the bids):**
  TreVeyon Henderson **$451** (drop Singletary), Zay Flowers **$201** (drop
  Hutchinson). SKIP Nacua (reversal), Etienne, Kraft, Dowdle, Stafford.
  $348 stays banked; largest bid landed in this league all year is $400.
- [ ] 🔴 **DYNASTY TRC: send Stevenson + Tre Tucker for Jameson Williams**
  (jetsdelalaguna) tonight — Sal has Stevenson at 6/10 "sell for whatever,"
  Henderson has taken the job, and DJ Moore + Nico Collins are both Out.
  Lineup: Goff over Burrow, Kelce at TE, GB DEF for TNF (set Thursday).
- [ ] 🔴 **GALLAMIJOS DYN:** ACCEPT ElGeneral4 (Jeanty + Flowers). DeeJay
  Dallas $3 optional (21/23, two open spots, no drop needed). **Compliance
  watch: Tua logged a full practice Tuesday — move him off IR the day his
  Out tag lifts or the roster goes illegal.** Flex: Adonai Mitchell unless
  Dowdle practices full Friday.
- [ ] **MEXICA:** no Wednesday claim. Bowers starts over Mayer (+7.5); hold
  Mayer until Friday's designation, then he is the drop. Caleb Douglas'
  ankle is the Wednesday tripwire. **Handcuff note: LaloCura owns Emmett
  Johnson, the handcuff to your Kenneth Walker — buy him cheap now (FF:
  must-roster; Reid is actively cutting Walker's 535-opportunity pace).**
- [ ] **LoR:** no claims (28/28 with four Out players and reserve_allow_out=0,
  so no IR path). Bowers starts over Parkinson (+7.8). The eventual cut is
  Jauan Jennings (29), NOT rookie Camden Brown.
- [ ] **Dynasty Mexica:** lineup optimal; set London before TNF (Penix
  starts). Loveland stays benched (Sal 10/10 concern).
- [ ] **Unknown offer states** — ElGeneral4 and Jro91: ask the user whether
  they are still live on Sleeper.
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
