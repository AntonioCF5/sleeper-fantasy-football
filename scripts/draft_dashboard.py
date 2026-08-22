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
from sleeper import api  # noqa: E402
from sleeper.reports import _owner_names  # noqa: E402

REFRESH_SECONDS = 5
CTX_TTL = 3600          # rebuild a league's context at most hourly (or on /api/refresh)
BOARD_LIMIT = 400        # rows sent to the rankings table

_lock = threading.Lock()
_ctx_cache = {}           # league_id -> (ctx_tuple, loaded_at)
_state = {}                # league_id -> {"data", "stamp", "error", "picks_seen"}
_active = {"league_id": None}
_config = json.loads((ROOT / "config.json").read_text())


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
    elite_ids = live_draft.compute_elite_ids(board)
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
#view-rankings,#view-team{height:100%;min-height:0;overflow-y:auto;scrollbar-width:thin}
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
  </div>
  <div class="tabs">
    <div class="tab active" data-view="draft" onclick="setView('draft')">Draft Room</div>
    <div class="tab" data-view="rankings" onclick="setView('rankings')">Rankings</div>
    <div class="tab" data-view="team" onclick="setView('team')">👤 My Team</div>
  </div>
  <div class="mseg" id="mseg">
    <button data-m="picks" onclick="setMTab('picks')">🎯 Picks</button>
    <button data-m="plan" onclick="setMTab('plan')">📋 Plan</button>
    <button data-m="queue" onclick="setMTab('queue')">💤 Queue</button>
  </div>
  <div class="progress"><i id="progressbar" style="width:0%"></i></div>
</header>

<div id="tooltip"></div>
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
#glossaryBack{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:20;
  display:none;backdrop-filter:blur(2px)}
#glossaryBack.open{display:block}
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

function setView(v){
  currentView=v; localStorage.setItem("ff_view",v);
  document.body.dataset.view=v;
  document.querySelectorAll(".tab").forEach(t=>t.classList.toggle("active",t.dataset.view===v));
  $("view-draft").style.display=v==="draft"?"":"none";
  $("view-rankings").style.display=v==="rankings"?"":"none";
  $("view-team").style.display=v==="team"?"":"none";
  updateUrl();
  if(v==="rankings" && !rankingsLoaded) loadRankings();
}
function updateUrl(){
  const p=new URLSearchParams(); p.set("league",currentLeague||""); p.set("view",currentView);
  history.replaceState(null,"","?"+p.toString());
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
  const r=await fetch("/api/leagues"); leaguesList=await r.json();
  if(!currentLeague) currentLeague=leaguesList[0]?.league_id;
  $("leagueSel").innerHTML=leaguesList.map(l=>
    `<option value="${l.league_id}" ${l.league_id===currentLeague?"selected":""}>${esc(l.name)} — ${l.teams}t</option>`).join("");
  paintLeagueStatus(leaguesList.find(l=>l.league_id===currentLeague));
  $("leagueSel").onchange=async e=>{
    currentLeague=e.target.value; localStorage.setItem("ff_league",currentLeague);
    paintLeagueStatus(leaguesList.find(l=>l.league_id===currentLeague));
    rankingsLoaded=false; updateUrl();
    await selectLeague();
    if(currentView==="rankings") loadRankings();
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
  if(currentView==="rankings") loadRankings(true);
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
  $("squeuesec").style.display=(d.sleeper_queue||[]).length?"":"none";
  $("squeue").innerHTML=(d.sleeper_queue||[]).map(s=>`
    <div class="card sq-row${s.closing?" closing":""}">
      <div class="sq-round num">R${s.window_round}</div>
      ${player(s,` <span>${TYPE_ICON[s.type]||""}</span>${s.closing?` <span class="sq-closing-tag">⚠ WINDOW CLOSING</span>`:""}`)}
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

let lastStamp=null, lastTickAt=0;
async function tick(){
  try{
    const r=await fetch("/data?league_id="+encodeURIComponent(currentLeague||""));
    const j=await r.json();
    if(j.data && (j.stamp!==lastStamp)){render(j.data);lastStamp=j.stamp;}
    lastTickAt=Date.now();
    $("err").textContent=j.error?("api: "+j.error):"";
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

// ---------- rankings ----------
async function loadRankings(force){
  $("rkEmpty").style.display="none";
  $("rkBody").innerHTML=`<tr><td colspan="11" class="empty">Loading…</td></tr>`;
  try{
    const r=await fetch(`/api/board?league_id=${encodeURIComponent(currentLeague)}${force?"&force=1":""}`);
    rankingsData=await r.json();
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
  if(sortKey===k) sortDir*=-1; else {sortKey=k; sortDir = (k==="adp")?1:-1;}
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
      : r.status==="drafted" ? `<span class="ownerpill">Drafted · ${esc(r.owner)} #${r.pick_no}</span>`
      : `<span class="ownerpill">${term("Rostered","Rostered")} · ${esc(r.owner)}</span>`;
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
  renderGlossary();
  await loadLeagues();
  setView(currentView);
  await selectLeague();
  tick();
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
