# Project Status

*Living document — update at the end of any session that changes strategy,
tooling, or league state. Last updated: **2026-08-21** (preseason week 2,
draft season).*

## What this project is

Claude acts as the user's (elmijo, user_id 214122236888477696) fantasy
football expert across 8 Sleeper leagues. Sleeper's API is read-only, so the
loop is always: **Claude analyzes → user executes in the Sleeper app.**
`CLAUDE.md` holds the operating playbook; this file holds current state.

## League portfolio (2026)

| League | Format | Status | Strategy |
|---|---|---|---|
| FANTASY MEXICA | 18t, half PPR, 6pt paTD, IDP, keeper | **pre_draft, slot 10** | Hero RB + early QB (Lamar @27). Keeper: Tyler Shough @R10 (locked, poor value, +6% Kellen Moore thesis applied). Full plan: `reports/2026/draft/fantasy-mexica-draft-plan.md` |
| Gallamijos League | 18t, full PPR + PPFD, IDP | pre_draft, slot 2 | Hero RB → WR flood → late-round QB |
| 🪓 Guillotine MX | 18t, superflex, 6pt paTD | pre_draft, **order not set** | QB Hammer: 3 QBs in first 5 picks |
| 🪓 Guillotine TRC | 18t, full PPR, 1QB, $1000 FAAB | pre_draft, **order not set** | Robust RB floor + QB R7-9; hoard FAAB |
| Dynasty Mexica | 12t, half PPR | in_season, **#1 of 12** | Win-now. Burrow UNTRADEABLE (Bengals fan) — he's Maye insurance; TE surplus (LaPorta) is the RB2 trade capital |
| DYNASTY TRC | 10t, full PPR (co-owned w/ charlyae17) | in_season, #7 of 10 | One move away: Goff is the tradeable QB surplus (Burrow untouchable) → WR2/TE; pounce trigger armed |
| League of Record | 12t, **dynasty**, TE-prem, 6pt paTD | in_season, #8 of 12 | Stroud is the trade chip; Bowers untouchable; RB is the hole. (Confirmed settings.type=2 — apply dynasty rules here, incl. dynasty-value waivers and trade-posture framing.) |
| Gallamijos Dynasty | 12t, full PPR | in_season, #10 of 12 | Rebuild: sell Mahomes/Montgomery for youth + 2027 firsts (offer out to ElGeneral4 for Jeanty) |

## Key decisions & standing rules (chronological)

1. **FANTASY MEXICA scoring override**: league shows `idp_tkl_ast: 5.0` on
   Sleeper — commissioner typo, real value 0.5. Corrected via
   `scoring_overrides` in `config.json`; all analysis uses
   `reports.get_league_corrected()`. If Sleeper gets fixed, remove override.
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
6. **Elite = capped top-3 by VORP within tier 1 per position**, excludes K.
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
  (category filter cards). League switcher, glossary, custom tooltips,
  on-clock beep + auto-jump, collapsible sections. Launch config:
  `.claude/launch.json`.
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

- [ ] **STANDING TRADE OFFERS — built 2026-08-24, user to send** (full
  packages + pitch scripts in the 2026-08-22 newsletter "Recommended
  trades"; update state here as sent/countered/dead):
  UNTOUCHABLES (user, 2026-08-24): **Joe Burrow — never tradeable, any
  league (Bengals fan)**; **Blake Corum — keep** (young, real LAR path).
  1. Dynasty Mexica → Juliosg: LaPorta for D'Andre Swift (ask) or Etienne
     (fallback) — TE surplus buys the RB2; Burrow stays as Maye insurance.
     Never ask Walker (-42 their side, auto-decline).
  2. League of Record → Gernant88: Stroud for Breece (ask); settle at
     Stroud for Bucky Irving (me +53, them -3). Their QB2 is Flacco.
  3. Gallamijos Dynasty → ElGeneral4: Mahomes + Montgomery for Ashton
     Jeanty (their lineup +5; rebuild takes the 22yo). Alternate ask:
     2027 1st + Addison. Do not take less.
  4. DYNASTY TRC: NO trade — no QB-needy buyer (all 9 rivals checked).
     POUNCE TRIGGER armed, Goff ONLY: any rival QB1 injury/benching →
     same-day premium offer. Daily task checks the trigger every run.
- [ ] **Phase-system build items (before week 1)**: (a) lineup optimizer
  ceiling mode for weeks 15-17 (prefer boom/bust when projections close);
  (b) newsletter start/sit-deltas section (task prompt already carries it);
  (c) weekly report notes phase framing. Methodology already in CLAUDE.md
  "The manager".
- [ ] **Draft dates**: all 4 redraft drafts unscheduled. When one is set →
  run the draft-morning checklist (CLAUDE.md pre-draft checklist: fresh ADP,
  injury sweep, ECR cross-check, Vegas moves, re-simulation) + dry-run the
  dashboard with the user ~10 min before.
- [ ] **Guillotine MX & TRC**: commissioner hasn't randomized draft order —
  recs/round-plan appear automatically once slot is known.
- [ ] **Coaching gaps**: ATL (Tommy Rees) and SEA (Fleury) have notes but no
  player adjustments — revisit on draft morning with usage reports.
- [ ] **FANTASY MEXICA**: remind commissioner to fix assist scoring to 0.5
  before week 1. If league will play at 5.0, IDP strategy inverts (ask user).
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
- [ ] **Waiver claims recommended 2026-08-22, CORRECTED for dynasty value
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
