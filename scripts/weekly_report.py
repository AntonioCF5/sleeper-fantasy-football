#!/usr/bin/env python3
"""Generate weekly reports for every league in config.json.

Usage: python3 scripts/weekly_report.py [week]   (defaults to current NFL week)
Reports land in reports/<season>/week<NN>/<league_name>.md
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
    state = api.get_state()
    season = config.get("season") or state["league_season"]
    week = int(sys.argv[1]) if len(sys.argv) > 1 else max(state.get("week") or 1, 1)

    outdir = ROOT / "reports" / str(season) / f"week{week:02d}"
    outdir.mkdir(parents=True, exist_ok=True)

    for lg in config["leagues"]:
        print(f"Analyzing {lg['name']} ...")
        md = reports.weekly_report(lg["league_id"], config["user_id"], str(season), week)
        slug = re.sub(r"[^A-Za-z0-9]+", "-", lg["name"]).strip("-").lower()
        path = outdir / f"{slug}.md"
        path.write_text(md)
        print(f"  -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
