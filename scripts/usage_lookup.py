#!/usr/bin/env python3
"""Week-by-week usage for named players, to verify newsletter/dossier claims
(Late-Round, producer briefs) against Sleeper's stat rows before they go on air.

    python3 scripts/usage_lookup.py "Jonathan Taylor" "CeeDee Lamb" [--weeks 6-9] [--season 2026]

Per week: snap % (snaps), share of the team's targets and carries (skill
players only), scrimmage yards and PPR. Team TD split by pass/rush with --team CIN.
Wk 10 use: confirmed Lamb 44%, Jefferson 33%, Chase Brown 38% of carries; caught
"Taylor 3 straight games under 70% snaps" (it was 2 of 3) and "Tuten 50% snaps" (36%).
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from sleeper import api  # noqa: E402
from sleeper.scoring import score_stat_line  # noqa: E402
import podcast_prep as pp  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--weeks", default="1-18")
    ap.add_argument("--season", default="2026")
    ap.add_argument("--team", action="append", default=[], help="print pass/rush TD split for this team")
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.weeks.split("-"))
    team = defaultdict(lambda: defaultdict(float))
    P = defaultdict(dict)
    for w in range(lo, hi + 1):
        rows = api.get_week_stat_rows(a.season, w) or []
        if not rows:
            continue
        for r in rows:
            st, p = r.get("stats") or {}, r.get("player") or {}
            if p.get("position") not in pp.SKILL:
                continue
            t = r.get("team")
            for k, sk in (("tgt", "rec_tgt"), ("rush", "rush_att"), ("ptd", "pass_td"), ("rtd", "rush_td")):
                team[(t, w)][k] += st.get(sk) or 0
            if (st.get("off_snp") or 0) > 0:
                P[f"{p.get('first_name')} {p.get('last_name')}".lower()][w] = (t, st)
    pct = lambda a, b: f"{a / b:.0%}" if b else "—"  # noqa: E731
    for name in a.names:
        d = P.get(name.lower())
        print(f"== {name}" + ("" if d else " (sin snaps en esas semanas)"))
        for w in sorted(d or {}):
            t, st = d[w]
            T = team[(t, w)]
            print(f"  S{w} {t}: snaps {pct(st.get('off_snp') or 0, st.get('tm_off_snp') or 0)} ({int(st.get('off_snp') or 0)})"
                  f" · targets {int(st.get('rec_tgt') or 0)} = {pct(st.get('rec_tgt') or 0, T['tgt'])}"
                  f" · acarreos {int(st.get('rush_att') or 0)} = {pct(st.get('rush_att') or 0, T['rush'])}"
                  f" · yds {int((st.get('rush_yd') or 0) + (st.get('rec_yd') or 0))}"
                  f" · {score_stat_line(st, pp.PPR):.1f} PPR")
    for t in a.team:
        ptd = sum(v["ptd"] for (tm, _), v in team.items() if tm == t)
        rtd = sum(v["rtd"] for (tm, _), v in team.items() if tm == t)
        print(f"== {t}: TD de pase {int(ptd)} · TD por tierra {int(rtd)} ({pct(ptd, ptd + rtd)} por aire)")


if __name__ == "__main__":
    main()
