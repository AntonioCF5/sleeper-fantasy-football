"""Multi-season NFL game history — coaches, QBs, closing lines, since 1999.

Source: nflverse's games.csv (github.com/nflverse/nfldata, maintained weekly
in-season). One row per game with both head coaches, both starting QBs,
closing spread/total/moneylines, rest days, roof, divisional flag, and the
ESPN event id (so it joins to sleeper/espn.py games). Parsed with stdlib csv;
cached 12h in data/cache/nflverse/.

Conventions here (normalized at load):
  - team codes are ESPN's current-franchise codes (LA→LAR, WAS→WSH,
    OAK→LV, SD→LAC, STL→LAR) so a franchise's history is continuous;
  - `spread` is the HOME line in betting notation (negative = home favored),
    i.e. nflverse spread_line with the sign flipped;
  - `result` = home score - away score.
"""

import csv
import io
import subprocess
import time
from collections import defaultdict
from pathlib import Path

URL = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"
CACHE = Path(__file__).resolve().parent.parent / "data" / "cache" / "nflverse" / "games.csv"
TTL = 12 * 3600
FRANCHISE = {"LA": "LAR", "WAS": "WSH", "OAK": "LV", "SD": "LAC", "STL": "LAR"}
NUM = ("season", "week", "away_score", "home_score", "result", "total", "away_rest",
       "home_rest", "away_moneyline", "home_moneyline", "spread_line", "total_line", "div_game")


def _team(t):
    return FRANCHISE.get(t, t)


def load_games():
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if not CACHE.exists() or time.time() - CACHE.stat().st_mtime > TTL:
        out = subprocess.run(["curl", "-sL", "--max-time", "90", URL], capture_output=True).stdout
        if out.startswith(b"game_id,"):
            CACHE.write_bytes(out)
    games = []
    for r in csv.DictReader(io.StringIO(CACHE.read_text())):
        for k in NUM:
            v = r.get(k)
            r[k] = float(v) if v not in (None, "", "NA") else None
        r["home_team"], r["away_team"] = _team(r["home_team"]), _team(r["away_team"])
        r["spread"] = -r["spread_line"] if r["spread_line"] is not None else None
        r["final"] = r["result"] is not None
        hour = int((r.get("gametime") or "13:00").split(":")[0])
        r["primetime"] = hour >= 19 or r.get("weekday") in ("Monday", "Thursday") and hour >= 18
        games.append(r)
    return games


class Ledger:
    """W-L-P tallies: straight up, ATS, O/U, margin."""

    def __init__(self):
        self.su = [0, 0, 0]
        self.ats = [0, 0, 0]
        self.ou = [0, 0, 0]
        self.margins = []

    def add(self, margin, cover=None, ou=None):
        self.su[0 if margin > 0 else 1 if margin < 0 else 2] += 1
        self.margins.append(margin)
        if cover is not None:
            self.ats[0 if cover > 0 else 1 if cover < 0 else 2] += 1
        if ou is not None:
            self.ou[0 if ou > 0 else 1 if ou < 0 else 2] += 1

    @property
    def n(self):
        return sum(self.su)

    @property
    def n_ats(self):
        return sum(self.ats)

    def pct(self, which="su"):
        w, l, _ = getattr(self, which)
        return w / (w + l) if w + l else None

    def fmt(self, which="su"):
        w, l, p = (int(x) for x in getattr(self, which))
        return f"{w}-{l}" + (f"-{p}" if p else "")

    def avg_margin(self):
        return sum(self.margins) / len(self.margins) if self.margins else None


def side_rows(games, final_only=True):
    """Each game twice, once per team, from that team's perspective."""
    for g in games:
        if final_only and not g["final"]:
            continue
        for home in (True, False):
            t, o = (g["home_team"], g["away_team"]) if home else (g["away_team"], g["home_team"])
            margin = g["result"] if home else -g["result"] if g["result"] is not None else None
            line = None
            if g["spread"] is not None:
                line = g["spread"] if home else -g["spread"]
            ou = (g["total"] - g["total_line"]) if g["final"] and g["total_line"] is not None else None
            yield {
                "g": g, "team": t, "opp": o, "home": home and g.get("location") != "Neutral",
                "coach": g["home_coach"] if home else g["away_coach"],
                "opp_coach": g["away_coach"] if home else g["home_coach"],
                "qb": g["home_qb_name"] if home else g["away_qb_name"],
                "rest": g["home_rest"] if home else g["away_rest"],
                "margin": margin, "line": line,
                "cover": (margin + line) if margin is not None and line is not None else None,
                "ou": ou,
            }


def tally(rows):
    led = Ledger()
    for r in rows:
        led.add(r["margin"], r["cover"], r["ou"])
    return led


def index(games):
    """Per-coach / per-QB / per-team row lists, chronological."""
    by_coach, by_qb, by_team = defaultdict(list), defaultdict(list), defaultdict(list)
    for r in side_rows(sorted(games, key=lambda g: (g["gameday"], g["gametime"] or ""))):
        by_coach[r["coach"]].append(r)
        by_qb[r["qb"]].append(r)
        by_team[r["team"]].append(r)
    return by_coach, by_qb, by_team


def pythagorean(points_for, points_against, games, exp=2.37):
    if not points_for or not points_against:
        return None
    pf, pa = points_for ** exp, points_against ** exp
    return games * pf / (pf + pa)
