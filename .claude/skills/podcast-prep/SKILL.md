---
name: podcast-prep
description: Weekly NFL podcast prep. Use when the user asks to prep the podcast, "the show", the episode, a game-by-game rundown of the upcoming NFL week, betting lines / "do the lines make sense", best bets, or week-ahead fantasy talking points for recording. Runs scripts/podcast_prep.py (lines, line movement, ATS/O-U records, SRS + FPI line check, ranked team stats, rest/spot, injuries, fantasy usage and matchups), adds the research layer, and writes an on-air rundown with picks logged to data/intel/podcast_picks.json.
---

# Podcast prep

The user records a weekly podcast about the upcoming NFL week. For every game
he needs three things: **who wins and whether the casino line makes sense**,
the **stats and stories worth saying on air**, and **fantasy advice**. This
skill has two layers, the same way the weekly report does: a script builds
the data, and Claude adds the research and the calls. This is a living
document: when the user corrects the format or the process, update it here in
the same commit.

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
- **Fantasy table**: projections re-scored in PPR (half), target/carry share
  over the last 3 games vs the season (⬆️/⬇️ trend), snap % over the last 3,
  and opponent fantasy points allowed by position, ranked (🟢 top-8 softest,
  🔴 bottom-8). 📈 = Sleeper trending add. DST line: sacks, takeaways and
  points allowed vs the opponent's sacks taken and giveaways.
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
and the top 3 fantasy calls. Then the path to the rundown.
