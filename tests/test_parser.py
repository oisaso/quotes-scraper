"""Parser tests for scrape.py - added as the repo's first real test suite.

Run from the scraper/ directory:
    python -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrape import QuotesParser  # noqa: E402

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "quotes_page1.html"


class QuotesParserTests(unittest.TestCase):
    def parse_fixture(self):
        parser = QuotesParser()
        parser.feed(FIXTURE.read_text(encoding="utf-8"))
        return parser

    def test_fixture_yields_ten_quotes(self):
        self.assertEqual(len(self.parse_fixture().quotes), 10)

    def test_first_quote_fields(self):
        first = self.parse_fixture().quotes[0]
        self.assertEqual(first["author"], "Albert Einstein")
        self.assertIn("world", first["quote"])
        self.assertIn("change", first["tags"])

    def test_pagination_link_found(self):
        self.assertEqual(self.parse_fixture().next_href, "/page/2/")

    def test_malformed_html_does_not_crash(self):
        parser = QuotesParser()
        parser.feed("<div class='quote'><span class='text'>half open")
        # no closing tags: parser must not raise, even if it yields nothing
        self.assertIsInstance(parser.quotes, list)

    def test_quote_without_author_is_skipped(self):
        parser = QuotesParser()
        parser.feed(
            "<div class='quote'>"
            "<span class='text'>orphan quote</span>"
            "</div>"
        )
        self.assertEqual(parser.quotes, [])


if __name__ == "__main__":
    unittest.main()
