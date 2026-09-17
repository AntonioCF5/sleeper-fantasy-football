#!/usr/bin/env python3
"""Survivor pool planner — one team per week, no repeats, N lives.

Pulls the full remaining schedule with DraftKings lookahead lines from
ESPN's public scoreboard, converts each side to a win probability (de-vigged
moneyline when present, else the spread through a normal model with the NFL's
~13.5-point margin std-dev), then solves the ASSIGNMENT problem exactly
(Hungarian): the set of weekly picks with no repeated team that maximizes
the product of win probabilities. That is the survival-maximizing plan for
one life; for N lives the report also gives P(at most N-1 losses) by DP,
plus each week's best alternatives so the plan can flex when lines move.

Why an assignment and not "best favorite each week": greedy burns the elite
teams early and leaves nothing for the weeks with one lonely favorite. The
optimizer sees week 14 when it picks week 2.

State (used teams, lives) lives in data/intel/survivor.json:
  {"lives": 3, "used": {"1": "PIT"}, "pool": "..."}

Uso: python3 scripts/survivor_plan.py [--week N] [--avoid-week18]
                                      [--regress 0.03] [--max-fade 3]
  --avoid-week18  treat week 18 as unreliable (starters rest) — its lines
                  get a 0.9 haircut so the plan prefers to burn a good team
                  there only if nothing else is needed.
  --regress R     shrink each future week's edge toward 50% by R per week of
                  distance (lookahead lines are guesses that move; a -13.5 in
                  week 15 is worth less than a -13.5 this Sunday). Default 0.03.
  --max-fade N    at most N picks may ride on the SAME opponent being bad
                  (default 3). The raw optimum fades MIA/ARI 14 times in 17
                  weeks — one good Dolphins stretch would sink the whole plan.
"""
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "intel" / "survivor.json"
SD = 13.5  # NFL margin-of-victory std dev


def espn_week(week):
    url = ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
           f"?seasontype=2&week={week}&dates=2026")
    out = subprocess.run(["curl", "-s", "--max-time", "30", url], capture_output=True).stdout
    return json.loads(out).get("events", [])


def _devig(ml_a, ml_b):
    def imp(ml):
        ml = int(ml)
        return 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)
    a, b = imp(ml_a), imp(ml_b)
    return a / (a + b)


def _phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def games_with_probs(week):
    """[(team, opp, p_win, home?, spread_str)] for every side of every game."""
    rows = []
    for ev in espn_week(week):
        c = ev["competitions"][0]
        if c["status"]["type"]["name"] != "STATUS_SCHEDULED":
            continue
        home = next(x for x in c["competitors"] if x["homeAway"] == "home")["team"]["abbreviation"]
        away = next(x for x in c["competitors"] if x["homeAway"] == "away")["team"]["abbreviation"]
        odds = (c.get("odds") or [None])[0]
        if not odds:
            continue
        ml = odds.get("moneyline") or {}
        mh = ((ml.get("home") or {}).get("close") or {}).get("odds")
        ma = ((ml.get("away") or {}).get("close") or {}).get("odds")
        spread = odds.get("spread")
        if mh and ma:
            p_home = _devig(mh, ma)
        elif spread is not None:
            p_home = _phi(-float(spread) / SD)
        else:
            continue
        det = odds.get("details", "")
        rows.append((home, away, p_home, True, det))
        rows.append((away, home, 1 - p_home, False, det))
    return rows


def hungarian(cost):
    """Min-cost assignment for a rectangular cost matrix (rows ≤ cols).
    Returns list of column index per row. O(n^2 m)."""
    n, m = len(cost), len(cost[0])
    INF = float("inf")
    u = [0] * (n + 1); v = [0] * (m + 1); p = [0] * (m + 1); way = [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i; j0 = 0
        minv = [INF] * (m + 1); used = [False] * (m + 1)
        while True:
            used[j0] = True; i0 = p[j0]; delta = INF; j1 = 0
            for j in range(1, m + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur; way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]; j1 = j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta; v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]; p[j0] = p[j1]; j0 = j1
            if j0 == 0:
                break
    ans = [0] * n
    for j in range(1, m + 1):
        if p[j]:
            ans[p[j] - 1] = j - 1
    return ans


def p_survive(probs, lives):
    """P(at most lives-1 losses) over independent weekly picks."""
    dp = [1.0] + [0.0] * (lives - 1)  # dp[k] = P(exactly k losses so far)
    for p in probs:
        new = [0.0] * lives
        for k in range(lives):
            new[k] += dp[k] * p
            if k + 1 < lives:
                new[k + 1] += dp[k] * (1 - p)
        dp = new
    return sum(dp)


def main():
    st = json.loads(STATE.read_text()) if STATE.exists() else {"lives": 3, "used": {}}
    lives = st.get("lives", 3)
    used = {int(k): v for k, v in st.get("used", {}).items()}
    start = int(sys.argv[sys.argv.index("--week") + 1]) if "--week" in sys.argv else max(used, default=0) + 1
    avoid18 = "--avoid-week18" in sys.argv
    regress = float(sys.argv[sys.argv.index("--regress") + 1]) if "--regress" in sys.argv else 0.03
    max_fade = int(sys.argv[sys.argv.index("--max-fade") + 1]) if "--max-fade" in sys.argv else 3
    weeks = list(range(start, 19))
    banned = set(used.values())

    board = {}   # week -> {team: (p, opp, home, det)}  (p = adjusted, used for the optimizer)
    raw = {}     # week -> {team: p_raw}                (market number, for display)
    for wk in weeks:
        rows = games_with_probs(wk)
        board[wk] = {}; raw[wk] = {}
        for team, opp, p, home, det in rows:
            if team in banned:
                continue
            raw[wk][team] = p
            p = 0.5 + (p - 0.5) * max(0.4, 1 - regress * (wk - start))
            if wk == 18 and avoid18:
                p = 0.5 + (p - 0.5) * 0.6
            board[wk][team] = (p, opp, home, det)
    teams = sorted({t for wk in weeks for t in board[wk]})

    def solve(penalty):
        # cost = -log p ; missing (bye) = big cost ; penalty[(wk, team)] added for over-faded opponents
        cost = [[(-math.log(board[wk][t][0]) + penalty.get((wk, t), 0.0)) if t in board[wk] else 50.0
                 for t in teams] for wk in weeks]
        assign = hungarian(cost)
        return {wk: teams[j] for wk, j in zip(weeks, assign)}

    # Enforce --max-fade iteratively: when an opponent is faded more than N
    # times, make its WEAKEST-edge fades progressively more expensive and
    # re-solve until the cap holds (converges in a few rounds).
    penalty = {}
    for _ in range(40):
        plan = solve(penalty)
        fades = {}
        for wk, t in plan.items():
            if t in board[wk]:
                fades.setdefault(board[wk][t][1], []).append((board[wk][t][0], wk, t))
        over = {opp: v for opp, v in fades.items() if len(v) > max_fade}
        if not over:
            break
        for opp, v in over.items():
            for p_, wk, t in sorted(v)[:len(v) - max_fade]:
                penalty[(wk, t)] = penalty.get((wk, t), 0.0) + 0.15

    print(f"SURVIVOR — {lives} vidas, usados: {', '.join(f'S{k}:{v}' for k, v in sorted(used.items())) or 'ninguno'}")
    print(f"Plan óptimo semanas {weeks[0]}-{weeks[-1]} (líneas DraftKings via ESPN, hoy)\n")
    print(f"regresión {regress}/sem · máx {max_fade} fades por rival · "
          f"{'semana 18 descontada' if avoid18 else 'semana 18 a valor de mercado'}\n")
    print(f"{'Sem':<4}{'Pick':<5}{'vs':<9}{'mercado':>8}{'ajust.':>8}  {'línea':<12} alternativas libres (mercado)")
    probs = []
    for wk in weeks:
        t = plan[wk]
        if t not in board[wk]:
            print(f"{wk:<4}{'—':<5}  (sin opción)"); continue
        p, opp, home, det = board[wk][t]
        probs.append(raw[wk][t])
        others = sorted(((raw[wk][k], k, v[1], v[2]) for k, v in board[wk].items() if k != t and k not in plan.values()),
                        reverse=True)[:3]
        alt = ", ".join(f"{k} {'vs' if h else '@'} {o} {q:.0%}" for q, k, o, h in others)
        print(f"{wk:<4}{t:<5}{('vs ' if home else '@ ') + opp:<9}{raw[wk][t]:>7.0%}{p:>8.0%}  {det:<12} {alt}")
    fades = {}
    for wk, t in plan.items():
        if t in board[wk]:
            fades[board[wk][t][1]] = fades.get(board[wk][t][1], 0) + 1
    print("\nRivales 'fadeados': " + ", ".join(f"{k}×{v}" for k, v in sorted(fades.items(), key=lambda kv: -kv[1]) if v > 1))
    print(f"P(ganar TODAS, a mercado) = {math.prod(probs):.1%}   |   P(sobrevivir con {lives} vidas) = {p_survive(probs, lives):.1%}")
    # semanas apretadas: mejor opción libre < 65%
    tight = [wk for wk in weeks if plan[wk] in board[wk] and board[wk][plan[wk]][0] < 0.65]
    if tight:
        print(f"Semanas apretadas (pick < 65%): {', '.join(map(str, tight))} — ahí se gastan vidas, no favoritos.")
    st["plan_generated"] = {str(wk): plan[wk] for wk in weeks}
    STATE.write_text(json.dumps(st, indent=1))


if __name__ == "__main__":
    main()
