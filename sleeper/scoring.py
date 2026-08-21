"""Score stat lines under a league's exact custom scoring settings.

Sleeper scoring works by summing scoring_settings[stat] * stat_value for
every stat key present in both the league's scoring_settings and the
player's stat line. This means we can score PROJECTED stat lines under any
custom ruleset (TE premium, 6pt pass TD, points-per-first-down, etc.)
instead of trusting the generic pts_ppr fields.
"""


def score_stat_line(stats: dict, scoring_settings: dict) -> float:
    if not stats:
        return 0.0
    return round(
        sum(v * stats[k] for k, v in scoring_settings.items() if k in stats and stats[k]),
        2,
    )


# Which fantasy positions can fill each Sleeper roster slot.
SLOT_ELIGIBILITY = {
    "QB": {"QB"},
    "RB": {"RB"},
    "WR": {"WR"},
    "TE": {"TE"},
    "K": {"K"},
    "DEF": {"DEF"},
    "FLEX": {"RB", "WR", "TE"},
    "WRRB_FLEX": {"RB", "WR"},
    "REC_FLEX": {"WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
    "IDP_FLEX": {"DL", "LB", "DB"},
    "DL": {"DL", "DE", "DT"},
    "LB": {"LB", "ILB", "OLB"},
    "DB": {"DB", "CB", "SS", "FS", "S"},
}


def league_format_notes(league: dict) -> list[str]:
    """Human-readable strategic implications of a league's settings."""
    notes = []
    s = league.get("scoring_settings", {})
    slots = [p for p in league.get("roster_positions", []) if p != "BN"]
    n_teams = league.get("total_rosters", 12)

    ppr = s.get("rec", 0)
    notes.append(
        f"{n_teams}-team, "
        + ("full PPR" if ppr >= 1 else "half PPR" if ppr >= 0.5 else "standard (no PPR)")
    )
    if s.get("rec_te", 0) > s.get("rec", 0) or s.get("bonus_rec_te", 0) > 0:
        notes.append("TE premium — elite TEs jump a full round in value")
    if s.get("pass_td", 4) >= 6:
        notes.append("6pt passing TDs — QBs score closer to elite RB/WR range")
    if slots.count("SUPER_FLEX") or slots.count("QB") >= 2:
        notes.append("Superflex/2QB — QBs are the scarcest asset; draft 2 early, 3 total")
    if any(k in s for k in ("rush_fd", "rec_fd", "pass_fd")):
        notes.append("Points per first down — volume/possession receivers gain value")
    flex_n = sum(slots.count(f) for f in ("FLEX", "WRRB_FLEX", "REC_FLEX"))
    if flex_n >= 2:
        notes.append(f"{flex_n} flex spots — depth at RB/WR matters more than usual")
    if "K" not in slots:
        notes.append("No kicker slot")
    if "DEF" not in slots:
        notes.append("No team defense slot")
    if any(p in SLOT_ELIGIBILITY["IDP_FLEX"] | {"IDP_FLEX"} for p in slots):
        notes.append("IDP league — individual defensive players are rostered")
    taxi = league.get("settings", {}).get("taxi_slots", 0)
    if taxi:
        notes.append(f"Taxi squad ({taxi} slots) — stash rookies")
    if league.get("settings", {}).get("type") == 2:
        notes.append("Dynasty league — rookie picks & long-term value matter")
    elif league.get("settings", {}).get("type") == 1:
        notes.append("Keeper league — check keeper costs before drafting")
    return notes
