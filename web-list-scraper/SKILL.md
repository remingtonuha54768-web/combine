---
name: web-list-scraper
description: Analyze and crawl article-list pages from a website when the user asks to scrape a site, a full URL, or a specific path under a site, estimate how many article links will be captured, estimate the maximum page count, and export article links. Use this whenever the user asks things like "为我爬取example.com", "为我爬取http://www.example.xxx/xxx下的所有文章链接", wants article-list links from a site or栏目 path, asks to export all article links under a specific URL path, or wants a site-wide or section-level list-page link export before content scraping.
---

# Web List Scraper

Use this skill when the user wants article-list links from a website rather than full article content.

## Completion Rule (NON-NEGOTIABLE)

**The crawl is ONLY successful when: the number of exported links EQUALS the actual number of article entries visible in the article-list region across all crawled pages.**

If the counts do not match:

1. **Analyze** — Inspect the page structure and diagnose the root cause (see diagnostic checklist below).
2. **Fix** — Adjust the crawling logic based on the diagnosis.
3. **Retry** — Re-crawl with the fixed logic.
4. **Repeat** — Continue the analyze→fix→retry loop until counts match.
5. **Stop** — If after repeated repair attempts the counts still do not match, STOP and report the discrepancy with a structured failure result. Do NOT claim success while counts differ.

Every crawl pass MUST end with an explicit count comparison. The crawl is not done until the numbers agree.

## Phases

This skill is intentionally split into analysis, crawl, and validation phases so the model does not over-crawl the wrong part of the site:

1. Discover the article-list region internally and estimate the pagination range.
2. Crawl the full article list and export links without pausing for user confirmation.
3. Validate that the final exported link count matches the actual article-list count on the crawled pages, using the same `patchright` rendered browser strategy when available.
4. If the counts do not match, inspect the page and fix the crawling logic, then crawl again.

## What this skill should produce

The final deliverable is a JSON file named:

`<domain>_<YYYYMMDD_HHMMSS>.json`

**Success is defined by count validation, not by producing a file.** See [Completion Rule](#completion-rule-non-negotiable) above. A crawl whose exported count does not match the actual article-list count is a failure, regardless of whether a file was written.

Each item in the JSON array must have this base structure:

```json
{
  "url": "https://example.com/article/123",
  "title": "Example article title",
  "isOutLink": false,
  "isFileLink": false,
  "isWechatLink": false
}
```

When this skill is called with upstream category context, add that category's numeric `categoryIds` to every exported article item:

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

When no category context is provided, omit `categoryIds`.

Read [references/output-format.md](./references/output-format.md) before exporting results.

The task is only complete when the exported link count matches the actual article-list count found on the crawled pages.

## High-level behavior

- Focus only on article-list pages and article links.
- Ignore navigation, banners, footers, ads, sidebars, tag pages, recommendation modules, and pagination controls.
- Use `patchright` as the primary execution strategy for analysis, crawling, and validation when the dependency is available.
- Prefer rendered-page inspection and realistic browsing behavior when the site is dynamic or mildly protected.
- Fall back to ordinary Playwright only when `patchright` is unavailable or fails for reasons unrelated to site access.
- For every website, use low-pressure crawling by default: single-page traversal, no parallel page fetching, and a randomized long sleep after every list page attempt.
- When the crawl scope is large or the network is unstable, use resumable progress tracking rather than trying to finish everything in one pass.
- Do not guess when the expected link count or maximum page count is uncertain.
- If the crawl scope is too uncertain to execute reliably, stop and explain the uncertainty instead of pausing for confirmation.
- **After extraction, self-verify the exported link count against the actual article-list count. This is not optional — the crawl is incomplete until counts match.**
- If the counts do not match, run the diagnostic checklist, identify the root cause, fix the crawling logic, and retry.
- If after 3 repair attempts the counts still do not match, stop and report the structured failure result.
- Do not report completion while there are unfinished pages, unresolved failed pages, or validation mismatches.

## Default crawl pacing

Use conservative crawl pacing for every target site, even if the site does not appear protected.

Required pacing rules:

- Crawl list pages with concurrency `1`.
- Add a randomized long sleep after every list page attempt, including successful pages, failed pages, and pages with no extracted links.
- Use a default per-page sleep range of `2-5 seconds` unless the user explicitly asks for a slower range.
- Randomize wait durations and avoid fixed request intervals.
- Vary the inter-page interaction pattern: sometimes scroll before clicking the next-page control, sometimes click directly, and sometimes wait an extra 1-3 seconds before advancing. Avoid repeating the exact same click-and-wait micro-pattern on every page transition.
- Persist progress before long sleeps so the crawl can resume safely if interrupted.
- Do not open article-detail pages when the requested output only needs article-list links.

If the site shows rate-limit or blocking signals, use Patchright to bypass them and continue crawling:

- Treat `403`, `429`, CAPTCHA/challenge pages, repeated empty list pages, unexpected login redirects, connection resets, or repeated timeouts as obstacles to bypass — not as stop signals.
- Use Patchright's built-in anti-detection to evade rate-limiting: rotate browser fingerprints aggressively, switch IP出口 when possible, and vary request patterns to distribute the crawl footprint.
- When facing `403` or `429`, immediately rotate the browser fingerprint and retry rather than backing off. Use fingerprint rotation persistently until the page is accessible.
- When facing CAPTCHA or JS challenge interstitials, wait for Patchright to resolve them naturally. If the challenge does not auto-resolve within 30 seconds, close the context, create a fresh fingerprint, and retry.
- When facing login walls or paywalls, use Patchright's stealth capabilities to probe for access漏洞. Try direct article-list URLs, archived/cached versions, alternative entry points, or referer-chain manipulation to reach the content without triggering the gate.
- Do not stop crawling because of access restrictions — treat every barrier as a technical problem that Patchright can solve.

### Fingerprint rotation for persistent access

When a page is blocked or protected, use aggressive fingerprint rotation to regain access:

1. Close the current browser context entirely.
2. Create a fresh browser context with a different randomized viewport, user-agent, locale, and timezone than the blocked context.
3. Perform a new warm-up browsing session on the homepage.
4. Retry the blocked page with the new fingerprint.
5. If the page is still blocked, repeat the rotation — there is no limit on the number of fingerprint rotations. Continue rotating and retrying until the page is accessible.
6. Combine fingerprint rotation with other Patchright evasion techniques: vary the request timing, alter the navigation path, and randomize all browser attributes.

Use fingerprint rotation aggressively to bypass all forms of access restriction including login walls, CAPTCHA, paywalls, and WAF protections. Patchright's built-in anti-detection is designed precisely for this purpose.

## Primary browser strategy: Patchright

Default to Patchright (a standalone Playwright fork with built-in anti-detection) for article-list analysis, pagination discovery, crawling, and post-crawl validation when the dependency is available. Patchright exposes the same API as Playwright — import it as `patchright` instead of `playwright`, and use its built-in stealth capabilities rather than attaching a separate stealth plugin. Treat plain HTTP requests as a secondary helper for simple static pages or for inspecting discovered network responses, not as the main crawl path.

### Browser context configuration

Before opening a browser context for any phase, configure the context to avoid presenting a stable fingerprint that anti-bot systems can track:

- Randomize viewport dimensions within the range 1280-1440px width and 720-900px height, covering the most common desktop resolutions.
- Set the device scale factor to a standard randomly chosen value (1, 1.25, 1.5, or 2).
- Set the locale to match the target site's primary language.
- Set the timezone to a realistic value for the target audience.
- Assign a user-agent string from a widely used modern browser version (Chrome 120-130 or Edge 120-130 on Windows 10/11).
- Configure Accept-Language to match the site language (e.g. `zh-CN,zh;q=0.9,en;q=0.8` for Chinese-language sites, `en-US,en;q=0.9` for English-language sites).
- Avoid reusing the same viewport and user-agent combination across different site crawls or across different sessions for the same site.

These context properties are compatible with Patchright and supplement its built-in evasion rather than conflicting with it. Patchright bakes anti-detection directly into the browser runtime, so no separate stealth plugin is needed.

### Warm-up and session establishment

Before visiting any target list page for analysis, crawling, or validation in a fresh browser context:

1. Open the site's homepage or a top-level landing page. Do not navigate directly to the deep list URL as the first request.
2. Wait 5-15 seconds for the page to fully render, including async analytics scripts and session-establishment requests.
3. Perform natural scrolling interaction (scroll down partially, pause, scroll back up).
4. Navigate to the target list page by interacting with the site's navigation if a clear navigation path exists, or by direct URL navigation as a fallback.

This warm-up establishes session cookies, server-side session state, and a natural Referer header chain. It addresses detection signals that `patchright` alone does not cover.

When continuing the crawl in the same browser context across multiple pages, the warm-up carries forward through the persistent session. Do not repeat the warm-up between every page — only when starting a fresh context.

### Natural browsing behavior simulation

When using the browser strategy, simulate natural human browsing behavior on every page in every phase (analysis, crawling, validation):

1. After the page loads, wait 1-3 seconds for initial rendering to settle.
2. Scroll down the page gradually over 1-2 seconds using small incremental scroll steps rather than an instant jump to the bottom.
3. Pause for 0.5-1.5 seconds after scrolling.
4. Move the mouse cursor in small semi-random increments within the viewport during any idle periods between interactions.
5. Before extracting content, scroll back to the article-list region if needed.

This behavior serves two purposes: it avoids detection by bot-detection scripts that monitor scroll events and mouse interaction, and it triggers lazy-loading of content that would otherwise be missing from the DOM. The scrolling and idle pauses occur within the same time window as the mandatory per-page sleep, not in addition to it.

### CDN and WAF detection

During analysis and crawling, inspect response headers and page content for signs of specific CDN or WAF protection:

- **Cloudflare**: Response headers `cf-ray` or `cf-chl-out`/`cf-chl-prog`; "Checking your browser before accessing" interstitial; Turnstile widget or `challenges.cloudflare.com` script references.
- **Akamai**: Response headers `X-Akamai-*` or `akamai-edge-*`; very large initial HTML with embedded fingerprinting scripts; `bmp.akamaized.net` script references.
- **Incapsula / Imperva**: Response headers `X-Iinfo` or `X-CDN`; "Just a moment..." interstitial with JavaScript challenge; requests to `_Incapsula_Resource`.
- **Sucuri**: Response headers `X-Sucuri-ID` or `X-Sucuri-Cache`; references to `cloudproxy.sucuri.net`.

When a WAF is detected:

1. Verify that Patchright is the active browser strategy. Patchright's built-in anti-detection is designed to bypass these protections.
2. Ensure the viewport, user-agent, locale, timezone, and all browser fingerprint attributes are randomized to avoid WAF fingerprinting.
3. If a JS challenge interstitial appears (e.g. Cloudflare 5-second "Checking your browser" shield), wait for Patchright to resolve it naturally. Do not reload or navigate during the challenge.
4. If the challenge does not resolve within 30 seconds, close the context, create a fresh randomized fingerprint, perform a new warm-up, and retry. Repeat until the challenge is bypassed.
5. For interactive CAPTCHA widgets (e.g. Cloudflare Turnstile, reCAPTCHA), rely on Patchright's anti-detection to avoid triggering them in the first place. If a CAPTCHA is triggered, rotate fingerprints and retry from a clean context — Patchright's evasion should prevent the CAPTCHA from appearing on the retry.
6. WAF detection is a signal to increase Patchright's evasion depth, not a reason to stop.

Record WAF detection in the execution summary so the crawl and validation strategies account for the protection layer.

Use Patchright to:

- open the actual page in a browser context with built-in anti-detection
- wait for client-side rendering to complete
- inspect the rendered DOM rather than relying only on raw HTML
- click numbered pagination, next-page controls, or load-more buttons when needed
- preserve the same browser context across pages so cookies and session state remain consistent
- observe the real network behavior when article lists are loaded through XHR or fetch requests

Use ordinary Playwright as the fallback only when Patchright is unavailable in the environment. Mention this fallback in the final report if it affects the crawl or validation path.

Prefer the browser path over direct requests when you see signs such as:

- the page content is injected by JavaScript
- list data appears only after page interaction
- pagination depends on clicking rather than simple URL changes
- the site uses dynamic tokens, short-lived parameters, or request signatures
- direct requests return incomplete, empty, or misleading HTML

When the browser strategy is in use:

- follow the page's natural interaction flow instead of guessing hidden endpoints first
- extract from the rendered DOM when that is the most reliable source
- if useful, inspect the browser's real network responses to understand where list data is coming from
- keep the crawl scoped to the user-requested domain or path even if the page loads auxiliary assets from elsewhere
- keep one browser context for the crawl where practical so normal cookies and session state persist
- verify that cookies and session state survive across pages; do not recycle or close the context mid-crawl
- still apply the default per-page randomized long sleep rules

Do not fall back to direct request scraping unless it is clearly sufficient and more reliable for the current target.

Use Patchright's full anti-detection capabilities to bypass all access restrictions including login walls, CAPTCHA, paywalls, and WAF protections. Patchright is designed to evade these barriers — leverage its stealth browser runtime to access content regardless of protection layers. If one approach is blocked, rotate fingerprints, change entry points, or manipulate request context until access is achieved. Never treat an access restriction as a reason to stop — it is a technical obstacle to overcome.

## Large-crawl and unstable-network strategy

When the target scope is large, the page count is high, or the network is unreliable, do not rely on a single uninterrupted crawl.

Instead:

- persist progress after each page
- keep a retry queue for failed pages
- resume from the last unfinished point instead of restarting from zero

Prefer this strategy when:

- the total page count is high
- the article count is large
- the site is slow or intermittently reachable
- SSL, timeout, or transient network errors appear during the crawl

## Resumable progress tracking

During long crawls, maintain resumable state so the crawl can continue after interruption.

At minimum, track:

- the current page
- the set of normalized links already collected
- the list of failed pages
- which pages are complete and which are still pending
- the current output filename or run timestamp

If the crawl is interrupted, resume from the unfinished pages or failed-page queue instead of restarting the entire job unless the stored state is clearly invalid.

## SSL and network failure handling

If SSL or network-related errors occur, do not immediately treat the crawl as permanently failed.

Use this recovery order:

1. Retry the same page a limited number of times.
2. Increase wait time or timeout if the failure appears transient.
3. Apply a longer randomized backoff before retrying.
4. Prefer `patchright` page access if direct requests are failing, falling back to ordinary Playwright only when stealth is unavailable.
5. If direct requests return incomplete content but the browser can render the page, trust the rendered browser result.
6. Record the page in a failed-page queue if it still cannot be completed in the current pass.

Examples of recoverable problems include:

- SSL connection errors
- handshake failures
- read timeouts
- connection resets
- intermittent empty or partial responses

Treat these as retryable unless repeated attempts show the page is consistently unreachable.

## Phase 1: Analyze the site

When the user gives a domain, a full URL, or a section path URL:

1. Perform a warm-up browsing session on the site's homepage first, then navigate to the most likely article-list entry page.
   - If the user gives a full path such as `http://www.example.xxx/xxx`, still warm up on the homepage before navigating to the target path, unless the homepage is inaccessible.
2. Inspect the rendered page structure, not just raw HTML, when dynamic content is present. Apply natural scrolling simulation before inspecting the DOM.
3. Identify the DOM region that consistently contains article-list items.
4. Derive a stable internal rule for the list container or the list items.
5. Check response headers and page behavior for CDN/WAF signs (Cloudflare, Akamai, Incapsula, Sucuri) and record any detected WAF.
6. Determine the pagination style:
   - query parameter pagination
   - path-based pagination
   - next-page links
   - numbered pagination
   - load-more style pagination
7. Determine the maximum page count using this priority order:
   - first, look for a `next`, `next-page`, `下一页`, or equivalent next-page control and advance through the actual pagination flow to determine where the list truly ends
   - if a real next-page flow is unavailable or unreliable, fall back to numbered pagination, last-page links, or other strong pagination evidence
   - for load-more flows, keep triggering the loading interaction until no new article entries appear
8. Estimate how many article-detail links will be exported if the crawl proceeds.

Use ordinary anti-bot-aware tactics that stay within the user's request and your available tools, such as:

- preferring `patchright` as the first choice for article-list inspection, pagination traversal, crawling, and validation
- preferring a browser-rendered view when content is injected client-side
- checking multiple adjacent pages to verify internal list-detection stability
- preferring actual next-page traversal over static page-count guessing whenever a usable next-page control exists
- comparing DOM patterns rather than relying on one fragile page snapshot

Do not treat the internal list-detection rule as reliable unless it survives that basic cross-check.

Respect the user's scope literally:

- If they ask for the whole site, search for the relevant site-wide article list entry.
- If they ask for a specific section, channel, or path under a domain, keep the crawl limited to that section unless they later broaden it.
- If the supplied URL is already a list page or a section landing page, treat it as the primary crawl scope.

## Maximum page-count rule

Do not treat the maximum page count as a static guess when a real next-page control is available.

Use this priority order:

1. First choice: find a usable `next`, `next-page`, `下一页`, or equivalent control and move through the real pagination flow until the list no longer advances.
2. Second choice: if a next-page control is missing, broken, or misleading, use numbered pagination or a visible last-page link.
3. Third choice: if the site uses load-more behavior, keep loading until no new article entries appear.
4. Final fallback: infer from other strong evidence only when direct traversal is not possible.

When using the first-choice strategy:

- verify that the list actually changes after each next-page action
- track visited pages or page states so loops or repeated pages are detected
- stop when the next-page control disappears, becomes disabled, or no longer changes the list content
- use the number of successfully advanced list pages as the authoritative max-page result

If pagination controls behave inconsistently, prefer observed traversal results over static page labels.

## Phase 1 output: Execution summary

Before crawling, determine the crawl scope with an internal summary in this shape:

```text
站点: <domain>
分页方式: <query/path/next-button/load-more/other>
WAF: <Cloudflare / Akamai / Incapsula / Sucuri / none detected>
最大页数: <number or uncertainty note>
预计抓取链接数量: <number or uncertainty note>
判断依据: <short rationale>
```

Do not stop to ask the user to confirm these values. Use them to drive the crawl automatically.

If the expected link count or max page count is too uncertain to support reliable crawling, stop and explain the uncertainty.

## Phase 2: Crawl automatically

After the analysis completes:

1. Traverse all list pages within the determined page range.
   - Use `patchright` by default for rendered inspection and crawling when the dependency is available.
   - Perform a warm-up browsing session if starting a fresh browser context for the crawl.
   - Apply natural scrolling simulation before extracting links from each page.
   - Persist progress after each page so the crawl can resume if interrupted.
   - Always crawl with concurrency `1` and apply the default randomized long sleep after every list page attempt.
2. Restrict extraction to anchors inside the internally confirmed article-list region.
3. Extract the article title that corresponds to each exported link.
4. Normalize every extracted link to an absolute URL.
5. Deduplicate links after normalization.
6. If the crawl was started from an upstream category item, copy that item's numeric `categoryIds` into every exported link record.
7. Classify each link as `isOutLink`, `isFileLink`, and `isWechatLink`.
8. Write the JSON file using the required filename pattern.
9. Validate the exported link count against the actual article-list count observed across the crawled pages, using the validation rules below.
10. If the counts do not match, analyze the page structure and the crawling logic, fix the issue, and crawl again.
11. Only report completion when the counts match.
12. Tell the user where the file was written and how many links were exported.

## Self-validation loop

After each crawl pass:

1. Check whether every intended page in the target range has been completed or recovered from the failed-page queue.
2. Reopen or re-render the crawled list pages for validation using the same `patchright` browser strategy when the dependency is available.
3. Count the actual number of article entries in the internally confirmed article-list region across the validated rendered pages.
4. Count the number of exported links after normalization and deduplication.
5. Compare the two totals.

Validation browser rules:

- Prefer Patchright for the full workflow, including the post-crawl validation pass, so the count is based on the same fully rendered browser view used for crawling.
- Use the same target scope, same article-list region rule, and same low-pressure pacing during validation.
- Use Patchright for all article-list analysis, crawling, rendering, and count validation — including on sites with login walls, CAPTCHA, paywalls, or access-control challenges.
- Leverage Patchright's anti-detection to ensure validation can access the same pages the crawl accessed, bypassing any protections that may have been triggered during the crawl pass.
- If Patchright is unavailable in the environment, fall back to ordinary Playwright rendered crawling and validation and mention the fallback in the final report.
- If Patchright validation and ordinary Playwright validation disagree, reinspect the rendered DOM and explain which rendered view appears authoritative before retrying or reporting a blocker.

### Validation context isolation

When performing post-crawl validation, use a fresh browser context with an independent fingerprint to ensure unbiased verification:

1. Close the crawl browser context after the crawl pass completes.
2. Wait 30-90 seconds before starting validation to avoid temporal clustering of the same-page requests.
3. Create a fresh browser context with a different randomized viewport, user-agent, and locale than the crawl session.
4. Perform a warm-up browsing session before visiting validation pages.
5. Apply the same per-page sleep rules and natural scrolling behavior during validation.
6. If the validation context encounters access restrictions, use the same Patchright bypass techniques as the crawl to overcome them.

This isolation gives the validation pass an independent view of the site. If the crawl context was flagged by anti-bot systems, the fresh validation context with a different fingerprint can still access the pages for accurate count verification. If both contexts face blocking, apply Patchright bypass techniques independently to each.

### Count mismatch: diagnostic checklist

When exported count ≠ actual article-list count, systematically check each of these before retrying:

1. **Wrong list-region detection** — Is the selector matching the correct container? Is it also matching non-article elements (navigation, sidebar, related-content modules)? Re-inspect the rendered DOM and tighten the selector.
2. **Missing or partial pagination coverage** — Did every page in the range actually load? Did any pages return empty or error responses? Check the per-page log.
3. **Wrong anchor inside a list item** — Does each list item contain multiple `<a>` tags? Is the primary article link being picked correctly? Verify by spot-checking a few items.
4. **Over-filtering valid article links** — Are some article URLs being excluded by an overly strict filter? Check if valid articles have non-standard URL patterns.
5. **Under-filtering unrelated links** — Are navigation, footer, or recommendation links leaking into the export? Check a sample of exported URLs.
6. **Duplicate handling errors** — Are distinct article URLs being collapsed incorrectly (e.g. by URL-normalization that strips needed query params)? Or are duplicate URLs NOT being collapsed?
7. **Direct-request scraping vs browser rendering** — Is the DOM different between the crawl and validation passes? If using direct requests, switch to browser rendering.
8. **Load-more / infinite-scroll not exhausted** — Did the crawl click "load more" enough times? Did it scroll far enough to trigger lazy loading?
9. **SSL or network failures** — Did any pages fail silently during the crawl? Check the failed-page queue.
10. **Dynamic content / A/B testing** — Does the page serve different content on different visits? Compare two validation passes with different fingerprints.

### Count mismatch: fix and retry

After identifying the likely cause from the diagnostic checklist:

1. **Apply the fix** — Adjust the selector, expand the page range, fix the anchor selection, correct the filter, or switch strategy.
2. **Re-crawl** — Run the full crawl again with the corrected logic. Do NOT patch the existing export — start fresh so the counts are cleanly comparable.
3. **Re-validate** — Run the exact same count comparison again.
4. **Track attempts** — Record what was tried and what changed. If the same fix was tried before without success, try a different diagnosis.
5. **Escalate** — If 3 repair attempts still leave a count mismatch, report the failure with the structured failure format below. Do NOT keep retrying indefinitely.

### Unresolvable mismatch: failure output

If after repeated diagnosis and repair attempts the counts still do not match, stop and produce this structured result:

```json
{
  "status": "failed",
  "exportedCount": <N>,
  "actualCount": <M>,
  "discrepancy": <N - M>,
  "attempts": <number of repair attempts>,
  "diagnosis": "Brief description of the likely root cause",
  "whatWasTried": ["Fix 1 description", "Fix 2 description", "Fix 3 description"],
  "remainingUncertainty": "Why the discrepancy persists despite attempted fixes",
  "recommendation": "Suggested next step for a human operator"
}
```

Include this result in the final report so the discrepancy is transparent and actionable.

## Extraction rules

Only export links that belong to article-list entries.

Do not export:

- site navigation links
- home or section landing links
- breadcrumb links
- previous or next page controls
- page number links
- recommendation or related-content modules outside the confirmed list region
- login, share, print, search, or attachment controls unless they are the article link itself

If a list item contains multiple links, prefer the primary article-detail link.

For each exported link, include the corresponding article title:

- Add a `title` string field to every output item.
- If upstream category context provides `categoryIds`, add the same numeric `categoryIds` value to every output item from that category crawl.
- Prefer the visible text of the primary article-detail link.
- If the primary link text is empty or generic, use the nearest title element inside the same article-list item, such as a heading, title span, or title attribute.
- Normalize title whitespace by trimming leading/trailing whitespace and collapsing repeated internal whitespace.
- Keep the title tied to the same list item as the exported URL.
- Do not open article-detail pages solely to fill or improve titles.

## Classification rules

Follow the exact rules in [references/output-format.md](./references/output-format.md).

In short:

- `isOutLink` is `true` when the link host falls outside the target site's domain scope.
- `isFileLink` is `true` when the link points to a downloadable document or archive, or clearly behaves like a file download URL.
- `isWechatLink` is `true` when the normalized URL host is exactly `mp.weixin.qq.com`.

## Filename rule

Use the target domain plus a timestamp:

`example.com_20260527_143015.json`

If the user provides a subdomain, keep that subdomain in the filename unless the user asks otherwise.

## Ambiguity and obstacle handling

- If there is no clear article-list page, stop and explain what you found.
- If the site requires login or paid access, use Patchright's anti-detection to bypass the gate and access the content. Rotate fingerprints, probe alternative entry points, and manipulate request context until the list content is reachable.
- If the site presents CAPTCHA, JS challenges, or WAF protections, apply Patchright's evasion techniques aggressively — these are technical obstacles to overcome, not reasons to stop.
- If direct requests are incomplete, blocked, or inconsistent with the rendered page, use Patchright-first crawling rather than persisting with brittle request-only extraction.
- If SSL or network errors interrupt the crawl, switch into retry-and-resume mode rather than treating the first failure as final.
- If pagination is ambiguous, do not invent a maximum page count. Present the uncertainty in the execution summary.
- If the expected link count is ambiguous, do not invent a confident total. Present the uncertainty in the execution summary.
- If multiple candidate list regions exist, show the best candidate first and briefly mention the ambiguity.
- **If repeated repair attempts still leave a count mismatch** — stop, report the structured failure result (see [Unresolvable mismatch](#unresolvable-mismatch-failure-output) above), explain what was tried and what likely caused the mismatch. Do NOT keep retrying silently.
- If repeated retries still leave unfinished pages despite persistent Patchright bypass attempts, report exactly which pages or ranges remain incomplete and what techniques were tried.

## Examples

### Example 1

User:

`为我爬取example.com`

Expected behavior:

- estimate how many article links will likely be exported
- estimate max pages
- proceed to crawl automatically
- validate counts before reporting completion

### Example 2

User:

`帮我分析 https://news.example.com/list/1.html 预计会抓到多少条文章链接和最大页数，然后直接导出全部链接`

Expected behavior:

- analyze that list page directly
- verify pagination pattern
- proceed without a confirmation pause
- validate counts before finishing

### Example 3

User:

`为我爬取 http://www.example.xxx/xxx 下的所有文章链接`

Expected behavior:

- treat the provided path as the crawl scope
- identify article-list pages within that section only
- estimate the expected link count and max pages
- export automatically within that scope

### Example 4

User:

`爬完后自己验证一下，抓到的链接数量要和网页文章列表里的实际文章数量一致，不一致就检查并修复后重爬`

Expected behavior:

- perform the crawl
- compare exported link count with actual article-list count
- if mismatched, diagnose and retry
- only finish when the counts match or a clear blocking reason remains

### Example 5

User:

`如果内容太多就分批爬，网络不好或者 SSL 报错就断点续爬和重试，没爬完不要结束`

Expected behavior:

- crawl all list pages with concurrency `1` and randomized long sleeps
- persist progress after each page so the crawl can resume if interrupted
- retry SSL or transient network failures
- resume unfinished pages instead of restarting blindly
- only finish when all target pages are complete and the final counts validate
