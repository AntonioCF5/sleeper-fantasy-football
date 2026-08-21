#!/usr/bin/env python3
"""Generate a league-specific VORP draft board for each redraft league.

Usage: python3 scripts/draft_prep.py [league_id]   (defaults to all leagues in config)
Boards land in reports/<season>/draft/<league_name>.md
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sleeper import api, reports  # noqa: E402


def main():
    config = json.loads((ROOT / "config.json").read_text())
    season = str(config.get("season") or api.get_state()["league_season"])
    leagues = config["leagues"]
    if len(sys.argv) > 1:
        leagues = [lg for lg in leagues if lg["league_id"] == sys.argv[1]]

    outdir = ROOT / "reports" / season / "draft"
    outdir.mkdir(parents=True, exist_ok=True)
    for lg in leagues:
        print(f"Building draft board for {lg['name']} ...")
        md = reports.draft_report(lg["league_id"], season)
        slug = re.sub(r"[^A-Za-z0-9]+", "-", lg["name"]).strip("-").lower()
        path = outdir / f"{slug}.md"
        path.write_text(md)
        print(f"  -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
