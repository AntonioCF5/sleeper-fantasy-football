"""Usage intel from last season's actual stats.

The expert-methods layer (data/intel/expert_methods.md) identifies target
share as "the stickiest year-over-year stat" and vacated-opportunity
accounting as a core valuation tool. Both are computable from Sleeper's
season stats: rec_tgt, rush_att, off_snp/tm_off_snp, plus each row's team.
"""

from collections import defaultdict

from . import api

SKILL_POSITIONS = ("QB", "RB", "WR", "TE")


def season_usage(season: str):
    """(per-player usage, per-team totals) for a completed season.

    per-player: pid -> {team, tgt, rush, snp, tm_snp, gms}
    per-team:   team -> {tgt, rush} (summed over skill players)
    """
    players_usage = {}
    team_tot = defaultdict(lambda: {"tgt": 0.0, "rush": 0.0})
    for r in api.get_season_stats(season, SKILL_POSITIONS) or []:
        st = r.get("stats") or {}
        pid, team = r.get("player_id"), r.get("team")
        if not pid or not team:
            continue
        tgt = st.get("rec_tgt") or 0.0
        rush = st.get("rush_att") or 0.0
        players_usage[pid] = {
            "team": team, "tgt": tgt, "rush": rush,
            "snp": st.get("off_snp") or 0.0,
            "tm_snp": st.get("tm_off_snp") or 0.0,
            "gms": st.get("gms_active"),
        }
        team_tot[team]["tgt"] += tgt
        team_tot[team]["rush"] += rush
    return players_usage, dict(team_tot)


def usage_shares(season: str):
    """pid -> {tgt_share, rush_share, snap_share} as percentages (previous
    season; absent for rookies / players without stats)."""
    pu, tt = season_usage(season)
    out = {}
    for pid, u in pu.items():
        tot = tt.get(u["team"], {})
        out[pid] = {
            "tgt_share": round(100 * u["tgt"] / tot["tgt"], 1) if tot.get("tgt") else None,
            "rush_share": round(100 * u["rush"] / tot["rush"], 1) if tot.get("rush") else None,
            "snap_share": round(100 * u["snp"] / u["tm_snp"], 1) if u["tm_snp"] else None,
        }
    return out


def vacated(season: str, players: dict):
    """Per-team vacated opportunity: how many of last season's targets and
    carries belong to players no longer on that roster (current team from
    the players dump differs, or the player is a free agent/retired).

    team -> {tgt_pct, rush_pct, tgt, rush, departed: [(name, tgt, rush), ...]}
    """
    pu, tt = season_usage(season)
    out = {}
    for team, tot in tt.items():
        gone_tgt = gone_rush = 0.0
        departed = []
        for pid, u in pu.items():
            if u["team"] != team:
                continue
            cur = (players.get(pid) or {}).get("team")
            if cur != team:
                gone_tgt += u["tgt"]
                gone_rush += u["rush"]
                if u["tgt"] >= 20 or u["rush"] >= 30:
                    p = players.get(pid) or {}
                    name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or pid
                    departed.append((name, u["tgt"], u["rush"], cur or "FA"))
        departed.sort(key=lambda d: -(d[1] + d[2]))
        out[team] = {
            "tgt": round(gone_tgt), "rush": round(gone_rush),
            "tgt_pct": round(100 * gone_tgt / tot["tgt"], 1) if tot["tgt"] else 0.0,
            "rush_pct": round(100 * gone_rush / tot["rush"], 1) if tot["rush"] else 0.0,
            "departed": departed[:6],
        }
    return out
