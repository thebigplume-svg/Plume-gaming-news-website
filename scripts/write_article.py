#!/usr/bin/env python3
"""
Write one article as a content file for the Next.js site.

Reads a JSON payload from stdin:

    {
      "title": "...",
      "dek": "one-sentence summary shown on cards",
      "body": ["paragraph one", "paragraph two", ...],
      "category": "News",
      "tags": ["Xbox", "Release Date"],
      "source_name": "IGN",
      "source_url": "https://...",
      "published_at": "2026-08-18T12:00:00Z"   // optional, defaults to now
    }

Writes content/news/<slug>.json, where <slug> is derived from the title
(and de-duplicated if it already exists). Prints the created slug and path
as JSON on success. This script only writes a file — committing, pushing,
and opening a PR for review is the calling agent's job (see README.md).
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEWS_DIR = ROOT / "content" / "news"


def slugify(title):
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug[:80].rstrip("-")


def unique_slug(base):
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    slug = base
    n = 2
    while (NEWS_DIR / f"{slug}.json").exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


def main():
    payload = json.load(sys.stdin)

    required = ["title", "dek", "body", "category", "source_name", "source_url"]
    missing = [f for f in required if not payload.get(f)]
    if missing:
        raise SystemExit(f"Payload missing required field(s): {', '.join(missing)}")

    slug = unique_slug(slugify(payload["title"]))
    article = {
        "slug": slug,
        "title": payload["title"],
        "dek": payload["dek"],
        "body": payload["body"],
        "category": payload["category"],
        "tags": payload.get("tags", []),
        "source_name": payload["source_name"],
        "source_url": payload["source_url"],
        "published_at": payload.get(
            "published_at", datetime.now(timezone.utc).isoformat()
        ),
    }

    out_path = NEWS_DIR / f"{slug}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(article, f, indent=2)
        f.write("\n")

    print(json.dumps({"slug": slug, "path": str(out_path.relative_to(ROOT))}, indent=2))


if __name__ == "__main__":
    main()
