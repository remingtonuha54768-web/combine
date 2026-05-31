import json
import tempfile
import unittest
from pathlib import Path

from scripts.match_categories import (
    flatten_leaf_categories,
    match_categories,
    save_matches,
)


class MatchCategoriesTests(unittest.TestCase):
    def test_flatten_leaf_categories_ignores_parent_nodes(self):
        tree = [
            {
                "id": 1,
                "categoryName": "政策法规",
                "list": [
                    {"id": 2, "categoryName": "法律法规", "list": None},
                    {"id": 3, "categoryName": "行业标准", "list": []},
                ],
            },
            {"id": 4, "categoryName": "通知公告", "list": None},
        ]

        self.assertEqual(
            flatten_leaf_categories(tree),
            [
                {"id": 2, "categoryName": "法律法规"},
                {"id": 3, "categoryName": "行业标准"},
                {"id": 4, "categoryName": "通知公告"},
            ],
        )

    def test_match_categories_outputs_only_successful_leaf_matches(self):
        source_categories = [
            {"category": "政策法规", "url": "https://example.com/policy"},
            {"category": "法律法规", "url": "https://example.com/law"},
            {"category": "通知公告", "url": "https://example.com/notice"},
        ]
        leaf_categories = [
            {"id": 2, "categoryName": "法律法规"},
            {"id": 4, "categoryName": "通知公告"},
        ]

        self.assertEqual(
            match_categories(source_categories, leaf_categories),
            [
                {
                    "category": "法律法规",
                    "categoryIds": 2,
                    "url": "https://example.com/law",
                },
                {
                    "category": "通知公告",
                    "categoryIds": 4,
                    "url": "https://example.com/notice",
                },
            ],
        )

    def test_save_matches_writes_json_array(self):
        matches = [{"category": "通知公告", "categoryIds": 4, "url": "https://example.com"}]

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "matched.json"
            save_matches(matches, output_path)

            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), matches)


if __name__ == "__main__":
    unittest.main()
