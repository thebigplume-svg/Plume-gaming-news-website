#!/usr/bin/env python3
"""
Pull finished clips from OpusClip and make a thumbnail for each one.

    export OPUSCLIP_API_KEY=...        # OpusClip dashboard -> API key (bottom-left)
    python3 thumbnails/opusclip_thumbnails.py <project id or project URL> [more ...]

For every clip in each project this:
  1. downloads the clip video (skipped if already downloaded),
  2. uses the clip's OpusClip title as the headline,
  3. runs the normal thumbnail pipeline (make_thumbnails.py) on it.

Output (default ./opusclip/):
    opusclip/<project id>/<clip>.mp4
    opusclip/<project id>/thumbnails/<clip>.jpg
    opusclip/<project id>/titles.json   <- edit a headline/badge here, re-run with --force

The project ID is in the URL when you open a project in the OpusClip web
app; you can paste the whole URL. Uses only the Python standard library on
top of what make_thumbnails.py already needs.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
API_BASE = os.environ.get("OPUSCLIP_API_BASE", "https://api.opus.pro")

# Field names vary a little between API versions; try these in order.
TITLE_KEYS = ("title", "clipTitle", "name")
VIDEO_KEYS = ("uriForExport", "exportUri", "uriForPreview", "videoUrl", "url")
ID_KEYS = ("id", "clipId", "curationId")


def api_key() -> str:
    key = os.environ.get("OPUSCLIP_API_KEY", "").strip()
    if not key:
        env = HERE / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("OPUSCLIP_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"\'')
    if not key:
        raise SystemExit(
            "No OpusClip API key. Get one from the OpusClip dashboard (bottom-left -> API),\n"
            "then:  export OPUSCLIP_API_KEY=your_key   (or put OPUSCLIP_API_KEY=... in thumbnails/.env)"
        )
    return key


def project_id(arg: str) -> str:
    """Accept a bare ID or any OpusClip URL that contains one."""
    arg = arg.strip()
    if "://" not in arg:
        return arg
    u = urllib.parse.urlparse(arg)
    q = urllib.parse.parse_qs(u.query)
    for k in ("id", "projectId", "project_id", "pid"):
        if q.get(k):
            return q[k][0]
    parts = [p for p in u.path.split("/") if p]
    if parts:
        return parts[-1]
    raise SystemExit(f"couldn't find a project ID in {arg}")


def get_json(path: str, key: str, params: dict) -> object:
    url = f"{API_BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "User-Agent": "plume-thumbnails/1.0",
    })
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if e.code == 429 and attempt < 4:      # rate limited: back off and retry
                time.sleep(int(e.headers.get("Retry-After") or 2 ** (attempt + 2)))
                continue
            if e.code in (401, 403):
                raise SystemExit(f"OpusClip rejected the API key ({e.code}). Check OPUSCLIP_API_KEY "
                                 f"and that your plan includes API access.\n{body}")
            raise SystemExit(f"OpusClip API error {e.code} for {path}: {body}")
        except urllib.error.URLError as e:
            raise SystemExit(f"Couldn't reach OpusClip at {API_BASE} ({e.reason}). Check your internet connection.")
    raise SystemExit("OpusClip API kept rate-limiting; try again in a minute.")


def as_list(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for k in ("data", "clips", "items", "results"):
            v = payload.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                return as_list(v)
    return []


def fetch_clips(pid: str, key: str) -> list[dict]:
    payload = get_json("/api/exportable-clips", key, {"q": "findByProjectId", "projectId": pid})
    return as_list(payload)


def first(d: dict, keys) -> str | None:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def slug(text: str, fallback: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60].rstrip("-")
    return s or fallback


def download(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "plume-thumbnails/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.replace(dest)


def sync_project(pid: str, key: str, root: Path, badge: str | None) -> Path:
    folder = root / pid
    folder.mkdir(parents=True, exist_ok=True)
    titles_path = folder / "titles.json"
    titles = json.loads(titles_path.read_text()) if titles_path.exists() else {}

    clips = fetch_clips(pid, key)
    if not clips:
        print(f"  project {pid}: no finished clips yet (still processing, expired, or wrong ID)")
        return folder
    print(f"  project {pid}: {len(clips)} clip(s)")

    for n, clip in enumerate(clips, 1):
        cid = first(clip, ID_KEYS) or str(n)
        title = first(clip, TITLE_KEYS) or f"Clip {n}"
        video_url = first(clip, VIDEO_KEYS)
        name = f"{n:02d}-{slug(title, cid)}.mp4"
        dest = folder / name
        # keep any headline/badge you already edited in titles.json
        titles.setdefault(name, {"title": title, **({"badge": badge} if badge else {}),
                                 "opusclip_id": cid})
        if dest.exists():
            continue
        if not video_url:
            print(f"    ! {title}: no download URL in API response, skipped")
            continue
        print(f"    ↓ {name}")
        try:
            download(video_url, dest)
        except Exception as e:
            print(f"    ! {title}: download failed ({e})", file=sys.stderr)

    titles_path.write_text(json.dumps(titles, indent=2, ensure_ascii=False) + "\n")
    return folder


def main() -> None:
    ap = argparse.ArgumentParser(description="Make thumbnails for your OpusClip clips.")
    ap.add_argument("projects", nargs="+", help="OpusClip project IDs or project URLs")
    ap.add_argument("-o", "--out", default="opusclip", help="where to put clips + thumbnails (default ./opusclip)")
    ap.add_argument("--badge", help='sticker on every thumbnail, e.g. "NEW"')
    ap.add_argument("--force", action="store_true", help="re-make existing thumbnails")
    ap.add_argument("--download-only", action="store_true", help="just fetch clips + titles, no thumbnails")
    args = ap.parse_args()

    key = api_key()
    root = Path(args.out).expanduser().resolve()
    for p in args.projects:
        pid = project_id(p)
        folder = sync_project(pid, key, root, args.badge)
        if args.download_only:
            continue
        cmd = [sys.executable, str(HERE / "make_thumbnails.py"), str(folder)]
        if args.force:
            cmd.append("--force")
        subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
