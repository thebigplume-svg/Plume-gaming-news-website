#!/usr/bin/env python3
"""
Publish a single article to WordPress via the REST API.

Reads WP_URL, WP_USERNAME, WP_APP_PASSWORD from the environment (never from
files committed to git). Reads the post payload as JSON from stdin:

    {
      "title": "...",
      "content_html": "<p>...</p>",
      "excerpt": "optional short excerpt",
      "category": "News",
      "tags": ["Xbox", "Release Date"],
      "status": "draft",                 // or "publish" — defaults to config
      "source_name": "IGN",
      "source_url": "https://..."
    }

If source_name/source_url are present, an attribution line + link is
appended to the content automatically (do not also hand-write one).

Prints the created post's id, link, and edit link as JSON on success.
"""
import base64
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_json(path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def api_request(base_url, path, auth_header, method="GET", data=None):
    url = f"{base_url.rstrip('/')}/wp-json/wp/v2/{path.lstrip('/')}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", auth_header)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"WordPress API error {e.code} on {method} {path}: {err_body}")


def get_or_create_term(base_url, auth_header, taxonomy, name):
    if not name:
        return None
    results = api_request(
        base_url, f"{taxonomy}?search={urllib.parse.quote(name)}", auth_header
    )
    for r in results:
        if r["name"].lower() == name.lower():
            return r["id"]
    created = api_request(base_url, taxonomy, auth_header, method="POST", data={"name": name})
    return created["id"]


def build_content(content_html, source_name, source_url):
    content = content_html.strip()
    if source_name and source_url:
        content += (
            f'\n<p><em>Source: <a href="{source_url}" target="_blank" '
            f'rel="noopener noreferrer">{source_name}</a></em></p>'
        )
    return content


def main():
    wp_url = os.environ.get("WP_URL")
    wp_user = os.environ.get("WP_USERNAME")
    wp_pass = os.environ.get("WP_APP_PASSWORD")
    if not (wp_url and wp_user and wp_pass):
        raise SystemExit(
            "Missing WP_URL / WP_USERNAME / WP_APP_PASSWORD environment variables. "
            "See README.md for setup instructions."
        )

    payload = json.load(sys.stdin)
    title = payload.get("title")
    content_html = payload.get("content_html")
    if not title or not content_html:
        raise SystemExit("Payload must include 'title' and 'content_html'.")

    settings = load_json(ROOT / "config" / "settings.json", {})
    status = payload.get("status") or settings.get("wp_post_status", "draft")

    token = base64.b64encode(f"{wp_user}:{wp_pass}".encode("utf-8")).decode("utf-8")
    auth_header = f"Basic {token}"

    category_name = payload.get("category") or settings.get("default_category", "News")
    category_id = get_or_create_term(wp_url, auth_header, "categories", category_name)

    tag_ids = []
    for tag_name in payload.get("tags", []):
        tid = get_or_create_term(wp_url, auth_header, "tags", tag_name)
        if tid:
            tag_ids.append(tid)

    post_data = {
        "title": title,
        "content": build_content(
            content_html, payload.get("source_name"), payload.get("source_url")
        ),
        "status": status,
    }
    if payload.get("excerpt"):
        post_data["excerpt"] = payload["excerpt"]
    if category_id:
        post_data["categories"] = [category_id]
    if tag_ids:
        post_data["tags"] = tag_ids

    created = api_request(wp_url, "posts", auth_header, method="POST", data=post_data)

    result = {
        "id": created["id"],
        "status": created["status"],
        "link": created.get("link"),
        "edit_link": f"{wp_url.rstrip('/')}/wp-admin/post.php?post={created['id']}&action=edit",
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
