"""Page scraper — extracts on-page SEO elements from a URL."""
import json
import logging
from urllib.parse import urlparse, urljoin

import httpx
from bs4 import BeautifulSoup

from app.models.schemas import PageSEO

logger = logging.getLogger(__name__)


def _get_meta_content(soup: BeautifulSoup, attrs: dict) -> str:
    """Extract content attribute from a meta tag, or empty string."""
    tag = soup.find("meta", attrs=attrs)
    return tag.get("content", "").strip() if tag else ""


async def scrape_page(url: str) -> PageSEO:
    """Scrape a URL and extract SEO-relevant elements."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; SEOBot/1.0)",
            })
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type:
            logger.warning("Non-HTML response from %s: %s", url, content_type)
            return PageSEO(url=url)

        soup = BeautifulSoup(resp.text, "lxml")
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
                if isinstance(data, dict) and "@type" in data:
                    schema_types.append(data["@type"])
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "@type" in item:
                            schema_types.append(item["@type"])
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
    except Exception as e:
        logger.warning("Page scrape failed for %s: %s", url, e)
        return PageSEO(url=url)
