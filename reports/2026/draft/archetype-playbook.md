# Draft Archetype Playbook — 2026 Redraft Leagues

*The archetypes are branches of one decision tree, not scripts. Every draft
starts on a default branch chosen from the league's format + our board +
draft slot; explicit triggers switch branches mid-draft. The live dashboard's
urgency engine executes the tactics; this playbook sets the strategy.*

## The archetypes (2026 state of the art)

| Archetype | Definition | Wins when | Fails when |
|---|---|---|---|
| **Hero RB** | One elite anchor RB in R1, then WR/TE/upside for 4-6 rounds, RB depth late | Your anchor is a true 20+ PPG bell-cow; WR middle rounds are deep (they are in 2026) | Anchor gets hurt and you skipped the handcuff |
| **Robust RB** | 2-3 RBs in first 3-4 rounds | Deep leagues where RB replacement is unplayable (our 18-teamers!); TD-driven scoring | League is PPR-flooded and WRs outscore your RB2/3 |
| **Zero RB** | No RB until ~R6; load elite WR/TE; late RBs = upside/handcuffs | Full PPR, injuries hit RBs drafted early, your late RB darts hit | Deep leagues: RB pool evaporates and waivers can't save you |
| **Hero WR** | Elite WR anchor R1, balanced after | WR tier 1 clearly out-projects RB tier at your slot; half/full PPR | RB cliff comes early (18 teams) and you're on the wrong side |
| **Late-round QB** | Wait until R8+; stream matchups | 1QB league with a flat QB7-17 tier (2026 is exactly this); 4-pt pass TD | 6-pt pass TDs, superflex, or 18 teams draining the flat tier early |
| **Early TE** | Bowers/McBride in R2-3 for a weekly positional edge | Elite-TE gap is real (2026: only 2 elites); TE-premium scoring | You pass a tier-1 RB/WR to do it in a league where TE12 is startable |
| **QB Hammer** *(our name)* | 2-3 QBs in the first 5 rounds | Superflex/2QB, especially 18 teams where backup-tier QBs start weekly | 1QB anything — never |

2026 consensus notes that match our math: Hero RB is the analyst default this
year; late-round QB "is back" because QB7–17 project nearly flat (our boards
show the same flat tier); only two elite TEs exist (Bowers, McBride — our
boards put Bowers alone in T1); recommended Zero-RB targets (Corum, Bigsby)
are literally our handcuff/league-winner list. Deep-league adjustments:
role security > upside in early rounds, RB depth swings 18-teamers, the
waiver wire cannot fix mistakes after week 1.

---

## League assignments

### Gallamijos League — 18t, full PPR + yardage bonuses, 4-pt pass TD, IDP · slot 2
*(CORRECTED 2026-08-25: earlier version claimed PPFD — every first-down field
in this league scores 0.0. Real quirk: +1 at 100 rush/rec yds, +2 at 200,
+1/+2 at 300/400 pass yds — a CEILING tilt, not a possession-floor tilt.)*
**Branch EN DISPUTA — revisión de la mañana del draft (2026-08-30, 8:30am):
la tarea pre-draft RECOMIENDA revertir a ANCLA RB (Gibbs si cae, si no
Bijan). Decisión final del user, pendiente al momento de escribir.**
*(El 29/8 el user eligió Chase en el 2 y de ahí salió la ruta RB-RB forzada
en el 35/38. La simulación fresca del 30/8 — 50 drafts con ruido de ADP,
cada ancla jugando su MEJOR línea — dice: Bijan 547.1 · Nacua 516.5 ·
Chase 509.1. **Bijan supera a Chase por 38.0 VORP**, y por +36.9 incluso
borrando a Flowers del board. Mecanismo: con el RB anclado en el 2, el pick
38 compra a Flowers (104.8); con Chase, el 38 está obligado a Swift (66.8).
Además solo hay UN pick antes del nuestro, así que es imposible que Gibbs y
Bijan se vayan los dos: el ancla RB no nos la pueden quitar, el WR élite sí.
Sal Vetri (29/8) ordena igual que nuestro board: 1 Gibbs, 2 Bijan, 3 Nacua,
4 Chase. Nacua queda vetado por psoas — 2 semanas sin drills de equipo.
Plan completo y la línea alterna si el user sostiene a Chase:
`gallamijos-league-draft-plan.md`.)*
- R1 (#2): Gibbs or Bijan — a true single-player-tier anchor. This is the
  textbook Hero RB league: full PPR + deep WR middle + flat QB tier.
- R2–R6: WRs — full PPR pays targets, and the 100-yd bonus nudges toward
  high-yardage X receivers over pure short-target compilers when a tie
  needs breaking. One RB from T3/T4 when a tier is dying, TE only on the
  trigger below.
- QB: **wait until R8–10** — 4-pt pass TDs + flat tier = classic late QB.
  Emergency trigger below protects the floor.
- IDP R10+, K/DEF last two rounds, final 3 picks = league-winner stashes.

Pivot branches: Early TE (if Bowers reaches our value line ~R2/3 turn);
Robust RB (if WR run rounds 2-3 leaves RB T3 intact at the turn — take two).

### FANTASY MEXICA — 18t, half PPR, 6-pt pass TD, IDP, keeper · slot 10
**Branch REVISED 2026-08-29 (draft morning, fresh ADP): HERO RB + LATE QB**
*(was "Anchor & Air / early QB" — the data killed it; see
`fantasy-mexica-draft-plan.md` for the full math.)*
- The 6-pt-paTD "elite QB" heuristic does NOT survive this board: the QB
  cliff is only between the top two, and QB3→QB12 spans just 27 points
  across nine QBs. Purdy sits at ADP 123 (+60) and Goff at ADP 139 (+73),
  so a 336-point QB costs a pick in the 118-139 range.
- The decisive comparison: Lamar at 27 (VORP 71.3) + filler WR at 135
  (~13.6) = 84.9, versus Flowers at 27 (73.6) + Goff at 135 (39.4) = 113.0.
  **Late QB wins by ~28 VORP.** Note the lens: Allen out-scores Gibbs on
  raw points (404 vs 314) but loses badly on VORP (106 vs 189) because QB
  replacement level here is enormous.
- Plan: picks 10/27/46/63/82/99 are RB/WR only; QB at 118 (Purdy, one pick
  ahead of ADP); DEF and K deliberately last (both carry +50 to +105 value
  at ADP 174-228 in this scoring).
- FORMAT VETO NOTE: CLAUDE.md's general "late-round QB is dead in 6-pt-TD
  leagues" rule is a heuristic, not a law — it assumed a QB-less roster and
  a draining pool. Here a keeper QB already exists and 18 one-QB teams
  cannot drain 14+ startable arms before pick 139. Verify per board, per
  season; do not carry this revision forward blindly.
- Then the Hero RB shape resumes: WR/RB value R3-7, IDP R8+, stashes late.
- Full pick-by-pick plan: `fantasy-mexica-draft-plan.md`.

Pivot branches: Hero WR (if 6+ RBs gone at #10, take Nacua/Chase tier);
QB-first inversion (if a top-3 QB inexplicably reaches #10, take him, RB at 27).

### 🪓 Guillotine MX — 18t, superflex, 6-pt pass TD, full PPR
**Default branch: QB HAMMER — no other archetype is legal here**
- 36 QB slots vs ~32 startable QBs: 3 QBs in your first 4-5 picks. Our board
  has QBs as 15 of the top 17; the market (ADP) underprices the middle tier
  by 30-50 picks — you can hammer QBs AND get value doing it.
- After 3 QBs: floor RB/WR volume only (guillotine = survive weekly).
  No stashes, no rookies-in-waiting, K/DEF don't exist here.

Pivot branch (only one): if the room also hammers QBs early (QB run in R1-2),
take the best RB/WR floor available and re-enter the QB queue one tier lower —
never leave round 6 with fewer than 2 QBs.

### 🪓 Guillotine TRC — 18t, full PPR, 1QB, $1000 FAAB
**Default branch: ROBUST RB (floor variant) + LATE-ISH QB**
- Guillotine floor logic + 18-team RB scarcity = two secure-role RBs in the
  first three rounds beats a hero build; volatility is death in this format.
- QB: flat tier says wait, but 18 teams drain it — target **R7-9**, never
  past ~QB16. TE: mid-round floor guy; no early TE unless Bowers falls a round.
- Every pick must produce week 1. Zero stashes. Hoard FAAB for eliminations.

Pivot branches: Hero WR (if slot lands 1.13-1.18 and the RB tier is dead by
your first pick); Balanced (if PPR WR value floods rounds 2-4).

---

## The switching protocol (live, at every one of your picks)

State = current branch + roster so far + which tiers died since your last pick.
Check the triggers **in this order** — first one that fires wins:

1. **ELITE FALLER** — a single-player-tier guy (his own tier on our board) is
   available ≥12 picks past his ADP → take him, then re-branch around him.
   Value cliffs beat plans; a plan that refuses a falling Bowers/Allen is a
   bad plan.
2. **QB EMERGENCY** (1QB leagues running late-QB) — count startable QBs left
   (our tier 2-3) vs QB-empty teams picking before your next turn. When
   startable ≤ needy + 2 → take your QB NOW. This is the trigger that keeps
   late-round QB from becoming no-QB.
3. **TIER DEATH AT NEED** — the tier you planned to hit at this pick has ≤1
   player left → take the last one now, or if already gone, switch to the
   branch that draws from a living tier (Hero RB → Hero WR is the usual flip).
4. **RUN DETECTED** — 3+ consecutive picks at one position since your last
   turn → runs in 18-teamers don't stop; jump one round early on the next
   tier at that position if you need it, or ignore the run entirely if your
   branch doesn't (never chase a run into a dead tier).
5. **NONE FIRED** → continue the branch: take the dashboard's top pick that
   fits it.

Branch switches are announced explicitly in my on-deck briefs during live
drafts: "Branch: Hero RB, healthy" / "SWITCHING → Hero WR: RB T3 died at
pick 40." The dashboard's urgency chips (⏳ gone, ⛰ last-in-tier) are the
trigger inputs — the protocol is why the numbers say what they say.

**Discipline rule:** one switch per trigger, never per hunch. The 2026
consensus and our own math agree on the failure mode: managers who abandon
structure mid-draft because of one surprising pick end up with no structure
at all. Triggers are the only exits.
