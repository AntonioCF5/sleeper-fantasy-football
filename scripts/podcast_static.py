#!/usr/bin/env python3
"""Build a self-contained, shareable copy of the podcast app for one week.

    python3 scripts/podcast_static.py [week] [season]

→ reports/<season>/podcast/weekNN/podcast-app-share.html

The live app (podcast_app.py) reads data.json + rundown.md + podcast_picks.json
from a local server. A shared page (a claude.ai artifact) can't: no server, no
remote images, no fetch, and only a plain #name survives in the URL. So this
build takes the same podcast_app.html and:
  - embeds the week's payload (exactly what /api/week returns) as JSON;
  - embeds team logos and the offensive starters' Sleeper headshots as data: URIs
    (every other avatar falls back to initials, logos to the colored team chip);
  - swaps the #/season/week/game/tab router for plain hashes
    (#cartelera, #recap, #general-guion, #cin-atl-fantasy);
  - hides Actualizar and the week picker (one frozen week).
Re-run it after any refresh to republish the artifact.
"""

import base64
import json
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import podcast_app  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SKILL_POS = {"QB", "RB", "WR", "TE"}


def fetch_data_uri(url, mime, px=None):
    out = subprocess.run(["curl", "-sf", "--max-time", "20", url], capture_output=True).stdout
    if not out or len(out) < 200:
        return None
    if px:  # Sleeper's "thumb" is ~45KB; an 88px JPEG is ~3KB and plenty for a 40px avatar (macOS sips)
        with tempfile.TemporaryDirectory() as d:
            src, dst = Path(d) / "in", Path(d) / "out.jpg"
            src.write_bytes(out)
            r = subprocess.run(["sips", "-Z", str(px), "-s", "format", "jpeg", "-s", "formatOptions", "70",
                                str(src), "--out", str(dst)], capture_output=True)
            if r.returncode == 0 and dst.exists():
                out, mime = dst.read_bytes(), "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(out).decode()}"


def images(payload):
    teams = sorted({t for g in payload["games"] for t in (g["sheet"]["away"], g["sheet"]["home"])})
    pids = set()
    for g in payload["games"]:
        for L in (g["sheet"].get("lineups") or {}).values():
            for gr in (L or {}).get("groups") or []:
                for sp in gr["spots"]:
                    x = sp["depth"][sp["start"]]
                    if sp["pos"] in SKILL_POS and x.get("pid"):
                        pids.add(x["pid"])
    logo_url = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/nfl/500/{}.png&h=128&w=128"
    with ThreadPoolExecutor(12) as ex:
        logos = dict(zip(teams, ex.map(lambda t: fetch_data_uri(logo_url.format(t.lower()), "image/png", px=None), teams)))
        heads = dict(zip(pids, ex.map(lambda p: fetch_data_uri(
            f"https://sleepercdn.com/content/nfl/players/thumb/{p}.jpg", "image/jpeg", px=88), pids)))
    return {"logo": {k: v for k, v in logos.items() if v}, "head": {k: v for k, v in heads.items() if v}}


STATIC_ROUTER = r'''
// ---- static build: plain-hash router (#cartelera, #recap, #general-guion, #cin-atl-fantasy)
function parseHash() {
  const h = decodeURIComponent(location.hash.replace(/^#/, "")).toLowerCase();
  const m = h.match(/^([a-z]+)-([a-z]+)-([a-z]+)$/);
  if (m) { const g = (S.games || []).find(x => x.game.toLowerCase() === `${m[1]}@${m[2]}`); if (g) return {game: g.game, tab: m[3]}; }
  if (h.startsWith("general-")) return {game: "cartelera", tab: h.slice(8)};
  return {game: "cartelera", tab: h || "cartelera"};
}
function hashFor(game, tab) {
  if (game && game !== "cartelera") return `#${game.toLowerCase().replace("@", "-")}-${tab}`;
  return tab === "cartelera" || tab === "recap" ? `#${tab}` : `#general-${tab}`;
}
function go(game, tab, replace = false) {
  const h = hashFor(game, tab || (game ? "resumen" : "cartelera"));
  if (replace) { try { history.replaceState(null, "", h); } catch {} route(); }
  else if (location.hash !== h) location.hash = h; else route();
}
async function route() {
  try { if (!S.data) await loadWeek(); } catch (e) { return renderError(e); }
  const h = parseHash();
  const game = h.game && S.byKey[h.game] ? h.game : null;
  S.game = game;
  const valid = (game ? TABS : OV_TABS).map(t => t[0]);
  S.tab = valid.includes(h.tab) ? h.tab : valid[0];
  markNav(); renderView();
  $("#sidebar").classList.remove("open");
}
'''


def build(season, week):
    payload = podcast_app.week_payload(season, week)
    payload["weeks"] = [{"season": season, "week": week}]
    img = images(payload)
    html = podcast_app.PAGE.read_text(encoding="utf-8")

    def sub(old, new, count=1):
        nonlocal html
        assert html.count(old) == count, (html.count(old), old[:80])
        html = html.replace(old, new)

    # data comes from the page, not the server
    sub('''async function api(path, opts) {
  const r = await fetch(path, opts);''', '''async function api(path, opts) {
  if (window.__DATA__) return window.__DATA__;
  const r = await fetch(path, opts);''')
    # images: embedded data URIs only (remote images are blocked in an artifact)
    sub('src="https://a.espncdn.com/i/teamlogos/nfl/500/${t.toLowerCase()}.png"',
        'src="${(window.__IMG__?.logo || {})[t] || "data:,"}"')
    sub("const src = x.pid ? `https://sleepercdn.com/content/nfl/players/thumb/${x.pid}.jpg` : x.head;",
        "const src = (window.__IMG__?.head || {})[x.pid] || null;")
    # router: replace the three functions
    a = html.index("function parseHash() {")
    b = html.index('window.addEventListener("hashchange", route);')
    html = html[:a] + STATIC_ROUTER.strip() + "\n" + html[b:]
    # one frozen week: no refresh, no week picker
    sub("</style>", "#refreshBtn, #weekSel { display: none !important; }\n</style>")
    blob = json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":")).replace("</", "<\\/")
    iblob = json.dumps(img, separators=(",", ":"))
    sub("<script>\n\"use strict\";", f"<script>window.__DATA__ = {blob};\nwindow.__IMG__ = {iblob};</script>\n<script>\n\"use strict\";")
    sub("<title>Podcast NFL · Preparación</title>", f"<title>Podcast NFL · Semana {week}</title>")
    dest = ROOT / "reports" / str(season) / "podcast" / f"week{int(week):02d}" / "podcast-app-share.html"
    dest.write_text(html, encoding="utf-8")
    print(f"→ {dest}  ({dest.stat().st_size / 1e6:.1f} MB · {len(img['logo'])} logos · {len(img['head'])} fotos)")
    return dest


if __name__ == "__main__":
    ws = podcast_app.weeks()
    week = int(sys.argv[1]) if len(sys.argv) > 1 else ws[0]["week"]
    season = sys.argv[2] if len(sys.argv) > 2 else next(w["season"] for w in ws if w["week"] == week)
    build(season, week)
