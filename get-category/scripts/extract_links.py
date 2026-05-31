import argparse
import asyncio
import json
import random
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urldefrag, urlparse
from urllib.request import Request, urlopen

try:
    from patchright.async_api import async_playwright

    HAS_PATCHRIGHT = True
except ImportError:
    async_playwright = None  # type: ignore[assignment]
    HAS_PATCHRIGHT = False

SKIP_SCHEMES = ("javascript:", "mailto:", "tel:", "sms:", "data:")
LOCATION_TAGS = ("nav", "header", "footer", "aside", "main")


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class LinkParser(HTMLParser):
    """Parse HTML and extract all visible <a> tag candidates with location context."""

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.stack: list[str] = []
        self.links: list[dict[str, str]] = []
        self._active_link: dict[str, str] | None = None
        self._active_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self.stack.append(tag)
        if tag != "a":
            return

        attr_map = {name.lower(): value for name, value in attrs if value is not None}
        href = attr_map.get("href", "").strip()
        if not href or href.startswith("#") or href.lower().startswith(SKIP_SCHEMES):
            return

        absolute_url = urldefrag(urljoin(self.base_url, href))[0]
        self._active_link = {
            "url": absolute_url,
            "location": self._current_location(),
        }
        self._active_text = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "a" and self._active_link is not None:
            text = normalize_space("".join(self._active_text))
            if text:
                self.links.append(
                    {
                        "text": text,
                        "url": self._active_link["url"],
                        "location": self._active_link["location"],
                    }
                )
            self._active_link = None
            self._active_text = []

        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if self._active_link is not None:
            self._active_text.append(data)

    def _current_location(self) -> str:
        for tag in reversed(self.stack):
            if tag in LOCATION_TAGS:
                return tag
        return "body"


def extract_candidates(html: str, base_url: str) -> list[dict[str, str]]:
    """Parse static or rendered HTML and return deduplicated link candidates."""
    parser = LinkParser(base_url)
    parser.feed(html)
    return dedupe_links(parser.links)


def dedupe_links(links: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for link in links:
        key = (link["text"].casefold(), link["url"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(link)
    return unique


def _fetch_html_static(url: str, timeout: int = 20) -> str:
    """Fetch page HTML via plain HTTP request (no JS rendering)."""
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "")
        charset_match = re.search(r"charset=([\w.-]+)", content_type, re.I)
        charset = charset_match.group(1) if charset_match else "utf-8"
        return response.read().decode(charset, errors="replace")


def save_candidates(candidates: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Patchright browser helpers
# ---------------------------------------------------------------------------

_CHROME_VERSION_RANGE = (120, 130)
_VIEWPORT_WIDTH_RANGE = (1280, 1440)
_VIEWPORT_HEIGHT_RANGE = (720, 900)
_DEVICE_SCALE_FACTORS = (1, 1.25, 1.5, 2)
_WARMUP_HOMEPAGE_TIMEOUT = 30_000
_TARGET_PAGE_TIMEOUT = 30_000


def _random_viewport() -> dict[str, int]:
    return {
        "width": random.randint(*_VIEWPORT_WIDTH_RANGE),
        "height": random.randint(*_VIEWPORT_HEIGHT_RANGE),
    }


def _random_user_agent() -> str:
    major = random.randint(*_CHROME_VERSION_RANGE)
    return (
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.0.0 Safari/537.36"
    )


def _random_dsf() -> float:
    return random.choice(_DEVICE_SCALE_FACTORS)


async def _warm_up(page, domain: str) -> None:
    """Visit the site homepage and perform natural scrolling to establish
    session cookies, a plausible Referer chain, and server-side session state
    before navigating to the actual target page."""
    homepage = f"https://{domain}"
    try:
        await page.goto(homepage, wait_until="domcontentloaded", timeout=_WARMUP_HOMEPAGE_TIMEOUT)
    except Exception:
        # Warm-up is best-effort; proceed even if the homepage is unreachable.
        return

    await asyncio.sleep(random.uniform(3, 8))

    # Gradual scroll down
    await page.evaluate("window.scrollBy(0, 300)")
    await asyncio.sleep(random.uniform(0.5, 1.5))
    await page.evaluate("window.scrollBy(0, 200)")
    await asyncio.sleep(random.uniform(0.5, 1.0))
    # Partial scroll back up
    await page.evaluate("window.scrollBy(0, -150)")
    await asyncio.sleep(random.uniform(0.3, 1.0))


async def _simulate_natural_browsing(page) -> None:
    """After the target page loads, simulate natural human browsing behavior
    to trigger lazy-loaded content and avoid bot-detection heuristics."""
    await asyncio.sleep(random.uniform(1, 3))

    # Gradual scroll down in small increments
    for _ in range(random.randint(2, 4)):
        delta = random.randint(150, 400)
        await page.evaluate(f"window.scrollBy(0, {delta})")
        await asyncio.sleep(random.uniform(0.3, 0.8))

    # Pause mid-page
    await asyncio.sleep(random.uniform(0.5, 1.5))

    # Scroll back to top so all nav regions are in view
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(random.uniform(0.3, 0.7))


async def extract_candidates_patchright(url: str, timeout: int = 30) -> list[dict[str, str]]:
    """Launch a Patchright browser, warm up on the site, navigate to *url*,
    wait for JS rendering, simulate natural browsing, then extract all visible
    ``<a>`` candidates from the fully rendered DOM.

    Returns the same ``[{text, url, location}, ...]`` shape as the static
    ``extract_candidates()`` parser so downstream tooling is unchanged.
    """
    if not HAS_PATCHRIGHT:
        raise RuntimeError(
            "patchright is not installed. Install it with: pip install patchright\n"
            "Then run: patchright install chromium\n"
            "Or use --no-browser for static HTML fallback."
        )

    domain = urlparse(url).netloc

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
            viewport=_random_viewport(),
            user_agent=_random_user_agent(),
            device_scale_factor=_random_dsf(),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )

        page = await context.new_page()

        try:
            # Phase 1 — establish session via homepage warm-up
            await _warm_up(page, domain)

            # Phase 2 — navigate to the actual target page
            await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)

            # Phase 3 — simulate natural browsing (triggers lazy content,
            #          avoids naive bot-detection scripts)
            await _simulate_natural_browsing(page)

            # Phase 4 — grab the fully rendered HTML and feed it through the
            #          same deterministic parser used by the static path
            html = await page.content()
        finally:
            await browser.close()

    return extract_candidates(html, url)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch a page and save candidate links for category detection. "
            "Uses Patchright (Playwright fork with anti-detection) by default "
            "so JavaScript-heavy and mildly protected pages render correctly. "
            "Pass --no-browser for a lightweight static-HTTP fallback."
        )
    )
    parser.add_argument("url", help="Page URL to inspect")
    parser.add_argument(
        "-o",
        "--output",
        default="candidate-links.json",
        help="Path for candidate link JSON",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Use static urllib fetch + HTMLParser instead of Patchright rendering",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Page load timeout in seconds (Patchright mode only)",
    )
    args = parser.parse_args(argv)

    if args.no_browser:
        html = _fetch_html_static(args.url)
        candidates = extract_candidates(html, args.url)
    else:
        try:
            candidates = asyncio.run(
                extract_candidates_patchright(args.url, timeout=args.timeout)
            )
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    save_candidates(candidates, Path(args.output))
    print(f"Saved {len(candidates)} candidate links to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
