---
name: podcast-prep
description: Weekly NFL podcast prep. Use when the user asks to prep the podcast, "the show", the episode, a game-by-game rundown of the upcoming NFL week, betting lines / "do the lines make sense", best bets, or week-ahead fantasy talking points for recording. Also use when they ask to open the podcast app, add a stat to it, or what a number on the sheet/app means (SRS, yds/pase, yds/target, how to read the Fantasy or Uso table). Runs scripts/podcast_prep.py (lines, line movement, ATS/O-U records, SRS + FPI line check, ranked team stats, coach/QB/series history, rest/spot, injuries, fantasy usage and matchups), adds the research layer, writes an on-air rundown in Spanish with picks logged to data/intel/podcast_picks.json, and serves it all in the local app (scripts/podcast_app.py).
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

Asked something smaller, do only that piece:
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
