#!/usr/bin/env python3
"""Fantasy command center — live draft assistant + full league rankings.

Usage: python3 scripts/draft_dashboard.py [league_id] [port]
  league_id defaults to the first league in config.json.
  port defaults to 8787.

Two views, one server, switchable without restarting:
  - Draft Room: live pick-by-pick recommendations (scripts/live_draft.py engine)
  - Rankings:   the full board for the active league — searchable, sortable,
                filterable, and cross-referenced against who already has each
                player (drafted this draft, or rostered — works in-season too)

Switch leagues from the header dropdown; no restart needed. State (league,
view) persists in the URL and localStorage. This is meant to stay open
across the whole season, not just draft day.
"""

import json
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import live_draft  # noqa: E402
from sleeper import analysis, api  # noqa: E402
from sleeper.reports import _owner_names, get_league_corrected  # noqa: E402

REFRESH_SECONDS = 5
CTX_TTL = 3600          # rebuild a league's context at most hourly (or on /api/refresh)
BOARD_LIMIT = 400        # rows sent to the rankings table

_lock = threading.Lock()
_ctx_cache = {}           # league_id -> (ctx_tuple, loaded_at)
_state = {}                # league_id -> {"data", "stamp", "error", "picks_seen"}
_active = {"league_id": None}
_config = json.loads((ROOT / "config.json").read_text())


def _norm_name(name):
    """Match curated rulings to Sleeper names robustly: case/diacritics/
    punctuation-insensitive so 'D.J. Moore' == 'DJ Moore'."""
    import unicodedata
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _leagues():
    return _config.get("leagues", [])


def get_ctx(league_id, force=False):
    with _lock:
        cached = _ctx_cache.get(league_id)
    if cached and not force and time.time() - cached[1] < CTX_TTL:
        return cached[0]
    ctx = live_draft.load_context(league_id)
    with _lock:
        _ctx_cache[league_id] = (ctx, time.time())
    return ctx


_moves_cache = {}          # league_id -> (payload, loaded_at)
MOVES_TTL = 600            # waiver/trade data refreshes at most every 10 min


def moves_payload(league_id, force=False):
    """Waivers + drops + trades for one league (the Moves tab / Trade center).

    Standing offers come from data/intel/trade_offers.json (curated — the
    same file the daily newsletter maintains). Everything else is computed:
    recent drops still unclaimed, top free agents vs the weakest ACTIVE
    bench spots (taxi/IR excluded — they consume no bench space), FAAB
    budget state, and algorithmic trade-target ideas.
    """
    with _lock:
        cached = _moves_cache.get(league_id)
    if cached and not force and time.time() - cached[1] < MOVES_TTL:
        return cached[0]

    league = get_league_corrected(league_id)
    players = api.get_players()
    my_id = _config.get("user_id")
    season = str(_config.get("season") or api.get_state()["league_season"])
    scoring = league.get("scoring_settings", {})
    sp = analysis.season_projection_map(season, scoring, analysis.league_positions(league))
    rosters = api.get_rosters(league_id) or []
    owners = _owner_names(league_id)
    mine = next((r for r in rosters if r.get("owner_id") == my_id
                 or my_id in (r.get("co_owners") or [])), None)
    dynasty = (league.get("settings") or {}).get("type") == 2
    in_season = league.get("status") == "in_season"

    def pdict(pid):
        p = players.get(pid) or {}
        return {"player_id": pid, "name": p.get("full_name") or pid,
                "pos": analysis.canonical_pos(p) or "?", "team": p.get("team") or "FA",
                "age": p.get("age"), "injury": p.get("injury_status") or "",
                "proj": round(sp.get(pid, 0))}

    out = {"league": league.get("name"), "in_season": in_season, "dynasty": dynasty,
           "drops": [], "waiver_targets": [], "weakest_bench": [], "faab": None,
           "trade_offers": [], "trade_targets": []}

    # Standing offers (curated file)
    tf = ROOT / "data" / "intel" / "trade_offers.json"
    if tf.exists():
        data = json.loads(tf.read_text())
        out["trade_offers"] = [o for o in data.get("offers", [])
                               if o.get("league_id") == league_id]

    if in_season and mine:
        # FAAB state
        s = league.get("settings") or {}
        if s.get("waiver_type") == 2:
            budget = s.get("waiver_budget", 0)
            used = (mine.get("settings") or {}).get("waiver_budget_used", 0)
            spent = [((r.get("settings") or {}).get("waiver_budget_used", 0))
                     for r in rosters if r is not mine]
            out["faab"] = {"budget": budget, "used": used, "left": budget - used,
                           "rival_max_spent": max(spent, default=0)}
        # Weakest ACTIVE bench (dynasty ordering happens in the UI copy; here
        # we exclude taxi/IR — they consume no bench spot)
        starters = set(mine.get("starters") or [])
        ir_taxi = set((mine.get("reserve") or []) + (mine.get("taxi") or []))
        bench = [p for p in (mine.get("players") or [])
                 if p not in starters and p not in ir_taxi]
        out["weakest_bench"] = sorted((pdict(p) for p in bench),
                                      key=lambda x: x["proj"])[:5]
        # Bench floor = weakest DROPPABLE bench spot. In dynasty the
        # dynasty-value rule protects young stashes, so the floor comes from
        # age-26+ players only (falls back to overall floor if none) —
        # otherwise a protected 24yo handcuff makes everything look like an
        # upgrade and every card screams CLAIM.
        bench_all = sorted((pdict(pl) for pl in bench), key=lambda x: x["proj"])
        # Unknown age = fringe veteran, not a protected young stash.
        droppable = ([b for b in bench_all if (b.get("age") if b.get("age") is not None else 30) >= 26]
                     if dynasty else bench_all)
        bench_floor = (droppable[0]["proj"] if droppable
                       else bench_all[0]["proj"] if bench_all else 0)
        # Starting-slot exposure per position (dedicated + flex eligibility),
        # and the user's Nth-best active player there — a claim must upgrade a
        # slot the roster can actually use, not just beat the bench floor.
        slots_l = [s for s in league.get("roster_positions", []) if s != "BN"]
        sf = "SUPER_FLEX" in slots_l or slots_l.count("QB") >= 2
        FLEX_ELIG = {"FLEX": ("RB", "WR", "TE"), "WRRB_FLEX": ("RB", "WR"),
                     "REC_FLEX": ("WR", "TE"), "SUPER_FLEX": ("QB", "RB", "WR", "TE")}
        exposure = {}
        for pos in ("QB", "RB", "WR", "TE", "K", "DEF"):
            n = slots_l.count(pos)
            n += sum(1 for s in slots_l if pos in FLEX_ELIG.get(s, ()))
            exposure[pos] = max(n, 1) if pos in ("QB", "RB", "WR", "TE") else slots_l.count(pos)
        active = [pl for pl in (mine.get("players") or []) if pl not in ir_taxi]
        by_pos_proj = {}
        for pl in active:
            pos = analysis.canonical_pos(players.get(pl) or {})
            by_pos_proj.setdefault(pos, []).append(sp.get(pl, 0))
        for v in by_pos_proj.values():
            v.sort(reverse=True)

        def nth_best(pos):
            n = max(exposure.get(pos, 1), 1)  # 0-exposure K/DEF: compare vs best
            vals = by_pos_proj.get(pos, [])
            return round(vals[n - 1]) if len(vals) >= n else 0

        n_teams = league.get("total_rosters", 12)

        def verdict(proj, trend, pos=None, age=None):
            """Claim = a startable upgrade: beats the user's Nth-best active
            player at the position (N = starting exposure incl. flex) AND
            the droppable bench floor — or breakout-level trending
            (projections lag news; the user's speed edge). Caps, per the
            methodology: DEF/K never auto-claim (streaming commodity in
            ≤12-team leagues, set-and-forget in 18s); dynasty 29+ veterans
            without breaking news cap at watch; a position where the
            candidate doesn't beat the user's startable depth caps at watch."""
            v, why = None, ""
            slot_bar = nth_best(pos) if pos else 0
            startable_up = proj > slot_bar + 10
            if (proj >= bench_floor + 25 and startable_up) or trend >= 30000:
                v = "claim"
                why = (f"upgrades a startable slot: {proj} vs your #{exposure.get(pos,1)} {pos} ({slot_bar})"
                       if proj >= bench_floor + 25 and startable_up else
                       f"breaking: {trend:,} adds/24h — projections lag news")
            elif proj >= bench_floor + 5 or trend >= 8000:
                v, why = "watch", (f"doesn't beat your startable {pos} depth ({proj} vs {slot_bar})"
                                   if not startable_up and proj >= bench_floor + 5
                                   else f"marginal vs droppable-bench floor {bench_floor}")
            if v == "claim" and trend >= 30000 and proj < 15:
                v, why = "watch", f"trending hard ({trend:,}/24h) but projects ~nothing — investigate the news before bidding"
            if v == "claim" and pos in ("DEF", "K"):
                v = "watch"
                why = ("streaming commodity — matchup call, not a roster upgrade"
                       if n_teams <= 12 else
                       "set-and-forget league size — swap only if clearly better than yours")
            if v == "claim" and pos and not startable_up and trend < 30000:
                v, why = "watch", f"roster already deep at {pos} ({proj} vs your #{exposure.get(pos,1)}: {slot_bar})"
            if v == "claim" and dynasty and (age or 0) >= 29 and trend < 15000:
                v, why = "watch", "veteran points in a dynasty league — your call, not a default claim"
            return v, why
        # Drop it like it's hot
        try:
            drops = analysis.recent_drops(league_id, players, sp, hours=96)
            out["drops"] = []
            for d in drops[:8]:
                row = {**pdict(d["player_id"]), "dropped_by": d["dropped_by"],
                       "hours_ago": d["hours_ago"], "trend": d["trend_count"]}
                row["verdict"], row["verdict_why"] = verdict(
                    row["proj"], row["trend"], row["pos"], row.get("age"))
                out["drops"].append(row)

        except Exception:
            pass
        # Top free agents (proj + trending), excluding rostered
        rostered = set()
        for r in rosters:
            rostered.update(r.get("players") or [])
        trending = {t["player_id"]: t["count"]
                    for t in api.get_trending("add", 24, 300) or []}
        fas = []
        for pid, v in sp.items():
            if pid in rostered or pid not in players:
                continue
            pl = players[pid]
            if not pl.get("team") or analysis.canonical_pos(pl) in ("K", "DEF"):
                continue
            tr = trending.get(pid, 0)
            if v >= 60 or tr >= 8000:
                fas.append((v + min(tr, 50000) / 500, pid, tr))
        fas.sort(reverse=True)
        out["waiver_targets"] = []
        for _, pid, tr in fas[:8]:
            row = {**pdict(pid), "trend": tr}
            row["verdict"], row["verdict_why"] = verdict(
                row["proj"], tr, row["pos"], row.get("age"))
            out["waiver_targets"].append(row)

        # Curated overlay: newsletter rulings (data/intel/waiver_claims.json)
        # ALWAYS win over auto signals for the players they cover — the
        # dashboard and the newsletter must never disagree.
        wc = ROOT / "data" / "intel" / "waiver_claims.json"
        rulings = {}
        if wc.exists():
            for c in json.loads(wc.read_text()).get("claims", []):
                if c.get("league_id") == league_id:
                    rulings[_norm_name(c["player"])] = c
        covered = set()
        for lst in (out["drops"], out["waiver_targets"]):
            for row in lst:
                c = rulings.get(_norm_name(row["name"]))
                if c:
                    covered.add(_norm_name(row["name"]))
                    row["verdict"] = c["verdict"]
                    row["verdict_why"] = c["why"]
                    row["source"] = "newsletter"
                    if c.get("bid") is not None:
                        row["bid"] = c["bid"]
                    if c.get("drop"):
                        row["drop_for"] = c["drop"]
        # A ruling ALWAYS renders, even when the auto signals didn't surface
        # the player — inject a row for it so the tab can never contradict
        # the newsletter by omission.
        name_to_pid = {_norm_name(players[p].get("full_name") or ""): p
                       for p in rostered | set(sp) if p in players}
        for key, c in rulings.items():
            if key in covered:
                continue
            pid = name_to_pid.get(key)
            row = {**(pdict(pid) if pid else
                      {"name": c["player"], "pos": "?", "team": "?", "proj": 0}),
                   "trend": 0, "verdict": c["verdict"], "verdict_why": c["why"],
                   "source": "newsletter", "injected": True}
            if c.get("bid") is not None:
                row["bid"] = c["bid"]
            if c.get("drop"):
                row["drop_for"] = c["drop"]
            out["waiver_targets"].append(row)
        order = {"claim": 0, "optional": 1, "watch": 2, "skip": 3}
        for lst in (out["drops"], out["waiver_targets"]):
            lst.sort(key=lambda r: (order.get(r["verdict"], 2),
                                    0 if r.get("source") == "newsletter" else 1,
                                    -(r["proj"] + min(r["trend"], 50000) / 500)))
        # Algorithmic trade ideas (complementary needs)
        try:
            ideas = analysis.trade_suggestions(
                league_id, mine["roster_id"], players, sp,
                league.get("roster_positions", []))
            out["trade_targets"] = [
                {"partner": owners.get(next((r.get("owner_id") for r in rosters
                                             if r["roster_id"] == i["partner_roster_id"]), None), "?"),
                 "note": i["note"]} for i in (ideas or [])[:5]]
        except Exception:
            pass

    with _lock:
        _moves_cache[league_id] = (out, time.time())
    return out


_rosters_cache = {}
ROSTERS_TTL = 600


def rosters_payload(league_id, force=False):
    """Every team in a league: owner, record, starters/bench/IR/taxi with
    projections — powers the rival-roster viewer (owner names anywhere in
    the UI open this)."""
    with _lock:
        cached = _rosters_cache.get(league_id)
    if cached and not force and time.time() - cached[1] < ROSTERS_TTL:
        return cached[0]
    league = get_league_corrected(league_id)
    players = api.get_players()
    my_id = _config.get("user_id")
    season = str(_config.get("season") or api.get_state()["league_season"])
    sp = analysis.season_projection_map(
        season, league.get("scoring_settings", {}), analysis.league_positions(league))
    rosters = api.get_rosters(league_id) or []
    owners = _owner_names(league_id)

    def pdict(pid):
        pl = players.get(pid) or {}
        return {"player_id": pid, "name": pl.get("full_name") or pid,
                "pos": analysis.canonical_pos(pl) or "?", "team": pl.get("team") or "FA",
                "age": pl.get("age"), "injury": pl.get("injury_status") or "",
                "proj": round(sp.get(pid, 0))}

    teams = []
    for r in rosters:
        own = r.get("owner_id")
        mine = own == my_id or my_id in (r.get("co_owners") or [])
        name = owners.get(own, "?")
        st = r.get("settings") or {}
        starters = [p for p in (r.get("starters") or []) if p and p != "0"]
        reserve = r.get("reserve") or []
        taxi = r.get("taxi") or []
        bench = [p for p in (r.get("players") or [])
                 if p not in set(starters) and p not in set(reserve) and p not in set(taxi)]
        skey = lambda x: -x["proj"]
        teams.append({
            "roster_id": r["roster_id"], "owner": name, "mine": mine,
            "record": f"{st.get('wins', 0)}-{st.get('losses', 0)}"
                      + (f"-{st.get('ties')}" if st.get("ties") else ""),
            "fpts": st.get("fpts", 0),
            "starters": [pdict(p) for p in starters],
            "starters_proj": round(sum(sp.get(p, 0) for p in starters)),
            "bench": sorted((pdict(p) for p in bench), key=skey),
            "reserve": [pdict(p) for p in reserve],
            "taxi": [pdict(p) for p in taxi],
        })
    teams.sort(key=lambda x: (-x["starters_proj"]))
    out = {"league": league.get("name"), "teams": teams}
    with _lock:
        _rosters_cache[league_id] = (out, time.time())
    return out


def recompute(league_id, ctx=None):
    ctx = ctx or get_ctx(league_id)
    try:
        data = live_draft.compute_advice(league_id, ctx=ctx)
        with _lock:
            _state[league_id] = {"data": data, "stamp": time.strftime("%H:%M:%S"), "error": ""}
    except Exception as e:
        with _lock:
            _state.setdefault(league_id, {})["error"] = str(e)


def _updater():
    while True:
        lid = _active["league_id"]
        if lid:
            try:
                ctx = get_ctx(lid)
                draft_id = ctx[2]["draft_id"]
                picks = api.get_draft_picks(draft_id, ttl=0) or []
                st = _state.get(lid)
                if st is None or st.get("picks_seen") != len(picks):
                    recompute(lid, ctx)
                    # Only mark the pick count consumed when the recompute
                    # actually succeeded — otherwise retry next cycle instead
                    # of sitting on an error for a whole pick.
                    if not _state.get(lid, {}).get("error"):
                        _state[lid]["picks_seen"] = len(picks)
            except Exception as e:
                with _lock:
                    _state.setdefault(lid, {})["error"] = str(e)
        time.sleep(REFRESH_SECONDS)


def build_board_payload(league_id, ctx):
    """Full ranked board + who currently has each player (draft picks pre-
    completion, roster ownership once the draft is done — this is what makes
    the Rankings view double as a free-agent/waiver board in season)."""
    config, league, draft, players, board, adp, winners, style, risk = ctx
    elite_ids = live_draft.compute_elite_ids(board, league)
    owners = _owner_names(league_id)
    taken = {}
    if draft.get("status") != "complete":
        slot_to_uid = {v: k for k, v in (draft.get("draft_order") or {}).items()}
        for p in api.get_draft_picks(draft["draft_id"], ttl=0) or []:
            pid = p["metadata"]["player_id"]
            uid = p.get("picked_by") or slot_to_uid.get(p.get("draft_slot"))
            taken[pid] = {"status": "drafted", "owner": owners.get(uid, "Keeper"),
                          "pick_no": p["pick_no"]}
    else:
        for r in api.get_rosters(league_id):
            oname = owners.get(r.get("owner_id"), "Unknown")
            for pid in r.get("players") or []:
                taken[pid] = {"status": "rostered", "owner": oname, "pick_no": None}

    out = []
    for r in board[:BOARD_LIMIT]:
        p = players.get(r["player_id"]) or {}
        info = taken.get(r["player_id"])
        out.append({
            "player_id": r["player_id"],
            "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or r["player_id"],
            "team": p.get("team") or "FA",
            "pos": r["pos"], "pos_rank": r["pos_rank"], "tier": r["tier"],
            "rank": r["rank"], "proj": r["proj"], "vorp": r["vorp"],
            "adp": r.get("adp"), "value": r.get("value"), "flags": r.get("flags", ""),
            "injury": p.get("injury_status") or "",
            "style": style.get(r["player_id"]), "elite": r["player_id"] in elite_ids,
            "risk": risk.get(r["player_id"]), "expert": r.get("expert"),
            "tgt_share": r.get("tgt_share"), "rush_share": r.get("rush_share"),
            "snap_share": r.get("snap_share"),
            "status": info["status"] if info else "available",
            "owner": info["owner"] if info else None,
            "pick_no": info["pick_no"] if info else None,
        })
    return out


def league_list_payload():
    out = []
    for lg in _leagues():
        try:
            live = api.get_league(lg["league_id"])
            status, teams, name = live.get("status", lg.get("status")), live.get(
                "total_rosters", lg.get("teams")), live.get("name", lg["name"])
        except Exception:
            status, teams, name = lg.get("status"), lg.get("teams"), lg["name"]
        out.append({"league_id": lg["league_id"], "name": name, "teams": teams, "status": status})
    return out


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Draft Assistant</title>
<style>
:root{
  --bg:#0b0e13; --surface:#131820; --surface2:#1a212c; --surface3:#212a37; --border:#232c3a;
  --ink:#e8edf4; --ink2:#9aa7b8; --ink3:#5f6c7d;
  --accent:#5b9cf5; --accent-soft:rgba(91,156,245,.14);
  --gone:#f2545b;  --gone-soft:rgba(242,84,91,.13);
  --tier:#e5a13c;  --tier-soft:rgba(229,161,60,.13);
  --need:#3fb7a2;  --need-soft:rgba(63,183,162,.13);
  --stash:#b07df0; --stash-soft:rgba(176,125,240,.13);
}
*{box-sizing:border-box;margin:0}
html,body{height:100%}
body{background:var(--bg);color:var(--ink);
  font:14.5px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif;
  height:100dvh;display:flex;flex-direction:column;overflow:hidden}
.num{font-variant-numeric:tabular-nums}
header{position:sticky;top:0;z-index:5;background:rgba(11,14,19,.94);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--border)}
.headtop{padding:11px 20px 9px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
header h1{font-size:16px;font-weight:650;letter-spacing:.2px;white-space:nowrap}
.pill{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--border);
  background:var(--surface);border-radius:999px;padding:4px 12px;font-size:12.5px;
  color:var(--ink2);white-space:nowrap}
.pill b{color:var(--ink);font-weight:600}
.dot{width:7px;height:7px;border-radius:50%;background:var(--need);flex:none;
  animation:pulse 2s infinite}
@keyframes pulse{50%{opacity:.35}}
.onclock{background:var(--accent);color:#fff;border-color:transparent;
  font-weight:700;animation:pulseStrong 1s infinite}
@keyframes pulseStrong{0%,100%{box-shadow:0 0 0 0 rgba(91,156,245,.65)}50%{box-shadow:0 0 0 8px rgba(91,156,245,0)}}
body.onclock{box-shadow:inset 0 0 0 3px var(--accent)}
select#leagueSel{background:var(--surface2);border:1px solid var(--border);color:var(--ink);
  border-radius:9px;padding:6px 10px;font-size:13px;font-weight:600;max-width:260px}
.statustag{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;
  padding:1px 6px;border-radius:5px;margin-left:6px}
.st-pre_draft{background:var(--tier-soft);color:var(--tier)}
.st-drafting{background:var(--accent-soft);color:var(--accent)}
.st-in_season,.st-complete{background:var(--need-soft);color:var(--need)}
.iconbtn{background:var(--surface2);border:1px solid var(--border);color:var(--ink2);
  border-radius:999px;padding:5px 13px;font-size:12.5px;font-weight:650;cursor:pointer;
  display:flex;align-items:center;gap:6px}
.iconbtn:hover{color:var(--ink);border-color:var(--accent)}
.spacer{margin-left:auto}
.tabs{display:flex;gap:2px;padding:0 20px}
.tab{padding:9px 15px 10px;font-size:13.5px;font-weight:650;color:var(--ink3);
  cursor:pointer;border-bottom:2px solid transparent;user-select:none}
.tab.active{color:var(--ink);border-bottom-color:var(--accent)}
.tab:hover{color:var(--ink)}
.progress{height:2px;background:var(--surface2)}
.progress i{display:block;height:100%;background:var(--accent);transition:width .3s}
main{flex:1;min-height:0;width:100%;max-width:1560px;margin:0 auto;
  padding:14px 20px 6px}
#view-draft{height:100%;min-height:0}
#view-rankings,#view-team,#view-moves,#view-rivals{height:100%;min-height:0;overflow-y:auto;scrollbar-width:thin}
#view-rivals{max-width:760px;margin:0 auto;width:100%;padding-bottom:24px}
.rival-controls{padding:10px 0 4px}
#rivalSel{background:var(--surface2);border:1px solid var(--border);color:var(--ink);
  border-radius:8px;padding:8px 12px;font-size:14px;width:100%;max-width:340px}
#view-moves{max-width:760px;margin:0 auto;width:100%;padding-bottom:24px}
#view-team{max-width:760px;margin:0 auto;width:100%}
.teampill{cursor:pointer;font-weight:650;color:var(--ink)!important}
.teampill:hover{border-color:var(--accent)}
@media(max-width:820px){.teampill{display:none}}
.teamhead{display:flex;gap:10px;align-items:center;flex-wrap:wrap;
  background:var(--surface);border:1px solid var(--border);border-radius:14px;
  padding:14px 18px;margin-bottom:16px}
.teamhead-stat{display:flex;flex-direction:column;align-items:center;min-width:64px;
  cursor:pointer;padding:6px 10px;border-radius:10px;border:1px solid transparent;
  transition:background .12s,border-color .12s}
.teamhead-stat:hover{background:var(--surface2)}
.teamhead-stat.active{background:var(--accent-soft);border-color:var(--accent)}
.teamhead-stat.active b,.teamhead-stat.active span{color:var(--accent)}
.teamhead-stat b{font-size:22px;font-weight:700}
.teamhead-stat span{font-size:11px;color:var(--ink3);text-transform:uppercase;
  letter-spacing:.4px}
.teamhead-lean{margin-left:auto;font-size:12.5px;font-weight:650;color:var(--accent);
  background:var(--accent-soft);padding:5px 12px;border-radius:999px}
.teamfilter-tag{font-size:12.5px;color:var(--ink2);margin:-6px 0 14px 2px}
.teamfilter-tag b{color:var(--accent)}
.teamfilter-clear{color:var(--ink3);cursor:pointer;text-decoration:underline;
  text-underline-offset:2px}
.teamfilter-clear:hover{color:var(--ink)}
.teamgroup{margin-bottom:18px}
.teamgroup h3{font-size:11.5px;font-weight:700;color:var(--ink3);text-transform:uppercase;
  letter-spacing:.7px;margin-bottom:8px;display:flex;align-items:center;gap:8px}
.teamgroup h3 .cnt{background:var(--surface2);border-radius:999px;padding:1px 8px;
  font-size:10.5px}
.teamplayer{display:flex;align-items:center;gap:10px;background:var(--surface);
  border:1px solid var(--border);border-radius:11px;padding:10px 14px;margin-bottom:6px}
.teamplayer .tp-name{font-weight:650;font-size:14px;display:flex;align-items:center;gap:7px}
.tp-vorp-wrap{margin-left:auto;display:flex;flex-direction:column;align-items:flex-end;
  gap:1px}
.teamplayer .tp-vorp{font-weight:700;font-size:15px}
.tp-vorp-label{font-size:9px;color:var(--ink3);text-transform:uppercase;letter-spacing:.4px}
@media(max-width:640px){#view-team{padding:0}
  .teamhead{padding:12px 14px;gap:8px}
  .teamhead-stat{min-width:52px}
  .teamhead-stat b{font-size:18px}}
/* Desktop: app-shell — three independently scrolling columns, zero page scroll.
   Col A = decide now, Col B = plan ahead, Col C = memory (queue/roster/room). */
.cols{display:grid;grid-template-columns:1.2fr 1fr .95fr;gap:16px;height:100%;min-height:0}
.col{overflow-y:auto;min-width:0;min-height:0;padding-right:4px;scrollbar-width:thin;
  scrollbar-color:var(--surface3) transparent}
.col::-webkit-scrollbar,#view-rankings::-webkit-scrollbar{width:8px}
.col::-webkit-scrollbar-thumb,#view-rankings::-webkit-scrollbar-thumb{
  background:var(--surface3);border-radius:4px}
.col::-webkit-scrollbar-track,#view-rankings::-webkit-scrollbar-track{background:transparent}
.col section h2{position:sticky;top:0;z-index:2;background:var(--bg);
  padding:4px 0 6px;margin:0 0 6px}
/* Tablet: two columns; memory column spans full width below, its two
   halves side by side. The workspace scrolls as one unit here. */
@media(max-width:1120px) and (min-width:821px){
  .cols{grid-template-columns:1.1fr 1fr;overflow-y:auto}
  .col{overflow:visible;min-height:auto}
  #colC{grid-column:1/-1;display:grid;grid-template-columns:1fr 1fr;
    gap:0 16px;align-items:start}
}
/* Mobile segmented control (hidden on desktop) */
.mseg{display:none;gap:4px;padding:8px 14px 10px;overflow-x:auto}
.mseg button{flex:1;background:var(--surface);border:1px solid var(--border);
  color:var(--ink2);border-radius:9px;padding:7px 10px;font-size:12.5px;
  font-weight:650;cursor:pointer;white-space:nowrap}
.mseg button.on{background:var(--accent-soft);border-color:var(--accent);color:var(--ink)}
@media(max-width:820px){
  /* compact header: the league dropdown already carries the name */
  header h1{display:none}
  .headtop{gap:6px;padding:8px 12px 4px}
  .pill{padding:3px 9px;font-size:11.5px}
  .iconbtn{padding:4px 10px;font-size:11.5px}
  .tabs{padding:0 12px}
  .tab{padding:7px 12px 8px;font-size:13px}
  .mseg{padding:6px 12px 8px}
  body[data-view="draft"] .mseg{display:flex}
  .cols{display:block;overflow-y:auto}
  .col{overflow:visible;padding-right:0}
  #colA,#colB,#colC{display:none}
  body.m-picks #colA{display:block}
  body.m-plan #colB{display:block}
  body.m-queue #colC{display:block}
}
section h2{font-size:12px;font-weight:650;color:var(--ink3);
  text-transform:uppercase;letter-spacing:.9px;margin:2px 0 10px}
/* Collapsible sections */
.sec h2{cursor:pointer;user-select:none;display:flex;align-items:center;gap:7px;
  padding:4px 2px;border-radius:8px}
.sec h2:hover{color:var(--ink);background:var(--surface2)}
.chev{display:inline-block;font-size:9px;color:var(--ink3);transition:transform .15s ease;
  flex:none}
.sec.collapsed .chev{transform:rotate(-90deg)}
.sec .sec-body{overflow:hidden;max-height:4000px;transition:max-height .2s ease,opacity .15s ease;
  opacity:1}
.sec.collapsed .sec-body{max-height:0;opacity:0;pointer-events:none}
.secsum{text-transform:none;letter-spacing:0;font-size:11px;font-weight:600;
  color:var(--accent);margin-left:auto;padding-right:4px}
.sec:not(.collapsed) .secsum{display:none}
.card{background:var(--surface);border:1px solid var(--border);
  border-radius:13px;padding:12px 14px;margin-bottom:8px}
.banner{background:var(--surface);border:1px solid var(--border);border-radius:14px;
  padding:16px;font-size:13.5px;color:var(--ink2);margin-bottom:14px}
.banner.err{border-color:var(--gone);color:var(--gone)}
.rec{display:grid;grid-template-columns:34px minmax(0,1fr) auto;gap:4px 12px;
  align-items:center}
.rec.primary{border-color:var(--accent);
  box-shadow:0 0 0 1px var(--accent), 0 6px 24px -12px rgba(91,156,245,.5)}
.rec .rankno{font-size:19px;font-weight:700;color:var(--ink3);text-align:center}
.rec.primary .rankno{color:var(--accent)}
.pname{font-size:16px;font-weight:650;display:flex;align-items:center;gap:8px;
  flex-wrap:wrap}
.meta{font-size:12.5px;color:var(--ink2)}
.badge{font-size:10.5px;font-weight:700;padding:2px 7px;border-radius:6px;
  background:var(--surface2);border:1px solid var(--border);color:var(--ink2)}
.inj{color:var(--gone);font-size:11.5px;font-weight:600}
.stats{text-align:right}
.stats .v{font-size:16px;font-weight:650}
.stats .a{font-size:11.5px;color:var(--ink3)}
.vbar{grid-column:2/4;height:4px;border-radius:2px;background:var(--surface2);
  overflow:hidden;margin-top:2px}
.vbar i{display:block;height:100%;background:var(--accent);border-radius:2px}
.chips{grid-column:2/4;display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.chip{font-size:11.5px;font-weight:600;padding:3px 9px;border-radius:999px}
.chip.gone{color:var(--gone);background:var(--gone-soft)}
.chip.tier{color:var(--tier);background:var(--tier-soft)}
.chip.need{color:var(--need);background:var(--need-soft)}
.chip.stash{color:var(--stash);background:var(--stash-soft)}
.chip.balance{color:var(--accent);background:var(--accent-soft)}
.chip.term{border-bottom:none}
.styleicon{font-size:12px;cursor:help}
.styleicon.elite{filter:drop-shadow(0 0 3px rgba(229,161,60,.5))}
.sq-row{display:grid;grid-template-columns:44px minmax(0,1fr) auto;gap:2px 10px;
  align-items:center;padding:9px 14px}
.sq-row.closing{border-color:var(--tier)}
.sq-round{font-size:11px;font-weight:700;color:var(--ink3);background:var(--surface2);
  border-radius:6px;padding:3px 0;text-align:center}
.sq-row.closing .sq-round{color:var(--tier);background:var(--tier-soft)}
.sq-why{grid-column:2/4;font-size:11.5px;color:var(--ink3);margin-top:1px}
.sq-closing-tag{font-size:10px;font-weight:700;color:var(--tier);letter-spacing:.4px}
.balmeter{font-size:11px;font-weight:650;color:var(--ink2);margin-left:auto;
  text-transform:none;letter-spacing:0}
/* Round plan: compact card per round — badge left, three stacked lanes right */
.rp-row{display:grid;grid-template-columns:46px minmax(0,1fr);gap:10px;
  background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:9px 12px 9px 9px;margin-bottom:8px;align-items:center}
.rp-round{display:flex;flex-direction:column;justify-content:center;align-items:center;
  background:var(--surface2);border-radius:9px;padding:6px 0;align-self:stretch}
.rp-round b{font-size:13.5px}
.rp-round span{font-size:9.5px;color:var(--ink3)}
.rp-lanes{display:flex;flex-direction:column;gap:4px;min-width:0}
.rp-line{display:flex;align-items:baseline;gap:6px;min-width:0;font-size:12.5px}
.rp-lane{flex:none;width:16px;text-align:center}
.rp-name{font-weight:650;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rp-meta{flex:none;font-size:10.5px;color:var(--ink3);margin-left:auto}
.rp-empty{color:var(--ink3);font-size:11px}
.rowlist .card{display:flex;justify-content:space-between;align-items:center;
  padding:10px 14px}
.side .card{padding:12px 14px}
.rosteritem{display:flex;justify-content:space-between;align-items:baseline;
  padding:5px 0;border-bottom:1px solid var(--border);font-size:13.5px}
.rosteritem:last-child{border:none}
.empty{color:var(--ink3);font-size:13px;padding:8px 2px}
.lastpick{display:flex;gap:8px;align-items:baseline;padding:4px 0;
  font-size:12.5px;color:var(--ink2)}
.lastpick b{color:var(--ink);font-weight:600}
footer{flex:none;background:rgba(11,14,19,.92);
  border-top:1px solid var(--border);padding:6px 20px;font-size:12px;
  color:var(--ink3);display:flex;gap:16px;align-items:center}
.err{color:var(--gone)}
.term{border-bottom:1px dotted var(--ink3);cursor:help}
#tooltip{position:fixed;display:none;max-width:300px;background:var(--surface3);
  border:1px solid var(--border);border-radius:9px;padding:9px 12px;font-size:12.5px;
  line-height:1.45;color:var(--ink);box-shadow:0 10px 28px -6px rgba(0,0,0,.55);
  z-index:50;pointer-events:none}
/* rankings view */
.rk-controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
.rk-controls input[type=text]{background:var(--surface2);border:1px solid var(--border);
  border-radius:9px;padding:8px 12px;color:var(--ink);font-size:13.5px;outline:none;
  min-width:200px;flex:1}
.rk-controls input[type=text]:focus{border-color:var(--accent)}
.chipbtn{background:var(--surface2);border:1px solid var(--border);color:var(--ink2);
  border-radius:999px;padding:5px 12px;font-size:12px;font-weight:650;cursor:pointer}
.chipbtn.on{background:var(--accent);border-color:var(--accent);color:#fff}
.rk-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:14px}
table.rk{width:100%;border-collapse:collapse;font-size:13.5px;min-width:760px}
table.rk thead th{position:sticky;top:0;background:var(--surface3);text-align:left;
  padding:9px 10px;font-size:11px;text-transform:uppercase;letter-spacing:.5px;
  color:var(--ink3);cursor:pointer;white-space:nowrap;border-bottom:1px solid var(--border)}
table.rk thead th:hover{color:var(--ink)}
table.rk thead th.sorted{color:var(--accent)}
table.rk tbody td{padding:8px 10px;border-bottom:1px solid var(--border);white-space:nowrap}
table.rk tbody tr:hover{background:var(--surface2)}
table.rk tbody tr.taken{opacity:.45}
table.rk tbody tr.tierbreak td{border-top:2px solid var(--tier)}
table.rk tbody tr.tierbreak td:nth-child(2){position:relative}
table.rk tbody tr.tierbreak td:nth-child(2)::before{content:"⛰ new tier for this position";
  position:absolute;top:-9px;left:8px;font-size:9px;font-weight:700;color:var(--tier);
  background:var(--surface3);padding:0 5px;border-radius:3px;letter-spacing:.3px;
  white-space:nowrap;z-index:2}
.tierpill.brk{background:var(--tier-soft);color:var(--tier)}
.rk-hint{font-size:11.5px;color:var(--ink3);margin:-6px 0 12px}
table.rk th:nth-child(2),table.rk td:nth-child(2){position:sticky;left:0;
  background:var(--surface3);z-index:1}
table.rk td:nth-child(2){background:var(--surface)}
table.rk tbody tr:hover td:nth-child(2){background:var(--surface2)}
table.rk tbody tr.taken td:nth-child(2){background:var(--surface)}
.rk-name{font-weight:600;display:flex;align-items:center;gap:6px}
.tierpill{font-size:10.5px;font-weight:700;padding:1px 6px;border-radius:5px;
  background:var(--surface2);color:var(--ink2)}
.ownerpill{font-size:11px;color:var(--ink3)}
.posfilter{display:flex;gap:6px;flex-wrap:wrap}
@media(max-width:480px){body{font-size:12px}main{padding:12px}.headtop{padding:9px 12px 7px}}
</style></head><body>
<header>
  <div class="headtop">
    <h1 id="leagueName">Draft Assistant</h1>
    <select id="leagueSel"></select>
    <span class="pill" id="pickstate"></span>
    <span class="pill" id="nextpick"></span>
    <div class="spacer"></div>
    <button class="pill teampill" id="teamPill" onclick="setView('team')" title="Jump to My Team">
      <span id="teamPillText">My team</span></button>
    <span class="pill"><span class="dot"></span><span id="stamp">connecting…</span></span>
    <button class="iconbtn" onclick="manualRefresh()">⟳ Refresh</button>
    <button class="iconbtn" onclick="openGlossary()">📖 Glossary</button>
    <button class="pill" onclick="showRosterIndex()">👥 Rosters</button>
  </div>
  <div class="tabs">
    <div class="tab active" data-view="draft" onclick="setView('draft')">Draft Room</div>
    <div class="tab" data-view="rankings" onclick="setView('rankings')">Rankings</div>
    <div class="tab" data-view="team" onclick="setView('team')">👤 My Team</div>
    <div class="tab" data-view="moves" onclick="setView('moves')">🔥 Moves</div>
    <div class="tab" data-view="rivals" onclick="setView('rivals')">👥 Rivals</div>
  </div>
  <div class="mseg" id="mseg">
    <button data-m="picks" onclick="setMTab('picks')">🎯 Picks</button>
    <button data-m="plan" onclick="setMTab('plan')">📋 Plan</button>
    <button data-m="queue" onclick="setMTab('queue')">💤 Queue</button>
  </div>
  <div class="progress"><i id="progressbar" style="width:0%"></i></div>
  <div id="pathBar"><span class="path-back term" data-tip="Go back to where you were (browser back works too)" onclick="history.back()">←</span><span id="pathCrumbs" class="term" data-tip="Where you are: league / view / selection. Click any segment to jump straight there."></span></div>
</header>

<div id="tooltip"></div>
<div id="rosterBack" onclick="closeRoster()"></div>
<aside id="rosterPane" aria-label="Team roster">
  <div class="ghead"><h2 id="rosterTitle">Roster</h2>
    <button class="gclose" onclick="closeRoster()" aria-label="Close">&times;</button></div>
  <div class="gbody" id="rosterBody"></div>
</aside>
<div id="glossaryBack" onclick="closeGlossary()"></div>
<aside id="glossary" aria-label="Glossary">
  <div class="ghead"><h2>Glossary</h2>
    <button class="gclose" onclick="closeGlossary()" aria-label="Close">&times;</button></div>
  <div class="gbody">
    <div class="gsearch"><input id="gsearch" placeholder="Search a term…" oninput="filterGlossary()"></div>
    <dl id="glist"></dl>
  </div>
</aside>

<main>
  <div id="view-draft">
    <div class="cols">
      <div class="col" id="colA">
        <div id="draftBanner"></div>
        <section class="sec" data-sec="recs">
          <h2 onclick="toggleSec('recs')"><span class="chev">▾</span>Top picks now</h2>
          <div class="sec-body"><div id="recs"></div></div></section>
      </div>
      <div class="col" id="colB">
        <section class="sec" id="planSec" data-sec="plan" style="display:none">
          <h2 class="term" data-tip="A live map of your next rounds, re-simulated after every pick: for each of your upcoming turns, one 🚀 high-upside, 💤 sleeper, and 🛡 safe pick. A player only appears at his NOW-OR-NEVER round — still available at that pick, but gone by your next one (per ADP). An empty lane means nothing there needs taking that round; wait. The last planned round shows best available (no horizon beyond it)." onclick="toggleSec('plan')"><span class="chev">▾</span>📋 Round plan</h2>
          <div class="sec-body"><div id="roundplan"></div></div></section>
        <section class="sec" data-sec="waiters">
          <h2 class="term" data-tip="His ADP is later than your NEXT-NEXT pick (the one after your upcoming turn), so the room probably won't take him before you get another shot — spend your upcoming pick elsewhere and still land him then." onclick="toggleSec('waiters')"><span class="chev">▾</span>🟢 Safe to wait</h2>
          <div class="sec-body"><div id="waiters" class="rowlist"></div></div></section>
      </div>
      <div class="col" id="colC">
        <section class="sec" id="squeuesec" data-sec="squeue">
          <h2 class="term" data-tip="Players the market underprices in THIS league's scoring, plus contingent league-winners — the names we must not forget. Ordered by the round the market will take them; amber = their window closes before your next 1-2 turns." onclick="toggleSec('squeue')"><span class="chev">▾</span>💤 Sleeper queue</h2>
          <div class="sec-body"><div id="squeue" class="rowlist"></div></div></section>
        <section class="sec" id="stashsec" data-sec="stashes" style="display:none">
          <h2 class="term" data-tip="Late-round picks that may score nothing for weeks but have a real path to a top-12 role if injury/role battles break their way." onclick="toggleSec('stashes')"><span class="chev">▾</span>🎟 League-winner window</h2>
          <div class="sec-body"><div id="stashes"></div></div></section>
        <section class="sec collapsed" data-sec="last">
          <h2 onclick="toggleSec('last')"><span class="chev">▾</span>Last picks in the room
            <span class="secsum" id="lastSum"></span></h2>
          <div class="sec-body"><div class="card" id="last"></div></div></section>
      </div>
    </div>
  </div>

  <div id="view-team" style="display:none">
    <div class="teamhead">
      <div class="teamhead-stat active" data-filter="all" onclick="setTeamFilter('all')"><b id="teamCount">0</b><span>players</span></div>
      <div class="teamhead-stat" data-filter="elite" onclick="setTeamFilter('elite')"><b id="teamElite">0</b><span>👑 elite</span></div>
      <div class="teamhead-stat" data-filter="floor" onclick="setTeamFilter('floor')"><b id="teamFloor">0</b><span>🛡 floor</span></div>
      <div class="teamhead-stat" data-filter="ceiling" onclick="setTeamFilter('ceiling')"><b id="teamCeiling">0</b><span>🚀 ceiling</span></div>
      <div class="teamhead-lean" id="teamLean"></div>
    </div>
    <div class="teamfilter-tag" id="teamFilterTag" style="display:none">
      Showing <b id="teamFilterLabel"></b> · <span class="teamfilter-clear" onclick="setTeamFilter('all')">✕ clear</span></div>
    <div id="teamGroups"></div>
    <div class="card" id="teamEmpty" style="display:none">
      <div class="empty">No players on your roster yet — they'll appear here as you draft.</div>
    </div>
    <div class="card" id="teamFilterEmpty" style="display:none">
      <div class="empty">No players in this category yet.</div>
    </div>
    <div id="teamTrades"></div>
  </div>

  <div id="view-rivals" style="display:none">
    <div class="rival-controls">
      <select id="rivalSel" onchange="selectRival(this.value)"></select>
    </div>
    <div id="rivalBody"><div class="empty">Loading rosters…</div></div>
  </div>

  <div id="view-moves" style="display:none">
    <div id="movesBody"><div class="empty">Loading moves…</div></div>
  </div>

  <div id="view-rankings" style="display:none">
    <div class="rk-controls">
      <input type="text" id="rkSearch" placeholder="Search player or team… (press / to focus)">
      <div class="posfilter" id="rkPosFilter"></div>
      <button class="chipbtn" id="rkAvailToggle" onclick="toggleAvailOnly()">Available only</button>
    </div>
    <div class="rk-hint">⛰ amber line = you've crossed into a new value tier for that position — the players just above just got noticeably better/worse.</div>
    <div class="rk-wrap"><table class="rk">
      <thead><tr>
        <th data-k="rank">Rank</th><th data-k="name">Player</th><th data-k="pos_rank">Pos</th>
        <th data-k="tier">Tier</th><th data-k="proj">Proj</th><th data-k="vorp">VORP</th>
        <th data-k="adp">ADP</th><th data-k="value">Value</th><th data-k="riskScore">Risk</th>
        <th data-k="usageScore">'25 Usage</th><th data-k="status">Status</th>
      </tr></thead>
      <tbody id="rkBody"></tbody>
    </table></div>
    <div class="empty" id="rkEmpty" style="display:none">No players match.</div>
  </div>
</main>

<footer><span id="foot"></span><span class="err" id="err"></span></footer>

<style>
#glossaryBack,#rosterBack{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:20;
  display:none;backdrop-filter:blur(2px)}
#glossaryBack.open,#rosterBack.open{display:block}
#rosterPane{position:fixed;top:0;right:0;bottom:0;width:400px;max-width:94vw;
  background:var(--surface);border-left:1px solid var(--border);z-index:21;
  transform:translateX(100%);transition:transform .22s ease;
  display:flex;flex-direction:column}
#rosterPane.open{transform:translateX(0)}
#rosterPane .ghead{padding:16px 18px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between}
#rosterPane .ghead h2{font-size:14px;color:var(--ink);margin:0}
#rosterPane .gclose{background:none;border:none;color:var(--ink3);font-size:20px;
  cursor:pointer;line-height:1;padding:2px 6px}
#rosterPane .gbody{overflow-y:auto;padding:10px 14px;flex:1}
#rosterPane h3{font-size:11px;color:var(--ink3);text-transform:uppercase;
  letter-spacing:.6px;margin:14px 0 6px}
.rosterrow{display:flex;align-items:center;gap:8px;padding:7px 8px;
  border-bottom:1px solid var(--border);font-size:13px}
.rosterrow:last-child{border-bottom:none}
.rosterrow .rp-proj{margin-left:auto;color:var(--ink2)}
.vbadge{font-size:10px;font-weight:700;letter-spacing:.5px;border-radius:5px;
  padding:2px 7px;margin-left:6px;vertical-align:1px}
.vclaim{background:rgba(255,120,60,.16);color:#ff9b63;border:1px solid rgba(255,120,60,.4)}
.vwatch{background:var(--surface3);color:var(--ink2);border:1px solid var(--border)}
.voptional{background:rgba(240,200,60,.14);color:#e8c766;border:1px solid rgba(240,200,60,.35)}
.vskip{background:var(--surface2);color:var(--ink3);border:1px solid var(--border);text-decoration:line-through}
.card.vhot{border-color:rgba(255,120,60,.45)}
.ownerlink{color:var(--accent);cursor:pointer;text-decoration:underline;
  text-decoration-style:dotted;text-underline-offset:2px}
.ownerlink:hover{filter:brightness(1.2)}
#pathBar{display:flex;align-items:center;gap:8px;padding:4px 14px 6px;
  overflow-x:auto;scrollbar-width:none;white-space:nowrap;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px}
#pathBar::-webkit-scrollbar{display:none}
.path-back{color:var(--ink2);cursor:pointer;border:1px solid var(--border);
  border-radius:6px;padding:1px 8px;background:var(--surface2);flex:0 0 auto;
  user-select:none}
.path-back:hover{color:var(--ink);border-color:var(--accent)}
#pathCrumbs{color:var(--ink3)}
.crumb{color:var(--ink2);cursor:pointer;padding:1px 2px}
.crumb:hover{color:var(--accent);text-decoration:underline}
.crumb.here{color:var(--ink);cursor:default;text-decoration:none}
.crumb-sep{color:var(--ink3);margin:0 4px;user-select:none}
#glossary{position:fixed;top:0;right:0;bottom:0;width:380px;max-width:92vw;
  background:var(--surface);border-left:1px solid var(--border);z-index:21;
  transform:translateX(100%);transition:transform .22s ease;
  display:flex;flex-direction:column}
#glossary.open{transform:translateX(0)}
#glossary .ghead{padding:16px 18px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between}
#glossary .ghead h2{font-size:14px;color:var(--ink);text-transform:none;
  letter-spacing:0;margin:0}
#glossary .gclose{background:none;border:none;color:var(--ink3);font-size:20px;
  cursor:pointer;line-height:1;padding:2px 6px}
#glossary .gclose:hover{color:var(--ink)}
#glossary .gbody{overflow-y:auto;padding:6px 18px 24px}
#glossary .gsearch{position:sticky;top:0;background:var(--surface);padding:10px 0 8px}
#glossary .gsearch input{width:100%;background:var(--surface2);border:1px solid var(--border);
  border-radius:9px;padding:9px 12px;color:var(--ink);font-size:13.5px;outline:none}
#glossary .gsearch input:focus{border-color:var(--accent)}
#glossary dt{font-size:13.5px;font-weight:700;color:var(--ink);margin-top:14px;
  display:flex;align-items:center;gap:8px}
#glossary dt .gicon{font-size:13px}
#glossary dd{font-size:13px;color:var(--ink2);margin:3px 0 0;line-height:1.5}
#glossary .gitem.hide{display:none}
</style>

<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const qs=new URLSearchParams(location.search);

const GLOSSARY=[
 {t:"VORP",i:"📊",d:"Value Over Replacement Player — projected points above the best player left at that position if everyone drafted starters first. This is our core rank; higher VORP = bigger edge over your bench/waiver alternative."},
 {t:"ADP",i:"🎯",d:"Average Draft Position on this platform, in this league's format (PPR/superflex/etc). It predicts where the ROOM will take a player — not his true value. Compare it to our rank: if ADP is much later than our rank, he's safe to wait on; if much earlier, the market will take him before you'd naturally pick him."},
 {t:"Tier",i:"⛰",d:"Players grouped by natural value cliffs (gaps in VORP), not straight rank. The rule: take from a tier that's about to run out; never reach inside a deep, flat tier where the 8th option is nearly as good as the 1st."},
 {t:"'25 Usage",i:"📈",d:"Last season's real usage shares — the stats the experts call 'stickiest' year-over-year. WR/TE show target share (T%): 25%+ strong, 30%+ elite. RBs show carry share (R%). Hover for the full trio including offensive snap share. 'rookie' = no 2025 NFL stats. Visibility only — projections already price expected roles."},
 {t:"Vacated opportunity",i:"🕳️",d:"Targets/carries from last season belonging to players no longer on that roster — someone must absorb them. Per-team numbers live in reports/<season>/draft/vacated-opportunity.md and team_env.json (refresh with scripts/vacated_report.py). The cross-reference that turns camp reports into draft picks."},
 {t:"Risk index",i:"⚠️",d:"A systematic 0-100 downside-risk score per player: positional age curve (RBs decline from ~26-27, WRs from ~29, TEs from ~30, QBs from ~34, K/DEF ageless), last-season durability (games active), current injury status, rookie uncertainty, and TD-dependence volatility. 🟢 under 20, 🟡 20-44, 🔴 45+. High risk shaves up to 12% off a player's VORP before ranking, so the board is risk-adjusted — two players with equal projections rank differently if one is a 29-year-old RB coming off injury. Same formula for everyone; no per-player judgment."},
 {t:"Elite",i:"👑",d:"Tier 1 at his position — a real value cliff separates him from the field, computed once from the full board (not the shrinking available pool), so he stays tagged 'elite' all draft long even after other tier-1 peers get drafted, and even once he's on your roster. Usually only 1-3 players per position qualify. Can combine with floor or ceiling — an elite player who's also high-floor is a true lock; an elite ceiling player is a true alpha. A genuine elite faller (way past his ADP) overrides any archetype plan — take him."},
 {t:"Gone by your next pick",i:"⏳",d:"His ADP falls inside the gap between now and your next turn — the room is very likely to take him before you pick again. Treat these as now-or-never."},
 {t:"Safe to wait",i:"🟢",d:"His ADP is later than your NEXT-NEXT pick (the one after your upcoming turn) — the room probably won't take him before you get another shot, so you can use your upcoming pick on someone else and still land him then. This is deliberately NOT 'will he survive your very next pick' — that bar is almost always trivially cleared and would flag elite players as 'safe' right before they vanish."},
 {t:"Pos rank (e.g. RB1, WR12)",i:"#️⃣",d:"His rank within just his own position — the 1st, 12th, etc. best at that spot on our board. Useful for spotting position runs and comparing like-for-like."},
 {t:"League-winner / stash",i:"🎟",d:"A late-round pick that may score nothing for weeks, but has a real path to a top-12 role if an injury or role battle breaks his way. Only worth a pick in the final rounds, where the alternative is a replacement-level veteran with a firm, low ceiling."},
 {t:"Handcuff",i:"🔗",d:"The backup to a bell-cow running back. If the starter gets hurt, the handcuff inherits a starter's workload overnight — cheap insurance with league-winning upside, best on good offenses."},
 {t:"Replacement level",i:"🪑",d:"The projected points of the best player at a position who'd be left on waivers if every team filled its starters. VORP is measured against this line, and it moves with your league's team count and roster slots."},
 {t:"Superflex",i:"♾️",d:"A flex roster slot that can start a QB in addition to RB/WR/TE. Because two QBs can start at once, QBs become the scarcest, most valuable position — draft them far earlier than in single-QB leagues."},
 {t:"PPR / Half PPR",i:"🏈",d:"Points Per Reception — a bonus (1.0 full, 0.5 half) for every catch, on top of yardage/TDs. Raises the value of high-volume pass-catchers (slot WRs, receiving RBs, TEs) relative to boom/bust deep threats."},
 {t:"IDP",i:"🛡️",d:"Individual Defensive Player — leagues that start real DL/LB/DB instead of (or beside) a team DEF. Scoring is built from tackles, sacks, and takeaways, and can vary wildly by league (see: our assisted-tackle scoring fix)."},
 {t:"Keeper",i:"🔒",d:"A player a team is allowed to keep from last season instead of re-drafting, usually at a cost (a draft round or auction price). Keepers are removed from the draft pool at their assigned pick."},
 {t:"Snake draft",i:"🐍",d:"Draft order reverses each round (1→18, then 18→1, then 1→18...) so no one repeatedly picks last. Your exact pick numbers each round follow directly from your slot."},
 {t:"Offense tier (1-5)",i:"🌡️",d:"Our team-environment rating built from Vegas win totals and implied scoring — tier 1 offenses (shootout-heavy, high win total) get a small projection boost; tier 5 offenses get a small haircut. Everyone on that team is nudged, not just the stars."},
 {t:"FAAB",i:"💰",d:"Free Agent Acquisition Budget — a fixed-dollar budget (not priority order) teams bid blind for waiver players. Highest bid wins the claim; the money doesn't carry over between waiver periods in most leagues."},
 {t:"Rostered",i:"👤",d:"This player is on a team's roster right now (used once a draft is complete — this is the in-season view). Shows who has him so you know he's not a free agent."},
 {t:"Value column",i:"⚖️",d:"ADP minus our rank. Positive = the market lets you draft him later than he's worth here (a target); negative = the market takes him earlier than our math says (pay up or pass)."},
 {t:"Round plan",i:"📋",d:"A live map of your next ~6 rounds, re-simulated after every pick in the room: for each of your upcoming turns it projects who will still be available (by ADP) and offers one 🚀 high-upside, one 💤 sleeper, and one 🛡 safe pick. Each name appears once, at the earliest round you'd realistically take him. It's the flight plan; Top Picks Now is the control stick."},
 {t:"Sleeper",i:"💤",d:"A player the market underprices — his ADP is far later than what he's actually worth under THIS league's scoring and settings. The Sleeper Queue lists them by the round the market will take them, so you scoop them one round before their window closes instead of forgetting them mid-draft."},
 {t:"Floor player",i:"🛡",d:"Production built on stable weekly volume — catches, carries, attempts — with low touchdown dependence. Scores something every week. The stability half of a balanced roster."},
 {t:"Ceiling player",i:"🚀",d:"A spike-week scorer whose points lean on touchdowns and big plays. Can win you a week single-handedly, can also give you 4 points. The upside half of a balanced roster."},
 {t:"Roster balance",i:"⚖️",d:"A championship roster mixes floor (🛡) and ceiling (🚀) players — floors keep you alive every week, ceilings win you the weeks you're outgunned. The meter over My Roster shows your mix; when it skews 2+ one way, recommendations get a small nudge toward the other kind."},
 {t:"🏟 Dome",i:"🏟",d:"Team plays home games indoors — stable conditions, never a weather risk. Carries a small positive projection nudge."},
 {t:"❄️ Cold December",i:"❄️",d:"Team's home stadium is cold-weather outdoor, and this player is a QB/WR/TE/K — the fantasy playoffs (weeks 15-17) are more likely to be a weather-affected passing game. Carries a small negative projection nudge. Not applied to RBs, since weather mainly disrupts the passing game."},
];
const FLAG_MEANING={"🏟":"Dome team — stable conditions, no weather risk.",
  "❄️":"Cold-weather outdoor stadium — passing game risk in the wk 15-17 fantasy playoffs.",
  "📺":"Fresh expert take (The Fantasy Footballers / Sal Vetri) — hover shows the distilled thesis."};
function flagsTitle(flags){
  return Object.keys(FLAG_MEANING).filter(k=>flags.includes(k)).map(k=>FLAG_MEANING[k]).join(" ");
}
function renderGlossary(){
  $("glist").innerHTML=GLOSSARY.map(g=>`
    <div class="gitem"><dt><span class="gicon">${g.i}</span>${esc(g.t)}</dt>
      <dd>${esc(g.d)}</dd></div>`).join("");
}
function openGlossary(){renderGlossary();$("glossary").classList.add("open");
  $("glossaryBack").classList.add("open");setTimeout(()=>$("gsearch").focus(),80);}
function closeGlossary(){$("glossary").classList.remove("open");$("glossaryBack").classList.remove("open");}
function filterGlossary(){
  const q=$("gsearch").value.toLowerCase();
  document.querySelectorAll("#glist .gitem").forEach((el,i)=>{
    const g=GLOSSARY[i];
    el.classList.toggle("hide", q && !(g.t.toLowerCase().includes(q)||g.d.toLowerCase().includes(q)));
  });
}
const TERMDEF=Object.fromEntries(GLOSSARY.map(g=>[g.t,g.d]));
// Wraps `label` in a hoverable span ONLY when there's real explanatory text
// behind it — an element with nothing to say never gets the "?" cursor.
function tip(label,text){
  if(!text) return esc(label);
  return `<span class="term" data-tip="${esc(text)}">${esc(label)}</span>`;
}
function term(label,key){return tip(label,TERMDEF[key]);}

// ---------- custom tooltip (immediate + reliable, unlike native title=) ----------
const tipEl=$("tooltip");
function positionTip(e){
  const pad=14, w=tipEl.offsetWidth||260, h=tipEl.offsetHeight||50;
  let x=e.clientX+pad, y=e.clientY+pad;
  if(x+w>window.innerWidth-8) x=e.clientX-w-pad;
  if(y+h>window.innerHeight-8) y=Math.max(8,e.clientY-h-pad);
  tipEl.style.left=x+"px"; tipEl.style.top=y+"px";
}
document.addEventListener("mouseover",e=>{
  const t=e.target.closest("[data-tip]");
  if(t){ tipEl.textContent=t.getAttribute("data-tip"); tipEl.style.display="block"; positionTip(e); }
});
document.addEventListener("mousemove",e=>{
  if(tipEl.style.display==="block") positionTip(e);
});
document.addEventListener("mouseout",e=>{
  const t=e.target.closest("[data-tip]");
  if(t && !(e.relatedTarget && t.contains(e.relatedTarget))) tipEl.style.display="none";
});

// ---------- audio alert on "on the clock" ----------
let audioCtx=null;
document.addEventListener("click",()=>{ if(!audioCtx){ try{audioCtx=new (window.AudioContext||window.webkitAudioContext)();}catch(e){} } },{once:true});
function beep(){
  if(!audioCtx) return;
  try{
    if(audioCtx.state==="suspended") audioCtx.resume();
    [0,180].forEach(delay=>setTimeout(()=>{
      const o=audioCtx.createOscillator(), g=audioCtx.createGain();
      o.type="sine"; o.frequency.value=880;
      g.gain.setValueAtTime(0.0001,audioCtx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.35,audioCtx.currentTime+0.01);
      g.gain.exponentialRampToValueAtTime(0.0001,audioCtx.currentTime+0.3);
      o.connect(g); g.connect(audioCtx.destination);
      o.start(); o.stop(audioCtx.currentTime+0.3);
    },delay));
  }catch(e){}
}

// ---------- keyboard ----------
document.addEventListener("keydown",e=>{
  if(e.key==="Escape"){closeGlossary();return;}
  if(e.key==="/" && document.activeElement.tagName!=="INPUT"){
    e.preventDefault();
    if(currentView==="rankings") $("rkSearch").focus(); else setView("rankings");
  }
});

// ---------- state ----------
let currentView=qs.get("view")||localStorage.getItem("ff_view")||"draft";
let currentLeague=qs.get("league")||localStorage.getItem("ff_league")||null;
let wasOnClock=false, rankingsLoaded=false, rankingsData=[], sortKey="vorp", sortDir=-1, availOnly=false;
let currentRival=qs.get("rival")||null;

function setView(v){
  currentView=v; localStorage.setItem("ff_view",v);
  document.body.dataset.view=v;
  document.querySelectorAll(".tab").forEach(t=>t.classList.toggle("active",t.dataset.view===v));
  $("view-draft").style.display=v==="draft"?"":"none";
  $("view-rankings").style.display=v==="rankings"?"":"none";
  $("view-team").style.display=v==="team"?"":"none";
  $("view-moves").style.display=v==="moves"?"":"none";
  $("view-rivals").style.display=v==="rivals"?"":"none";
  updateUrl();
  if(v==="rankings" && !rankingsLoaded) loadRankings();
  if(v==="moves") loadMoves();
  if(v==="team") loadTeamTrades();
  if(v==="rivals") loadRivals();
}
function updateUrl(){
  const p=new URLSearchParams(); p.set("league",currentLeague||""); p.set("view",currentView);
  if(currentView==="rivals"&&currentRival) p.set("rival",currentRival);
  const url="?"+p.toString();
  if(typeof popNav!=="undefined" && popNav){history.replaceState(null,"",url);}
  else if(location.search!==url){history.pushState(null,"",url);}
  try{renderPath();}catch(e){}
}
// Mobile section tabs (Draft Room only; CSS-gated to <=820px)
let mTab=localStorage.getItem("ff_mtab")||"picks";
function setMTab(t){
  mTab=t; localStorage.setItem("ff_mtab",t);
  document.body.classList.remove("m-picks","m-plan","m-queue","m-team");
  document.body.classList.add("m-"+t);
  document.querySelectorAll("#mseg button").forEach(b=>
    b.classList.toggle("on",b.dataset.m===t));
}
setMTab(mTab);

// ---------- collapsible sections ----------
// Default state lives in the markup (roster/last start collapsed, rest
// open); localStorage overrides once the user has ever toggled one.
document.querySelectorAll(".sec[data-sec]").forEach(el=>{
  const key="ff_sec_"+el.dataset.sec, saved=localStorage.getItem(key);
  if(saved!==null) el.classList.toggle("collapsed", saved==="1");
});
function toggleSec(name){
  const el=document.querySelector(`.sec[data-sec="${name}"]`);
  if(!el) return;
  el.classList.toggle("collapsed");
  localStorage.setItem("ff_sec_"+name, el.classList.contains("collapsed")?"1":"0");
}
const STYLE_ICON={floor:"🛡",ceiling:"🚀",balanced:""};
const STYLE_TITLE={floor:"Floor player — production built on stable weekly volume (catches/carries), low TD dependence.",
  ceiling:"Ceiling player — spike-week scorer whose points lean on TDs/big plays; high weekly upside, low floor.",
  balanced:""};
const RISK_ICON={low:"🟢",med:"🟡",high:"🔴"};
function riskTag(p){
  // inline dot only for notable risk — a green dot on everyone is noise
  const r=p.risk; if(!r||!r.band||r.band==="low") return "";
  const txt=`Risk ${r.score}/100 (${r.band}). `+(r.factors.length?r.factors.join(". ")+".":"No specific risk factors.")
    +" Systematic index: age curve + last-season durability + current injury + volatility. High risk shaves up to 12% of a player's VORP before ranking.";
  return `<span class="styleicon term" data-tip="${esc(txt)}">${RISK_ICON[r.band]}</span>`;
}
const ELITE_TITLE="Elite — Tier 1 at his position on our board: a real value cliff separates him from everyone else, not just \"best of what's left.\" Stays tagged all draft long, even once other tier-1 peers get drafted. A true elite faller (miles past his ADP) overrides any draft plan — take him.";
function styleTag(p){
  let out="";
  if(p.elite) out+=`<span class="styleicon term elite" data-tip="${esc(ELITE_TITLE)}">👑</span>`;
  const s=p.style;
  if(s&&STYLE_ICON[s]) out+=`<span class="styleicon term" data-tip="${esc(STYLE_TITLE[s])}">${STYLE_ICON[s]}</span>`;
  out+=riskTag(p);
  return out;
}
function player(p,extra=""){return `<span class="pname">${esc(p.name)}
  <span class="badge">${esc(p.pos)} · ${esc(p.team)}</span>${styleTag(p)}
  ${p.injury?`<span class="inj">${esc(p.injury)}</span>`:""}${extra}</span>`}

let leaguesList=[];
async function loadLeagues(){
  // The first request can race the server's initial board computation (which
  // can take a minute). Retry instead of letting one failure kill init() and
  // leave the league switcher permanently empty.
  for(let attempt=0; attempt<40 && !leaguesList.length; attempt++){
    try{
      const r=await fetch("/api/leagues");
      const j=await r.json();
      if(Array.isArray(j) && j.length){ leaguesList=j; break; }
    }catch(e){ /* server still warming up */ }
    $("err").textContent="loading leagues…";
    await new Promise(res=>setTimeout(res,1500));
  }
  $("err").textContent="";
  if(!leaguesList.length){
    $("err").textContent="could not load leagues — is the server still starting?";
    return;
  }
  if(!currentLeague || !leaguesList.some(l=>l.league_id===currentLeague))
    currentLeague=leaguesList[0]?.league_id;
  $("leagueSel").innerHTML=leaguesList.map(l=>
    `<option value="${l.league_id}" ${l.league_id===currentLeague?"selected":""}>${esc(l.name)} — ${l.teams}t</option>`).join("");
  paintLeagueStatus(leaguesList.find(l=>l.league_id===currentLeague));
  $("leagueSel").onchange=async e=>{
    currentLeague=e.target.value; localStorage.setItem("ff_league",currentLeague);
    paintLeagueStatus(leaguesList.find(l=>l.league_id===currentLeague));
    rankingsLoaded=false; updateUrl();
    await selectLeague();
    if(currentView==="rankings") loadRankings();
    if(currentView==="moves") loadMoves();
    if(currentView==="team") loadTeamTrades();
    if(currentView==="rivals") loadRivals(true);
  };
}
function paintLeagueStatus(l){
  if(!l) return;
  $("leagueName").innerHTML=esc(l.name)+`<span class="statustag st-${l.status}">${esc((l.status||"").replace("_"," "))}</span>`;
}
async function selectLeague(){
  $("stamp").textContent="switching league…";
  await fetch("/api/select?league_id="+encodeURIComponent(currentLeague));
  await tick();
}
function manualRefresh(){
  $("stamp").textContent="refreshing…";
  fetch("/api/refresh?league_id="+encodeURIComponent(currentLeague)).then(tick);
  delete movesCache[currentLeague]; delete rostersCache[currentLeague];
  if(currentView==="rankings") loadRankings(true);
  if(currentView==="moves") loadMoves();
  if(currentView==="rivals") loadRivals&&loadRivals();
}

function render(d){
  document.title=(d.on_clock?"🔴 ON THE CLOCK · ":"")+d.league+" · Draft Assistant";
  document.body.classList.toggle("onclock", !!d.on_clock);
  if(d.on_clock && !wasOnClock){
    beep();
    // on a phone, jump straight to the decision screen
    if(window.innerWidth<=820) setMTab("picks");
  }
  wasOnClock=!!d.on_clock;

  $("pickstate").innerHTML=`Round <b class="num">${d.round}/${d.rounds}</b>
    &nbsp;·&nbsp; Pick <b class="num">#${d.pick_on_clock}</b>`;
  $("progressbar").style.width=Math.min(100,100*(d.pick_on_clock-1)/Math.max(1,d.total_picks))+"%";
  const np=$("nextpick");
  if(d.on_clock){np.className="pill onclock";np.textContent="YOU ARE ON THE CLOCK";}
  else if(d.my_next){np.className="pill";
    np.innerHTML=`Your pick <b class="num">#${d.my_next}</b>
      &nbsp;·&nbsp; <b class="num">${d.until}</b> away`;}
  else if(!d.slot && d.status!=="complete"){np.className="pill";np.textContent="Order not set";}
  else{np.className="pill";np.textContent="No picks left";}

  $("draftBanner").innerHTML =
    d.status==="complete"
      ? `<div class="banner">🏁 This draft is complete. Final roster and pick history below — switch to <b>Rankings</b> for free-agent / waiver value.</div>`
    : (!d.slot)
      ? `<div class="banner">🕐 The commissioner hasn't set the draft order yet, so we don't know your pick slot. Recommendations will appear here once the order is randomized — switch to <b>Rankings</b> for the pre-draft board in the meantime.</div>`
    : "";

  const maxv=Math.max(...(d.recs||[]).map(r=>r.vorp),1);
  $("recs").innerHTML=(d.recs||[]).slice(0,6).map((r,i)=>`
    <div class="card rec${i==0?" primary":""}">
      <div class="rankno num">${i+1}</div>
      ${player(r)}
      <div class="stats num"><div class="v">${r.vorp.toFixed(0)}</div>
        <div class="a">${term("VORP","VORP")} · ${term("ADP","ADP")} ${r.adp?r.adp.toFixed(0):"—"}
        · ${term(r.pos_rank,"Pos rank (e.g. RB1, WR12)")} ${term("T"+r.tier,"Tier")}</div></div>
      <div class="vbar"><i style="width:${Math.max(4,100*r.vorp/maxv)}%"></i></div>
      ${r.reasons.length?`<div class="chips">${r.reasons.map(x=>{
        const ic={gone:"⏳",tier:"⛰",need:"➕",stash:"🎟",balance:"⚖️"}[x.kind]||"";
        const gk={gone:"Gone by your next pick",tier:"Tier",need:null,
                  stash:"League-winner / stash",balance:"Roster balance"}[x.kind];
        const tp=gk?(TERMDEF[gk]||""):"";
        return `<span class="chip ${x.kind}${tp?" term":""}" ${tp?`data-tip="${esc(tp)}"`:""}>${ic} ${esc(x.text)}</span>`;
      }).join("")}</div>`:""}
    </div>`).join("")||(d.status!=="complete"?`<div class="empty">No candidates.</div>`:"");
  $("waiters").innerHTML=(d.waiters||[]).map(p=>`
    <div class="card">${player(p)}
      <span class="meta num">${term("ADP","ADP")} ${p.adp.toFixed(0)} · ${term("VORP","VORP")} ${p.vorp.toFixed(0)}</span>
    </div>`).join("")||`<div class="empty">Nothing safely waitable — value is being drafted at price.</div>`;
  $("stashsec").style.display=(d.stashes||[]).length?"":"none";
  $("stashes").innerHTML=(d.stashes||[]).map(p=>`
    <div class="card">${player(p)}
      <div class="meta" style="margin-top:4px">${esc(p.why)}</div></div>`).join("");
  const plan=d.round_plan||[];
  $("planSec").style.display=plan.length?"":"none";
  const LANE_META={upside:["🚀","High-upside pick projected available at this round"],
    sleeper:["💤","Sleeper (market-underpriced) pick projected available at this round"],
    safe:["🛡","Safe high-floor pick projected available at this round"]};
  $("roundplan").innerHTML=plan.map(rp=>`
    <div class="rp-row">
      <div class="rp-round"><b class="num">R${rp.round}</b><span class="num">#${rp.pick_no}</span></div>
      <div class="rp-lanes">
      ${["upside","sleeper","safe"].map(lane=>{
        const p=rp[lane];
        if(!p) return `<div class="rp-line rp-empty"><span class="rp-lane">${LANE_META[lane][0]}</span> —</div>`;
        return `<div class="rp-line">
          <span class="rp-lane term" data-tip="${esc(LANE_META[lane][1])}">${LANE_META[lane][0]}</span>
          <span class="rp-name">${esc(p.name)}${styleTag(p)}${p.injury?` <span class="inj">${esc(p.injury[0])}</span>`:""}</span>
          <span class="rp-meta num">${esc(p.pos_rank)} · V${p.vorp.toFixed(0)}${p.adp?` · A${p.adp.toFixed(0)}`:""}</span>
        </div>`;
      }).join("")}
      </div>
    </div>`).join("");
  const TYPE_ICON={value:"💤",winner:"🎟",both:"💤🎟"};
  const TYPE_TIP={value:TERMDEF["Sleeper"],
                  winner:TERMDEF["League-winner / stash"],
                  both:"Both a sleeper (market underprices him here) AND a league-winner stash (late-round contingent upside). "};
  $("squeuesec").style.display=(d.sleeper_queue||[]).length?"":"none";
  $("squeue").innerHTML=(d.sleeper_queue||[]).map(s=>`
    <div class="card sq-row${s.closing?" closing":""}">
      <div class="sq-round num">R${s.window_round}</div>
      ${player(s,` <span class="term" data-tip="${esc(TYPE_TIP[s.type]||"")}">${TYPE_ICON[s.type]||""}</span>${s.closing?` <span class="sq-closing-tag">⚠ WINDOW CLOSING</span>`:""}`)}
      <span class="meta num">${s.value!=null?("+"+s.value+" val"):""}</span>
      <div class="sq-why">${esc(s.why)}</div>
    </div>`).join("");
  renderTeam(d);
  const lastPicks=d.last_picks||[];
  $("lastSum").textContent = lastPicks.length
    ? `#${lastPicks[0].pick_no} ${lastPicks[0].name}` : "none yet";
  $("last").innerHTML=lastPicks.map(p=>`
    <div class="lastpick"><span class="num">#${p.pick_no}</span>
      <b>${esc(p.name)}</b> <span>${esc(p.pos)} · ${esc(p.team)}</span></div>`).join("")
    ||`<div class="empty">Draft hasn't started.</div>`;
  $("foot").textContent=`slot ${d.slot||"—"} · draft ${d.status} · pick ${d.pick_on_clock}/${d.total_picks}`;
}

const POS_ORDER=["QB","RB","WR","TE","K","DEF","DL","LB","DB"];
const TEAM_FILTER_LABEL={all:"all players",elite:"👑 elite players",
  floor:"🛡 floor players",ceiling:"🚀 ceiling players"};
const TEAM_FILTER_PRED={all:()=>true, elite:p=>!!p.elite,
  floor:p=>p.style==="floor", ceiling:p=>p.style==="ceiling"};
let teamFilter="all", lastTeamD=null;
function setTeamFilter(f){
  teamFilter=f;
  document.querySelectorAll(".teamhead-stat").forEach(el=>
    el.classList.toggle("active",el.dataset.filter===f));
  if(lastTeamD) renderTeam(lastTeamD);
}
function renderTeam(d){
  lastTeamD=d;
  const fullRoster=d.roster||[], b=d.balance;
  // Header pill: always-visible one-click shortcut into My Team (desktop only, CSS-gated)
  $("teamPillText").textContent = `👤 ${fullRoster.length||0}` +
    (b ? ` · 👑${b.elite||0} 🛡${b.floor} 🚀${b.ceiling}` : "");
  $("teamCount").textContent=fullRoster.length;
  $("teamElite").textContent=b?(b.elite||0):0;
  $("teamFloor").textContent=b?b.floor:0;
  $("teamCeiling").textContent=b?b.ceiling:0;
  $("teamLean").textContent = b&&b.lean ? `Lean ${b.lean==="floor"?"🛡 floor":"🚀 ceiling"} next pick` : "";
  $("teamEmpty").style.display = fullRoster.length?"none":"";

  const roster=fullRoster.filter(TEAM_FILTER_PRED[teamFilter]||(()=>true));
  const filtered=teamFilter!=="all";
  $("teamFilterTag").style.display=filtered?"":"none";
  if(filtered) $("teamFilterLabel").textContent=`${roster.length} ${TEAM_FILTER_LABEL[teamFilter]}`;
  $("teamFilterEmpty").style.display=(filtered && fullRoster.length && !roster.length)?"":"none";

  const groups={};
  roster.forEach(p=>{ (groups[p.pos]=groups[p.pos]||[]).push(p); });
  const order=[...POS_ORDER, ...Object.keys(groups).filter(p=>!POS_ORDER.includes(p)).sort()];
  $("teamGroups").innerHTML = order.filter(pos=>groups[pos]&&groups[pos].length).map(pos=>{
    const players=groups[pos].slice().sort((a,b2)=>(b2.vorp||0)-(a.vorp||0));
    return `<div class="teamgroup">
      <h3>${esc(pos)} <span class="cnt">${players.length}</span></h3>
      ${players.map(p=>`
        <div class="teamplayer">${player(p)}
          <span class="tp-vorp-wrap"><span class="tp-vorp num term" data-tip="${esc(TERMDEF["VORP"])}">${p.vorp!=null?p.vorp.toFixed(0):"—"}</span><span class="tp-vorp-label">VORP</span></span>
        </div>`).join("")}
    </div>`;
  }).join("");
}

let lastStamp=null, lastTickAt=0, everRendered=false;
async function tick(){
  const lg=currentLeague;
  try{
    const r=await fetch("/data?league_id="+encodeURIComponent(lg||""));
    const j=await r.json();
    if(lg!==currentLeague) return;  // league switched mid-poll — stale payload
    if(j.data && (j.stamp!==lastStamp)){render(j.data);lastStamp=j.stamp;everRendered=true;}
    lastTickAt=Date.now();
    $("err").textContent=j.error?("api: "+j.error):"";
    // A blank page with a tiny red "loading" line reads as broken. Until the
    // first render lands, say plainly that boards are being computed.
    if(!everRendered){
      $("draftBanner").innerHTML=
        `<div class="banner">⏳ Computing boards for this league — projections are
         re-scored under its exact settings, which takes up to a minute on a
         cold start. This panel fills in automatically.</div>`;
    }
  }catch(e){$("err").textContent="connection lost — retrying";}
}
setInterval(()=>{
  if(!lastTickAt) return;
  const secs=Math.round((Date.now()-lastTickAt)/1000);
  $("stamp").textContent=(secs<2?"updated just now":`updated ${secs}s ago`);
},1000);
setInterval(tick,5000);
// After laptop/tab sleep the elapsed-time pill can show hours until the next
// poll fires — refresh immediately on wake instead.
document.addEventListener("visibilitychange",()=>{if(!document.hidden) tick();});
window.addEventListener("focus",()=>tick());

// ---------- rival roster viewer ----------
let rostersCache={};   // league_id -> {t:epoch_ms, j:payload}
const CLIENT_TTL_MS=10*60*1000;  // always-open tab: refetch stale data
async function fetchRosters(force){
  const lg=currentLeague;  // capture NOW — the await below can outlive a league switch
  const hit=rostersCache[lg];
  if(!force && hit && Date.now()-hit.t<CLIENT_TTL_MS) return hit.j;
  const r=await fetch("/api/rosters?league_id="+encodeURIComponent(lg)+(force?"&force=1":""));
  const j=await r.json();
  if(!j.error) rostersCache[lg]={t:Date.now(),j};  // keyed by the league we fetched
  return j;
}
function ownerLink(name){
  if(!name||name==="?"||name==="ME") return esc(name||"");
  return `<span class="ownerlink" data-owner="${esc(name)}">${esc(name)}</span>`;
}
function rosterRows(list){
  return (list||[]).map(pl=>`
    <div class="rosterrow">${player(pl)}
      <span class="rp-proj num">${pl.proj}</span></div>`).join("")
    || `<div class="empty">—</div>`;
}
async function showRoster(owner, skipTrail){
  const j=await fetchRosters(false);
  if(j.error||!j.teams) return;
  const team=j.teams.find(x=>x.owner===owner)||(owner==="ME"&&j.teams.find(x=>x.mine));
  if(!team) return;
  $("rosterTitle").innerHTML=`${esc(team.owner)}${team.mine?" (you)":""}
    <span class="meta num" style="margin-left:8px">${esc(team.record)} · starters proj ${team.starters_proj}</span>`;
  $("rosterBody").innerHTML=`
    <h3>Starters (${team.starters.length}) — proj ${team.starters_proj}</h3>${rosterRows(team.starters)}
    <h3>Bench (${team.bench.length})</h3>${rosterRows(team.bench)}
    ${team.reserve.length?`<h3>IR (${team.reserve.length})</h3>${rosterRows(team.reserve)}`:""}
    ${team.taxi.length?`<h3>Taxi (${team.taxi.length})</h3>${rosterRows(team.taxi)}`:""}`;
  $("rosterPane").classList.add("open");$("rosterBack").classList.add("open");
}
function closeRoster(){$("rosterPane").classList.remove("open");$("rosterBack").classList.remove("open");}
async function showRosterIndex(){
  const j=await fetchRosters(false);
  if(j.error||!j.teams) return;
  $("rosterTitle").textContent=`${j.league} — all rosters`;
  $("rosterBody").innerHTML=`<h3>By projected starting lineup</h3>`+j.teams.map(tm=>`
    <div class="rosterrow rosterjump" style="cursor:pointer" data-owner="${esc(tm.owner)}">
      <b>${esc(tm.owner)}${tm.mine?" (you)":""}</b>
      <span class="meta num">${esc(tm.record)}</span>
      <span class="rp-proj num">${tm.starters_proj}</span></div>`).join("");
  $("rosterPane").classList.add("open");$("rosterBack").classList.add("open");
}
document.addEventListener("click",e=>{
  const el=e.target.closest(".ownerlink,.rosterjump");
  if(el&&el.dataset.owner) showRoster(el.dataset.owner);
});

// ---------- rivals tab ----------
function rivalTeamHtml(team){
  return `
    <div class="card" style="margin-bottom:10px">
      <b>${esc(team.owner)}${team.mine?" (you)":""}</b>
      <span class="meta num" style="margin-left:8px">${esc(team.record)} · starters proj ${team.starters_proj}${team.fpts?` · PF ${team.fpts}`:""}</span>
    </div>
    <h3 style="font-size:11px;color:var(--ink3);text-transform:uppercase;letter-spacing:.6px;margin:12px 0 6px">Starters (${team.starters.length})</h3>${rosterRows(team.starters)}
    <h3 style="font-size:11px;color:var(--ink3);text-transform:uppercase;letter-spacing:.6px;margin:12px 0 6px">Bench (${team.bench.length})</h3>${rosterRows(team.bench)}
    ${team.reserve.length?`<h3 style="font-size:11px;color:var(--ink3);text-transform:uppercase;letter-spacing:.6px;margin:12px 0 6px">IR (${team.reserve.length})</h3>${rosterRows(team.reserve)}`:""}
    ${team.taxi.length?`<h3 style="font-size:11px;color:var(--ink3);text-transform:uppercase;letter-spacing:.6px;margin:12px 0 6px">Taxi (${team.taxi.length})</h3>${rosterRows(team.taxi)}`:""}`;
}
async function loadRivals(leagueChanged){
  const j=await fetchRosters(false);
  if(j.error||!j.teams){$("rivalBody").innerHTML=`<div class="empty">Couldn't load rosters.</div>`;return;}
  const saved=(currentRival&&j.teams.some(x=>x.owner===currentRival))?currentRival
            :localStorage.getItem("ff_rival_"+currentLeague);
  let pick=(!leagueChanged&&saved&&j.teams.some(x=>x.owner===saved))?saved
           :(j.teams.find(x=>!x.mine)||j.teams[0]).owner;
  currentRival=pick;
  $("rivalSel").innerHTML=j.teams.map(x=>
    `<option value="${esc(x.owner)}" ${x.owner===pick?"selected":""}>${esc(x.owner)}${x.mine?" (you)":""} — ${esc(x.record)} · proj ${x.starters_proj}</option>`).join("");
  renderRival(j, pick);
}
function renderRival(j, owner){
  const team=j.teams.find(x=>x.owner===owner);
  $("rivalBody").innerHTML=team?rivalTeamHtml(team):`<div class="empty">Team not found.</div>`;
}
async function selectRival(owner){
  localStorage.setItem("ff_rival_"+currentLeague, owner);
  currentRival=owner;
  const j=await fetchRosters(false);
  if(!j.error&&j.teams) renderRival(j, owner);
  updateUrl();
}

// ---------- breadcrumb path (terminal-style) ----------
// The URL is the path: league / view [ / rival ]. ← is real history-back.
const VIEW_LABEL={draft:"Draft Room",rankings:"Rankings",team:"My Team",moves:"Moves",rivals:"Rivals"};
function leagueShort(lid){
  const l=leaguesList.find(x=>x.league_id===lid);
  return l?l.name.replace(/^🪓 /,""):"…";
}
function renderPath(){
  if(!leaguesList.length) return;
  const segs=[{label:leagueShort(currentLeague),act:"league"},
              {label:VIEW_LABEL[currentView]||currentView,act:"view"}];
  if(currentView==="rivals"&&currentRival) segs.push({label:currentRival,act:"rival"});
  $("pathCrumbs").innerHTML=segs.map((s,i)=>{
    const here=i===segs.length-1;
    return `<span class="crumb${here?" here":""}" data-act="${s.act}">${esc(s.label)}</span>`;
  }).join(`<span class="crumb-sep">/</span>`);
}
document.addEventListener("click",e=>{
  const c=e.target.closest(".crumb");
  if(!c||c.classList.contains("here")) return;
  if(c.dataset.act==="league") setView("draft");        // league root = Draft Room
  else if(c.dataset.act==="view"){currentRival=null;setView(currentView);} // drop the rival segment
});
// Browser back/forward: URL is pushed on each navigation (see updateUrl),
// popstate restores without re-pushing.
let popNav=false;
window.addEventListener("popstate",async ()=>{
  const q=new URLSearchParams(location.search);
  const lg=q.get("league"), vw=q.get("view")||"draft";
  popNav=true;
  currentRival=q.get("rival")||null;
  if(lg && lg!==currentLeague){
    currentLeague=lg; localStorage.setItem("ff_league",lg);
    const sel=$("leagueSel"); if(sel) sel.value=lg;
    paintLeagueStatus(leaguesList.find(l=>l.league_id===lg));
    rankingsLoaded=false;
    await selectLeague();
  }
  setView(vw);
  popNav=false;
});

// ---------- moves + trade center ----------
let movesCache={};   // league_id -> {t:epoch_ms, j:payload}
async function fetchMoves(force){
  const lg=currentLeague;  // capture NOW — see fetchRosters
  const hit=movesCache[lg];
  if(!force && hit && Date.now()-hit.t<CLIENT_TTL_MS) return hit.j;
  const r=await fetch("/api/moves?league_id="+encodeURIComponent(lg)+(force?"&force=1":""));
  const j=await r.json();
  if(!j.error) movesCache[lg]={t:Date.now(),j};
  return j;
}
function offerCard(o){
  if(!o.partner) return `
    <div class="card"><b>⏱ Pounce trigger armed</b>
      <div class="sq-why">${esc(o.why||"")}</div></div>`;
  return `
    <div class="card">
      <div><b>📬 To ${ownerLink(o.partner)}</b> <span class="meta">· ${esc(o.state||"")}</span></div>
      <div style="margin:6px 0"><span class="badge">GIVE</span> ${esc((o.give||[]).join(" + "))}
        &nbsp;→&nbsp; <span class="badge">GET</span> <b>${esc((o.get||[]).join(" + "))}</b></div>
      ${o.lineup_delta?`<div class="meta num">${esc(o.lineup_delta)}</div>`:""}
      <div class="sq-why">${esc(o.why||"")}</div>
      ${o.fallback?`<div class="sq-why">↩ Fallback: ${esc(o.fallback)}</div>`:""}
      ${o.pitch?`<div class="sq-why">🗣 “${esc(o.pitch)}”</div>`:""}
    </div>`;
}
async function loadTeamTrades(){
  const el=$("teamTrades"); if(!el) return;
  const j=await fetchMoves(false);
  if(j.error){el.innerHTML="";return;}
  const offers=(j.trade_offers||[]).map(offerCard).join("");
  const targets=(j.trade_targets||[]).map(i=>`
    <div class="card"><b>${ownerLink(i.partner)}</b><div class="sq-why">${esc(i.note)}</div></div>`).join("");
  el.innerHTML = (offers||targets) ? `
    <h2 style="margin:18px 0 8px">🤝 Trade center</h2>
    ${offers?`<div class="meta" style="margin-bottom:6px">Standing offers (you send in the Sleeper app; Burrow &amp; Corum are untouchable):</div>${offers}`:""}
    ${targets?`<div class="meta" style="margin:10px 0 6px">Complementary-need partners (algorithmic — raw ideas, not vetted offers):</div>${targets}`:""}` : "";
}
async function loadMoves(){
  const el=$("movesBody");
  el.innerHTML=`<div class="empty">Scanning waivers, drops and trades…</div>`;
  const lg=currentLeague;
  const j=await fetchMoves(false);
  if(lg!==currentLeague) return;  // league switched while loading — stale response
  if(j.error){el.innerHTML=`<div class="empty">Couldn't load: ${esc(j.error)}</div>`;return;}
  if(!j.in_season){
    el.innerHTML=`
      ${(j.trade_offers||[]).length?`<h2>🤝 Standing trades</h2>${j.trade_offers.map(offerCard).join("")}`:""}
      <div class="card"><div class="empty">Waivers &amp; drops activate once this league is in season —
      it hasn't drafted yet. Use <b>Rankings</b> for the pre-draft board.</div></div>`;
    return;
  }
  const faab=j.faab?`<div class="pill" style="margin:0 0 10px;white-space:normal;height:auto;line-height:1.5;padding:8px 12px">💰 FAAB
      <b class="num">$${j.faab.left}</b>/<span class="num">$${j.faab.budget}</span> left
      · most aggressive rival has spent <b class="num">$${j.faab.rival_max_spent}</b></div>`:"";
  const vBadge=d=>{
    const nl=d.source==="newsletter";
    const tipPrefix=nl?"Newsletter ruling: ":"Auto signal (newsletter hasn't ruled on him): ";
    if(d.verdict==="claim") return `<span class="vbadge vclaim term" data-tip="${esc(tipPrefix+(d.verdict_why||""))}">🔥 CLAIM${d.bid!=null?` $${esc(String(d.bid))}`:""}${d.drop_for?` · drop ${esc(d.drop_for)}`:""}</span>`;
    if(d.verdict==="optional") return `<span class="vbadge voptional term" data-tip="${esc(tipPrefix+(d.verdict_why||""))}">🟡 OPTIONAL${d.bid!=null?` $${esc(String(d.bid))}`:""}</span>`;
    if(d.verdict==="skip") return `<span class="vbadge vskip term" data-tip="${esc(tipPrefix+(d.verdict_why||""))}">✋ SKIP</span>`;
    if(d.verdict==="watch") return `<span class="vbadge vwatch term" data-tip="${esc(tipPrefix+(d.verdict_why||""))}">👀 watch</span>`;
    return "";
  };
  const drops=(j.drops||[]).map(d=>`
    <div class="card${d.verdict==="claim"?" vhot":""}">${player(d,vBadge(d))}
      <span class="meta num">proj ${d.proj} · ${d.trend?d.trend.toLocaleString()+" adds/24h · ":""}dropped by ${ownerLink(d.dropped_by)} ${d.hours_ago}h ago</span>
    </div>`).join("")||`<div class="empty">No valuable drops in the last 4 days.</div>`;
  const fas=(j.waiver_targets||[]).map(d=>`
    <div class="card${d.verdict==="claim"?" vhot":""}">${player(d,vBadge(d))}
      <span class="meta num">proj ${d.proj}${d.trend?` · ${d.trend.toLocaleString()} adds/24h`:""}</span>
    </div>`).join("")||`<div class="empty">Nothing on the wire beats your bench.</div>`;
  const bench=(j.weakest_bench||[]).map(d=>`
    <div class="card">${player(d)}<span class="meta num">proj ${d.proj}${d.age?` · age ${d.age}`:""}</span></div>`).join("");
  el.innerHTML=`
    ${faab}
    <h2 class="term" data-tip="Players other managers dropped recently who are still free agents — a good drop is the cheapest acquisition in fantasy, and drops often precede news going wide.">🔥 Drop it like it's hot</h2>${drops}
    <h2 class="term" data-tip="Top free agents by projection + trending adds under THIS league's scoring. Compare against your weakest bench before claiming; in dynasty leagues never cut young stashes for veteran points.">📈 Waiver targets</h2>${fas}
    ${bench?`<h2 class="term" data-tip="Your lowest-projected ACTIVE bench players (taxi/IR excluded — they consume no bench spot). Drop candidates — but in dynasty leagues rank drops by ASSET value: aging vets first, stalled year-3+ second, young stashes never.">🪑 Weakest bench</h2>${bench}`:""}
    <div class="meta" style="margin-top:10px">Badges with a $ bid are the newsletter's rulings — the two surfaces always agree. Plain badges are auto signals for players the newsletter hasn't ruled on yet (🔥 = startable upgrade or breakout trending; DEF/K and dynasty vets never auto-claim). In dynasty leagues pick the DROP by asset value: aging vets first, young stashes never.</div>`;
}

// ---------- rankings ----------
async function loadRankings(force){
  $("rkEmpty").style.display="none";
  $("rkBody").innerHTML=`<tr><td colspan="11" class="empty">Loading…</td></tr>`;
  const lg=currentLeague;
  try{
    const r=await fetch(`/api/board?league_id=${encodeURIComponent(lg)}${force?"&force=1":""}`);
    const data=await r.json();
    if(lg!==currentLeague) return;  // league switched while loading — stale response
    rankingsData=data;
    rankingsData.forEach(r=>{
      r.riskScore=r.risk?r.risk.score:null;
      // usage sort key: the position's primary share (WR/TE targets, RB rushes)
      r.usageScore = ((r.pos==="RB"||r.pos==="QB") ? r.rush_share : r.tgt_share) ?? null;
    });
    rankingsLoaded=true;
    buildPosFilter();
    renderRankings();
  }catch(e){ $("rkBody").innerHTML=`<tr><td colspan="11" class="empty">Failed to load rankings.</td></tr>`; }
}
let posFilter="ALL";
function buildPosFilter(){
  const positions=["ALL",...new Set(rankingsData.map(r=>r.pos))];
  $("rkPosFilter").innerHTML=positions.map(p=>
    `<button class="chipbtn ${p===posFilter?"on":""}" onclick="setPosFilter('${p}')">${p}</button>`).join("");
}
function setPosFilter(p){posFilter=p;buildPosFilter();renderRankings();}
function toggleAvailOnly(){availOnly=!availOnly;$("rkAvailToggle").classList.toggle("on",availOnly);renderRankings();}
$("rkSearch")?.addEventListener("input",renderRankings);
document.querySelectorAll("table.rk thead th").forEach(th=>th.addEventListener("click",()=>{
  const k=th.dataset.k;
  // First click gives the natural "best first" order per column: rank/tier/
  // ADP ascending (1 is best), value columns descending. Second click flips.
  if(sortKey===k) sortDir*=-1; else {sortKey=k; sortDir = (k==="adp"||k==="rank"||k==="tier")?1:-1;}
  document.querySelectorAll("table.rk thead th").forEach(x=>x.classList.remove("sorted"));
  th.classList.add("sorted");
  renderRankings();
}));
function renderRankings(){
  if(!rankingsData.length) return;
  const q=($("rkSearch")?.value||"").toLowerCase();
  let rows=rankingsData.filter(r=>
    (posFilter==="ALL"||r.pos===posFilter) &&
    (!availOnly||r.status==="available") &&
    (!q || r.name.toLowerCase().includes(q) || r.team.toLowerCase().includes(q)));
  rows=rows.slice().sort((a,b)=>{
    let av=a[sortKey], bv=b[sortKey];
    if(av==null) return 1; if(bv==null) return -1;
    if(typeof av==="string") return sortDir*av.localeCompare(bv);
    return sortDir*(av-bv);
  });
  $("rkEmpty").style.display=rows.length?"none":"";
  const lastTierSeen={};
  $("rkBody").innerHTML=rows.slice(0,400).map(r=>{
    const statusHtml = r.status==="available" ? `<span class="meta">Free</span>`
      : r.status==="drafted" ? `<span class="ownerpill">Drafted · ${ownerLink(r.owner)} #${r.pick_no}</span>`
      : `<span class="ownerpill">${term("Rostered","Rostered")} · ${ownerLink(r.owner)}</span>`;
    // ADP beyond ~400 is noise (undrafted-pool artifact), not real waiver value
    const val = (r.value==null||(r.adp||0)>400) ? "—" : (r.value>0?"+":"")+r.value;
    // Tier break: this position's value just dropped to the next tier down —
    // tracked independently per position, so it works in any sort/filter view.
    const isBreak = lastTierSeen[r.pos]!==undefined && lastTierSeen[r.pos]!==r.tier;
    lastTierSeen[r.pos]=r.tier;
    const rowClass=[r.status!=='available'?'taken':'', isBreak?'tierbreak':''].filter(Boolean).join(" ");
    return `<tr class="${rowClass}">
      <td class="num">${r.rank}</td>
      <td><div class="rk-name">${esc(r.name)}<span class="badge">${esc(r.team)}</span>${styleTag(r)}
        ${r.injury?`<span class="inj">${esc(r.injury)}</span>`:""}${(r.flags&&(flagsTitle(r.flags)||r.expert))?` <span class="term" data-tip="${esc([flagsTitle(r.flags),r.expert].filter(Boolean).join(" — "))}">${r.flags}</span>`:(r.flags?` <span>${r.flags}</span>`:"")}</div></td>
      <td>${esc(r.pos_rank)}</td>
      <td><span class="tierpill${isBreak?' brk':''}">T${r.tier}</span></td>
      <td class="num">${r.proj.toFixed(0)}</td>
      <td class="num">${r.vorp.toFixed(0)}</td>
      <td class="num">${r.adp?r.adp.toFixed(0):"—"}</td>
      <td class="num">${val}</td>
      <td class="num">${r.risk?`<span class="term" data-tip="${esc((r.risk.factors||[]).join(". ")||"No specific risk factors")}">${RISK_ICON[r.risk.band]||""} ${r.risk.score}</span>`:"—"}</td>
      <td class="num">${(()=>{
        if(!["QB","RB","WR","TE"].includes(r.pos)) return "—";
        if(r.usageScore==null) return `<span class="meta">rookie</span>`;
        const parts=[];
        if(r.tgt_share!=null) parts.push(`${r.tgt_share}% of team targets`);
        if(r.rush_share!=null&&r.rush_share>=3) parts.push(`${r.rush_share}% of team carries`);
        if(r.snap_share!=null) parts.push(`${r.snap_share}% of offensive snaps`);
        let label;
        if(r.pos==="QB") label = (r.rush_share!=null&&r.rush_share>=5)?`R${r.rush_share}%`:"—";
        else label = r.pos==="RB" ? `R${r.rush_share}%` : `T${r.tgt_share}%`;
        if(label==="—") return label;
        return `<span class="term" data-tip="${esc("2025 season: "+parts.join(" · ")+". Target share is the stickiest year-over-year stat — 25%+ is strong, 30%+ elite (WR/TE). For RBs the shown number is carry share.")}">${label}</span>`;
      })()}</td>
      <td>${statusHtml}</td>
    </tr>`;
  }).join("");
}

(async function init(){
  try{
    renderGlossary();
    await loadLeagues();
    setView(currentView);
    if(leaguesList.length) await selectLeague();
    tick();
  }catch(e){
    // Never leave the UI half-booted and silent — say what broke.
    $("err").textContent="startup error: "+(e&&e.message?e.message:e);
    tick();
  }
})();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _json(self, obj):
        out = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        path = parsed.path

        if path == "/api/leagues":
            return self._json(league_list_payload())

        if path == "/api/select":
            lid = params.get("league_id", [None])[0]
            if lid:
                _active["league_id"] = lid
                try:
                    recompute(lid)
                except Exception as e:
                    return self._json({"ok": False, "error": str(e)})
            return self._json({"ok": True, "league_id": lid})

        if path == "/api/refresh":
            lid = params.get("league_id", [_active["league_id"]])[0]
            if lid:
                try:
                    ctx = get_ctx(lid, force=True)
                    recompute(lid, ctx)
                except Exception as e:
                    return self._json({"ok": False, "error": str(e)})
            return self._json({"ok": True})

        if path == "/api/board":
            lid = params.get("league_id", [_active["league_id"]])[0]
            force = params.get("force", ["0"])[0] == "1"
            if not lid:
                return self._json([])
            try:
                ctx = get_ctx(lid, force=force)
                return self._json(build_board_payload(lid, ctx))
            except Exception as e:
                return self._json({"error": str(e)})

        if path == "/api/rosters":
            lid = params.get("league_id", [_active["league_id"]])[0]
            force = params.get("force", ["0"])[0] == "1"
            if not lid:
                return self._json({})
            try:
                return self._json(rosters_payload(lid, force=force))
            except Exception as e:
                return self._json({"error": str(e)})

        if path == "/api/moves":
            lid = params.get("league_id", [_active["league_id"]])[0]
            force = params.get("force", ["0"])[0] == "1"
            if not lid:
                return self._json({})
            try:
                return self._json(moves_payload(lid, force=force))
            except Exception as e:
                return self._json({"error": str(e)})

        if path == "/data":
            lid = params.get("league_id", [_active["league_id"]])[0]
            st = _state.get(lid, {"data": None, "stamp": "", "error": "loading…"})
            return self._json(st)

        out = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(out)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


def main():
    league_id = sys.argv[1] if len(sys.argv) > 1 else _leagues()[0]["league_id"]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8787
    _active["league_id"] = league_id
    threading.Thread(target=_updater, daemon=True).start()
    print(f"Draft dashboard: http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
