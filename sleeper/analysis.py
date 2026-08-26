"""Analysis engine: lineups, power rankings, waivers, trades, draft boards."""

from collections import defaultdict
from math import ceil

from . import api
from .scoring import SLOT_ELIGIBILITY, score_stat_line

INJURY_OUT = {"Out", "IR", "PUP", "Sus", "NA", "DNR", "COV"}


# ---------------------------------------------------------------- helpers


DEFAULT_POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")

# Two-way players (e.g. Travis Hunter, WR/CB) list an IDP tag in
# fantasy_positions alongside their offensive one, and Sleeper doesn't
# order it consistently (Hunter's is ['DB', 'WR'] — IDP first). Naively
# taking index 0 leaks an IDP position tag onto an offensive player even
# in leagues with no IDP slots at all. Offense is the primary fantasy
# role whenever one is present; pure IDP/DEF players are unaffected.
OFFENSE_POS_PRIORITY = ("QB", "RB", "WR", "TE", "K")


def canonical_pos(entry: dict):
    """Best single fantasy position for a player dict (a full record from
    api.get_players(), or the lighter 'player' meta dict embedded in a
    projection row) — see OFFENSE_POS_PRIORITY for why this isn't just
    fantasy_positions[0]."""
    fp = entry.get("fantasy_positions") or []
    for p in OFFENSE_POS_PRIORITY:
        if p in fp:
            return p
    if fp:
        return fp[0]
    return entry.get("position")


def league_positions(league: dict) -> tuple:
    """Which player positions to fetch projections for, given roster slots."""
    slots = set(league.get("roster_positions", []))
    pos = ["QB", "RB", "WR", "TE"]
    if "K" in slots:
        pos.append("K")
    if "DEF" in slots:
        pos.append("DEF")
    if slots & {"DL", "LB", "DB", "IDP_FLEX"}:
        pos += ["DL", "LB", "DB"]
    return tuple(pos)


def projection_map(season: str, week: int, scoring_settings: dict,
                   positions=DEFAULT_POSITIONS) -> dict:
    """player_id -> projected points under THIS league's scoring."""
    projs = api.get_week_projections(season, week, positions) or []
    return {
        p["player_id"]: score_stat_line(p.get("stats") or {}, scoring_settings)
        for p in projs
    }


def season_projection_map(season: str, scoring_settings: dict,
                          positions=DEFAULT_POSITIONS) -> dict:
    """player_id -> full-season projected points under this league's scoring."""
    projs = api.get_season_projections(season, positions) or []
    return {
        p["player_id"]: score_stat_line(p.get("stats") or {}, scoring_settings)
        for p in projs
    }


def player_label(players: dict, pid: str) -> str:
    p = players.get(pid)
    if not p:
        return pid
    pos = "/".join(p.get("fantasy_positions") or [p.get("position") or "?"])
    inj = p.get("injury_status")
    tag = f" [{inj}]" if inj else ""
    return f"{p.get('first_name', '')} {p.get('last_name', '')} ({pos}, {p.get('team') or 'FA'}){tag}"


def _positions(players: dict, pid: str) -> set:
    p = players.get(pid) or {}
    return set(p.get("fantasy_positions") or ([p["position"]] if p.get("position") else []))


# ---------------------------------------------------------------- lineup


def optimal_lineup(roster_player_ids, roster_positions, players, proj):
    """Exact max-points fill of starting slots (DP over slot subsets).

    Greedy filling mis-assigns dual-eligible players (a WR/TE dual consumed
    by the WR slot can strand the TE slot with a scrub); this solves the
    assignment exactly. Returns (lineup, bench) where lineup is
    [(slot, player_id, points)] in the league's display order.
    """
    slots = [s for s in roster_positions if s != "BN"]
    available = [
        pid for pid in roster_player_ids
        if (players.get(pid) or {}).get("injury_status") not in INJURY_OUT
    ]
    elig = {
        pid: [i for i, s in enumerate(slots)
              if _positions(players, pid) & SLOT_ELIGIBILITY.get(s, set())]
        for pid in available
    }
    # Prune: only the top-(n_slots) eligible players per slot can matter.
    cands = set()
    for i in range(len(slots)):
        el = sorted((p for p in available if i in elig[p]),
                    key=lambda p: -proj.get(p, 0.0))
        cands.update(el[: len(slots)])
    pool = sorted(cands, key=lambda p: -proj.get(p, 0.0))

    # layers[k][mask] = best total after considering pool[:k] with `mask`
    # slots filled; choice[(k, mask)] = slot index pool[k] took to reach mask.
    layers = [{0: 0.0}]
    choice = {}
    for k, pid in enumerate(pool):
        prev = layers[-1]
        cur = dict(prev)
        pts = proj.get(pid, 0.0)
        for mask, val in prev.items():
            for i in elig[pid]:
                bit = 1 << i
                if not mask & bit:
                    v2 = val + pts
                    if v2 > cur.get(mask | bit, -1.0):
                        cur[mask | bit] = v2
                        choice[(k, mask | bit)] = i
        layers.append(cur)
    final = layers[-1]
    best_mask = max(final, key=lambda m: (final[m], bin(m).count("1")))

    assigned = {}  # slot index -> pid
    mask = best_mask
    for k in range(len(pool) - 1, -1, -1):
        i = choice.get((k, mask))
        if i is not None and layers[k + 1][mask] > layers[k].get(mask, -1.0):
            assigned[i] = pool[k]
            mask &= ~(1 << i)
    lineup = [
        (s, assigned.get(i), proj.get(assigned[i], 0.0) if i in assigned else 0.0)
        for i, s in enumerate(slots)
    ]
    bench = sorted(
        set(roster_player_ids) - {pid for _, pid, _ in lineup if pid},
        key=lambda pid: -proj.get(pid, 0.0),
    )
    return lineup, bench


def lineup_delta(current_starters, roster_player_ids, roster_positions, players, proj):
    """Compare current starters vs optimal. Returns (optimal, bench, gain, swaps)."""
    lineup, bench = optimal_lineup(roster_player_ids, roster_positions, players, proj)
    optimal_pts = sum(pts for _, _, pts in lineup)
    current_pts = sum(proj.get(pid, 0.0) for pid in current_starters or [])
    optimal_ids = {pid for _, pid, _ in lineup if pid}
    swaps_in = optimal_ids - set(current_starters or [])
    swaps_out = set(current_starters or []) - optimal_ids - {"0", None}
    return lineup, bench, round(optimal_pts - current_pts, 2), (swaps_in, swaps_out)


# ------------------------------------------------------------- standings


def power_rankings(league_id: str, through_week: int):
    """All-play record + points-for based power score per roster."""
    rosters = api.get_rosters(league_id) or []
    # Align strictly by week number — index-based pairing miscounts when a
    # roster is missing a week, and one bad fetch must not truncate history.
    weeks = {}  # wk -> {roster_id: pts}
    for wk in range(1, max(through_week, 1) + 1):
        try:
            ms = api.get_matchups(league_id, wk) or []
        except Exception:
            continue
        scores = {m["roster_id"]: m["points"] for m in ms
                  if m.get("points") is not None}
        # A week nobody has scored in yet is an unplayed week, not 0-0 ties.
        if scores and any(v > 0 for v in scores.values()):
            weeks[wk] = scores
    allplay = defaultdict(lambda: [0, 0])
    for scores in weeks.values():
        for rid, pts in scores.items():
            for orid, o in scores.items():
                if orid == rid:
                    continue
                if pts > o:
                    allplay[rid][0] += 1
                elif pts < o:
                    allplay[rid][1] += 1
    out = []
    for r in rosters:
        rid = r["roster_id"]
        s = r.get("settings", {})
        pf = s.get("fpts", 0) + s.get("fpts_decimal", 0) / 100
        w, l = allplay.get(rid, (0, 0))
        out.append({
            "roster_id": rid,
            "owner_id": r.get("owner_id"),
            "record": f"{s.get('wins', 0)}-{s.get('losses', 0)}"
                      + (f"-{s['ties']}" if s.get("ties") else ""),
            "pf": round(pf, 1),
            "allplay": f"{w}-{l}",
            "allplay_pct": w / (w + l) if (w + l) else 0.0,
        })
    out.sort(key=lambda x: (-x["allplay_pct"], -x["pf"]))
    return out


# --------------------------------------------------------------- waivers


def waiver_targets(league_id: str, players: dict, proj: dict, season_proj: dict, limit: int = 15):
    """Trending + high-projection free agents not on any roster."""
    rostered = set()
    for r in api.get_rosters(league_id) or []:
        rostered.update(r.get("players") or [])
    trending = {t["player_id"]: t["count"] for t in api.get_trending("add", 24, 200) or []}
    candidates = {}
    for pid in set(trending) | {p for p, v in proj.items() if v >= 8}:
        if pid in rostered or pid not in players:
            continue
        pl = players[pid]
        if pl.get("injury_status") in INJURY_OUT or not pl.get("team"):
            continue
        candidates[pid] = {
            "player_id": pid,
            "trend_count": trending.get(pid, 0),
            "week_proj": proj.get(pid, 0.0),
            "season_proj": season_proj.get(pid, 0.0),
        }
    # Blend: trending count signals breaking news the projections haven't caught.
    ranked = sorted(
        candidates.values(),
        key=lambda c: -(c["season_proj"] + c["week_proj"] * 2 + min(c["trend_count"], 50000) / 2500))
    return ranked[:limit]


def recent_drops(league_id: str, players: dict, season_proj: dict,
                 hours: int = 72, min_season_proj: float = 40.0):
    """Players other managers dropped recently who are still free agents.

    The "drop it like it's hot" scan: a good player hitting waivers is the
    cheapest acquisition in fantasy, and drops often precede news going wide
    (the dropper knows something, or is making a mistake worth pouncing on).
    Returns [{player_id, dropped_by, hours_ago, season_proj, trend_count}],
    best value first. Transactions live in round/week buckets; scans the
    current-week bucket plus the previous one so nothing at a boundary hides.
    """
    import time as _time
    now_ms = _time.time() * 1000
    state = api.get_state() or {}
    week = max(state.get("week") or 1, 1)
    txs = []
    for w in {week, max(week - 1, 1), 1}:
        txs.extend(api.get_transactions(league_id, w) or [])
    rostered = set()
    for r in api.get_rosters(league_id) or []:
        rostered.update(r.get("players") or [])
    users = {u["user_id"]: u.get("display_name") or "?"
             for u in api.get_league_users(league_id) or []}
    roster_owner = {r["roster_id"]: users.get(r.get("owner_id"), "?")
                    for r in api.get_rosters(league_id) or []}
    trending = {t["player_id"]: t["count"] for t in api.get_trending("add", 24, 300) or []}
    seen, out = set(), []
    for t in txs:
        ts = t.get("status_updated") or 0
        if t.get("status") != "complete" or (now_ms - ts) > hours * 3600 * 1000:
            continue
        for pid, rid in (t.get("drops") or {}).items():
            if pid in seen or pid in rostered:
                continue  # already re-claimed, or duplicated across buckets
            seen.add(pid)
            sp = season_proj.get(pid, 0.0)
            if sp < min_season_proj and trending.get(pid, 0) < 5000:
                continue
            out.append({
                "player_id": pid,
                "dropped_by": roster_owner.get(rid, "?"),
                "hours_ago": round((now_ms - ts) / 3600000),
                "season_proj": round(sp),
                "trend_count": trending.get(pid, 0),
            })
    out.sort(key=lambda d: -(d["season_proj"] + min(d["trend_count"], 50000) / 500))
    return out


# ---------------------------------------------------------------- trades


def positional_needs(roster_player_ids, roster_positions, players, season_proj):
    """Per-position starter-quality surplus/deficit for one roster.

    Returns {pos: {'starters_needed': n, 'quality': [top season projections]}}
    """
    need = defaultdict(int)
    for slot in roster_positions:
        if slot == "BN":
            continue
        elig = SLOT_ELIGIBILITY.get(slot, set())
        if len(elig) == 1:
            need[next(iter(elig))] += 1
        else:  # count flex demand fractionally against RB/WR/TE pool
            for p in elig:
                need[p] += 1 / len(elig)
    by_pos = defaultdict(list)
    for pid in roster_player_ids:
        for pos in _positions(players, pid):
            by_pos[pos].append(season_proj.get(pid, 0.0))
    out = {}
    for pos, n in need.items():
        vals = sorted(by_pos.get(pos, []), reverse=True)
        # Ceil, not round: superflex adds fractional QB demand (1.25) that
        # rounding erased — a superflex team wants 2 startable QBs. The
        # epsilon absorbs float dust from summed 1/3 flex shares.
        n_int = max(1, ceil(n - 1e-9))
        out[pos] = {
            "starters_needed": n_int,
            "top": vals[: n_int + 1],
            "depth_score": sum(vals[: n_int + 1]),
        }
    return out


def trade_suggestions(league_id: str, my_roster_id: int, players, season_proj, roster_positions):
    """Find complementary-need trade partners: I'm deep where they're thin and vice versa."""
    rosters = api.get_rosters(league_id)
    needs = {
        r["roster_id"]: positional_needs(r.get("players") or [], roster_positions, players, season_proj)
        for r in rosters
    }
    mine = needs.get(my_roster_id, {})
    ideas = []
    for rid, theirs in needs.items():
        if rid == my_roster_id:
            continue
        for pos in ("QB", "RB", "WR", "TE"):
            m, t = mine.get(pos), theirs.get(pos)
            if not m or not t:
                continue
            # I have surplus (bench piece projects near starter level), they're thin.
            my_surplus = len(m["top"]) > m["starters_needed"] and m["top"][-1] > 90
            their_thin = len(t["top"]) <= t["starters_needed"] or (t["top"] and t["top"][-1] < 80)
            if my_surplus and their_thin:
                ideas.append({"partner_roster_id": rid, "i_send_pos": pos,
                              "note": f"They are thin at {pos}; my depth piece there has real value to them."})
    return ideas


# ------------------------------------------------------- slot values


def slot_values(league, board, k_rounds: int = 6):
    """Expected value of each draft slot: simulate the first k_rounds with
    opponents drafting by ADP while the evaluated slot takes best VORP at
    each of its turns. Captures the experts' point that a slot's worth is
    its two-pick turn combos, not its first pick.

    Returns [{slot, total_vorp, picks: [(pick_no, name-ish row), ...]}, ...]
    sorted best-first.
    """
    n = league.get("total_rosters", 12)
    adp_pool = sorted((r for r in board if r.get("adp")), key=lambda r: r["adp"])
    results = []
    for slot in range(1, n + 1):
        my_picks = set()
        for rd in range(1, k_rounds + 1):
            my_picks.add((rd - 1) * n + slot if rd % 2 else rd * n - slot + 1)
        taken = set()
        idx = 0
        picks = []
        for pick_no in range(1, k_rounds * n + 1):
            if pick_no in my_picks:
                best = next((r for r in board if r["player_id"] not in taken), None)
                if best:
                    taken.add(best["player_id"])
                    picks.append((pick_no, best))
            else:
                while idx < len(adp_pool) and adp_pool[idx]["player_id"] in taken:
                    idx += 1
                if idx < len(adp_pool):
                    taken.add(adp_pool[idx]["player_id"])
                    idx += 1
        results.append({
            "slot": slot,
            "total_vorp": round(sum(r["vorp"] for _, r in picks), 1),
            "picks": picks,
        })
    results.sort(key=lambda s: -s["total_vorp"])
    return results


# ------------------------------------------------------------- risk

# Positional age curves: (age risk starts, points per year past it, cap).
# Grounded in the established aging research: RBs cliff earliest (~27-28,
# mileage-driven); WRs decline after ~29-30; TEs break out late and last
# into their early 30s; QBs age slowest (pocket passers into late 30s);
# IDP speed positions (LB/DB) fade in the late 20s, DL slightly later.
# K/DEF: age is irrelevant.
AGE_RISK = {
    "RB": (26, 8, 35),
    "WR": (29, 8, 30),
    "TE": (30, 7, 28),
    "QB": (34, 6, 25),
    "LB": (29, 6, 20),
    "DB": (29, 6, 20),
    "DL": (30, 6, 20),
}

INJURY_RISK_POINTS = {
    "Questionable": 10, "Doubtful": 20, "Out": 25, "Sus": 25,
    "IR": 35, "PUP": 35, "NA": 35, "DNR": 35, "COV": 35,
}

RISK_VORP_DISCOUNT = 0.12  # max % of positive VORP shaved at risk score 100


def risk_index(player: dict, pos: str, prev_games, style=None) -> dict:
    """Composite 0-100 risk score with human-readable factors.

    Components: positional age curve, last-season durability (games active),
    current injury status, rookie uncertainty, weekly volatility (ceiling
    style). Systematic by construction — no per-player judgment.
    """
    score, factors = 0, []
    age = player.get("age")
    curve = AGE_RISK.get(pos)
    if age and curve:
        start, per_year, cap = curve
        if age >= start:
            pts = min((age - start + 1) * per_year, cap)
            score += pts
            factors.append(f"Age {age} — past the typical {pos} decline point ({start}+)")
    years_exp = player.get("years_exp")
    if years_exp == 0:
        score += 8
        factors.append("Rookie — no NFL durability track record")
    elif prev_games is not None:
        if prev_games >= 16:
            pass
        elif prev_games >= 14:
            score += 10; factors.append(f"Missed time last season ({prev_games:.0f} games active)")
        elif prev_games >= 10:
            score += 20; factors.append(f"Missed significant time last season ({prev_games:.0f} games)")
        else:
            score += 30; factors.append(f"Major missed time last season ({prev_games:.0f} games)")
    elif years_exp and years_exp > 0 and pos not in ("DEF",):
        score += 30
        factors.append("No games last season (missed year / not on a roster)")
    inj = player.get("injury_status")
    if inj and inj in INJURY_RISK_POINTS:
        score += INJURY_RISK_POINTS[inj]
        part = player.get("injury_body_part")
        factors.append(f"Currently {inj}" + (f" ({part})" if part and part != "Undisclosed" else ""))
    if style == "ceiling":
        score += 5
        factors.append("TD/big-play dependent — volatile week to week")
    score = min(score, 100)
    band = "low" if score < 20 else "med" if score < 45 else "high"
    return {"score": score, "band": band, "factors": factors}


def apply_risk(board, risk_map):
    """Shave up to RISK_VORP_DISCOUNT of positive VORP by risk score, then
    re-rank. A systematic, documented discount for downside tail risk that
    mean projections don't carry — NOT a per-player judgment call."""
    for r in board:
        risk = risk_map.get(r["player_id"])
        if risk and r["vorp"] > 0 and risk["score"]:
            r["vorp"] = round(r["vorp"] * (1 - RISK_VORP_DISCOUNT * risk["score"] / 100), 1)
    board.sort(key=lambda r: -r["vorp"])
    pos_rank = defaultdict(int)
    for i, r in enumerate(board):
        r["rank"] = i + 1
        pos_rank[r["pos"]] += 1
        r["pos_rank"] = f"{r['pos']}{pos_rank[r['pos']]}"
        r["value"] = round((r["adp"] - r["rank"]), 1) if r.get("adp") else None
    return board


def style_class(stats, scoring, pos):
    """Classify a projected stat line as floor / ceiling / balanced.

    Heuristic: production built on volume (receptions, carries, attempts)
    is stable week to week; production concentrated in touchdowns and big
    plays is volatile. Floor = low TD-share + real volume. Ceiling = high
    TD-share or thin volume. A championship roster wants both kinds.
    """
    if pos in ("K", "DEF", "DL", "LB", "DB"):
        return None
    total = score_stat_line(stats, scoring)
    if total <= 40:
        return None
    td = score_stat_line(
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


def apply_standard_risk(board, league, season, players, style_map=None):
    """The ONE risk pipeline every board surface must run (coherence rule:
    draft reports and the dashboard must rank identically). Builds the
    style map (unless given), prior-season durability, per-player risk
    index, then applies the systematic VORP discount and re-ranks.
    Returns the style map so callers can reuse it."""
    scoring = league.get("scoring_settings", {})
    positions = league_positions(league)
    if style_map is None:
        style_map = {}
        for p in api.get_season_projections(season, positions) or []:
            st = p.get("stats") or {}
            pl = p.get("player") or players.get(p["player_id"]) or {}
            s = style_class(st, scoring, canonical_pos(pl))
            if s:
                style_map[p["player_id"]] = s
    prev_games = {}
    try:
        for p in api.get_season_stats(str(int(season) - 1), positions) or []:
            g = (p.get("stats") or {}).get("gms_active")
            if g is not None:
                prev_games[p["player_id"]] = g
    except Exception:
        pass  # durability data unavailable: risk falls back to age+injury only
    risk = {}
    for r in board:
        pl = players.get(r["player_id"]) or {}
        risk[r["player_id"]] = risk_index(
            pl, r["pos"], prev_games.get(r["player_id"]),
            style_map.get(r["player_id"]))
    apply_risk(board, risk)
    return style_map


# ---------------------------------------------------- league winners


def league_winners(league: dict, players: dict, season_proj: dict, adp: dict,
                   superflex: bool = False, limit: int = 20):
    """Late-round picks with contingent league-winning upside.

    These are NOT best-available-now players: each has a realistic path to a
    top-12 positional role that current projections can't price (an injury
    ahead of them, a role battle, a year-2 leap). Draft capital: the last
    3-4 rounds, where the alternative is a replacement-level veteran.
    """
    from .intel import team_env
    env = team_env()
    out = []

    # Positional projection ranks for context
    pos_rank = {}
    by_pos = defaultdict(list)
    for pid, v in season_proj.items():
        for pos in _positions(players, pid):
            by_pos[pos].append((v, pid))
    for pos, vals in by_pos.items():
        for i, (v, pid) in enumerate(sorted(vals, reverse=True), 1):
            pos_rank.setdefault((pos, pid), i)

    # Team RB rooms from depth charts
    rooms = defaultdict(list)
    for pid, p in players.items():
        if p.get("position") == "RB" and p.get("team") and p.get("depth_chart_order"):
            rooms[p["team"]].append((p["depth_chart_order"], pid))

    for team, room in rooms.items():
        room.sort()
        if len(room) < 2:
            continue
        starter, backup = room[0][1], room[1][1]
        st_rank = pos_rank.get(("RB", starter), 99)
        bu_adp = adp.get(backup)
        tier = (env.get(team) or {}).get("offense_tier", 3)
        st = players[starter]
        # 1. Handcuff to a heavy workload: starter is a top-18 RB, backup cheap
        if st_rank <= 18 and (bu_adp is None or bu_adp > 110) and tier <= 3:
            frail = " (starter already " + st["injury_status"] + ")" if st.get("injury_status") else ""
            out.append({
                "player_id": backup, "category": "handcuff",
                "score": (19 - st_rank) * 3 + (4 - tier) * 5 + (10 if frail else 0),
                "why": f"Direct backup to {st['first_name']} {st['last_name']} "
                       f"(RB{st_rank}){frail}; inherits a top-12 workload on contact",
            })
        # 2. Ambiguous backfield on a good offense: top two project close
        p1, p2 = season_proj.get(starter, 0), season_proj.get(backup, 0)
        if tier <= 2 and p1 > 0 and p2 / max(p1, 1) > 0.72 and (bu_adp is None or bu_adp > 90):
            out.append({
                "player_id": backup, "category": "ambiguous-backfield",
                "score": 20 + (3 - tier) * 6,
                "why": f"Near-even timeshare with {st['first_name']} {st['last_name']} "
                       f"on a tier-{tier} offense; winner becomes a weekly RB2",
            })

    # 3. Year-2/3 WR breakout profile on a functional offense
    for pid, p in players.items():
        if p.get("position") != "WR" or not p.get("team"):
            continue
        a = adp.get(pid)
        tier = (env.get(p["team"]) or {}).get("offense_tier", 3)
        wr_rank = pos_rank.get(("WR", pid), 999)
        if (p.get("years_exp") in (1, 2) and (p.get("age") or 99) <= 24
                and tier <= 3 and (a is None or a > 100) and 25 <= wr_rank <= 75):
            out.append({
                "player_id": pid, "category": "year2-breakout",
                "score": (76 - wr_rank) * 0.5 + (4 - tier) * 4,
                "why": f"Year-{p['years_exp']+1} WR, age {p.get('age')}, tier-{tier} "
                       f"offense, already projects WR{wr_rank} with classic breakout profile",
            })

    # 4. Superflex only: cheap QBs with a path to every-week starter value
    if superflex:
        for pid, p in players.items():
            if p.get("position") == "QB" and p.get("team") and p.get("depth_chart_order") == 2:
                a = adp.get(pid)
                q_rank = pos_rank.get(("QB", pid), 999)
                if q_rank <= 40 and (a is None or a > 130):
                    out.append({
                        "player_id": pid, "category": "qb-stash",
                        "score": 15, "why": "One depth-chart move from superflex starter value",
                    })

    seen, ranked = set(), []
    for c in sorted(out, key=lambda c: -c["score"]):
        if c["player_id"] not in seen:
            seen.add(c["player_id"])
            c["adp"] = adp.get(c["player_id"])
            ranked.append(c)
    return ranked[:limit]


# ----------------------------------------------------------- draft board


IDP_BOARD_EXCLUDE = {"DL", "LB", "DB", "IDP_FLEX"}


def draft_board(league: dict, season: str, players: dict, top_n: int = 200):
    """VORP-based board under the league's exact scoring + roster settings.

    IDP players are excluded by user decision (2026-08-24): IDP slots are
    single-starter positions with enormous replacement depth, so ranking
    defenders alongside offense only distorted the offensive board (and the
    Value column compared an all-position rank against offense-only ADP).
    Fill IDP slots with final-round picks/waivers; weekly lineup optimization
    (optimal_lineup + projection_map) still covers IDP starters unchanged.
    """
    scoring = league.get("scoring_settings", {})
    slots = [p for p in league.get("roster_positions", [])
             if p != "BN" and p not in IDP_BOARD_EXCLUDE]
    n_teams = league.get("total_rosters", 12)
    projs = api.get_season_projections(season, league_positions(league))
    superflex = "SUPER_FLEX" in slots or slots.count("QB") >= 2

    rows = []
    for p in projs:
        pl = p.get("player") or players.get(p["player_id"]) or {}
        pos = canonical_pos(pl)
        if not pos or pos in IDP_BOARD_EXCLUDE:
            continue
        pts = score_stat_line(p.get("stats") or {}, scoring)
        adp_key = "adp_2qb" if superflex else (
            "adp_ppr" if scoring.get("rec", 0) >= 1 else
            "adp_half_ppr" if scoring.get("rec", 0) >= 0.5 else "adp_std")
        adp = (p.get("stats") or {}).get(adp_key)
        if adp is not None and adp >= 999:
            adp = None  # Sleeper's undrafted sentinel — not a real market price
        if pts > 0:
            rows.append({"player_id": p["player_id"], "pos": pos, "proj": pts, "adp": adp})

    # Replacement level via league-wide greedy starter fill: every team's
    # slots get the best available player (so superflex slots naturally take
    # QBs when QBs outscore flexes); replacement = next man up per position.
    by_pos = defaultdict(list)
    for r in rows:
        by_pos[r["pos"]].append(r["proj"])
    for vals in by_pos.values():
        vals.sort(reverse=True)
    taken = defaultdict(int)  # pos -> count consumed by starters
    fill = sorted(slots * n_teams, key=lambda s: len(SLOT_ELIGIBILITY.get(s, set())))
    for slot in fill:
        elig = SLOT_ELIGIBILITY.get(slot, set()) & set(by_pos)
        best = max(
            (p for p in elig if taken[p] < len(by_pos[p])),
            key=lambda p: by_pos[p][taken[p]],
            default=None,
        )
        if best:
            taken[best] += 1
    replacement = {
        pos: vals[min(taken[pos], len(vals) - 1)] for pos, vals in by_pos.items()
    }

    for r in rows:
        r["vorp"] = round(r["proj"] - replacement.get(r["pos"], 0.0), 1)
    rows.sort(key=lambda r: -r["vorp"])
    pos_rank = defaultdict(int)
    for i, r in enumerate(rows):
        r["rank"] = i + 1
        pos_rank[r["pos"]] += 1
        r["pos_rank"] = f"{r['pos']}{pos_rank[r['pos']]}"
        # Value flag: our rank vs market ADP.
        r["value"] = round((r["adp"] - r["rank"]), 1) if r.get("adp") else None
    _assign_tiers(rows)
    return rows[:top_n], replacement


def _assign_tiers(rows):
    """Tier players within each position by natural VORP gaps.

    A tier break = a projection cliff. Draft strategy: what matters is not
    a player's rank but whether you're about to be caught on the wrong side
    of a cliff — take the last player of a tier over a higher-ranked player
    whose tier is deep.
    """
    by_pos = defaultdict(list)
    for r in rows:
        by_pos[r["pos"]].append(r)  # already sorted by vorp desc
    for pos, plist in by_pos.items():
        gaps = [plist[i]["vorp"] - plist[i + 1]["vorp"] for i in range(len(plist) - 1)]
        top_gaps = sorted(gaps[:30], reverse=True)
        # Break threshold: a gap notably larger than typical for the position,
        # floor of 12 season points so flat positions form big honest tiers.
        med = top_gaps[len(top_gaps) // 2] if top_gaps else 0
        threshold = max(12.0, med * 3.0)
        tier = 1
        for i, r in enumerate(plist):
            r["tier"] = tier
            if i < len(gaps) and gaps[i] >= threshold:
                tier += 1
