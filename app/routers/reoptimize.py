"""Reoptimize endpoint — runs SEO data pipeline + LLM reoptimization brief."""
import asyncio
import logging
import os
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.config import get_settings
from app.models.schemas import (
    AhrefsMetrics,
    KeywordMetrics,
    PageSEO,
    ReoptimizationBrief,
)
from app.services.ahrefs import get_domain_metrics, get_keyword_metrics
from app.services.competitor_analysis import analyze_competitors, identify_gaps
from app.services.llm_reoptimizer import generate_reoptimization_brief

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["reoptimize"])

OUTPUT_DIR = "output"


class ReoptimizeRequest(BaseModel):
    """Request model for reoptimize endpoint."""
    url: str
    keyword: str
    secondary_keywords: list[str] = []
    notes: str = ""

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


@router.post("/reoptimize", response_model=ReoptimizationBrief)
async def reoptimize(request: ReoptimizeRequest):
    """
    Run the full SEO reoptimization pipeline:
    1. Scrape target page + get Ahrefs/keyword metrics (parallel)
    2. Analyze competitors (SERP + scrape)
    3. Run gap analysis
    4. Generate AI reoptimization brief via LLM
    5. Save brief to output/
    6. Return data + AI brief
    """
    # Lazy import to avoid circular deps with page_scraper
    from app.services.page_scraper import scrape_page

    warnings: list[str] = []

    # Step 1: Parallel data collection
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

    # Step 2: Competitor analysis
    serp_results, competitors = await analyze_competitors(
        request.keyword, request.url
    )
    if not competitors:
        warnings.append("No competitor data retrieved — gap analysis will be limited.")

    # Step 3: Gap analysis
    gaps = identify_gaps(target_seo, competitors)

    # Step 4: AI reoptimization brief
    try:
        ai_brief = await generate_reoptimization_brief(
            target_seo=target_seo,
            ahrefs_metrics=ahrefs_data,
            keyword_metrics=keyword_data,
            serp_results=serp_results,
            competitors=competitors,
            gap_analysis=gaps,
            keyword=request.keyword,
            secondary_keywords=request.secondary_keywords,
            notes=request.notes,
        )
        ai_model = get_settings().openrouter_model
    except Exception as e:
        logger.error("LLM reoptimization failed: %s", e)
        ai_brief = f"AI brief generation failed: {e}"
        ai_model = "error"
        warnings.append(f"AI brief generation failed: {e}")

    # Step 5: Save AI brief to file
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_keyword = request.keyword.replace(" ", "_")[:50]
    filename = f"reopt_brief_{safe_keyword}_{timestamp}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(ai_brief)

    # Step 6: Return combined response
    return ReoptimizationBrief(
        target_url=request.url,
        keyword=request.keyword,
        target_page_seo=target_seo,
        ahrefs_metrics=ahrefs_data,
        keyword_metrics=keyword_data,
        serp_results=serp_results,
        competitors=competitors,
        gap_analysis=gaps,
        warnings=warnings,
        ai_brief=ai_brief,
        ai_model=ai_model,
        ai_markdown_path=filepath,
    )
