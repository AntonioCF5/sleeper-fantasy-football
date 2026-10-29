#!/usr/bin/env python3
"""Podcast prep app: a local web UI over the weekly podcast data.

Usage: python3 scripts/podcast_app.py [port]      (default 8790)

Pick a game and see everything about it in one place: line and models, team
comparison, coaches and history, fantasy usage, injuries, and that game's
rundown segment. Reads what scripts/podcast_prep.py writes
(reports/<season>/podcast/weekNN/data.json), plus rundown.md and
data/intel/podcast_picks.json at request time, so rundown edits show up on
reload. The "Actualizar" button re-runs podcast_prep.py for the open week.
"""

import json
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
PAGE = Path(__file__).resolve().parent / "podcast_app.html"
PICKS = ROOT / "data" / "intel" / "podcast_picks.json"
REFRESH_LOCK = threading.Lock()


def weeks():
    out = []
    for f in (ROOT / "reports").glob("*/podcast/week*/data.json"):
        season, wk = f.parts[-4], int(f.parent.name[4:])
        out.append({"season": season, "week": wk})
    return sorted(out, key=lambda x: (x["season"], x["week"]), reverse=True)


def week_dir(season, week):
    return ROOT / "reports" / str(season) / "podcast" / f"week{int(week):02d}"


def parse_rundown(path):
    """Split the rundown into per-game segments (keyed AWAY@HOME) and the
    slate-wide sections (cold open, best bets, fantasy, regression, survivor)."""
    if not path.exists():
        return {}, []
    games, sections = {}, []
    cur = None
    for line in path.read_text().splitlines():
        m = re.match(r"^### ([A-Z]{2,3}) @ ([A-Z]{2,3})\b", line)
        if m:
            cur = {"key": f"{m[1]}@{m[2]}", "title": line[4:], "lines": []}
            games[cur["key"]] = cur
            continue
        if line.startswith("## "):
            title = line[3:].strip()
            cur = None if title.lower().startswith("partido por partido") else {"title": title, "lines": []}
            if cur:
                sections.append(cur)
            continue
        if line.startswith("# ") or line.strip() == "---":
            continue
        if cur is not None:
            cur["lines"].append(line)
    for c in list(games.values()) + sections:
        c["md"] = "\n".join(c.pop("lines")).strip()
    return games, sections


def week_payload(season, week):
    d = week_dir(season, week)
    data = json.loads((d / "data.json").read_text())
    games, sections = parse_rundown(d / "rundown.md")
    picks = []
    if PICKS.exists():
        picks = (json.loads(PICKS.read_text()).get("weeks") or {}).get(str(week)) or []
    data["rundown"] = {"games": games, "sections": sections}
    data["picks"] = picks
    data["weeks"] = weeks()
    return data


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        raw = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str))

    def do_GET(self):
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        if url.path in ("/", "/index.html"):
            return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        if url.path == "/api/weeks":
            return self._json(weeks())
        if url.path == "/api/week":
            ws = weeks()
            if not ws:
                return self._json({"error": "No hay datos. Corre python3 scripts/podcast_prep.py"}, 404)
            season, week = q.get("season", ws[0]["season"]), q.get("week", ws[0]["week"])
            try:
                return self._json(week_payload(season, week))
            except FileNotFoundError:
                return self._json({"error": f"No hay datos de la semana {week}"}, 404)
        self._send(404, "not found", "text/plain")

    def do_POST(self):
        url = urlparse(self.path)
        if url.path != "/api/refresh":
            return self._send(404, "not found", "text/plain")
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        if not REFRESH_LOCK.acquire(blocking=False):
            return self._json({"ok": False, "log": "Ya se está actualizando."}, 409)
        try:
            cmd = [sys.executable, str(ROOT / "scripts" / "podcast_prep.py")] + ([q["week"]] if q.get("week") else [])
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=300)
            return self._json({"ok": r.returncode == 0, "log": (r.stdout + r.stderr)[-2000:]},
                              200 if r.returncode == 0 else 500)
        except subprocess.TimeoutExpired:
            return self._json({"ok": False, "log": "Se tardó más de 5 minutos."}, 504)
        finally:
            REFRESH_LOCK.release()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8790
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Podcast app → http://localhost:{port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
