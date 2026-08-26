#!/usr/bin/env python3
"""Live draft assistant. Reads the draft in real time, recommends picks.

Usage:
  python3 scripts/live_draft.py <league_id>            one-shot: state + advice
  python3 scripts/live_draft.py <league_id> --watch    poll every 10s until draft ends
  python3 scripts/live_draft.py <league_id> --exclude <pid,pid>   manually mark
        players unavailable (safety valve if the API ever lags the room)

Board = our rankings: VORP under exact league scoring (+ config overrides),
intel layer, tiers. Advice = urgency-aware: what to take now vs safe to wait.
`compute_advice()` returns structured data (used by draft_dashboard.py);
`advise()` prints it for the CLI.
"""

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sleeper import analysis, api, intel, usage  # noqa: E402
from sleeper.reports import get_league_corrected  # noqa: E402

POLL_SECONDS = 10
# Roster construction guardrails (per drafted-position counts, keeper included)
CAPS = {"QB": 3, "RB": 7, "WR": 7, "TE": 2, "DL": 2, "LB": 2, "DB": 2, "K": 1, "DEF": 1}
LATE_ONLY = {"K", "DEF"}          # only in the final 3 rounds
STASH_ROUNDS_FROM_END = 4          # league-winner window


def _style(stats, scoring, pos):
    """Classify a projected stat line as floor / ceiling / balanced.

    Heuristic: production built on volume (receptions, carries, attempts)
    is stable week to week; production concentrated in touchdowns and big
    plays is volatile. Floor = low TD-share + real volume. Ceiling = high
    TD-share or thin volume. A championship roster wants both kinds.
    """
    if pos in ("K", "DEF", "DL", "LB", "DB"):
        return None
    total = analysis.score_stat_line(stats, scoring)
    if total <= 40:
        return None
    td = analysis.score_stat_line(
        {k: v for k, v in stats.items() if k.endswith("_td")}, scoring)
    gp = stats.get("gp") or 17
    volume = ((stats.get("rec") or 0) / gp >= 4.5
              or (stats.get("rush_att") or 0) / gp >= 11
              or (stats.get("pass_att") or 0) / gp >= 28)
    td_share = td / total if total else 0
    if td_share <= 0.32 and volume:
        return "floor"
    if td_share >= 0.38 or (not volume and td_share >= 0.30):
        return "ceiling"
    return "balanced"


def load_context(league_id):
    config = json.loads((ROOT / "config.json").read_text())
    league = get_league_corrected(league_id)
    draft = api.get_league_drafts(league_id)[0]
    players = api.get_players()
    season = str(config.get("season") or api.get_state()["league_season"])
    board, _ = analysis.draft_board(league, season, players, top_n=700)
    intel.apply_intel(board, players)
    slots = league["roster_positions"]
    superflex = "SUPER_FLEX" in slots or slots.count("QB") >= 2
    scoring = league["scoring_settings"]
    adp_key = ("adp_2qb" if superflex else "adp_ppr" if scoring.get("rec", 0) >= 1
               else "adp_half_ppr" if scoring.get("rec", 0) >= 0.5 else "adp_std")
    adp = {}
    sproj = {}
    style = {}
    for p in api.get_season_projections(season, analysis.league_positions(league)):
        st = p.get("stats") or {}
        a = st.get(adp_key)
        if a and a < 999:
            adp[p["player_id"]] = a
        sproj[p["player_id"]] = analysis.score_stat_line(st, scoring)
        pl = p.get("player") or players.get(p["player_id"]) or {}
        pos = analysis.canonical_pos(pl)
        s = _style(st, scoring, pos)
        if s:
            style[p["player_id"]] = s
    # Risk index: last-season durability (games active) + age curve +
    # current injury + volatility. Applied as a systematic VORP discount
    # BEFORE tiers form, so tiers/ranks reflect risk-adjusted value.
    # ONE shared pipeline with reports.draft_report (coherence rule).
    prev_season = str(int(season) - 1)
    analysis.apply_standard_risk(board, league, season, players, style_map=style)
    analysis._assign_tiers(board)
    # Last-season usage shares — the experts' "stickiest" stats (visibility
    # columns; projections already price expected roles, so no VORP change).
    try:
        shares = usage.usage_shares(prev_season)
        for r in board:
            r.update(shares.get(r["player_id"], {}))
    except Exception:
        pass  # usage data unavailable: columns simply stay empty
    winners = {w["player_id"]: w for w in
               analysis.league_winners(league, players, sproj, adp, superflex)}
    return config, league, draft, players, board, adp, winners, style, risk


def my_pick_numbers(draft, user_id, n_teams, rounds):
    """Pick schedule honoring the draft's real type: snake (default),
    linear (Sleeper's rookie-draft default — every round runs 1..N), and
    snake's reversal_round setting (e.g. 3rd-round reversal doubles the
    same direction once, flipping parity from that round on)."""
    slot = (draft.get("draft_order") or {}).get(user_id)
    if not slot:
        return None, []
    dtype = draft.get("type") or "snake"
    reversal = (draft.get("settings") or {}).get("reversal_round") or 0
    picks = []
    for r in range(1, rounds + 1):
        if dtype == "linear":
            forward = True
        else:  # snake, with optional reversal round
            forward = r % 2 == 1
            if reversal and r >= reversal:
                forward = not forward
        pk = (r - 1) * n_teams + slot if forward else r * n_teams - slot + 1
        picks.append(pk)
    return slot, picks


def _player_dict(players, pid, adp=None):
    p = players.get(pid) or {}
    return {
        "player_id": pid,
        "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or pid,
        "pos": analysis.canonical_pos(p) or "?",
        "team": p.get("team") or "FA",
        "injury": p.get("injury_status") or "",
        "adp": adp,
    }


ELITE_CAP_PER_POS = 3


def compute_elite_ids(board, league=None):
    """'Elite' = the true standout tier at a position, not just 'no cliff
    found yet.' Tier 1 from analysis._assign_tiers can balloon to 100+
    players on flat, low-differentiation positions (deep IDP, kickers)
    where no real value gap ever appears — that's a limitation of gap
    clustering on a homogeneous pool, not genuine elite status (verified:
    one league's "tier 1" DL group spanned +27 to -51 VORP, 194 players).
    Cap to the top few by VORP within tier 1, and require positive VORP
    (meaningfully above replacement), so elite stays a small, real signal —
    usually 1-3 players per position, matching how the term is actually used.
    """
    # K is excluded everywhere (flat position, no real elite tier). In
    # DYNASTY leagues DEF is excluded too (user decision 2026-08-24): DEF is
    # a streaming commodity there, and a crown invites paying up for one.
    exclude = {"K"}
    if league is not None and (league.get("settings") or {}).get("type") == 2:
        exclude.add("DEF")
    by_pos = defaultdict(list)
    for r in board:
        if r["pos"] in exclude:
            continue
        if r.get("tier") == 1 and r["vorp"] > 0:
            by_pos[r["pos"]].append(r)
    ids = set()
    for rows in by_pos.values():
        rows.sort(key=lambda r: -r["vorp"])
        ids.update(r["player_id"] for r in rows[:ELITE_CAP_PER_POS])
    return ids


def _build_sleeper_queue(live, adp, winners, players, rounds, n, horizon, style, elite_ids):
    """Players the market misprices in THIS league (our rank far ahead of
    ADP) plus contingent league-winners — the names to not forget as the
    draft unfolds. Ordered by draft window (ADP). `horizon` is the pick
    number by which we know our next turn falls, or None if the draft slot
    isn't set yet (commissioner hasn't randomized order) — "closing" is
    simply omitted in that case rather than guessed.
    """
    queue = []
    for r in live[:400]:
        pid = r["player_id"]
        if r["pos"] in ("K", "DEF", "DL", "LB", "DB"):
            continue  # streamable positions: ADP gaps there are noise, not sleepers
        a = adp.get(pid)
        gap = (a - r["rank"]) if (a and a <= rounds * n) else None
        is_value = gap is not None and gap >= 15 and a >= 30
        is_winner = pid in winners
        if not (is_value or is_winner):
            continue
        window_pick = a if a else rounds * n  # winners w/o ADP: anytime late
        queue.append({
            **_player_dict(players, pid, a),
            "pos_rank": r["pos_rank"], "tier": r["tier"], "vorp": r["vorp"],
            "value": round(gap, 0) if gap is not None else None,
            "type": "winner" if is_winner and not is_value else
                    "both" if is_winner else "value",
            "why": winners[pid]["why"] if is_winner else
                   f"Board rank {r['rank']} vs ADP {a:.0f} in this scoring",
            "style": style.get(pid), "elite": pid in elite_ids,
            "window_round": min(rounds, int((window_pick - 1) // n + 1)),
            "closing": a is not None and horizon is not None and a <= horizon + n,
        })
    queue.sort(key=lambda q: (not q["closing"], q["window_round"], -(q["value"] or 0)))
    return queue[:14]


def _round_plan(live, mine, made, next_open, adp, style, winners, players, n, rounds, elite_ids):
    """For each of my next picks, simulate market removals by ADP and offer
    one candidate per lane: 🚀 upside (ceiling), 💤 sleeper (value gap or
    league-winner), 🛡 safe (floor). Recomputed on every pick, so the plan
    adapts live as players come off the board.

    A player is only offered at a round if it's his NOW-OR-NEVER moment:
    still on the board at this pick, but his ADP says the room takes him
    before my next turn. Offering a player any earlier wastes the pick —
    e.g. an ADP-42 sleeper must never appear as a round-1 option when my
    round-2 pick is #27; his slot is round 2, the last realistic moment.
    A lane can legitimately be empty ("—"): nothing at that lane needs
    taking this round, which is itself useful information. The final
    planned round has no next-pick horizon, so anything available shows.
    """
    future = [p for p in mine if p >= next_open and p not in made][:6]
    if not future:
        return []
    my_picks = set(mine)
    skill = ("K", "DEF", "DL", "LB", "DB")
    # sleeper set: full value-gap criteria (not the display-limited queue)
    sleeper_ids = {r["player_id"] for r in live
                   if r["pos"] not in skill
                   and (a := adp.get(r["player_id"])) and a <= rounds * n
                   and a >= 30 and a - r["rank"] >= 15} | set(winners)
    adp_sorted = sorted((r["player_id"] for r in live if adp.get(r["player_id"])),
                        key=lambda pid: adp[pid])
    removed, shown, idx, cur, plan = set(), set(), 0, next_open, []
    # Max 2 appearances of one position per lane across the plan — a lane
    # that says "QB" six rounds straight isn't a plan, it's a rut.
    lane_pos_count = {"upside": {}, "sleeper": {}, "safe": {}}
    for p in future:
        n_removals = sum(1 for i in range(cur, p) if i not in made and i not in my_picks)
        for _ in range(n_removals):
            while idx < len(adp_sorted) and adp_sorted[idx] in removed:
                idx += 1
            if idx < len(adp_sorted):
                removed.add(adp_sorted[idx]); idx += 1
        cur = p + 1
        # Now-or-never horizon: my next pick after this one (full schedule,
        # not just the displayed window). Last planned round → no horizon.
        next_mine = next((q for q in mine if q > p and q not in made), None)
        is_last_planned = p == future[-1]

        def dying(r):
            if is_last_planned or next_mine is None:
                return True
            a = adp.get(r["player_id"])
            return a is not None and a <= next_mine + 3

        avail = [r for r in live
                 if r["player_id"] not in removed and r["player_id"] not in shown
                 and dying(r)]

        def best(pred, exclude_ids, lane):
            for r in avail:  # live is board-order (best value first)
                pid = r["player_id"]
                if (pid not in exclude_ids and pred(r)
                        and lane_pos_count[lane].get(r["pos"], 0) < 2):
                    return r
            return None

        used = set()
        lanes = {}
        def pick_upside():
            # Best ceiling vs best balanced, compared on VORP with a modest
            # edge for the true ceiling — a weak pure-ceiling guy should not
            # beat a stud balanced player (nor the reverse, blindly).
            c = best(lambda r: style.get(r["player_id"]) == "ceiling"
                     and r["pos"] not in skill, used, "upside")
            b = best(lambda r: style.get(r["player_id"]) == "balanced"
                     and r["pos"] not in skill, used, "upside")
            if c and b:
                return c if c["vorp"] + 15 >= b["vorp"] else b
            return c or b

        lane_defs = (
            ("upside", pick_upside),
            ("sleeper", lambda: best(
                lambda r: r["player_id"] in sleeper_ids, used, "sleeper")),
            # safe: floor OR balanced in pure board order — preferring a
            # weaker floor player over a stronger balanced one buries the
            # best boring pick (the Derrick Henry problem).
            ("safe", lambda: best(
                lambda r: style.get(r["player_id"]) in ("floor", "balanced")
                and r["pos"] not in skill, used, "safe")),
        )
        for lane, chooser in lane_defs:
            r = chooser()
            if r:
                pid = r["player_id"]
                used.add(pid); shown.add(pid)
                lane_pos_count[lane][r["pos"]] = lane_pos_count[lane].get(r["pos"], 0) + 1
                lanes[lane] = {
                    **_player_dict(players, pid, adp.get(pid)),
                    "pos_rank": r["pos_rank"], "tier": r["tier"],
                    "vorp": r["vorp"], "style": style.get(pid),
                    "elite": pid in elite_ids,
                }
        plan.append({"round": (p - 1) // n + 1, "pick_no": p, **lanes})
    return plan


def compute_advice(league_id, exclude=frozenset(), ctx=None):
    """Full decision state as a structured dict."""
    config, league, draft, players, board, adp, winners, style, risk = ctx or load_context(league_id)
    n = league["total_rosters"]
    rounds = draft["settings"]["rounds"]
    uid = config["user_id"]
    picks = api.get_draft_picks(draft["draft_id"], ttl=0) or []
    made = {p["pick_no"] for p in picks}
    taken = {p["metadata"]["player_id"] for p in picks} | set(exclude)
    slot, mine = my_pick_numbers(draft, uid, n, rounds)
    if draft.get("status") == "complete":
        # Draft picks alone under-represent a real roster (waiver adds,
        # trades, prior seasons) — use the actual current roster instead.
        my_roster = next((r for r in api.get_rosters(league["league_id"])
                          if r.get("owner_id") == uid or uid in (r.get("co_owners") or [])), None)
        my_ids = set((my_roster or {}).get("players") or [])
    else:
        # picked_by is the ACTUAL picker — draft_slot alone misattributes a
        # traded pick made by its new owner at the user's original slot.
        # Slot is only the fallback for autopicks that carry no picked_by.
        my_ids = {p["metadata"]["player_id"] for p in picks
                  if p.get("picked_by") == uid
                  or (not p.get("picked_by") and p.get("draft_slot") == slot)}
    next_open = next(i for i in range(1, rounds * n + 2) if i not in made)
    my_next = next((p for p in mine if p >= next_open and p not in made), None)
    vorp_of = {r["player_id"]: r["vorp"] for r in board}
    # Computed once from the full frozen `board` (not the shrinking `live`
    # pool), so a player stays tagged elite all draft long even after other
    # tier-1 peers get drafted, and it still applies to rostered players.
    elite_ids = compute_elite_ids(board, league)

    out = {
        "league": league["name"],
        "status": draft["status"],
        "slot": slot,
        "round": (next_open - 1) // n + 1,
        "rounds": rounds,
        "pick_on_clock": next_open,
        "total_picks": rounds * n,
        "my_next": my_next,
        "on_clock": my_next == next_open,
        "until": None,
        "roster": sorted(
            ({**_player_dict(players, pid), "vorp": vorp_of.get(pid),
              "style": style.get(pid), "elite": pid in elite_ids,
              "risk": risk.get(pid)} for pid in my_ids),
            key=lambda d: -(d["vorp"] or 0)),
        "recs": [], "waiters": [], "stashes": [], "stash_window": False,
        "sleeper_queue": [], "balance": None, "round_plan": [],
        "last_picks": [
            {**_player_dict(players, p["metadata"]["player_id"]), "pick_no": p["pick_no"]}
            for p in sorted(picks, key=lambda x: -x["pick_no"])[:6]
        ],
    }

    # These need only "what's been taken" and "what's on my roster" — both
    # known even before the commissioner sets the draft order (slot=None),
    # so they must NOT sit behind the my_next-is-known guard below.
    live = [r for r in board if r["player_id"] not in taken]
    floor_n = sum(1 for pid in my_ids if style.get(pid) == "floor")
    ceil_n = sum(1 for pid in my_ids if style.get(pid) == "ceiling")
    elite_n = sum(1 for pid in my_ids if pid in elite_ids)
    out["balance"] = {"floor": floor_n, "ceiling": ceil_n, "elite": elite_n,
                      "lean": ("floor" if ceil_n - floor_n >= 2 else
                               "ceiling" if floor_n - ceil_n >= 2 else None)}
    out["sleeper_queue"] = _build_sleeper_queue(
        live, adp, winners, players, rounds, n, horizon=my_next, style=style,
        elite_ids=elite_ids)

    if my_next is None:
        return out
    on_clock = out["on_clock"]
    horizon = (next((p for p in mine if p > next_open and p not in made), rounds * n)
               if on_clock else my_next)
    out["horizon"] = horizon
    out["until"] = 0 if on_clock else sum(
        1 for i in range(next_open, my_next) if i not in made)
    # Recompute with the real horizon now that we know it (more accurate
    # "closing" flags than the my_next-only estimate used above).
    out["sleeper_queue"] = _build_sleeper_queue(
        live, adp, winners, players, rounds, n, horizon=horizon, style=style,
        elite_ids=elite_ids)
    out["round_plan"] = _round_plan(
        live, mine, made, next_open, adp, style, winners, players, n, rounds,
        elite_ids=elite_ids)

    my_counts = {}
    for pid in my_ids:
        pos = analysis.canonical_pos(players.get(pid) or {}) or "?"
        my_counts[pos] = my_counts.get(pos, 0) + 1

    my_round = (my_next - 1) // n + 1
    out["stash_window"] = my_round > rounds - STASH_ROUNDS_FROM_END

    def survives(r):
        a = adp.get(r["player_id"])
        return a is None or a > horizon + 3

    # "Safe to wait" answers a DIFFERENT question than the recs bonus: not
    # "will he last until my upcoming pick" (horizon) but "can I skip him at
    # my upcoming pick and still get him at the pick AFTER that" — i.e. the
    # bar is my next-next pick, not my next pick. Conflating the two used to
    # make elite players (ADP 6-10) show as "safe to wait" whenever the next
    # personal pick was imminent, which is actively wrong advice.
    wait_horizon = next((p for p in mine if p > my_next and p not in made), rounds * n)

    def survives_to_wait(r):
        a = adp.get(r["player_id"])
        return a is None or a > wait_horizon + 3

    lean = out["balance"]["lean"]

    recs = []
    for r in live[:120]:
        pos = r["pos"]
        if my_counts.get(pos, 0) >= CAPS.get(pos, 0):
            continue
        if pos in LATE_ONLY and my_round <= rounds - 3:
            continue
        tier_left = sum(1 for x in live if x["pos"] == pos and x["tier"] == r["tier"])
        score, reasons = r["vorp"], []
        if not survives(r):
            score += 25; reasons.append({"kind": "gone", "text": "Gone by your next pick"})
        if tier_left <= 2:
            score += 15; reasons.append(
                {"kind": "tier", "text": f"Last {tier_left} in {pos} tier {r['tier']}"})
        if my_counts.get(pos, 0) == 0 and pos not in ("K", "DEF"):
            score += 10; reasons.append({"kind": "need", "text": f"No {pos} on roster"})
        if r["player_id"] in winners and out["stash_window"]:
            score += 30; reasons.append(
                {"kind": "stash", "text": winners[r["player_id"]]["why"]})
        if lean and style.get(r["player_id"]) == lean and my_round >= 3:
            score += 6; reasons.append(
                {"kind": "balance",
                 "text": f"Roster needs {lean} — he's a {lean} player"})
        recs.append((score, r, reasons))
    recs.sort(key=lambda t: -t[0])

    for score, r, reasons in recs[:8]:
        out["recs"].append({
            **_player_dict(players, r["player_id"], adp.get(r["player_id"])),
            "pos_rank": r["pos_rank"], "tier": r["tier"], "vorp": r["vorp"],
            "score": round(score, 1), "reasons": reasons, "survives": survives(r),
            "style": style.get(r["player_id"]), "elite": r["player_id"] in elite_ids,
            "risk": risk.get(r["player_id"]),
        })

    out["waiters"] = [
        {**_player_dict(players, r["player_id"], adp.get(r["player_id"])),
         "pos_rank": r["pos_rank"], "vorp": r["vorp"], "elite": r["player_id"] in elite_ids}
        for s, r, w in recs[:25] if adp.get(r["player_id"]) and survives_to_wait(r)][:6]
    if out["stash_window"]:
        out["stashes"] = [
            {**_player_dict(players, pid, adp.get(pid)),
             "why": w["why"], "category": w["category"]}
            for pid, w in winners.items() if pid not in taken][:6]
    return out


def advise(league_id, exclude=frozenset(), ctx=None):
    """CLI presentation of compute_advice()."""
    d = compute_advice(league_id, exclude, ctx)

    def label(p):
        inj = f" [{p['injury']}]" if p["injury"] else ""
        return f"{p['name']} ({p['pos']}, {p['team']}){inj}"

    print(f"\n=== {d['league']} | pick #{d['pick_on_clock']} (R{d['round']}) "
          f"| draft {d['status']} | my slot {d['slot']}")
    print("My roster so far: " + (", ".join(label(p) for p in d["roster"]) or "(empty)"))
    if d["my_next"] is None:
        print("No picks remaining."); return False
    if d["on_clock"]:
        print(f"*** YOU ARE ON THE CLOCK (pick #{d['pick_on_clock']}) "
              f"— next turn after this: #{d['horizon']}")
    else:
        print(f"My next pick: #{d['my_next']} — {d['until']} picks away")
    print("\nTOP PICKS NOW:")
    for r in d["recs"][:6]:
        why = "; ".join(x["text"] for x in r["reasons"])
        adp_s = f"{r['adp']:.0f}" if r.get("adp") else "—"
        print(f"  {r['pos_rank']:<6} T{r['tier']} {label(r):<44}"
              f" vorp={r['vorp']:>6} adp={adp_s}" + (f"  [{why}]" if why else ""))
    if d["waiters"]:
        print("SAFE TO WAIT (will last past your upcoming pick): "
              + ", ".join(p["name"] for p in d["waiters"]))
    if d.get("balance"):
        b = d["balance"]
        lean = f" — lean {b['lean'].upper()}" if b["lean"] else " — balanced"
        print(f"ROSTER BALANCE: {b['floor']} floor / {b['ceiling']} ceiling{lean}")
    if d.get("round_plan"):
        print("ROUND PLAN (🚀 upside / 💤 sleeper / 🛡 safe):")
        for rp in d["round_plan"]:
            lanes = " | ".join(
                f"{ic} {rp[k]['name']} ({rp[k]['pos_rank']})"
                for k, ic in (("upside", "🚀"), ("sleeper", "💤"), ("safe", "🛡"))
                if rp.get(k))
            print(f"  R{rp['round']:<3}#{rp['pick_no']:<5}{lanes}")
    if d.get("sleeper_queue"):
        print("SLEEPER QUEUE (don't forget):")
        for s in d["sleeper_queue"][:8]:
            closing = " ⚠CLOSING" if s["closing"] else ""
            print(f"  R{s['window_round']:<3} {label(s):<44} [{s['type']}]{closing}")
    if d["stashes"]:
        print("LEAGUE-WINNER WINDOW — top stashes still free:")
        for w in d["stashes"]:
            print(f"  🎟 {label(w)} — {w['why']}")
    return d["status"] != "complete"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    league_id = sys.argv[1]
    exclude = set()
    if "--exclude" in sys.argv:
        exclude = set(sys.argv[sys.argv.index("--exclude") + 1].split(","))
    if "--watch" in sys.argv:
        ctx = load_context(league_id)
        draft_id = ctx[2]["draft_id"]
        seen = -1
        while True:
            picks = api.get_draft_picks(draft_id, ttl=0) or []
            if len(picks) != seen:
                seen = len(picks)
                if not advise(league_id, exclude, ctx):
                    break
            time.sleep(POLL_SECONDS)
    else:
        advise(league_id, exclude)


if __name__ == "__main__":
    main()
