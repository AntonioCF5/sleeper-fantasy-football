"""Intel layer: fold non-Sleeper signals into boards and weekly calls.

Sleeper projections are the baseline; this layer adjusts them with the
context projections can't see. Data lives in two hand-curated JSON files
(refreshed via web research before drafts and weekly in-season):

data/intel/team_env.json — per NFL team:
  {
    "KC": {
      "win_total": 11.5,          # Vegas season win total
      "implied_ppg": 25.1,        # implied offensive environment (optional)
      "offense_tier": 1,          # 1 elite .. 5 bad (judgment from research)
      "venue": "outdoor|dome|retractable",
      "cold_dec": true,           # cold-weather home in fantasy playoffs
      "note": "one-liner from research"
    }, ...
  }

data/intel/player_adjust.json — per player_id:
  {
    "4881": {"mult": 0.92, "flag": "⚠️", "note": "hamstring, missed camp"},
    ...
  }
  mult multiplies projected points (0.85 fade .. 1.15 boost — keep small;
  this is a thumb on the scale, not a new projection). flag shows on boards.

Both files are optional; missing file = no adjustment.
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "intel"

# Offense tier -> projection multiplier. Good offenses lift everyone
# (more TDs, more plays, better game script); bad ones cap ceilings.
TIER_MULT = {1: 1.05, 2: 1.02, 3: 1.0, 4: 0.98, 5: 0.94}


def _load(name):
    p = DATA_DIR / name
    if p.exists():
        return json.loads(p.read_text())
    return {}


def team_env():
    return _load("team_env.json")


def player_adjust():
    return _load("player_adjust.json")


def expert_takes(players):
    """data/intel/expert_takes.json (distilled weekly from The Fantasy
    Footballers + Sal Vetri via scripts/expert_watch.py) resolved to
    player_ids. Returns pid -> list of take dicts. Name resolution prefers
    an exact first+last match on the right team; falls back to name-only
    when unambiguous."""
    data = _load("expert_takes.json")
    takes = data.get("takes", []) if isinstance(data, dict) else []
    by_name = {}
    for pid, p in players.items():
        if not p.get("team"):
            continue
        key = f"{p.get('first_name','')} {p.get('last_name','')}".strip().lower()
        by_name.setdefault(key, []).append((pid, p))
    out = {}
    for t in takes:
        cands = by_name.get((t.get("player") or "").strip().lower(), [])
        if len(cands) > 1 and t.get("team"):
            cands = [c for c in cands if c[1].get("team") == t["team"]]
        if len(cands) == 1:
            out.setdefault(cands[0][0], []).append(t)
    return out


def apply_intel(board_rows, players):
    """Adjust a draft_board's proj/vorp in place; returns list of note strings.

    Adjustments: team offense tier multiplier, cold-December venue haircut
    for pass-catchers/QBs (fantasy playoffs are weeks 15-17), and per-player
    research multipliers. Re-sorts and re-ranks the board afterward.
    """
    env = team_env()
    adj = player_adjust()
    takes = expert_takes(players)
    notes = []
    for r in board_rows:
        pl = players.get(r["player_id"]) or {}
        team = pl.get("team")
        mult = 1.0
        flags = []
        e = env.get(team) if team else None
        if e:
            mult *= TIER_MULT.get(e.get("offense_tier", 3), 1.0)
            if e.get("cold_dec") and r["pos"] in ("QB", "WR", "TE", "K"):
                mult *= 0.98
                flags.append("❄️")
            if e.get("venue") == "dome":
                flags.append("🏟")
        a = adj.get(r["player_id"])
        if a:
            mult *= a.get("mult", 1.0)
            if a.get("flag"):
                flags.append(a["flag"])
            if a.get("note"):
                notes.append(f"{pl.get('first_name','')} {pl.get('last_name','')}: {a['note']}")
        pt = takes.get(r["player_id"])
        if pt:
            # visibility only — expert takes never move projections by
            # themselves (any adjustment goes through player_adjust.json
            # with a documented reason, per the standing rules)
            flags.append("📺")
            r["expert"] = "; ".join(
                f"[{t.get('source','?')}] {t.get('direction','?')}: {t.get('why','')}"
                for t in pt[:3])
        if mult != 1.0:
            delta = r["proj"] * (mult - 1)
            r["proj"] = round(r["proj"] + delta, 1)
            r["vorp"] = round(r["vorp"] + delta, 1)
        r["flags"] = "".join(flags)
    # re-rank on adjusted vorp
    board_rows.sort(key=lambda r: -r["vorp"])
    from collections import defaultdict
    pos_rank = defaultdict(int)
    for i, r in enumerate(board_rows):
        r["rank"] = i + 1
        pos_rank[r["pos"]] += 1
        r["pos_rank"] = f"{r['pos']}{pos_rank[r['pos']]}"
        r["value"] = round((r["adp"] - r["rank"]), 1) if r.get("adp") else None
    return notes
