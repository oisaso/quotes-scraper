#!/usr/bin/env python3
"""
quotes-scraper - small, polite, zero-dependency web scraper.

Scrapes quotes.toscrape.com (a public scraping sandbox), follows pagination,
retries failed requests with exponential backoff, rate-limits itself, and
exports clean CSV / JSON.

Usage:
    python scrape.py                              # live, 3 pages
    python scrape.py --pages 5 --json out.json    # live, 5 pages, JSON too
    python scrape.py --offline                    # parse bundled fixture, no network

No third-party packages required.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

BASE_URL = "https://quotes.toscrape.com/"
FIXTURE = Path(__file__).parent / "fixtures" / "quotes_page1.html"
USER_AGENT = "PortfolioScraper/1.0 (demo build; contact: example@example.com)"
TIMEOUT = 15
MAX_RETRIES = 3

log = logging.getLogger("scraper")


class QuotesParser(HTMLParser):
    """Extracts quote blocks and the pagination link from one page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.quotes: list[dict] = []
        self.next_href: str | None = None
        self._div_depth = 0
        self._in_quote = False
        self._in_next = False
        self._capture: str | None = None
        self._current: dict | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        attr = {k: v or "" for k, v in attrs}
        classes = set(attr.get("class", "").split())

        if tag == "div" and "quote" in classes:
            self._in_quote = True
            self._div_depth = 1
            self._current = {"text": "", "author": "", "tags": []}
            return

        if not self._in_quote:
            if tag == "li" and "next" in classes:
                self._in_next = True
            elif tag == "a" and self._in_next and "href" in attr:
                self.next_href = attr["href"]
            return

        if tag == "div":
            self._div_depth += 1
        elif tag == "span" and "text" in classes:
            self._capture = "text"
        elif tag == "small" and "author" in classes:
            self._capture = "author"
        elif tag == "a" and "tag" in classes:
            self._capture = "tag"

    def handle_endtag(self, tag: str) -> None:
        if self._in_quote:
            if tag in ("span", "small", "a"):
                self._capture = None
            elif tag == "div":
                self._div_depth -= 1
                if self._div_depth == 0:
                    self._finish_quote()
            return
        if tag == "li":
            self._in_next = False

    def handle_data(self, data: str) -> None:
        if not (self._in_quote and self._capture and self._current is not None):
            return
        if self._capture == "tag":
            self._current["tags"].append(data)
        else:
            self._current[self._capture] += data

    def _finish_quote(self) -> None:
        if self._current is None:
            return
        text = " ".join(self._current["text"].split())
        author = " ".join(self._current["author"].split())
        tags = [t.strip() for t in self._current["tags"] if t.strip()]
        if text and author:
            self.quotes.append({"quote": text, "author": author, "tags": tags})
        self._in_quote = False
        self._current = None
        self._capture = None


def fetch(url: str, retries: int = MAX_RETRIES) -> str:
    """GET a page with retries + exponential backoff. Raises on final failure."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
            if attempt == retries:
                break
            wait = 2**attempt + random.uniform(0, 0.5)
            log.warning("request failed (attempt %d/%d): %s - retrying in %.1fs",
                        attempt, retries, exc, wait)
            time.sleep(wait)
    raise RuntimeError(f"giving up on {url}: {last_error}")


def parse_page(html: str) -> QuotesParser:
    parser = QuotesParser()
    parser.feed(html)
    return parser


def scrape(base_url: str, pages: int, delay: float) -> list[dict]:
    """Walk pagination, dedupe by (quote, author), return clean records."""
    results: list[dict] = []
    seen: set[tuple[str, str]] = set()
    next_url: str | None = base_url
    page = 0

    while next_url and page < pages:
        page += 1
        log.info("page %d: %s", page, next_url)
        parser = parse_page(fetch(next_url))
        added = 0
        for record in parser.quotes:
            key = (record["quote"], record["author"])
            if key not in seen:
                seen.add(key)
                results.append(record)
                added += 1
        log.info("page %d: %d found, %d new (total %d)",
                 page, len(parser.quotes), added, len(results))

        next_url = urllib.parse.urljoin(next_url, parser.next_href) if parser.next_href else None
        if next_url and page < pages:
            # polite crawl: base delay + jitter, never hammer the target
            time.sleep(delay + random.uniform(0, 0.3))

    return results


def write_csv(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig: opens cleanly in Excel without mojibake
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["quote", "author", "tags"])
        for record in records:
            writer.writerow([record["quote"], record["author"], "; ".join(record["tags"])])


def write_json(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Polite quotes scraper (zero dependencies).")
    parser.add_argument("--pages", type=int, default=3, help="max pages to crawl (default 3)")
    parser.add_argument("--offline", action="store_true", help="parse bundled fixture, no network")
    parser.add_argument("--out", default="output/quotes.csv", help="CSV output path")
    parser.add_argument("--json", default=None, help="optional JSON output path")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between page requests")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    started = time.monotonic()
    if args.offline:
        log.info("offline mode: %s", FIXTURE)
        records = parse_page(FIXTURE.read_text(encoding="utf-8")).quotes
        pages_done = 1
    else:
        records = scrape(BASE_URL, args.pages, args.delay)
        pages_done = args.pages

    if not records:
        log.error("no quotes parsed - target layout may have changed")
        return 1

    csv_path = Path(args.out)
    write_csv(records, csv_path)
    print(f"done: {len(records)} quotes from {pages_done} page(s) in {time.monotonic() - started:.1f}s")
    print(f"csv  -> {csv_path}")

    if args.json:
        json_path = Path(args.json)
        write_json(records, json_path)
        print(f"json -> {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
