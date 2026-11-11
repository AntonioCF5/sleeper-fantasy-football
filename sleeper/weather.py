"""Kickoff-hour weather forecast per NFL stadium (Open-Meteo, free, no key).

ESPN's summary `weather` is the current reading at the stadium, not the
forecast for kickoff, and it has no wind. Wind is what moves totals and
kickers. Open-Meteo gives hourly forecasts up to 16 days out by lat/lon, so
every stadium carries coordinates and a roof type:
  dome         fixed roof (SoFi's canopy counts): weather doesn't play
  retractable  forecast shown, plus a note that the roof can close
  open         forecast is what they play in

curl-based with a file cache, like sleeper/espn.py.
"""

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache" / "weather"
TTL = 3 * 3600

# home team (ESPN code) -> (lat, lon, roof)
STADIUMS = {
    "ARI": (33.5276, -112.2626, "retractable"), "ATL": (33.7554, -84.4009, "retractable"),
    "BAL": (39.2780, -76.6227, "open"), "BUF": (42.7738, -78.7870, "open"),
    "CAR": (35.2258, -80.8528, "open"), "CHI": (41.8623, -87.6167, "open"),
    "CIN": (39.0955, -84.5161, "open"), "CLE": (41.5061, -81.6995, "open"),
    "DAL": (32.7473, -97.0945, "retractable"), "DEN": (39.7439, -105.0201, "open"),
    "DET": (42.3400, -83.0456, "dome"), "GB": (44.5013, -88.0622, "open"),
    "HOU": (29.6847, -95.4107, "retractable"), "IND": (39.7601, -86.1639, "retractable"),
    "JAX": (30.3239, -81.6373, "open"), "KC": (39.0489, -94.4839, "open"),
    "LV": (36.0909, -115.1833, "dome"), "LAC": (33.9535, -118.3392, "dome"),
    "LAR": (33.9535, -118.3392, "dome"), "MIA": (25.9580, -80.2389, "open"),
    "MIN": (44.9737, -93.2577, "dome"), "NE": (42.0909, -71.2643, "open"),
    "NO": (29.9511, -90.0812, "dome"), "NYG": (40.8135, -74.0745, "open"),
    "NYJ": (40.8135, -74.0745, "open"), "PHI": (39.9008, -75.1675, "open"),
    "PIT": (40.4468, -80.0158, "open"), "SF": (37.4030, -121.9700, "open"),
    "SEA": (47.5952, -122.3316, "open"), "TB": (27.9759, -82.5033, "open"),
    "TEN": (36.1665, -86.7713, "open"), "WSH": (38.9078, -76.8645, "open"),
}
# neutral / international sites, matched by a substring of ESPN's venue name
VENUES = {
    "Bernabéu": (40.4531, -3.6883, "retractable"), "Tottenham": (51.6043, -0.0664, "open"),
    "Wembley": (51.5560, -0.2796, "open"), "Olympiastadion": (52.5147, 13.2395, "open"),
    "Allianz Arena": (48.2188, 11.6247, "open"), "Bayern Munich": (48.2188, 11.6247, "open"),  # ESPN: "FC Bayern Munich Stadium" "Azteca": (19.3029, -99.1505, "open"),
    "Banorte": (19.3029, -99.1505, "open"), "Neo Química": (-23.5453, -46.4742, "open"),
    "Melbourne Cricket": (-37.8200, 144.9834, "open"), "Croke Park": (53.3607, -6.2512, "open"),
    "Maracanã": (-22.9121, -43.2302, "open"),
}

# WMO weather codes -> Spanish
_CODES = [((0,), "despejado"), ((1,), "mayormente despejado"), ((2,), "parcialmente nublado"),
          ((3,), "nublado"), ((45, 48), "niebla"), ((51, 53, 55, 56, 57), "llovizna"),
          ((61, 63, 66, 80, 81), "lluvia"), ((65, 67, 82), "lluvia fuerte"),
          ((71, 73, 75, 77, 85, 86), "nieve"), ((95, 96, 99), "tormenta eléctrica")]


def _desc(code):
    return next((d for cs, d in _CODES if code in cs), "")


def _get(url):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{hashlib.sha1(url.encode()).hexdigest()}.json"
    if f.exists() and time.time() - f.stat().st_mtime < TTL:
        try:
            return json.loads(f.read_text())
        except json.JSONDecodeError:
            f.unlink(missing_ok=True)
    out = subprocess.run(["curl", "-s", "--max-time", "20", url], capture_output=True).stdout
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    if "hourly" in data:
        f.write_text(json.dumps(data))
    return data


def site(home, venue=""):
    for k, v in VENUES.items():
        if k.lower() in (venue or "").lower():
            return v
    return STADIUMS.get(home)


def forecast(home, venue, kickoff_iso):
    """Forecast for the kickoff hour: {roof, desc, temp_c, temp_f, wind_kmh, wind_mph,
    gust_kmh, gust_mph, precip, flags, text, tip} or {roof: 'dome', text: 'techado'};
    None when the stadium is unknown or the game is beyond the 16-day horizon."""
    st = site(home, venue)
    if not st:
        return None
    lat, lon, roof = st
    if roof == "dome":
        return {"roof": "dome", "text": "techado", "tip": "Estadio techado: el clima no juega."}
    kick = datetime.fromisoformat(kickoff_iso).astimezone(timezone.utc)
    days = (kick.date() - datetime.now(timezone.utc).date()).days
    if days > 15 or days < -1:
        return None
    day = kick.strftime("%Y-%m-%d")
    d = _get("https://api.open-meteo.com/v1/forecast?"
             f"latitude={lat}&longitude={lon}&timezone=UTC&start_date={day}&end_date={day}"
             "&hourly=temperature_2m,precipitation_probability,wind_speed_10m,wind_gusts_10m,weather_code") or {}
    h = d.get("hourly") or {}
    times = h.get("time") or []
    if not times:
        return None
    # kickoff hour plus the next two: the game is ~3h; report the worst wind and rain of the window
    i = min(range(len(times)), key=lambda k: abs(datetime.fromisoformat(times[k] + "+00:00") - kick))
    win = range(i, min(i + 3, len(times)))
    pick = lambda key, f=max: f((h[key][k] for k in win if h[key][k] is not None), default=None)  # noqa: E731
    t = h["temperature_2m"][i]
    wind, gust, rain = pick("wind_speed_10m"), pick("wind_gusts_10m"), pick("precipitation_probability")
    if gust is not None and wind is not None:
        gust = max(gust, wind)  # window maxima can come from different hours
    code = h["weather_code"][i]
    worst = max((h["weather_code"][k] for k in win if h["weather_code"][k] is not None), default=None)
    # rain/snow in the window only names the sky when it's likely (≥40%); otherwise the rain % speaks for itself
    if worst is not None and worst >= 51 and (rain or 0) >= 40:
        code = worst
    elif code is not None and code >= 51:
        code = 3
    out = {"roof": roof, "desc": _desc(code), "temp_c": round(t) if t is not None else None,
           "temp_f": round(t * 9 / 5 + 32) if t is not None else None,
           "wind_kmh": round(wind) if wind is not None else None, "wind_mph": round(wind / 1.609) if wind is not None else None,
           "gust_kmh": round(gust) if gust is not None else None, "gust_mph": round(gust / 1.609) if gust is not None else None,
           "precip": rain}
    flags = []
    if (wind or 0) >= 24 or (gust or 0) >= 40:   # ~15 mph sustained / 25 mph gusts: passing and kicking suffer
        flags.append("viento")
    if (rain or 0) >= 50 and code is not None and code >= 51:
        flags.append("nieve" if code in (71, 73, 75, 77, 85, 86) else "lluvia")
    if t is not None and t <= 0:
        flags.append("frío")
    out["flags"] = flags
    bits = [f"{out['temp_c']}°C" if t is not None else None, out["desc"] or None,
            f"viento {out['wind_kmh']} km/h" + (f" (ráfagas {out['gust_kmh']})" if gust and gust - (wind or 0) >= 10 else "")
            if wind is not None else None,
            f"{rain}% lluvia" if (rain or 0) >= 10 else None]
    out["text"] = " · ".join(b for b in bits if b)
    out["tip"] = (f"Pronóstico para la hora del partido (Open-Meteo, se actualiza cada 3 h): {out['temp_f']}°F, "
                  f"viento {out['wind_mph']} mph" + (f", ráfagas {out['gust_mph']} mph" if gust else "")
                  + (f", {rain}% de probabilidad de lluvia" if rain is not None else "") + "."
                  + (" Techo retráctil: si llueve o hace frío, lo pueden cerrar." if roof == "retractable" else "")
                  + (" Viento de 24 km/h (15 mph) o más castiga el pase profundo y las patadas." if "viento" in flags else ""))
    return out
