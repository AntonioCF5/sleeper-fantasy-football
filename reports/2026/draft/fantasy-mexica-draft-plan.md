# FANTASY MEXICA — Draft Battle Plan (Slot 10 of 18)

*18-team snake · half PPR · 6-pt pass TD · IDP (DL/LB/DB) · 19 rounds ·
17 keepers frozen on the board · Your R10 pick = Tyler Shough (keeper, locked)*

> Scoring note — RESOLVED 2026-08-25: the 5.0 assisted-tackle typo was fixed
> on Sleeper's side (API now returns **0.5** natively, verified live). The
> config.json override was removed; all numbers below already used 0.5, so
> nothing changes. No commissioner reminder needed.

**Archetype: HERO RB + EARLY QB ("Anchor & Air")** — see
`archetype-playbook.md` for the branch definitions and the live switching
triggers. Late-round QB is explicitly dead in this league (6-pt pass TDs,
Shough-only keeper, 17 QB-needy teams); pivot branches are Hero WR (if 6+
RBs are gone at #10) and QB-first inversion (if a top-3 QB falls to #10).

## The three realities of this draft

1. **RBs rule the board.** Under corrected scoring, 8 of my top 12 are RBs
   (replacement level RB125 vs WR125 but far steeper RB dropoff). The RB1
   tier will not survive from pick #10 to #27 — urgency +46.
2. **6-pt passing TDs + your QB situation.** Your keeper Shough is QB20 —
   a backup, not a plan. 17 other teams need QBs and Lawrence is already
   kept. Leave round 2–3 with a top-8 QB. Lamar Jackson at #27 is the play.
3. **IDPs are off the board entirely** (user decision 2026-08-24: single
   starter slots, bottomless replacement depth — boards and the dashboard
   now show offense only). Fill DL/LB/DB with the final picks or post-draft
   waivers; any warm body starts. The live assistant won't suggest IDP
   names — just grab a starting DL, LB, and DB somewhere in the last 3-4
   rounds alongside the league-winner stashes, and never earlier.

## Round-by-round plan

| Rd | Pick | Target | Backup plan |
|----|------|--------|-------------|
| 1 | #10 | **Best RB standing: Ashton Jeanty / Derrick Henry / De'Von Achane / Saquon** | CeeDee Lamb if 6+ RBs already gone |
| 2 | #27 | **Lamar Jackson / best top-6 QB** (6-pt TDs; Allen will be gone) | A.J. Brown / Chris Olave, then QB hard at R3 |
| 3 | #46 | **RB2: David Montgomery / Travis Etienne / D'Andre Swift** (urg +30) | Sam LaPorta if TE tier about to break |
| 4 | #63 | **Best WR: Mike Evans / Parker Washington tier** | George Kittle |
| 5 | #82 | **WR2 or TE1** (Kittle/Strange tier if no TE yet) | Jack Campbell if you want the top LB locked |
| 6 | #99 | Best offensive player available — WR/RB depth | Brock Purdy as QB insurance if Lamar missed |
| 7 | #118 | WR3 (Jayden Reed tier) / RB3 | — |
| 8 | #135 | RB depth (Jordan Mason type) or **LB: Jack Campbell / Nakobe Dean** if still around | — |
| 9 | #154 | WR4 upside (Matthew Golden tier) | LB if not yet filled |
| 10 | #171 | 🔒 Tyler Shough (keeper) | — |
| 11 | #190 | **Contested handcuff if one slid** (Pacheco ADP 172 / Bigsby 166 / B.Robinson 160) else DL: Van Ginkel / Hutchinson | DB: Travis Hunter / Kyle Hamilton |
| 12 | #207 | RB4 upside swing (ambiguous backfield) or TE2 | DL if not filled |
| 13 | #226 | **DB: Chamarri Conner / best available box safety** | — |
| 14 | #243 | 🎟 **League-winner stash #1: handcuff to YOUR RB1** (whoever you drafted R1 — e.g. Justice Hill if Henry, Ty Johnson if Cook) | Last IDP piece |
| 15 | #262 | 🎟 **League-winner stash #2**: DJ Giddens (IND, ADP 672) / Samaje Perine (CIN, 614) — free top-5-offense handcuffs | TE2 if empty |
| 16 | #279 | 🎟 **League-winner stash #3**: Xavier Worthy (KC, year-3 WR) / Jalen McMillan / Tre' Harris breakout profiles | — |
| 17 | #298 | **DEF** (stream all season; they're all within 4 pts of each other) | — |
| 18 | #315 | **K** | — |
| 19 | #334 | 🎟 **League-winner stash #4**: best remaining from the board's Late-Round League Winners table | — |

## Build target (19 roster spots)

- 2 QB (top-8 QB + Shough) · 5–6 RB · 5–6 WR · 2 TE
- **3–4 IDP, all after round 8** (1 DL + 1–2 LB + 1 DB). Only 3 start and
  the position is flat — churn from waivers in-season.
- K + DEF in the last 3 rounds, never earlier.

## Standing rules during the draft

- Never pass a player whose ADP is 25+ picks later than my board rank
  (the Value column on the main board) unless the position is capped.
- If a run starts (3+ same-position picks in a row), jump one round early
  on the next tier player at that position; 18-team runs don't stop.
- ~~Assist-scoring contingency~~ RESOLVED: Sleeper now returns 0.5 natively
  (2026-08-25), the inversion scenario is dead. Kept for history only: at
  5.0/assist the IDP plan would have inverted completely (Campbell becomes a
  round-4 pick and IDP depth wins leagues). That inversion would also mean
  putting IDP back on the boards: remove the position filter in
  `analysis.draft_board` (`IDP_BOARD_EXCLUDE`) for this league first.

*Regenerate this plan the morning of the draft — ADP shifts, injuries, and
depth-chart news move targets. During the live draft I can poll picks in
real time and call audibles.*
