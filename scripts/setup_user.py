#!/usr/bin/env python3
"""Resolve a Sleeper username to user_id + leagues and save config.json.

Usage: python3 scripts/setup_user.py <sleeper_username> [season]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sleeper import api  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: setup_user.py <sleeper_username> [season]")
    username = sys.argv[1]
    season = sys.argv[2] if len(sys.argv) > 2 else api.get_state()["league_season"]

    user = api.get_user(username)
    if not user:
        sys.exit(f"No Sleeper user named {username!r}")
    leagues = api.get_user_leagues(user["user_id"], season) or []

    config = {
        "username": user.get("username") or username,
        "user_id": user["user_id"],
        "display_name": user.get("display_name"),
        "season": season,
        "leagues": [
            {
                "league_id": lg["league_id"],
                "name": lg["name"],
                "teams": lg.get("total_rosters"),
                "status": lg.get("status"),
            }
            for lg in leagues
        ],
    }
    path = Path(__file__).resolve().parent.parent / "config.json"
    path.write_text(json.dumps(config, indent=2))
    print(f"Saved {path}")
    print(f"User: {config['display_name']} ({config['user_id']})")
    print(f"{len(leagues)} league(s) in {season}:")
    for lg in config["leagues"]:
        print(f"  - {lg['name']} ({lg['teams']} teams, {lg['status']}) [{lg['league_id']}]")


if __name__ == "__main__":
    main()
