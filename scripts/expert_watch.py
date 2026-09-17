#!/usr/bin/env python3
"""Expert-source watcher: The Fantasy Footballers + Sal Vetri (YouTube).

Detects new videos and fetches transcripts so Claude can distill them into
data/intel/expert_takes.json during weekly analysis sessions. Zero pip
dependencies — YouTube blocks urllib's HTTP/1.1 on some endpoints and the
feed endpoint is edge-flaky, so all HTTP goes through curl with retries.

Usage:
  python3 scripts/expert_watch.py --check        # list unprocessed videos
  python3 scripts/expert_watch.py --fetch-new    # transcripts for all unprocessed
  python3 scripts/expert_watch.py --fetch VID    # transcript for one video
  python3 scripts/expert_watch.py --mark VID...  # mark videos processed
                                                 # (after takes are distilled)

The analysis step is deliberately NOT automated code: Claude reads the
transcripts, extracts actionable takes, and reconciles them against our
boards under the rules in CLAUDE.md ("Expert layer").
"""

import json
import re
import subprocess
import sys
import time
import html
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "data" / "intel" / "expert_state.json"
TRANSCRIPT_DIR = ROOT / "data" / "cache" / "transcripts"

CHANNELS = {
    "sal-vetri": {
        "name": "Sal Vetri",
        "channel_id": "UC6oJruhkkXrws3HWqPfMHJw",
    },
    "fantasy-footballers": {
        "name": "The Fantasy Footballers",
        "channel_id": "UC-No2ITxJsNt50oJQ3fLmUA",
    },
}

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _curl(url, post_json=None, retries=1, ok=lambda b: True):
    """curl wrapper (HTTP/2 + consent cookies); retries flaky endpoints."""
    cmd = ["curl", "-s", "--max-time", "45", "-H", f"User-Agent: {UA}",
           "-b", "CONSENT=YES+1; SOCS=CAI", url]
    if post_json is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(post_json)]
    for attempt in range(retries):
        out = subprocess.run(cmd, capture_output=True).stdout
        if out and ok(out):
            return out
        # Backoff capped at 5s: uncapped linear growth made a full 25-retry
        # cycle sleep 5.4 min (24 min worst case with curl timeouts) per
        # channel, long enough for a scheduled run to be abandoned mid-fetch.
        # Capped, the same 25 attempts spread over ~2 min and actually finish.
        time.sleep(min(1 + attempt, 5))
    return None


def _load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"seen": {}}


def _save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=1))


# How each channel's list was obtained on this run ("rss" | "innertube"),
# so check() can report a fallback instead of a silent success.
FEED_VIA = {}


def _fetch_feed_rss(channel_id):
    """Recent uploads via RSS (~15 newest). The RSS edge is flaky — and on
    2026-09-07/13/16 it 404'd or 500'd for BOTH channels for the whole
    9pm run window, 25 retries deep — so this is no longer the only path."""
    out = _curl(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}",
                retries=10, ok=lambda b: b.lstrip().startswith(b"<?xml"))
    if not out:
        return None
    ns = {"a": "http://www.w3.org/2005/Atom",
          "yt": "http://www.youtube.com/xml/schemas/2015"}
    root = ET.fromstring(out)
    entries = []
    for e in root.findall("a:entry", ns):
        entries.append({
            "video_id": e.find("yt:videoId", ns).text,
            "title": e.find("a:title", ns).text,
            "published": e.find("a:published", ns).text[:10],
        })
    return entries


def _relative_date(text):
    """'20 hours ago' / '3 days ago' / 'Streamed 2 weeks ago' → YYYY-MM-DD
    (approximate; InnerTube gives relative dates only)."""
    import datetime as _dt
    m = re.search(r"(\d+)\s+(minute|hour|day|week|month|year)s?\s+ago", text or "")
    today = _dt.date.today()
    if not m:
        return today.isoformat()
    n, unit = int(m.group(1)), m.group(2)
    days = {"minute": 0, "hour": 0, "day": 1, "week": 7, "month": 30, "year": 365}[unit] * n
    return (today - _dt.timedelta(days=days)).isoformat()


def _innertube_browse(channel_id, params):
    body = {"context": {"client": {"clientName": "WEB",
                                   "clientVersion": "2.20240101.00.00"}},
            "browseId": channel_id, "params": params}
    out = _curl("https://www.youtube.com/youtubei/v1/browse", post_json=body,
                retries=3, ok=lambda b: b.lstrip().startswith(b"{"))
    return json.loads(out) if out else None


def _fetch_feed_innertube(channel_id):
    """Fallback catalogue via the InnerTube browse API — the backend the
    YouTube web app itself uses, independent of the RSS edge. Videos tab
    (30 newest, relative dates) + Shorts tab (no dates; capped to the 8
    newest so a fallback night doesn't dredge up months of old shorts the
    RSS window never showed us)."""
    entries = []
    d = _innertube_browse(channel_id, "EgZ2aWRlb3PyBgQKAjoA")  # Videos tab
    if d:
        def walk(o):
            if isinstance(o, dict):
                if "lockupViewModel" in o:
                    lv = o["lockupViewModel"]
                    md = lv.get("metadata", {}).get("lockupMetadataViewModel", {})
                    rows = (md.get("metadata", {}).get("contentMetadataViewModel", {})
                            .get("metadataRows", []))
                    parts = [p.get("text", {}).get("content", "") for r in rows
                             for p in r.get("metadataParts", [])]
                    when = next((x for x in parts if "ago" in x), "")
                    if lv.get("contentId") and md.get("title", {}).get("content"):
                        entries.append({"video_id": lv["contentId"],
                                        "title": md["title"]["content"],
                                        "published": _relative_date(when)})
                for x in o.values():
                    walk(x)
            elif isinstance(o, list):
                for x in o:
                    walk(x)
        walk(d)
    d = _innertube_browse(channel_id, "EgZzaG9ydHPyBgUKA5oBAA%3D%3D")  # Shorts tab
    shorts = []
    if d:
        def walk_s(o):
            if isinstance(o, dict):
                if "shortsLockupViewModel" in o:
                    s = o["shortsLockupViewModel"]
                    vid = ((s.get("onTap", {}).get("innertubeCommand", {})
                            .get("reelWatchEndpoint", {}) or {}).get("videoId"))
                    title = s.get("overlayMetadata", {}).get("primaryText", {}).get("content")
                    if vid and title:
                        shorts.append({"video_id": vid, "title": title,
                                       "published": time.strftime("%Y-%m-%d")})
                for x in o.values():
                    walk_s(x)
            elif isinstance(o, list):
                for x in o:
                    walk_s(x)
        walk_s(d)
    # Only what the RSS window would plausibly have shown: the Videos tab
    # goes 30 deep and dredges up preseason uploads that predate this
    # system's first run (never "seen") — in-season, anything older than
    # 10 days is stale, not new.
    import datetime as _dt
    cutoff = (_dt.date.today() - _dt.timedelta(days=10)).isoformat()
    entries = [e for e in entries if e["published"] >= cutoff]
    entries += shorts[:8]
    return entries or None


def fetch_feed(channel_id):
    """Recent uploads: RSS first (exact dates), InnerTube browse if the RSS
    edge is down. Records which path worked in FEED_VIA."""
    entries = _fetch_feed_rss(channel_id)
    if entries is not None:
        FEED_VIA[channel_id] = "rss"
        return entries
    entries = _fetch_feed_innertube(channel_id)
    if entries is not None:
        FEED_VIA[channel_id] = "innertube"
        return entries
    return None


def fetch_transcript(video_id):
    """Caption track via InnerTube (ANDROID client returns unsigned URLs),
    then parse the XML timedtext into plain text."""
    body = {"context": {"client": {"clientName": "ANDROID",
                                   "clientVersion": "20.10.38"}},
            "videoId": video_id}
    out = _curl("https://www.youtube.com/youtubei/v1/player",
                post_json=body, retries=3,
                ok=lambda b: b.lstrip().startswith(b"{"))
    if not out:
        return None, "player request failed"
    d = json.loads(out)
    tracks = ((d.get("captions") or {})
              .get("playerCaptionsTracklistRenderer", {})
              .get("captionTracks", []))
    if not tracks:
        return None, f"no captions (status: {d.get('playabilityStatus', {}).get('status')})"
    # prefer human-made English track over auto-generated (asr)
    tracks.sort(key=lambda t: (t.get("languageCode") != "en",
                               t.get("kind") == "asr"))
    xml_bytes = _curl(tracks[0]["baseUrl"], retries=3,
                      ok=lambda b: b.lstrip().startswith(b"<?xml"))
    if not xml_bytes:
        return None, "caption download failed"
    root = ET.fromstring(xml_bytes)
    parts = [t.strip() for p in root.iter("p") for t in ["".join(p.itertext())] if t.strip()]
    return html.unescape(" ".join(parts)), None


def check(state, quiet=False):
    new = []
    health = state.setdefault("feed_health", {})
    for key, ch in CHANNELS.items():
        entries = fetch_feed(ch["channel_id"])
        if entries is None:
            # Record the miss so consecutive failures are visible across runs
            # instead of depending on someone noticing an absent section.
            h = health.setdefault(key, {})
            h["consecutive_failures"] = h.get("consecutive_failures", 0) + 1
            h["last_failure"] = time.strftime("%Y-%m-%d")
            n = h["consecutive_failures"]
            print(f"!! feed failed for {ch['name']} — {n} consecutive miss(es); "
                  f"last success {h.get('last_success', 'unknown')}. Nothing was "
                  "marked processed, so the next successful run catches up "
                  "automatically (RSS carries ~15 uploads).")
            if n >= 3:
                print(f"!! {ch['name']} has now missed {n} runs in a row — "
                      "investigate the feed/channel_id rather than retrying.")
            _save_state(state)
            continue
        h = health.setdefault(key, {})
        if h.get("consecutive_failures"):
            print(f"** {ch['name']} feed recovered after "
                  f"{h['consecutive_failures']} miss(es).")
        h["consecutive_failures"] = 0
        h["last_success"] = time.strftime("%Y-%m-%d")
        via = FEED_VIA.get(ch["channel_id"], "rss")
        h["via"] = via
        if via == "innertube":
            h["rss_failures"] = h.get("rss_failures", 0) + 1
            print(f"** {ch['name']}: RSS edge down — catalogue recovered via "
                  f"InnerTube browse ({len(entries)} items; dates approximate, "
                  f"shorts capped at 8). RSS misses so far: {h['rss_failures']}.")
        else:
            h["rss_failures"] = 0
        _save_state(state)
        fresh = [e for e in entries if e["video_id"] not in state["seen"]]
        # YouTube RSS only carries the latest ~15 uploads. If EVERY entry is
        # new despite prior runs, older videos may have scrolled out of the
        # window since the last successful run — flag it instead of missing
        # them silently.
        if state["seen"] and entries and len(fresh) == len(entries):
            print(f"!! {ch['name']}: all {len(entries)} feed entries are new — "
                  "the RSS window (~15) may have dropped older uploads since "
                  "the last run; check the channel page for anything missed.")
        new.extend({**e, "source": key} for e in fresh)
    if not quiet:
        if not new:
            print("No unprocessed videos.")
        for e in sorted(new, key=lambda x: x["published"]):
            print(f"[{e['source']}] {e['published']} {e['video_id']}  {e['title']}")
    return new


def fetch_one(video_id, meta, state):
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    path = TRANSCRIPT_DIR / f"{video_id}.txt"
    if path.exists():
        print(f"cached: {path}")
        return True
    text, err = fetch_transcript(video_id)
    if text is None:
        print(f"!! {video_id}: {err}")
        return False
    header = (f"# {meta.get('title', video_id)}\n"
              f"# source: {meta.get('source', '?')} | published: {meta.get('published', '?')}"
              f" | https://youtu.be/{video_id}\n\n")
    path.write_text(header + text)
    print(f"saved: {path} ({len(text.split())} words)")
    return True


def main():
    args = sys.argv[1:]
    state = _load_state()
    if "--check" in args or not args:
        check(state)
    elif "--fetch-new" in args:
        for e in check(state, quiet=True):
            fetch_one(e["video_id"], e, state)
    elif "--fetch" in args:
        i = args.index("--fetch") + 1
        if i >= len(args):
            sys.exit("--fetch needs a video id")
        fetch_one(args[i], {}, state)
    elif "--mark" in args:
        vids = args[args.index("--mark") + 1:]
        if vids == ["all"]:
            # everything with a fetched transcript counts as processed
            vids = [f.stem for f in TRANSCRIPT_DIR.glob("*.txt")]
        if not vids:
            sys.exit("--mark needs video id(s) or 'all'")
        # A typo'd id marked as processed becomes permanently invisible to
        # --check — refuse ids with no fetched transcript.
        missing = [v for v in vids if not (TRANSCRIPT_DIR / f"{v}.txt").exists()]
        if missing:
            sys.exit("refusing to mark ids with no fetched transcript "
                     f"(typo would hide the video forever): {' '.join(missing)}")
        new = {e["video_id"]: e for e in check(state, quiet=True)}
        for v in vids:
            meta = new.get(v, {})
            state["seen"][v] = {**meta, "processed": time.strftime("%Y-%m-%d")}
        _save_state(state)
        print(f"marked {len(vids)} processed")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
