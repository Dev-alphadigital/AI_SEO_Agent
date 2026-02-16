"""Ahrefs API v3 client for SEO metrics."""
import logging
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.models.schemas import AhrefsMetrics, KeywordMetrics, SerpEntry

logger = logging.getLogger(__name__)

BASE_URL = "https://api.ahrefs.com/v3"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_settings().ahrefs_api_key}",
        "Accept": "application/json",
    }


def _domain(url: str) -> str:
    """Extract domain from a URL."""
    parsed = urlparse(url)
    return parsed.netloc or parsed.path


async def get_domain_metrics(target: str) -> AhrefsMetrics:
    """Get domain-level Ahrefs metrics (DR, UR, backlinks, referring domains)."""
    domain = _domain(target)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{BASE_URL}/site-explorer/domain-rating",
                headers=_headers(),
                params={"target": domain, "output": "json"},
            )
            resp.raise_for_status()
            dr_data = resp.json()

            resp2 = await client.get(
                f"{BASE_URL}/site-explorer/metrics",
                headers=_headers(),
                params={"target": domain, "output": "json"},
            )
            resp2.raise_for_status()
            metrics_data = resp2.json()

        return AhrefsMetrics(
            domain_rating=dr_data.get("domain_rating", 0),
            url_rating=metrics_data.get("metrics", {}).get("url_rating", 0),
            backlinks=metrics_data.get("metrics", {}).get("backlinks", 0),
            referring_domains=metrics_data.get("metrics", {}).get("refdomains", 0),
            organic_keywords=metrics_data.get("metrics", {}).get("org_keywords", 0),
            organic_traffic=metrics_data.get("metrics", {}).get("org_traffic", 0),
        )
    except Exception as e:
        logger.warning("Ahrefs domain metrics failed for %s: %s", target, e)
        return AhrefsMetrics()


async def get_keyword_metrics(keyword: str, country: str = "us") -> KeywordMetrics:
    """Get keyword-level metrics (volume, difficulty, CPC)."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{BASE_URL}/keywords-explorer/overview",
                headers=_headers(),
                params={
                    "keyword": keyword,
                    "country": country,
                    "output": "json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        kw = data.get("keywords", [{}])[0] if data.get("keywords") else {}
        return KeywordMetrics(
            keyword=keyword,
            volume=kw.get("volume", 0),
            difficulty=kw.get("difficulty", 0),
            cpc=kw.get("cpc", 0.0),
            traffic_potential=kw.get("traffic_potential", 0),
        )
    except Exception as e:
        logger.warning("Ahrefs keyword metrics failed for '%s': %s", keyword, e)
        return KeywordMetrics(keyword=keyword)


async def get_serp_overview(keyword: str, country: str = "us") -> list[SerpEntry]:
    """Get top 10 SERP results for a keyword."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{BASE_URL}/keywords-explorer/serp-overview",
                headers=_headers(),
                params={
                    "keyword": keyword,
                    "country": country,
                    "output": "json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        entries = []
        for pos in data.get("serp", [])[:10]:
            entries.append(SerpEntry(
                position=pos.get("position", 0),
                url=pos.get("url", ""),
                title=pos.get("title", ""),
                domain_rating=pos.get("domain_rating", 0),
            ))
        return entries
    except Exception as e:
        logger.warning("Ahrefs SERP overview failed for '%s': %s", keyword, e)
        return []


async def get_backlinks_summary(target: str) -> dict:
    """Get backlink count and referring domain stats."""
    domain = _domain(target)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{BASE_URL}/site-explorer/backlinks-stats",
                headers=_headers(),
                params={"target": domain, "output": "json"},
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning("Ahrefs backlinks summary failed for %s: %s", target, e)
        return {}
