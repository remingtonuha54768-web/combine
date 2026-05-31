import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://www.shanghuiyi.com"


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def flatten_leaf_categories(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    leaves: list[dict[str, Any]] = []
    for node in nodes:
        children = node.get("list") or []
        if children:
            leaves.extend(flatten_leaf_categories(children))
            continue

        if "id" in node and node.get("categoryName"):
            leaves.append({"id": node["id"], "categoryName": node["categoryName"]})
    return leaves


def match_categories(
    source_categories: list[dict[str, Any]],
    leaf_categories: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    leaves_by_name = {
        normalize_name(str(leaf["categoryName"])): leaf
        for leaf in leaf_categories
        if leaf.get("categoryName")
    }

    matches: list[dict[str, Any]] = []
    seen_ids: set[tuple[str, Any]] = set()
    for item in source_categories:
        category = str(item.get("category", "")).strip()
        url = str(item.get("url", "")).strip()
        if not category or not url:
            continue

        leaf = leaves_by_name.get(normalize_name(category))
        if not leaf:
            continue

        key = (category, leaf["id"])
        if key in seen_ids:
            continue
        seen_ids.add(key)
        matches.append(
            {
                "category": category,
                "categoryIds": leaf["id"],
                "url": url,
            }
        )
    return matches


def fetch_category_tree(app_key: str, base_url: str = DEFAULT_BASE_URL) -> list[dict[str, Any]]:
    base_url = base_url.rstrip("/")
    query = urlencode({"appKey": app_key})
    url = f"{base_url}/open/ai/article/categories?{query}"
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if payload.get("errno") != 0:
        message = payload.get("errmsg") or "failed to fetch category tree"
        raise RuntimeError(message)

    data = payload.get("data")
    if not isinstance(data, list):
        raise RuntimeError("category tree response data must be a list")
    return data


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_matches(matches: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(matches, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Match crawled category links with leaf nodes from the article category tree."
    )
    parser.add_argument(
        "--categories",
        default="categories.json",
        help="Input JSON produced by the get-category workflow",
    )
    parser.add_argument(
        "--output",
        default="matched_categories.json",
        help="Output JSON path for matched categories",
    )
    parser.add_argument(
        "--app-key",
        required=True,
        help="appKey used by GET /open/ai/article/categories",
    )
    parser.add_argument(
        "--base",
        default=DEFAULT_BASE_URL,
        help="API base URL",
    )
    parser.add_argument(
        "--tree-json",
        help="Optional local category tree response or data JSON for offline testing",
    )
    args = parser.parse_args(argv)

    source_categories = load_json(Path(args.categories))
    if args.tree_json:
        tree_payload = load_json(Path(args.tree_json))
        tree = tree_payload.get("data", tree_payload) if isinstance(tree_payload, dict) else tree_payload
    else:
        tree = fetch_category_tree(args.app_key, args.base)

    leaves = flatten_leaf_categories(tree)
    matches = match_categories(source_categories, leaves)
    save_matches(matches, Path(args.output))
    print(f"Saved {len(matches)} matched categories to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
