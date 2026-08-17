# Plume Gaming News Agent

Automation that keeps the news section of **plumegaming.com** (WordPress, hosted
on Bluehost) current: it pulls headlines from major gaming outlets, writes an
original short summary with attribution for each, and creates them as
**drafts** in WordPress via the REST API for review before anything goes live.

This repo does not run the website itself — WordPress does that. This repo is
just the news-gathering + publishing pipeline, plus a recurring schedule that
runs it.

## How it works

```
scripts/fetch_news.py   → pulls RSS/Atom feeds (config/sources.json),
                           filters out anything already posted or older
                           than the lookback window, prints candidate
                           stories as JSON.

  (the agent writes a short original summary + picks category/tags
   for each candidate it decides to run with)

scripts/post_to_wp.py   → takes one article as JSON on stdin, creates it
                           as a WordPress post (draft by default) via the
                           REST API, auto-appends a "Source: <outlet>" link.

scripts/mark_posted.py  → records which stories were handled in
                           state/posted.json so they're never re-posted.
```

Nothing here scrapes or republishes full articles — `fetch_news.py` only
reads the title/link/short description each outlet already publishes in its
own RSS feed. The actual article text posted to WordPress is a fresh summary
plus a clearly labeled link back to the original source. Keep it that way;
posting scraped full-text is both a copyright problem and against most
outlets' terms of service.

## One-time setup

### 1. Create a WordPress Application Password

Do **not** use your main WordPress login password for this.

1. Log in to `https://plumegaming.com/wp-admin`
2. Go to **Users → Profile** (your own user)
3. Scroll to **Application Passwords**
4. Name it `news-agent`, click **Add New Application Password**
5. Copy the generated password immediately (spaces included) — WordPress
   only shows it once.

You need three values afterwards:
- `WP_URL` — `https://plumegaming.com`
- `WP_USERNAME` — your WordPress username (not email)
- `WP_APP_PASSWORD` — the generated password from step 4

The WordPress user needs at least the **Author** role (Editor if you want it
able to set categories/tags that don't exist yet).

### 2. Set those as environment variables (not files)

These must **never** be committed to git. Set `WP_URL`, `WP_USERNAME`, and
`WP_APP_PASSWORD` as environment variables on this Claude Code environment
("plumegaming website") via the environment settings in Claude Code on the
web — see https://code.claude.com/docs/en/claude-code-on-the-web. Every
scheduled run of this agent uses that same environment, so it only needs to
be set once.

### 3. Allow outbound network access to the news sources + WordPress

This environment's network policy currently blocks outbound requests to
external sites by default (confirmed while building this: RSS pulls to IGN,
Polygon, Kotaku, PC Gamer, etc. all came back `403` from the egress proxy —
an org policy denial, not a bug in these scripts). Before the schedule can
actually fetch news or reach your site, the environment's network policy
needs to allow HTTPS to:

- `plumegaming.com` (your WordPress REST API)
- the feed domains in `config/sources.json` (ign.com, polygon.com,
  kotaku.com, pcgamer.com, eurogamer.net, gamespot.com,
  rockpapershotgun.com, vg247.com, gamerant.com, destructoid.com)

Adjust this in the environment's network policy settings (Claude Code on the
web → environment settings). Once updated, re-run `python3
scripts/fetch_news.py` from a session in this environment to confirm it
returns candidates instead of 403 errors.

## Configuration

- `config/sources.json` — which RSS feeds to pull, and each one's default
  WordPress category. Add/remove outlets freely.
- `config/settings.json` — how far back to look (`lookback_hours`), how many
  candidates to fetch per run (`max_candidates`), how many articles to
  actually publish per run (`articles_per_run`), and whether posts land as
  `draft` or `publish` (`wp_post_status`).

To switch from draft review to fully autonomous publishing once you trust
the output, change `wp_post_status` in `config/settings.json` from `"draft"`
to `"publish"`.

## Running it manually

```bash
# 1. See what's new
python3 scripts/fetch_news.py

# 2. For each candidate you want to run with, write a short (3-5 sentence)
#    original summary + pick a category/tags, then:
echo '{
  "title": "...",
  "content_html": "<p>...</p>",
  "category": "News",
  "tags": ["PS5"],
  "source_name": "IGN",
  "source_url": "https://..."
}' | python3 scripts/post_to_wp.py

# 3. Mark it posted so it's not re-fetched next run
echo '[{"fingerprint": "<from step 1 output>", "title": "...", "link": "...", "wp_post_id": <id from step 2>}]' \
  | python3 scripts/mark_posted.py

# 4. Commit the state file so the dedup log persists
git add state/posted.json && git commit -m "Record posted articles" && git push
```

## Running it on a schedule

This is wired up as a recurring Claude Code Routine (~every 4 hours) that
performs the manual steps above automatically for `articles_per_run` stories
per run, using the writing judgment of the agent to summarize each story and
choose categories/tags, then commits and pushes the updated dedup log.
It will silently do nothing if there are no new candidates. It cannot
succeed until the two setup steps above (env vars + network policy) are
complete — until then, runs will fail at the fetch or publish step and that
failure is worth checking on.

## Editorial policy baked into the automation

- **Draft-first**: posts are created as WordPress drafts, not published live,
  until you flip `wp_post_status` to `"publish"` in settings.
- **Attribution required**: every post links back to its original source;
  the agent is instructed not to omit this.
- **No duplicate coverage**: `state/posted.json` prevents the same story
  being posted twice, even across outlets covering the same news (the agent
  checks candidate titles for close duplicates before picking which stories
  to run).
