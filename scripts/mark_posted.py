#!/usr/bin/env python3
"""
Record fingerprint(s) as posted so fetch_news.py won't surface them again.

Usage:
    echo '[{"fingerprint": "...", "title": "...", "link": "...", "wp_post_id": 123}]' \
        | python3 scripts/mark_posted.py

Reads a JSON array from stdin (each item must include at least
"fingerprint"), merges it into state/posted.json, trims to the configured
history limit, and writes the file back. The caller is responsible for
committing + pushing state/posted.json afterwards.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_json(path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    settings = load_json(ROOT / "config" / "settings.json", {})
    state_path = ROOT / settings.get("state_file", "state/posted.json")
    limit = settings.get("posted_history_limit", 1000)

    new_entries = json.load(sys.stdin)
    if isinstance(new_entries, dict):
        new_entries = [new_entries]

    state = load_json(state_path, {"posted": []})
    existing = {e["fingerprint"]: e for e in state.get("posted", [])}

    now = datetime.now(timezone.utc).isoformat()
    for entry in new_entries:
        if "fingerprint" not in entry:
            continue
        entry.setdefault("posted_at", now)
        existing[entry["fingerprint"]] = entry

    merged = sorted(existing.values(), key=lambda e: e.get("posted_at", ""), reverse=True)
    merged = merged[:limit]

    state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump({"posted": merged}, f, indent=2)
        f.write("\n")

    print(f"Recorded {len(new_entries)} entries. State now has {len(merged)} total.")


if __name__ == "__main__":
    main()
