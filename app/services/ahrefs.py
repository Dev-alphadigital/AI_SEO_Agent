"""Ahrefs API v3 client for SEO metrics."""
import logging
from datetime import date
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


def _today() -> str:
    """Return today's date as YYYY-MM-DD for Ahrefs date param."""
    return date.today().isoformat()


async def get_domain_metrics(target: str) -> AhrefsMetrics:
    """Get domain-level Ahrefs metrics (DR, backlinks, referring domains, organic)."""
    domain = _domain(target)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Domain Rating
            resp = await client.get(
                f"{BASE_URL}/site-explorer/domain-rating",
                headers=_headers(),
                params={"target": domain, "date": _today(), "output": "json"},
            )
            resp.raise_for_status()
            dr_data = resp.json().get("domain_rating", {})

            # Site metrics (organic keywords, traffic)
            resp2 = await client.get(
                f"{BASE_URL}/site-explorer/metrics",
                headers=_headers(),
                params={
                    "target": domain,
                    "date": _today(),
                    "output": "json",
                    "select": "org_keywords,org_traffic",
                },
            )
            resp2.raise_for_status()
            met = resp2.json().get("metrics", {})

            # Backlinks stats
            resp3 = await client.get(
                f"{BASE_URL}/site-explorer/backlinks-stats",
                headers=_headers(),
                params={"target": domain, "date": _today(), "output": "json"},
            )
            resp3.raise_for_status()
            bl = resp3.json().get("metrics", {})

        return AhrefsMetrics(
            domain_rating=dr_data.get("domain_rating", 0),
            backlinks=bl.get("live", 0),
            referring_domains=bl.get("live_refdomains", 0),
            organic_keywords=met.get("org_keywords", 0),
            organic_traffic=met.get("org_traffic", 0),
        )
    except Exception as e:
        logger.warning("Ahrefs domain metrics failed for %s: %s", target, e)
        return AhrefsMetrics()


async def get_keyword_metrics(keyword: str, country: str = "us") -> KeywordMetrics:
    """Get keyword-level metrics (volume, difficulty, CPC, intent)."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{BASE_URL}/keywords-explorer/overview",
                headers=_headers(),
                params={
                    "keywords": keyword,
                    "country": country,
                    "output": "json",
                    "select": "volume,difficulty,cpc,traffic_potential,intents",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        kw = data.get("keywords", [{}])[0] if data.get("keywords") else {}

        # Parse search intent from Ahrefs intents dict
        intents = kw.get("intents", {})
        intent = ""
        if intents:
            intent = max(intents, key=intents.get) if intents else ""

        # Ahrefs returns CPC in cents — convert to dollars
        raw_cpc = kw.get("cpc", 0) or 0
        cpc = raw_cpc / 100 if raw_cpc > 10 else raw_cpc

        return KeywordMetrics(
            keyword=keyword,
            volume=kw.get("volume", 0) or 0,
            difficulty=kw.get("difficulty", 0) or 0,
            cpc=cpc,
            traffic_potential=kw.get("traffic_potential", 0) or 0,
            intent=intent,
        )
    except Exception as e:
        logger.warning("Ahrefs keyword metrics failed for '%s': %s", keyword, e)
        return KeywordMetrics(keyword=keyword)


async def get_serp_overview(keyword: str, country: str = "us") -> list[SerpEntry]:
    """Get top 10 SERP results for a keyword."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{BASE_URL}/serp-overview/serp-overview",
                headers=_headers(),
                params={
                    "keyword": keyword,
                    "country": country,
                    "date": _today(),
                    "output": "json",
                    "select": "position,url,title,domain_rating",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        entries = []
        for pos in data.get("positions", []):
            url = pos.get("url")
            if not url:
                continue  # Skip SERP features (PAA, snippets) with no URL
            entries.append(SerpEntry(
                position=pos.get("position", 0),
                url=url,
                title=pos.get("title", ""),
                domain_rating=pos.get("domain_rating", 0) or 0,
            ))
        return entries[:10]
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
                params={"target": domain, "date": _today(), "output": "json"},
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning("Ahrefs backlinks summary failed for %s: %s", target, e)
        return {}
