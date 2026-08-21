"""Sleeper API client. Read-only public API, no auth required.

Docs: https://docs.sleeper.com  (plus undocumented projections/stats endpoints).
All requests are cached to data/cache/ with per-endpoint TTLs to stay well
under Sleeper's 1000 req/min limit and to avoid re-downloading the ~5MB
players dump.
"""

import gzip
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.sleeper.app"
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"

HOUR = 3600
DAY = 24 * HOUR


def _fetch(url: str, ttl: int):
    """GET with file cache. ttl=0 disables caching.

    Sleeper returns HTTP 404 (not an empty body) for some list endpoints
    when there's simply nothing yet — e.g. draft picks before any pick has
    been made. Treat that as "no data" (None) rather than an error; callers
    already do `get_x(...) or []`/`or {}`.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(url.encode()).hexdigest()
    path = CACHE_DIR / f"{key}.json.gz"
    if ttl and path.exists() and time.time() - path.stat().st_mtime < ttl:
        with gzip.open(path, "rt") as f:
            return json.load(f)
    req = urllib.request.Request(url, headers={"User-Agent": "sleeper-ff-toolkit"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    with gzip.open(path, "wt") as f:
        json.dump(data, f)
    return data


def _v1(path: str, ttl: int = 5 * 60):
    return _fetch(f"{BASE}/v1/{path}", ttl)


# ---------------------------------------------------------------- core


def get_state():
    """Current NFL season/week. {'season': '2026', 'week': 2, 'season_type': 'pre', ...}"""
    return _v1("state/nfl", ttl=HOUR)


def get_user(username_or_id: str):
    return _v1(f"user/{username_or_id}", ttl=DAY)


def get_user_leagues(user_id: str, season: str):
    return _v1(f"user/{user_id}/leagues/nfl/{season}", ttl=HOUR)


def get_league(league_id: str):
    return _v1(f"league/{league_id}", ttl=HOUR)


def get_rosters(league_id: str):
    return _v1(f"league/{league_id}/rosters", ttl=15 * 60)


def get_league_users(league_id: str):
    return _v1(f"league/{league_id}/users", ttl=HOUR)


def get_matchups(league_id: str, week: int):
    return _v1(f"league/{league_id}/matchups/{week}", ttl=15 * 60)


def get_transactions(league_id: str, week: int):
    return _v1(f"league/{league_id}/transactions/{week}", ttl=15 * 60)


def get_traded_picks(league_id: str):
    return _v1(f"league/{league_id}/traded_picks", ttl=HOUR)


def get_playoff_bracket(league_id: str, bracket: str = "winners_bracket"):
    return _v1(f"league/{league_id}/{bracket}", ttl=HOUR)


# ---------------------------------------------------------------- drafts


def get_league_drafts(league_id: str):
    return _v1(f"league/{league_id}/drafts", ttl=HOUR)


def get_draft(draft_id: str):
    return _v1(f"draft/{draft_id}", ttl=15 * 60)


def get_draft_picks(draft_id: str, ttl: int = 5 * 60):
    """ttl=0 for live drafts — every call hits the API fresh."""
    return _v1(f"draft/{draft_id}/picks", ttl=ttl)


# ---------------------------------------------------------------- players


def get_players():
    """Full NFL player dump keyed by player_id. ~5MB; cached 24h."""
    return _v1("players/nfl", ttl=DAY)


def get_trending(kind: str = "add", lookback_hours: int = 24, limit: int = 50):
    """kind: 'add' or 'drop'. Returns [{'player_id': ..., 'count': ...}]."""
    return _v1(
        f"players/nfl/trending/{kind}?lookback_hours={lookback_hours}&limit={limit}",
        ttl=HOUR,
    )


# ------------------------------------------------- projections & stats
# Undocumented but stable endpoints used by the Sleeper app itself.


def get_week_projections(season: str, week: int, positions=("QB", "RB", "WR", "TE", "K", "DEF")):
    """List of {player_id, stats: {granular projected stat line}, player: {...}}."""
    qs = "&".join(f"position[]={p}" for p in positions)
    return _fetch(
        f"{BASE}/projections/nfl/{season}/{week}?season_type=regular&{qs}&order_by=pts_half_ppr",
        ttl=6 * HOUR,
    )


def get_season_projections(season: str, positions=("QB", "RB", "WR", "TE", "K", "DEF")):
    """Full-season projections incl. ADP fields (adp_ppr, adp_half_ppr, adp_2qb, ...)."""
    qs = "&".join(f"position[]={p}" for p in positions)
    return _fetch(
        f"{BASE}/projections/nfl/{season}?season_type=regular&{qs}&order_by=adp_half_ppr",
        ttl=DAY,
    )


def get_season_stats(season: str, positions=("QB", "RB", "WR", "TE", "K", "DEF")):
    """Full-season actual stats (incl. gms_active) — durability signal."""
    qs = "&".join(f"position[]={p}" for p in positions)
    return _fetch(f"{BASE}/stats/nfl/{season}?season_type=regular&{qs}", ttl=DAY)


def get_week_stats(season: str, week: int):
    """Actual stats for a completed week, dict keyed by player_id."""
    return _fetch(f"{BASE}/v1/stats/nfl/regular/{season}/{week}", ttl=7 * DAY)


def get_player_week_stats(player_id: str, season: str):
    """Weekly stat lines for one player across a season, keyed by week."""
    return _fetch(
        f"{BASE}/stats/nfl/player/{player_id}?season_type=regular&season={season}&grouping=week",
        ttl=DAY,
    )
