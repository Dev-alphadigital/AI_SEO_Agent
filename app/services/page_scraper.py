"""Page scraper — extracts on-page SEO elements from a URL."""
import asyncio
import json
import logging
import random
from urllib.parse import urlparse, urljoin

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser

from app.models.schemas import PageSEO

logger = logging.getLogger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
]

# Browser singleton
_browser: Browser | None = None
_pw_instance = None
_browser_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    """Lazy-init asyncio.Lock (can't create at module import time)."""
    global _browser_lock
    if _browser_lock is None:
        _browser_lock = asyncio.Lock()
    return _browser_lock


async def _get_browser() -> Browser:
    """Launch or reuse a shared Chromium instance, protected by lock."""
    global _browser, _pw_instance
    async with _get_lock():
        if _browser is None or not _browser.is_connected():
            _pw_instance = await async_playwright().start()
            _browser = await _pw_instance.chromium.launch(headless=True)
            logger.info("Playwright Chromium browser launched")
        return _browser


async def close_browser() -> None:
    """Shut down the shared browser and Playwright instance."""
    global _browser, _pw_instance
    async with _get_lock():
        if _browser is not None:
            await _browser.close()
            _browser = None
        if _pw_instance is not None:
            await _pw_instance.stop()
            _pw_instance = None
            logger.info("Playwright browser closed")


def _request_headers() -> dict[str, str]:
    """Return realistic browser headers to avoid bot detection."""
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }


def _get_meta_content(soup: BeautifulSoup, attrs: dict) -> str:
    """Extract content attribute from a meta tag, or empty string."""
    tag = soup.find("meta", attrs=attrs)
    return tag.get("content", "").strip() if tag else ""


_CHALLENGE_PHRASES = (
    "just a moment",
    "attention required",
    "access denied",
    "please wait",
    "checking your browser",
)


def _looks_like_bot_challenge(title: str, h1: str, status_code: int) -> bool:
    """Return True when the response looks like a bot challenge page."""
    if status_code != 200:
        return False
    if h1:
        return False
    if not title:
        return True
    return any(phrase in title.lower() for phrase in _CHALLENGE_PHRASES)


async def _fetch_html_playwright(url: str) -> str:
    """Fetch a page using headless Chromium (bypasses JS challenges)."""
    browser = await _get_browser()
    context = await browser.new_context(
        user_agent=random.choice(_USER_AGENTS),
        viewport={"width": 1920, "height": 1080},
    )
    try:
        page = await context.new_page()
        await page.goto(url, wait_until="networkidle", timeout=30000)
        return await page.content()
    finally:
        await context.close()


async def _fetch_html(url: str) -> httpx.Response:
    """Fetch URL with retry on 403 using a different user-agent."""
    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=True,
        http2=True,
    ) as client:
        resp = await client.get(url, headers=_request_headers())
        if resp.status_code == 403:
            # Retry with a Google cache-style referer and different UA
            retry_headers = _request_headers()
            retry_headers["Referer"] = "https://www.google.com/"
            resp = await client.get(url, headers=retry_headers)
        resp.raise_for_status()
        return resp


def _parse_html(html: str, url: str) -> PageSEO:
    """Parse HTML and extract all SEO-relevant elements."""
    soup = BeautifulSoup(html, "lxml")
    parsed_url = urlparse(url)
    base_domain = parsed_url.netloc

    # Title
    title = soup.title.get_text(strip=True) if soup.title else ""

    # Meta description
    meta_description = _get_meta_content(soup, {"name": "description"})

    # Canonical
    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    canonical_url = canonical_tag.get("href", "").strip() if canonical_tag else ""

    # Robots
    robots = _get_meta_content(soup, {"name": "robots"})

    # Viewport
    has_viewport = soup.find("meta", attrs={"name": "viewport"}) is not None

    # Lang
    html_tag = soup.find("html")
    lang = html_tag.get("lang", "").strip() if html_tag else ""

    # Open Graph tags
    og_title = _get_meta_content(soup, {"property": "og:title"})
    og_description = _get_meta_content(soup, {"property": "og:description"})
    og_image = _get_meta_content(soup, {"property": "og:image"})
    og_type = _get_meta_content(soup, {"property": "og:type"})

    # Twitter Card tags
    twitter_card = _get_meta_content(soup, {"name": "twitter:card"})
    twitter_title = _get_meta_content(soup, {"name": "twitter:title"})
    twitter_description = _get_meta_content(soup, {"name": "twitter:description"})

    # Headings
    h1 = ""
    h1_tag = soup.find("h1")
    if h1_tag:
        h1 = h1_tag.get_text(strip=True)

    h2s = [tag.get_text(strip=True) for tag in soup.find_all("h2")]
    h3s = [tag.get_text(strip=True) for tag in soup.find_all("h3")]

    # Images
    images = soup.find_all("img")
    image_count = len(images)
    images_with_alt = sum(1 for img in images if img.get("alt", "").strip())

    # Schema / structured data detection
    schema_types: list[str] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and "@type" in item:
                    t = item["@type"]
                    if isinstance(t, list):
                        schema_types.extend(str(x) for x in t)
                    else:
                        schema_types.append(str(t))
        except (json.JSONDecodeError, TypeError):
            pass
    has_schema_markup = len(schema_types) > 0

    # Word count — visible text only (decompose non-visible elements)
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()
    visible_text = soup.get_text(separator=" ", strip=True)
    word_count = len(visible_text.split())

    # Links — internal vs external
    internal_links = 0
    external_links = 0
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        absolute = urljoin(url, href)
        link_domain = urlparse(absolute).netloc
        if link_domain == base_domain:
            internal_links += 1
        else:
            external_links += 1

    return PageSEO(
        url=url,
        title=title,
        title_length=len(title),
        meta_description=meta_description,
        meta_description_length=len(meta_description),
        canonical_url=canonical_url,
        h1=h1,
        h2s=h2s,
        h3s=h3s,
        word_count=word_count,
        internal_links=internal_links,
        external_links=external_links,
        og_title=og_title,
        og_description=og_description,
        og_image=og_image,
        og_type=og_type,
        twitter_card=twitter_card,
        twitter_title=twitter_title,
        twitter_description=twitter_description,
        robots=robots,
        has_viewport=has_viewport,
        lang=lang,
        image_count=image_count,
        images_with_alt=images_with_alt,
        has_schema_markup=has_schema_markup,
        schema_types=schema_types,
    )


async def scrape_page(url: str) -> PageSEO:
    """Scrape a URL and extract SEO-relevant elements."""
    try:
        resp = await _fetch_html(url)

        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type:
            logger.warning("Non-HTML response from %s: %s", url, content_type)
            return PageSEO(url=url)

        result = _parse_html(resp.text, url)

        # Detect bot challenge pages and retry with Playwright
        if _looks_like_bot_challenge(result.title, result.h1, resp.status_code):
            logger.info("Bot challenge detected for %s — trying Playwright fallback", url)
            try:
                pw_html = await _fetch_html_playwright(url)
                pw_result = _parse_html(pw_html, url)
                logger.info("Playwright fallback succeeded for %s", url)
                return pw_result
            except Exception as pw_err:
                logger.warning(
                    "Playwright fallback failed for %s: %s — returning httpx result",
                    url, pw_err,
                )
                return result

        return result
    except Exception as e:
        logger.warning("Page scrape failed for %s: %s", url, e)
        return PageSEO(url=url)
