#!/usr/bin/env python3
"""Vacated-opportunity report: targets/carries that left each NFL roster.

The experts' valuation tool ("GB must replace 167 targets — who absorbs
them?") computed from real data: last season's per-player usage vs current
rosters. Writes reports/<season>/draft/vacated-opportunity.md and stores
vac_tgt_pct / vac_rush_pct on each team in data/intel/team_env.json so the
intel layer and draft-morning research can use them.

Usage: python3 scripts/vacated_report.py
"""

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sleeper import api, usage  # noqa: E402


def main():
    season = api.get_state()["league_season"]
    prev = str(int(season) - 1)
    players = api.get_players()
    vac = usage.vacated(prev, players)

    env_path = ROOT / "data" / "intel" / "team_env.json"
    env = json.loads(env_path.read_text())
    for team, v in vac.items():
        if team in env:
            env[team]["vac_tgt_pct"] = v["tgt_pct"]
            env[team]["vac_rush_pct"] = v["rush_pct"]
    env_path.write_text(json.dumps(env, indent=1))

    L = [f"# Vacated Opportunity — {prev} volume no longer on the roster",
         f"*Generated {date.today().isoformat()}. Targets/carries from {prev} "
         "belonging to players who changed teams or are unsigned. High vacated "
         "share = someone must eat; cross-reference with camp/preseason usage "
         "to find who.*", "",
         "| Team | Vacated targets | Vacated carries | Departed (top) |",
         "|------|-----------------|-----------------|----------------|"]
    for team, v in sorted(vac.items(), key=lambda kv: -kv[1]["tgt_pct"]):
        dep = ", ".join(f"{d[0]} ({d[3]})" for d in v["departed"][:3]) or "—"
        L.append(f"| {team} | **{v['tgt_pct']}%** ({v['tgt']}) | "
                 f"{v['rush_pct']}% ({v['rush']}) | {dep} |")
    out = ROOT / "reports" / str(season) / "draft" / "vacated-opportunity.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L))
    print(f"wrote {out.relative_to(ROOT)} and updated team_env.json")


if __name__ == "__main__":
    main()
