---
name: podcast-prep
description: Weekly NFL podcast prep. Use when the user asks to prep the podcast, "the show", the episode, a game-by-game rundown of the upcoming NFL week, betting lines / "do the lines make sense", best bets, or week-ahead fantasy talking points for recording. Also use for the RECAP segment — "el recap", how last week's games went vs the line, the injuries, and waiver priorities by position for the podcast audience (scripts/podcast_recap.py, §8). Also use when they ask to open the podcast app, add a stat to it, or what a number on the sheet/app means (SRS, yds/pase, yds/target, how to read the Fantasy or Uso table). Runs scripts/podcast_prep.py (lines, line movement, ATS/O-U records, SRS + FPI line check, ranked team stats, coach/QB/series history, rest/spot, injuries, fantasy usage and matchups), adds the research layer, writes an on-air rundown in Spanish with picks logged to data/intel/podcast_picks.json, and serves it all in the local app (scripts/podcast_app.py).
---

# Podcast prep

The user records a weekly podcast about the upcoming NFL week. For every game
he needs three things: **who wins and whether the casino line makes sense**,
the **stats and stories worth saying on air**, and **fantasy advice**. This
skill has two layers, the same way the weekly report does: a script builds
the data, and Claude adds the research and the calls. This is a living
document: when the user corrects the format or the process, update it here in
the same commit.

## 0. The whole run, in order

When the user says "prep the podcast" (or "the show", "semana N"), run all of
this without asking. Each step is detailed in the section named.

1. **Data**: `python3 scripts/podcast_prep.py [week]` (§1). Read the header
   (last week's record), the slate table, the 🚩 list, "Roles más grandes"
   and "History notes" before anything else.
2. **App**: `preview_start {name: "podcast-app"}`. The user preps from it, so
   it should be open and current (§6).
3. **Research**: 2-3 parallel subagents, plus expert takes and the survivor
   plan (§2).
4. **Rundown**: write `rundown.md` in Spanish, every game, in kickoff order
   (§3). Back each fantasy call with a usage number, and check every
   superlative against the whole slate.
5. **Picks**: log every side, total and ML in `podcast_picks.json` (§4).
6. **Verify in the app**: reload, open each game's Resumen, Fantasy and
   Guion tabs, and confirm the pick, Historia and Fantasy blocks came
   through. Then check that no tab on any game shows `undefined`, `NaN` or
   an empty card (§6).
7. **Close out**: commit, and post the chat summary (§5).

The episode opens with the **recap of the week just played plus waivers**
(§8). That runs Monday/Tuesday, after the games and before waivers clear,
and it's a separate run: "haz el recap", "los waivers de la semana".

**One episode = recap of week N + preview of week N+1** (user 2026-11-02: the
show records on recap day, and a guion whose "tres historias" were week 8's
previews was wrong for a week-9 recording). So whenever the recap of week N
exists and week N+1 has no `rundown.md` yet, the recording needs the whole
run above for N+1 too: `podcast_prep.py N+1`, research, rundown, picks. The
app opens on the newest week with data and shows week N's recap in that
week's Recap tab, so prepping N+1 is also what makes the app current. A
Monday rundown says in its header that no practice reports exist yet and
that the MNF teams' injuries are still pending.

Asked something smaller, do only that piece:
- "recap" / "waivers" → §8 in full.
- "refresh the lines" → step 1 plus the app's Actualizar button.
- "add X to the app/sheet" → §6, "Adding a metric".
- "what does X mean" / "how do I read this table" → §7, answered in Spanish
  with the user's own screenshot rows as the examples.

## 1. Data layer (always first)

```
python3 scripts/podcast_prep.py [week]      # default: ESPN's current week
```
→ `reports/<season>/podcast/weekNN/podcast-prep.md` (one sheet per game) +
`data.json` (the same numbers, machine-readable). Runs in about 10s. Upcoming-slate data
caches for 3h and finished games for a week. **Re-run it on recording day**,
because lines and injury tags move all week. Games that are already final (TNF) drop off.

What the sheet holds, and how to read it:
- **Slate table**: spread and total, open → now, implied team totals, market
  win % (de-vigged ML) vs ESPN FPI win %, our SRS line, 🚩 flags.
- **Line check**: two independent fair lines against the market. SRS is our
  opponent-adjusted margin rating (blowouts capped at ±21, shrunk n/(n+3)).
  FPI is ESPN's win % converted to points. 🚩 = BOTH lean the same way by ≥2
  pts. "mild lean" = same direction but under the bar. "split" = no signal.
  **Neither model knows about this week's injuries.** When a line moved a long way
  (PHI @ WSH wk 8: opened WSH +2.5, now -6), the market is usually reacting to
  a QB or other news the models can't see. Find the reason before calling it a gap.
- **Openers can be stale lookahead numbers.** ESPN's "opened" line is sometimes a
  number posted before the prior week's games (wk 8: CAR @ GB "opened -7" and
  KC @ DEN's flip both turned out to be lookahead lines, not real moves). A big
  move with no news behind it gets checked against a second book before it goes on air.
- **nflverse coach names lag for the current season** (2026: Gannon at ARI,
  McDermott at BUF, Morris at ATL, "Kubliak" at LV). `fix_coaches()` overwrites
  this season's rows with `team_env.json`'s `hc`, so keep that field current
  when a coach is fired in-season.
- **ESPN's injury list lags.** It can carry an IR tag on a player already back at
  practice (wk 8: Shavers). Practice participation from the research layer wins.
- **"missed N of last 3"** next to a player means the L3 shares cover only the
  games he played inside his team's last three. Usage from a player returning
  from injury is a projection question, not a trend.
- **Total check**: a naive points-for/points-against total. It is blind to QB
  changes and weather, so it only counts as a talking point when it is ≥3 off
  and the research backs it.
- **Team table**: SU (home/road), ATS (as fav/as dog), O/U, average margin and
  average cover margin, SRS, points for/against, plus ESPN stats ranked 1-32
  (net yds/pass att, yds/rush, 3rd down %, red-zone TD %, turnover diff, sacks
  both ways, plays/game). Also the spot: rest days, off bye, short week,
  west-coast team at 1pm ET, divisional game, next opponent (lookahead).
- **Last 5** with the line and result (✓ covered, ✗ didn't, O/U).
- **Injuries**: ESPN Out/Doubtful/Questionable list.
- **Fantasy table**: projections re-scored in PPR (half), then each number
  as last 3 games (season):
  - target share; on the QB row, pass attempts per game instead
  - yards per pass attempt for QBs; yards per target for everyone else
  - carry share, and snap % over the last 3
  - opponent fantasy points allowed to the position, ranked (🟢 top-8
    softest, 🔴 bottom-8)

  ⬆️/⬇️ = target share moved ≥5 pts or carry share ≥10 pts vs the season
  (needs ≥2 games in the window). 📈 = Sleeper trending add.

  Yds/pase is GROSS (pass yards ÷ attempts, sacks left out). It is not the team
  table's "Yds netas/intento", which takes out sack yards. Yds/target
  counts incompletions (receiving yards ÷ targets). Both print "—" under 5
  attempts or targets in the window.

  DST line: sacks, takeaways and points allowed vs the opponent's sacks taken
  and giveaways.
- **Usage by team** (user 2026-10-28: usage numbers back up the arguments):
  per team, the top 3 RBs by backfield share and the top 6 WR/TE by target
  share, each shown as last 3 games (season). Columns: snap %, target %,
  targets per game, % of completed air yards, red-zone share (targets for
  WR/TE, carries for RB), and % of backfield touches (carries + catches over
  all of the team's RB touches). Under each table there's a one-line read:
  - backfield: "un solo hombre" (≥70%, no second back ≥30%), "reparto claro"
    (≥55%) or "comité"
  - top-2 target share: "árbol concentrado" at ≥50%, "reparto abierto" under 38%
  Slate-wide, **Roles más grandes** lists target magnets (≥27%) and workhorses
  (≥70% of backfield touches).
  - Air yards are COMPLETED air yards (Sleeper's `rec_air_yd` = rec_yd −
    rec_yar), not air yards on every target, so a bad QB drags them down. Say
    "yardas aéreas completadas" on air.
  - **Routes run are not in any free 2026 feed.** nflverse participation data
    stops at 2025, Sleeper and ESPN don't carry routes, and PFF, FantasyPoints
    and Rotowire put them behind a paywall. Use route participation only when
    the user pastes it from a subscription; otherwise targets per snap and
    snap % are the stand-ins.
- **Coaches & history** (nflverse games file since 1999, closing lines,
  includes playoffs; module `sleeper/history.py`), per team:
  - head coach career SU/ATS
  - the coach in THIS spot: favorite/underdog (7+ if the line is), home/road,
    after a win/loss, off a bye or on short rest, primetime, division games
  - coach vs this franchise and vs the opposing head coach
  - the starting QB's career, his record vs this opponent and in this role
  - this season's home and road splits (SU, ATS, points for and against)
  - the 3-season home/road margin gap
  - Pythagorean wins vs actual, and one-score record
  - series history (last 10: SU, ATS, O/U, average total, streak, last meeting)
  - a ranked **Notable** list, plus a slate-wide "History notes" section
  Signal vs color on these (say which on air):
  - Rest/bye spots and QB-specific matchups carry a mechanism.
  - Pythagorean and one-score gaps are the best regression signal on the sheet.
  - Team home-field gaps carry ±2 pts of noise and are mostly noise, except
    altitude (Denver).
  - Coach ATS splits and series ATS are color: the sheet tags them
    *(trend — color)*. They go on air as talking points, never as the reason
    for a pick. When one cuts against a pick, say so (the pushback segment);
    don't bury it.
- Slate-wide: top and bottom implied totals, softest matchups per position,
  usage risers, trending adds.

**Browsing it:** the local app (§6) shows the same data one game at a time.

## 2. Research layer (what the script can't see)

Delegate the web research to **2-3 parallel subagents** (4-6 games each,
general-purpose). Hand each one its games plus that part of the sheet, so it
returns findings instead of re-deriving the stats. Each returns, per game:
1. **Why the line moved**: any move of ≥1.5 pts, or any move across 3, 7 or 10,
   needs a named cause (injury, QB change, sharp money report, weather).
2. **QB / key-player status**: practice participation Wed-Fri, beat-reporter
   language. The ESPN tag alone is not enough.
3. **Weather**: wind forecast for outdoor games. ESPN gives only temperature
   and precipitation; wind ≥15 mph is what moves totals and passing games.
4. **Coaching / scheme / role changes**: new play-caller, depth-chart moves,
   snap-count notes. Cross-check `data/intel/team_env.json` (hc/oc/coach_note).
5. One or two **storylines** a listener would care about (revenge game, streak,
   milestone, coach on the hot seat). Label these as color, not reasons.

Also pull, without delegating: `data/intel/expert_takes.json` for players on
this slate (Fantasy Footballers / Sal Vetri, from the expert layer), and
`python3 scripts/survivor_plan.py` for the survivor segment.

## 3. The rundown (Claude writes it)

→ `reports/<season>/podcast/weekNN/rundown.md`. It is written to be **spoken**:
short lines, numbers rounded the way people say them, no tables inside game
segments. The host is a sharp veteran: lead with the edge, not the lesson.

**Language: the podcast is in SPANISH (user 2026-10-28).** The rundown is
always written in Mexican Spanish, to be read on air. **The data sheet is in
Spanish too** (`podcast_prep.py` prints Spanish labels, CDMX times, Spanish
injury tags and body parts via `STATUS_ES`/`BODY_ES`; G/P/E and A/B in the
last-5 logs). Only the research layer's notes stay in English, since they're
internal. When the script prints a new string, write it in Spanish. Conventions,
applied the same way every week:
- Team nicknames as Mexican broadcasts say them: Empacadores, Panteras,
  Cuervos, Bills, Bengalíes, Titanes, Cardenales, Vaqueros, Vikingos, Leones,
  Raiders, Jets, Cafés, Acereros, Halcones, Bucaneros, Potros, Jaguares,
  Cargadores, Carneros, Jefes, Broncos, Patriotas, Delfines, Águilas,
  Comandantes, Osos, Halcones Marinos, Texanos, Santos, Gigantes, 49ers.
  City names are fine too. Game headers keep the codes (`CAR @ GB`).
- Betting terms:
  - spread → spread / la línea; ATS → contra la línea
  - over/under → altas/bajas
  - favorite/underdog → favorito / no favorito
  - lean → inclinación; pass → paso; "good to X" → sirve hasta X
  - sharp money → dinero fuerte / dinero inteligente
  - lookahead line → línea anticipada
- Football terms:
  - QB → mariscal (QB also OK); TE → ala cerrada
  - sack → captura; turnovers → balones
  - third down → tercera oportunidad; red zone → zona roja
  - bye → semana de descanso; short week → semana corta
  - IR → reserva de lesionados; one-score game → partido de una posesión
- Fantasy terms: start → arranca; sit → banca; fade → fuera; smash →
  partidazo; sleeper → sorpresa. Leave targets, snaps, backfield, flex,
  streaming, FAAB and waivers in English, the way Spanish-language fantasy
  audiences say them.
- Kickoff times in Mexico City time with ET in parentheses. Mexico has no DST
  since 2022, so CDMX = ET-2 while the US is on daylight time and ET-1 from
  the first Sunday of November.
- Same structure, rules and discipline as below. Only the language changes.

```
# Week N rundown
## Cold open: the 3 storylines of the week (one line each)
## Last week's record (from the prep sheet header) + one-line post-mortem
## Game by game (kickoff order)
### AWAY @ HOME — line, total, kickoff
- The number: what the line says, where it opened, why it moved
- Case for AWAY: 2-3 stats that actually explain football (efficiency, trenches, turnovers, spot)
- Case for HOME: same
- The call: winner + side/total/PASS · confidence ★–★★★ · "good to X, pass past Y"
- History: the 1-2 coach/series/QB/regression notes worth saying, tagged signal or color
- Fantasy: 1 start · 1 sit/fade · 1 sleeper/deep play, each with its stat
## Best bets card (3-5 max, from the calls above)
## Fantasy segment: smash spots, traps, the usage riser to grab now
## Regression watch: records vs point differential (Pythagorean + one-score games)
## Survivor pick (survivor_plan.py output + the week's line)
```

Rules for the calls:
- **Most games are a PASS on the spread.** The market is efficient. Give a bet
  only with (a) a 🚩 or mild lean that the research supports, or (b) news the
  line hasn't absorbed yet. Every game still gets a straight-up winner.
- **Key numbers**: 3 and 7 (then 10, 6, 4) on spreads, 41/44/47 on totals.
  Say whether the current number sits on or off one, and the worst number you
  would still bet.
- **ATS/O-U trends are color, never the reason.** Seven games of cover margins
  are noise. On air: "they're 5-1 to the over, and here's why that's real or
  not". Reasons come from efficiency, matchups, injuries and the spot.
- **Audit mechanisms** (CLAUDE.md expert-layer rule): "thin backfield → more
  passing" is false for favorites. Test any causal claim against the sheet
  before saying it.
- **Fantasy advice is league-agnostic.** The audience isn't in his leagues, so
  use PPR/half from the sheet. Never reveal his rosters or league business on air.
- Confidence: ★ lean, ★★ bet, ★★★ best bet. Be decisive, like the weekly report.
- **Back every fantasy call and every player-driven game argument with a usage
  number** from the usage table: target share, backfield share, red-zone
  share, snap trend. "Gibbs is questionable" lands harder as "91% of Detroit's
  backfield touches and a 9% backup". When usage cuts against a call, change
  the call or say so on air (wk 8: Stevenson went from start to flex at 51% of
  the backfield; Chase's L3 dip to 61% snaps). Every superlative ("the most on
  the slate") gets checked against the whole slate first.

## 4. Log the picks (accountability)

Every side/total/ML said on air goes into `data/intel/podcast_picks.json`
under `weeks.<N>`, with the line **at pick time** from the side's
perspective (schema in the file's `_schema` key). The script grades them on
the next run once games are final and prints "Last week X-Y · Season X-Y" at
the top of the sheet, which feeds the "last week's record" segment. Never
backfill or edit a logged line after the fact.

## 5. Close out

Commit `reports/<season>/podcast/weekNN/` and `podcast_picks.json` together.
In chat, give: the 🚩 games and why they did or didn't become bets, the best-bets card,
and the top 3 fantasy calls. Then the path to the rundown, and say the app
is open on the slate.

## 6. The local app

`python3 scripts/podcast_app.py [port]` serves the app at
http://localhost:8790. Start it with `preview_start {name: "podcast-app"}`
(config in `.claude/launch.json`), never with Bash. It is stdlib only, with no
build step: `podcast_app.py` is the server and `podcast_app.html` is the whole
UI (HTML, CSS and JS in one file).
- It reads `data.json`, `rundown.md` and `podcast_picks.json` on every
  request, so an edit to the rundown shows up on reload.
- **Actualizar** re-runs `podcast_prep.py` for the open week (POST
  `/api/refresh?week=N`, behind a lock, 5-minute timeout).
- Routing is in the hash, `#/season/week/GAME/tab`, so a link opens a
  specific game and tab.

**What each tab shows, and where it comes from:**
- Overview:
  - Cartelera: KPIs, pick cards and the slate table.
  - Recap y waivers: `recap.json` + Claude's `recap.md` (§8). It shows this
    week's recap once one exists, otherwise last week's, which is the one
    that opens this week's episode. Once a game is final, its hero also
    shows the final score.
  - Guion general: the rundown's `##` sections.
  - Notas de la hoja: `slate_md`.
- Per game:
  - **Resumen**: the line, open → now, SRS/FPI/market on one axis, win %
    bars, the verdict, and "El pick al aire" from the rundown.
  - **Equipos**: `team_rows` with a 1-32 rank chip on every "(Nº)".
  - **Historia**: `series`, `notables` and the rundown's Historia bullet.
  - **Fantasy**: the player table, the DST line and the rundown's Fantasy bullet.
  - **Uso**: usage bars, where the bar is the last 3 games and the tick mark
    is the season.
  - **Lesiones**: `injuries`.
  - **Guion**: the game's rundown segment.
  - **Hoja completa**: the game's full sheet markdown.

**Contract with the rundown:** the app splits it on `### AWAY @ HOME`
headers (ESPN codes, e.g. `WSH`), and skips the `## Partido por partido` heading.
It pulls these bullets by their exact labels:
- `- **El pick:**`
- `- **Historia:**`
- `- **Fantasy:**`

Rename any of these and that block goes empty in the app.

Shortcuts:
- J/K or ↑/↓: next or previous game
- ←/→ or 1-8: switch tab
- G: back to the slate
- /: search
- T: theme
- ?: help

**Adding a metric** (the order the QB attempts and yds/pase work followed):
1. In `podcast_prep.py`, read the stat in `load_sleeper`. Aggregate it in
   `agg()` for both windows (last 3 and season). Put a minimum-sample guard
   on any rate (`None` under 5).
2. Expose it in the structure the app reads: `usage_data` rows, or the
   game's fantasy players in `sheet`.
3. Print it in the sheet markdown (header plus row), in Spanish.
4. In `podcast_app.html`, render a cell for it. Use the same last 3 = bold,
   season = grey convention, ▲/▼ only past a stated threshold, and add one
   line to that tab's legend card explaining it.
5. Re-run, then verify in the browser:
   - every game and every tab, checked with JS text checks for
     `undefined`/`NaN` (screenshots can lag a frame behind)
   - 375px mobile width with no horizontal scroll
   - no console errors
6. Document it in §1 and §7, and commit the code, the regenerated week and
   this file together.

## 7. Explaining the numbers (answer in Spanish, with his rows)

When he asks what something means, answer in Spanish: define it, give the
formula, then read it off his own screenshot or game, and end with the
on-air takeaway.
- **SRS** (Simple Rating System): each team's point margin, adjusted for
  opponents and home field. Blowouts are capped at ±21 a game, home field
  is worth 1.5 points, and the rating shrinks toward 0 by n/(n+3) early in
  the season.
  - SRS line = home rating − away rating + 1.5.
  - The 🚩 flag needs SRS AND FPI to disagree with the market by ≥2 pts in
    the same direction.
  - Neither model sees this week's injuries.
- **Yds/pase vs Yds/target**: the QB's gross yards per attempt (sacks
  excluded), and a receiver's yards per time he's targeted (incompletions
  count against him).
  - Volume times efficiency is the read: many attempts at a low yds/pase is
    empty volume.
  - A high yds/target on a small sample is usually one long catch.
  - An RB near 10 yds/target isn't sustainable.
- **How to read the Fantasy table** (row by row):
  - Bold = the team's last 3 games; grey = season.
  - PPR on top, half below. A small gap between them means few catches.
  - Targets: share of the team's targets. On the QB row it's attempts per
    game, with ▲/▼ at a gap of ≥3.
  - Yds/pase · yds/target: ▲/▼ only at a gap of ≥1 yard. A 0.9 gap gets no
    arrow, so say "flat", not "falling".
  - Grey only, with no bold number: under 5 targets in the window, so there
    is no recent rate.
  - "se perdió N de los últimos 3": the bold numbers come from fewer games,
    so treat them as a sample, not a trend.
  - 📈: Sleeper adds over the last 48h. Explain WHY he's trending (role
    change, injury, trade rumor) before calling him a play.
  - Columns off the right edge: Acarreos (carry share), Snaps (last 3) and
    Rival (opponent's rank out of 32 in points allowed to the position;
    green = 8 softest, red = 8 toughest).
- **How to read the Uso table**:
  - The bar is the last 3 games and the tick is the season.
  - % backfield = (carries + catches) ÷ all of the team's RB touches.
  - Air yards are COMPLETED air yards only.
  - The read line under each table labels the backfield ("un solo hombre",
    "reparto claro", "comité") and the target tree ("árbol concentrado",
    "reparto abierto").

## 8. Recap + waivers (Monday/Tuesday, the episode's opening segment)

The recap and waiver segment opens each episode. It goes over the week just
played: results against the line, the games themselves, the injuries, and
waiver priorities **by position** for a general audience. Run it after the
Sunday games. Run it again after MNF if a Monday game matters, because
injuries and stat lines are still settling. Waivers clear Tuesday night, so
the waiver half goes stale after that.

### 8.1 Data

```
python3 scripts/podcast_recap.py [week]     # default: the week just played
```
→ `reports/<season>/podcast/weekNN/recap-prep.md` + `recap.json`, written into
the folder of the week that was played. It runs in about 10s and grades
`podcast_picks.json` for that week. Unfinished games (MNF) show as pending;
re-run once they're final.

What it holds:
- **Our picks**: each graded W/L/pending, plus the week and season record.
- **Results vs the closing line**: who covered and by how much, the
  over/under, and records for favorites, home teams and overs.
  - "Donde más falló el mercado" lists the three biggest cover margins.
    Before calling one a story, find the cause: a turnover avalanche, a QB
    injury, or a blowout script.
- **Injuries that move fantasy**: ESPN's per-game injury list, keeping only
  entries dated at or after kickoff, so pregame inactives drop out. Each
  injured player gets:
  - his role before this week (backfield touches, targets or snaps)
  - his snap % in this game
  - whoever absorbed the role, with that player's rostered %
  - the latest Sleeper news headline

  A teammate only counts as having absorbed the role if the injured player
  actually lost it: he was ruled out, didn't play, or played under 60% of
  his usual snaps.
- **Game by game**:
  - the box score: yards, yards per play, per pass and per carry,
    turnovers, 3rd down, sacks taken, red zone, time of possession
  - the top 5 PPR lines
  - **usage that changed** vs the season before this week: backfield share
    +20 pts, target share +10, snaps +25, or a starter cut to half his snaps
  - the injuries
- **Waivers for next week, by position** (a pool of QB 8, RB 12, WR 12, TE 8, DST 8):
  - Who qualifies: rostered in ≤50% of Sleeper **redraft** leagues
    (`api.get_ownership`, the research endpoint), or 50-80% when the role
    changed this week (an inherited role or a usage jump); never Out/IR.
  - Projection: the average of Sleeper's projection re-scored in PPR and a
    **usage-implied projection**. Sleeper lags role changes by days (wk 8:
    Mike Washington Jr. at 81% of the LV backfield was projected 5.2; his
    usage implied 18.6).
    - RB: this week's share × the team's RB PPR per game.
    - WR/TE: target share × team targets per game × league PPR per target.
  - Tier, from the CLAUDE.md FAAB ladder:
    - **A** (30-60%): inherited ≥55% of a backfield.
    - **B** (15-25%): any other inherited role, or a projection at or above
      the position's starter line (QB12/RB24/WR24/TE12).
    - **C** (1-5%): everyone else.
  - DST streamers: next week's projection in standard scoring, against the
    opponent's implied total from the market.
- **Para comprar, vender y vigilar** (added from the user's week 8 notes):
  - **Rachas**: 3+ straight games with RB 100+ scrimmage yards or 17+
    carries, WR 8+ targets, TE 7+ targets, or QB 20+ points. Each comes with
    the next 4 opponents' rank vs the position.
  - **Perdieron el rol sin lesión**: an RB whose backfield share fell 25+
    pts from ≥45% (wk 8: Jeanty, 71% → 16%), or a WR/TE at ≥15% of targets
    who drew ≤5% while playing half the snaps or more (Omar Cooper: 0
    targets on 78% of the snaps). Tagged when the game was a blowout.
  - **Titulares que fallaron**: a starter-level player (season average at
    the QB12/RB24/WR24/TE12 line) who scored under half his average.
    - "Uso intacto" means his share held at ≥85% of normal, which makes him
      a buy-low candidate. Otherwise "el uso también bajó".
    - Each one comes with his schedule.
  - **Mariscales en duda**: any QB besides the season's starter who took
    ≥10% of the snaps or 2+ passes, tagged as injury relief, blowout mop-up,
    or with the game still in play.
  - **"Sin <QB>"**: when a QB lost his game to injury, his top 3 targets'
    lines with the backup in (wk 8: Flowers 0/5 without Lamar).
- **Most-added on Sleeper (24h)**: the platform's list, with each player's
  week. Every name on it needs a WHY before it becomes a call (CLAUDE.md:
  investigate huge add counts). A player can trend because of somebody
  else's injury (wk 8: Singletary at 503k adds on a bye week).

### 8.2 Research layer (2 parallel subagents)

1. **Injuries**: diagnosis, MRI, timeline and Monday's coach quotes for every
   row in "Lesiones que mueven el fantasy", and for every starter who left a
   game. Ask the decisive question for each one: who starts at that position
   in week N+1? (wk 8: BAL lost Lamar, Huntley AND Fagnano in one game.)
2. **Roles**: why each 📈 player is trending, and whether each usage jump
   will last. Was it a teammate's injury, a depth-chart move, or blowout
   garbage time? Cross-check `data/intel/expert_takes.json`.

The mechanical tier is a starting point. Research moves it:
- An A tier holds only if the injury is multi-week.
- A one-week fill-in drops to C.
- A role confirmed by the coach moves up a tier.
- **A usage jump in a blowout loss is a script, not a role.** Check the
  score before you trust a share.

### 8.3 The spoken recap (Claude writes it)

→ `reports/<season>/podcast/weekNN/recap.md`, in Spanish, written to be
spoken, with the same conventions as §3. The app shows each `##` section as
a card at the top of the Recap tab, so keep these headings:

```
# Recap semana N
## Lo que pasó: the 3 stories of the week (one line each, with the number that proves it)
## Nuestros picks: record + one honest post-mortem line per loss (what we missed, not "bad luck")
## Contra la línea: favorites/home/overs, the biggest market miss and WHY
## Lesiones: each one → timeline → who replaces him → fantasy verdict
## Comprar, vender y vigilar: buy low / sell / earned status / status the box score oversells / watch list (see below)
## Waivers por posición: RB / WR / TE / QB / DST, each a RANKED list of 5+ as "1. Name (team, % in leagues): why — FAAB %"
## Los que NO: the trap adds (a trending name whose role isn't real), with the stat that says so
```

Waiver rules (the same discipline as the weekly report):
- **Rank several per position (user 2026-11-02).** Give at least 5 for each of
  RB, WR, TE, QB and DST, numbered 1-N. The script's pool is larger than
  that (QB 8, RB 12, WR 12, TE 8, DST 8), so research can drop the traps and
  still leave 5. A position with fewer than 5 real adds says so, and the
  rest of its list is labeled as streamers or deep-league names.
- **"Libre en X%"**: players rostered in 50-80% of leagues make the pool only
  when their role changed this week (wk 8: Allgeier at 58%, Coleman at 75%).
  Rank them with everyone else, and say how many leagues they're still free
  in.
- **Priority goes by position, and inside each position by rest-of-season
  role.** A one-week boom is not a role. Lead with the add that changes
  rosters: an inherited workhorse role, then a starting job, then streamers.
- Back every call with its usage number: "81% of the backfield touches,
  up from 22%", not "he looked good".
- Give the FAAB % from the tier, after research has adjusted it. Bids are
  always odd numbers.
- Keep it league-agnostic. Never mention his rosters or his leagues on air.
  His own waivers are the weekly report's and the newsletter's job.

**Comprar, vender y vigilar** (what the user's own recap notes cover, wk 8). Every
call carries its usage number and, when it's about the future, the schedule:
- **Buy low**: a player who flopped while his usage held, with a soft
  schedule ahead (wk 8: London 26% of targets and Bijan 79% of the
  backfield after Penix's 4 INTs).
- **Sell**:
  - a streak about to end: a starter coming back, or the schedule turning
    (Braelon Allen: 4 straight 100-yard games, and Breece returns)
  - a role lost to a coach's decision (Jeanty)
  - a team you can't trust (the Chargers: Hampton played 18 of 61 snaps)
- **Status earned vs. status the box score oversells**:
  - Earned (wk 8: Coleman is Denver's RB1, Gordon has a workload): call it
    with its numbers.
  - Oversold: say so with the number (Bucky "RB1" on 30 of 60 snaps in a
    0-completion game; Tuten "league winner" on 27 of 54 snaps against a
    tough schedule).
- **Downstream of injuries**: a hurt QB drags his receivers. Say who loses
  value, not just who gains it.
- **QB watch**: a benching, or a backup's snaps. Blowout mop-up (wk 8:
  Richardson's 13 snaps in a 35-point loss) is not a QB change unless
  something else says so.
- **Trade rumors and "visibly frustrated" reads are color.** Label them as
  color.
- **Check every schedule claim against the ranks.** "Good schedule coming
  up" was wrong for Tuten in week 8.

**When the user pastes his own notes** (WhatsApp/Twitter style, often in
English):
1. Treat them as input to the recap, not as text to copy.
2. Check every stat against the week's Sleeper rows and our scoring. (Wk 8:
   nearly all held up. Jones's "under 7" was 4.6 and 8.5 in our PPR.)
3. Fold the ones that hold up into the recap in Spanish and in his framing.
   Move picks if a note changes a call. (Wk 8: Emmett Johnson moved from
   "Los que NO" to a stash, because he's the clean handcuff to Walker's 21
   carries.)
4. **Push back with the number wherever the data disagrees.** (Wk 8: Tuten's
   schedule, Bucky as an RB1, selling Jefferson after 9 targets on 51 of 53
   snaps, "Richardson SZN" off blowout snaps.) He wants that friction.
5. If his notes cover a kind of analysis the script doesn't produce yet,
   add it to the script and to this section. That's how this section
   started.

### 8.4 Close out

Commit `recap-prep.md`, `recap.json`, `recap.md` and `podcast_picks.json`
together. In chat, give the record, the 3 injuries that matter most, and the
top waiver per position with its FAAB.

