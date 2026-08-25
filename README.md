# Sleeper Fantasy Football Expert

A zero-dependency Python toolkit + Claude workflow that turns Claude Code into
a full-service fantasy football analyst for your [Sleeper](https://sleeper.com)
leagues: a live draft command center, custom-scoring rankings, weekly reports,
waiver targets, trade radar, and VORP draft boards.

The Sleeper API is read-only, so the loop is: **Claude analyzes → you tap the
buttons in the app.**

- **[CLAUDE.md](CLAUDE.md)** — the operating playbook (how Claude works here)
- **[STATUS.md](STATUS.md)** — current state: leagues, decisions, pending work

## Quick start

```bash
# 1. Point it at your Sleeper account (no password needed — public API)
python3 scripts/setup_user.py your_sleeper_username

# 2. Draft prep: boards tuned to each league's exact settings
python3 scripts/draft_prep.py

# 3. The command center (draft day AND in-season)
python3 scripts/draft_dashboard.py          # http://localhost:8787

# 4. In season: weekly report for every league
python3 scripts/weekly_report.py
```

## The command center (`localhost:8787`)

One page, three tabs, switchable across all your leagues without restarting;
open it on a second monitor or your phone (same Wi-Fi, use the Mac's LAN IP):

- **Draft Room** — live pick-by-pick recommendations with reasons (gone-by-
  your-next-pick, last-in-tier, roster needs), a round-by-round plan
  (🚀 upside / 💤 sleeper / 🛡 safe per round), a sleeper queue with
  window-closing alerts, league-winner stashes, and an audible + visual
  on-the-clock alert. Re-simulates after every pick in the room.
- **Rankings** — the full board under this league's exact scoring:
  search, sort, position filters, tier-break lines, per-player risk index,
  and live ownership (who drafted/rosters each player — doubles as the
  waiver board in season).
- **My Team** — roster grouped by position with clickable category filters
  (👑 elite / 🛡 floor / 🚀 ceiling) and a balance meter.

## What makes it sharp

- **Exact custom scoring** — projections are re-scored from granular stat
  lines under each league's `scoring_settings`, so TE-premium / superflex /
  points-per-first-down / 6-pt-passing-TD / IDP leagues get correct math
  (including a per-league override mechanism for commissioner typos).
- **VORP + tiers** — replacement level from a league-wide greedy starter
  simulation; tier breaks at real value cliffs; ADP-vs-board Value column
  showing who the market misprices *in your format*.
- **Risk index** — systematic 0-100 downside score (positional age curves,
  last-season durability, injury status, volatility) that discounts VORP
  before ranking. No per-player hand-tuning, ever.
- **Intel layer** — Vegas win totals → offense tiers, dome/cold-December
  venue flags, the full 2026 coaching map (21 new OCs), and documented
  scheme-riser adjustments (`data/intel/`).
- **Player categories** — 👑 elite, 🛡 floor, 🚀 ceiling, 💤 sleepers,
  🎟 league-winners — each computably defined (see the in-app Glossary).
- **Draft archetypes with switch triggers** — Hero RB, QB Hammer, Robust RB
  etc. assigned per league, with explicit in-draft pivot rules
  (`reports/2026/draft/archetype-playbook.md`).

No API keys, no scraping, no dependencies beyond Python 3.9+.

## EL DESTAPE DE MIROSLAVA (capa social)

Roast semanal de WhatsApp para las ligas Gallamijos, escrito por el personaje
"Miroslava" (reportera de sideline, sin piedad, español lagunero). Canon:
`data/intel/miroslava.md`. Generación automática los martes 7:30am
(`roast-semanal-gallamijos`) + on-demand; entrega en formato WhatsApp nativo
por archivo y correo. Ver CLAUDE.md → "EL DESTAPE DE MIROSLAVA".
