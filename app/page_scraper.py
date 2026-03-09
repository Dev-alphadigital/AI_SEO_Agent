"""
Page scraper for SEO briefs — fetches metadata, headings, body text, links, and rich content.

Two-tier approach:
1. requests (fast) — works for most sites
2. Playwright fallback — for bot-blocked sites (Tesla, Nike, Goldman Sachs, etc.)

Used for:
- Current State (title, meta, H1, full heading hierarchy, body text)
- Issues to Fix (no H1, duplicate titles, thin content)
- Internal/external link extraction
- Rich content detection (tables, figures, images, charts)
"""

import re
from typing import Optional, Tuple
from urllib.parse import urlparse, urljoin

# Realistic browser headers (sometimes helps avoid blocks)
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


def _parse_html(html: str, source_url: str = "") -> dict:
    """Parse HTML and extract SEO metadata, body text, links, and rich content.

    Shared by requests and Playwright.
    """
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    title = (title_tag.get_text(strip=True) or "").strip() if title_tag else ""

    meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    meta_description = ""
    if meta and meta.get("content"):
        meta_description = (meta.get("content", "") or "").strip()

    h1_tag = soup.find("h1")
    h1 = (h1_tag.get_text(strip=True) or "").strip() if h1_tag else None

    # Extract ALL headings H1-H6 (classified by level)
    headings = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = (tag.get_text(strip=True) or "").strip()
        if text:
            headings.append(f"{tag.name}: {text}")

    # Extract links (internal vs external) before removing scripts/styles
    internal_links = []
    external_links = []
    source_domain = ""
    if source_url:
        parsed_source = urlparse(source_url)
        source_domain = (parsed_source.netloc or "").replace("www.", "").lower()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        anchor = (a_tag.get_text(strip=True) or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        # Resolve relative URLs
        full_url = urljoin(source_url, href) if source_url else href
        parsed_href = urlparse(full_url)
        href_domain = (parsed_href.netloc or "").replace("www.", "").lower()

        link_entry = {"anchor": anchor[:100], "url": full_url}
        if source_domain and href_domain == source_domain:
            internal_links.append(link_entry)
        elif href_domain:
            external_links.append(link_entry)

    # Detect rich content elements before decomposing
    rich_content = {
        "tables": len(soup.find_all("table")),
        "figures": len(soup.find_all("figure")),
        "images": len(soup.find_all("img")),
        "iframes": len(soup.find_all("iframe")),
        "canvas": len(soup.find_all("canvas")),
        "svg": len(soup.find_all("svg")),
        "videos": len(soup.find_all("video")),
    }

    # Extract body text (remove scripts/styles first)
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    body = soup.find("body")
    text = body.get_text(separator=" ", strip=True) if body else ""
    words = re.findall(r"\b\w+\b", text, re.UNICODE)
    word_count = len(words)

    # Full body text for Gemini context (content analysis needs complete page)
    body_text = " ".join(words[:15000]) if words else ""

    issues = []
    if not h1 or not h1.strip():
        issues.append("No H1 tag detected — add a single H1 with primary keyword")
    if title and h1 and _normalize_for_compare(title) == _normalize_for_compare(h1):
        issues.append("Duplicate title/H1 — title and H1 are identical; differentiate for SERP clarity")
    if word_count < 300:
        issues.append(f"Thin content — ~{word_count} words; consider 300+ for better rankings")

    return {
        "success": True,
        "error": None,
        "title": title,
        "meta_description": meta_description,
        "h1": h1,
        "headings": headings,
        "word_count": word_count,
        "body_text": body_text,
        "internal_links": internal_links[:50],  # Cap at 50 to avoid bloat
        "external_links": external_links[:30],
        "rich_content": rich_content,
        "issues": issues,
    }


def _scrape_with_requests(url: str, timeout: int) -> Tuple[Optional[str], Optional[str]]:
    """Try requests. Returns (html, error)."""
    if not HAS_REQUESTS:
        return None, "Install requests and beautifulsoup4"
    try:
        resp = requests.get(url, timeout=timeout, headers=BROWSER_HEADERS)
        resp.raise_for_status()
        return resp.text, None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code in (401, 403, 503, 429):
            return None, str(e)  # Likely blocked — try Playwright
        return None, str(e)
    except Exception as e:
        return None, str(e)


def _scrape_with_playwright(url: str, timeout: int) -> Tuple[Optional[str], Optional[str]]:
    """Fallback: use headless Chromium for bot-blocked sites."""
    if not HAS_PLAYWRIGHT:
        return None, "Install playwright and run: playwright install chromium"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=BROWSER_HEADERS["User-Agent"],
                locale="en-US",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            page.wait_for_load_state("networkidle", timeout=5000)
            html = page.content()
            browser.close()
            return html, None
    except Exception as e:
        return None, str(e)


def scrape_page(url: str, timeout: int = 20, force_playwright: bool = False) -> dict:
    """
    Scrape page for SEO metadata and content.

    Strategy:
    - If force_playwright: use Playwright only.
    - Else: try requests first; on 403/401/503/429, fall back to Playwright.

    Returns:
        {
            "success": bool,
            "error": str | None,
            "title": str,
            "meta_description": str,
            "h1": str | None,
            "headings": list[str],
            "word_count": int,
            "issues": list[str],
            "method": "requests" | "playwright" | None
        }
    """
    if not url.startswith("http"):
        url = "https://" + url

    html = None
    method = None
    last_error = None

    if force_playwright:
        html, last_error = _scrape_with_playwright(url, timeout)
        if html:
            method = "playwright"
    else:
        html, last_error = _scrape_with_requests(url, timeout)
        if html:
            method = "requests"
        elif last_error and HAS_PLAYWRIGHT:
            html, pw_err = _scrape_with_playwright(url, timeout)
            if html:
                method = "playwright"
                last_error = None
            else:
                last_error = pw_err or last_error

    if html:
        result = _parse_html(html, source_url=url)
        result["method"] = method

        # Retry with Playwright if headings look suspiciously sparse for a content-heavy page
        # (likely JS-rendered headings that requests can't see)
        if (result.get("success")
                and len(result.get("headings", [])) < 3
                and result.get("word_count", 0) > 500
                and HAS_PLAYWRIGHT
                and method != "playwright"):
            pw_html, pw_err = _scrape_with_playwright(url, timeout)
            if pw_html:
                pw_result = _parse_html(pw_html, source_url=url)
                if len(pw_result.get("headings", [])) > len(result.get("headings", [])):
                    pw_result["method"] = "playwright"
                    return pw_result

        return result

    return {
        "success": False,
        "error": last_error or "Scraping failed",
        "title": "",
        "meta_description": "",
        "h1": None,
        "headings": [],
        "word_count": 0,
        "body_text": "",
        "internal_links": [],
        "external_links": [],
        "rich_content": {},
        "issues": [],
        "method": None,
    }


def _normalize_for_compare(s: str) -> str:
    """Normalize string for duplicate detection."""
    return " ".join(s.lower().split())
