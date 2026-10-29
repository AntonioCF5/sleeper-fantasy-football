"""ESPN public NFL endpoints — schedule, lines, game context, team stats.

Read-only, no auth. curl-based like scripts/survivor_plan.py (ESPN's edge is
fine with curl; urllib gets throttled more). Everything caches to
data/cache/espn/ — finished games never change, so their odds/scoreboards
cache for a week; anything about the upcoming slate refreshes every 3h.

Endpoints:
  site.api  …/scoreboard?week=N      schedule, scores, records, venue
  site.api  …/summary?event=ID       injuries, weather, FPI predictor, leaders
  core.api  …/competitions/ID/odds   DraftKings open/close/current spread,
                                     total, moneyline — also for FINISHED
                                     games, which is what makes ATS/O-U
                                     records computable
  core.api  …/teams/ID/statistics    season team stats (3rd down, red zone,
                                     turnovers, yards/play…)
"""

import hashlib
import json
import subprocess
import time
from pathlib import Path

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache" / "espn"
SITE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"

HOUR = 3600
LIVE_TTL = 3 * HOUR
FINAL_TTL = 7 * 24 * HOUR

# ESPN → Sleeper team codes (the only mismatch).
TO_SLEEPER = {"WSH": "WAS"}

DIVISIONS = {
    "AFC East": ["BUF", "MIA", "NE", "NYJ"],
    "AFC North": ["BAL", "CIN", "CLE", "PIT"],
    "AFC South": ["HOU", "IND", "JAX", "TEN"],
    "AFC West": ["DEN", "KC", "LV", "LAC"],
    "NFC East": ["DAL", "NYG", "PHI", "WSH"],
    "NFC North": ["CHI", "DET", "GB", "MIN"],
    "NFC South": ["ATL", "CAR", "NO", "TB"],
    "NFC West": ["ARI", "LAR", "SF", "SEA"],
}
DIVISION_OF = {t: d for d, ts in DIVISIONS.items() for t in ts}


def _get(url: str, ttl: int):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{hashlib.sha1(url.encode()).hexdigest()}.json"
    if f.exists() and time.time() - f.stat().st_mtime < ttl:
        try:
            return json.loads(f.read_text())
        except json.JSONDecodeError:
            f.unlink(missing_ok=True)
    out = subprocess.run(["curl", "-s", "--max-time", "30", url], capture_output=True).stdout
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    f.write_text(json.dumps(data))
    return data


def current_week():
    d = _get(f"{SITE}/scoreboard", HOUR) or {}
    return (d.get("week") or {}).get("number"), (d.get("season") or {}).get("year")


def scoreboard(week: int, season, final=False):
    url = f"{SITE}/scoreboard?seasontype=2&week={week}&dates={season}"
    return (_get(url, FINAL_TTL if final else LIVE_TTL) or {}).get("events", [])


def summary(event_id):
    return _get(f"{SITE}/summary?event={event_id}", LIVE_TTL) or {}


def odds(event_id, final=False):
    """DraftKings line for one game, or None. Shape:
    {spread: home-perspective (neg = home favored), total, ml_home, ml_away,
     open_spread, open_total, details}."""
    d = _get(f"{CORE}/events/{event_id}/competitions/{event_id}/odds",
             FINAL_TTL if final else LIVE_TTL) or {}
    items = d.get("items") or []
    it = next((i for i in items if (i.get("provider") or {}).get("name") == "DraftKings"),
              items[0] if items else None)
    if not it or it.get("spread") is None:
        return None
    h = it.get("homeTeamOdds") or {}
    a = it.get("awayTeamOdds") or {}

    def _num(x):
        try:
            return float(str(x).replace("+", ""))
        except (TypeError, ValueError):
            return None

    open_spread = _num(((h.get("open") or {}).get("pointSpread") or {}).get("american"))
    open_total = _num(((it.get("open") or {}).get("total") or {}).get("american"))
    return {
        "spread": float(it["spread"]),
        "total": _num(it.get("overUnder")),
        "ml_home": _num(h.get("moneyLine")),
        "ml_away": _num(a.get("moneyLine")),
        "open_spread": open_spread,
        "open_total": open_total,
        "details": it.get("details", ""),
    }


def team_stats(team_id, season):
    """{stat_name: float} flattened across ESPN's categories (first wins)."""
    d = _get(f"{CORE}/seasons/{season}/types/2/teams/{team_id}/statistics", 12 * HOUR) or {}
    flat = {}
    for cat in ((d.get("splits") or {}).get("categories") or []):
        for s in cat.get("stats", []):
            flat.setdefault(f"{cat['name']}.{s['name']}", s.get("value"))
    return flat
