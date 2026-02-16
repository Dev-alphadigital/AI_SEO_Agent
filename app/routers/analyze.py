"""Analyze endpoint — runs the full SEO brief pipeline."""
import asyncio
import logging
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.models.schemas import (
    AhrefsMetrics,
    KeywordMetrics,
    PageSEO,
    SEOBrief,
)
from app.services.ahrefs import get_domain_metrics, get_keyword_metrics
from app.services.brief_generator import generate_brief
from app.services.competitor_analysis import analyze_competitors, identify_gaps
from app.services.page_scraper import scrape_page

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    """Request model for analyze endpoint."""
    url: str
    keyword: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        parsed = urlparse(v)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("URL must include scheme and domain (e.g. https://example.com)")
        return v

    @field_validator("keyword")
    @classmethod
    def validate_keyword(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Keyword must not be empty")
        return v


@router.post("/analyze", response_model=SEOBrief)
async def analyze(request: AnalyzeRequest):
    """
    Run the full SEO analysis pipeline:
    1. Scrape target page
    2. Get Ahrefs metrics for target
    3. Get keyword metrics
    4. Get SERP overview + scrape competitors
    5. Run gap analysis
    6. Generate brief (JSON response + saved Markdown)
    """
    warnings: list[str] = []

    # Steps 1-3 run in parallel, with graceful degradation
    results = await asyncio.gather(
        scrape_page(request.url),
        get_domain_metrics(request.url),
        get_keyword_metrics(request.keyword),
        return_exceptions=True,
    )

    # Unpack with fallbacks
    if isinstance(results[0], PageSEO):
        target_seo = results[0]
    else:
        logger.warning("Page scrape failed: %s", results[0])
        warnings.append(f"Page scrape failed: {results[0]}")
        target_seo = PageSEO(url=request.url)

    if isinstance(results[1], AhrefsMetrics):
        ahrefs_data = results[1]
    else:
        logger.warning("Ahrefs domain metrics failed: %s", results[1])
        warnings.append(f"Ahrefs domain metrics unavailable: {results[1]}")
        ahrefs_data = AhrefsMetrics()

    if isinstance(results[2], KeywordMetrics):
        keyword_data = results[2]
    else:
        logger.warning("Keyword metrics failed: %s", results[2])
        warnings.append(f"Keyword metrics unavailable: {results[2]}")
        keyword_data = KeywordMetrics(keyword=request.keyword)

    # Step 4: Competitor analysis (SERP + scrape) — already handles errors internally
    serp_results, competitors = await analyze_competitors(
        request.keyword, request.url
    )
    if not competitors:
        warnings.append("No competitor data retrieved — gap analysis will be limited.")

    # Step 5: Gap analysis
    gaps = identify_gaps(target_seo, competitors)

    # Step 6: Generate brief
    brief = generate_brief(
        target_url=request.url,
        keyword=request.keyword,
        target_seo=target_seo,
        ahrefs_data=ahrefs_data,
        keyword_data=keyword_data,
        serp_results=serp_results,
        competitors=competitors,
        gaps=gaps,
        warnings=warnings,
    )

    return brief
