"""Markdown report generation for weekly league reports and draft prep."""

import json
from datetime import date
from pathlib import Path

from . import analysis, api, intel
from .scoring import league_format_notes


def get_league_corrected(league_id: str) -> dict:
    """League object with any scoring_overrides from config.json applied.

    Use when the league's settings on Sleeper are known to be wrong (e.g. a
    commissioner typo awaiting a fix) so analysis uses the intended scoring.
    """
    league = api.get_league(league_id)
    cfg_path = Path(__file__).resolve().parent.parent / "config.json"
    if cfg_path.exists():
        for lg in json.loads(cfg_path.read_text()).get("leagues", []):
            if lg.get("league_id") == league_id and lg.get("scoring_overrides"):
                league = dict(league)
                league["scoring_settings"] = {
                    **league["scoring_settings"], **lg["scoring_overrides"]
                }
    return league


def _owner_names(league_id):
    users = api.get_league_users(league_id)
    return {u["user_id"]: u.get("display_name") or u.get("username", "?") for u in users}


def weekly_report(league_id: str, my_user_id: str, season: str, week: int) -> str:
    league = get_league_corrected(league_id)
    players = api.get_players()
    rosters = api.get_rosters(league_id)
    owners = _owner_names(league_id)
    scoring = league.get("scoring_settings", {})
    roster_positions = league.get("roster_positions", [])
    positions = analysis.league_positions(league)
    proj = analysis.projection_map(season, week, scoring, positions)
    season_proj = analysis.season_projection_map(season, scoring, positions)

    mine = next((r for r in rosters if r.get("owner_id") == my_user_id
                 or my_user_id in (r.get("co_owners") or [])), None)

    L = [f"# {league['name']} — Week {week} Report",
         f"*Generated {date.today().isoformat()} · {league.get('season')} season*", ""]
    L.append("**Format:** " + "; ".join(league_format_notes(league)))
    L.append("")

    # ---- Power rankings
    pr = analysis.power_rankings(league_id, week - 1)
    if any(p["pf"] > 0 for p in pr):
        L += ["## Power Rankings (all-play + points for)", "",
              "| # | Team | Record | All-Play | PF |", "|---|------|--------|----------|----|"]
        for i, p in enumerate(pr, 1):
            me = " **(you)**" if mine and p["roster_id"] == mine["roster_id"] else ""
            L.append(f"| {i} | {owners.get(p['owner_id'], '?')}{me} | {p['record']} | {p['allplay']} | {p['pf']} |")
        L.append("")

    if mine:
        rid = mine["roster_id"]
        # ---- Matchup
        matchups = api.get_matchups(league_id, week) or []
        my_m = next((m for m in matchups if m["roster_id"] == rid), None)
        if my_m and my_m.get("matchup_id"):
            opp = next((m for m in matchups if m["matchup_id"] == my_m["matchup_id"]
                        and m["roster_id"] != rid), None)
            if opp:
                opp_roster = next((r for r in rosters if r["roster_id"] == opp["roster_id"]), {})
                opp_name = owners.get(opp_roster.get("owner_id"), "?")
                opp_lineup, _ = analysis.optimal_lineup(
                    opp.get("players") or opp_roster.get("players") or [],
                    roster_positions, players, proj)
                opp_pts = sum(p for _, _, p in opp_lineup)
                L += [f"## Week {week} Matchup vs {opp_name}", ""]

        # ---- Lineup
        starters = (my_m.get("starters") if my_m else None) or mine.get("starters") or []
        lineup, bench, gain, (swap_in, swap_out) = analysis.lineup_delta(
            starters, mine.get("players") or [], roster_positions, players, proj)
        total = sum(p for _, _, p in lineup)
        L += [f"## Recommended Lineup — projected {total:.1f} pts", ""]
        if my_m and my_m.get("matchup_id") and opp:
            L.append(f"*Opponent ({opp_name}) optimal projects {opp_pts:.1f} pts.*\n")
        L += ["| Slot | Player | Proj |", "|------|--------|------|"]
        for slot, pid, pts in lineup:
            L.append(f"| {slot} | {analysis.player_label(players, pid) if pid else '— EMPTY —'} | {pts:.1f} |")
        L.append("")
        if gain > 0.5 and swap_in:
            L.append(f"**Action needed:** current lineup leaves **{gain:.1f} pts** on the bench.")
            for pid in swap_in:
                L.append(f"- START {analysis.player_label(players, pid)} ({proj.get(pid, 0):.1f})")
            for pid in swap_out:
                L.append(f"- SIT {analysis.player_label(players, pid)} ({proj.get(pid, 0):.1f})")
            L.append("")
        elif starters:
            L.append("Current lineup is already optimal (per projections). ✅\n")

        # ---- Injury flags on my roster
        flags = [pid for pid in mine.get("players") or []
                 if (players.get(pid) or {}).get("injury_status")]
        if flags:
            L += ["## Injury Watch", ""]
            for pid in sorted(flags, key=lambda p: -season_proj.get(p, 0)):
                L.append(f"- {analysis.player_label(players, pid)}")
            L.append("")

        # ---- Waivers
        targets = analysis.waiver_targets(league_id, players, proj, season_proj)
        if targets:
            worst_bench = min((season_proj.get(pid, 0.0) for pid in bench), default=0)
            L += ["## Waiver Wire Targets", "",
                  "| Player | Wk Proj | Szn Proj | Adds (24h) |",
                  "|--------|---------|----------|------------|"]
            for t in targets:
                hot = " 🔥" if t["trend_count"] > 10000 else ""
                L.append(f"| {analysis.player_label(players, t['player_id'])}{hot} | "
                         f"{t['week_proj']:.1f} | {t['season_proj']:.0f} | {t['trend_count']:,} |")
            L.append("")
            L.append(f"*Your weakest bench spot projects {worst_bench:.0f} season pts — "
                     "anyone above that is an upgrade.*\n")

        # ---- Trade ideas
        ideas = analysis.trade_suggestions(league_id, rid, players, season_proj, roster_positions)
        if ideas:
            L += ["## Trade Radar", ""]
            for idea in ideas[:5]:
                partner = next((r for r in rosters if r["roster_id"] == idea["partner_roster_id"]), {})
                L.append(f"- **{owners.get(partner.get('owner_id'), '?')}**: {idea['note']}")
            L.append("")
    else:
        L.append("\n*(Configured user does not own a roster in this league.)*\n")

    return "\n".join(L)


def draft_report(league_id: str, season: str, top_n: int = 120) -> str:
    league = get_league_corrected(league_id)
    players = api.get_players()
    board, replacement = analysis.draft_board(league, season, players, top_n=top_n)
    intel_notes = intel.apply_intel(board, players)
    analysis._assign_tiers(board)  # re-tier after intel adjustments

    L = [f"# {league['name']} — Draft Board ({season})",
         f"*Generated {date.today().isoformat()} · VORP under this league's exact scoring, "
         "adjusted by the intel layer (team environment, venue, research)*", "",
         "**Format:** " + "; ".join(league_format_notes(league)), "",
         "**Replacement level (season pts):** "
         + ", ".join(f"{p} {v:.0f}" for p, v in sorted(replacement.items())), "",
         "| Rank | Player | Pos | Tier | Proj | VORP | ADP | Value | Flags |",
         "|------|--------|-----|------|------|------|-----|-------|-------|"]
    prev_tier = {}
    for r in board:
        val = ("+" if (r["value"] or 0) > 0 else "") + str(r["value"]) if r["value"] is not None else "—"
        adp = f"{r['adp']:.0f}" if r.get("adp") else "—"
        # visual cue at position-tier boundaries
        tier_cell = f"**T{r['tier']}**" if prev_tier.get(r["pos"]) not in (None, r["tier"]) else f"T{r['tier']}"
        prev_tier[r["pos"]] = r["tier"]
        L.append(f"| {r['rank']} | {analysis.player_label(players, r['player_id'])} | "
                 f"{r['pos_rank']} | {tier_cell} | {r['proj']:.0f} | {r['vorp']} | {adp} | {val} "
                 f"| {r.get('flags','')} |")
    L += ["", "*Value = ADP minus our rank: positive means the market lets you draft "
          "them later than they're worth in THIS league's settings. Bold tier = "
          "first player after a projection cliff at his position — prefer the last "
          "player BEFORE a cliff over a deeper tier's best. "
          "Flags: ❄️ cold-weather venue in fantasy playoffs (wk 15-17), 🏟 dome, "
          "others per research note.*"]
    if intel_notes:
        L += ["", "**Research notes applied:**"] + [f"- {n}" for n in intel_notes]

    # Late-round league winners
    scoring = league.get("scoring_settings", {})
    positions = analysis.league_positions(league)
    season_proj = analysis.season_projection_map(season, scoring, positions)
    slots = league.get("roster_positions", [])
    superflex = "SUPER_FLEX" in slots or slots.count("QB") >= 2
    adp_key = ("adp_2qb" if superflex else
               "adp_ppr" if scoring.get("rec", 0) >= 1 else
               "adp_half_ppr" if scoring.get("rec", 0) >= 0.5 else "adp_std")
    adp = {}
    for p in api.get_season_projections(season, positions):
        a = (p.get("stats") or {}).get(adp_key)
        if a and a < 999:
            adp[p["player_id"]] = a
    winners = analysis.league_winners(league, players, season_proj, adp, superflex)
    if winners:
        L += ["", "## Late-Round League Winners", "",
              "*Contingent-upside stashes for the final 3-4 rounds. They may do "
              "nothing for a month — the payoff is a top-12 role by the fantasy "
              "playoffs. Never spend these picks on replacement-level veterans.*", "",
              "| Player | Type | ADP | Path |", "|--------|------|-----|------|"]
        for w in winners:
            adp_s = f"{w['adp']:.0f}" if w.get("adp") else "undrafted"
            L.append(f"| {analysis.player_label(players, w['player_id'])} | "
                     f"{w['category']} | {adp_s} | {w['why']} |")
    return "\n".join(L)
