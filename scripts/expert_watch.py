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
        time.sleep(1 + attempt)
    return None


def _load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"seen": {}}


def _save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=1))


def fetch_feed(channel_id):
    """Recent uploads via RSS. Edge-flaky: ~1 in 3 requests 404s, hence retries."""
    out = _curl(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}",
                retries=25, ok=lambda b: b.lstrip().startswith(b"<?xml"))
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
    for key, ch in CHANNELS.items():
        entries = fetch_feed(ch["channel_id"])
        if entries is None:
            print(f"!! feed failed for {ch['name']} (YouTube edge flakiness — retry later)")
            continue
        for e in entries:
            if e["video_id"] not in state["seen"]:
                new.append({**e, "source": key})
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
        vid = args[args.index("--fetch") + 1]
        fetch_one(vid, {}, state)
    elif "--mark" in args:
        vids = args[args.index("--mark") + 1:]
        if vids == ["all"]:
            # everything with a fetched transcript counts as processed
            vids = [f.stem for f in TRANSCRIPT_DIR.glob("*.txt")]
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
