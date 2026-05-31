---
name: get-category
description: Use when a user asks to crawl, extract, identify, match, or save website category links, navigation channels, section links, menu columns, 栏目链接, 导航栏目, 频道, 分类链接, or categoryIds as JSON; require appKey before crawling.
---

# Get Category

Use this skill to turn a website URL into category-link JSON, then automatically match the result to article-category leaf IDs from the Shanghuiyi API.

Before crawling any page, require an `appKey`. If the user invokes this skill without an `appKey`, ask for the `appKey` first and do not start crawling until the user provides it.

First output:

```json
[
  {
    "category": "栏目名称",
    "url": "栏目链接"
  }
]
```

Matched output:

```json
[
  {
    "category": "栏目名称",
    "categoryIds": 123,
    "url": "栏目链接"
  }
]
```

## Workflow

1. Resolve the user's target URL and output paths. Default paths: `categories.json` and `matched_categories.json`.
2. Confirm `appKey` is available before crawling. If it is missing, ask the user for `appKey` and stop until they provide it.
3. Run `scripts/extract_links.py <url> -o candidate-links.json` to collect link candidates.
   - The script uses **Patchright** (a Playwright fork with built-in anti-detection) by default.
   - Patchright renders the page in a real Chromium browser, so JavaScript-heavy SPAs, dynamic navigation, and lazy-loaded content are handled correctly.
   - The script performs a homepage warm-up, natural scrolling simulation, and randomized browser fingerprinting to evade bot detection.
   - If Patchright is unavailable, pass `--no-browser` to fall back to a static `urllib` + `HTMLParser` fetch.
4. Inspect the candidates and use model judgment to identify true category links.
5. Normalize final URLs to absolute URLs, remove duplicates, and save only `{ "category", "url" }` objects.
6. Read `reference-article.md`, then call `GET https://www.shanghuiyi.com/open/ai/article/categories?appKey=<appKey>` to fetch the category tree.
7. Match the final category links only against leaf nodes in the category tree.
8. Save successful matches to `matched_categories.json`, unless the user specifies another path.
9. Briefly report both output paths and the number of categories matched.

## Category Judgment

Treat a link as a category when it represents a stable section, channel, topic index, product/category listing, or site navigation destination.

Prefer links from:

- Primary navigation, header menus, sidebars, footer section lists
- URL patterns such as `/news`, `/sports`, `/products/software`, `/category/name`, `/topics/name`
- Repeated channel names, business sections, product families, documentation groups

Filter out:

- Login, register, account, cart, checkout, search, language switches
- Article/detail pages, single product pages, tags for one article, comments
- Social sharing, app downloads, ads, external partner links
- Empty labels, anchors, `javascript:`, `mailto:`, `tel:`

When uncertain, keep broad navigation/category pages and discard one-off content pages.

## Output Rules

- Save valid UTF-8 JSON.
- Use an array at the top level.
- For `categories.json`, use `category` for the visible栏目名称 and `url` for the absolute栏目链接.
- For `matched_categories.json`, use `category`, `categoryIds`, and `url`.
- Do not include helper fields such as `text`, `location`, `confidence`, or notes in output JSON.
- Preserve the site's language for category names unless the user asks for translation.

## Category Tree Matching

Use `scripts/match_categories.py` after `categories.json` exists:

```bash
python scripts/match_categories.py --app-key <appKey> --categories categories.json --output matched_categories.json
```

The script uses `https://www.shanghuiyi.com` as the default API base. Pass `--base` only when the user gives a different base URL.

Matching rules:

- Use only leaf nodes from the API category tree. A node with non-empty `list` is a parent and must not be used as `categoryIds`.
- Prefer exact normalized name matches between crawled `category` and leaf `categoryName`.
- If exact matching misses obvious synonyms, use model judgment to map only high-confidence category pairs, then save the same `{ "category", "categoryIds", "url" }` shape.
- Exclude unmatched categories from `matched_categories.json`.

## Script Notes

### extract_links.py

`scripts/extract_links.py` fetches a page and saves candidate links as JSON. It is only a candidate extractor — it does not decide which links are categories. Use the model to make the final decision from candidate text, URL shape, DOM location, and page context.

**Default mode — Patchright browser rendering:**

- Requires `patchright` installed: `pip install patchright && patchright install chromium`
- Launches a headless Chromium browser with randomized fingerprint (viewport, user-agent, device scale factor, locale, timezone).
- Warms up by visiting the site homepage first to establish session cookies and a plausible Referer chain.
- Waits for `networkidle` so JavaScript-rendered navigation and lazy-loaded content are fully present.
- Simulates natural scrolling to avoid bot-detection heuristics.
- Extracts the fully rendered DOM as HTML and parses it with the same deterministic `LinkParser` used in static mode.
- Works against SPAs (React / Vue / Next.js), Cloudflare-protected sites, and pages with dynamic navigation injection.

**Fallback mode — `--no-browser`:**

- Uses `urllib.request` with a Chrome 125 User-Agent for a lightweight static fetch.
- Parses raw HTML with `HTMLParser` — no JavaScript execution.
- Suitable for simple server-rendered sites without anti-bot protection. Fails on JS-heavy pages and WAF-protected sites.

**Anti-detection capabilities (Patchright mode):**

| Protection | Handled? | Mechanism |
|---|---|---|
| JavaScript rendering (SPA) | Yes | Real Chromium browser |
| Cloudflare / Akamai / WAF | Yes | Patchright built-in anti-detection + fingerprint randomization |
| CAPTCHA / JS challenges | Partial | Fingerprint rotation avoids triggering; no interactive solving |
| Rate limiting (429) | N/A | Single-page fetch, no repeated requests |
| TLS fingerprinting (JA3) | Yes | Real Chromium TLS stack |
| Browser fingerprinting | Yes | Randomized viewport, UA, device scale factor per session |
| Session / Referer checks | Yes | Homepage warm-up establishes natural Referer chain |

### match_categories.py

`scripts/match_categories.py` fetches or loads the article category tree, flattens leaf categories, performs deterministic normalized-name matching, and writes matched JSON.

If network access is unavailable, ask for permission to fetch the URL or ask the user to provide saved HTML.
