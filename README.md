# Plume Gaming News

A gaming news site with an automated agent that keeps it current: it pulls
headlines from major gaming outlets, writes an original short summary with
attribution for each, and opens them as a **pull request** for review before
anything goes live. There is no separate CMS — the site is a Next.js app,
and articles are files in this repo.

## How it's put together

```
app/                     → Next.js site (App Router). Homepage feed + a
                            page per article, statically generated.
content/news/*.json      → One file per article. This is the database.
lib/content.ts           → Reads content/news/*.json for the site to render.

scripts/fetch_news.py    → Pulls RSS/Atom feeds (config/sources.json),
                            filters out anything already posted or older
                            than the lookback window, prints candidate
                            stories as JSON.

  (the agent writes a short original summary + picks category/tags
   for each candidate it decides to run with)

scripts/write_article.py → Takes one article as JSON on stdin, writes
                            content/news/<slug>.json.

scripts/mark_posted.py   → Records which stories were handled in
                            state/posted.json so they're never re-posted.
```

Nothing here scrapes or republishes full articles — `fetch_news.py` only
reads the title/link/short description each outlet already publishes in its
own RSS feed. The actual text on the site is a fresh summary plus a clearly
labeled link back to the original source. Keep it that way; posting scraped
full-text is both a copyright problem and against most outlets' terms of
service.

## The publishing workflow (this replaces a CMS draft queue)

Because content is just files in git, "draft and review" is a **pull
request**:

1. The scheduled agent run writes new `content/news/*.json` files on a
   branch and opens a PR.
2. Vercel automatically builds a **preview deployment** for that PR — a
   real, live URL showing exactly how the new articles will look on the
   site.
3. You review the preview link and merge the PR (or ask for changes, or
   close it) — merging to `main` is what actually publishes, since Vercel
   deploys `main` to the live domain.

No login, no admin dashboard, no credentials to manage for publishing —
review happens as a GitHub PR + a Vercel preview link.

## One-time setup

### 1. Deploy the site to Vercel

1. Go to [vercel.com](https://vercel.com), sign in (or create an account),
   and click **Add New → Project**.
2. Import this GitHub repository (`thebigplume-svg/Plume-gaming-news-website`).
3. Vercel auto-detects Next.js — leave the defaults and click **Deploy**.
4. Once deployed, go to the project's **Settings → Domains** and add
   `plumegaming.com` (and `www.plumegaming.com` if you want both). Vercel
   will show you the DNS records to add.

### 2. Point your domain at Vercel

In your domain's DNS settings (wherever `plumegaming.com` is registered —
this may still be Bluehost even though the site itself is moving off it),
update the records to the ones Vercel showed you in step 1.4 (typically an
`A` record to Vercel's IP and/or a `CNAME` for `www`). DNS changes can take
a few hours to propagate.

### 3. Allow outbound network access to the news sources

This environment's network policy currently blocks outbound requests to
external sites by default (confirmed while building this: RSS pulls to IGN,
Polygon, Kotaku, PC Gamer, etc. all came back `403` from the egress proxy —
an org policy denial). Before the schedule can actually fetch news, the
environment's network policy needs to allow HTTPS to the feed domains in
`config/sources.json` (ign.com, polygon.com, kotaku.com, pcgamer.com,
eurogamer.net, gamespot.com, rockpapershotgun.com, vg247.com, gamerant.com,
destructoid.com). Adjust this in the environment's network policy settings
in Claude Code on the web. Once updated, re-run `python3
scripts/fetch_news.py` from a session in this environment to confirm it
returns candidates instead of 403 errors.

That's it — no application passwords, no API keys, no separate hosting
account credentials. Git push access is already wired up in this
environment.

## Configuration

- `config/sources.json` — which RSS feeds to pull, and each one's default
  site category. Add/remove outlets freely.
- `config/settings.json` — how far back to look (`lookback_hours`), how many
  candidates to fetch per run (`max_candidates`), and how many articles to
  actually publish per run (`articles_per_run`).

## Running it manually

```bash
# 1. See what's new
python3 scripts/fetch_news.py

# 2. For each candidate you want to run with, write a short (3-5 sentence)
#    original summary + pick a category/tags, then:
echo '{
  "title": "...",
  "dek": "one-sentence summary for the card/homepage",
  "body": ["Paragraph one.", "Paragraph two."],
  "category": "News",
  "tags": ["PS5"],
  "source_name": "IGN",
  "source_url": "https://..."
}' | python3 scripts/write_article.py

# 3. Mark it posted so it's not re-fetched next run
echo '[{"fingerprint": "<from step 1 output>", "title": "...", "link": "..."}]' \
  | python3 scripts/mark_posted.py

# 4. Preview locally
npm run dev   # http://localhost:3000

# 5. Commit on a branch and open a PR (rather than pushing straight to main)
git checkout -b news/$(date +%Y-%m-%d)
git add content/news state/posted.json
git commit -m "Add N new articles"
git push -u origin HEAD
# then open a PR — Vercel will comment with a preview link
```

## Running it on a schedule

This is wired up as a recurring Claude Code Routine (~every 4 hours) that
performs the manual steps above automatically for `articles_per_run`
stories per run: fetch candidates, write original summaries, commit to a
new branch, and open a PR. It will silently do nothing if there are no new
candidates. It cannot succeed until network access (setup step 3 above) is
in place — until then, runs will report that they're blocked rather than
failing loudly.

## Branding

The site currently uses a placeholder visual identity (wordmark, colors,
type) so it isn't blank — swap in your real logo and brand colors whenever
you're ready. Colors and fonts live in `app/globals.css` as CSS custom
properties (`--accent`, `--bg`, etc., defined for both light and dark mode);
the wordmark markup is in `components/Masthead.tsx`. A real logo file can
replace `app/favicon.ico` and be added to `public/` for use in the masthead.

## Editorial policy baked into the automation

- **Review before publish**: new articles land as a PR with a live preview,
  not directly on the production site.
- **Attribution required**: every article links back to its original
  source; the agent is instructed not to omit this.
- **No duplicate coverage**: `state/posted.json` prevents the same story
  being posted twice, even across outlets covering the same news (the agent
  checks candidate titles for close duplicates before picking which stories
  to run).
