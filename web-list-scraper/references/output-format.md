# Output Format And Link Classification

## JSON output

Write a JSON array. Each item must contain these base fields:

- `url`: normalized absolute URL
- `title`: article title text corresponding to the URL
- `isOutLink`: boolean
- `isFileLink`: boolean
- `isWechatLink`: boolean

If a wrapper or pipeline invokes the scraper with a matched category record, every exported item for that crawl must also include that record's numeric `categoryIds`. If the scraper is used directly without upstream category context, omit `categoryIds`.

Example:

```json
[
  {
    "url": "https://example.com/article/123",
    "title": "Example article title",
    "categoryIds": 123,
    "isOutLink": false,
    "isFileLink": false,
    "isWechatLink": false
  },
  {
    "url": "https://cdn.example.net/report.pdf",
    "title": "Annual report PDF",
    "categoryIds": 123,
    "isOutLink": true,
    "isFileLink": true,
    "isWechatLink": false
  },
  {
    "url": "https://mp.weixin.qq.com/s/abc123",
    "title": "WeChat article title",
    "categoryIds": 123,
    "isOutLink": true,
    "isFileLink": false,
    "isWechatLink": true
  }
]
```

## Filename

Use:

`<domain>_<YYYYMMDD_HHMMSS>.json`

Examples:

- `example.com_20260527_143015.json`
- `news.example.com_20260527_143015.json`

## URL normalization

Before deduplication and classification:

1. Resolve relative URLs against the current page.
2. Prefer `https` when the resolved page is `https`.
3. Remove obvious duplicate fragments when they do not change the target resource.
4. Keep query parameters when they appear to identify the resource.

## Title extraction

Each output item must include `title`, the article title corresponding to the exported URL.

Use this priority order:

1. Visible text of the primary article-detail link.
2. The nearest title element inside the same article-list item, such as a heading, title span, or equivalent title node.
3. A meaningful `title` attribute from the primary link when visible text is empty or generic.

Normalize titles by trimming leading/trailing whitespace and collapsing repeated internal whitespace. Keep the title tied to the same list item as the URL. Do not open article-detail pages solely to fill or improve titles.

## `isOutLink` rule

Mark `isOutLink` as `true` when the normalized URL host is outside the target site's domain scope.

Examples for target domain `example.com`:

- `https://example.com/a/1` -> `false`
- `https://www.example.com/a/1` -> `false`
- `https://news.example.com/a/1` -> `false`
- `https://other-site.com/a/1` -> `true`

If the site uses a clearly separate content CDN or document host and the link still represents an article-detail destination chosen from the list, mark the value based on host reality rather than guessing intent.

## `isFileLink` rule

Mark `isFileLink` as `true` when the URL clearly points to a file or a download endpoint.

Common file extensions include:

- `.pdf`
- `.doc`
- `.docx`
- `.xls`
- `.xlsx`
- `.csv`
- `.ppt`
- `.pptx`
- `.zip`
- `.rar`
- `.7z`
- `.txt`
- `.rtf`

Also treat URLs as file links when they include strong download cues, such as:

- `/download/`
- `download=`
- `attachment`
- `file=`

When in doubt, prefer a conservative judgment and keep the reasoning consistent across all exported links.

## `isWechatLink` rule

Mark `isWechatLink` as `true` when the normalized URL host is exactly:

- `mp.weixin.qq.com`

Examples:

- `https://mp.weixin.qq.com/s/abc123` -> `true`
- `https://example.com/article/1` -> `false`
- `https://weixin.qq.com/` -> `false`

`isWechatLink` is independent from the other fields. In most cases, a WeChat article URL will also be an external link and not a file link.
