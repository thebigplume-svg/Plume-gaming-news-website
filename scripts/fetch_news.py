#!/usr/bin/env python3
"""
Fetch new gaming-news candidates from configured RSS/Atom feeds.

Reads config/sources.json + config/settings.json, filters out items already
posted (tracked in state/posted.json) or older than the configured lookback
window, and prints a JSON array of candidates to stdout — newest first.

This script only gathers raw facts (title, link, source, publish time,
feed-provided description). It does NOT write the article copy itself —
that's left to the agent invoking this script, which should write an
original summary per candidate and attribute + link back to the source
before publishing.

Usage:
    python3 scripts/fetch_news.py [--limit N]
"""
import argparse
import hashlib
import json
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
CONFIG_SOURCES = ROOT / "config" / "sources.json"
CONFIG_SETTINGS = ROOT / "config" / "settings.json"

ATOM_NS = "{http://www.w3.org/2005/Atom}"


def load_json(path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def strip_html(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_link(link):
    if not link:
        return link
    link = link.split("?")[0].split("#")[0]
    return link.rstrip("/")


def item_fingerprint(link, title):
    basis = normalize_link(link) or title or ""
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def parse_date(raw):
    if not raw:
        return None
    raw = raw.strip()
    try:
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def fetch_feed(url, user_agent, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def parse_rss_items(root, source_name):
    items = []
    channel_items = root.findall(".//item")
    for it in channel_items:
        title = strip_html((it.findtext("title") or "").strip())
        link = (it.findtext("link") or "").strip()
        guid = (it.findtext("guid") or link or title).strip()
        desc = strip_html(it.findtext("description") or it.findtext("summary") or "")
        pub = (
            it.findtext("pubDate")
            or it.findtext("{http://purl.org/dc/elements/1.1/}date")
            or ""
        )
        if not title or not link:
            continue
        items.append(
            {
                "title": title,
                "link": link,
                "guid": guid,
                "description": desc[:600],
                "published": pub,
                "source": source_name,
            }
        )
    return items


def parse_atom_items(root, source_name):
    items = []
    for entry in root.findall(f".//{ATOM_NS}entry"):
        title = strip_html((entry.findtext(f"{ATOM_NS}title") or "").strip())
        link_el = entry.find(f"{ATOM_NS}link")
        link = link_el.get("href") if link_el is not None else ""
        guid = (entry.findtext(f"{ATOM_NS}id") or link or title).strip()
        summary = strip_html(
            entry.findtext(f"{ATOM_NS}summary") or entry.findtext(f"{ATOM_NS}content") or ""
        )
        pub = entry.findtext(f"{ATOM_NS}published") or entry.findtext(f"{ATOM_NS}updated") or ""
        if not title or not link:
            continue
        items.append(
            {
                "title": title,
                "link": link,
                "guid": guid,
                "description": summary[:600],
                "published": pub,
                "source": source_name,
            }
        )
    return items


def parse_feed(raw_bytes, source_name):
    try:
        root = ElementTree.fromstring(raw_bytes)
    except ElementTree.ParseError:
        return []
    if root.tag.endswith("feed"):
        return parse_atom_items(root, source_name)
    return parse_rss_items(root, source_name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    sources_cfg = load_json(CONFIG_SOURCES, {"sources": []})
    settings = load_json(
        CONFIG_SETTINGS,
        {"lookback_hours": 30, "max_candidates": 20, "state_file": "state/posted.json",
         "user_agent": "PlumeGamingNewsAgent/1.0"},
    )
    state_path = ROOT / settings.get("state_file", "state/posted.json")
    state = load_json(state_path, {"posted": []})
    seen_fingerprints = {entry["fingerprint"] for entry in state.get("posted", [])}

    lookback_hours = settings.get("lookback_hours", 30)
    cutoff = datetime.now(timezone.utc).timestamp() - lookback_hours * 3600
    limit = args.limit or settings.get("max_candidates", 20)
    user_agent = settings.get("user_agent", "PlumeGamingNewsAgent/1.0")

    all_items = []
    errors = []
    for src in sources_cfg.get("sources", []):
        try:
            raw = fetch_feed(src["url"], user_agent)
            parsed = parse_feed(raw, src["name"])
            for p in parsed:
                p["default_category"] = src.get("default_category", "News")
            all_items.extend(parsed)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            errors.append({"source": src["name"], "error": str(e)})

    candidates = []
    seen_this_run = set()
    for item in all_items:
        fp = item_fingerprint(item["link"], item["title"])
        if fp in seen_fingerprints or fp in seen_this_run:
            continue
        dt = parse_date(item["published"])
        if dt is not None and dt.timestamp() < cutoff:
            continue
        seen_this_run.add(fp)
        item["fingerprint"] = fp
        item["published_parsed"] = dt.isoformat() if dt else None
        candidates.append(item)

    candidates.sort(
        key=lambda x: x["published_parsed"] or "1970-01-01T00:00:00+00:00", reverse=True
    )
    candidates = candidates[:limit]

    print(json.dumps({"candidates": candidates, "errors": errors}, indent=2))


if __name__ == "__main__":
    main()
