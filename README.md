# Quotes scraper — portfolio demo

**What it proves:** a working, production-shaped scraper with no third-party
dependencies — pagination, retries with backoff, rate limiting, dedupe,
clean CSV/JSON export. This is the "automation / scraper" gig's proof piece.

## Run it

```bash
# live, 3 pages
python scrape.py

# live, 5 pages, also export JSON
python scrape.py --pages 5 --json output/quotes.json

# no network needed (bundled fixture)
python scrape.py --offline --out output/quotes_offline.csv
```

Python 3.10+. Nothing to install.

## What a buyer sees

- `output/quotes.csv` — 30+ rows, UTF-8 with BOM so Excel opens it clean
- Retry messages if the network hiccups, never a crash on one bad page
- `--delay` — politeness built in, not bolted on

## Files

| File | Role |
|---|---|
| `scrape.py` | everything: parser, fetch/retry, crawl, export |
| `fixtures/quotes_page1.html` | saved page used by `--offline` |

## How it maps to the gig

Bought as "Python automation script / scraper." The swappable target +
config-driven parse is the story: replace `BASE_URL`/parser, keep the
plumbing (retry, dedupe, export) — that plumbing is what buyers are paying for.
