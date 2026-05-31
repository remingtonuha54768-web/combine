---
name: category-to-list-pipeline
description: Use when the user wants to identify website category links and crawl article-list links for each matched category, especially when connecting get-category output to web-list-scraper with categoryIds or isolated per-category subagents.
---

# Category To List Pipeline

Use this skill to run a two-stage workflow: first get matched category links with `get-category`, then dispatch one isolated subagent per matched category to run `web-list-scraper`.

The main agent coordinates the batch. It does not directly crawl article-list pages after `matched_categories.json` exists.

## Required inputs

- `targetUrl`: the website URL to analyze for category links.
- `appKey`: required by `get-category` before crawling or matching categories.

If `appKey` is missing, ask for it first and do not start crawling.

## Workflow

1. Run `get-category` for `targetUrl` and `appKey`.
2. Produce `categories.json` and `matched_categories.json`, unless the user provides different paths.
3. Read `matched_categories.json` as the handoff contract. Each item must contain:

```json
{
  "category": "栏目名称",
  "categoryIds": 123,
  "url": "https://example.com/news"
}
```

4. If `matched_categories.json` is empty, stop and report that there are no matched categories to crawl.
5. Process matched categories sequentially in file order by default.
6. For each matched category, dispatch a subagent to run `web-list-scraper` for that category only.
7. Pass the category `url` as the crawl target and the numeric `categoryIds` as upstream category context.
8. Require the subagent to ensure every exported article item includes the same `categoryIds` value.
9. Require the subagent to write its category crawl to a separate output file so categories from the same domain cannot overwrite each other.
10. Collect each subagent result and write `pipeline_manifest.json` after the batch completes.

## Subagent dispatch

Dispatch exactly one subagent per matched category. By default, wait for one subagent to finish before dispatching the next one.

Subagent input must use this shape:

```json
{
  "category": "通知公告",
  "categoryIds": 103,
  "url": "https://example.com/news",
  "outputDir": "category-to-list_example.com_20260531_173000",
  "allowedCommandStyle": "Use Python or Bash commands that are already allowed in the current subagent environment. Do not use PowerShell."
}
```

The subagent prompt must include:

- Use `web-list-scraper`.
- Crawl only the provided `url`.
- Treat the provided numeric `categoryIds` as upstream category context.
- Add that same `categoryIds` value to every exported article item.
- Write the article-list JSON under `outputDir`.
- Preserve `web-list-scraper` analysis, crawl, pacing, and validation rules.
- Follow the provided `allowedCommandStyle`. The main agent must state the known allowed command style before dispatch.
- Do not use PowerShell by default. Prefer allowed Python commands, Bash commands, existing scraper scripts, and existing browser/crawl tools only when they match `allowedCommandStyle`.
- If PowerShell is denied, do not retry with PowerShell. Use a natural equivalent only when it performs the same task and is allowed in the current subagent environment.
- Do not bypass permission denials with unrelated tools or side effects.
- If a denied command is essential and no allowed equivalent exists, stop that category crawl and return the failed result shape with `error` beginning `Permission denied:` and naming the denied command and why it was needed.
- Return only the structured result described below.

Subagent result must use this shape:

```json
{
  "category": "通知公告",
  "categoryIds": 103,
  "url": "https://example.com/news",
  "status": "success",
  "articleListOutput": "category-to-list_example.com_20260531_173000/001_通知公告_103_example.com_20260531_173000.json",
  "articleCount": 42,
  "validated": true,
  "error": null
}
```

For failed category crawls, the subagent must return `status: "failed"`, `articleListOutput: null`, `articleCount: 0`, `validated: false`, and a concise `error`.

For permission failures, the `error` should identify the missing capability, for example:

`Permission denied: PowerShell(Get-Content ...) required to inspect the exported JSON file`

Do not default to parallel subagents. Use small-batch parallel dispatch only when the user explicitly asks for faster crawling and accepts higher target-site pressure.

## Article output

Each downstream article-list JSON item must follow the `web-list-scraper` output format and include `categoryIds`:

```json
{
  "url": "https://example.com/article/123",
  "title": "Example article title",
  "categoryIds": 123,
  "isOutLink": false,
  "isFileLink": false,
  "isWechatLink": false
}
```

`categoryIds` must come only from the current matched category record. Do not infer or rematch it inside `web-list-scraper`.

## Output organization

Use a stable per-run output directory, for example:

`category-to-list_<domain>_<YYYYMMDD_HHMMSS>/`

Inside the directory, store:

- `categories.json`
- `matched_categories.json`
- one article-list JSON file per matched category
- `pipeline_manifest.json`

Use filenames that include a safe category label and `categoryIds`, for example:

`001_通知公告_103_example.com_20260531_173000.json`

If the category name contains characters that are unsafe for a filename, replace them with `_`.

## Manifest

Write `pipeline_manifest.json` with this structure:

```json
{
  "sourceUrl": "https://example.com",
  "matchedCategoriesPath": "matched_categories.json",
  "categories": [
    {
      "category": "通知公告",
      "categoryIds": 103,
      "url": "https://example.com/news",
      "status": "success",
      "articleListOutput": "001_通知公告_103_example.com_20260531_173000.json",
      "articleCount": 42,
      "validated": true,
      "error": null
    }
  ]
}
```

Build the manifest from subagent results. For failed category crawls, set `status` to `failed`, set `articleListOutput` to `null`, set `articleCount` to `0`, set `validated` to `false`, and record a concise `error`.

When writing the manifest, normalize successful `articleListOutput` to a path relative to `outputDir` if the subagent returns a path that includes `outputDir`. This keeps the manifest portable inside the run directory.

## Failure handling

- Keep the batch serial unless the user explicitly requests small-batch parallelism.
- If one subagent reports a clear blocker, record the failure in the manifest and continue with the next category.
- If one subagent reports `Permission denied:`, record that category as failed and continue with the next category. At the end, report that the failed category needs additional tool permission before retrying.
- If two consecutive categories fail with the same `Permission denied:` capability, stop the batch early, write the manifest for completed and failed categories so far, and report the missing permission instead of producing repeated failures.
- Preserve `web-list-scraper` validation rules for each category. A category is successful only when its exported link count matches the actual article-list count; a clear blocker is a failed category with an `error` in the manifest.
- At the end, report the matched category count, successful crawl count, failed crawl count, and manifest path.
