"""
Page scraper for SEO briefs — fetches metadata, headings, body text, links, and rich content.

Three-tier approach:
1. curl_cffi (impersonates real Chrome TLS fingerprint — best anti-bot bypass)
2. requests (fast, lightweight — works for most sites)
3. Playwright + stealth fallback — for JS-heavy pages that need rendering

Used for:
- Current State (title, meta, H1, full heading hierarchy, body text)
- Issues to Fix (no H1, duplicate titles, thin content)
- Internal/external link extraction
- Rich content detection (tables, figures, images, charts)
"""

import re
from typing import Optional, Tuple
from urllib.parse import urlparse, urljoin

# Realistic browser headers
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

try:
    from playwright_stealth import stealth_sync
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False


def _is_blocked(html: str) -> bool:
    """Check if HTML is a bot-block page (Access Denied, Captcha, etc.)."""
    if not html or len(html) < 1500:
        lower = html.lower() if html else ""
        if any(sig in lower for sig in [
            "access denied", "403 forbidden", "just a moment",
            "checking your browser", "captcha", "bot detection",
            "please verify you are a human",
        ]):
            return True
    return False


def _parse_html(html: str, source_url: str = "") -> dict:
    """Parse HTML and extract SEO metadata, body text, links, and rich content."""
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    title = (title_tag.get_text(strip=True) or "").strip() if title_tag else ""

    meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    meta_description = ""
    if meta and meta.get("content"):
        meta_description = (meta.get("content", "") or "").strip()

    h1_tag = soup.find("h1")
    h1 = (h1_tag.get_text(strip=True) or "").strip() if h1_tag else None

    # Extract ALL headings H1-H6
    headings = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = (tag.get_text(strip=True) or "").strip()
        if text:
            headings.append(f"{tag.name}: {text}")

    # Extract links (internal vs external)
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
        full_url = urljoin(source_url, href) if source_url else href
        parsed_href = urlparse(full_url)
        href_domain = (parsed_href.netloc or "").replace("www.", "").lower()

        link_entry = {"anchor": anchor[:100], "url": full_url}
        if source_domain and href_domain == source_domain:
            internal_links.append(link_entry)
        elif href_domain:
            external_links.append(link_entry)

    # Detect rich content elements
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
        "internal_links": internal_links[:50],
        "external_links": external_links[:30],
        "rich_content": rich_content,
        "issues": issues,
    }


def _scrape_with_curl_cffi(url: str, timeout: int) -> Tuple[Optional[str], Optional[str]]:
    """Primary: use curl_cffi to impersonate real Chrome TLS fingerprint.

    This bypasses most anti-bot systems (Cloudflare, Akamai, PerimeterX)
    because the TLS handshake, HTTP/2 fingerprint, and header order all
    match a real Chrome browser — unlike requests or Playwright.
    """
    if not HAS_CURL_CFFI:
        return None, "curl_cffi not installed"
    try:
        resp = cffi_requests.get(
            url,
            impersonate="chrome131",
            timeout=timeout,
            allow_redirects=True,
        )
        if resp.status_code == 200:
            html = resp.text
            if _is_blocked(html):
                return None, "Access denied (blocked by anti-bot)"
            return html, None
        elif resp.status_code in (401, 403, 503, 429):
            return None, f"HTTP {resp.status_code} (blocked)"
        else:
            return None, f"HTTP {resp.status_code}"
    except Exception as e:
        return None, str(e)


def _scrape_with_requests(url: str, timeout: int) -> Tuple[Optional[str], Optional[str]]:
    """Fallback 1: standard requests library."""
    if not HAS_REQUESTS:
        return None, "Install requests and beautifulsoup4"
    try:
        resp = requests.get(url, timeout=timeout, headers=BROWSER_HEADERS)
        resp.raise_for_status()
        html = resp.text
        if _is_blocked(html):
            return None, "Access denied (blocked by anti-bot)"
        return html, None
    except requests.exceptions.HTTPError as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)


def _scrape_with_playwright(url: str, timeout: int) -> Tuple[Optional[str], Optional[str]]:
    """Fallback 2: headless Chromium with stealth for JS-rendered pages."""
    if not HAS_PLAYWRIGHT:
        return None, "Install playwright and run: playwright install chromium"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--no-sandbox",
                ],
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                timezone_id="America/New_York",
                color_scheme="light",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                },
            )
            page = context.new_page()

            if HAS_STEALTH:
                stealth_sync(page)

            page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass

            html = page.content()
            browser.close()

            if _is_blocked(html):
                return None, "Access denied (blocked by anti-bot even with Playwright)"
            return html, None
    except Exception as e:
        return None, str(e)


def scrape_page(url: str, timeout: int = 20, force_playwright: bool = False) -> dict:
    """
    Scrape page for SEO metadata and content.

    Strategy (priority order):
    1. curl_cffi — impersonates real Chrome TLS fingerprint (best anti-bot bypass)
    2. requests — standard HTTP (fast, works for most sites)
    3. Playwright + stealth — headless browser for JS-rendered content

    If curl_cffi succeeds with good content, we still check if Playwright
    would yield more headings (for JS-rendered pages).
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
        # Tier 1: curl_cffi (best for anti-bot)
        if HAS_CURL_CFFI:
            html, last_error = _scrape_with_curl_cffi(url, timeout)
            if html:
                method = "curl_cffi"

        # Tier 2: requests (if curl_cffi unavailable or failed)
        if not html and HAS_REQUESTS:
            req_html, req_err = _scrape_with_requests(url, timeout)
            if req_html:
                html = req_html
                method = "requests"
                last_error = None
            elif req_err:
                last_error = last_error or req_err

        # Tier 3: Playwright (if both HTTP methods failed)
        if not html and HAS_PLAYWRIGHT:
            pw_html, pw_err = _scrape_with_playwright(url, timeout)
            if pw_html:
                html = pw_html
                method = "playwright"
                last_error = None
            elif pw_err:
                last_error = last_error or pw_err

    if html:
        result = _parse_html(html, source_url=url)
        result["method"] = method

        # If we got HTML but headings are sparse, try Playwright for JS-rendered content
        if (result.get("success")
                and len(result.get("headings", [])) < 3
                and result.get("word_count", 0) > 500
                and HAS_PLAYWRIGHT
                and method != "playwright"):
            pw_html, pw_err = _scrape_with_playwright(url, timeout)
            if pw_html and not _is_blocked(pw_html):
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
