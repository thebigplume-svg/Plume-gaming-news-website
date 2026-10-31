# Plume Money

A personal budgeting app and a YouTube channel spending tracker, in one page.
It is a single self-contained file (`index.html`) with no build step and no
server. It's kept separate from the news site, so it isn't part of the Next.js
build and isn't deployed with it.

## Run it

Open `budget-app/index.html` in any browser (double-click it). That's it.

## What's inside

**Personal Budget tab**
- Log income and expenses by category for the selected month
- Set a monthly limit per category. Bars turn amber at 85% and red when over
- Shows income, spending, what's left this month, and the budget remaining

**YouTube Channel tab** (kept fully separate from personal money)
- Log channel revenue (AdSense, sponsorships, memberships, affiliate, merch…)
  and expenses (gear, software, games for content, editors, music, ads…)
- Mark expenses as tax-deductible
- Tag entries with a video or project to see cost, revenue and net per video
- Track recurring subscriptions (monthly or yearly), see the monthly and
  yearly totals, and log all monthly ones into a month with one click
  (it won't log the same subscription twice in a month)
- Switch between month and year-to-date totals
- Export to CSV for your accountant or tax software

**Settings & Backup tab**
- Currency and light/dark theme
- Download a JSON backup, or restore from one

## Your data

Everything is stored in your browser's local storage on this device. Nothing
is sent anywhere. Clearing your browser data erases it, so use **Download
backup** regularly. The backup file is also how you move your data to another
device or browser.
