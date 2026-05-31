import json
import tempfile
import unittest
from pathlib import Path

from scripts.extract_links import extract_candidates, save_candidates


class ExtractLinksTests(unittest.TestCase):
    def test_extracts_visible_navigation_candidates(self):
        html = """
        <html>
          <body>
            <nav>
              <a href="/news">News</a>
              <a href="/sports">Sports</a>
              <a href="#top">Top</a>
              <a href="javascript:void(0)">Menu</a>
            </nav>
            <main>
              <a href="/news/2026/05/article.html">Story headline</a>
            </main>
          </body>
        </html>
        """

        candidates = extract_candidates(html, "https://example.com")

        self.assertEqual(
            candidates,
            [
                {
                    "text": "News",
                    "url": "https://example.com/news",
                    "location": "nav",
                },
                {
                    "text": "Sports",
                    "url": "https://example.com/sports",
                    "location": "nav",
                },
                {
                    "text": "Story headline",
                    "url": "https://example.com/news/2026/05/article.html",
                    "location": "main",
                },
            ],
        )

    def test_save_candidates_writes_json_array(self):
        candidates = [{"text": "News", "url": "https://example.com/news", "location": "nav"}]

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "candidates.json"
            save_candidates(candidates, output_path)

            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), candidates)


if __name__ == "__main__":
    unittest.main()
